"""文件监视器

监视指定文件夹，检测新文件并触发处理。
使用 FileProcessor 统一处理逻辑。
"""

import os
import asyncio
import re
from pathlib import Path
from typing import Callable, Optional, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent
import logging

from ..config.settings import get_config
from ..core.task_engine import Task, TaskType, get_task_engine
from .file_processor import get_file_processor

logger = logging.getLogger(__name__)


class ArchiveHandler(FileSystemEventHandler):
    """文件系统事件处理器

    检测新创建/修改的文件，识别压缩包并触发处理。
    """

    def __init__(
        self,
        on_archive_detected: Callable[[str], None],
        get_excluded_paths: Callable[[], Set[str]],
        is_paused: Callable[[], bool],
        mark_processed: Callable[[str], None]
    ):
        self.on_archive_detected = on_archive_detected
        self.get_excluded_paths = get_excluded_paths
        self.is_paused = is_paused
        self.mark_processed = mark_processed
        self._file_processor = get_file_processor()

    def on_created(self, event):
        if event.is_directory:
            return
        if self.is_paused():
            return
        file_path = str(event.src_path)
        if file_path in self.get_excluded_paths():
            logger.debug(f"文件在排除列表中，跳过: {file_path}")
            return
        if not os.path.exists(file_path):
            logger.debug(f"文件不存在，跳过: {file_path}")
            return
        result = self._is_archive(file_path)
        if result:
            self.on_archive_detected(file_path)
        elif result is False:
            self._mark_volume_file_processed(file_path)

    def on_modified(self, event):
        if event.is_directory:
            return
        if self.is_paused():
            return
        file_path = str(event.src_path)
        if file_path in self.get_excluded_paths():
            return
        if not os.path.exists(file_path):
            return
        result = self._is_archive(file_path)
        if result:
            self.on_archive_detected(file_path)
        elif result is False:
            self._mark_volume_file_processed(file_path)

    def _mark_volume_file_processed(self, file_path: str):
        """将分卷文件标记为已处理（防止重复检测）"""
        filename = os.path.basename(file_path).lower()

        if re.search(r'\.z\d{2}$', filename):
            logger.debug(f"ZIP 分卷文件标记为已处理: {file_path}")
            self.mark_processed(file_path)
        elif re.search(r'\.7z\.\d{3}$', filename):
            logger.debug(f"7z 分卷文件标记为已处理: {file_path}")
            self.mark_processed(file_path)
        elif re.search(r'\.part\d+\.(rar|zip|7z|exe)$', filename, re.IGNORECASE):
            part_match = re.search(r'\.part(\d+)\.', filename, re.IGNORECASE)
            if part_match and int(part_match.group(1)) > 1:
                logger.debug(f"分卷文件标记为已处理: {file_path}")
                self.mark_processed(file_path)

    def _is_archive(self, path: str) -> bool:
        """检查是否是压缩包文件（委托给 FileProcessor）"""
        return self._file_processor.is_archive(path)


