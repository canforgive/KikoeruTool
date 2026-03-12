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
    WAITING_RETRY = "waiting_retry"  # 等待重试（未找到版本等）
    COMPLETED = "completed"
    FAILED = "failed"

class TaskType(str, Enum):
    EXTRACT = "extract"
    FILTER = "filter"
    METADATA = "metadata"
    RENAME = "rename"
    AUTO_PROCESS = "auto_process"
    PROCESS_EXISTING_FOLDER = "process_existing_folder"  # 处理已存在的文件夹（跳过解压）
    ASMR_SYNC_DOWNLOAD = "asmr_sync_download"  # ASMR 同步下载任务

class Task:
    """任务对象"""
    def __init__(
        self,
        task_type: TaskType,
        source_path: str,
        output_path: Optional[str] = None,
        auto_classify: bool = False,
        metadata: Optional[dict] = None,
        skip_archive: bool = False,
        task_id: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        rjcode: Optional[str] = None
    ):
        self.id = task_id if task_id else str(uuid.uuid4())
        self.type = task_type
        self.status = status if status else TaskStatus.PENDING
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
        self.rjcode = rjcode  # 作品的RJ号，用于重复检测
    
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

    def set_waiting_retry(self, reason: str, retry_after: datetime = None):
        """设置等待重试状态"""
        self.status = TaskStatus.WAITING_RETRY
        self.current_step = f"等待重试: {reason}"
        self.task_metadata['retry_reason'] = reason
        self.task_metadata['retry_after'] = retry_after.isoformat() if retry_after else None
        self.task_metadata['retry_count'] = self.task_metadata.get('retry_count', 0) + 1
        logger.info(f"任务 {self.id} 进入等待重试状态: {reason}")

    def can_retry_now(self) -> bool:
        """检查是否可以重试"""
        if self.status != TaskStatus.WAITING_RETRY:
            return False
        retry_after = self.task_metadata.get('retry_after')
        if retry_after:
            from datetime import datetime
            return datetime.fromisoformat(retry_after) <= datetime.utcnow()
        return True

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
        self._retry_scheduler_task: Optional[asyncio.Task] = None  # 重试调度器任务

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
        rjcode = self._extract_rjcode(task.source_path) or "未知"
        logger.info(f"[{rjcode}] 任务提交 - ID: {task.id[:8]}..., 源文件: {os.path.basename(task.source_path)}")
        return task.id
    
    async def _process_task(self, task: Task):
        """处理单个任务"""
        from .extract_service import ExtractService
        from .filter_service import FilterService
        from .metadata_service import MetadataService
        from .rename_service import RenameService
        from .classifier import SmartClassifier
        
        rjcode = self._extract_rjcode(task.source_path) or "未知"
        task.rjcode = rjcode
        logger.info(f"[{rjcode}] ========== 开始处理任务 ==========")
        logger.info(f"[{rjcode}] 任务ID: {task.id}, 类型: {task.type.value}")
        logger.info(f"[{rjcode}] 源路径: {task.source_path}")
        
        try:
            task.start()
            await self._notify_progress(task)
            
            if task.type == TaskType.AUTO_PROCESS:
                extract_service = ExtractService()
                filter_service = FilterService()
                metadata_service = MetadataService()
                classifier = SmartClassifier()
                
                logger.debug(f"[{rjcode}] 步骤0: 预检重复")
                task.update_progress(5, "预检中")
                rjcode = self._extract_rjcode(task.source_path)
                logger.debug(f"[{rjcode}] 提取到的RJ号: {rjcode}")
                if rjcode and task.auto_classify:
                    is_duplicate = await classifier.check_duplicate_before_extract(rjcode, task, self)
                    logger.debug(f"[{rjcode}] 重复检查结果: {is_duplicate}")
                    if is_duplicate:
                        logger.info(f"[{rjcode}] 作品已存在或正在处理中，已添加到问题作品列表")
                        task.status = TaskStatus.COMPLETED
                        task.update_progress(100, "重复作品，请在问题作品页面处理")
                        task.completed_at = datetime.utcnow()
                        return
                
                logger.debug(f"[{rjcode}] 步骤1: 解压")
                task.update_progress(10, "解压中")
                extracted_path = await extract_service.extract(task)
                logger.debug(f"[{rjcode}] 解压结果路径: {extracted_path}")
                if not extracted_path:
                    logger.error(f"[{rjcode}] 解压失败，任务终止")
                    return

                await task.wait_if_paused()
                if task.is_cancelled():
                    logger.info(f"[{rjcode}] 任务已取消")
                    return

                logger.debug(f"[{rjcode}] 步骤2: 获取元数据")
                task.update_progress(40, "获取元数据")
                metadata = await metadata_service.fetch(extracted_path, task)
                logger.debug(f"[{rjcode}] 元数据: {metadata.get('work_name', '未知')}")
                task.task_metadata = metadata

                await task.wait_if_paused()
                if task.is_cancelled():
                    return

                logger.debug(f"[{rjcode}] 步骤3: 重命名")
                task.update_progress(60, "重命名文件夹")
                from .rename_service import RenameService
                rename_service = RenameService()
                renamed_path = await rename_service.rename(extracted_path, task)
                logger.debug(f"[{rjcode}] 重命名后路径: {renamed_path}")

                await task.wait_if_paused()
                if task.is_cancelled():
                    return

                logger.debug(f"[{rjcode}] 步骤4: 过滤")
                task.update_progress(75, "过滤文件中")
                await filter_service.filter(renamed_path, task)

                await task.wait_if_paused()
                if task.is_cancelled():
                    return

                logger.debug(f"[{rjcode}] 步骤5: 扁平化")
                from ..config.settings import get_config
                config = get_config()
                if config.rename.flatten_single_subfolder:
                    task.update_progress(78, "扁平化文件夹结构")
                    renamed_path = rename_service._flatten_single_subfolder(renamed_path)
                    logger.debug(f"[{rjcode}] 扁平化后路径: {renamed_path}")

                if config.rename.remove_empty_folders:
                    task.update_progress(79, "清理空文件夹")
                    rename_service.remove_empty_folders(renamed_path, remove_root=False)

                await task.wait_if_paused()
                if task.is_cancelled():
                    return

                # 步骤5.5: 字幕文件繁体转简体（如果启用）
                if getattr(config.asmr_sync, 'simplify_chinese_enabled', False) if hasattr(config, 'asmr_sync') else False:
                    task.update_progress(79, "字幕繁体转简体")
                    from .subtitle_sync_service import get_subtitle_sync_service
                    subtitle_svc = get_subtitle_sync_service()
                    simplify_result = subtitle_svc.convert_subtitles_to_simplified_in_folder(renamed_path)
                    if simplify_result['converted_files'] > 0:
                        logger.info(f"[{rjcode}] 字幕繁简转换完成: 处理 {simplify_result['total_files']} 个文件, "
                                   f"转换 {simplify_result['converted_files']} 个文件")

                await task.wait_if_paused()
                if task.is_cancelled():
                    return

                logger.debug(f"[{rjcode}] 步骤6: 智能分类")
                if task.auto_classify:
                    task.update_progress(80, "智能分类")
                    final_path = await classifier.classify_and_move(renamed_path, metadata, task)
                    task.output_path = final_path
                    logger.debug(f"[{rjcode}] 分类后路径: {final_path}")

                logger.debug(f"[{rjcode}] 步骤7: 归档压缩包")
                task.update_progress(95, "归档压缩包")
                await self._archive_source_file(task)

                task.update_progress(100, "完成")
                task.complete()
                logger.info(f"[{rjcode}] ========== 任务完成 ==========")
                
            elif task.type == TaskType.PROCESS_EXISTING_FOLDER:
                filter_service = FilterService()
                metadata_service = MetadataService()
                classifier = SmartClassifier()
                
                existing_folder_path = task.source_path
                logger.debug(f"[{rjcode}] 处理已存在文件夹: {existing_folder_path}")
                
                logger.debug(f"[{rjcode}] 步骤0: 预检重复")
                task.update_progress(5, "预检中")
                rjcode = self._extract_rjcode(existing_folder_path)
                logger.debug(f"[{rjcode}] 提取到的RJ号: {rjcode}")
                if rjcode and task.auto_classify:
                    from .duplicate_service import get_duplicate_service
                    duplicate_service = get_duplicate_service()
                    
                    check_result = await duplicate_service.check_duplicate_enhanced(
                        rjcode,
                        check_linked_works=True,
                        cue_languages=['CHI_HANS', 'CHI_HANT', 'ENG']
                    )
                    logger.debug(f"[{rjcode}] 重复检查结果: is_duplicate={check_result.is_duplicate}")
                    
                    if check_result.is_duplicate:
                        conflict_type = check_result.conflict_type
                        
                        if check_result.direct_duplicate:
                            logger.warning(f"[{rjcode}] 已存在: {check_result.direct_duplicate['path']}")
                        elif check_result.linked_works_found:
                            linked_rjcodes = [w['rjcode'] for w in check_result.linked_works_found]
                            logger.warning(f"[{rjcode}] 关联作品冲突: {linked_rjcodes}")
                        
                        classifier._add_to_conflict_works(
                            task.id,
                            rjcode,
                            conflict_type,
                            check_result.direct_duplicate['path'] if check_result.direct_duplicate else 
                            (check_result.linked_works_found[0]['path'] if check_result.linked_works_found else "未知路径"),
                            existing_folder_path,
                            {},
                            linked_works_info=check_result.linked_works_found,
                            analysis_info=check_result.analysis_info,
                            related_rjcodes=check_result.related_rjcodes
                        )
                        
                        logger.info(f"[{rjcode}] 已添加到问题作品列表")
                        task.status = TaskStatus.COMPLETED
                        task.update_progress(100, f"发现{get_conflict_type_name(conflict_type)}，请在问题作品页面处理")
                        task.completed_at = datetime.utcnow()
                        return
                    
                    is_processing = await classifier.check_duplicate_before_extract(rjcode, task, self)
                    if is_processing:
                        logger.info(f"[{rjcode}] 正在处理中，已添加到问题作品列表")
                        task.status = TaskStatus.COMPLETED
                        task.update_progress(100, "正在处理中，请在问题作品页面查看")
                        task.completed_at = datetime.utcnow()
                        return
                
                extracted_path = existing_folder_path
                
                await task.wait_if_paused()
                if task.is_cancelled():
                    return
                
                logger.debug(f"[{rjcode}] 步骤1: 获取元数据")
                task.update_progress(30, "获取元数据")
                metadata = await metadata_service.fetch(extracted_path, task)
                logger.debug(f"[{rjcode}] 元数据: {metadata.get('work_name', '未知')}")
                task.task_metadata = metadata
                
                await task.wait_if_paused()
                if task.is_cancelled():
                    return
                
                logger.debug(f"[{rjcode}] 步骤2: 重命名")
                task.update_progress(50, "重命名文件夹")
                from .rename_service import RenameService
                rename_service = RenameService()
                renamed_path = await rename_service.rename(extracted_path, task)
                logger.debug(f"[{rjcode}] 重命名后路径: {renamed_path}")

                await task.wait_if_paused()
                if task.is_cancelled():
                    return

                # 获取配置
                from ..config.settings import get_config
                config = get_config()

                # 简繁转换（在重命名后、过滤前）
                if hasattr(config, 'asmr_sync') and getattr(config.asmr_sync, 'simplify_chinese_enabled', False):
                    from .subtitle_sync_service import SubtitleSyncService
                    subtitle_svc = SubtitleSyncService()
                    task.update_progress(60, "字幕繁简转换中")
                    simplify_result = subtitle_svc.convert_subtitles_to_simplified_in_folder(renamed_path)
                    if simplify_result['converted_files'] > 0:
                        logger.info(f"[{rjcode}] 字幕繁简转换完成: 处理 {simplify_result['total_files']} 个文件, "
                                   f"转换 {simplify_result['converted_files']} 个文件")

                await task.wait_if_paused()
                if task.is_cancelled():
                    return

                logger.debug(f"[{rjcode}] 步骤3: 过滤")
                task.update_progress(70, "过滤文件中")
                await filter_service.filter(renamed_path, task)

                await task.wait_if_paused()
                if task.is_cancelled():
                    return

                logger.debug(f"[{rjcode}] 步骤4: 扁平化")
                if config.rename.flatten_single_subfolder:
                    task.update_progress(75, "扁平化文件夹结构")
                    renamed_path = rename_service._flatten_single_subfolder(renamed_path)
                    logger.debug(f"[{rjcode}] 扁平化后路径: {renamed_path}")

                if config.rename.remove_empty_folders:
                    task.update_progress(78, "清理空文件夹")
                    rename_service.remove_empty_folders(renamed_path, remove_root=False)

                await task.wait_if_paused()
                if task.is_cancelled():
                    return

                logger.debug(f"[{rjcode}] 步骤5: 智能分类")
                if task.auto_classify:
                    task.update_progress(80, "智能分类")
                    final_path = await classifier.classify_and_move(renamed_path, metadata, task)
                    task.output_path = final_path
                    logger.debug(f"[{rjcode}] 分类后路径: {final_path}")
                
                task.update_progress(100, "完成")
                task.complete()
                logger.info(f"[{rjcode}] ========== 任务完成 ==========")
                
            else:
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
                elif task.type == TaskType.ASMR_SYNC_DOWNLOAD:
                    # ASMR 同步下载任务
                    await self._process_asmr_sync_download(task)

                # 只有当任务没有被设置为其他状态（如 waiting_retry）时才标记为完成
                if task.status == TaskStatus.PROCESSING:
                    task.complete()
                    logger.info(f"[{rjcode}] ========== 任务完成 ==========")
                
        except Exception as e:
            logger.error(f"[{rjcode}] 任务失败: {e}", exc_info=True)
            task.fail(str(e))
            logger.info(f"[{rjcode}] ========== 任务失败 ==========")
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

        # 启动重试调度器
        if not self._retry_scheduler_task:
            self._retry_scheduler_task = asyncio.create_task(self._retry_scheduler())
            logger.info("重试调度器已启动")

        # 加载等待重试的任务
        self.load_waiting_retry_tasks()

    async def _retry_scheduler(self):
        """定时重试调度器，使用cron表达式"""
        from croniter import croniter
        from ..config.settings import get_config

        while not self._shutdown:
            try:
                config = get_config()
                cron_expr = config.asmr_sync.retry_cron if hasattr(config, 'asmr_sync') else "0 */1 * * *"

                # 计算下次执行时间
                cron = croniter(cron_expr, datetime.utcnow())
                next_run = cron.get_next(datetime)
                wait_seconds = (next_run - datetime.utcnow()).total_seconds()

                logger.info(f"[重试调度器] Cron: {cron_expr}, 下次执行: {next_run.strftime('%Y-%m-%d %H:%M:%S')} UTC, 等待 {wait_seconds/3600:.1f} 小时")

                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)

                # 检查待重试任务
                await self._check_retry_tasks()

            except Exception as e:
                logger.error(f"重试调度器错误: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟再重试

    async def _check_retry_tasks(self):
        """检查并重试等待中的任务（由cron调度器触发）"""
        from ..config.settings import get_config

        config = get_config()
        max_retry = config.asmr_sync.max_retry_count if hasattr(config, 'asmr_sync') else 10

        retry_count = 0
        for task_id, task in list(self.tasks.items()):
            if task.status == TaskStatus.WAITING_RETRY:
                # 检查重试次数
                if task.task_metadata.get('retry_count', 0) >= max_retry:
                    logger.warning(f"任务 {task_id} 已达到最大重试次数 {max_retry}，标记为失败")
                    task.fail("已达到最大重试次数")
                    continue

                # cron调度器触发，直接重试所有等待中的任务
                logger.info(f"[Cron重试] 重试任务 {task_id}: {task.rjcode}")
                task.status = TaskStatus.PENDING
                task.current_step = "等待重试"
                await self.queue.put(task)
                retry_count += 1

        if retry_count > 0:
            logger.info(f"[Cron重试] 已将 {retry_count} 个任务加入重试队列")

    def stop(self):
        """停止引擎"""
        self._shutdown = True
        if self._worker_task:
            self._worker_task.cancel()
        if self._retry_scheduler_task:
            self._retry_scheduler_task.cancel()

    def retry_task(self, task_id: str):
        """手动重试等待中的任务"""
        logger.info(f"[重试] 尝试重试任务: {task_id}")
        logger.info(f"[重试] 当前内存中的任务: {list(self.tasks.keys())}")

        if task_id in self.tasks:
            task = self.tasks[task_id]
            logger.info(f"[重试] 找到任务 {task_id}, 状态: {task.status}, RJ号: {task.rjcode}")
            if task.status == TaskStatus.WAITING_RETRY:
                task.status = TaskStatus.PENDING
                task.current_step = "等待重试"
                asyncio.create_task(self.queue.put(task))
                logger.info(f"[重试] 任务 {task_id} ({task.rjcode}) 已加入重试队列")
                return True
            else:
                logger.warning(f"[重试] 任务 {task_id} 状态不是 WAITING_RETRY: {task.status}")
        else:
            logger.warning(f"[重试] 任务 {task_id} 不在内存中")
            # 尝试从数据库加载
            from ..models.database import WaitingRetryTask, SessionLocal
            db = SessionLocal()
            try:
                wt = db.query(WaitingRetryTask).filter(WaitingRetryTask.id == task_id).first()
                if wt:
                    logger.info(f"[重试] 从数据库找到任务: {wt.rjcode}")
                    # 创建任务并加入队列
                    task = Task(
                        task_type=TaskType.ASMR_SYNC_DOWNLOAD,
                        source_path=wt.subtitle_folder,
                        task_id=wt.id,
                        status=TaskStatus.PENDING,
                        rjcode=wt.rjcode
                    )
                    task.task_metadata = wt.task_metadata or {}
                    task.task_metadata['subtitle_folder'] = wt.subtitle_folder
                    task.task_metadata['work_title'] = wt.work_title
                    task.current_step = "手动重试"
                    self.tasks[task.id] = task
                    asyncio.create_task(self.queue.put(task))
                    # 从等待重试表删除
                    db.delete(wt)
                    db.commit()
                    logger.info(f"[重试] 任务 {task_id} ({wt.rjcode}) 从数据库加载并加入队列")
                    return True
            except Exception as e:
                logger.error(f"[重试] 从数据库加载任务失败: {e}")
            finally:
                db.close()
        return False

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

    def _save_waiting_retry_task(self, task: Task, subtitle_folder: str, work_title: str, retry_reason: str, retry_after):
        """保存等待重试任务到数据库"""
        from ..models.database import WaitingRetryTask, SessionLocal
        from ..config.settings import get_config
        import uuid

        logger.info(f"[等待重试] 开始保存任务 {task.rjcode} 到数据库...")
        db = SessionLocal()
        try:
            # 检查是否已存在
            existing = db.query(WaitingRetryTask).filter(WaitingRetryTask.rjcode == task.rjcode).first()
            if existing:
                # 更新现有记录
                existing.retry_count = (existing.retry_count or 0) + 1
                existing.retry_reason = retry_reason
                existing.retry_after = retry_after
                existing.updated_at = datetime.utcnow()
                existing.task_metadata = task.task_metadata
                logger.info(f"[等待重试] 更新任务 {task.rjcode}, 重试次数: {existing.retry_count}")
            else:
                # 创建新记录
                config = get_config()
                max_retry = config.asmr_sync.max_retry_count if hasattr(config, 'asmr_sync') else 10
                waiting_task = WaitingRetryTask(
                    id=str(uuid.uuid4()),
                    rjcode=task.rjcode,
                    subtitle_folder=subtitle_folder,
                    work_title=work_title,
                    retry_reason=retry_reason,
                    retry_count=1,
                    max_retry_count=max_retry,
                    retry_after=retry_after,
                    task_metadata=task.task_metadata
                )
                db.add(waiting_task)
                logger.info(f"[等待重试] 创建新任务记录 {task.rjcode}")
            db.commit()
            logger.info(f"[等待重试] 任务 {task.rjcode} 已提交到数据库")

            # 验证保存结果
            count = db.query(WaitingRetryTask).count()
            logger.info(f"[等待重试] 数据库中当前共有 {count} 条等待重试记录")
        except Exception as e:
            logger.error(f"[等待重试] 保存任务失败: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()

    def _remove_waiting_retry_task(self, rjcode: str):
        """从数据库删除等待重试任务"""
        from ..models.database import WaitingRetryTask, SessionLocal

        db = SessionLocal()
        try:
            db.query(WaitingRetryTask).filter(WaitingRetryTask.rjcode == rjcode).delete()
            db.commit()
            logger.info(f"[等待重试] 删除任务 {rjcode}")
        except Exception as e:
            logger.error(f"[等待重试] 删除任务失败: {e}")
            db.rollback()
        finally:
            db.close()

    def _remove_waiting_retry_task_by_id(self, task_id: str):
        """从数据库删除等待重试任务（通过任务ID）"""
        from ..models.database import WaitingRetryTask, SessionLocal

        db = SessionLocal()
        try:
            db.query(WaitingRetryTask).filter(WaitingRetryTask.id == task_id).delete()
            db.commit()
            logger.info(f"[等待重试] 删除任务 ID: {task_id}")
        except Exception as e:
            logger.error(f"[等待重试] 删除任务失败: {e}")
            db.rollback()
        finally:
            db.close()

    def load_waiting_retry_tasks(self):
        """从数据库加载等待重试的任务"""
        from ..models.database import WaitingRetryTask, SessionLocal, get_db_path_info

        db_path = get_db_path_info()
        logger.info(f"[等待重试] 开始从数据库加载等待重试任务...")
        logger.info(f"[等待重试] 数据库路径: {db_path}")

        db = SessionLocal()
        try:
            waiting_tasks = db.query(WaitingRetryTask).all()
            logger.info(f"[等待重试] 数据库中找到 {len(waiting_tasks)} 条等待重试记录")

            loaded_count = 0
            for wt in waiting_tasks:
                # 检查是否已加载
                if wt.rjcode in [t.rjcode for t in self.tasks.values() if t.status == TaskStatus.WAITING_RETRY]:
                    logger.debug(f"[等待重试] 任务 {wt.rjcode} 已在内存中，跳过")
                    continue

                # 创建任务对象
                task = Task(
                    task_type=TaskType.ASMR_SYNC_DOWNLOAD,
                    source_path=wt.subtitle_folder,
                    task_id=wt.id,
                    status=TaskStatus.WAITING_RETRY,
                    rjcode=wt.rjcode
                )
                task.task_metadata = wt.task_metadata or {}
                task.task_metadata['subtitle_folder'] = wt.subtitle_folder
                task.task_metadata['work_title'] = wt.work_title
                task.task_metadata['retry_reason'] = wt.retry_reason
                task.task_metadata['retry_count'] = wt.retry_count
                task.task_metadata['retry_after'] = wt.retry_after.isoformat() if wt.retry_after else None
                task.current_step = f"等待重试: {wt.retry_reason}"

                self.tasks[task.id] = task
                loaded_count += 1
                logger.info(f"[等待重试] 加载任务 {wt.rjcode}, 重试次数: {wt.retry_count}")

            logger.info(f"[等待重试] 共加载 {loaded_count} 个等待重试任务")
            return loaded_count
        except Exception as e:
            logger.error(f"[等待重试] 加载任务失败: {e}", exc_info=True)
            return 0
        finally:
            db.close()

    def get_waiting_retry_tasks_from_db(self):
        """从数据库获取等待重试任务列表（用于API返回）"""
        from ..models.database import WaitingRetryTask, SessionLocal

        db = SessionLocal()
        try:
            waiting_tasks = db.query(WaitingRetryTask).all()
            return [wt.to_dict() for wt in waiting_tasks]
        except Exception as e:
            logger.error(f"[等待重试] 获取任务列表失败: {e}")
            return []
        finally:
            db.close()
    
    def _extract_rjcode(self, path: str) -> Optional[str]:
        """从路径中提取RJ号
        
        支持格式：
        - RJ123456, RJ12345678
        - VJ123456, BJ123456
        - 纯数字目录名：01503161 -> RJ01503161
        - 带前缀的数字：39.RJ01570159 -> RJ01570159
        """
        import re
        
        # 优先匹配标准格式 [RVB]J + 6/8位数字
        pattern = r'[RVB]J(\d{6}|\d{8})(?!\d)'
        match = re.search(pattern, path, re.IGNORECASE)
        if match:
            return match.group(0).upper()
        
        # 尝试从路径最后的目录/文件名中提取纯数字
        # 例如：E:\path\01503161 -> RJ01503161
        path_parts = re.split(r'[\\/]', path)
        if path_parts:
            last_part = path_parts[-1]
            # 移除常见前缀如 "39." 等
            clean_name = re.sub(r'^\d+\.', '', last_part)
            # 匹配6位或8位纯数字
            num_match = re.match(r'^(\d{6}|\d{8})$', clean_name)
            if num_match:
                num = num_match.group(1)
                return f"RJ{num}"
        
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

        logger.info(f"[Archive] 开始归档检测 - source_path: {source_path}")
        logger.info(f"[Archive] source_dir: {source_dir}, filename: {filename}")

        # 检查是否是分卷压缩的首卷
        # 格式1: .partX.rar/zip/7z/exe (如 filename.part1.rar) - 带扩展名的分卷
        part_match = re.search(r'^(.*)\.part(\d+)\.(rar|zip|7z|exe)$', filename, re.IGNORECASE)
        # 格式4: .part1, .part2, ... (无扩展名的RAR分卷格式) - 新增支持
        no_ext_part_match = re.search(r'^(.*)\.part(\d+)$', filename, re.IGNORECASE)
        # 格式2: .zip 首卷 + .z01, .z02... 分卷 (ZIP 分卷格式)
        zip_volume_match = re.search(r'^(.*)\.zip$', filename, re.IGNORECASE)
        # 格式3: .7z.001, .7z.002... 分卷 (7z 分卷格式)
        seven_z_volume_match = re.search(r'^(.*)\.7z\.001$', filename, re.IGNORECASE)

        logger.info(f"[Archive] 匹配结果 - part_match: {part_match is not None}, no_ext_part_match: {no_ext_part_match is not None}")
        
        if part_match:
            base_name = part_match.group(1)
            for f in os.listdir(source_dir):
                if re.match(rf'{re.escape(base_name)}\.part\d+\.(rar|zip|7z|exe)$', f, re.IGNORECASE):
                    volume_path = os.path.join(source_dir, f)
                    if volume_path not in files_to_archive:
                        files_to_archive.append(volume_path)
            logger.info(f"检测到分卷压缩包，共 {len(files_to_archive)} 个分卷文件: {[os.path.basename(f) for f in files_to_archive]}")
        elif no_ext_part_match:  # 新增无扩展名分卷格式的处理
            base_name = no_ext_part_match.group(1)
            for f in os.listdir(source_dir):
                if re.match(rf'{re.escape(base_name)}\.part\d+$', f, re.IGNORECASE):
                    volume_path = os.path.join(source_dir, f)
                    if volume_path not in files_to_archive:
                        files_to_archive.append(volume_path)
            logger.info(f"检测到无扩展名分卷压缩包，共 {len(files_to_archive)} 个分卷文件: {[os.path.basename(f) for f in files_to_archive]}")
        elif zip_volume_match:
            # 检查是否存在对应的 .zXX 分卷文件
            base_name = zip_volume_match.group(1)
            volume_files = []
            for f in os.listdir(source_dir):
                if re.match(rf'^{re.escape(base_name)}\.z\d+$', f, re.IGNORECASE):
                    volume_files.append(os.path.join(source_dir, f))
            if volume_files:
                # 找到分卷文件，将所有分卷加入归档列表
                files_to_archive.extend(volume_files)
                logger.info(f"检测到 ZIP 分卷压缩包，共 {len(files_to_archive)} 个文件: {[os.path.basename(f) for f in files_to_archive]}")
        elif seven_z_volume_match:
            # 检查是否存在对应的 .7z.XXX 分卷文件
            base_name = seven_z_volume_match.group(1)
            volume_files = []
            for f in os.listdir(source_dir):
                if re.match(rf'^{re.escape(base_name)}\.7z\.\d+$', f, re.IGNORECASE):
                    volume_files.append(os.path.join(source_dir, f))
            if volume_files:
                # 找到分卷文件，将所有分卷加入归档列表（排除已在列表中的首卷）
                for vf in volume_files:
                    if vf not in files_to_archive:
                        files_to_archive.append(vf)
                logger.info(f"检测到 7z 分卷压缩包，共 {len(files_to_archive)} 个文件: {[os.path.basename(f) for f in files_to_archive]}")
        
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

    async def _process_asmr_sync_download(self, task: Task):
        """
        处理 ASMR 同步下载任务

        task.task_metadata 应包含:
        - rjcode: RJ号
        - subtitle_folder: 字幕文件夹路径
        - work_title: 作品标题（可选）
        """
        from .asmr_download_service import get_asmr_download_service
        from .subtitle_sync_service import get_subtitle_sync_service
        from .rename_service import RenameService
        from .classifier import SmartClassifier
        from ..config.settings import get_config

        config = get_config()
        asmr_service = get_asmr_download_service()
        subtitle_service = get_subtitle_sync_service()
        rename_service = RenameService()
        classifier = SmartClassifier()

        rjcode = task.task_metadata.get('rjcode', '')
        subtitle_folder = task.task_metadata.get('subtitle_folder', '')
        work_title = task.task_metadata.get('work_title', '')

        logger.info(f"[{rjcode}] 开始 ASMR 同步下载任务")

        try:
            # 步骤1: 创建下载目录
            task.update_progress(5, "准备下载目录")
            temp_path = config.storage.temp_path
            download_dir = os.path.join(temp_path, f"{rjcode}_asmr_sync")
            os.makedirs(download_dir, exist_ok=True)

            # 步骤2: 获取作品信息和下载文件
            task.update_progress(10, "获取作品信息")

            def progress_callback(rj, current, total, step):
                progress = 10 + int((current / total) * 60) if total > 0 else 10
                task.update_progress(progress, step)

            # 获取筛选规则
            filter_rules = config.filter.rules
            logger.info(f"[ASMR同步] 筛选规则数量: {len(filter_rules)}")
            for i, rule in enumerate(filter_rules):
                if isinstance(rule, dict):
                    logger.info(f"[ASMR同步] 规则{i+1}: name={rule.get('name')}, enabled={rule.get('enabled')}, pattern={rule.get('pattern')}")
                else:
                    logger.info(f"[ASMR同步] 规则{i+1}: name={getattr(rule, 'name', '未知')}, enabled={getattr(rule, 'enabled', True)}, pattern={getattr(rule, 'pattern', '')}")

            # 存储文件下载进度
            task.task_metadata['download_files'] = []

            def file_progress_callback(file_name, file_index, total_files, downloaded_bytes, total_bytes):
                """单个文件的下载进度回调"""
                files = task.task_metadata.get('download_files', [])
                found = False
                for f in files:
                    if f['name'] == file_name:
                        f['downloaded'] = downloaded_bytes
                        f['total'] = total_bytes
                        f['progress'] = int((downloaded_bytes / total_bytes * 100)) if total_bytes > 0 else 0
                        found = True
                        break
                if not found:
                    files.append({
                        'name': file_name,
                        'index': file_index,
                        'total_files': total_files,
                        'downloaded': downloaded_bytes,
                        'total': total_bytes,
                        'progress': int((downloaded_bytes / total_bytes * 100)) if total_bytes > 0 else 0,
                        'status': 'downloading'
                    })
                task.task_metadata['download_files'] = files

            def check_pause():
                """检查任务是否被暂停"""
                return task.status == TaskStatus.PAUSED

            download_result = await asmr_service.download_work(
                rjcode=rjcode,
                dest_dir=download_dir,
                filter_rules=filter_rules,
                progress_callback=progress_callback,
                file_progress_callback=file_progress_callback,
                check_pause=check_pause
            )

            # 保存失败文件列表
            if download_result.get('failed_files'):
                task.task_metadata['failed_files'] = download_result['failed_files']

            # 处理暂停情况
            if download_result.get('paused'):
                logger.info(f"[{rjcode}] 下载被暂停，等待恢复...")
                task.update_progress(task.progress, "已暂停 - 等待恢复")
                await task.wait_if_paused()
                if task.is_cancelled():
                    return

            if not download_result['success']:
                # 检查是否是"未找到版本"错误
                error_msg = download_result.get('error', '下载失败')
                if '未找到该作品的任何版本' in error_msg or '未找到' in error_msg:
                    # 进入等待重试状态，使用 cron 计算下次重试时间
                    from croniter import croniter
                    cron_expr = config.asmr_sync.retry_cron if hasattr(config, 'asmr_sync') else "0 */1 * * *"
                    now = datetime.utcnow()
                    cron = croniter(cron_expr, now)
                    retry_after = cron.get_next(datetime)

                    task.set_waiting_retry(error_msg, retry_after)
                    task.task_metadata['subtitle_folder'] = subtitle_folder
                    task.task_metadata['work_title'] = work_title

                    # 保存到数据库持久化
                    self._save_waiting_retry_task(task, subtitle_folder, work_title, error_msg, retry_after)

                    wait_hours = (retry_after - now).total_seconds() / 3600
                    logger.warning(f"[{rjcode}] 未在 asmr.one 找到作品，将在 {wait_hours:.1f} 小时后重试 (cron: {cron_expr})")
                    return

                # 检查是否有部分文件下载成功
                if download_result.get('downloaded_files'):
                    task.task_metadata['partial_success'] = True
                    logger.warning(f"[{rjcode}] 部分文件下载成功，但有失败: {len(download_result.get('failed_files', []))} 个文件失败")
                else:
                    task.fail(error_msg)
                    return

            work_title = download_result.get('title', work_title)
            actual_rjcode = download_result.get('actual_rjcode', rjcode)
            task.task_metadata['work_title'] = work_title
            task.task_metadata['actual_rjcode'] = actual_rjcode
            task.rjcode = actual_rjcode  # 更新任务的RJ号为实际下载的版本

            await task.wait_if_paused()
            if task.is_cancelled():
                return

            # 步骤3: 清理LRC广告（如果启用）
            lrc_clean_result = None
            if hasattr(config, 'asmr_sync') and config.asmr_sync.lrc_clean_enabled:
                task.update_progress(70, "清理LRC广告")
                custom_patterns = config.asmr_sync.lrc_clean_patterns if hasattr(config.asmr_sync, 'lrc_clean_patterns') else None
                lrc_clean_result = subtitle_service.clean_lrc_files_in_folder(subtitle_folder, custom_patterns)
                if lrc_clean_result['cleaned_files'] > 0:
                    logger.info(f"[{rjcode}] LRC广告清理完成: 处理 {lrc_clean_result['total_files']} 个文件, "
                               f"清理 {lrc_clean_result['cleaned_files']} 个文件, "
                               f"移除 {lrc_clean_result['total_removed_lines']} 行广告")
                task.task_metadata['lrc_clean_result'] = lrc_clean_result

            # 步骤3.5: 字幕文件繁体转简体（如果启用）
            simplify_result = None
            if hasattr(config, 'asmr_sync') and getattr(config.asmr_sync, 'simplify_chinese_enabled', False):
                task.update_progress(72, "字幕繁体转简体")
                simplify_result = subtitle_service.convert_subtitles_to_simplified_in_folder(subtitle_folder)
                if simplify_result['converted_files'] > 0:
                    logger.info(f"[{rjcode}] 字幕繁简转换完成: 处理 {simplify_result['total_files']} 个文件, "
                               f"转换 {simplify_result['converted_files']} 个文件")
                task.task_metadata['simplify_result'] = simplify_result

            # 步骤4: 同步字幕文件
            task.update_progress(75, "同步字幕文件")
            sync_result = subtitle_service.sync_subtitles_to_download(
                download_dir=download_dir,
                subtitle_folder=subtitle_folder
            )

            # 保存字幕同步结果到任务元数据
            task.task_metadata['sync_result'] = {
                'success': sync_result['success'],
                'renamed_files': sync_result.get('renamed_files', []),
                'copied_subtitles': sync_result.get('copied_subtitles', []),
                'errors': sync_result.get('errors', [])
            }

            if not sync_result['success']:
                logger.warning(f"[{rjcode}] 字幕同步部分失败: {sync_result.get('errors', [])}")
            else:
                logger.info(f"[{rjcode}] 字幕同步成功: 重命名 {len(sync_result.get('renamed_files', []))} 个文件")

            await task.wait_if_paused()
            if task.is_cancelled():
                return

            # 步骤4: 重命名文件夹
            task.update_progress(85, "重命名文件夹")

            # 检测标题是否包含日文字符
            def contains_japanese(text):
                """检测文本是否包含日文字符（平假名、片假名、日文汉字）"""
                for char in text:
                    if '\u3040' <= char <= '\u309F':  # 平假名
                        return True
                    if '\u30A0' <= char <= '\u30FF':  # 片假名
                        return True
                    if '\u4E00' <= char <= '\u9FAF':  # 日文汉字（CJK统一表意文字）
                        # 进一步检查是否是常见日文用字
                        pass
                # 检查是否包含平假名或片假名
                import re
                if re.search(r'[\u3040-\u309F\u30A0-\u30FF]', text):
                    return True
                return False

            # 如果下载的标题包含日文，尝试从字幕文件夹名称获取中文标题
            final_work_title = work_title
            if contains_japanese(work_title):
                # 从字幕文件夹路径提取名称
                subtitle_folder_name = os.path.basename(subtitle_folder)
                logger.info(f"[{rjcode}] 检测到日文标题，尝试从字幕文件夹获取中文名称: {subtitle_folder_name}")

                # 尝试从字幕文件夹名称提取标题（格式通常是: RJxxxxxxxx 标题）
                import re
                match = re.match(r'(RJ\d+)\s*(.+)', subtitle_folder_name, re.IGNORECASE)
                if match:
                    extracted_title = match.group(2).strip()
                    if extracted_title and not contains_japanese(extracted_title):
                        final_work_title = extracted_title
                        logger.info(f"[{rjcode}] 使用字幕文件夹标题: {final_work_title}")
                    else:
                        logger.info(f"[{rjcode}] 字幕文件夹标题也包含日文，保留原标题")

            # 构建元数据用于重命名
            metadata = {
                'rjcode': actual_rjcode,  # 使用实际下载的RJ号
                'work_name': final_work_title,
                'work_title': final_work_title,
            }
            task.task_metadata.update(metadata)

            renamed_path = await rename_service.rename(download_dir, task)
            logger.info(f"[{rjcode}] 重命名后路径: {renamed_path}")

            # 步骤4.5: 扁平化文件夹
            if config.rename.flatten_single_subfolder:
                task.update_progress(87, "扁平化文件夹结构")
                renamed_path = rename_service._flatten_single_subfolder(renamed_path)
                logger.info(f"[{rjcode}] 扁平化后路径: {renamed_path}")

            await task.wait_if_paused()
            if task.is_cancelled():
                return

            # 步骤5: 智能分类
            if task.auto_classify:
                task.update_progress(90, "智能分类")
                final_path = await classifier.classify_and_move(renamed_path, metadata, task)
                task.output_path = final_path
                logger.info(f"[{rjcode}] 分类后路径: {final_path}")
            else:
                # 移动到 library_path
                task.update_progress(90, "移动到媒体库")
                library_path = config.storage.library_path
                final_path = os.path.join(library_path, os.path.basename(renamed_path))

                # 处理重名
                counter = 1
                while os.path.exists(final_path):
                    final_path = os.path.join(library_path, f"{os.path.basename(renamed_path)}_{counter}")
                    counter += 1

                shutil.move(renamed_path, final_path)
                task.output_path = final_path
                logger.info(f"[{rjcode}] 移动到: {final_path}")

            # 步骤6: 移动字幕文件夹到Finished目录
            task.update_progress(95, "整理字幕文件夹")
            try:
                subtitle_parent = os.path.dirname(subtitle_folder)
                finished_dir = os.path.join(subtitle_parent, "Finished")

                # 创建Finished目录
                os.makedirs(finished_dir, exist_ok=True)

                # 移动字幕文件夹
                subtitle_folder_name = os.path.basename(subtitle_folder)
                dest_subtitle_path = os.path.join(finished_dir, subtitle_folder_name)

                # 处理重名
                counter = 1
                while os.path.exists(dest_subtitle_path):
                    dest_subtitle_path = os.path.join(finished_dir, f"{subtitle_folder_name}_{counter}")
                    counter += 1

                shutil.move(subtitle_folder, dest_subtitle_path)
                logger.info(f"[{rjcode}] 字幕文件夹已移动到: {dest_subtitle_path}")
                task.task_metadata['subtitle_moved_to'] = dest_subtitle_path

            except Exception as move_error:
                logger.warning(f"[{rjcode}] 移动字幕文件夹失败: {move_error}")

            task.update_progress(100, "完成")
            task.complete()
            logger.info(f"[{rjcode}] ASMR 同步下载任务完成")

        except Exception as e:
            logger.error(f"[{rjcode}] ASMR 同步下载任务失败: {e}", exc_info=True)
            task.fail(str(e))

            # 清理临时文件
            if 'download_dir' in locals() and os.path.exists(download_dir):
                try:
                    shutil.rmtree(download_dir)
                    logger.info(f"[{rjcode}] 清理临时目录: {download_dir}")
                except Exception as cleanup_error:
                    logger.warning(f"[{rjcode}] 清理临时目录失败: {cleanup_error}")

# 全局任务引擎实例
_task_engine: Optional[TaskEngine] = None

def get_task_engine() -> TaskEngine:
    """获取任务引擎实例"""
    global _task_engine
    if _task_engine is None:
        _task_engine = TaskEngine()
    return _task_engine
