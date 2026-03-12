"""
字幕同步服务
处理字幕文件的扫描、匹配和重命名

核心功能：
1. 将下载的wav文件重命名为与lrc字幕文件匹配的名称
2. 确保wav和lrc文件的对应顺序正确
3. 处理标题只有日文的情况，使用字幕文件夹中的标准命名
4. 净化LRC文件中的广告内容
"""
import os
import re
import shutil
import logging
from typing import Optional, List, Dict, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class SubtitleSyncService:
    """字幕同步服务"""

    # 支持的字幕格式
    SUBTITLE_EXTENSIONS = {'.lrc', '.vtt', '.srt', '.ass', '.ssa'}

    # 支持的音频格式
    AUDIO_EXTENSIONS = {'.wav', '.mp3', '.flac', '.m4a', '.ogg', '.wma', '.aac'}

    # LRC广告清理正则表达式
    LRC_AD_PATTERNS = [
        # Telegram账号
        r'@[\w]{3,}',
        # 社交媒体链接
        r'(?:https?://)?(?:www\.)?(?:telegram|t)\.me/\S+',
        r'(?:https?://)?(?:www\.)?twitter\.com/\S+',
        r'(?:https?://)?(?:www\.)?x\.com/\S+',
        r'(?:https?://)?(?:www\.)?weibo\.com/\S+',
        r'(?:https?://)?(?:www\.)?weibo\.cn/\S+',
        # QQ/微信群
        r'QQ群[：:]\s*\d+',
        r'微信群[：:]\s*[\w\-]+',
        r'群号[：:]\s*\d+',
        # 常见广告关键词
        r'Telegram',
        r'telegram',
        r'电报',
        r'tg群',
        r'TG群',
        # 网站推广
        r'(?:https?://)?(?:www\.)?asmr\d*\.one\S*',
        r'(?:https?://)?(?:www\.)?dlsite\.com/\S+',
        # 纯数字ID广告（通常是QQ号）
        r'[\[【(]?\d{5,12}[\]】)]?(?=\s*$|\s*\])',
    ]

    def __init__(self):
        pass

    def clean_lrc_content(self, content: str, custom_patterns: List[str] = None) -> Tuple[str, int]:
        """
        清理LRC文件内容中的广告

        Args:
            content: LRC文件内容
            custom_patterns: 自定义清理规则列表

        Returns:
            (清理后的内容, 清理的行数)
        """
        lines = content.split('\n')
        cleaned_lines = []
        removed_count = 0

        # 合并默认规则和自定义规则
        all_patterns = list(self.LRC_AD_PATTERNS)
        if custom_patterns:
            all_patterns.extend(custom_patterns)

        # 编译所有正则表达式
        compiled_patterns = []
        for pattern in all_patterns:
            try:
                compiled_patterns.append(re.compile(pattern, re.IGNORECASE))
            except re.error as e:
                logger.warning(f"无效的正则表达式: {pattern}, 错误: {e}")

        for line in lines:
            original_line = line

            # 检查是否是时间轴行（格式：[mm:ss.xx] 或 [mm:ss:xx]）
            time_match = re.match(r'^(\[\d{1,2}:\d{2}[.:]\d{2,3}\])', line)
            if time_match:
                time_tag = time_match.group(1)
                text = line[len(time_tag):].strip()

                # 检查文本是否匹配广告规则
                is_ad = False
                for pattern in compiled_patterns:
                    if pattern.search(text):
                        is_ad = True
                        break

                if is_ad:
                    # 清除广告内容，只保留时间轴
                    cleaned_lines.append(time_tag)
                    removed_count += 1
                    logger.debug(f"清理广告: '{original_line}' -> '{time_tag}'")
                else:
                    cleaned_lines.append(original_line)
            else:
                # 非时间轴行，保留原样（如元数据行 [ti:标题] 等）
                cleaned_lines.append(original_line)

        return '\n'.join(cleaned_lines), removed_count

    def clean_lrc_file(self, lrc_path: str, custom_patterns: List[str] = None) -> Tuple[bool, int]:
        """
        清理单个LRC文件

        Args:
            lrc_path: LRC文件路径
            custom_patterns: 自定义清理规则列表

        Returns:
            (是否成功, 清理的行数)
        """
        try:
            with open(lrc_path, 'r', encoding='utf-8') as f:
                content = f.read()

            cleaned_content, removed_count = self.clean_lrc_content(content, custom_patterns)

            if removed_count > 0:
                with open(lrc_path, 'w', encoding='utf-8') as f:
                    f.write(cleaned_content)
                logger.info(f"[LRC清理] {os.path.basename(lrc_path)}: 清理了 {removed_count} 行广告")

            return True, removed_count

        except Exception as e:
            logger.error(f"[LRC清理] 处理文件失败 {lrc_path}: {e}")
            return False, 0

    def clean_lrc_files_in_folder(self, folder_path: str, custom_patterns: List[str] = None) -> Dict:
        """
        清理文件夹中的所有LRC文件

        Args:
            folder_path: 文件夹路径
            custom_patterns: 自定义清理规则列表

        Returns:
            清理结果统计
        """
        result = {
            'total_files': 0,
            'cleaned_files': 0,
            'total_removed_lines': 0,
            'errors': []
        }

        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith('.lrc'):
                    lrc_path = os.path.join(root, file)
                    result['total_files'] += 1

                    success, removed_count = self.clean_lrc_file(lrc_path, custom_patterns)

                    if success:
                        if removed_count > 0:
                            result['cleaned_files'] += 1
                            result['total_removed_lines'] += removed_count
                    else:
                        result['errors'].append(lrc_path)

        if result['total_files'] > 0:
            logger.info(f"[LRC清理] 完成: 处理 {result['total_files']} 个文件, "
                       f"清理 {result['cleaned_files']} 个文件, "
                       f"移除 {result['total_removed_lines']} 行广告")

        return result

    def convert_to_simplified_chinese(self, text: str) -> Tuple[str, bool]:
        """
        将繁体中文转换为简体中文

        Args:
            text: 原始文本

        Returns:
            (转换后的文本, 是否发生了转换)
        """
        try:
            import opencc

            # 创建繁体到简体的转换器
            converter = opencc.OpenCC('t2s')  # traditional to simplified

            # 检查文本中是否包含繁体字
            converted_text = converter.convert(text)

            # 检查是否有变化
            if converted_text != text:
                return converted_text, True
            return text, False

        except Exception as e:
            logger.error(f"[繁简转换] 转换失败: {e}")
            return text, False

    def convert_subtitle_file_to_simplified(self, file_path: str) -> Tuple[bool, bool]:
        """
        将字幕文件内容从繁体中文转换为简体中文

        Args:
            file_path: 字幕文件路径

        Returns:
            (是否成功, 是否发生了转换)
        """
        try:
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 转换为简体
            converted_content, was_converted = self.convert_to_simplified_chinese(content)

            # 如果有变化，写回文件
            if was_converted:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(converted_content)
                logger.info(f"[繁简转换] {os.path.basename(file_path)}: 已转换为简体中文")

            return True, was_converted

        except Exception as e:
            logger.error(f"[繁简转换] 处理文件失败 {file_path}: {e}")
            return False, False

    def convert_subtitles_to_simplified_in_folder(self, folder_path: str) -> Dict:
        """
        将文件夹中的所有字幕文件转换为简体中文

        Args:
            folder_path: 文件夹路径

        Returns:
            转换结果统计
        """
        result = {
            'total_files': 0,
            'converted_files': 0,
            'errors': []
        }

        for root, dirs, files in os.walk(folder_path):
            for file in files:
                # 检查是否是字幕文件
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext in self.SUBTITLE_EXTENSIONS:
                    subtitle_path = os.path.join(root, file)
                    result['total_files'] += 1

                    success, was_converted = self.convert_subtitle_file_to_simplified(subtitle_path)

                    if success:
                        if was_converted:
                            result['converted_files'] += 1
                    else:
                        result['errors'].append(subtitle_path)

        if result['total_files'] > 0:
            logger.info(f"[繁简转换] 完成: 处理 {result['total_files']} 个文件, "
                       f"转换 {result['converted_files']} 个文件")

        return result

    def scan_subtitle_folders(self, source_dir: str) -> List[Dict]:
        """
        扫描包含字幕文件的文件夹

        Args:
            source_dir: 源目录路径

        Returns:
            发现的作品列表，每个元素包含 rjcode, folder_path, subtitle_files
        """
        results = []

        if not os.path.exists(source_dir):
            logger.warning(f"源目录不存在: {source_dir}")
            return results

        # 遍历源目录下的子文件夹
        for item in os.listdir(source_dir):
            item_path = os.path.join(source_dir, item)

            if not os.path.isdir(item_path):
                continue

            # 尝试提取 RJ 号
            rjcode = self.extract_rjcode_from_folder(item)
            if not rjcode:
                logger.debug(f"无法从文件夹名提取 RJ 号: {item}")
                continue

            # 扫描字幕文件
            subtitle_files = self._scan_subtitle_files(item_path)

            if subtitle_files:
                results.append({
                    'rjcode': rjcode,
                    'folder_name': item,
                    'folder_path': item_path,
                    'subtitle_files': subtitle_files,
                    'subtitle_count': len(subtitle_files)
                })
                logger.info(f"发现作品: {rjcode}, 字幕文件: {len(subtitle_files)} 个")

        return results

    def extract_rjcode_from_folder(self, folder_name: str) -> Optional[str]:
        """
        从文件夹名提取 RJ 号

        支持格式:
        - RJ123456 标题
        - RJ12345678 标题
        - [RJ123456] 标题
        - RJ123456

        Args:
            folder_name: 文件夹名称

        Returns:
            RJ 号（如 RJ123456）或 None
        """
        # 匹配 RJ + 6位或8位数字
        pattern = r'[RVB]J(\d{6}|\d{8})(?!\d)'
        match = re.search(pattern, folder_name, re.IGNORECASE)
        if match:
            return match.group(0).upper()
        return None

    def _scan_subtitle_files(self, folder_path: str) -> List[Dict]:
        """
        扫描文件夹中的字幕文件

        Args:
            folder_path: 文件夹路径

        Returns:
            字幕文件信息列表
        """
        subtitle_files = []

        for root, dirs, files in os.walk(folder_path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in self.SUBTITLE_EXTENSIONS:
                    file_path = os.path.join(root, file)
                    subtitle_files.append({
                        'name': file,
                        'path': file_path,
                        'ext': ext,
                        'base_name': os.path.splitext(file)[0]
                    })

        return subtitle_files

    def match_audio_subtitle(self, audio_files: List[str], subtitle_files: List[Dict]) -> List[Dict]:
        """
        匹配音频文件和字幕文件

        匹配规则（按优先级）:
        1. 序号匹配: 提取数字序号，数值相同则匹配（如 "01" 和 "1" 都等于1）
        2. 文件顺序匹配: 当没有序号时，按文件列表顺序一一对应
        3. 标题相似度匹配: 作为辅助验证

        重要：将音频文件重命名为与字幕文件相同的名称（保留原音频扩展名）

        Args:
            audio_files: 音频文件路径列表
            subtitle_files: 字幕文件信息列表

        Returns:
            匹配结果列表，每个元素包含 audio_path, subtitle_path, new_audio_name
        """
        matches = []
        used_audio = set()  # 记录已匹配的音频文件

        # 第一步：按序号匹配（最可靠）
        logger.info(f"[字幕同步] 开始匹配 {len(audio_files)} 个音频文件和 {len(subtitle_files)} 个字幕文件")

        # 提取所有音频文件的序号
        audio_with_number = []
        audio_without_number = []
        for audio_path in audio_files:
            audio_name = os.path.splitext(os.path.basename(audio_path))[0]
            audio_number = self._extract_track_number(audio_name)
            if audio_number is not None:
                audio_with_number.append((audio_number, audio_path, audio_name))
            else:
                audio_without_number.append((audio_path, audio_name))

        # 提取所有字幕文件的序号
        subtitle_with_number = []
        subtitle_without_number = []
        for sub_info in subtitle_files:
            subtitle_name = sub_info['base_name']
            subtitle_number = self._extract_track_number(subtitle_name)
            if subtitle_number is not None:
                subtitle_with_number.append((subtitle_number, sub_info))
            else:
                subtitle_without_number.append(sub_info)

        logger.info(f"[字幕同步] 有序号的音频: {len(audio_with_number)}, 无序号: {len(audio_without_number)}")
        logger.info(f"[字幕同步] 有序号的字幕: {len(subtitle_with_number)}, 无序号: {len(subtitle_without_number)}")

        # 按序号匹配（使用数值比较，"01" 和 "1" 都是1，会匹配）
        audio_number_map = {}  # {数字序号: (路径, 名称)}
        for num, path, name in audio_with_number:
            if num not in audio_number_map:  # 避免重复序号覆盖
                audio_number_map[num] = (path, name)

        for sub_number, sub_info in sorted(subtitle_with_number, key=lambda x: x[0]):
            if sub_number in audio_number_map:
                audio_path, audio_name = audio_number_map[sub_number]
                if audio_path not in used_audio:
                    audio_ext = os.path.splitext(audio_path)[1]
                    new_name = sub_info['base_name'] + audio_ext

                    matches.append({
                        'audio_path': audio_path,
                        'subtitle_path': sub_info['path'],
                        'subtitle_name': sub_info['name'],
                        'new_audio_name': new_name,
                        'match_score': 100,
                        'match_type': f'序号匹配({sub_number})'
                    })
                    used_audio.add(audio_path)
                    logger.info(f"[字幕同步] 序号匹配({sub_number}): 音频'{audio_name}' -> 字幕'{sub_info['base_name']}'")

        # 第二步：对于没有序号的文件，按文件列表顺序匹配
        # 按原始序号排序剩余的音频文件
        remaining_audio = [(path, name) for path, name in audio_without_number if path not in used_audio]
        # 有序号但未匹配的也加入（按序号排序）
        remaining_audio_from_numbered = [(path, name) for num, path, name in sorted(audio_with_number, key=lambda x: x[0]) if path not in used_audio]
        remaining_audio.extend(remaining_audio_from_numbered)

        # 字幕也按原始序号排序
        remaining_subtitle = list(subtitle_without_number)
        remaining_subtitle.extend([s for num, s in sorted(subtitle_with_number, key=lambda x: x[0]) if s['path'] not in [m['subtitle_path'] for m in matches]])

        # 按顺序匹配剩余文件
        for i, (audio_path, audio_name) in enumerate(remaining_audio):
            if i < len(remaining_subtitle):
                sub_info = remaining_subtitle[i]
                audio_ext = os.path.splitext(audio_path)[1]
                new_name = sub_info['base_name'] + audio_ext

                matches.append({
                    'audio_path': audio_path,
                    'subtitle_path': sub_info['path'],
                    'subtitle_name': sub_info['name'],
                    'new_audio_name': new_name,
                    'match_score': 70,
                    'match_type': '顺序匹配'
                })
                used_audio.add(audio_path)
                logger.info(f"[字幕同步] 顺序匹配: 音频'{audio_name}' -> 字幕'{sub_info['base_name']}'")

        # 记录未匹配的文件
        unmatched_audio = [path for path in audio_files if path not in used_audio]
        if unmatched_audio:
            logger.warning(f"[字幕同步] {len(unmatched_audio)} 个音频文件未找到匹配的字幕")

        logger.info(f"[字幕同步] 匹配完成，成功匹配 {len(matches)} 对文件")
        return matches

    def _extract_track_number(self, filename: str) -> Optional[int]:
        """
        从文件名提取轨道序号（返回整数值）

        支持格式:
        - 01, 02, 03, 1, 2, 3
        - Track01, Track02, Track1, Track2
        - track_01, track_02
        - 01『标题』, 02『标题』
        - Tr1, Tr2, Tr01, Tr02

        Returns:
            整数序号，如 1, 2, 3... 或 None
        """
        # 移除开头的常见前缀
        clean_name = re.sub(r'^(Track|track|TRK|trk|Tr)[_-]?', '', filename)

        # 匹配开头的数字
        match = re.match(r'^(\d{1,3})', clean_name)
        if match:
            return int(match.group(1))  # 返回整数值，"01" -> 1, "1" -> 1

        return None

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        计算两个字符串的相似度

        使用简单的字符重叠率计算
        """
        # 清理字符串
        def clean(s):
            # 移除序号和标点
            s = re.sub(r'^\d{1,3}', '', s)
            s = re.sub(r'[『』「」\[\]（）\(\)\s]', '', s)
            return s.lower()

        c1 = clean(str1)
        c2 = clean(str2)

        if not c1 or not c2:
            return 0.0

        # 计算字符重叠率
        set1 = set(c1)
        set2 = set(c2)

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        if union == 0:
            return 0.0

        return intersection / union

    def rename_audio_to_match_subtitle(
        self,
        audio_path: str,
        new_name: str,
        dry_run: bool = False
    ) -> Tuple[bool, str]:
        """
        重命名音频文件使名称与字幕文件一致

        Args:
            audio_path: 音频文件路径
            new_name: 新文件名
            dry_run: 是否只预览不执行

        Returns:
            (是否成功, 新路径或错误信息)
        """
        try:
            dir_path = os.path.dirname(audio_path)
            new_path = os.path.join(dir_path, new_name)

            # 检查目标文件是否已存在
            if os.path.exists(new_path) and new_path != audio_path:
                logger.warning(f"目标文件已存在: {new_path}")
                return False, f"目标文件已存在: {new_name}"

            if dry_run:
                logger.info(f"[预览] 重命名: {os.path.basename(audio_path)} -> {new_name}")
                return True, new_path

            os.rename(audio_path, new_path)
            logger.info(f"重命名: {os.path.basename(audio_path)} -> {new_name}")
            return True, new_path

        except Exception as e:
            logger.error(f"重命名失败: {e}")
            return False, str(e)

    def sync_subtitles_to_download(
        self,
        download_dir: str,
        subtitle_folder: str,
        dry_run: bool = False
    ) -> Dict:
        """
        将字幕文件同步到下载目录

        Args:
            download_dir: 下载目录
            subtitle_folder: 字幕源文件夹
            dry_run: 是否只预览不执行

        Returns:
            同步结果
        """
        result = {
            'success': True,
            'renamed_files': [],
            'copied_subtitles': [],
            'errors': []
        }

        try:
            # 扫描下载的音频文件
            audio_files = []
            for root, dirs, files in os.walk(download_dir):
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in self.AUDIO_EXTENSIONS:
                        audio_files.append(os.path.join(root, file))

            # 扫描字幕文件
            subtitle_files = self._scan_subtitle_files(subtitle_folder)

            if not audio_files:
                result['errors'].append('下载目录中没有找到音频文件')
                result['success'] = False
                return result

            if not subtitle_files:
                result['errors'].append('字幕文件夹中没有找到字幕文件')
                result['success'] = False
                return result

            # 匹配音频和字幕
            matches = self.match_audio_subtitle(audio_files, subtitle_files)

            # 执行重命名和复制
            for match in matches:
                # 重命名音频文件
                success, new_path_or_error = self.rename_audio_to_match_subtitle(
                    match['audio_path'],
                    match['new_audio_name'],
                    dry_run
                )

                if success:
                    result['renamed_files'].append({
                        'original': os.path.basename(match['audio_path']),
                        'new': match['new_audio_name'],
                        'subtitle': match['subtitle_name']
                    })

                    # 复制字幕文件
                    if not dry_run:
                        subtitle_dest = os.path.join(
                            os.path.dirname(match['audio_path']),
                            match['subtitle_name']
                        )
                        shutil.copy2(match['subtitle_path'], subtitle_dest)
                        result['copied_subtitles'].append(match['subtitle_name'])
                else:
                    result['errors'].append(f"重命名失败: {new_path_or_error}")

            logger.info(f"字幕同步完成: 重命名 {len(result['renamed_files'])} 个文件")

        except Exception as e:
            logger.error(f"字幕同步失败: {e}", exc_info=True)
            result['success'] = False
            result['errors'].append(str(e))

        return result


# 全局服务实例
_subtitle_sync_service: Optional[SubtitleSyncService] = None


def get_subtitle_sync_service() -> SubtitleSyncService:
    """获取字幕同步服务实例"""
    global _subtitle_sync_service
    if _subtitle_sync_service is None:
        _subtitle_sync_service = SubtitleSyncService()
    return _subtitle_sync_service