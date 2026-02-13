import os
import asyncio
from pathlib import Path
from typing import Callable, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent
import logging

from ..config.settings import get_config
from ..core.task_engine import Task, TaskType, get_task_engine

logger = logging.getLogger(__name__)

class ArchiveHandler(FileSystemEventHandler):
    """文件系统事件处理器"""
    
    def __init__(self, on_archive_detected: Callable):
        self.on_archive_detected = on_archive_detected
    
    def on_created(self, event):
        if event.is_directory:
            return
        if self._is_archive(event.src_path):
            self.on_archive_detected(event.src_path)
    
    def on_modified(self, event):
        if event.is_directory:
            return
        if self._is_archive(event.src_path):
            self.on_archive_detected(event.src_path)
    
    def _is_archive(self, path: str) -> bool:
        """检查是否是压缩包文件"""
        filename = Path(path).name.lower()
        ext = Path(path).suffix.lower()
        
        # 常见压缩格式
        archive_extensions = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.exe'}
        
        # 检查后缀（有正确后缀的优先按后缀处理）
        if ext in archive_extensions:
            # 检查是否是分卷压缩的非首卷文件（如 .part2.rar, .part3.rar）
            # 只处理第一个分卷（.part1.xxx 或 .part01.xxx）
            import re
            part_match = re.search(r'\.part(\d+)\.', filename)
            if part_match:
                part_num = int(part_match.group(1))
                if part_num > 1:
                    logger.debug(f"跳过分卷压缩的非首卷文件: {filename}")
                    return False
                # part1 或 part01 返回 True，继续检查
                return True
            
            # 检查其他分卷模式（如 .z01, .z02 等）
            z_match = re.search(r'\.(z|z\d+)$', filename)
            if z_match:
                # 如果匹配到 z01-z99，跳过；如果是 z 或 zip，则处理
                if re.search(r'\.z\d{2}$', filename):
                    logger.debug(f"跳过 zip 分卷文件: {filename}")
                    return False
            
            # 检查是否是自解压文件（通常包含 setup, install 等关键字，且是 .exe）
            if ext == '.exe':
                # 检查文件名是否包含压缩相关关键字
                archive_keywords = ['rar', 'zip', '7z', 'archive', 'setup', 'install', 'self-extract']
                if any(keyword in filename for keyword in archive_keywords):
                    return True
            
            return True
        
        # 对于没有后缀名或后缀名不在列表中的文件，尝试通过魔数检测
        if not ext or ext not in archive_extensions:
            return self._detect_archive_by_magic(path)
        
        return False
    
    def _detect_archive_by_magic(self, path: str) -> bool:
        """通过文件魔数检测是否为压缩文件"""
        # 定义压缩文件的魔数
        magic_bytes = {
            b'PK\x03\x04': 'zip',  # ZIP
            b'PK\x05\x06': 'zip',  # 空 ZIP
            b'PK\x07\x08': 'zip',  # ZIP64
            b'Rar!': 'rar',        # RAR
            b'7z\xBC\xAF\x27\x1C': '7z',  # 7Z
            b'\x1f\x8b': 'gz',      # GZIP
            b'BZh': 'bz2',         # BZIP2
            b'\xFD7zXZ': 'xz',     # XZ
        }
        
        try:
            # 检查文件是否存在且可读
            if not os.path.exists(path) or not os.path.isfile(path):
                return False
            
            # 检查文件大小（至少要有魔数的大小）
            file_size = os.path.getsize(path)
            if file_size < 4:
                return False
            
            # 读取文件头（最多8字节）
            with open(path, 'rb') as f:
                header = f.read(8)
            
            # 检查魔数
            for magic, file_type in magic_bytes.items():
                if header.startswith(magic):
                    logger.info(f"通过魔数检测到压缩文件: {path} (类型: {file_type})")
                    return True
            
            return False
        except (PermissionError, IOError) as e:
            logger.debug(f"无法读取文件进行魔数检测: {path}, 错误: {e}")
            return False
        except Exception as e:
            logger.warning(f"魔数检测失败: {path}, 错误: {e}")
            return False

