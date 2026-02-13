import asyncio
import uuid
import os
import shutil
from datetime import datetime
from typing import Optional, Callable
from enum import Enum
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PAUSED = "paused"
    WAITING_MANUAL = "waiting_manual"  # 等待手动处理（重复作品）
    COMPLETED = "completed"
    FAILED = "failed"

class TaskType(str, Enum):
    EXTRACT = "extract"
    FILTER = "filter"
    METADATA = "metadata"
    RENAME = "rename"
    AUTO_PROCESS = "auto_process"
    PROCESS_EXISTING_FOLDER = "process_existing_folder"  # 处理已存在的文件夹（跳过解压）

class Task:
    """任务对象"""
    def __init__(
        self,
        task_type: TaskType,
        source_path: str,
        output_path: Optional[str] = None,
        auto_classify: bool = False,
        metadata: Optional[dict] = None,
        skip_archive: bool = False
    ):
        self.id = str(uuid.uuid4())
        self.type = task_type
        self.status = TaskStatus.PENDING
        self.source_path = source_path
        self.output_path = output_path
        self.auto_classify = auto_classify
        self.skip_archive = skip_archive  # 是否跳过归档（用于重新解压）
        self.progress = 0
        self.current_step = "等待中"
        self.error_message = None
        self.task_metadata = metadata or {}
        self.created_at = datetime.utcnow()
        self.started_at = None
        self.completed_at = None
        self._cancelled = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self.rjcode: Optional[str] = None  # 作品的RJ号，用于重复检测
    
    def start(self):
        """开始任务"""
        self.status = TaskStatus.PROCESSING
        self.started_at = datetime.utcnow()
        self.current_step = "处理中"
    
    def complete(self):
        """完成任务"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.progress = 100
        self.current_step = "完成"
    
    def fail(self, error: str):
        """任务失败"""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error
        self.current_step = f"失败: {error}"
    
    def pause(self):
        """暂停任务"""
        self.status = TaskStatus.PAUSED
        self._pause_event.clear()
    
    def resume(self):
        """恢复任务"""
        self.status = TaskStatus.PROCESSING
        self._pause_event.set()
    
    def cancel(self):
        """取消任务"""
        self._cancelled = True
        self.status = TaskStatus.FAILED
        self.error_message = "用户取消"
        self.completed_at = datetime.utcnow()
        self.current_step = "已取消"
        logger.info(f"任务 {self.id} 已被用户取消")
    
    async def wait_if_paused(self):
        """如果暂停则等待"""
        await self._pause_event.wait()
    
    def is_cancelled(self) -> bool:
        """检查是否被取消"""
        return self._cancelled
    
    def update_progress(self, progress: int, step: str):
        """更新进度"""
        self.progress = min(100, max(0, progress))
        self.current_step = step
        logger.info(f"任务 {self.id}: {step} ({progress}%)")

def get_conflict_type_name(conflict_type: str) -> str:
    """获取冲突类型的中文名称"""
    names = {
        'DUPLICATE': '直接重复',
        'LINKED_WORK_ORIGINAL': '原作已存在',
        'LINKED_WORK_TRANSLATION': '翻译版已存在',
        'LINKED_WORK_CHILD': '子版本已存在',
        'LINKED_WORK': '关联作品',
        'LANGUAGE_VARIANT': '语言变体',
        'MULTIPLE_VERSIONS': '多版本'
    }
    return names.get(conflict_type, '冲突')

class TaskEngine:
    """任务引擎 - 管理任务队列和执行"""
    
    def __init__(self, max_concurrent: int = 2):
        self.max_concurrent = max_concurrent
        self.tasks: dict[str, Task] = {}
        self.queue: asyncio.Queue = asyncio.Queue()
        self.processing: set[str] = set()
        self._processing_rjcodes: set[str] = set()  # 正在处理的RJ号集合，防止并发重复处理
        self._shutdown = False
        self._worker_task: Optional[asyncio.Task] = None
        self._progress_callbacks: list[Callable] = []
    
    def is_rjcode_processing(self, rjcode: str) -> bool:
        """检查RJ号是否正在被处理"""
        return rjcode in self._processing_rjcodes
    
    def mark_rjcode_processing(self, rjcode: str):
        """标记RJ号正在处理"""
        self._processing_rjcodes.add(rjcode)
        logger.info(f"标记RJ号正在处理: {rjcode}")
    
    def unmark_rjcode_processing(self, rjcode: str):
        """取消标记RJ号"""
        if rjcode in self._processing_rjcodes:
            self._processing_rjcodes.discard(rjcode)
            logger.info(f"取消标记RJ号: {rjcode}")
    
    def add_progress_callback(self, callback: Callable):
        """添加进度回调"""
        self._progress_callbacks.append(callback)
    
    async def _notify_progress(self, task: Task):
        """通知进度更新"""
        for callback in self._progress_callbacks:
            try:
                callback(task)
            except Exception as e:
                logger.error(f"进度回调错误: {e}")
    
    async def submit(self, task: Task) -> str:
        """提交任务"""
        self.tasks[task.id] = task
        await self.queue.put(task)
        logger.info(f"任务 {task.id} 已提交")
        return task.id
    
    async def _process_task(self, task: Task):
        """处理单个任务"""
        from .extract_service import ExtractService
        from .filter_service import FilterService
        from .metadata_service import MetadataService
        from .rename_service import RenameService
        from .classifier import SmartClassifier
        
        try:
            task.start()
            await self._notify_progress(task)
            
            # 根据任务类型执行不同流程
            if task.type == TaskType.AUTO_PROCESS:
                # 自动全流程
                extract_service = ExtractService()
                filter_service = FilterService()
                metadata_service = MetadataService()
                classifier = SmartClassifier()
                
                # 0. 预检：在解压前检查是否重复（传入engine以标记处理中状态）
                task.update_progress(5, "预检中")
                rjcode = self._extract_rjcode(task.source_path)
                if rjcode and task.auto_classify:
                    is_duplicate = await classifier.check_duplicate_before_extract(rjcode, task, self)
                    if is_duplicate:
                        logger.info(f"作品 {rjcode} 已存在或正在处理中，已添加到问题作品列表")
                        # 直接完成任务，不保留在队列中
                        # 问题作品已在数据库中记录，用户可以在"问题作品"页面处理
                        task.status = TaskStatus.COMPLETED
                        task.update_progress(100, "重复作品，请在问题作品页面处理")
                        task.completed_at = datetime.utcnow()
                        # 注意：如果是因为正在处理而返回True，不应该清除标记
                        # 只有真正开始处理的任务才会标记，所以这里不需要清除
                        return
                
                # 1. 解压
                task.update_progress(10, "解压中")
                extracted_path = await extract_service.extract(task)
                if not extracted_path:
                    # 解压失败，任务状态已被设置为 failed，直接返回
                    logger.error(f"任务 {task.id}: 解压失败，任务已标记为失败状态")
                    return

                await task.wait_if_paused()
                if task.is_cancelled():
                    return

                # 2. 获取元数据
                task.update_progress(40, "获取元数据")
                metadata = await metadata_service.fetch(extracted_path, task)
                task.task_metadata = metadata

                await task.wait_if_paused()
                if task.is_cancelled():
                    return

                # 3. 重命名文件夹
                task.update_progress(60, "重命名文件夹")
                from .rename_service import RenameService
                rename_service = RenameService()
                renamed_path = await rename_service.rename(extracted_path, task)

                await task.wait_if_paused()
                if task.is_cancelled():
                    return

                # 4. 过滤（在重命名后的文件夹上进行）
                task.update_progress(75, "过滤文件中")
                await filter_service.filter(renamed_path, task)

                await task.wait_if_paused()
                if task.is_cancelled():
                    return

                # 5. 扁平化单层文件夹（在过滤之后，移动之前）
                from ..config.settings import get_config
                config = get_config()
                if config.rename.flatten_single_subfolder:
                    task.update_progress(78, "扁平化文件夹结构")
                    renamed_path = rename_service._flatten_single_subfolder(renamed_path)
                    logger.info(f"任务引擎 - 扁平化后路径: {renamed_path}")

                # 5.5 移除空文件夹（在扁平化之后）
                if config.rename.remove_empty_folders:
                    task.update_progress(79, "清理空文件夹")
                    rename_service.remove_empty_folders(renamed_path, remove_root=False)

                await task.wait_if_paused()
                if task.is_cancelled():
                    return

                # 6. 智能分类和移动
                if task.auto_classify:
                    task.update_progress(80, "智能分类")
                    final_path = await classifier.classify_and_move(renamed_path, metadata, task)
                    task.output_path = final_path

                # 7. 移动压缩包到已处理目录
                task.update_progress(95, "归档压缩包")
                await self._archive_source_file(task)

                task.update_progress(100, "完成")
                task.complete()
                
            elif task.type == TaskType.PROCESS_EXISTING_FOLDER:
                # 处理已存在的文件夹（跳过解压）
                filter_service = FilterService()
                metadata_service = MetadataService()
                classifier = SmartClassifier()
                
                # source_path 直接是已存在的文件夹路径
                existing_folder_path = task.source_path
                
                # 0. 预检：检查是否重复（包括关联作品）
                task.update_progress(5, "预检中")
                rjcode = self._extract_rjcode(existing_folder_path)
                if rjcode and task.auto_classify:
                    # 使用改进的查重服务检查关联作品
                    from .duplicate_service import get_duplicate_service
                    duplicate_service = get_duplicate_service()
                    
                    check_result = await duplicate_service.check_duplicate_enhanced(
                        rjcode,
                        check_linked_works=True,
                        cue_languages=['CHI_HANS', 'CHI_HANT', 'ENG']
                    )
                    
                    if check_result.is_duplicate:
                        # 发现重复或关联作品冲突
                        conflict_type = check_result.conflict_type
                        
                        if check_result.direct_duplicate:
                            # 直接重复
                            logger.warning(f"作品 {rjcode} 已存在: {check_result.direct_duplicate['path']}")
                        elif check_result.linked_works_found:
                            # 关联作品冲突
                            linked_rjcodes = [w['rjcode'] for w in check_result.linked_works_found]
                            logger.warning(f"作品 {rjcode} 发现关联作品冲突: {linked_rjcodes}")
                        
                        # 添加到问题作品列表，包含关联作品信息
                        classifier._add_to_conflict_works(
                            task.id,
                            rjcode,
                            conflict_type,
                            check_result.direct_duplicate['path'] if check_result.direct_duplicate else 
                            (check_result.linked_works_found[0]['path'] if check_result.linked_works_found else "未知路径"),
                            existing_folder_path,
                            {},  # 尚无元数据
                            linked_works_info=check_result.linked_works_found,
                            analysis_info=check_result.analysis_info,
                            related_rjcodes=check_result.related_rjcodes
                        )
                        
                        logger.info(f"作品 {rjcode} 已存在或有关联作品冲突，已添加到问题作品列表")
                        task.status = TaskStatus.COMPLETED
                        task.update_progress(100, f"发现{get_conflict_type_name(conflict_type)}，请在问题作品页面处理")
                        task.completed_at = datetime.utcnow()
                        return
                    
                    # 再检查是否正在处理中
                    is_processing = await classifier.check_duplicate_before_extract(rjcode, task, self)
                    if is_processing:
                        logger.info(f"作品 {rjcode} 正在处理中，已添加到问题作品列表")
                        task.status = TaskStatus.COMPLETED
                        task.update_progress(100, "正在处理中，请在问题作品页面查看")
                        task.completed_at = datetime.utcnow()
                        return
                
                # 直接使用已存在的文件夹路径，不需要解压
                extracted_path = existing_folder_path
                
                await task.wait_if_paused()
                if task.is_cancelled():
                    return
                
                # 1. 获取元数据
                task.update_progress(30, "获取元数据")
                metadata = await metadata_service.fetch(extracted_path, task)
                task.task_metadata = metadata
                
                await task.wait_if_paused()
                if task.is_cancelled():
                    return
                
                # 2. 重命名文件夹
                task.update_progress(50, "重命名文件夹")
                from .rename_service import RenameService
                rename_service = RenameService()
                renamed_path = await rename_service.rename(extracted_path, task)
                
                await task.wait_if_paused()
                if task.is_cancelled():
                    return
                
                # 3. 过滤（在重命名后的文件夹上进行）
                task.update_progress(70, "过滤文件中")
                await filter_service.filter(renamed_path, task)
                
                await task.wait_if_paused()
                if task.is_cancelled():
                    return
                
                # 4. 扁平化单层文件夹（在过滤之后，移动之前）
                from ..config.settings import get_config
                config = get_config()
                if config.rename.flatten_single_subfolder:
                    task.update_progress(75, "扁平化文件夹结构")
                    renamed_path = rename_service._flatten_single_subfolder(renamed_path)
                    logger.info(f"任务引擎 - 扁平化后路径: {renamed_path}")
                
                # 4.5 移除空文件夹（在扁平化之后）
                if config.rename.remove_empty_folders:
                    task.update_progress(78, "清理空文件夹")
                    rename_service.remove_empty_folders(renamed_path, remove_root=False)
                
                await task.wait_if_paused()
                if task.is_cancelled():
                    return
                
                # 5. 智能分类和移动
                if task.auto_classify:
                    task.update_progress(80, "智能分类")
                    final_path = await classifier.classify_and_move(renamed_path, metadata, task)
                    task.output_path = final_path
                
                task.update_progress(100, "完成")
                task.complete()
                
            else:
                # 单个步骤处理
                if task.type == TaskType.EXTRACT:
                    service = ExtractService()
                    task.output_path = await service.extract(task)
                elif task.type == TaskType.FILTER:
                    service = FilterService()
                    await service.filter(task.source_path, task)
                elif task.type == TaskType.METADATA:
                    service = MetadataService()
                    task.task_metadata = await service.fetch(task.source_path, task)
                elif task.type == TaskType.RENAME:
                    service = RenameService()
                    await service.rename(task.source_path, task)
                
                task.complete()
                
        except Exception as e:
            logger.error(f"任务 {task.id} 失败: {e}", exc_info=True)
            task.fail(str(e))
        finally:
            # 清理任务产生的临时文件（无论成功还是失败）
            await self._cleanup_failed_task(task)
            self.processing.discard(task.id)
            # 清除RJ号处理标记
            if task.rjcode:
                self.unmark_rjcode_processing(task.rjcode)
            await self._notify_progress(task)
    
    async def _worker(self):
        """工作线程"""
        while not self._shutdown:
            try:
                # 控制并发数
                while len(self.processing) >= self.max_concurrent:
                    await asyncio.sleep(0.1)
                
                task = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                self.processing.add(task.id)
                
                # 创建任务处理协程
                asyncio.create_task(self._process_task(task))
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"工作线程错误: {e}")
    
    def start(self):
        """启动引擎"""
        if not self._worker_task:
            self._worker_task = asyncio.create_task(self._worker())
            logger.info("任务引擎已启动")
    
    def stop(self):
        """停止引擎"""
        self._shutdown = True
        if self._worker_task:
            self._worker_task.cancel()
    
    def pause_task(self, task_id: str):
        """暂停任务"""
        if task_id in self.tasks:
            self.tasks[task_id].pause()
    
    def resume_task(self, task_id: str):
        """恢复任务"""
        if task_id in self.tasks:
            self.tasks[task_id].resume()
    
    def cancel_task(self, task_id: str):
        """取消任务"""
        if task_id in self.tasks:
            self.tasks[task_id].cancel()
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def update_task_status(self, task_id: str, status: TaskStatus, message: Optional[str] = None):
        """更新任务状态"""
        task = self.tasks.get(task_id)
        if task:
            task.status = status
            if message:
                task.current_step = message
            if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                task.completed_at = datetime.utcnow()
            logger.info(f"任务 {task_id} 状态更新为: {status.value}")
            return True
        return False
    
    def get_all_tasks(self) -> list[Task]:
        """获取所有任务，按创建时间倒序排列"""
        return sorted(self.tasks.values(), key=lambda t: t.created_at, reverse=True)
    
    def get_pending_tasks(self) -> list[Task]:
        """获取待处理任务，按创建时间倒序排列"""
        return sorted([t for t in self.tasks.values() if t.status == TaskStatus.PENDING], 
                     key=lambda t: t.created_at, reverse=True)
    
    def get_processing_tasks(self) -> list[Task]:
        """获取进行中任务，按创建时间倒序排列"""
        return sorted([t for t in self.tasks.values() if t.status == TaskStatus.PROCESSING], 
                     key=lambda t: t.created_at, reverse=True)
    
    def get_completed_tasks(self) -> list[Task]:
        """获取已完成任务，按创建时间倒序排列"""
        return sorted([t for t in self.tasks.values() if t.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]], 
                     key=lambda t: t.created_at, reverse=True)
    
    def _extract_rjcode(self, path: str) -> Optional[str]:
        """从路径中提取RJ号"""
        import re
        pattern = r'[RVB]J(\d{6}|\d{8})(?!\d)'
        match = re.search(pattern, path, re.IGNORECASE)
        if match:
            return match.group(0).upper()
        return None

    async def _cleanup_failed_task(self, task: Task):
        """清理失败任务产生的临时文件"""
        from ..config.settings import get_config
        
        config = get_config()
        cleaned_paths = []
        
        # 对于 PROCESS_EXISTING_FOLDER 类型，成功完成的任务不需要清理
        # 因为文件夹是直接从已有目录处理的，不是临时文件
        if task.type == TaskType.PROCESS_EXISTING_FOLDER:
            if task.status == TaskStatus.COMPLETED:
                # 成功完成的已有文件夹处理任务，不需要清理任何文件
                logger.info(f"已有文件夹处理任务成功完成，跳过清理: {task.source_path}")
                return
            # 失败的已有文件夹处理任务，只清理可能创建的临时文件
            # 不清理 source_path 或 output_path，因为那是用户的原始文件
            logger.info(f"已有文件夹处理任务失败，跳过清理原始文件: {task.source_path}")
            return
        
        # 1. 清理 output_path（如果已设置）- 只针对失败的任务
        if task.status == TaskStatus.FAILED and task.output_path and os.path.exists(task.output_path):
            try:
                shutil.rmtree(task.output_path)
                cleaned_paths.append(task.output_path)
                logger.info(f"清理失败任务缓存: {task.output_path}")
            except Exception as e:
                logger.warning(f"清理失败任务缓存失败: {task.output_path}, {e}")
        
        # 2. 如果是自动处理流程，检查并清理temp目录下所有可能的残留
        if task.type == TaskType.AUTO_PROCESS and task.source_path:
            source_name = Path(task.source_path).stem
            temp_path = config.storage.temp_path
            
            # 检查更多可能的目录名（包括带序号的后缀）
            possible_names = [
                source_name,
                f"{source_name}_1",
                f"{source_name}_2",
                f"{source_name}_3",
                f"{source_name}_temp",
            ]
            
            for name in possible_names:
                path = os.path.join(temp_path, name)
                if os.path.exists(path) and path not in cleaned_paths:
                    try:
                        shutil.rmtree(path)
                        cleaned_paths.append(path)
                        logger.info(f"清理残留目录: {path}")
                    except Exception as e:
                        logger.warning(f"清理残留目录失败: {path}, {e}")
        
        # 3. 如果任务状态是 failed，且是解压步骤失败，额外检查
        if task.status == TaskStatus.FAILED and task.source_path:
            # 检查是否有错误信息提示是解压失败
            if task.error_message and ("解压" in task.error_message or "密码" in task.error_message):
                source_name = Path(task.source_path).stem
                temp_path = config.storage.temp_path
                potential_path = os.path.join(temp_path, source_name)
                
                if os.path.exists(potential_path) and potential_path not in cleaned_paths:
                    try:
                        shutil.rmtree(potential_path)
                        logger.info(f"清理解压失败残留: {potential_path}")
                    except Exception as e:
                        logger.warning(f"清理解压失败残留失败: {potential_path}, {e}")

    async def _archive_source_file(self, task: Task):
        """将源压缩包移动到已处理目录并记录"""
        import shutil
        import uuid
        import os
        import re
        from datetime import datetime
        from ..config.settings import get_config
        from ..models.database import ProcessedArchive, get_db

        config = get_config()
        source_path = task.source_path
        processed_dir = config.storage.processed_archives_path

        # 检查是否需要跳过归档（重新解压的情况）
        if task.skip_archive:
            logger.info(f"任务标记为跳过归档，更新处理记录: {source_path}")
            # 只更新数据库中的处理次数和时间
            filename = os.path.basename(source_path)
            
            db = next(get_db())
            try:
                # 尝试通过文件名查找记录
                existing_record = db.query(ProcessedArchive).filter(
                    ProcessedArchive.filename == filename
                ).first()
                
                logger.info(f"查找记录 - 文件名: {filename}, 找到: {existing_record is not None}")
                
                # 如果通过文件名找不到，尝试通过当前路径查找
                if not existing_record:
                    # 尝试多种路径匹配方式
                    existing_record = db.query(ProcessedArchive).filter(
                        ProcessedArchive.current_path == source_path
                    ).first()
                    logger.info(f"通过完整路径查找: {source_path}, 找到: {existing_record is not None}")
                    
                    # 如果还找不到，尝试通过文件名模糊匹配
                    if not existing_record:
                        all_records = db.query(ProcessedArchive).filter(
                            ProcessedArchive.filename.like(f'%{filename}%')
                        ).all()
                        logger.info(f"模糊查找 {filename}，找到 {len(all_records)} 条记录")
                        if len(all_records) == 1:
                            existing_record = all_records[0]
                            logger.info(f"使用模糊匹配的记录: {existing_record.filename}")
                
                if existing_record:
                    old_count = existing_record.process_count or 0
                    old_status = existing_record.status
                    logger.info(f"更新记录前 - ID: {existing_record.id}, 旧次数: {old_count}, 旧状态: {old_status}")
                    
                    existing_record.process_count = old_count + 1
                    existing_record.processed_at = datetime.utcnow()
                    existing_record.status = 'completed'
                    db.commit()
                    
                    # 重新查询验证更新
                    db.expire_all()
                    verified = db.query(ProcessedArchive).filter(
                        ProcessedArchive.id == existing_record.id
                    ).first()
                    logger.info(f"更新记录后 - 新次数: {verified.process_count}, 新状态: {verified.status}")
                else:
                    logger.error(f"未找到归档记录: {filename}，无法更新状态")
                    # 列出所有记录帮助调试
                    all_files = db.query(ProcessedArchive.filename).all()
                    logger.info(f"数据库中所有文件名: {[f[0] for f in all_files[:10]]}")
            except Exception as e:
                logger.error(f"更新处理记录失败: {e}", exc_info=True)
                try:
                    db.rollback()
                except:
                    pass
            finally:
                db.close()
            return

        # 检查源文件是否存在
        if not os.path.exists(source_path):
            logger.warning(f"源文件不存在，无法归档: {source_path}")
            return
        
        # 检测是否是分卷压缩包，如果是则获取所有分卷文件
        files_to_archive = [source_path]
        source_dir = os.path.dirname(source_path)
        filename = os.path.basename(source_path)
        
        # 检查是否是分卷压缩的首卷（支持 .rar, .zip, .7z, .exe 等格式）
        # 匹配模式：filename.part1.rar, filename.part2.rar, filename.part1.exe（自解压）
        part_match = re.search(r'^(.*)\.part(\d+)\.(rar|zip|7z|exe)$', filename, re.IGNORECASE)
        if part_match:
            base_name = part_match.group(1)  # 基础名称（不含 .part 和扩展名）
            # 查找所有分卷文件（只要是相同的 base_name + .partX 就认为是同一组）
            for f in os.listdir(source_dir):
                # 匹配同一基础名称的所有分卷文件（忽略扩展名差异）
                if re.match(rf'{re.escape(base_name)}\.part\d+\.(rar|zip|7z|exe)$', f, re.IGNORECASE):
                    volume_path = os.path.join(source_dir, f)
                    if volume_path not in files_to_archive:
                        files_to_archive.append(volume_path)
            logger.info(f"检测到分卷压缩包，共 {len(files_to_archive)} 个分卷文件: {[os.path.basename(f) for f in files_to_archive]}")
        
        # 移动所有文件
        archived_files = []

        try:
            # 确保已处理目录存在
            os.makedirs(processed_dir, exist_ok=True)

            # 移动所有分卷文件（或单个文件）
            for file_path in files_to_archive:
                filename = os.path.basename(file_path)
                dest_path = os.path.join(processed_dir, filename)
                
                # 处理重名
                counter = 1
                original_dest = dest_path
                while os.path.exists(dest_path):
                    name, ext = os.path.splitext(filename)
                    dest_path = os.path.join(processed_dir, f"{name}({counter}){ext}")
                    counter += 1

                # 移动文件
                shutil.move(file_path, dest_path)
                logger.info(f"压缩包已归档: {file_path} -> {dest_path}")
                archived_files.append((filename, dest_path, file_path))

            # 记录主文件（第一个分卷或唯一文件）到数据库
            if archived_files:
                main_filename, main_dest_path, main_source_path = archived_files[0]
                rjcode = self._extract_rjcode(main_source_path)
                file_size = os.path.getsize(main_dest_path)

                db = next(get_db())
                try:
                    # 查找是否已存在相同文件名的记录
                    existing_record = db.query(ProcessedArchive).filter(
                        ProcessedArchive.filename == main_filename
                    ).first()
                    
                    if existing_record:
                        # 更新已有记录
                        existing_record.current_path = main_dest_path
                        existing_record.file_size = file_size
                        existing_record.processed_at = datetime.utcnow()
                        existing_record.process_count = (existing_record.process_count or 1) + 1
                        existing_record.task_id = task.id
                        existing_record.status = 'completed'
                        logger.info(f"更新压缩包归档记录: {main_filename}，处理次数: {existing_record.process_count}")
                    else:
                        # 创建新记录
                        from datetime import datetime
                        now = datetime.utcnow()
                        archive_record = ProcessedArchive(
                            id=str(uuid.uuid4()),
                            original_path=main_source_path,
                            current_path=main_dest_path,
                            filename=main_filename,
                            rjcode=rjcode or '',
                            file_size=file_size,
                            processed_at=now,  # 显式设置处理时间
                            process_count=1,
                            task_id=task.id,
                            status='completed'
                        )
                        db.add(archive_record)
                        logger.info(f"已记录压缩包归档信息: {main_filename}, 时间: {now}")
                    
                    db.commit()
                except Exception as e:
                    logger.error(f"记录压缩包归档信息失败: {e}")
                    db.rollback()
                finally:
                    db.close()

        except Exception as e:
            logger.error(f"归档压缩包失败: {e}")

# 全局任务引擎实例
_task_engine: Optional[TaskEngine] = None

def get_task_engine() -> TaskEngine:
    """获取任务引擎实例"""
    global _task_engine
    if _task_engine is None:
        _task_engine = TaskEngine()
    return _task_engine
