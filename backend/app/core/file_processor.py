"""统一的文件处理服务

整合 Watcher、Upload API、Scan API 三种入口的文件处理逻辑：
1. 等待文件稳定
2. 检测分卷组
3. 处理分卷组（标记所有分卷为已处理）
4. 文件名规范化
5. 创建任务
"""

import os
import re
import asyncio
from pathlib import Path
from typing import Optional, Set, List, Callable
import logging

from ..config.settings import get_config
from ..core.task_engine import Task, TaskType, get_task_engine

logger = logging.getLogger(__name__)


class VolumeSet:
    """分卷组信息"""
    def __init__(self, base_name: str, volumes: List[str], volume_type: str):
        self.base_name = base_name
        self.volumes = volumes  # 排序后的分卷路径列表
        self.type = volume_type
        self.is_complete = False


class FileProcessor:
    """统一的文件处理服务

    提供统一的文件入库处理流程，确保：
    - Watcher 监听
    - Upload API 上传
    - Scan API 扫描
    三种入口使用相同的处理逻辑
    """

    def __init__(self):
        self._processed_files: Set[str] = set()  # 已处理文件集合

    @property
    def config(self):
        """动态获取最新配置"""
        return get_config()

    # ========== 公共接口 ==========

    async def process_file(
        self,
        file_path: str,
        auto_classify: bool = True,
        wait_stable: bool = True,
        max_wait: int = 300,
        is_processed: Optional[Callable[[str], bool]] = None,
        mark_processed: Optional[Callable[[str], None]] = None,
        pause_fn: Optional[Callable[[], None]] = None,
        resume_fn: Optional[Callable[[], None]] = None
    ) -> Optional[Task]:
        """统一的文件处理流程

        Args:
            file_path: 文件路径
            auto_classify: 是否自动分类
            wait_stable: 是否等待文件稳定
            max_wait: 最大等待时间（秒）
            is_processed: 检查文件是否已处理的回调
            mark_processed: 标记文件为已处理的回调
            pause_fn: 暂停文件监听的回调（用于重命名操作）
            resume_fn: 恢复文件监听的回调

        Returns:
            创建的任务对象，如果未创建任务则返回 None
        """
        logger.info(f"[FileProcessor] 开始处理文件: {file_path}")
        original_path = file_path

        try:
            # 1. 检查文件是否已处理
            if is_processed and is_processed(file_path):
                logger.debug(f"[FileProcessor] 文件已处理，跳过: {file_path}")
                return None

            # 2. 等待文件稳定
            if wait_stable:
                logger.info(f"[FileProcessor] 等待文件稳定: {file_path}")
                try:
                    await self.wait_file_stable(file_path, max_wait=max_wait)
                    logger.info(f"[FileProcessor] 文件已稳定: {file_path}")
                except TimeoutError:
                    logger.error(f"[FileProcessor] 等待文件稳定超时: {file_path}")
                    if mark_processed:
                        mark_processed(file_path)
                    return None

            # 3. 检测分卷组
            volume_set = self.detect_volume_set(file_path)
            if volume_set:
                logger.info(f"[FileProcessor] 检测到分卷组: {volume_set.base_name}, 共 {len(volume_set.volumes)} 个分卷")
                file_path = await self._process_volume_set(
                    file_path, volume_set,
                    is_processed=is_processed,
                    mark_processed=mark_processed
                )
                if not file_path:
                    return None
            else:
                # 检查是否可能是分卷文件但未检测到完整组
                file_path = await self._handle_potential_volume(
                    file_path,
                    is_processed=is_processed,
                    mark_processed=mark_processed
                )
                if not file_path:
                    return None

            # 4. 文件名规范化（需要暂停监听以避免重复事件）
            file_path = await self._normalize_file(
                file_path,
                pause_fn=pause_fn,
                resume_fn=resume_fn,
                mark_processed=mark_processed
            )
            logger.info(f"[FileProcessor] 规范化后路径: {file_path}")

            # 5. 检查是否已在任务队列中
            engine = get_task_engine()
            existing = any(
                t.source_path == file_path and t.status.value in ["pending", "processing"]
                for t in engine.get_all_tasks()
            )
            if existing:
                logger.info(f"[FileProcessor] 文件已在任务队列中: {file_path}")
                if mark_processed:
                    mark_processed(file_path)
                return None

            # 6. 创建任务
            logger.info(f"[FileProcessor] 创建任务: {file_path}")
            task = Task(
                task_type=TaskType.AUTO_PROCESS,
                source_path=file_path,
                auto_classify=auto_classify
            )

            await engine.submit(task)
            logger.info(f"[FileProcessor] 任务已提交: {task.id}")

            # 标记文件为已处理
            if mark_processed:
                mark_processed(file_path)

            return task

        except Exception as e:
            logger.error(f"[FileProcessor] 处理文件失败: {file_path}, {e}", exc_info=True)
            if mark_processed:
                mark_processed(original_path)
            return None

    async def process_directory(
        self,
        directory: str,
        auto_classify: bool = True,
        is_processed: Optional[Callable[[str], bool]] = None,
        mark_processed: Optional[Callable[[str], None]] = None,
        pause_fn: Optional[Callable[[], None]] = None,
        resume_fn: Optional[Callable[[], None]] = None
    ) -> List[Task]:
        """扫描目录并处理所有文件

        Args:
            directory: 目录路径
            auto_classify: 是否自动分类
            is_processed: 检查文件是否已处理的回调
            mark_processed: 标记文件为已处理的回调
            pause_fn: 暂停文件监听的回调（用于重命名操作）
            resume_fn: 恢复文件监听的回调

        Returns:
            创建的任务列表
        """
        logger.info(f"[FileProcessor] 开始扫描目录: {directory}")
        tasks = []

        if not os.path.exists(directory):
            logger.warning(f"[FileProcessor] 目录不存在: {directory}")
            return tasks

        # 收集所有待处理的压缩包
        archive_files = []
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)

                # 检查是否已处理
                if is_processed and is_processed(file_path):
                    continue

                # 检查是否是压缩包
                if self.is_archive(file_path):
                    # 检查文件大小
                    try:
                        file_size = os.path.getsize(file_path)
                        if file_size < 1024:  # 小于1KB，可能正在复制中
                            logger.warning(f"[FileProcessor] 文件太小，跳过: {file_path} ({file_size} bytes)")
                            continue
                    except OSError:
                        continue

                    archive_files.append(file_path)

        logger.info(f"[FileProcessor] 找到 {len(archive_files)} 个待处理文件")

        # 记录已处理的分卷文件，避免重复创建任务
        processed_volumes: Set[str] = set()

        for file_path in archive_files:
            # 检查是否是已处理的分卷
            if file_path in processed_volumes:
                continue

            # 检测分卷组
            volume_set = self.detect_volume_set(file_path)
            if volume_set:
                # 标记所有分卷为已处理（仅用于本次扫描的内存记录，不调用 mark_processed）
                # mark_processed 会在 process_file 成功创建任务后调用
                for vol in volume_set.volumes:
                    processed_volumes.add(vol)

            # 处理文件（不等待稳定，因为扫描时文件应该已经稳定）
            task = await self.process_file(
                file_path,
                auto_classify=auto_classify,
                wait_stable=False,
                is_processed=is_processed,
                mark_processed=mark_processed
            )
            if task:
                tasks.append(task)

        logger.info(f"[FileProcessor] 创建了 {len(tasks)} 个任务")
        return tasks

    def is_archive(self, file_path: str) -> bool:
        """检测是否是压缩包文件

        复用 ArchiveHandler._is_archive 逻辑，但作为独立方法提供

        Args:
            file_path: 文件路径

        Returns:
            是否是压缩包（True/False），如果是非首卷分卷文件返回 False
        """
        filename = Path(file_path).name.lower()
        ext = Path(file_path).suffix.lower()

        # 先检查是否是分卷文件后缀，如果是非首卷则跳过
        # ZIP 分卷: .z01, .z02, ... .z99 (z01是首卷)
        z_match = re.search(r'\.z(\d{2})$', filename)
        if z_match:
            vol_num = int(z_match.group(1))
            if vol_num > 1:  # z02, z03... 是非首卷
                logger.debug(f"[FileProcessor] 跳过 ZIP 分卷非首卷文件: {filename}")
                return False
            # z01 是首卷，通过魔数检测
            return self._detect_archive_by_magic(file_path)

        # 7z 分卷: .7z.001, .7z.002, ... (.7z.001 是首卷)
        sevenzip_match = re.search(r'\.7z\.(\d{3})$', filename)
        if sevenzip_match:
            vol_num = int(sevenzip_match.group(1))
            if vol_num > 1:  # .7z.002, .7z.003... 是非首卷
                logger.debug(f"[FileProcessor] 跳过 7z 分卷非首卷文件: {filename}")
                return False
            # .7z.001 是首卷，通过魔数检测
            return self._detect_archive_by_magic(file_path)

        # RAR/ZIP 分卷: .part2.rar, .part3.rar, ... (非首卷)
        part_match = re.search(r'\.part(\d+)\.(rar|zip|7z|exe)$', filename, re.IGNORECASE)
        if part_match and int(part_match.group(1)) > 1:
            logger.debug(f"[FileProcessor] 跳过分卷压缩的非首卷文件: {filename}")
            return False
        # RAR 分卷: .part2, .part3, ... (无扩展名格式，非首卷)
        # 注意: .part1 是首卷，需要通过魔数检测来识别
        part_match_no_ext = re.search(r'\.part(\d+)$', filename, re.IGNORECASE)
        if part_match_no_ext:
            part_num = int(part_match_no_ext.group(1))
            if part_num > 1:
                logger.debug(f"[FileProcessor] 跳过无扩展名的分卷压缩非首卷文件: {filename}")
                return False
            else:
                # .part1 首卷，通过魔数检测确定是否是压缩包
                return self._detect_archive_by_magic(file_path)

        # 常见压缩格式
        archive_extensions = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.exe'}

        # 检查后缀
        if ext in archive_extensions:
            # 检查是否是自解压文件
            if ext == '.exe':
                archive_keywords = ['rar', 'zip', '7z', 'archive', 'setup', 'install', 'self-extract']
                if any(keyword in filename for keyword in archive_keywords):
                    return True
            return True

        # 对于没有后缀名或后缀名不在列表中的文件，尝试通过魔数检测
        if not ext or ext not in archive_extensions:
            return self._detect_archive_by_magic(file_path)

    def detect_volume_set(self, file_path: str) -> Optional[VolumeSet]:
        """检测分卷组

        复用 ExtractService._detect_volume_set 逻辑

        Args:
            file_path: 文件路径（通常是首卷或潜在的分卷文件）

        Returns:
            VolumeSet 对象，如果不是分卷文件则返回 None
        """
        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)

        # 分卷模式识别（按优先级排序，更具体的模式在前）
        patterns = [
            (r'\.7z\.(\d{3})$', '7z_volume_with_ext'),  # .7z.001, .7z.002 (7z分卷，带.7z扩展名)
            (r'\.part(\d+)\.(rar|zip|7z)$', 'part'),
            (r'\.part(\d+)$', 'part_no_ext'),  # 无扩展名的RAR分卷格式
            (r'\.z(\d{2})$', 'zip_volume'),
            (r'\.(\d{3})$', '7z_volume'),  # 纯数字分卷（如 .001, .002）
            (r'\.(\d{2})$', 'generic'),
        ]

        for pattern, vtype in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                # 提取 base_name，只移除分卷后缀
                base_name = re.sub(pattern, '', filename)
                logger.info(f"[FileProcessor] 检测到分卷模式: {filename}, base_name={base_name}")

                # 查找所有分卷
                volumes = self._find_all_volumes(directory, base_name, pattern)
                logger.info(f"[FileProcessor] 找到 {len(volumes)} 个分卷: {[os.path.basename(v) for v in volumes]}")

                # 分卷组需要至少2个文件
                if len(volumes) > 1:
                    return VolumeSet(base_name, volumes, vtype)

        return None

    async def wait_file_stable(self, file_path: str, max_wait: int = 300):
        """等待文件稳定（大小不再变化）

        Args:
            file_path: 文件路径
            max_wait: 最大等待时间（秒）

        Raises:
            TimeoutError: 等待超时
        """
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
                    logger.debug(f"[FileProcessor] 文件太小，继续等待: {file_path} ({current_size} bytes)")
                    stable_count = 0
                elif current_size == previous_size:
                    stable_count += 1
                    logger.debug(f"[FileProcessor] 文件大小稳定 ({stable_count}/{required_stable}): {file_path}")
                else:
                    if previous_size != -1:
                        logger.info(f"[FileProcessor] 文件仍在复制中: {file_path} ({previous_size} -> {current_size} bytes)")
                    stable_count = 0

                previous_size = current_size

            except Exception as e:
                logger.debug(f"[FileProcessor] 等待文件稳定时出错: {e}")
                stable_count = 0

            await asyncio.sleep(check_interval)

    # ========== 私有方法 ==========

    async def _process_volume_set(
        self,
        file_path: str,
        volume_set: VolumeSet,
        is_processed: Optional[Callable[[str], bool]] = None,
        mark_processed: Optional[Callable[[str], None]] = None
    ) -> Optional[str]:
        """处理分卷压缩组

        1. 等待所有分卷稳定
        2. 标记所有分卷为已处理
        3. 返回首卷路径

        Args:
            file_path: 当前文件路径
            volume_set: 分卷组信息
            is_processed: 检查文件是否已处理的回调
            mark_processed: 标记文件为已处理的回调

        Returns:
            首卷路径，如果处理失败返回 None
        """
        logger.info(f"[FileProcessor] 处理分卷组: {volume_set.base_name}")

        # 标记所有分卷为已处理
        for volume in volume_set.volumes:
            if mark_processed and not (is_processed and is_processed(volume)):
                mark_processed(volume)

        # 等待所有分卷稳定
        for volume in volume_set.volumes:
            if volume != file_path:
                try:
                    await self.wait_file_stable(volume, max_wait=300)
                    logger.debug(f"[FileProcessor] 分卷已稳定: {volume}")
                except TimeoutError:
                    logger.error(f"[FileProcessor] 等待分卷稳定超时: {volume}")
                    return None

        return file_path

    async def _handle_potential_volume(
        self,
        file_path: str,
        is_processed: Optional[Callable[[str], bool]] = None,
        mark_processed: Optional[Callable[[str], None]] = None
    ) -> Optional[str]:
        """处理潜在的分卷文件

        检查文件名是否匹配分卷模式，如果是则等待其他分卷出现

        Args:
            file_path: 文件路径
            is_processed: 检查文件是否已处理的回调
            mark_processed: 标记文件为已处理的回调

        Returns:
            文件路径，如果不是分卷文件或已处理返回 None
        """
        part_patterns = [
            r'\.part(\d+)\.(rar|zip|7z)$',  # 带扩展名的分卷
            r'\.part(\d+)$',                  # 无扩展名的分卷
            r'\.z\d{2}$',                     # ZIP分卷
            r'\.\d{3}$',                      # 7z分卷
        ]

        is_potential_volume = any(
            re.search(p, os.path.basename(file_path), re.IGNORECASE)
            for p in part_patterns
        )

        if is_potential_volume:
            logger.info(f"[FileProcessor] 检测到可能是分卷文件，等待其他分卷: {os.path.basename(file_path)}")
            # 等待一段时间让其他分卷文件出现
            await asyncio.sleep(10)

            # 重新检测分卷组
            volume_set = self.detect_volume_set(file_path)
            if volume_set:
                logger.info(f"[FileProcessor] 等待后检测到分卷组: {volume_set.base_name}")
                return await self._process_volume_set(
                    file_path, volume_set,
                    is_processed=is_processed,
                    mark_processed=mark_processed
                )
            else:
                logger.info(f"[FileProcessor] 等待后仍未检测到分卷组，作为普通文件处理: {os.path.basename(file_path)}")
                return file_path

        return file_path

    async def _normalize_file(
        self,
        file_path: str,
        pause_fn: Optional[Callable[[], None]] = None,
        resume_fn: Optional[Callable[[], None]] = None,
        mark_processed: Optional[Callable[[str], None]] = None
    ) -> str:
        """规范化文件名

        调用 ExtractService 进行文件名规范化

        Args:
            file_path: 文件路径
            pause_fn: 暂停文件监听的回调（用于重命名操作）
            resume_fn: 恢复文件监听的回调
            mark_processed: 标记文件为已处理的回调

        Returns:
            规范化后的文件路径
        """
        from .extract_service import ExtractService

        extract_service = ExtractService()

        # 直接调用 normalize_archive_filename，它会处理所有情况
        # 包括：文件名规范化、添加缺失的后缀、分卷文件处理等

        # 暂停监听（避免重命名触发重复事件）
        if pause_fn:
            pause_fn()

        try:
            normalized_path = await extract_service.normalize_archive_filename(file_path)

            if normalized_path != file_path:
                logger.info(f"[FileProcessor] 文件已规范化: {file_path} -> {normalized_path}")
                # 标记新路径为已处理
                if mark_processed:
                    mark_processed(normalized_path)

            return normalized_path
        finally:
            # 恢复监听
            if resume_fn:
                resume_fn()

    def _find_all_volumes(self, directory: str, base_name: str, pattern: str) -> List[str]:
        """查找所有分卷文件

        Args:
            directory: 目录路径
            base_name: 基础文件名
            pattern: 分卷模式正则

        Returns:
            排序后的分卷文件路径列表
        """
        volumes = []
        try:
            files = os.listdir(directory)
            logger.info(f"[FileProcessor] _find_all_volumes: directory={directory}, base_name={base_name}, pattern={pattern}")
            logger.info(f"[FileProcessor] 目录中的文件: {files}")
            for file in files:
                if file.startswith(base_name) and re.search(pattern, file, re.IGNORECASE):
                    volumes.append(os.path.join(directory, file))
                    logger.info(f"[FileProcessor] 匹配到分卷: {file}")
        except Exception as e:
            logger.error(f"[FileProcessor] 列出目录失败: {e}")

        result = sorted(volumes)
        logger.info(f"[FileProcessor] 最终分卷列表: {[os.path.basename(v) for v in result]}")
        return result

    def _detect_archive_by_magic(self, path: str) -> bool:
        """通过文件魔数检测是否为压缩文件

        Args:
            path: 文件路径

        Returns:
            是否是压缩文件
        """
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
            if not os.path.exists(path) or not os.path.isfile(path):
                return False

            file_size = os.path.getsize(path)
            if file_size < 4:
                return False

            with open(path, 'rb') as f:
                header = f.read(8)

            for magic, file_type in magic_bytes.items():
                if header.startswith(magic):
                    logger.info(f"[FileProcessor] 通过魔数检测到压缩文件: {path} (类型: {file_type})")
                    return True

            return False
        except (PermissionError, IOError) as e:
            logger.debug(f"[FileProcessor] 无法读取文件进行魔数检测: {path}, 错误: {e}")
            return False
        except Exception as e:
            logger.warning(f"[FileProcessor] 魔数检测失败: {path}, 错误: {e}")
            return False


# 全局 FileProcessor 实例
_file_processor: Optional[FileProcessor] = None


def get_file_processor() -> FileProcessor:
    """获取 FileProcessor 实例"""
    global _file_processor
    if _file_processor is None:
        _file_processor = FileProcessor()
    return _file_processor