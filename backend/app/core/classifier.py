import os
import re
import shutil
from pathlib import Path
from typing import Optional, Dict
import logging

from ..config.settings import get_config, ClassificationRule
from ..models.database import LibrarySnapshot, ConflictWork, get_db
from ..core.task_engine import Task

logger = logging.getLogger(__name__)

class SmartClassifier:
    """智能分类器"""
    
    def __init__(self):
        self.config = get_config()
    
    async def check_duplicate_before_extract(self, rjcode: str, task: Task, engine=None) -> bool:
        """
        在解压前检查是否重复（包括检查是否有其他任务正在处理）
        返回True表示存在重复或正在处理中，应该停止处理
        """
        logger.info(f"开始预检: 检查RJ号 {rjcode} 是否已存在或正在处理")
        
        # 1. 检查是否已有其他任务正在处理这个RJ号
        if engine and engine.is_rjcode_processing(rjcode):
            logger.warning(f"RJ号 {rjcode} 正在被其他任务处理中，当前任务将等待")
            # 添加到问题作品表，标记为等待状态
            self._add_to_conflict_works(
                task.id, 
                rjcode, 
                'DUPLICATE', 
                "正在处理中", 
                task.source_path,
                {},
                status='PENDING'
            )
            return True
        
        # 2. 检查库中是否已存在
        existing = self._check_existing(rjcode)
        
        if existing:
            # 强制使用DUPLICATE类型（预检阶段无法判断语言差异）
            conflict_type = 'DUPLICATE'
            
            logger.info(f"预检发现重复: RJ={rjcode}, 类型={conflict_type}, 已存在={existing['path']}")
            
            # 添加到问题作品表（不解压，只记录压缩包路径）
            self._add_to_conflict_works(
                task.id, 
                rjcode, 
                conflict_type, 
                existing['path'], 
                task.source_path,  # 压缩包路径
                {}  # 尚无元数据
            )
            
            logger.info(f"预检发现重复作品: {rjcode}, 已添加到问题列表等待手动处理")
            return True
        
        # 3. 标记RJ号正在处理（防止其他任务同时处理）
        if engine:
            engine.mark_rjcode_processing(rjcode)
            task.rjcode = rjcode  # 保存RJ号到任务，用于后续清理
        
        logger.info(f"预检完成: RJ号 {rjcode} 未在库中发现，继续解压")
        return False
    
    async def classify_and_move(self, source_path: str, metadata: Dict, task: Task) -> str:
        """
        智能分类并移动到库存
        返回最终路径
        """
        rjcode = metadata.get('rjcode', '')
        
        # 1. 检查是否已存在
        task.update_progress(82, "检查重复")
        existing = self._check_existing(rjcode)
        
        if existing:
            # 使用DUPLICATE类型（解压后的重复检测，已有元数据但统一标记为重复）
            conflict_type = 'DUPLICATE'
            
            logger.info(f"解压后发现重复: RJ={rjcode}, 类型={conflict_type}, 已存在={existing['path']}")
            
            # 添加到问题作品表
            self._add_to_conflict_works(task.id, rjcode, conflict_type, existing['path'], source_path, metadata)
            
            # 等待用户处理（这里需要UI交互，简化处理）
            logger.info(f"发现重复作品: {rjcode}, 已添加到问题列表")
            # 临时移动到一个待处理目录
            # 使用重命名后的文件夹名称，而不是RJ号
            source_folder_name = os.path.basename(source_path)
            conflict_base_path = os.path.join(self.config.storage.library_path, '_conflicts')
            os.makedirs(conflict_base_path, exist_ok=True)
            final_path = self._move_with_rename(source_path, conflict_base_path)
            return final_path
        
        # 2. 应用分类规则
        task.update_progress(85, "应用分类规则")
        target_path = self._apply_classification_rules(metadata)
        
        # 3. 移动文件
        task.update_progress(90, "移动到库存")
        final_path = self._move_with_rename(source_path, target_path)
        
        # 4. 更新库存快照
        self._update_library_snapshot(rjcode, final_path)
        
        return final_path
    
    def _check_existing(self, rjcode: str) -> Optional[Dict]:
        """检查作品是否已存在于库存"""
        logger.info(f"检查RJ号 {rjcode} 是否已存在于库存")
        
        db = next(get_db())
        try:
            # 从数据库查询
            snapshot = db.query(LibrarySnapshot).filter(
                LibrarySnapshot.rjcode == rjcode
            ).first()

            # 验证数据库中的路径是否真实存在
            if snapshot:
                folder_path = str(snapshot.folder_path)
                logger.info(f"数据库中找到记录: {rjcode} -> {folder_path}")
                if os.path.exists(folder_path):
                    logger.info(f"确认路径存在: {folder_path}")
                    return {
                        'path': folder_path,
                        'size': snapshot.folder_size
                    }
                else:
                    # 路径不存在，清理过期的数据库记录
                    logger.warning(f"数据库记录存在但路径已不存在，清理过期记录: {rjcode} -> {folder_path}")
                    db.delete(snapshot)
                    db.commit()

            # 如果没有数据库记录，扫描库存目录
            library_path = Path(self.config.storage.library_path)
            logger.info(f"扫描库存目录: {library_path}")
            found_count = 0
            for folder in library_path.rglob('*'):
                if folder.is_dir() and rjcode in folder.name:
                    found_count += 1
                    logger.info(f"目录扫描找到已存在的作品: {rjcode} -> {folder}")
                    return {
                        'path': str(folder),
                        'size': self._get_folder_size(str(folder))
                    }
            
            logger.info(f"扫描完成，找到 {found_count} 个匹配项")
            return None
        except Exception as e:
            logger.error(f"检查作品存在性时出错: {e}")
            return None
        finally:
            db.close()
    
    def _determine_conflict_type(self, existing: Dict, new_metadata: Dict) -> str:
        """确定冲突类型"""
        existing_name = os.path.basename(existing['path']).lower()
        new_name = new_metadata.get('work_name', '').lower()
        
        # 检查是否是多语言版本
        if self._has_language_difference(existing_name, new_name):
            return 'LANGUAGE_VARIANT'
        
        # 检查是否是更新版本
        if existing['size'] != new_metadata.get('size', 0):
            return 'MULTIPLE_VERSIONS'
        
        return 'DUPLICATE'
    
    def _has_language_difference(self, name1: str, name2: str) -> bool:
        """检查是否有语言差异"""
        chinese_indicators = ['中文', '简体', '繁体', 'chinese', 'cn', 'tw']
        japanese_indicators = ['日文', 'japanese', 'jp']
        
        has_chinese_1 = any(ind in name1 for ind in chinese_indicators)
        has_chinese_2 = any(ind in name2 for ind in chinese_indicators)
        has_japanese_1 = any(ind in name1 for ind in japanese_indicators)
        has_japanese_2 = any(ind in name2 for ind in japanese_indicators)
        
        return has_chinese_1 != has_chinese_2 or has_japanese_1 != has_japanese_2
    
    def _add_to_conflict_works(self, task_id: str, rjcode: str, conflict_type: str,
                               existing_path: str, new_path: str, metadata: Dict,
                               status: str = 'PENDING', linked_works_info=None,
                               analysis_info=None, related_rjcodes=None):
        """添加到问题作品表（避免重复）"""
        import uuid
        from datetime import datetime
        
        db = next(get_db())
        try:
            # 检查是否已存在相同的冲突记录（相同的RJ号）
            # 无论新文件路径是否相同，只要是同一个RJ号且状态为PENDING，就不添加
            existing_conflict = db.query(ConflictWork).filter(
                ConflictWork.rjcode == rjcode,
                ConflictWork.status == 'PENDING'
            ).first()
            
            if existing_conflict:
                logger.info(f"冲突记录已存在，跳过重复添加: {rjcode}")
                return
            
            # 检查新文件是否还存在（如果用户已经手动删除了，就不需要再添加）
            if not os.path.exists(new_path):
                logger.info(f"新文件已不存在，跳过添加冲突记录: {rjcode}, 路径: {new_path}")
                return
            
            conflict = ConflictWork(
                id=str(uuid.uuid4()),
                task_id=task_id,
                rjcode=rjcode,
                conflict_type=conflict_type,
                existing_path=existing_path,
                new_path=new_path,
                new_metadata=metadata,
                status=status,
                linked_works_info=linked_works_info if linked_works_info is not None else [],
                analysis_info=analysis_info if analysis_info is not None else {},
                related_rjcodes=related_rjcodes if related_rjcodes is not None else [],
                created_at=datetime.utcnow()
            )
            db.add(conflict)
            db.commit()
            logger.info(f"添加问题作品记录: {rjcode}")
        except Exception as e:
            logger.error(f"添加问题作品失败: {e}")
            db.rollback()
        finally:
            db.close()
    
    def _apply_classification_rules(self, metadata: Dict) -> str:
        """应用分类规则生成目标路径"""
        library_base = self.config.storage.library_path
        
        for rule in self.config.classification:
            if not rule.enabled:
                continue
            
            path = self._apply_single_rule(rule, metadata)
            if path is not None:
                # path 可能是空字符串（表示无子目录）
                if path:
                    return os.path.join(library_base, path)
                else:
                    return library_base
        
        # 默认分类 - 直接放入库存根目录
        return library_base
    
    def _apply_single_rule(self, rule: ClassificationRule, metadata: Dict) -> Optional[str]:
        """应用单个分类规则，只返回分类目录（不包含作品文件夹名称）"""
        
        if rule.type == 'none':
            # 无子目录，直接返回空字符串表示根目录
            return ''
        
        elif rule.type == 'maker':
            maker_name = metadata.get('maker_name', '')
            if not maker_name:
                return None
            
            # 使用自定义模板或默认使用社团名
            template = rule.path_template or '{maker_name}'
            # 只替换社团名
            path = template.replace('{maker_name}', self._sanitize_path(maker_name))
            return path
        
        elif rule.type == 'series':
            series_name = metadata.get('series_name')
            if not series_name:
                # 使用fallback规则
                if rule.fallback:
                    # 找到fallback规则并应用
                    for fallback_rule in self.config.classification:
                        if fallback_rule.type == rule.fallback:
                            return self._apply_single_rule(fallback_rule, metadata)
                return None
            
            # 使用自定义模板或默认使用系列名
            template = rule.path_template or '{series_name}'
            path = template.replace('{series_name}', self._sanitize_path(series_name))
            return path
        
        elif rule.type == 'rjcode':
            rjcode = metadata.get('rjcode', '')
            if not rjcode:
                return None
            
            # 检查RJ号是否在规则指定的范围内
            if rule.rjcode_range:
                try:
                    # 解析范围，格式如 "RJ01400000-RJ01499999"
                    range_parts = rule.rjcode_range.replace(' ', '').upper().split('-')
                    if len(range_parts) == 2:
                        start_rj = range_parts[0]
                        end_rj = range_parts[1]
                        # 提取数字部分进行比较
                        rj_num = int(''.join(filter(str.isdigit, rjcode)))
                        start_num = int(''.join(filter(str.isdigit, start_rj)))
                        end_num = int(''.join(filter(str.isdigit, end_rj)))
                        
                        if rj_num < start_num or rj_num > end_num:
                            return None  # RJ号不在范围内，跳过此规则
                except Exception as e:
                    logger.warning(f"RJ号范围解析失败: {rule.rjcode_range}, 错误: {e}")
                    # 解析失败时不阻止分类
            
            # 使用自定义目录名称
            if rule.custom_name:
                return rule.custom_name
            else:
                # 默认使用RJ号的前缀
                rj_prefix = rjcode[:5] if len(rjcode) >= 5 else rjcode
                return f"{rj_prefix}系列"
        
        elif rule.type == 'date':
            release_date = metadata.get('release_date', '')
            if not release_date:
                return None
            
            try:
                year = release_date[:4]
                month = release_date[5:7]
                template = rule.path_template or '{year}/{month}'
                path = template.replace('{year}', year)
                path = path.replace('{month}', month)
                return path
            except:
                return None
        
        return None
    
    def _sanitize_path(self, path: str) -> str:
        """清理路径中的非法字符"""
        # 移除Windows保留字符
        path = re.sub(r'[<>:"/\\|?*]', '', path)
        # 限制长度
        if len(path) > 100:
            path = path[:100]
        return path.strip()
    
    def _move_with_rename(self, source: str, target_dir: str) -> str:
        """移动文件/文件夹，处理重名"""
        source_path = Path(source)
        target_path = Path(target_dir)
        
        # 确保目标目录存在
        target_path.mkdir(parents=True, exist_ok=True)
        
        # 最终目标
        final_target = target_path / source_path.name
        
        # 处理重名
        counter = 1
        original_target = final_target
        while final_target.exists():
            final_target = target_path / f"{original_target.stem}({counter}){original_target.suffix}"
            counter += 1
        
        # 执行移动
        shutil.move(str(source_path), str(final_target))
        logger.info(f"移动: {source_path} -> {final_target}")
        
        return str(final_target)
    
    def _update_library_snapshot(self, rjcode: str, folder_path: str):
        """更新库存快照"""
        from datetime import datetime
        
        db = next(get_db())
        try:
            # 删除旧记录
            db.query(LibrarySnapshot).filter(
                LibrarySnapshot.rjcode == rjcode
            ).delete()
            
            # 创建新记录
            folder_size = self._get_folder_size(folder_path)
            file_count = self._get_file_count(folder_path)
            
            snapshot = LibrarySnapshot(
                rjcode=rjcode,
                folder_path=folder_path,
                folder_size=folder_size,
                file_count=file_count,
                scanned_at=datetime.utcnow()
            )
            db.add(snapshot)
            db.commit()
        except Exception as e:
            logger.error(f"更新库存快照失败: {e}")
            db.rollback()
        finally:
            db.close()
    
    def _get_folder_size(self, folder_path: str) -> int:
        """获取文件夹大小"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(folder_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
        return total_size
    
    def _get_file_count(self, folder_path: str) -> int:
        """获取文件数量"""
        count = 0
        for dirpath, dirnames, filenames in os.walk(folder_path):
            count += len(filenames)
        return count
