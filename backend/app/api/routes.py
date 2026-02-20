from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import asyncio
import json
import logging
import os
from pathlib import Path
import re

# Create logger instance
logger = logging.getLogger(__name__)

from ..models.database import init_db, get_db
from ..core.task_engine import TaskEngine, Task, TaskType, get_task_engine
from ..core.watcher import get_watcher
from ..core.password_cleanup import get_cleanup_service
from ..core.processed_archive_cleanup import get_processed_archive_cleanup_service
from ..config.settings import get_config

# 初始化FastAPI应用
app = FastAPI(
    title="Prekikoeru API",
    description="DLsite作品整理工具API",
    version="1.0.0"
)

# ========== 健康检查 API ==========
@app.get("/api/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "prekikoeru",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 启动事件
@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    # 初始化数据库
    init_db()

    # 启动任务引擎
    engine = get_task_engine()
    engine.start()

    # 如果配置了自动启动监视器，则启动
    config = get_config()
    if config.watcher.enabled:
        watcher = get_watcher()
        watcher.start()

    # 启动密码库智能清理服务
    cleanup_service = get_cleanup_service()
    await cleanup_service.start()

    # 启动已处理压缩包智能清理服务
    archive_cleanup_service = get_processed_archive_cleanup_service()
    await archive_cleanup_service.start()

    # 扫描已处理压缩包目录，同步数据库
    await scan_processed_archives()

# 关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行"""
    # 停止任务引擎
    engine = get_task_engine()
    engine.stop()

    # 停止监视器
    watcher = get_watcher()
    watcher.stop()

    # 停止密码库智能清理服务
    cleanup_service = get_cleanup_service()
    await cleanup_service.stop()

    # 停止已处理压缩包智能清理服务
    archive_cleanup_service = get_processed_archive_cleanup_service()
    await archive_cleanup_service.stop()

# Pydantic模型
class TaskCreate(BaseModel):
    source_path: str
    task_type: str = "auto_process"
    auto_classify: bool = True

class TaskResponse(BaseModel):
    id: str
    type: str
    status: str
    source_path: str
    output_path: Optional[str]
    progress: int
    current_step: str
    error_message: Optional[str]
    
    class Config:
        from_attributes = True

class ConfigResponse(BaseModel):
    storage: dict
    processing: dict
    watcher: dict
    filter: dict
    metadata: dict
    rename: dict
    classification: list
    password_cleanup: Optional[dict] = None
    processed_archive_cleanup: Optional[dict] = None
    path_mapping: Optional[dict] = None
    kikoeru_server: Optional[dict] = None

# API路由
@app.post("/api/tasks", response_model=TaskResponse)
async def create_task(task_create: TaskCreate):
    """创建新任务"""
    engine = get_task_engine()
    
    task_type = TaskType(task_create.task_type)
    task = Task(
        task_type=task_type,
        source_path=task_create.source_path,
        auto_classify=task_create.auto_classify
    )
    
    await engine.submit(task)
    
    return TaskResponse(
        id=task.id,
        type=task.type.value,
        status=task.status.value,
        source_path=task.source_path,
        output_path=task.output_path,
        progress=task.progress,
        current_step=task.current_step,
        error_message=task.error_message
    )

@app.get("/api/tasks", response_model=List[TaskResponse])
async def get_tasks(status: Optional[str] = None):
    """获取任务列表"""
    engine = get_task_engine()
    
    if status == "pending":
        tasks = engine.get_pending_tasks()
    elif status == "processing":
        tasks = engine.get_processing_tasks()
    elif status == "completed":
        tasks = engine.get_completed_tasks()
    else:
        tasks = engine.get_all_tasks()
    
    return [
        TaskResponse(
            id=task.id,
            type=task.type.value,
            status=task.status.value,
            source_path=task.source_path,
            output_path=task.output_path,
            progress=task.progress,
            current_step=task.current_step,
            error_message=task.error_message
        )
        for task in tasks
    ]

@app.get("/api/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """获取单个任务"""
    engine = get_task_engine()
    task = engine.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="任务未找到")
    
    return TaskResponse(
        id=task.id,
        type=task.type.value,
        status=task.status.value,
        source_path=task.source_path,
        output_path=task.output_path,
        progress=task.progress,
        current_step=task.current_step,
        error_message=task.error_message
    )

@app.post("/api/tasks/{task_id}/pause")
async def pause_task(task_id: str):
    """暂停任务"""
    engine = get_task_engine()
    engine.pause_task(task_id)
    return {"message": "任务已暂停"}

@app.post("/api/tasks/{task_id}/resume")
async def resume_task(task_id: str):
    """恢复任务"""
    engine = get_task_engine()
    engine.resume_task(task_id)
    return {"message": "任务已恢复"}

@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """取消任务"""
    engine = get_task_engine()
    engine.cancel_task(task_id)
    return {"message": "任务已取消"}

@app.get("/api/config", response_model=ConfigResponse)
async def get_configuration():
    """获取配置"""
    config = get_config()
    return ConfigResponse(
        storage=config.storage.model_dump(),
        processing=config.processing.model_dump(),
        watcher=config.watcher.model_dump(),
        filter=config.filter.model_dump(),
        metadata=config.metadata.model_dump(),
        rename=config.rename.model_dump(),
        classification=[rule.model_dump() for rule in config.classification],
        password_cleanup=config.password_cleanup.model_dump(),
        processed_archive_cleanup=config.processed_archive_cleanup.model_dump(),
        path_mapping=config.path_mapping.model_dump(),
        kikoeru_server=config.kikoeru_server.model_dump() if hasattr(config, 'kikoeru_server') else None
    )

@app.post("/api/config")
async def update_configuration(request: Request):
    """更新配置"""
    from ..config.settings import save_config, ClassificationRule, FilterRule, PathMappingRule
    try:
        config_data = await request.json()
        logger.info(f"接收到配置保存请求，classification: {config_data.get('classification')}")
        
        # 记录重命名模板用于调试
        if 'rename' in config_data and config_data['rename']:
            template = config_data['rename'].get('template', 'NOT SET')
            logger.info(f"[CONFIG SAVE] 接收到的模板: '{template}'")
        
        # 确保 classification 字段格式正确
        if 'classification' in config_data and config_data['classification']:
            validated_rules = []
            for rule_data in config_data['classification']:
                try:
                    # 清理 None 值
                    rule_data_cleaned = {k: v for k, v in rule_data.items() if v is not None}
                    # 使用 Pydantic 验证每个规则
                    rule = ClassificationRule(**rule_data_cleaned)
                    validated_rules.append(rule.dict())
                    logger.info(f"规则验证通过: {rule_data_cleaned}")
                except Exception as e:
                    logger.warning(f"分类规则验证失败: {rule_data}, 错误: {e}")
                    # 跳过无效规则
            config_data['classification'] = validated_rules
            logger.info(f"验证后的分类规则: {validated_rules}")
        
        # 确保 filter 字段格式正确
        if 'filter' in config_data and config_data['filter'] and 'rules' in config_data['filter']:
            validated_filter_rules = []
            for rule_data in config_data['filter']['rules']:
                try:
                    # 确保 target 字段存在
                    if 'target' not in rule_data or not rule_data['target']:
                        rule_data['target'] = 'file'
                    # 使用 Pydantic 验证
                    rule = FilterRule(**rule_data)
                    validated_filter_rules.append(rule.dict())
                    logger.info(f"过滤规则验证通过: {rule_data}")
                except Exception as e:
                    logger.warning(f"过滤规则验证失败: {rule_data}, 错误: {e}")
                    # 跳过无效规则
            config_data['filter']['rules'] = validated_filter_rules
            logger.info(f"验证后的过滤规则数: {len(validated_filter_rules)}")
        
        # 确保 path_mapping 字段格式正确
        if 'path_mapping' in config_data and config_data['path_mapping'] and 'rules' in config_data['path_mapping']:
            validated_path_rules = []
            for rule_data in config_data['path_mapping']['rules']:
                try:
                    rule = PathMappingRule(**rule_data)
                    validated_path_rules.append(rule.dict())
                    logger.info(f"路径映射规则验证通过: {rule_data}")
                except Exception as e:
                    logger.warning(f"路径映射规则验证失败: {rule_data}, 错误: {e}")
                    # 跳过无效规则
            config_data['path_mapping']['rules'] = validated_path_rules
            logger.info(f"验证后的路径映射规则数: {len(validated_path_rules)}")
        
        # 处理 Kikoeru 服务器配置
        if 'kikoeru_server' in config_data:
            logger.info(f"[KIKOERU] 接收到 Kikoeru 服务器配置: {config_data['kikoeru_server']}")
            try:
                # 验证 KikoeruServerConfig
                from ..config.settings import KikoeruServerConfig
                kikoeru_config = KikoeruServerConfig(**config_data['kikoeru_server'])
                config_data['kikoeru_server'] = kikoeru_config.model_dump()
                logger.info(f"[KIKOERU] 配置验证通过: enabled={kikoeru_config.enabled}, server_url={kikoeru_config.server_url}")
            except Exception as e:
                logger.error(f"[KIKOERU] Kikoeru 配置验证失败: {e}")
                # 如果验证失败，保留原始配置
        else:
            logger.info("[KIKOERU] 未接收到 Kikoeru 服务器配置")
        
        result = save_config(config_data)
        logger.info(f"配置已保存，分类规则数: {len(config_data.get('classification', []))}")

        # 重新读取配置文件确保数据已写入
        from ..config.settings import get_config
        current_config = get_config()
        logger.info(f"当前配置中的分类规则: {[r.dict() for r in current_config.classification]}")

        # 如果密码清理配置变更，重启清理服务
        if 'password_cleanup' in config_data:
            logger.info("密码清理配置已变更，重启清理服务...")
            cleanup_service = get_cleanup_service()
            await cleanup_service.restart()
            logger.info("密码清理服务已重启")

        # 如果已处理压缩包清理配置变更，重启清理服务
        if 'processed_archive_cleanup' in config_data:
            logger.info("已处理压缩包清理配置已变更，重启清理服务...")
            archive_cleanup_service = get_processed_archive_cleanup_service()
            await archive_cleanup_service.restart()
            logger.info("已处理压缩包清理服务已重启")

        return {"message": "配置已保存", "config": config_data}
    except Exception as e:
        logger.error(f"保存配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"保存配置失败: {str(e)}")

@app.post("/api/watcher/start")
async def start_watcher():
    """启动文件夹监视器"""
    watcher = get_watcher()
    watcher.start()
    return {"message": "监视器已启动"}

@app.post("/api/watcher/stop")
async def stop_watcher():
    """停止文件夹监视器"""
    watcher = get_watcher()
    watcher.stop()
    return {"message": "监视器已停止"}

@app.get("/api/watcher/status")
async def get_watcher_status():
    """获取监视器状态"""
    watcher = get_watcher()
    return {
        "is_running": watcher.is_running,
        "watch_path": get_config().storage.input_path,
        "pending_files": list(watcher.pending_files)
    }

@app.post("/api/scan")
async def scan_input_directory():
    """手动扫描输入目录"""
    import os
    from ..core.watcher import get_watcher
    from ..core.task_engine import Task, TaskType, get_task_engine
    
    config = get_config()
    input_path = config.storage.input_path
    
    # 自动创建目录（如果不存在）
    if not os.path.exists(input_path):
        try:
            os.makedirs(input_path, exist_ok=True)
            logging.info(f"自动创建输入目录: {input_path}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"无法创建输入目录: {str(e)}")
    
    found_files = []
    watcher = get_watcher()
    engine = get_task_engine()
    
    # 扫描目录
    for root, dirs, files in os.walk(input_path):
        for file in files:
            file_path = os.path.join(root, file)
            
            # 使用与监视器相同的逻辑检查文件
            is_archive = False
            if watcher.handler:
                is_archive = watcher.handler._is_archive(file_path)
            else:
                # 如果没有 handler，使用基本检查逻辑（包含魔数检测）
                from pathlib import Path as PathLib
                from ..core.watcher import ArchiveHandler
                
                # 创建临时 handler 来检测文件
                temp_handler = ArchiveHandler(lambda x: None)
                is_archive = temp_handler._is_archive(file_path)
            
            if is_archive:
                # 检查文件大小（跳过正在复制中的小文件）
                try:
                    file_size = os.path.getsize(file_path)
                    if file_size < 1024:  # 小于1KB，可能正在复制中
                        logger.warning(f"文件太小，可能正在复制中，跳过: {file_path} ({file_size} bytes)")
                        continue
                except OSError:
                    continue
                
                # 检查是否已在处理队列中
                existing = any(
                    t.source_path == file_path and t.status.value in ["pending", "processing"]
                    for t in engine.get_all_tasks()
                )
                
                if not existing and file_path not in watcher.pending_files and file_path not in watcher._processed_files:
                    found_files.append(file_path)
    
    # 为每个找到的文件创建任务
    created_tasks = []
    for file_path in found_files:
        task = Task(
            task_type=TaskType.AUTO_PROCESS,
            source_path=file_path,
            auto_classify=config.watcher.auto_classify
        )
        await engine.submit(task)
        created_tasks.append(task.id)
    
    return {
        "message": f"扫描完成，找到 {len(found_files)} 个文件",
        "found_count": len(found_files),
        "task_ids": created_tasks
    }

# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# ========== 密码库管理 API ==========

class PasswordEntryCreate(BaseModel):
    """创建密码请求模型"""
    rjcode: Optional[str] = None
    filename: Optional[str] = None
    password: str
    description: Optional[str] = None
    source: str = "manual"

class PasswordEntryUpdate(BaseModel):
    """更新密码请求模型"""
    rjcode: Optional[str] = None
    filename: Optional[str] = None
    password: Optional[str] = None
    description: Optional[str] = None

class PasswordEntryResponse(BaseModel):
    """密码响应模型"""
    id: str
    rjcode: Optional[str]
    filename: Optional[str]
    password: str
    description: Optional[str]
    source: str
    use_count: int
    last_used_at: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]

@app.get("/api/passwords", response_model=List[PasswordEntryResponse])
async def get_passwords(
    rjcode: Optional[str] = None,
    filename: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = "created_at",
    sort_order: Optional[str] = "desc"
):
    """获取密码列表，支持筛选和排序
    
    Args:
        rjcode: 按RJ号筛选
        filename: 按文件名筛选
        search: 搜索关键词
        sort_by: 排序字段（created_at, updated_at, rjcode, filename, use_count）
        sort_order: 排序方向（asc, desc）
    """
    from ..models.database import PasswordEntry, get_db
    
    db = next(get_db())
    try:
        query = db.query(PasswordEntry)
        
        if rjcode:
            query = query.filter(PasswordEntry.rjcode == rjcode)
        if filename:
            query = query.filter(PasswordEntry.filename.contains(filename))
        if search:
            query = query.filter(
                (PasswordEntry.rjcode.contains(search)) |
                (PasswordEntry.filename.contains(search)) |
                (PasswordEntry.description.contains(search))
            )
        
        # 排序功能
        valid_sort_fields = {
            "created_at": PasswordEntry.created_at,
            "updated_at": PasswordEntry.updated_at,
            "rjcode": PasswordEntry.rjcode,
            "filename": PasswordEntry.filename,
            "use_count": PasswordEntry.use_count
        }
        
        # 设置默认排序字段
        sort_field_key = sort_by if sort_by else "created_at"
        sort_field = valid_sort_fields.get(sort_field_key, PasswordEntry.created_at)
        
        # 设置默认排序方向
        order = sort_order.lower() if sort_order else "desc"
        if order == "desc":
            query = query.order_by(sort_field.desc())
        else:
            query = query.order_by(sort_field.asc())
        
        passwords = query.all()
        return [PasswordEntryResponse(**p.to_dict()) for p in passwords]
    finally:
        db.close()

@app.post("/api/passwords", response_model=PasswordEntryResponse)
async def create_password(entry: PasswordEntryCreate):
    """创建密码条目"""
    from ..models.database import PasswordEntry, get_db
    import uuid
    
    db = next(get_db())
    try:
        # 记录接收到的数据（用于调试）
        logger.info(f"创建密码条目 - RJ={entry.rjcode}, File={entry.filename}, Password长度={len(entry.password) if entry.password else 0}")
        
        # 确保密码不为空
        if not entry.password:
            raise HTTPException(status_code=400, detail="密码不能为空")
        
        # 检查是否已存在相同RJ号或文件名的密码
        existing = None
        if entry.rjcode:
            existing = db.query(PasswordEntry).filter(PasswordEntry.rjcode == entry.rjcode).first()
        if not existing and entry.filename:
            existing = db.query(PasswordEntry).filter(PasswordEntry.filename == entry.filename).first()
        
        if existing:
            # 更新现有密码
            existing.password = entry.password
            existing.description = entry.description or existing.description
            existing.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"更新密码成功: RJ={entry.rjcode}, File={entry.filename}")
            return PasswordEntryResponse(**existing.to_dict())
        
        # 创建新密码条目
        new_entry = PasswordEntry(
            id=str(uuid.uuid4()),
            rjcode=entry.rjcode,
            filename=entry.filename,
            password=entry.password,
            description=entry.description,
            source=entry.source
        )
        db.add(new_entry)
        db.commit()
        logger.info(f"创建密码成功: RJ={entry.rjcode}, File={entry.filename}")
        return PasswordEntryResponse(**new_entry.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"创建密码条目失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"保存密码失败: {str(e)}")
    finally:
        db.close()

@app.post("/api/passwords/batch")
async def batch_create_passwords(entries: List[PasswordEntryCreate]):
    """批量创建密码条目"""
    from ..models.database import PasswordEntry, get_db
    import uuid
    
    db = next(get_db())
    created_count = 0
    updated_count = 0
    
    try:
        for entry in entries:
            # 检查是否已存在
            existing = None
            if entry.rjcode:
                existing = db.query(PasswordEntry).filter(PasswordEntry.rjcode == entry.rjcode).first()
            if not existing and entry.filename:
                existing = db.query(PasswordEntry).filter(PasswordEntry.filename == entry.filename).first()
            
            if existing:
                # 更新
                existing.password = entry.password
                existing.description = entry.description or existing.description
                existing.updated_at = datetime.utcnow()
                updated_count += 1
            else:
                # 创建新条目
                new_entry = PasswordEntry(
                    id=str(uuid.uuid4()),
                    rjcode=entry.rjcode,
                    filename=entry.filename,
                    password=entry.password,
                    description=entry.description,
                    source=entry.source
                )
                db.add(new_entry)
                created_count += 1
        
        db.commit()
        logger.info(f"批量导入密码: 新建 {created_count} 条, 更新 {updated_count} 条")
        return {
            "message": f"批量导入完成",
            "created": created_count,
            "updated": updated_count
        }
    except Exception as e:
        db.rollback()
        logger.error(f"批量导入密码失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量导入失败: {str(e)}")
    finally:
        db.close()

@app.put("/api/passwords/{password_id}", response_model=PasswordEntryResponse)
async def update_password(password_id: str, entry: PasswordEntryUpdate):
    """更新密码条目"""
    from ..models.database import PasswordEntry, get_db
    
    db = next(get_db())
    try:
        password_entry = db.query(PasswordEntry).filter(PasswordEntry.id == password_id).first()
        if not password_entry:
            raise HTTPException(status_code=404, detail="密码条目不存在")
        
        if entry.rjcode is not None:
            password_entry.rjcode = entry.rjcode
        if entry.filename is not None:
            password_entry.filename = entry.filename
        if entry.password is not None:
            password_entry.password = entry.password
        if entry.description is not None:
            password_entry.description = entry.description
        
        password_entry.updated_at = datetime.utcnow()
        db.commit()
        
        return PasswordEntryResponse(**password_entry.to_dict())
    finally:
        db.close()

@app.delete("/api/passwords/{password_id}")
async def delete_password(password_id: str):
    """删除密码条目"""
    from ..models.database import PasswordEntry, get_db
    
    db = next(get_db())
    try:
        password_entry = db.query(PasswordEntry).filter(PasswordEntry.id == password_id).first()
        if not password_entry:
            raise HTTPException(status_code=404, detail="密码条目不存在")
        
        db.delete(password_entry)
        db.commit()
        return {"message": "密码已删除"}
    finally:
        db.close()

@app.get("/api/passwords/find-for-archive")
async def find_password_for_archive(archive_path: str):
    """查找适合指定压缩包的密码"""
    from ..models.database import PasswordEntry, get_db
    from pathlib import Path
    import re
    
    db = next(get_db())
    try:
        filename = Path(archive_path).name
        
        # 提取RJ号
        rj_match = re.search(r'[RVB]J(\d{6}|\d{8})(?!\d)', filename, re.IGNORECASE)
        rjcode = rj_match.group(0).upper() if rj_match else None
        
        # 首先尝试精确匹配RJ号
        if rjcode:
            entry = db.query(PasswordEntry).filter(PasswordEntry.rjcode == rjcode).first()
            if entry:
                return {
                    "found": True,
                    "password": entry.password,
                    "match_type": "rjcode",
                    "rjcode": rjcode,
                    "entry": entry.to_dict()
                }
        
        # 其次尝试文件名匹配
        entry = db.query(PasswordEntry).filter(PasswordEntry.filename == filename).first()
        if entry:
            return {
                "found": True,
                "password": entry.password,
                "match_type": "filename",
                "entry": entry.to_dict()
            }
        
        return {"found": False, "rjcode": rjcode}
    finally:
        db.close()

@app.post("/api/passwords/import-from-text")
async def import_passwords_from_text(request: Request):
    """从文本批量导入密码 - 每行一个密码，只添加密码不解析RJ号
    
    格式：每行一个密码，系统自动尝试匹配
    """
    from ..models.database import PasswordEntry, get_db
    import uuid
    
    data = await request.json()
    text = data.get("text", "")
    
    if not text.strip():
        raise HTTPException(status_code=400, detail="文本内容不能为空")
    
    db = next(get_db())
    entries = []
    lines = text.strip().split('\n')
    
    try:
        for line in lines:
            password = line.strip()
            if not password:
                continue
            
            # 检查该密码是否已存在（避免重复）
            existing = db.query(PasswordEntry).filter(PasswordEntry.password == password).first()
            if existing:
                # 密码已存在，跳过
                entries.append({"password": password, "status": "skipped", "reason": "已存在"})
            else:
                # 创建新的密码条目（只存储密码，不关联RJ号或文件名）
                entry = PasswordEntry(
                    id=str(uuid.uuid4()),
                    password=password,
                    source='batch',
                    description='批量导入'
                )
                db.add(entry)
                entries.append({"password": password, "status": "success"})
        
        db.commit()
        success_count = sum(1 for e in entries if e["status"] == "success")
        skipped_count = sum(1 for e in entries if e["status"] == "skipped")
        
        return {
            "message": f"导入完成：新建 {success_count} 个，跳过 {skipped_count} 个（已存在）",
            "imported": success_count,
            "skipped": skipped_count,
            "entries": entries
        }
    except Exception as e:
        db.rollback()
        logger.error(f"导入密码失败: {e}")
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")
    finally:
        db.close()

@app.get("/api/logs")
async def get_logs(lines: int = 100):
    """获取日志文件内容"""
    import os
    log_dir = os.environ.get('DATA_PATH', './data')
    log_file = os.path.join(log_dir, 'app.log')
    
    if not os.path.exists(log_file):
        return {"logs": []}
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            # 返回最后N行
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return {"logs": [line.strip() for line in recent_lines if line.strip()]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取日志失败: {str(e)}")

@app.get("/api/conflicts")
async def get_conflicts():
    """获取问题作品列表"""
    from ..models.database import ConflictWork, get_db
    
    db = next(get_db())
    try:
        conflicts = db.query(ConflictWork).filter(ConflictWork.status == 'PENDING').all()
        return {
            "conflicts": [
                {
                    "id": c.id,
                    "rjcode": c.rjcode,
                    "conflict_type": c.conflict_type,
                    "existing_path": c.existing_path,
                    "new_path": c.new_path,
                    "new_metadata": c.new_metadata,
                    "status": c.status,
                    "created_at": c.created_at.isoformat() if c.created_at else None
                }
                for c in conflicts
            ]
        }
    finally:
        db.close()

@app.post("/api/conflicts/{conflict_id}/resolve")
async def resolve_conflict(conflict_id: str, action: dict):
    """处理问题作品"""
    from ..models.database import ConflictWork, ProcessedArchive, get_db
    from ..core.extract_service import ExtractService
    from ..core.filter_service import FilterService
    from ..core.metadata_service import MetadataService
    from ..core.classifier import SmartClassifier
    from ..core.task_engine import Task, TaskType
    import shutil
    import re
    
    db = next(get_db())
    try:
        conflict = db.query(ConflictWork).filter(ConflictWork.id == conflict_id).first()
        if not conflict:
            raise HTTPException(status_code=404, detail="问题作品不存在")
        
        action_type = action.get("action")
        config = get_config()
        
        # 检查new_path是否是压缩包（预检阶段的冲突）
        from ..core.watcher import ArchiveHandler
        temp_handler = ArchiveHandler(lambda x: None)
        is_archive = temp_handler._is_archive(conflict.new_path)
        
        if action_type == "KEEP_NEW":
            # 删除旧版本
            if os.path.exists(conflict.existing_path):
                shutil.rmtree(conflict.existing_path)
            
            if is_archive:
                # 如果是压缩包，需要先解压
                logger.info(f"保留新版：先解压压缩包 {conflict.new_path}")
                
                # 检查文件是否已经在 processed 目录中（重新解压的情况）
                is_in_processed = conflict.new_path.startswith(config.storage.processed_archives_path)
                if is_in_processed:
                    logger.info(f"检测到文件已在 processed 目录中，设置 skip_archive=True: {conflict.new_path}")
                
                # 创建临时任务用于解压
                task = Task(
                    task_type=TaskType.AUTO_PROCESS,
                    source_path=conflict.new_path,
                    auto_classify=True,
                    skip_archive=is_in_processed  # 如果在 processed 目录中，跳过归档
                )
                
                # 解压
                extract_service = ExtractService()
                filter_service = FilterService()
                metadata_service = MetadataService()
                classifier = SmartClassifier()
                
                extracted_path = await extract_service.extract(task)
                if not extracted_path:
                    # 解压失败（通常是密码错误），任务状态已被设置为 failed
                    error_msg = task.error_message or "解压失败"
                    logger.error(f"处理冲突失败: {error_msg}")
                    return {"success": False, "error": error_msg}
                
                # 获取元数据
                metadata = await metadata_service.fetch(extracted_path, task)
                task.task_metadata = metadata  # 设置元数据到任务对象
                
                # 重命名文件夹
                from app.core.rename_service import RenameService
                rename_service = RenameService()
                renamed_path = await rename_service.rename(extracted_path, task)
                
                # 过滤（在重命名后的文件夹上进行）
                await filter_service.filter(renamed_path, task)
                
                # 扁平化单层文件夹（在过滤之后，移动之前）
                if config.rename.flatten_single_subfolder:
                    renamed_path = rename_service._flatten_single_subfolder(renamed_path)
                    logger.info(f"保留新版 - 扁平化后路径: {renamed_path}")

                # 移除空文件夹（在扁平化之后）
                if config.rename.remove_empty_folders:
                    rename_service.remove_empty_folders(renamed_path, remove_root=False)

                # 移动到正确位置
                final_path = await classifier.classify_and_move(renamed_path, metadata, task)
                
                # 归档压缩包到 processed 目录（不要删除，以便将来重新处理）
                from app.core.task_engine import TaskEngine
                engine = TaskEngine()
                await engine._archive_source_file(task)
                
                logger.info(f"保留新版完成：已解压并移动到 {final_path}，压缩包已归档")
                
                # 更新 ProcessedArchive 状态为 completed
                if is_in_processed:
                    filename = os.path.basename(conflict.new_path)
                    archive_record = db.query(ProcessedArchive).filter(
                        ProcessedArchive.filename == filename
                    ).first()
                    if archive_record:
                        archive_record.status = 'completed'
                        archive_record.processed_at = datetime.utcnow()
                        db.commit()
                        logger.info(f"冲突解决后更新 ProcessedArchive 状态为 completed: {filename}")
            else:
                # 如果是已解压的文件夹，直接移动
                if os.path.exists(conflict.new_path):
                    target_path = os.path.join(config.storage.library_path, os.path.basename(conflict.new_path))
                    shutil.move(conflict.new_path, target_path)
                    logger.info(f"保留新版完成：已移动到 {target_path}")
            
            conflict.status = "KEEP_NEW"
            
        elif action_type == "KEEP_OLD":
            # 删除新版本
            if os.path.exists(conflict.new_path):
                if os.path.isfile(conflict.new_path):
                    os.remove(conflict.new_path)  # 删除压缩包
                else:
                    shutil.rmtree(conflict.new_path)  # 删除文件夹
            # 更新 ProcessedArchive 状态为 completed（用户选择保留旧版，新版任务结束）
            if is_archive:
                filename = os.path.basename(conflict.new_path)
                archive_record = db.query(ProcessedArchive).filter(
                    ProcessedArchive.filename == filename
                ).first()
                if archive_record:
                    archive_record.status = 'completed'
                    archive_record.processed_at = datetime.utcnow()
                    db.commit()
                    logger.info(f"冲突解决后更新 ProcessedArchive 状态为 completed (KEEP_OLD): {filename}")
            
            conflict.status = "KEEP_OLD"
            
        elif action_type == "MERGE":
            # 合并：保留两个版本，新版本加编号
            if is_archive:
                logger.info(f"合并：先解压压缩包 {conflict.new_path}")
                task = Task(
                    task_type=TaskType.AUTO_PROCESS,
                    source_path=conflict.new_path,
                    auto_classify=True
                )
                
                extract_service = ExtractService()
                filter_service = FilterService()
                metadata_service = MetadataService()
                classifier = SmartClassifier()
                
                extracted_path = await extract_service.extract(task)
                if extracted_path:
                    await filter_service.filter(extracted_path, task)
                    metadata = await metadata_service.fetch(extracted_path, task)
                    
                    # 修改metadata使文件夹名加编号
                    rjcode = metadata.get('rjcode', '')
                    target_base = os.path.join(config.storage.library_path, conflict.rjcode)
                    counter = 1
                    while os.path.exists(f"{target_base}({counter})"):
                        counter += 1
                    metadata['work_name'] = f"{metadata.get('work_name', '')}({counter})"
                    
                    final_path = await classifier.classify_and_move(extracted_path, metadata, task)
                    os.remove(conflict.new_path)
                    logger.info(f"合并完成：新版本已保存为 {final_path}")
                    
                    # 更新 ProcessedArchive 状态为 completed
                    filename = os.path.basename(conflict.new_path)
                    archive_record = db.query(ProcessedArchive).filter(
                        ProcessedArchive.filename == filename
                    ).first()
                    if archive_record:
                        archive_record.status = 'completed'
                        archive_record.processed_at = datetime.utcnow()
                        db.commit()
                        logger.info(f"冲突解决后更新 ProcessedArchive 状态为 completed: {filename}")
            
            conflict.status = "MERGE"
            
        elif action_type == "SKIP":
            # 跳过，删除新版本
            if os.path.exists(conflict.new_path):
                if os.path.isfile(conflict.new_path):
                    os.remove(conflict.new_path)
                else:
                    shutil.rmtree(conflict.new_path)
            # 更新 ProcessedArchive 状态为 completed（用户选择跳过，任务结束）
            if is_archive:
                filename = os.path.basename(conflict.new_path)
                archive_record = db.query(ProcessedArchive).filter(
                    ProcessedArchive.filename == filename
                ).first()
                if archive_record:
                    archive_record.status = 'completed'
                    archive_record.processed_at = datetime.utcnow()
                    db.commit()
                    logger.info(f"冲突解决后更新 ProcessedArchive 状态为 completed (SKIP): {filename}")
            
            conflict.status = "SKIP"
        
        # 更新关联任务的状态
        if conflict.task_id:
            engine = get_task_engine()
            from ..core.task_engine import TaskStatus
            engine.update_task_status(
                conflict.task_id, 
                TaskStatus.COMPLETED,
                f"问题作品已处理: {action_type}"
            )
        
        db.commit()
        return {"message": "处理成功"}
        
    except Exception as e:
        db.rollback()
        logger.error(f"处理冲突失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

async def scan_processed_archives():
    """启动时扫描已处理压缩包目录，同步数据库"""
    import os
    import re
    from datetime import datetime
    from ..models.database import ProcessedArchive, get_db
    from ..config.settings import get_config
    import uuid
    
    config = get_config()
    processed_dir = config.storage.processed_archives_path
    
    if not os.path.exists(processed_dir):
        logger.info(f"已处理压缩包目录不存在: {processed_dir}")
        return
    
    logger.info(f"开始扫描已处理压缩包目录: {processed_dir}")
    
    db = next(get_db())
    try:
        # 清理重复记录（保留最新的）
        all_archives = db.query(ProcessedArchive).order_by(ProcessedArchive.processed_at.desc()).all()
        seen_filenames = {}
        duplicates = []
        for archive in all_archives:
            if archive.filename in seen_filenames:
                duplicates.append(archive)
            else:
                seen_filenames[archive.filename] = archive
        
        if duplicates:
            logger.info(f"发现 {len(duplicates)} 个重复记录，正在清理...")
            for dup in duplicates:
                db.delete(dup)
            db.commit()
            logger.info("重复记录清理完成")
        
        # 重新获取清理后的记录
        db_archives = {a.filename: a for a in db.query(ProcessedArchive).all()}
        
        # 扫描目录中的文件
        found_files = []
        for filename in os.listdir(processed_dir):
            file_path = os.path.join(processed_dir, filename)
            if os.path.isfile(file_path):
                found_files.append(filename)
                file_size = os.path.getsize(file_path)
                
                # 提取RJ号
                rjcode = None
                match = re.search(r'[RVB]J(\d{6}|\d{8})(?!\d)', filename, re.IGNORECASE)
                if match:
                    rjcode = match.group(0).upper()
                
                if filename in db_archives:
                    # 更新现有记录（只更新路径和大小，不更新时间）
                    archive = db_archives[filename]
                    archive.current_path = file_path
                    archive.file_size = file_size
                    # 注意：不要在这里更新 processed_at，扫描只是同步文件状态，不是重新处理
                    logger.info(f"更新已处理压缩包记录路径: {filename}")
                else:
                    # 创建新记录
                    new_archive = ProcessedArchive(
                        id=str(uuid.uuid4()),
                        original_path=file_path,
                        current_path=file_path,
                        filename=filename,
                        rjcode=rjcode or '',
                        file_size=file_size,
                        processed_at=datetime.utcnow(),
                        process_count=1,
                        task_id='',
                        status='completed'
                    )
                    db.add(new_archive)
                    logger.info(f"添加新的已处理压缩包记录: {filename}")
        
        # 清理数据库中不存在的记录
        for filename, archive in list(db_archives.items()):
            if filename not in found_files:
                archive_path = os.path.join(processed_dir, filename)
                if not os.path.exists(archive_path):
                    logger.info(f"删除不存在的压缩包记录: {filename}")
                    db.delete(archive)
        
        db.commit()
        logger.info(f"已处理压缩包目录扫描完成，共发现 {len(found_files)} 个文件")
        
    except Exception as e:
        logger.error(f"扫描已处理压缩包目录失败: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

# 已处理压缩包API
@app.post("/api/processed-archives/scan")
async def scan_processed_archives_api():
    """手动触发扫描已处理压缩包目录"""
    try:
        await scan_processed_archives()
        return {"message": "扫描完成"}
    except Exception as e:
        logger.error(f"手动扫描失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"扫描失败: {str(e)}")

@app.get("/api/processed-archives")
async def get_processed_archives(
    search: Optional[str] = None,
    sort_by: Optional[str] = "processed_at",
    sort_order: Optional[str] = "desc"
):
    """获取已处理压缩包列表，支持搜索和排序
    
    Args:
        search: 搜索关键词（匹配RJ号、文件名）
        sort_by: 排序字段（rjcode, file_size, process_count, status, processed_at）
        sort_order: 排序方向（asc, desc）
    """
    from ..models.database import ProcessedArchive, get_db
    
    db = next(get_db())
    try:
        query = db.query(ProcessedArchive)
        
        # 搜索功能
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (ProcessedArchive.rjcode.contains(search)) |
                (ProcessedArchive.filename.contains(search))
            )
        
        # 排序功能
        valid_sort_fields = {
            "rjcode": ProcessedArchive.rjcode,
            "file_size": ProcessedArchive.file_size,
            "process_count": ProcessedArchive.process_count,
            "status": ProcessedArchive.status,
            "processed_at": ProcessedArchive.processed_at
        }
        
        sort_field = valid_sort_fields.get(sort_by, ProcessedArchive.processed_at)
        
        if sort_order.lower() == "desc":
            query = query.order_by(sort_field.desc())
        else:
            query = query.order_by(sort_field.asc())
        
        archives = query.all()
        return {
            "archives": [archive.to_dict() for archive in archives]
        }
    finally:
        db.close()

@app.post("/api/processed-archives/{archive_id}/reprocess")
async def reprocess_archive(archive_id: str):
    """重新处理已归档的压缩包"""
    from ..models.database import ProcessedArchive, get_db
    
    db = next(get_db())
    try:
        archive = db.query(ProcessedArchive).filter(ProcessedArchive.id == archive_id).first()
        if not archive:
            raise HTTPException(status_code=404, detail="压缩包记录不存在")
        
        # 检查文件是否还存在
        if not os.path.exists(archive.current_path):
            raise HTTPException(status_code=404, detail="压缩包文件不存在，可能已被删除")
        
        # 直接从 processed 目录解压，避免复制到 SSD
        logger.info(f"直接从 processed 目录重新解压: {archive.current_path}")
        
        # 创建新任务（标记为重新处理，直接从 processed 目录解压）
        engine = get_task_engine()
        task = Task(
            task_type=TaskType.AUTO_PROCESS,
            source_path=archive.current_path,  # 直接使用 processed 目录中的文件
            auto_classify=get_config().watcher.auto_classify,
            skip_archive=True  # 标记跳过归档（因为文件已在 processed 目录）
        )
        await engine.submit(task)
        
        # 更新记录状态和重新处理时间
        archive.status = 'reprocessing'
        archive.processed_at = datetime.utcnow()
        archive.process_count = (archive.process_count or 0) + 1
        db.commit()
        
        return {
            "message": "已创建重新处理任务",
            "task_id": task.id,
            "filename": archive.filename,
            "rjcode": archive.rjcode
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重新处理压缩包失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"重新处理失败: {str(e)}")
    finally:
        db.close()

# 库存管理API
@app.get("/api/library/files")
async def get_library_files():
    """获取库内所有文件（只扫描前两级目录）"""
    try:
        config = get_config()
        library_path = config.storage.library_path
        
        if not os.path.exists(library_path):
            return {"files": []}
        
        items = []
        item_id = 0
        
        # 只遍历前两级目录
        for item in os.listdir(library_path):
            item_path = os.path.join(library_path, item)
            
            # 跳过冲突文件夹和隐藏文件
            if item.startswith('_') or item.startswith('.'):
                continue
            
            # 如果是文件夹（如 RJ012xxxxx），遍历其子目录
            if os.path.isdir(item_path):
                for subitem in os.listdir(item_path):
                    subitem_path = os.path.join(item_path, subitem)
                    
                    # 跳过隐藏文件
                    if subitem.startswith('.'):
                        continue
                    
                    try:
                        stat = os.stat(subitem_path)
                        # 提取RJ号
                        rj_match = re.search(r'[RVB]J(\d{6}|\d{8})(?!\d)', subitem, re.IGNORECASE)
                        rjcode = rj_match.group(0).upper() if rj_match else None
                        
                        items.append({
                            "id": str(item_id),
                            "name": subitem,
                            "path": subitem_path,
                            "rjcode": rjcode,
                            "size": stat.st_size if os.path.isfile(subitem_path) else 0,
                            "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            "is_directory": os.path.isdir(subitem_path)
                        })
                        item_id += 1
                    except Exception as e:
                        logger.warning(f"获取项目信息失败: {subitem_path}, {e}")
            else:
                # 根目录下的文件
                try:
                    stat = os.stat(item_path)
                    rj_match = re.search(r'[RVB]J(\d{6}|\d{8})(?!\d)', item, re.IGNORECASE)
                    rjcode = rj_match.group(0).upper() if rj_match else None
                    
                    items.append({
                        "id": str(item_id),
                        "name": item,
                        "path": item_path,
                        "rjcode": rjcode,
                        "size": stat.st_size,
                        "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "is_directory": False
                    })
                    item_id += 1
                except Exception as e:
                    logger.warning(f"获取项目信息失败: {item_path}, {e}")
        
        # 按修改时间排序（最新的在前）
        items.sort(key=lambda x: x["modified_time"], reverse=True)
        
        return {"files": items}
        
    except Exception as e:
        logger.error(f"获取库文件失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取库文件失败: {str(e)}")

@app.post("/api/library/rename")
async def rename_library_file(request: Request):
    """重命名库内文件或文件夹"""
    try:
        data = await request.json()
        old_path = data.get("path")
        new_name = data.get("new_name")
        
        if not old_path or not new_name:
            raise HTTPException(status_code=400, detail="缺少必要参数")
        
        if not os.path.exists(old_path):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 构建新路径
        parent_dir = os.path.dirname(old_path)
        new_path = os.path.join(parent_dir, new_name)
        
        # 检查新名称是否已存在
        if os.path.exists(new_path):
            raise HTTPException(status_code=400, detail="新名称已存在")
        
        # 执行重命名
        os.rename(old_path, new_path)
        logger.info(f"重命名成功: {old_path} -> {new_path}")
        
        return {"message": "重命名成功", "new_path": new_path}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重命名失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"重命名失败: {str(e)}")

@app.post("/api/library/api-rename")
async def api_rename_library_file(request: Request):
    """使用API重新获取元数据并重命名"""
    try:
        data = await request.json()
        file_path = data.get("path")
        
        if not file_path:
            raise HTTPException(status_code=400, detail="缺少文件路径")
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 提取RJ号
        import re
        rj_match = re.search(r'[RVB]J\d{6,8}', os.path.basename(file_path), re.IGNORECASE)
        if not rj_match:
            raise HTTPException(status_code=400, detail="无法从文件名提取RJ号")
        
        rjcode = rj_match.group(0).upper()
        logger.info(f"API重新命名: {file_path}, RJ号: {rjcode}")
        
        # 获取元数据（强制刷新，不使用缓存）
        from ..core.metadata_service import MetadataService
        from ..models.database import WorkMetadata as WorkMetadataModel, get_db
        metadata_service = MetadataService()
        
        try:
            # 清除该RJ号的缓存（强制重新获取）
            db = next(get_db())
            try:
                deleted_count = db.query(WorkMetadataModel).filter(
                    WorkMetadataModel.rjcode == rjcode
                ).delete()
                db.commit()
                if deleted_count > 0:
                    logger.info(f"[{rjcode}] 已清除缓存，准备重新获取元数据")
                else:
                    logger.info(f"[{rjcode}] 无缓存，将直接获取元数据")
            except Exception as e:
                logger.warning(f"[{rjcode}] 清除缓存失败: {e}")
                db.rollback()
            finally:
                db.close()
            
            # 创建临时任务对象（用于进度更新，虽然这里不需要）
            from ..core.task_engine import Task, TaskType
            temp_task = Task(
                task_type=TaskType.METADATA,
                source_path=file_path
            )
            
            metadata = await metadata_service.fetch(file_path, temp_task)
            logger.info(f"获取到元数据: {metadata}")
        except Exception as e:
            logger.error(f"获取元数据失败: {e}")
            raise HTTPException(status_code=500, detail=f"获取元数据失败: {str(e)}")
        
        # 生成新名称
        work_name = metadata.get('work_name', '')
        if not work_name:
            raise HTTPException(status_code=500, detail="获取到的作品名称为空")
        
        config = get_config()
        logger.info(f"[API RENAME] 读取到的模板: '{config.rename.template}' (长度: {len(config.rename.template)})")
        logger.info(f"[API RENAME] api_rename_follow_template: {config.rename.api_rename_follow_template}")
        
        # 根据配置决定是否遵循重命名模板
        if config.rename.api_rename_follow_template:
            # 使用重命名服务生成名称
            from ..core.rename_service import RenameService
            rename_service = RenameService()
            
            # 创建临时任务对象用于重命名
            from ..core.task_engine import Task, TaskType
            temp_task = Task(
                task_type=TaskType.RENAME,
                source_path=file_path
            )
            temp_task.task_metadata = metadata
            
            # 编译名称
            new_name = rename_service._compile_name(metadata)
            new_name = rename_service._sanitize_filename(new_name)
            logger.info(f"[{rjcode}] 使用重命名模板生成名称: {new_name}")
        else:
            # 简单格式：RJ号 + 作品名
            import re
            def sanitize_filename(name):
                # 移除或替换Windows不允许的字符
                name = re.sub(r'[<>:"/\\|?*]', '_', name)
                # 移除控制字符
                name = re.sub(r'[\x00-\x1f\x7f]', '', name)
                # 移除末尾的空格和点
                name = name.rstrip(' .')
                return name
            
            new_name = f"{rjcode} {sanitize_filename(work_name)}"
            logger.info(f"[{rjcode}] 使用简单格式生成名称: {new_name}")
        
        # 构建新路径
        parent_dir = os.path.dirname(file_path)
        new_path = os.path.join(parent_dir, new_name)
        
        # 检查新名称是否已存在
        if os.path.exists(new_path) and new_path != file_path:
            raise HTTPException(status_code=400, detail="新名称已存在")
        
        if new_path == file_path:
            return {"message": "名称已是最新，无需重命名", "name": new_name}
        
        # 执行重命名
        os.rename(file_path, new_path)
        logger.info(f"API重命名成功: {file_path} -> {new_path}")
        
        return {
            "message": "API重命名成功",
            "old_name": os.path.basename(file_path),
            "new_name": new_name,
            "path": new_path,
            "metadata": metadata
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API重命名失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"API重命名失败: {str(e)}")

def map_path_to_local(remote_path: str) -> tuple[str, bool]:
    """
    将远程路径映射到本地路径
    返回: (映射后的路径, 是否成功映射)
    """
    config = get_config()
    if not config.path_mapping.enabled:
        return remote_path, False
    
    # 统一路径分隔符为 /
    remote_path_normalized = remote_path.replace("\\", "/")
    
    for rule in config.path_mapping.rules:
        if not rule.enabled:
            continue
        
        # 统一规则路径分隔符
        rule_remote = rule.remote_path.replace("\\", "/")
        
        # 检查路径是否匹配
        if remote_path_normalized.startswith(rule_remote):
            # 替换前缀
            relative_path = remote_path_normalized[len(rule_remote):]
            # 移除开头的 / 或 \
            relative_path = relative_path.lstrip("/\\")
            
            # 组合成本地路径
            local_path = os.path.join(rule.local_path, relative_path)
            return local_path, True
    
    return remote_path, False

@app.post("/api/library/delete")
async def delete_library_file(request: Request):
    """删除库内文件或文件夹（需要确认）"""
    try:
        data = await request.json()
        file_path = data.get("path")
        confirmed = data.get("confirmed", False)
        
        if not file_path:
            raise HTTPException(status_code=400, detail="缺少文件路径")
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 安全检查：确保在库目录内
        config = get_config()
        library_path = config.storage.library_path
        if not file_path.startswith(library_path):
            raise HTTPException(status_code=403, detail="只能删除库内的文件")
        
        if not confirmed:
            # 返回需要确认的信息
            import shutil
            if os.path.isdir(file_path):
                # 计算文件夹大小
                total_size = 0
                for dirpath, dirnames, filenames in os.walk(file_path):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        total_size += os.path.getsize(fp)
                return {
                    "need_confirm": True,
                    "type": "folder",
                    "name": os.path.basename(file_path),
                    "path": file_path,
                    "size": total_size
                }
            else:
                return {
                    "need_confirm": True,
                    "type": "file",
                    "name": os.path.basename(file_path),
                    "path": file_path,
                    "size": os.path.getsize(file_path)
                }
        
        # 执行删除
        import shutil
        if os.path.isdir(file_path):
            shutil.rmtree(file_path)
            logger.info(f"删除文件夹: {file_path}")
        else:
            os.remove(file_path)
            logger.info(f"删除文件: {file_path}")
        
        return {"message": "删除成功", "path": file_path}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

@app.post("/api/library/open-folder")
async def open_library_folder(request: Request):
    """打开文件夹位置"""
    try:
        data = await request.json()
        path = data.get("path")
        force_local = data.get("force_local", False)  # 是否强制使用本地映射
        
        if not path:
            raise HTTPException(status_code=400, detail="路径不能为空")
        
        # 检查路径映射配置
        config = get_config()
        mapped_path, is_mapped = map_path_to_local(path)
        
        # 判断打开模式
        open_mode = config.path_mapping.open_mode
        if force_local or open_mode == "mapped":
            # 使用映射路径打开
            target_path = mapped_path
            # 在映射模式下，不检查路径是否存在（因为后端无法访问客户端路径）
            logger.info(f"使用映射路径打开: {path} -> {target_path}")
            
            return {
                "message": "请使用本地路径打开",
                "mode": "mapped",
                "original_path": path,
                "mapped_path": target_path,
                "is_mapped": is_mapped
            }
        
        # 直接模式：后端直接打开（同设备部署）
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="路径不存在")
        
        # 获取文件夹路径（如果是文件，则获取所在文件夹）
        folder_path = path if os.path.isdir(path) else os.path.dirname(path)
        
        # 根据操作系统打开文件夹
        import platform
        import subprocess
        
        system = platform.system()
        if system == "Windows":
            # 使用 os.startfile 打开文件夹，更好地支持中文和特殊字符
            if os.path.isdir(path):
                # 如果是文件夹，直接打开
                os.startfile(path)
            else:
                # 如果是文件，使用 explorer /select 选中它
                # 使用字符串形式避免引号问题
                cmd = f'explorer /select,"{path}"'
                subprocess.run(cmd, shell=True, check=True)
        elif system == "Darwin":  # macOS
            subprocess.run(["open", "-R", path], check=True)
        else:  # Linux
            subprocess.run(["xdg-open", folder_path], check=True)
        
        return {"message": "已打开文件夹", "mode": "direct"}
        
    except Exception as e:
        logger.error(f"打开文件夹失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"打开文件夹失败: {str(e)}")

# 路径映射配置API
@app.get("/api/path-mapping/config")
async def get_path_mapping_config():
    """获取路径映射配置"""
    config = get_config().path_mapping
    return {
        "enabled": config.enabled,
        "open_mode": config.open_mode,
        "rules": [
            {
                "remote_path": rule.remote_path,
                "local_path": rule.local_path,
                "enabled": rule.enabled
            }
            for rule in config.rules
        ]
    }

@app.post("/api/path-mapping/config")
async def update_path_mapping_config(request: Request):
    """更新路径映射配置"""
    try:
        data = await request.json()
        config = get_config()
        
        # 更新配置
        config.path_mapping.enabled = data.get("enabled", config.path_mapping.enabled)
        config.path_mapping.open_mode = data.get("open_mode", config.path_mapping.open_mode)
        
        # 更新规则
        if "rules" in data:
            from app.config.settings import PathMappingRule
            config.path_mapping.rules = [
                PathMappingRule(**rule) for rule in data["rules"]
            ]
        
        # 保存配置
        save_config(config)
        
        return {"message": "路径映射配置已更新"}
        
    except Exception as e:
        logger.error(f"更新路径映射配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")

@app.post("/api/path-mapping/test")
async def test_path_mapping(request: Request):
    """测试路径映射"""
    try:
        data = await request.json()
        remote_path = data.get("path")
        
        if not remote_path:
            raise HTTPException(status_code=400, detail="路径不能为空")
        
        mapped_path, is_mapped = map_path_to_local(remote_path)
        
        return {
            "original_path": remote_path,
            "mapped_path": mapped_path,
            "is_mapped": is_mapped
        }
        
    except Exception as e:
        logger.error(f"测试路径映射失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"测试失败: {str(e)}")

# 密码库智能清理API
@app.get("/api/password-cleanup/status")
async def get_cleanup_status():
    """获取清理服务状态"""
    service = get_cleanup_service()
    config = get_config().password_cleanup

    return {
        "enabled": config.enabled,
        "is_running": service.is_running(),
        "cron_expression": config.cron_expression,
        "max_use_count": config.max_use_count,
        "preserve_days": config.preserve_days,
        "exclude_sources": config.exclude_sources,
        "next_cleanup_time": service.get_next_cleanup_time().isoformat() if service.get_next_cleanup_time() else None
    }

@app.get("/api/password-cleanup/preview")
async def preview_cleanup():
    """预览将要清理的密码（不实际删除）"""
    service = get_cleanup_service()
    result = await service.get_cleanup_preview()
    return result

@app.post("/api/password-cleanup/run")
async def run_cleanup():
    """手动执行清理"""
    service = get_cleanup_service()
    result = await service.cleanup_passwords(dry_run=False)
    return result

@app.get("/api/password-cleanup/history")
async def get_cleanup_history(limit: int = 50):
    """获取清理历史记录"""
    service = get_cleanup_service()
    history = await service.get_cleanup_history(limit=limit)
    return {
        "history": history,
        "total": len(history)
    }

@app.post("/api/password-cleanup/restart")
async def restart_cleanup_service():
    """重启清理服务（配置变更后调用）"""
    service = get_cleanup_service()
    await service.restart()
    return {
        "message": "密码库清理服务已重启",
        "status": await get_cleanup_status()
    }

# 已处理压缩包智能清理API
@app.get("/api/processed-archive-cleanup/status")
async def get_archive_cleanup_status():
    """获取已处理压缩包清理服务状态"""
    service = get_processed_archive_cleanup_service()
    config = get_config().processed_archive_cleanup

    return {
        "enabled": config.enabled,
        "is_running": service.is_running(),
        "cron_expression": config.cron_expression,
        "strategy": config.strategy,
        "preserve_days": config.preserve_days,
        "max_count": config.max_count,
        "max_size_gb": config.max_size_gb,
        "exclude_reprocessing": config.exclude_reprocessing,
        "next_cleanup_time": service.get_next_cleanup_time().isoformat() if service.get_next_cleanup_time() else None
    }

@app.get("/api/processed-archive-cleanup/preview")
async def preview_archive_cleanup():
    """预览将要清理的已处理压缩包（不实际删除）"""
    service = get_processed_archive_cleanup_service()
    result = await service.get_cleanup_preview()
    return result

@app.post("/api/processed-archive-cleanup/run")
async def run_archive_cleanup():
    """手动执行已处理压缩包清理"""
    service = get_processed_archive_cleanup_service()
    result = await service.cleanup_archives(dry_run=False)
    return result

@app.get("/api/processed-archive-cleanup/history")
async def get_archive_cleanup_history(limit: int = 50):
    """获取已处理压缩包清理历史记录"""
    service = get_processed_archive_cleanup_service()
    history = await service.get_cleanup_history(limit=limit)
    return {
        "history": history,
        "total": len(history)
    }

@app.post("/api/processed-archive-cleanup/restart")
async def restart_archive_cleanup_service():
    """重启已处理压缩包清理服务（配置变更后调用）"""
    service = get_processed_archive_cleanup_service()
    await service.restart()
    return {
        "message": "已处理压缩包清理服务已重启",
        "status": await get_archive_cleanup_status()
    }

# ========== 已存在文件夹处理 API ==========

class ExistingFolderResponse(BaseModel):
    """已存在文件夹响应模型"""
    name: str
    path: str
    rjcode: Optional[str]
    modified_time: str
    size: int
    is_directory: bool

@app.get("/api/existing-folders", response_model=List[ExistingFolderResponse])
async def get_existing_folders():
    """获取已存在文件夹目录中的所有文件夹"""
    try:
        config = get_config()
        existing_folders_path = config.storage.existing_folders_path
        
        # 如果目录不存在，返回空列表
        if not os.path.exists(existing_folders_path):
            return []
        
        folders = []
        for item in os.listdir(existing_folders_path):
            item_path = os.path.join(existing_folders_path, item)
            
            # 跳过隐藏文件和非文件夹项目
            if item.startswith('.') or not os.path.isdir(item_path):
                continue
            
            try:
                stat = os.stat(item_path)
                # 提取RJ号
                rj_match = re.search(r'[RVB]J(\d{6}|\d{8})(?!\d)', item, re.IGNORECASE)
                rjcode = rj_match.group(0).upper() if rj_match else None
                
                # 计算文件夹大小（简化版，只统计直接子项）
                size = 0
                try:
                    for subitem in os.listdir(item_path):
                        subitem_path = os.path.join(item_path, subitem)
                        if os.path.isfile(subitem_path):
                            size += os.path.getsize(subitem_path)
                except:
                    pass
                
                folders.append(ExistingFolderResponse(
                    name=item,
                    path=item_path,
                    rjcode=rjcode,
                    modified_time=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    size=size,
                    is_directory=True
                ))
            except Exception as e:
                logger.warning(f"获取文件夹信息失败: {item_path}, {e}")
        
        # 按修改时间排序（最新的在前）
        folders.sort(key=lambda x: x.modified_time, reverse=True)
        
        return folders
        
    except Exception as e:
        logger.error(f"获取已存在文件夹列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")

@app.post("/api/existing-folders/scan")
async def scan_existing_folders(check_duplicates: bool = True, force_refresh: bool = False):
    """扫描已存在文件夹目录，先快速列出所有文件夹，再后台查重
    
    Args:
        check_duplicates: 是否执行查重检查
        force_refresh: 是否强制刷新缓存
    """
    async def generate_folders():
        try:
            config = get_config()
            existing_folders_path = config.storage.existing_folders_path
            
            # 自动创建目录（如果不存在）
            if not os.path.exists(existing_folders_path):
                try:
                    os.makedirs(existing_folders_path, exist_ok=True)
                    logger.info(f"自动创建已存在文件夹目录: {existing_folders_path}")
                except Exception as e:
                    yield json.dumps({"error": f"无法创建目录: {str(e)}"}) + "\n"
                    return
            
            # 第一步：快速列出所有文件夹（不查重）
            items = os.listdir(existing_folders_path)
            folders = []
            
            yield json.dumps({
                "type": "start",
                "total": len(items),
                "message": f"开始扫描，共 {len(items)} 个项目"
            }) + "\n"
            
            # 先发送所有文件夹基本信息（立即可见）
            for index, item in enumerate(items):
                item_path = os.path.join(existing_folders_path, item)
                
                # 跳过隐藏文件和非文件夹项目
                if item.startswith('.') or not os.path.isdir(item_path):
                    continue
                
                # 提取RJ号
                rj_match = re.search(r'[RVB]J(\d{6}|\d{8})(?!\d)', item, re.IGNORECASE)
                rjcode = rj_match.group(0).upper() if rj_match else None
                
                folder_info = {
                    "name": item,
                    "path": item_path,
                    "rjcode": rjcode,
                    "status": "pending"  # 待检查状态
                }
                
                folders.append(folder_info)
                
                # 立即发送，让前端显示
                yield json.dumps({
                    "type": "folder",
                    "index": index,
                    "total": len(items),
                    "folder": folder_info,
                    "progress": f"{index + 1}/{len(items)}"
                }) + "\n"
            
            # 第二步：后台逐个查重（如果有RJ号且需要检查）
            if check_duplicates:
                conflict_count = 0
                
                yield json.dumps({
                    "type": "checking_start",
                    "message": f"开始查重检查，共 {len(folders)} 个文件夹"
                }) + "\n"
                
                # 获取数据库会话
                from ..models.database import get_db
                db = next(get_db())
                
                try:
                    for index, folder_info in enumerate(folders):
                        item_path = folder_info["path"]
                        item = folder_info["name"]
                        rjcode = folder_info["rjcode"]
                        
                        if not rjcode:
                            continue
                        
                        # 检查缓存
                        cache = None
                        if not force_refresh:
                            try:
                                from ..models.database import ExistingFolderCache
                                cache = db.query(ExistingFolderCache).filter(
                                    ExistingFolderCache.folder_path == item_path
                                ).first()
                            except Exception as e:
                                logger.warning(f"查询缓存失败: {e}")
                        
                        # 如果有缓存且不需要刷新，直接使用缓存
                        if cache and not force_refresh and not cache.needs_refresh:
                            folder_info["duplicate_info"] = cache.duplicate_info
                            folder_info["file_count"] = cache.file_count
                            folder_info["folder_size"] = cache.folder_size
                            folder_info["status"] = "cached"
                            if cache.duplicate_info:
                                conflict_count += 1
                            
                            # 发送更新
                            yield json.dumps({
                                "type": "folder_update",
                                "index": index,
                                "folder": folder_info,
                                "from_cache": True
                            }) + "\n"
                            continue
                        
                        # 没有缓存，执行API查询
                        try:
                            from ..core.duplicate_service import get_duplicate_service
                            duplicate_service = get_duplicate_service()
                            
                            # 添加延时避免429
                            if index > 0 and index % 5 == 0:
                                await asyncio.sleep(1)
                            
                            check_result = await duplicate_service.check_duplicate_enhanced(
                                rjcode, 
                                check_linked_works=True,
                                cue_languages=['CHI_HANS', 'CHI_HANT', 'ENG']
                            )
                            
                            if check_result.is_duplicate:
                                folder_info["duplicate_info"] = {
                                    "is_duplicate": True,
                                    "conflict_type": check_result.conflict_type,
                                    "direct_duplicate": check_result.direct_duplicate,
                                    "linked_works_found": check_result.linked_works_found,
                                    "related_rjcodes": check_result.related_rjcodes,
                                    "analysis_info": check_result.analysis_info
                                }
                                
                                # 获取推荐的解决选项
                                resolution_options = await duplicate_service.get_conflict_resolution_options(check_result)
                                folder_info["duplicate_info"]["resolution_options"] = resolution_options
                                conflict_count += 1
                            
                            folder_info["status"] = "checked"
                            
                            # 计算文件夹大小
                            folder_size = 0
                            file_count = 0
                            try:
                                for root, dirs, files in os.walk(item_path):
                                    file_count += len(files)
                                    for file in files:
                                        file_path = os.path.join(root, file)
                                        if os.path.isfile(file_path):
                                            folder_size += os.path.getsize(file_path)
                            except:
                                pass
                            
                            folder_info["file_count"] = file_count
                            folder_info["folder_size"] = folder_size
                            
                            # 保存到缓存
                            try:
                                from ..models.database import ExistingFolderCache
                                if cache:
                                    cache.duplicate_info = folder_info.get("duplicate_info")
                                    cache.file_count = file_count
                                    cache.folder_size = folder_size
                                    cache.updated_at = datetime.utcnow()
                                    cache.needs_refresh = False
                                else:
                                    cache = ExistingFolderCache(
                                        folder_path=item_path,
                                        folder_name=item,
                                        rjcode=rjcode,
                                        duplicate_info=folder_info.get("duplicate_info"),
                                        file_count=file_count,
                                        folder_size=folder_size
                                    )
                                    db.add(cache)
                                db.commit()
                            except Exception as e:
                                logger.warning(f"保存缓存失败: {e}")
                                db.rollback()
                            
                            # 发送更新
                            yield json.dumps({
                                "type": "folder_update",
                                "index": index,
                                "folder": folder_info,
                                "from_cache": False
                            }) + "\n"
                            
                        except Exception as e:
                            logger.warning(f"查重检查失败 {rjcode}: {e}")
                            folder_info["status"] = "error"
                            yield json.dumps({
                                "type": "folder_update",
                                "index": index,
                                "folder": folder_info,
                                "error": str(e)
                            }) + "\n"
                
                finally:
                    db.close()
                
                # 发送完成消息
                yield json.dumps({
                    "type": "complete",
                    "count": len(folders),
                    "conflict_count": conflict_count,
                    "folders": folders,
                    "message": f"扫描完成，找到 {len(folders)} 个文件夹" + (f"，其中 {conflict_count} 个可能有冲突" if conflict_count > 0 else "")
                }) + "\n"
            else:
                # 不检查重复，直接完成
                yield json.dumps({
                    "type": "complete",
                    "count": len(folders),
                    "conflict_count": 0,
                    "folders": folders,
                    "message": f"扫描完成，找到 {len(folders)} 个文件夹"
                }) + "\n"
            
        except Exception as e:
            logger.error(f"扫描已存在文件夹目录失败: {e}", exc_info=True)
            yield json.dumps({"type": "error", "error": f"扫描失败: {str(e)}"}) + "\n"
    
    return StreamingResponse(
        generate_folders(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )

@app.post("/api/existing-folders/refresh-cache")
async def refresh_existing_folders_cache():
    """刷新所有已有文件夹的缓存信息"""
    try:
        from ..models.database import get_db, ExistingFolderCache
        
        db = next(get_db())
        try:
            # 标记所有缓存需要刷新
            db.query(ExistingFolderCache).update({"needs_refresh": True})
            db.commit()
            
            return {"message": "已标记所有缓存需要刷新，下次扫描时将重新获取信息"}
        finally:
            db.close()
    except Exception as e:
        logger.error(f"刷新缓存失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"刷新缓存失败: {str(e)}")

@app.post("/api/existing-folders/clear-cache")
async def clear_existing_folders_cache():
    """清除所有已有文件夹的缓存"""
    try:
        from ..models.database import get_db, ExistingFolderCache
        
        db = next(get_db())
        try:
            # 删除所有缓存
            deleted_count = db.query(ExistingFolderCache).delete()
            db.commit()
            
            return {"message": f"已清除 {deleted_count} 条缓存"}
        finally:
            db.close()
    except Exception as e:
        logger.error(f"清除缓存失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"清除缓存失败: {str(e)}")


@app.post("/api/existing-folders/check-duplicates")
async def check_existing_folders_duplicates(request: Request):
    """批量检查已有文件夹的查重情况
    
    请求体格式：
    {
        "folders": ["/path/to/folder1", "/path/to/folder2"],
        "check_linked_works": true,
        "cue_languages": ["CHI_HANS", "CHI_HANT", "ENG"]
    }
    """
    try:
        data = await request.json()
        folder_paths = data.get("folders", [])
        check_linked = data.get("check_linked_works", True)
        cue_languages = data.get("cue_languages", ["CHI_HANS", "CHI_HANT", "ENG"])
        
        if not folder_paths:
            raise HTTPException(status_code=400, detail="未提供文件夹路径")
        
        from ..core.duplicate_service import get_duplicate_service
        duplicate_service = get_duplicate_service()
        
        results = []
        for folder_path in folder_paths:
            # 提取RJ号
            folder_name = os.path.basename(folder_path)
            rj_match = re.search(r'[RVB]J(\d{6}|\d{8})(?!\d)', folder_name, re.IGNORECASE)
            rjcode = rj_match.group(0).upper() if rj_match else None
            
            if not rjcode:
                results.append({
                    "folder_path": folder_path,
                    "folder_name": folder_name,
                    "rjcode": None,
                    "error": "无法提取RJ号"
                })
                continue
            
            try:
                check_result = await duplicate_service.check_duplicate_enhanced(
                    rjcode,
                    check_linked_works=check_linked,
                    cue_languages=cue_languages
                )
                
                result = {
                    "folder_path": folder_path,
                    "folder_name": folder_name,
                    "rjcode": rjcode,
                    "is_duplicate": check_result.is_duplicate,
                    "conflict_type": check_result.conflict_type,
                }
                
                if check_result.is_duplicate:
                    result.update({
                        "direct_duplicate": check_result.direct_duplicate,
                        "linked_works_found": check_result.linked_works_found,
                        "related_rjcodes": check_result.related_rjcodes,
                        "analysis_info": check_result.analysis_info
                    })
                    
                    # 获取推荐的解决选项
                    resolution_options = await duplicate_service.get_conflict_resolution_options(check_result)
                    result["resolution_options"] = resolution_options
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"查重检查失败 {rjcode}: {e}")
                results.append({
                    "folder_path": folder_path,
                    "folder_name": folder_name,
                    "rjcode": rjcode,
                    "error": str(e)
                })
        
        # 统计
        duplicate_count = sum(1 for r in results if r.get("is_duplicate"))
        
        return {
            "message": f"检查完成，发现 {duplicate_count}/{len(results)} 个冲突",
            "total": len(results),
            "duplicate_count": duplicate_count,
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量查重检查失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"检查失败: {str(e)}")

@app.post("/api/existing-folders/process")
async def process_existing_folders(request: Request):
    """处理选中的已存在文件夹
    
    请求体格式：
    {
        "folders": ["/path/to/folder1", "/path/to/folder2"],
        "auto_classify": true
    }
    """
    try:
        data = await request.json()
        folders = data.get("folders", [])
        auto_classify = data.get("auto_classify", True)
        
        if not folders:
            raise HTTPException(status_code=400, detail="未选择任何文件夹")
        
        # 验证所有路径是否有效
        config = get_config()
        existing_folders_path = config.storage.existing_folders_path
        
        valid_folders = []
        for folder_path in folders:
            # 安全检查：确保路径在 existing_folders_path 目录下
            if not folder_path.startswith(existing_folders_path):
                logger.warning(f"路径不在已存在文件夹目录下，跳过: {folder_path}")
                continue
            
            if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
                logger.warning(f"路径不存在或不是文件夹，跳过: {folder_path}")
                continue
            
            valid_folders.append(folder_path)
        
        if not valid_folders:
            raise HTTPException(status_code=400, detail="没有有效的文件夹可以处理")
        
        # 创建处理任务
        engine = get_task_engine()
        created_tasks = []
        
        for folder_path in valid_folders:
            task = Task(
                task_type=TaskType.PROCESS_EXISTING_FOLDER,
                source_path=folder_path,
                auto_classify=auto_classify
            )
            await engine.submit(task)
            created_tasks.append({
                "task_id": task.id,
                "folder_path": folder_path
            })
        
        return {
            "message": f"已创建 {len(created_tasks)} 个处理任务",
            "requested": len(folders),
            "created": len(created_tasks),
            "tasks": created_tasks
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理已存在文件夹失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")

@app.post("/api/existing-folders/delete")
async def delete_existing_folder(request: Request):
    """删除已有文件夹（用于抛弃新版）
    
    请求体格式：
    {
        "path": "/path/to/folder"
    }
    """
    try:
        data = await request.json()
        folder_path = data.get("path")
        
        if not folder_path:
            raise HTTPException(status_code=400, detail="未提供文件夹路径")
        
        # 安全检查：确保路径在 existing_folders_path 目录下
        config = get_config()
        existing_folders_path = config.storage.existing_folders_path
        
        if not folder_path.startswith(existing_folders_path):
            raise HTTPException(status_code=400, detail="路径不在已存在文件夹目录下")
        
        if not os.path.exists(folder_path):
            raise HTTPException(status_code=404, detail="文件夹不存在")
        
        # 删除文件夹
        import shutil
        shutil.rmtree(folder_path)
        logger.info(f"已删除文件夹: {folder_path}")
        
        return {"message": "文件夹已删除", "path": folder_path}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文件夹失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

@app.post("/api/existing-folders/process-with-resolution")
async def process_existing_folder_with_resolution(request: Request):
    """使用指定的解决方案处理已有文件夹
    
    请求体格式：
    {
        "folder_path": "/path/to/folder",
        "resolution": "KEEP_NEW|KEEP_OLD|KEEP_BOTH|MERGE|SKIP",
        "auto_classify": true
    }
    """
    try:
        data = await request.json()
        folder_path = data.get("folder_path")
        resolution = data.get("resolution")
        auto_classify = data.get("auto_classify", True)
        
        if not folder_path:
            raise HTTPException(status_code=400, detail="未提供文件夹路径")
        
        if not resolution:
            raise HTTPException(status_code=400, detail="未提供解决方案")
        
        # 安全检查：确保路径在 existing_folders_path 目录下
        config = get_config()
        existing_folders_path = config.storage.existing_folders_path
        
        if not folder_path.startswith(existing_folders_path):
            raise HTTPException(status_code=400, detail="路径不在已存在文件夹目录下")
        
        if not os.path.exists(folder_path):
            raise HTTPException(status_code=404, detail="文件夹不存在")
        
        # 根据解决方案执行不同操作
        if resolution == "SKIP":
            # 抛弃新版 - 删除文件夹
            import shutil
            shutil.rmtree(folder_path)
            logger.info(f"已抛弃新版（删除文件夹）: {folder_path}")
            return {"message": "已抛弃新版，文件夹已删除", "resolution": resolution}
        
        elif resolution in ["KEEP_NEW", "KEEP_BOTH", "MERGE", "MERGE_LANG"]:
            # 这些操作都需要创建处理任务
            # 从 ConflictWork 中查找并更新状态
            from ..models.database import ConflictWork, get_db
            db = next(get_db())
            try:
                # 提取RJ号
                folder_name = os.path.basename(folder_path)
                rj_match = re.search(r'[RVB]J(\d{6}|\d{8})(?!\d)', folder_name, re.IGNORECASE)
                rjcode = rj_match.group(0).upper() if rj_match else None
                
                if rjcode:
                    # 查找对应的冲突记录并更新状态
                    conflict = db.query(ConflictWork).filter(
                        ConflictWork.rjcode == rjcode,
                        ConflictWork.status == 'PENDING'
                    ).first()
                    
                    if conflict:
                        conflict.status = resolution
                        db.commit()
                        logger.info(f"更新冲突记录状态: {rjcode} -> {resolution}")
                
                # 创建处理任务
                engine = get_task_engine()
                task = Task(
                    task_type=TaskType.PROCESS_EXISTING_FOLDER,
                    source_path=folder_path,
                    auto_classify=auto_classify
                )
                await engine.submit(task)
                
                return {
                    "message": f"已创建处理任务，解决方案: {resolution}",
                    "resolution": resolution,
                    "task_id": task.id,
                    "folder_path": folder_path
                }
                
            finally:
                db.close()
        
        else:
            raise HTTPException(status_code=400, detail=f"未知的解决方案: {resolution}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")

# ========== 关联作品查询 API（改进的查重功能）==========

@app.get("/api/linked-works/{rjcode}")
async def get_linked_works(
    rjcode: str,
    include_full_linkage: bool = True,
    cue_languages: str = "CHI_HANS,CHI_HANT,ENG"
):
    """
    获取作品的关联作品链
    
    Args:
        rjcode: RJ号
        include_full_linkage: 是否包含完整关联链（包括所有语言版本）
        cue_languages: 需要查询的语言列表，逗号分隔
    """
    from ..core.dlsite_service import get_dlsite_service
    
    try:
        service = get_dlsite_service()
        languages = [lang.strip() for lang in cue_languages.split(',') if lang.strip()]
        
        if include_full_linkage:
            linked_works = await service.get_full_linkage(rjcode, languages)
        else:
            linked_works = await service.get_linked_works(rjcode)
        
        # 获取翻译信息
        trans_info = await service.get_translation_info(rjcode)
        
        return {
            "rjcode": rjcode,
            "translation_info": {
                "is_original": trans_info.is_original,
                "is_parent": trans_info.is_parent,
                "is_child": trans_info.is_child,
                "parent_workno": trans_info.parent_workno,
                "original_workno": trans_info.original_workno,
                "lang": trans_info.lang
            },
            "linked_works": {k: v.to_dict() for k, v in linked_works.items()},
            "total_count": len(linked_works)
        }
        
    except Exception as e:
        logger.error(f"获取关联作品失败 {rjcode}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取关联作品失败: {str(e)}")


@app.get("/api/linked-works/{rjcode}/check-library")
async def check_linked_works_in_library(
    rjcode: str,
    cue_languages: str = "CHI_HANS,CHI_HANT,ENG"
):
    """
    检查作品的关联作品是否在库中
    
    返回库中已存在的所有关联作品
    """
    from ..core.dlsite_service import get_dlsite_service
    from ..core.duplicate_service import get_duplicate_service
    
    try:
        dlsite_service = get_dlsite_service()
        duplicate_service = get_duplicate_service()
        languages = [lang.strip() for lang in cue_languages.split(',') if lang.strip()]
        
        # 获取完整关联链
        linked_works = await dlsite_service.get_full_linkage(rjcode, languages)
        
        # 检查哪些在库中
        found_in_library = await duplicate_service._check_linked_works_in_library(
            linked_works, rjcode
        )
        
        # 获取翻译信息
        trans_info = await dlsite_service.get_translation_info(rjcode)
        
        return {
            "rjcode": rjcode,
            "is_original": trans_info.is_original,
            "is_in_library": len(found_in_library) > 0,
            "library_works": [
                {
                    "rjcode": w.rjcode,
                    "work_type": w.work_type,
                    "lang": w.lang,
                    "work_name": w.work_name,
                    "path": w.folder_path,
                    "size": w.folder_size,
                    "file_count": w.file_count
                }
                for w in found_in_library
            ],
            "total_linked": len(linked_works),
            "found_in_library": len(found_in_library)
        }
        
    except Exception as e:
        logger.error(f"检查库中关联作品失败 {rjcode}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"检查失败: {str(e)}")


@app.post("/api/conflicts/enhanced-check")
async def enhanced_duplicate_check(request: Request):
    """
    改进的查重检查
    
    支持检测关联作品冲突
    """
    from ..core.duplicate_service import get_duplicate_service
    
    try:
        data = await request.json()
        rjcode = data.get("rjcode")
        check_linked = data.get("check_linked_works", True)
        cue_languages = data.get("cue_languages", ["CHI_HANS", "CHI_HANT"])
        
        if not rjcode:
            raise HTTPException(status_code=400, detail="RJ号不能为空")
        
        service = get_duplicate_service()
        result = await service.check_duplicate_enhanced(
            rjcode, 
            check_linked_works=check_linked,
            cue_languages=cue_languages
        )
        
        # 获取推荐的解决选项
        resolution_options = await service.get_conflict_resolution_options(result)
        
        return {
            "is_duplicate": result.is_duplicate,
            "conflict_type": result.conflict_type,
            "direct_duplicate": result.direct_duplicate,
            "linked_works_found": result.linked_works_found,
            "related_rjcodes": result.related_rjcodes,
            "analysis_info": result.analysis_info,
            "resolution_options": resolution_options
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"改进查重检查失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"检查失败: {str(e)}")


# ========== Kikoeru 搜索配置 API ==========

@app.get("/api/kikoeru-configs")
async def get_kikoeru_configs():
    """获取所有 Kikoeru 搜索配置"""
    from ..models.database import KikoeruSearchConfig, get_db
    
    db = next(get_db())
    try:
        configs = db.query(KikoeruSearchConfig).all()
        return {
            "configs": [config.to_dict() for config in configs]
        }
    finally:
        db.close()


@app.post("/api/kikoeru-configs")
async def create_kikoeru_config(request: Request):
    """创建 Kikoeru 搜索配置"""
    from ..models.database import KikoeruSearchConfig, get_db
    import uuid
    
    try:
        data = await request.json()
        db = next(get_db())
        
        config = KikoeruSearchConfig(
            id=str(uuid.uuid4()),
            name=data.get("name", "Kikoeru"),
            search_url_template=data.get("search_url_template", ""),
            show_url_template=data.get("show_url_template", ""),
            enabled=data.get("enabled", False),
            custom_headers=data.get("custom_headers", {})
        )
        
        db.add(config)
        db.commit()
        
        return {
            "message": "配置已创建",
            "config": config.to_dict()
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"创建 Kikoeru 配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")
    finally:
        db.close()


@app.put("/api/kikoeru-configs/{config_id}")
async def update_kikoeru_config(config_id: str, request: Request):
    """更新 Kikoeru 搜索配置"""
    from ..models.database import KikoeruSearchConfig, get_db
    
    try:
        data = await request.json()
        db = next(get_db())
        
        config = db.query(KikoeruSearchConfig).filter(
            KikoeruSearchConfig.id == config_id
        ).first()
        
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在")
        
        if "name" in data:
            config.name = data["name"]
        if "search_url_template" in data:
            config.search_url_template = data["search_url_template"]
        if "show_url_template" in data:
            config.show_url_template = data["show_url_template"]
        if "enabled" in data:
            config.enabled = data["enabled"]
        if "custom_headers" in data:
            config.custom_headers = data["custom_headers"]
        
        db.commit()
        
        return {
            "message": "配置已更新",
            "config": config.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新 Kikoeru 配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")
    finally:
        db.close()


@app.delete("/api/kikoeru-configs/{config_id}")
async def delete_kikoeru_config(config_id: str):
    """删除 Kikoeru 搜索配置"""
    from ..models.database import KikoeruSearchConfig, get_db
    
    db = next(get_db())
    try:
        config = db.query(KikoeruSearchConfig).filter(
            KikoeruSearchConfig.id == config_id
        ).first()
        
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在")
        
        db.delete(config)
        db.commit()
        
        return {"message": "配置已删除"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除 Kikoeru 配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
    finally:
        db.close()


# ========== Kikoeru 服务器查重配置 API ==========
from ..core.kikoeru_duplicate_service import get_kikoeru_service, KikoeruDuplicateService

class KikoeruServerConfig(BaseModel):
    """Kikoeru 服务器配置模型"""
    enabled: bool = False
    server_url: str = ""
    api_token: str = ""
    timeout: int = 10
    cache_ttl: int = 300

@app.get("/api/kikoeru-server/config")
async def get_kikoeru_server_config():
    """获取 Kikoeru 服务器查重配置"""
    try:
        config = get_config()
        # 直接访问 Pydantic 模型的属性
        kikoeru_config = config.kikoeru_server if hasattr(config, 'kikoeru_server') else None
        
        if kikoeru_config:
            return {
                "enabled": kikoeru_config.enabled,
                "server_url": kikoeru_config.server_url,
                "api_token": kikoeru_config.api_token,  # 注意：生产环境可能需要隐藏
                "timeout": kikoeru_config.timeout,
                "cache_ttl": kikoeru_config.cache_ttl
            }
        else:
            # 返回默认配置
            return {
                "enabled": False,
                "server_url": "",
                "api_token": "",
                "timeout": 10,
                "cache_ttl": 300
            }
    except Exception as e:
        logger.error(f"获取 Kikoeru 服务器配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")

@app.post("/api/kikoeru-server/config")
async def update_kikoeru_server_config(config: KikoeruServerConfig):
    """更新 Kikoeru 服务器查重配置（已弃用，请使用 /api/config）"""
    try:
        from ..config.settings import save_config
        
        # 只更新 kikoeru_server 部分配置
        config_to_save = {
            'kikoeru_server': {
                'enabled': config.enabled,
                'server_url': config.server_url.rstrip('/'),
                'api_token': config.api_token,
                'timeout': config.timeout,
                'cache_ttl': config.cache_ttl
            }
        }
        
        # 保存配置
        save_config(config_to_save)
        
        # 重新加载服务配置
        service = get_kikoeru_service()
        service.config = service._load_config()
        
        return {
            "message": "Kikoeru 服务器配置已更新",
            "config": {
                "enabled": config.enabled,
                "server_url": config.server_url,
                "timeout": config.timeout,
                "cache_ttl": config.cache_ttl
            }
        }
    except Exception as e:
        logger.error(f"更新 Kikoeru 服务器配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")

@app.post("/api/kikoeru-server/test")
async def test_kikoeru_server_connection():
    """测试 Kikoeru 服务器连接"""
    try:
        service = get_kikoeru_service()
        result = await service.test_connection()
        
        return result
    except Exception as e:
        logger.error(f"测试 Kikoeru 服务器连接失败: {e}")
        return {
            "success": False,
            "message": f"测试失败: {str(e)}",
            "latency": 0
        }

@app.post("/api/kikoeru-server/check")
async def check_kikoeru_duplicate(
    rjcode: str, 
    check_linkages: bool = True,
    cue_languages: str = "CHI_HANS CHI_HANT ENG"
):
    """检查作品及其关联作品是否在 Kikoeru 服务器中
    
    Args:
        rjcode: RJ号
        check_linkages: 是否检查关联作品
        cue_languages: 语言列表，空格分隔（如 'CHI_HANS CHI_HANT ENG'）
    """
    logger.info(f"=" * 60)
    logger.info(f"[Kikoeru查重] 开始查询: {rjcode}, check_linkages={check_linkages}")
    
    try:
        # 解析语言列表
        lang_list = cue_languages.split() if cue_languages else ["CHI_HANS", "CHI_HANT", "ENG"]
        logger.info(f"[Kikoeru查重] 检查语言: {lang_list}")
        
        service = get_kikoeru_service()
        
        if check_linkages:
            # 查询关联作品
            logger.info(f"[Kikoeru查重] 执行关联作品查询...")
            results = await service.check_duplicate_with_linkages(rjcode, lang_list, use_cache=True)
            
            # 格式化返回结果
            found_works = []
            for rj, res in results.items():
                if res.is_found:
                    found_works.append({
                        "rjcode": rj,
                        "title": res.title,
                        "circle_name": res.circle_name,
                        "tags": res.tags
                    })
            
            primary_result = results.get(rjcode, KikoeruCheckResult(rjcode=rjcode))
            
            logger.info(f"[Kikoeru查重] 关联查询完成: 总共 {len(results)} 个作品，找到 {len(found_works)} 个")
            
            return {
                "rjcode": rjcode,
                "is_found": primary_result.is_found or len(found_works) > 0,
                "title": primary_result.title,
                "circle_name": primary_result.circle_name,
                "tags": primary_result.tags,
                "linked_works_found": found_works,
                "total_checked": len(results),
                "source": "kikoeru_with_linkages",
                "checked_at": datetime.now().isoformat()
            }
        else:
            # 只查询单个作品
            result = await service.check_duplicate(rjcode, use_cache=True)
            
            return {
                "rjcode": result.rjcode,
                "is_found": result.is_found,
                "title": result.title,
                "circle_name": result.circle_name,
                "tags": result.tags,
                "linked_works_found": [],
                "total_checked": 1,
                "source": result.source,
                "checked_at": result.checked_at.isoformat() if result.checked_at else None
            }
    except Exception as e:
        logger.error(f"[Kikoeru查重] 查询失败: {rjcode}, 错误: {e}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"查重检查失败: {str(e)}")
    finally:
        logger.info(f"[Kikoeru查重] 查询结束: {rjcode}")
        logger.info(f"=" * 60)

@app.post("/api/kikoeru-server/clear-cache")
async def clear_kikoeru_cache():
    """清除 Kikoeru 查重缓存"""
    try:
        service = get_kikoeru_service()
        service.clear_cache()
        
        return {"message": "Kikoeru 查重缓存已清除"}
    except Exception as e:
        logger.error(f"清除 Kikoeru 缓存失败: {e}")
        raise HTTPException(status_code=500, detail=f"清除缓存失败: {str(e)}")


# 静态文件服务（前端）
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# 如果前端构建文件存在，则提供静态文件服务
# 优先使用环境变量指定的路径，否则使用默认路径
static_files_path = os.environ.get('STATIC_FILES_PATH', os.path.join(os.path.dirname(__file__), "../static"))
frontend_path = os.environ.get('FRONTEND_PATH', os.path.join(os.path.dirname(__file__), "../frontend/dist"))

# 检查多个可能的前端路径
possible_paths = [
    static_files_path,
    frontend_path,
    os.path.join(os.path.dirname(__file__), "../frontend/dist"),
    "/app/static",
]

frontend_build_path = None
logger.info(f"检查静态文件路径，当前工作目录: {os.getcwd()}")
for path in possible_paths:
    index_file = os.path.join(path, "index.html")
    path_exists = os.path.exists(path)
    index_exists = os.path.exists(index_file)
    logger.info(f"检查路径: {path} - 目录存在: {path_exists}, index.html存在: {index_exists}")
    if path_exists and index_exists:
        frontend_build_path = path
        logger.info(f"找到前端构建文件: {path}")
        break

# 注册静态文件服务（放在子路径，避免覆盖 API）
if frontend_build_path:
    # 提供静态资源文件（JS、CSS、图片等）
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_build_path, "assets")), name="assets")
    
    # 捕获所有非 API 路由，返回 index.html（SPA 支持）
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # API 路由不应该被拦截
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
            raise HTTPException(status_code=404, detail="Not found")
        
        # 对于前端路由，返回 index.html
        index_path = os.path.join(frontend_build_path, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        else:
            raise HTTPException(status_code=404, detail="Frontend not built")