class FolderWatcher:
    """文件夹监视器"""
    
    def __init__(self):
        self.config = get_config()
        self.observer: Optional[Observer] = None
        self.handler: Optional[ArchiveHandler] = None
        self.is_running = False
        self.pending_files: set = set()
        self._processed_files: set = set()  # 已处理的文件（避免重复）
        self._scan_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None  # 保存事件循环引用
    
    def start(self):
        """启动监视器"""
        if self.is_running:
            return
        
        # 保存当前事件循环引用
        self._loop = asyncio.get_event_loop()
        
        watch_path = self.config.storage.input_path
        if not os.path.exists(watch_path):
            os.makedirs(watch_path, exist_ok=True)
        
        self.handler = ArchiveHandler(self._on_archive_detected)
        self.observer = Observer()
        self.observer.schedule(self.handler, watch_path, recursive=True)
        self.observer.start()
        
        # 启动定期扫描任务
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
        """处理文件"""
        logger.info(f"开始处理文件: {file_path}")
        try:
            # 1. 首先等待文件复制完成（文件大小稳定）
            logger.info(f"等待文件复制完成: {file_path}")
            try:
                await self._wait_file_stable_simple(file_path, max_wait=300)  # 最多等待5分钟
                logger.info(f"文件已稳定，开始创建任务: {file_path}")
            except TimeoutError:
                logger.error(f"等待文件稳定超时: {file_path}")
                self.pending_files.discard(file_path)
                return
            
            task = Task(
                task_type=TaskType.AUTO_PROCESS,
                source_path=file_path,
                auto_classify=self.config.watcher.auto_classify
            )
            logger.info(f"任务创建成功: {task.id}, 状态: {task.status.value}")
            
            engine = get_task_engine()
            logger.info(f"任务引擎状态: 运行中={engine._worker_task is not None}, 队列大小={engine.queue.qsize()}, 处理中={len(engine.processing)}")
            
            await engine.submit(task)
            logger.info(f"任务已提交到引擎: {task.id}, 队列大小={engine.queue.qsize()}")
            
            # 等待任务完成
            while task.status.value in ["pending", "processing"]:
                await asyncio.sleep(1)
            
            # 任务完成后添加到已处理列表
            self._processed_files.add(file_path)
            logger.info(f"文件处理完成: {file_path}, 状态: {task.status.value}")
            
            # 处理后删除原文件（如果配置允许且处理成功，且不是重新解压）
            if self.config.watcher.delete_after_process and not task.skip_archive:
                if task.status.value == "completed":
                    try:
                        os.remove(file_path)
                        logger.info(f"已删除原文件: {file_path}")
                    except Exception as e:
                        logger.warning(f"删除原文件失败: {file_path}, {e}")
            elif task.skip_archive:
                logger.info(f"跳过删除原文件（重新解压）: {file_path}")
        
        except Exception as e:
            logger.error(f"处理文件失败: {file_path}, {e}")
            # 即使失败也添加到已处理列表，避免无限重试
            self._processed_files.add(file_path)
        finally:
            self.pending_files.discard(file_path)
    
    async def _wait_file_stable_simple(self, file_path: str, max_wait: int = 300):
        """简化的文件稳定性检测（用于watcher）"""
        previous_size = -1
        stable_count = 0
        required_stable = 3  # 需要连续3次稳定
        check_interval = 2  # 每2秒检查一次
        start_time = asyncio.get_event_loop().time()
        
        while stable_count < required_stable:
            current_time = asyncio.get_event_loop().time()
            
            # 检查超时
            if current_time - start_time > max_wait:
                raise TimeoutError(f"等待文件稳定超时: {file_path}")
            
            try:
                if not os.path.exists(file_path):
                    await asyncio.sleep(check_interval)
                    continue
                
                current_size = os.path.getsize(file_path)
                
                # 检查文件是否为空
                if current_size < 1024:  # 小于1KB
                    logger.debug(f"文件太小，继续等待: {file_path} ({current_size} bytes)")
                    stable_count = 0
                elif current_size == previous_size:
                    # 文件大小稳定，增加计数
                    stable_count += 1
                    logger.debug(f"文件大小稳定 ({stable_count}/{required_stable}): {file_path}")
                else:
                    # 文件大小在变化
                    if previous_size != -1:
                        logger.info(f"文件仍在复制中: {file_path} ({previous_size} -> {current_size} bytes)")
                    stable_count = 0
                    
                previous_size = current_size
                
            except Exception as e:
                logger.debug(f"等待文件稳定时出错: {e}")
                stable_count = 0
            
            await asyncio.sleep(check_interval)
    
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
        
        for root, dirs, files in os.walk(watch_path):
            for file in files:
                file_path = os.path.join(root, file)
                
                # 检查是否是压缩包
                if self.handler._is_archive(file_path):
                    # 检查是否已在处理队列中
                    engine = get_task_engine()
                    existing = any(
                        t.source_path == file_path and t.status.value in ["pending", "processing"]
                        for t in engine.get_all_tasks()
                    )
                    
                    # 检查是否已在处理队列中、已处理过或正在处理
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