class FolderWatcher:
    """文件夹监视器

    监视指定文件夹，检测新文件并使用 FileProcessor 处理。
    """

    def __init__(self):
        self.config = get_config()
        self.observer = None
        self.handler = None
        self.is_running = False
        self.pending_files = set()
        self._processed_files = set()
        self._scan_task = None
        self._loop = None
        self._paused = False  # 暂停监听标志
        self._file_processor = get_file_processor()

    def _get_excluded_paths(self):
        """获取所有应该排除的路径（pending + processed）"""
        return self.pending_files | self._processed_files

    def _mark_file_processed(self, file_path: str):
        """将文件标记为已处理"""
        self._processed_files.add(file_path)

    def _is_file_processed(self, file_path: str) -> bool:
        """检查文件是否已处理"""
        return file_path in self._processed_files or file_path in self.pending_files

    def pause_watching(self):
        """暂停文件监听（在重命名等操作前调用）"""
        self._paused = True
        if self.observer:
            try:
                self.observer.unschedule_all()
                logger.debug("已暂停文件监听")
            except Exception as e:
                logger.warning(f"暂停监听失败: {e}")

    def resume_watching(self):
        """恢复文件监听"""
        if not self._paused:
            return
        self._paused = False
        if self.observer and self.handler:
            try:
                watch_path = self.config.storage.input_path
                self.observer.schedule(self.handler, watch_path, recursive=True)
                logger.debug("已恢复文件监听")
            except Exception as e:
                logger.warning(f"恢复监听失败: {e}")

    def start(self):
        """启动监视器"""
        if self.is_running:
            return

        self._loop = asyncio.get_event_loop()

        watch_path = self.config.storage.input_path
        if not os.path.exists(watch_path):
            os.makedirs(watch_path, exist_ok=True)

        self.handler = ArchiveHandler(
            self._on_archive_detected,
            self._get_excluded_paths,
            lambda: self._paused,
            self._mark_file_processed
        )
        observer = Observer()
        observer.schedule(self.handler, watch_path, recursive=True)
        observer.start()
        self.observer = observer

        self._scan_task = asyncio.create_task(self._periodic_scan())

        self.is_running = True
        logger.info(f"文件夹监视器已启动: {watch_path}")

    def stop(self):
        """停止监视器"""
        if not self.is_running:
            return

        if self.observer:
            self.observer.stop()
            self.observer.join()

        if self._scan_task:
            self._scan_task.cancel()

        self.is_running = False
        logger.info("文件夹监视器已停止")

    def _on_archive_detected(self, file_path: str):
        """检测到压缩包"""
        # 检查是否已经在处理中或已处理过
        if file_path in self.pending_files:
            logger.debug(f"文件已在处理中，跳过: {file_path}")
            return

        if file_path in self._processed_files:
            logger.debug(f"文件已处理过，跳过: {file_path}")
            return

        self.pending_files.add(file_path)
        logger.info(f"检测到新文件: {file_path}")
        logger.info(f"auto_start配置: {self.config.watcher.auto_start}")

        # 创建自动处理任务
        if self.config.watcher.auto_start:
            logger.info(f"准备创建处理任务: {file_path}")
            # 使用保存的事件循环来调度任务
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(self._process_file(file_path), self._loop)
                logger.info(f"任务已调度: {file_path}")
            else:
                logger.error(f"事件循环未就绪，无法调度任务: {file_path}")
        else:
            logger.info(f"auto_start为false，跳过自动处理: {file_path}")

    async def _process_file(self, file_path: str):
        """处理文件（使用 FileProcessor 统一流程）"""
        logger.info(f"[Watcher] 开始处理文件: {file_path}")
        original_path = file_path

        try:
            # 使用 FileProcessor 处理文件
            # 传入暂停/恢复监听回调，用于文件名规范化时避免重复事件
            task = await self._file_processor.process_file(
                file_path,
                auto_classify=self.config.watcher.auto_classify,
                wait_stable=True,
                max_wait=300,
                is_processed=self._is_file_processed,
                mark_processed=self._mark_file_processed,
                pause_fn=self.pause_watching,
                resume_fn=self.resume_watching
            )

            if task:
                # 等待任务完成
                while task.status.value in ["pending", "processing"]:
                    await asyncio.sleep(1)

                # 任务完成后添加到已处理列表
                self._processed_files.add(task.source_path)
                logger.info(f"文件处理完成: {task.source_path}, 状态: {task.status.value}")

                # 处理后删除原文件（如果配置允许且处理成功，且不是重新解压）
                if self.config.watcher.delete_after_process and not task.skip_archive:
                    if task.status.value == "completed":
                        try:
                            # 检查文件是否还存在（可能已被归档移动）
                            if os.path.exists(task.source_path):
                                os.remove(task.source_path)
                                logger.info(f"已删除原文件: {task.source_path}")
                        except Exception as e:
                            logger.warning(f"删除原文件失败: {task.source_path}, {e}")
                elif task.skip_archive:
                    logger.info(f"跳过删除原文件（重新解压）: {task.source_path}")
            else:
                logger.info(f"[Watcher] 未创建任务: {file_path}")

        except Exception as e:
            logger.error(f"处理文件失败: {file_path}, {e}", exc_info=True)
            self._processed_files.add(file_path)
        finally:
            self.pending_files.discard(original_path)

    async def _periodic_scan(self):
        """定期扫描文件夹"""
        while True:
            try:
                await asyncio.sleep(self.config.watcher.scan_interval)
                await self._scan_folder()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"定期扫描失败: {e}")

    async def _scan_folder(self):
        """扫描文件夹中的现有文件"""
        watch_path = self.config.storage.input_path

        if not self.handler:
            return

        for root, dirs, files in os.walk(watch_path):
            for file in files:
                file_path = os.path.join(root, file)

                if file_path in self._get_excluded_paths():
                    continue

                if self.handler._is_archive(file_path):
                    engine = get_task_engine()
                    existing = any(
                        t.source_path == file_path and t.status.value in ["pending", "processing"]
                        for t in engine.get_all_tasks()
                    )

                    if not existing and file_path not in self.pending_files and file_path not in self._processed_files:
                        self._on_archive_detected(file_path)


# 全局监视器实例
_watcher: Optional[FolderWatcher] = None


def get_watcher() -> FolderWatcher:
    """获取监视器实例"""
    global _watcher
    if _watcher is None:
        _watcher = FolderWatcher()
    return _watcher