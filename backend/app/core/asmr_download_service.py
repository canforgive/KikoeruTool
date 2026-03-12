"""
ASMR.one 下载服务
从 asmr.one API 获取作品信息并下载文件
支持按语言优先级搜索关联版本（简中 > 繁中 > 日文）
"""
import os
import re
import aiohttp
import asyncio
import logging
from typing import Optional, List, Dict, Callable, Tuple
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# 语言优先级定义（数字越小优先级越高）
LANGUAGE_PRIORITY = {
    'CHI_HANS': 1,  # 简体中文
    'CHI_SIMP': 1,  # 简体中文（别名）
    'CHI_HANT': 2,  # 繁体中文
    'CHI_TRAD': 2,  # 繁体中文（别名）
    'JPN': 3,       # 日文（原版）
    'JAP': 3,       # 日文（别名）
    'ENG': 4,       # 英文
    'KOR': 5,       # 韩文
}


class LinkedWorkInfo:
    """关联作品信息"""
    def __init__(self, workno: str, lang: str = 'JPN', work_type: str = 'original'):
        self.workno = workno
        self.lang = lang
        self.work_type = work_type  # original, parent, child

    @property
    def priority(self) -> int:
        """获取语言优先级"""
        return LANGUAGE_PRIORITY.get(self.lang, 99)


