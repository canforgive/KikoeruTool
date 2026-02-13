"""
密码库智能清理服务
根据配置定期清理使用次数较少的密码
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import and_
from sqlalchemy.orm import Session

from ..config.settings import get_config, AppConfig
from ..models.database import PasswordEntry, PasswordCleanupLog, get_db

logger = logging.getLogger(__name__)


class PasswordCleanupService:
    """密码库智能清理服务"""
    
    _instance = None
    _scheduler: Optional[AsyncIOScheduler] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._scheduler = None
    
    async def start(self):
        """启动清理服务"""
        config = get_config().password_cleanup
        
        if not config.enabled:
            logger.info("密码库智能清理服务已禁用")
            return
        
        if self._scheduler is not None:
            logger.warning("清理服务已经在运行")
            return
        
        try:
            self._scheduler = AsyncIOScheduler()
            
            # 添加定时任务
            self._scheduler.add_job(
                self._cleanup_job,
                trigger=CronTrigger.from_crontab(config.cron_expression),
                id="password_cleanup",
                name="密码库智能清理",
                replace_existing=True
            )
            
            self._scheduler.start()
            logger.info(f"密码库智能清理服务已启动，Cron表达式: {config.cron_expression}")
            logger.info(f"清理规则: 使用次数 <= {config.max_use_count}, 保留天数 >= {config.preserve_days}")
            
            # 记录下次执行时间
            next_run = self._scheduler.get_job("password_cleanup").next_run_time
            logger.info(f"下次清理时间: {next_run}")
            
        except Exception as e:
            logger.error(f"启动密码库清理服务失败: {e}")
            self._scheduler = None
            raise
    
    async def stop(self):
        """停止清理服务"""
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("密码库智能清理服务已停止")
    
    async def restart(self):
        """重启清理服务（配置变更后调用）"""
        await self.stop()
        await self.start()
    
    async def _cleanup_job(self):
        """定时清理任务"""
        try:
            logger.info("开始执行密码库智能清理...")
            result = await self.cleanup_passwords()
            logger.info(f"密码库清理完成: 删除了 {result['deleted_count']} 个密码")
        except Exception as e:
            logger.error(f"密码库清理任务执行失败: {e}")
    
    async def cleanup_passwords(self, dry_run: bool = False) -> dict:
        """
        执行密码清理
        
        Args:
            dry_run: 如果为True，只返回将要删除的密码列表而不实际删除
        
        Returns:
            dict: 包含 deleted_count（删除数量）、deleted_passwords（删除的密码列表）、next_cleanup_time（下次清理时间）
        """
        config = get_config().password_cleanup
        
        if not config.enabled and not dry_run:
            return {
                "deleted_count": 0,
                "deleted_passwords": [],
                "message": "清理服务已禁用"
            }
        
        db = next(get_db())
        try:
            # 计算截止时间
            cutoff_date = datetime.utcnow() - timedelta(days=config.preserve_days)
            
            # 构建查询条件
            query = db.query(PasswordEntry).filter(
                and_(
                    PasswordEntry.use_count <= config.max_use_count,
                    PasswordEntry.created_at <= cutoff_date
                )
            )
            
            # 排除特定来源的密码
            if config.exclude_sources:
                query = query.filter(~PasswordEntry.source.in_(config.exclude_sources))
            
            # 获取待删除的密码
            passwords_to_delete = query.all()
            
            result = {
                "deleted_count": len(passwords_to_delete),
                "deleted_passwords": [],
                "dry_run": dry_run,
                "config": {
                    "max_use_count": config.max_use_count,
                    "preserve_days": config.preserve_days,
                    "cutoff_date": cutoff_date.isoformat()
                }
            }
            
            # 收集删除的密码信息（用于日志和返回）
            for entry in passwords_to_delete:
                password_info = {
                    "id": entry.id,
                    "password": entry.password[:3] + "***" if len(entry.password) > 3 else "***",  # 部分隐藏密码
                    "rjcode": entry.rjcode,
                    "filename": entry.filename,
                    "use_count": entry.use_count,
                    "source": entry.source,
                    "created_at": entry.created_at.isoformat() if entry.created_at else None,
                    "last_used_at": entry.last_used_at.isoformat() if entry.last_used_at else None
                }
                result["deleted_passwords"].append(password_info)
            
            if not dry_run and passwords_to_delete:
                # 执行删除
                deleted_ids = [p.id for p in passwords_to_delete]
                db.query(PasswordEntry).filter(PasswordEntry.id.in_(deleted_ids)).delete(synchronize_session=False)
                
                # 记录清理日志
                cleanup_log = PasswordCleanupLog(
                    id=str(uuid.uuid4()),
                    deleted_count=len(passwords_to_delete),
                    config_snapshot={
                        "max_use_count": config.max_use_count,
                        "preserve_days": config.preserve_days,
                        "exclude_sources": config.exclude_sources
                    },
                    deleted_passwords_summary=[
                        {"id": p["id"], "rjcode": p["rjcode"], "use_count": p["use_count"], "source": p["source"]}
                        for p in result["deleted_passwords"]
                    ]
                )
                db.add(cleanup_log)
                db.commit()
                
                logger.info(f"已删除 {len(passwords_to_delete)} 个低使用率密码")
            
            # 获取下次清理时间
            if self._scheduler and self._scheduler.get_job("password_cleanup"):
                next_run = self._scheduler.get_job("password_cleanup").next_run_time
                result["next_cleanup_time"] = next_run.isoformat() if next_run else None
            else:
                result["next_cleanup_time"] = None
            
            return result
            
        except Exception as e:
            db.rollback()
            logger.error(f"清理密码时出错: {e}")
            raise
        finally:
            db.close()
    
    async def get_cleanup_preview(self) -> dict:
        """获取清理预览（不实际删除）"""
        return await self.cleanup_passwords(dry_run=True)
    
    async def get_cleanup_history(self, limit: int = 50) -> List[dict]:
        """获取清理历史记录"""
        db = next(get_db())
        try:
            logs = db.query(PasswordCleanupLog).order_by(
                PasswordCleanupLog.created_at.desc()
            ).limit(limit).all()
            
            return [
                {
                    "id": log.id,
                    "deleted_count": log.deleted_count,
                    "config_snapshot": log.config_snapshot,
                    "deleted_passwords_summary": log.deleted_passwords_summary,
                    "created_at": log.created_at.isoformat() if log.created_at else None
                }
                for log in logs
            ]
        finally:
            db.close()
    
    def get_next_cleanup_time(self) -> Optional[datetime]:
        """获取下次清理时间"""
        if self._scheduler and self._scheduler.get_job("password_cleanup"):
            return self._scheduler.get_job("password_cleanup").next_run_time
        return None
    
    def is_running(self) -> bool:
        """检查服务是否正在运行"""
        return self._scheduler is not None and self._scheduler.running


# 全局服务实例
_cleanup_service: Optional[PasswordCleanupService] = None


def get_cleanup_service() -> PasswordCleanupService:
    """获取清理服务实例（单例）"""
    global _cleanup_service
    if _cleanup_service is None:
        _cleanup_service = PasswordCleanupService()
    return _cleanup_service


async def init_cleanup_service():
    """初始化并启动清理服务"""
    service = get_cleanup_service()
    await service.start()


async def shutdown_cleanup_service():
    """关闭清理服务"""
    service = get_cleanup_service()
    await service.stop()