class ASMRDownloadService:
    """ASMR.one 下载服务"""

    # API 基础 URL 列表（用于故障转移）
    API_BASE_URLS = [
        "https://api.asmr-200.com/api",
        "https://api.asmr-100.com/api",
    ]

    # DLsite API
    DLSITE_API = "https://www.dlsite.com/maniax/api/=/product.json"

    def __init__(self, config=None):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._current_api_index = 0
        self._cache: Dict = {}
        self._cache_ttl = 300  # 5分钟缓存

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP 会话"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        """关闭 HTTP 会话"""
        if self._session and not self._session.closed:
            await self._session.close()

    def _get_api_base(self) -> str:
        """获取当前 API 基础 URL"""
        return self.API_BASE_URLS[self._current_api_index]

    async def _switch_api(self):
        """切换到下一个 API 服务器"""
        self._current_api_index = (self._current_api_index + 1) % len(self.API_BASE_URLS)
        logger.info(f"切换 API 服务器到: {self._get_api_base()}")

    async def get_linked_works_from_dlsite(self, rjcode: str) -> List[LinkedWorkInfo]:
        """
        从 DLsite API 获取作品的所有关联版本

        Args:
            rjcode: RJ号

        Returns:
            关联作品列表（已按语言优先级排序）
        """
        # 标准化 RJ 号
        if rjcode.upper().startswith('RJ'):
            rjcode_num = rjcode[2:]
        else:
            rjcode_num = rjcode

        # 检查缓存
        cache_key = f"linked_{rjcode_num}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if (datetime.now() - cached['timestamp']).total_seconds() < self._cache_ttl:
                return cached['data']

        session = await self._get_session()
        works = []

        try:
            # 获取作品信息
            url = f"{self.DLSITE_API}?workno=RJ{rjcode_num}"
            logger.info(f"[DLsite] 获取关联作品: {url}")

            async with session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"[DLsite] 获取作品信息失败: HTTP {response.status}")
                    works.append(LinkedWorkInfo(f"RJ{rjcode_num}", 'JPN', 'original'))
                    return works

                data = await response.json()
                if not data or not isinstance(data, list) or len(data) == 0:
                    works.append(LinkedWorkInfo(f"RJ{rjcode_num}", 'JPN', 'original'))
                    return works

                product = data[0]

                # 获取翻译信息
                trans_info = product.get('translation_info', {})
                is_original = trans_info.get('is_original', True)
                is_parent = trans_info.get('is_parent', False)
                is_child = trans_info.get('is_child', False)
                original_workno = trans_info.get('original_workno')
                parent_workno = trans_info.get('parent_workno')
                current_lang = trans_info.get('lang', 'JPN')

                # 添加原作品
                if is_original:
                    works.append(LinkedWorkInfo(f"RJ{rjcode_num}", 'JPN', 'original'))
                elif original_workno:
                    works.append(LinkedWorkInfo(original_workno, 'JPN', 'original'))
                    if parent_workno and parent_workno != original_workno:
                        works.append(LinkedWorkInfo(parent_workno, current_lang, 'parent'))
                    works.append(LinkedWorkInfo(f"RJ{rjcode_num}", current_lang, 'child'))
                elif is_parent:
                    if original_workno:
                        works.append(LinkedWorkInfo(original_workno, 'JPN', 'original'))
                    works.append(LinkedWorkInfo(f"RJ{rjcode_num}", current_lang, 'parent'))
                else:
                    works.append(LinkedWorkInfo(f"RJ{rjcode_num}", current_lang, 'original'))

                # 获取语言版本
                language_editions = product.get('language_editions', [])
                if isinstance(language_editions, dict):
                    language_editions = list(language_editions.values())

                for edition in language_editions:
                    workno = edition.get('workno')
                    lang = edition.get('lang', 'JPN')
                    if workno and workno not in [w.workno for w in works]:
                        works.append(LinkedWorkInfo(workno, lang, 'translation'))

                # 对于子版本，也需要从父版本或原版获取语言版本
                if is_child and original_workno:
                    try:
                        parent_url = f"{self.DLSITE_API}?workno={original_workno}"
                        async with session.get(parent_url) as parent_response:
                            if parent_response.status == 200:
                                parent_data = await parent_response.json()
                                if parent_data and isinstance(parent_data, list) and len(parent_data) > 0:
                                    parent_product = parent_data[0]
                                    parent_editions = parent_product.get('language_editions', [])
                                    if isinstance(parent_editions, dict):
                                        parent_editions = list(parent_editions.values())

                                    for edition in parent_editions:
                                        workno = edition.get('workno')
                                        lang = edition.get('lang', 'JPN')
                                        if workno and workno not in [w.workno for w in works]:
                                            works.append(LinkedWorkInfo(workno, lang, 'translation'))
                    except Exception as e:
                        logger.warning(f"[DLsite] 获取父版本语言版本失败: {e}")

        except Exception as e:
            logger.error(f"[DLsite] 获取关联作品失败: {e}")
            if not works:
                works.append(LinkedWorkInfo(f"RJ{rjcode_num}", 'JPN', 'original'))

        # 按语言优先级排序
        works.sort(key=lambda w: w.priority)

        # 缓存结果
        self._cache[cache_key] = {
            'data': works,
            'timestamp': datetime.now()
        }

        logger.info(f"[DLsite] 找到 {len(works)} 个关联版本: {[(w.workno, w.lang) for w in works]}")
        return works

    async def fetch_work_info(self, rjcode: str) -> Optional[Dict]:
        """
        从 asmr.one API 获取作品信息

        Args:
            rjcode: RJ号，如 "RJ123456" 或 "123456"

        Returns:
            作品信息字典，包含标题、文件列表等
        """
        # 标准化 RJ 号
        if rjcode.upper().startswith('RJ'):
            rjcode_num = rjcode[2:]
        else:
            rjcode_num = rjcode

        session = await self._get_session()

        # 尝试所有 API 服务器
        for attempt in range(len(self.API_BASE_URLS)):
            api_base = self._get_api_base()
            url = f"{api_base}/workInfo/{rjcode_num}"

            try:
                logger.info(f"[ASMR] 获取作品信息: {url}")
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"[ASMR] 成功获取作品信息: {data.get('title', '未知标题')}")
                        return data
                    elif response.status == 404:
                        logger.warning(f"[ASMR] 作品不存在: {rjcode}")
                        return None
                    else:
                        logger.warning(f"[ASMR] 获取作品信息失败: HTTP {response.status}")
                        await self._switch_api()
            except aiohttp.ClientError as e:
                logger.error(f"[ASMR] 请求作品信息失败: {e}")
                await self._switch_api()

        logger.error(f"[ASMR] 所有 API 服务器都无法访问: {rjcode}")
        return None

    async def find_best_available_work(self, rjcode: str) -> Tuple[Optional[str], Optional[Dict]]:
        """
        查找最佳可用版本

        按简中 > 繁中 > 日文优先级搜索，返回第一个在 asmr.one 上可用的版本

        Args:
            rjcode: 原始 RJ号

        Returns:
            (可用RJ号, 作品信息) 或 (None, None)
        """
        # 获取所有关联版本
        linked_works = await self.get_linked_works_from_dlsite(rjcode)

        logger.info(f"[搜索] 开始按优先级搜索可用版本，共 {len(linked_works)} 个候选")

        for work in linked_works:
            logger.info(f"[搜索] 尝试: {work.workno} (语言: {work.lang}, 优先级: {work.priority})")

            work_info = await self.fetch_work_info(work.workno)
            if work_info:
                # 检查是否有文件
                tracks = await self.fetch_track_list(work.workno)
                if tracks:
                    logger.info(f"[搜索] 找到可用版本: {work.workno} ({work.lang})")
                    return work.workno, work_info

            # 添加延迟避免请求过快
            await asyncio.sleep(0.5)

        logger.warning(f"[搜索] 未找到任何可用版本: {rjcode}")
        return None, None

    async def fetch_track_list(self, rjcode: str) -> Optional[List[Dict]]:
        """
        获取作品的音轨/文件列表

        Args:
            rjcode: RJ号

        Returns:
            文件列表
        """
        # 标准化 RJ 号
        if rjcode.upper().startswith('RJ'):
            rjcode_num = rjcode[2:]
        else:
            rjcode_num = rjcode

        session = await self._get_session()

        for attempt in range(len(self.API_BASE_URLS)):
            api_base = self._get_api_base()
            url = f"{api_base}/tracks/{rjcode_num}"

            try:
                logger.info(f"[ASMR] 获取文件列表: {url}")
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        file_count = len(data) if isinstance(data, list) else 0
                        logger.info(f"[ASMR] 成功获取文件列表，共 {file_count} 个文件")

                        # 调试：打印第一个文件/文件夹的完整结构
                        if data and isinstance(data, list) and len(data) > 0:
                            first_item = data[0]
                            logger.info(f"[ASMR] 第一个项目结构: {list(first_item.keys())}")
                            if first_item.get('type') == 'folder' and first_item.get('children'):
                                logger.info(f"[ASMR] 第一个文件夹名称: {first_item.get('title')}")
                                children = first_item.get('children', [])
                                if children:
                                    logger.info(f"[ASMR] 第一个子项目结构: {list(children[0].keys())}")
                                    logger.info(f"[ASMR] 第一个子项目详情: {children[0]}")
                            else:
                                logger.info(f"[ASMR] 第一个文件详情: {first_item}")

                        return data
                    elif response.status == 404:
                        logger.warning(f"[ASMR] 文件列表不存在: {rjcode}")
                        return []
                    else:
                        logger.warning(f"[ASMR] 获取文件列表失败: HTTP {response.status}")
                        await self._switch_api()
            except aiohttp.ClientError as e:
                logger.error(f"[ASMR] 请求文件列表失败: {e}")
                await self._switch_api()

        logger.error(f"[ASMR] 所有 API 服务器都无法获取文件列表: {rjcode}")
        return None

    def _flatten_tracks(self, tracks: List[Dict], parent_path: str = "") -> List[Dict]:
        """
        扁平化音轨列表，提取所有可下载的文件

        Args:
            tracks: 音轨列表
            parent_path: 父级路径

        Returns:
            扁平化的文件列表
        """
        files = []

        for track in tracks:
            # 构建当前路径
            current_path = os.path.join(parent_path, track.get('title', '')) if parent_path else track.get('title', '')

            if track.get('type') == 'folder':
                # 如果是文件夹，递归处理子项
                children = track.get('children', [])
                files.extend(self._flatten_tracks(children, current_path))
            else:
                # 如果是文件，添加到列表
                # 支持多种ID字段名：id, hash, media_id
                file_id = track.get('id') or track.get('hash') or track.get('media_id')

                # 获取下载URL - 支持驼峰和下划线两种命名
                download_url = (track.get('mediaDownloadUrl') or
                               track.get('media_download_url') or
                               track.get('downloadUrl') or
                               track.get('download_url'))

                file_info = {
                    'id': file_id,
                    'title': track.get('title', ''),
                    'path': current_path,
                    'type': track.get('type'),
                    'media_download_url': download_url,
                    'size': track.get('size', 0),
                    'hash': track.get('hash'),  # ASMR.one 使用 hash 作为下载标识
                }
                files.append(file_info)

                # 调试：打印第一个文件的结构
                if len(files) == 1:
                    logger.info(f"[ASMR] 解析后第一个文件: title={file_info['title']}, download_url={download_url[:80] if download_url else 'None'}")

        return files

    async def download_file(
        self,
        url: str,
        dest_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        max_retries: int = 10,
        timeout: int = 60
    ) -> bool:
        """
        下载单个文件（支持断点续传和重试）

        Args:
            url: 下载 URL
            dest_path: 目标路径
            progress_callback: 进度回调函数 (downloaded_bytes, total_bytes)
            max_retries: 最大重试次数（默认10次）
            timeout: 单次请求超时时间（秒，默认60秒）

        Returns:
            是否成功
        """
        session = await self._get_session()

        for attempt in range(max_retries):
            try:
                # 确保目标目录存在
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)

                # 检查是否有未完成的下载（断点续传）
                temp_path = dest_path + '.downloading'
                resume_offset = 0

                if os.path.exists(temp_path):
                    resume_offset = os.path.getsize(temp_path)
                    logger.info(f"[下载] 发现未完成文件，从 {resume_offset} 字节处续传: {os.path.basename(dest_path)}")
                elif os.path.exists(dest_path):
                    # 文件已存在，检查大小是否完整
                    existing_size = os.path.getsize(dest_path)
                    # 先获取远程文件大小
                    async with session.head(url, timeout=aiohttp.ClientTimeout(total=30)) as head_response:
                        if head_response.status == 200:
                            remote_size = int(head_response.headers.get('content-length', 0))
                            if remote_size > 0 and existing_size >= remote_size:
                                logger.info(f"[下载] 文件已存在且完整，跳过: {os.path.basename(dest_path)}")
                                return True
                            elif existing_size > 0:
                                # 文件存在但不完整，重命名并续传
                                os.rename(dest_path, temp_path)
                                resume_offset = existing_size
                                logger.info(f"[下载] 文件不完整({existing_size}/{remote_size})，续传: {os.path.basename(dest_path)}")

                # 构建请求头（支持断点续传）
                headers = {}
                if resume_offset > 0:
                    headers['Range'] = f'bytes={resume_offset}-'

                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                    # 处理响应状态
                    if resume_offset > 0 and response.status == 206:
                        # 服务器支持断点续传
                        content_range = response.headers.get('content-range', '')
                        total_size = int(content_range.split('/')[-1]) if '/' in content_range else 0
                        downloaded = resume_offset
                        logger.info(f"[下载] 服务器支持断点续传，从 {resume_offset}/{total_size} 继续")
                    elif resume_offset > 0 and response.status == 200:
                        # 服务器不支持断点续传，重新下载
                        resume_offset = 0
                        total_size = int(response.headers.get('content-length', 0))
                        downloaded = 0
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                        logger.info(f"[下载] 服务器不支持断点续传，重新下载")
                    elif response.status != 200:
                        logger.error(f"下载失败: HTTP {response.status}, URL: {url}")
                        if attempt < max_retries - 1:
                            wait_time = min(5 * (attempt + 1), 30)  # 递增等待时间，最多30秒
                            logger.info(f"[下载] 等待 {wait_time} 秒后重试...")
                            await asyncio.sleep(wait_time)
                            continue
                        return False
                    else:
                        total_size = int(response.headers.get('content-length', 0))
                        downloaded = 0

                    # 写入文件
                    write_path = temp_path if resume_offset == 0 or response.status == 206 else dest_path
                    mode = 'ab' if resume_offset > 0 and response.status == 206 else 'wb'

                    with open(write_path, mode) as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback and total_size > 0:
                                progress_callback(downloaded, total_size)

                    # 下载完成，重命名临时文件
                    if os.path.exists(temp_path):
                        if os.path.exists(dest_path):
                            os.remove(dest_path)
                        os.rename(temp_path, dest_path)

                    logger.info(f"下载完成: {dest_path} ({downloaded} bytes)")
                    return True

            except asyncio.TimeoutError:
                logger.warning(f"[下载] 超时({timeout}秒)，第 {attempt + 1}/{max_retries} 次尝试: {os.path.basename(dest_path)}")
                if attempt < max_retries - 1:
                    wait_time = min(5 * (attempt + 1), 30)
                    logger.info(f"[下载] 等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
            except aiohttp.ClientError as e:
                logger.warning(f"[下载] 连接错误 {e}，第 {attempt + 1}/{max_retries} 次尝试: {os.path.basename(dest_path)}")
                if attempt < max_retries - 1:
                    wait_time = min(5 * (attempt + 1), 30)
                    logger.info(f"[下载] 等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
            except Exception as e:
                logger.error(f"下载文件失败: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(5)

        # 返回失败，但保留临时文件以支持后续续传
        logger.error(f"[下载] 文件下载失败，已尝试 {max_retries} 次: {os.path.basename(dest_path)}")
        return False

    def filter_files(self, files: List[Dict], filter_rules: List) -> List[Dict]:
        """
        应用筛选规则过滤文件列表

        Args:
            files: 文件列表
            filter_rules: 筛选规则列表（可以是对象或字典）

        Returns:
            过滤后的文件列表
        """
        if not filter_rules:
            logger.info("[筛选] 没有筛选规则，保留所有文件")
            return files

        # 音频扩展名集合
        audio_extensions = {'.wav', '.mp3', '.flac', '.m4a', '.ogg', '.wma', '.aac'}

        # 先打印所有筛选规则的状态
        logger.info(f"[筛选] 共有 {len(filter_rules)} 条筛选规则:")
        for i, rule in enumerate(filter_rules):
            if isinstance(rule, dict):
                name = rule.get('name', f'规则{i+1}')
                enabled = rule.get('enabled', True)
                pattern = rule.get('pattern', '')
                target = rule.get('target', 'file')
            else:
                name = getattr(rule, 'name', f'规则{i+1}')
                enabled = getattr(rule, 'enabled', True)
                pattern = getattr(rule, 'pattern', '')
                target = getattr(rule, 'target', 'file')
            status = "启用" if enabled else "禁用"
            logger.info(f"[筛选]   - {name}: pattern='{pattern}', target='{target}', 状态={status}")

        filtered_files = []
        excluded_count = 0

        # 调试：打印前几个文件名
        if files:
            logger.info(f"[筛选] 前5个文件名示例:")
            for i, f in enumerate(files[:5]):
                logger.info(f"[筛选]   {i+1}. title='{f.get('title', '')}', path='{f.get('path', '')}'")

        for file_info in files:
            file_name = file_info.get('title', '')
            file_path = file_info.get('path', file_name)  # 完整路径，包含文件夹名
            ext = os.path.splitext(file_name)[1].lower()

            # 只处理音频文件
            if ext not in audio_extensions:
                # 非音频文件（如图片、文本等）直接保留
                filtered_files.append(file_info)
                continue

            # 应用筛选规则
            should_exclude = False
            for rule in filter_rules:
                # 支持字典和对象两种访问方式
                if isinstance(rule, dict):
                    enabled = rule.get('enabled', True)
                    target = rule.get('target', 'file')
                    pattern = rule.get('pattern', '')
                    name = rule.get('name', '')
                else:
                    enabled = getattr(rule, 'enabled', True)
                    target = getattr(rule, 'target', 'file')
                    pattern = getattr(rule, 'pattern', '')
                    name = getattr(rule, 'name', '')

                if not enabled:
                    continue

                try:
                    # 根据target决定检查什么内容
                    if target == 'folder':
                        # 文件夹规则：检查完整路径（包含文件夹名）
                        check_content = file_path
                    elif target == 'all':
                        # 全部规则：检查路径和文件名
                        check_content = file_path
                    else:
                        # file规则：只检查文件名
                        check_content = file_name

                    if re.search(pattern, check_content, re.IGNORECASE):
                        should_exclude = True
                        logger.info(f"[筛选] 文件被规则 [{name}] 过滤: {file_path} (匹配'{pattern}')")
                        excluded_count += 1
                        break
                except re.error as e:
                    logger.error(f"正则表达式错误: {pattern}, {e}")

            if not should_exclude:
                filtered_files.append(file_info)

        logger.info(f"[筛选] 原始文件数: {len(files)}, 筛选后: {len(filtered_files)}, 排除: {excluded_count}")
        return filtered_files

    async def download_work(
        self,
        rjcode: str,
        dest_dir: str,
        filter_rules: List = None,
        progress_callback: Optional[Callable[[str, int, int, str], None]] = None,
        file_progress_callback: Optional[Callable[[str, int, int, int, int], None]] = None,
        check_pause: Optional[Callable[[], bool]] = None
    ) -> Dict:
        """
        下载整个作品并应用筛选规则
        自动搜索最佳可用版本（简中 > 繁中 > 日文）

        Args:
            rjcode: RJ号
            dest_dir: 目标目录
            filter_rules: 筛选规则列表
            progress_callback: 进度回调 (rjcode, current, total, step)
            file_progress_callback: 文件进度回调 (file_name, file_index, total_files, downloaded_bytes, total_bytes)
            check_pause: 检查是否需要暂停的回调函数，返回True表示需要暂停

        Returns:
            下载结果
        """
        result = {
            'rjcode': rjcode,
            'actual_rjcode': None,  # 实际下载的RJ号
            'success': False,
            'title': '',
            'lang': '',  # 实际下载版本的语言
            'downloaded_files': [],
            'failed_files': [],  # 失败的文件列表
            'filtered_files': [],
            'error': None,
            'tried_versions': [],  # 尝试过的版本列表
            'paused': False  # 是否被暂停
        }

        try:
            # 查找最佳可用版本
            if progress_callback:
                progress_callback(rjcode, 0, 100, "搜索最佳版本...")

            actual_rjcode, work_info = await self.find_best_available_work(rjcode)

            if not work_info:
                result['error'] = '在 asmr.one 上未找到该作品的任何版本'
                return result

            result['actual_rjcode'] = actual_rjcode
            result['title'] = work_info.get('title', '未知标题')

            # 获取文件列表
            if progress_callback:
                progress_callback(actual_rjcode, 5, 100, "获取文件列表...")

            tracks = await self.fetch_track_list(actual_rjcode)
            if tracks is None:
                result['error'] = '无法获取文件列表'
                return result

            if not tracks:
                result['error'] = '文件列表为空'
                return result

            # 扁平化文件列表
            all_files = self._flatten_tracks(tracks)
            logger.info(f"作品 {actual_rjcode} 共有 {len(all_files)} 个文件")

            # 应用筛选规则
            if filter_rules:
                logger.info(f"[筛选] 收到 {len(filter_rules)} 条筛选规则")
                # 详细打印每条规则
                for i, rule in enumerate(filter_rules):
                    if isinstance(rule, dict):
                        logger.info(f"[筛选] 规则{i+1}: {rule}")
                    else:
                        logger.info(f"[筛选] 规则{i+1}: {getattr(rule, 'name', 'unknown')}, enabled={getattr(rule, 'enabled', True)}, pattern={getattr(rule, 'pattern', '')}")

                filtered_files = self.filter_files(all_files, filter_rules)
                result['filtered_files'] = [f for f in all_files if f not in filtered_files]
                all_files = filtered_files
                logger.info(f"筛选后剩余 {len(all_files)} 个文件")
            else:
                logger.warning("[筛选] 没有收到筛选规则，将下载所有文件！")

            if not all_files:
                result['error'] = '筛选后没有可下载的文件'
                return result

            # 创建下载目录
            os.makedirs(dest_dir, exist_ok=True)

            # 下载文件
            total_files = len(all_files)
            failed_files = []  # 记录失败的文件

            for i, file_info in enumerate(all_files):
                # 检查是否需要暂停
                if check_pause and check_pause():
                    result['paused'] = True
                    result['failed_files'] = failed_files
                    logger.info(f"[ASMR] 下载被暂停，已完成 {i}/{total_files} 个文件")
                    return result

                relative_path = file_info.get('path', file_info['title'])
                if progress_callback:
                    progress_callback(actual_rjcode, i + 1, total_files, f"下载: {relative_path[:30]}")

                # 获取下载 URL - 优先使用 API 返回的完整下载链接
                download_url = file_info.get('media_download_url')

                # 如果没有完整链接，尝试通过 hash 构建
                if not download_url:
                    api_base = self._get_api_base()
                    file_hash = file_info.get('hash')
                    if file_hash:
                        download_url = f"{api_base}/download/{file_hash}"
                        logger.info(f"[ASMR] 构建下载链接: {download_url}")

                if not download_url:
                    logger.warning(f"无法获取下载链接: {file_info['title']}")
                    failed_files.append({
                        'path': relative_path,
                        'title': file_info['title'],
                        'reason': '无法获取下载链接'
                    })
                    continue

                # 构建目标路径 - 使用完整路径（包含文件夹层级）
                file_path = os.path.join(dest_dir, relative_path)

                logger.info(f"[ASMR] 下载文件 ({i+1}/{total_files}): {relative_path}")

                # 文件进度回调包装
                def make_file_callback(fname, findex, ftotal):
                    def cb(downloaded, total):
                        if file_progress_callback:
                            file_progress_callback(fname, findex, ftotal, downloaded, total)
                    return cb

                # 下载文件
                success = await self.download_file(
                    download_url,
                    file_path,
                    progress_callback=make_file_callback(relative_path, i + 1, total_files) if file_progress_callback else None
                )
                if success:
                    result['downloaded_files'].append({
                        'path': file_path,
                        'title': file_info['title'],
                        'relative_path': relative_path,
                        'size': file_info.get('size', 0)
                    })
                else:
                    failed_files.append({
                        'path': relative_path,
                        'title': file_info['title'],
                        'download_url': download_url,
                        'file_info': file_info,
                        'reason': '下载失败'
                    })

            result['failed_files'] = failed_files

            # 如果有失败文件，记录警告但不标记为完全失败（部分文件可能已下载）
            if failed_files:
                logger.warning(f"[ASMR] 下载完成但有 {len(failed_files)} 个文件失败:")
                for f in failed_files[:5]:  # 只显示前5个
                    logger.warning(f"  - {f['title']}: {f['reason']}")

            result['success'] = len(result['downloaded_files']) > 0
            logger.info(f"作品 {actual_rjcode} 下载完成，成功 {len(result['downloaded_files'])} 个，失败 {len(failed_files)} 个")

        except Exception as e:
            logger.error(f"下载作品失败: {e}", exc_info=True)
            result['error'] = str(e)

        return result


# 全局服务实例
_asmr_download_service: Optional[ASMRDownloadService] = None


def get_asmr_download_service() -> ASMRDownloadService:
    """获取 ASMR 下载服务实例"""
    global _asmr_download_service
    if _asmr_download_service is None:
        _asmr_download_service = ASMRDownloadService()
    return _asmr_download_service