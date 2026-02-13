import os
import re
import shutil
import subprocess
import asyncio
import filetype
from typing import Optional, List, Dict
from pathlib import Path
import logging

from ..config.settings import get_config
from ..core.task_engine import Task

logger = logging.getLogger(__name__)

class ArchiveInfo:
    """压缩包信息"""
    def __init__(self, path: str, file_list: List[Dict], password: Optional[str] = None):
        self.path = path
        self.file_list = file_list  # [{"name": "...", "size": 123, "crc": "..."}, ...]
        self.password = password
        self.is_volume = False
        self.volume_set: Optional[List[str]] = None

class ExtractService:
    """解压服务"""
    
    @property
    def config(self):
        """动态获取最新配置"""
        from ..config.settings import get_config
        return get_config()
    
    @property
    def seven_zip(self) -> str:
        """动态获取7z路径"""
        return self._find_7z_executable()
    
    def _find_7z_executable(self) -> str:
        """查找 7z 可执行文件"""
        import shutil
        
        # 首先尝试配置的路径
        configured_path = self.config.extract.seven_zip_path
        if configured_path and configured_path != "7z":
            if os.path.exists(configured_path):
                return configured_path
        
        # 尝试在 PATH 中查找
        seven_zip_path = shutil.which("7z")
        if seven_zip_path:
            return seven_zip_path
        
        # Windows 默认安装路径
        default_paths = [
            r"C:\Program Files\7-Zip\7z.exe",
            r"C:\Program Files (x86)\7-Zip\7z.exe",
        ]
        
        for path in default_paths:
            if os.path.exists(path):
                return path
        
        # 如果都找不到，返回配置的值（后续会报错）
        logger.error("找不到 7z 可执行文件。请安装 7-Zip 并确保它在 PATH 中，或在配置中指定正确路径。")
        return "7z"
    
    def _check_7z_available(self) -> bool:
        """检查 7z 是否可用"""
        try:
            result = subprocess.run([self.seven_zip, "--help"], capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"检查 7z 可用性失败: {e}")
            return False
    
    async def extract(self, task: Task) -> Optional[str]:
        """
        解压压缩包
        返回解压后的目录路径
        """
        # 首先检查 7z 是否可用
        if not self._check_7z_available():
            raise Exception("找不到 7z 可执行文件。请安装 7-Zip 并确保它在 PATH 中，或在配置中指定正确路径。")
        
        archive_path = task.source_path
        
        # 检查是否被取消
        if task.is_cancelled():
            logger.info(f"任务 {task.id} 已被取消，跳过解压")
            return None
        
        # 1. 等待文件稳定
        task.update_progress(5, "等待文件写入完成")
        await self._wait_file_stable(archive_path, task)
        
        # 检查暂停和取消
        await task.wait_if_paused()
        if task.is_cancelled():
            logger.info(f"任务 {task.id} 在等待文件稳定后被取消")
            return None
        
        # 2. 修复后缀名
        task.update_progress(10, "检测文件类型")
        archive_path = await self._repair_extension(archive_path)
        
        # 3. 检查是否是分卷
        volume_set = self._detect_volume_set(archive_path)
        if volume_set:
            task.update_progress(15, "等待分卷组完整")
            if not await self._wait_for_complete_set(volume_set, task):
                raise Exception("分卷组不完整或等待超时")
            archive_path = volume_set.volumes[0]  # 使用第一个分卷
        
        # 检查暂停和取消
        await task.wait_if_paused()
        if task.is_cancelled():
            logger.info(f"任务 {task.id} 在等待分卷后被取消")
            return None
        
        # 4. 获取压缩包内文件列表
        task.update_progress(20, "读取压缩包内容")
        archive_info = await self._get_archive_info(archive_path)
        if not archive_info:
            raise Exception("无法读取压缩包内容")
        
        # 5. 确定输出路径
        output_name = Path(archive_path).stem.strip()  # 去除首尾空格，避免Windows路径错误
        # 移除其他Windows不允许的字符
        output_name = re.sub(r'[<>:"|?*]', '', output_name)
        output_path = os.path.join(self.config.storage.temp_path, output_name)
        os.makedirs(output_path, exist_ok=True)
        
        # 6. 尝试解压
        task.update_progress(30, "开始解压")
        success, success_password = await self._try_extract(archive_info, output_path, task)
        
        if not success:
            # 更新任务状态为失败，并设置错误信息
            error_msg = "解压失败：无正确密码"
            task.fail(error_msg)
            logger.error(f"任务 {task.id}: {error_msg}")
            # 清理已创建的解压目录（包括部分解压的残留文件）
            self._cleanup_extract_path(output_path)
            return None
        
        # 记录成功使用的密码
        logger.info(f"外层压缩包解压成功，使用密码: {success_password or '无密码'}")
        
        # 检查暂停和取消
        await task.wait_if_paused()
        if task.is_cancelled():
            logger.info(f"任务 {task.id} 在解压完成后被取消，清理已解压文件")
            import shutil
            if os.path.exists(output_path):
                shutil.rmtree(output_path)
            return None
        
        # 7. 验证解压完整性
        task.update_progress(90, "验证解压完整性")
        if not await self._verify_extraction(archive_info, output_path):
            raise Exception("解压验证失败，文件不完整")
        
        # 8. 检查并解压嵌套压缩包
        if self.config.extract.extract_nested_archives:
            task.update_progress(95, "检查嵌套压缩包")
            nested_count = await self._extract_nested_archives(
                output_path, 
                task, 
                max_depth=self.config.extract.max_nested_depth,
                parent_password=success_password  # 传递成功使用的密码给嵌套压缩包
            )
            if nested_count > 0:
                logger.info(f"解压了 {nested_count} 个嵌套压缩包")
        else:
            logger.debug("嵌套压缩包解压已禁用")
        
        return output_path
    
    async def _extract_nested_archives(self, directory: str, task: Task, max_depth: int = 5, current_depth: int = 0, processed_paths: Optional[set] = None, parent_password: Optional[str] = None) -> int:
        """
        递归解压目录中的嵌套压缩包
        
        Args:
            directory: 要检查的目录
            task: 任务对象
            max_depth: 最大递归深度
            current_depth: 当前递归深度
            processed_paths: 已处理的文件路径集合（防止循环）
            parent_password: 外层压缩包使用的密码（优先尝试）
        
        Returns:
            解压的嵌套压缩包数量
        """
        if processed_paths is None:
            processed_paths = set()
        
        # 检查深度限制
        if current_depth >= max_depth:
            logger.warning(f"达到最大嵌套深度 {max_depth}，停止解压嵌套压缩包")
            return 0
        
        # 检查任务状态
        if task.is_cancelled():
            logger.info("任务被取消，停止解压嵌套压缩包")
            return 0
        await task.wait_if_paused()
        
        extracted_count = 0
        archive_extensions = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'}
        
        # 扫描目录中的所有文件
        try:
            for root, dirs, files in os.walk(directory):
                # 检查任务状态
                if task.is_cancelled():
                    break
                await task.wait_if_paused()
                
                for filename in files:
                    file_path = os.path.join(root, filename)
                    
                    # 检查是否已经处理过（防止循环）
                    file_real_path = os.path.realpath(file_path)
                    if file_real_path in processed_paths:
                        logger.debug(f"跳过已处理的文件: {filename}")
                        continue
                    
                    # 检查后缀名或通过魔数检测
                    is_archive = False
                    ext = Path(filename).suffix.lower()
                    
                    if ext in archive_extensions:
                        is_archive = True
                    else:
                        # 通过后缀名无法识别，尝试魔数检测
                        is_archive = await self._detect_by_magic_bytes(file_path) is not None
                    
                    if is_archive:
                        # 检查是否是分卷文件（跳过非首卷）
                        import re
                        part_match = re.search(r'\.part(\d+)\.', filename, re.IGNORECASE)
                        if part_match and int(part_match.group(1)) > 1:
                            continue
                        if re.search(r'\.z\d{2}$', filename, re.IGNORECASE):
                            continue
                        
                        logger.info(f"发现嵌套压缩包: {filename} (深度: {current_depth + 1}, 父密码: {parent_password or '无'})")
                        
                        # 检查任务状态
                        if task.is_cancelled():
                            break
                        await task.wait_if_paused()
                        
                        # 确定解压目标目录
                        # 如果压缩包名是 123.zip，解压到 123/ 目录
                        archive_name = Path(filename).stem
                        nested_output_dir = os.path.join(root, archive_name)
                        
                        # 如果目录已存在，添加序号
                        counter = 1
                        original_output_dir = nested_output_dir
                        while os.path.exists(nested_output_dir):
                            nested_output_dir = f"{original_output_dir}_{counter}"
                            counter += 1
                        
                        os.makedirs(nested_output_dir, exist_ok=True)
                        
                        # 尝试解压嵌套压缩包
                        try:
                            # 首先尝试使用父密码读取压缩包信息
                            nested_archive_info = await self._get_nested_archive_info(file_path, parent_password)
                            
                            if nested_archive_info:
                                task.update_progress(
                                    95, 
                                    f"解压嵌套压缩包 {filename} (层{current_depth + 1})"
                                )
                                
                                # 使用相同的密码策略解压
                                success, nested_success_password = await self._try_extract_nested(
                                    nested_archive_info, 
                                    nested_output_dir, 
                                    task,
                                    parent_password
                                )
                                
                                # 如果失败，尝试从密码库获取密码
                                if not success:
                                    logger.info(f"使用常规密码解压嵌套压缩包失败，尝试从密码库查找密码: {filename}")
                                    vault_passwords = await self._get_passwords_for_archive(file_path)
                                    if vault_passwords:
                                        for pwd in vault_passwords:
                                            if pwd != nested_archive_info.password and pwd != parent_password:
                                                logger.info(f"尝试使用密码库密码解压嵌套压缩包: {filename}")
                                                # 重新获取压缩包信息
                                                new_info = await self._get_nested_archive_info(file_path, pwd)
                                                if new_info:
                                                    success, nested_success_password = await self._try_extract_nested(
                                                        new_info, 
                                                        nested_output_dir, 
                                                        task,
                                                        pwd
                                                    )
                                                    if success:
                                                        nested_archive_info = new_info
                                                        break
                                
                                if success:
                                    logger.info(f"成功解压嵌套压缩包: {filename} (使用密码: {nested_success_password or '无密码'})")
                                    extracted_count += 1
                                    
                                    # 标记为已处理
                                    processed_paths.add(file_real_path)
                                    
                                    # 删除原始的嵌套压缩包文件
                                    try:
                                        os.remove(file_path)
                                        logger.info(f"已删除嵌套压缩包文件: {file_path}")
                                    except Exception as e:
                                        logger.warning(f"删除嵌套压缩包文件失败: {file_path}, 错误: {e}")
                                    
                                    # 递归检查解压出来的目录，传递成功使用的密码
                                    sub_count = await self._extract_nested_archives(
                                        nested_output_dir, 
                                        task, 
                                        max_depth, 
                                        current_depth + 1,
                                        processed_paths,
                                        nested_success_password  # 传递成功使用的密码给下一层
                                    )
                                    extracted_count += sub_count
                                else:
                                    logger.warning(f"无法解压嵌套压缩包: {filename} (已尝试所有密码)")
                                    # 清理失败的解压目录
                                    if os.path.exists(nested_output_dir):
                                        import shutil
                                        shutil.rmtree(nested_output_dir)
                            else:
                                logger.warning(f"无法读取嵌套压缩包内容: {filename}")
                        
                        except Exception as e:
                            logger.error(f"解压嵌套压缩包失败 {filename}: {e}")
                            # 清理失败的解压目录
                            if os.path.exists(nested_output_dir):
                                import shutil
                                shutil.rmtree(nested_output_dir)
        
        except Exception as e:
            logger.error(f"扫描嵌套压缩包时出错: {e}")
        
        return extracted_count
    
    async def _get_nested_archive_info(self, archive_path: str, parent_password: Optional[str] = None) -> Optional[ArchiveInfo]:
        """
        获取嵌套压缩包信息
        尝试所有可能的密码，返回能找到的第一个可用密码
        """
        # 构建密码列表：父密码优先，然后无密码，最后通用密码
        password_list = []
        
        # 1. 优先尝试父密码
        if parent_password:
            password_list.append(parent_password)
        
        # 2. 尝试无密码
        password_list.append("")
        
        # 3. 尝试通用密码
        password_list.extend(self.config.extract.password_list)
        
        # 去重（保持顺序）
        seen = set()
        unique_passwords = []
        for pwd in password_list:
            if pwd not in seen:
                seen.add(pwd)
                unique_passwords.append(pwd)
        
        # 尝试所有密码，找到能读取内容的
        for password in unique_passwords:
            file_list = await self._list_archive_contents(archive_path, password)
            if file_list is not None:
                source = "父密码" if password == parent_password else ("无密码" if password == "" else "通用密码")
                logger.info(f"成功读取嵌套压缩包内容，使用: {source} ({password or '无密码'})")
                return ArchiveInfo(archive_path, file_list, password)
        
        return None
    
    async def _try_extract_nested(self, archive_info: ArchiveInfo, output_path: str, task: Task, parent_password: Optional[str] = None) -> tuple[bool, Optional[str]]:
        """
        尝试解压嵌套压缩包
        尝试所有可能的密码：已知的密码、父密码、无密码、通用密码
        返回 (是否成功, 成功使用的密码)
        """
        # 构建完整的密码列表
        password_list = []
        
        # 1. 首先尝试已知的密码（从 _get_nested_archive_info 获取的）
        if archive_info.password:
            password_list.append((archive_info.password, "已知密码"))
        
        # 2. 尝试父密码（如果和已知密码不同）
        if parent_password and parent_password != archive_info.password:
            password_list.append((parent_password, "父密码"))
        
        # 3. 尝试无密码（如果还没试过）
        if "" != archive_info.password and "" != parent_password:
            password_list.append(("", "无密码"))
        
        # 4. 尝试通用密码（配置中的密码列表）
        for pwd in self.config.extract.password_list:
            if pwd and pwd != archive_info.password and pwd != parent_password:
                password_list.append((pwd, "通用密码"))
        
        logger.info(f"开始尝试解压嵌套压缩包，共 {len(password_list)} 个密码")
        
        for password, source in password_list:
            cmd = [
                self.seven_zip, 'x',
                '-y',  # 自动确认
                '-o' + output_path,  # 输出目录
                archive_info.path
            ]
            
            if password:
                cmd.append(f'-p{password}')
            else:
                cmd.append('-p')  # 空密码
            
            try:
                logger.info(f"尝试解压嵌套压缩包使用: {source} ({password or '无密码'})")
                result = await self._run_7z_command(cmd)
                
                if result.returncode == 0:
                    logger.info(f"嵌套压缩包解压成功，使用: {source} ({password or '无密码'})")
                    # 更新archive_info中的密码，用于传递给下一层
                    archive_info.password = password
                    return True, password
                else:
                    logger.warning(f"密码 {source} ({password or '无密码'}) 解压失败")
                
            except Exception as e:
                logger.warning(f"嵌套压缩包解压尝试失败: {e}")
                continue
        
        logger.error(f"嵌套压缩包解压失败，已尝试所有 {len(password_list)} 个密码")
        return False, None
    
    async def _wait_file_stable(self, file_path: str, task: Optional[Task] = None, max_wait: int = 3600):
        """等待文件大小稳定（文件复制完成检测）"""
        config = self.config.processing
        previous_size = -1
        stable_count = 0
        start_time = asyncio.get_event_loop().time()
        last_progress_time = start_time
        
        logger.info(f"开始等待文件复制完成: {file_path}")
        
        while stable_count < config.file_stable_checks:
            current_time = asyncio.get_event_loop().time()
            
            # 检查总超时
            if current_time - start_time > max_wait:
                raise TimeoutError(f"等待文件复制完成超时 ({max_wait}秒): {file_path}")
            
            # 检查任务是否被取消
            if task and task.is_cancelled():
                logger.info(f"任务在等待文件复制时被取消: {file_path}")
                return
            
            # 检查任务是否暂停
            if task:
                await task.wait_if_paused()
            
            try:
                # 检查文件是否存在
                if not os.path.exists(file_path):
                    await asyncio.sleep(config.file_stable_interval)
                    continue
                
                # 获取文件大小
                current_size = os.path.getsize(file_path)
                
                # 检查文件是否为空或太小（可能是刚开始复制）
                if current_size < 1024:  # 小于1KB认为可能是刚开始复制
                    logger.debug(f"文件太小 ({current_size} bytes)，等待更多数据写入...")
                    await asyncio.sleep(config.file_stable_interval)
                    continue
                
                # 检查文件大小是否稳定
                if current_size == previous_size:
                    stable_count += 1
                    # 尝试打开文件检查是否被锁定
                    try:
                        with open(file_path, 'rb') as f:
                            # 尝试读取文件开头（检查是否可以访问）
                            f.read(1)
                        # 如果成功读取且稳定次数达标，认为文件已复制完成
                        if stable_count >= config.file_stable_checks:
                            logger.info(f"文件复制完成检测通过: {file_path} ({current_size} bytes)")
                            return
                    except (PermissionError, OSError):
                        # 文件仍被锁定，重置稳定计数
                        logger.debug(f"文件仍被锁定，继续等待: {file_path}")
                        stable_count = 0
                else:
                    # 文件大小在变化，正在复制中
                    if stable_count > 0:
                        logger.info(f"文件仍在复制中，当前大小: {current_size} bytes")
                    stable_count = 0
                    last_progress_time = current_time
                
                previous_size = current_size
                
                # 如果长时间没有进度，发出警告
                if current_time - last_progress_time > 60:  # 1分钟没有变化
                    logger.warning(f"文件复制可能已停滞: {file_path}, 当前大小: {current_size} bytes")
                    
            except Exception as e:
                logger.warning(f"等待文件稳定时出错: {e}")
                await asyncio.sleep(config.file_stable_interval)
                continue
            
            await asyncio.sleep(config.file_stable_interval)
    
    async def _repair_extension(self, file_path: str) -> str:
        """修复文件后缀名"""
        if not self.config.extract.auto_repair_extension:
            return file_path
        
        filename = Path(file_path).name
        
        # 跳过自解压文件（.exe）
        if filename.lower().endswith('.exe'):
            logger.info(f"跳过自解压文件后缀名修复: {file_path}")
            return file_path
        
        # 跳过分卷压缩文件
        import re
        if re.search(r'\.part\d+\.(rar|zip|7z)$', filename, re.IGNORECASE):
            logger.info(f"跳过分卷压缩文件后缀名修复: {file_path}")
            return file_path
        
        # 检测真实文件类型
        real_type = await self._detect_real_type(file_path)
        if not real_type:
            logger.warning(f"无法检测文件类型: {file_path}")
            return file_path
        
        # 获取正确的后缀名
        correct_ext = self._get_correct_extension(real_type)
        current_ext = Path(file_path).suffix.lower()
        
        if current_ext != f".{correct_ext}":
            new_path = self._rename_with_extension(file_path, correct_ext)
            logger.info(f"修复后缀名: {file_path} -> {new_path}")
            return new_path
        
        return file_path
    
    async def _detect_real_type(self, file_path: str) -> Optional[str]:
        """检测文件真实类型"""
        # 方法1: 使用 filetype 库（添加重试机制）
        max_retries = 3
        for retry in range(max_retries):
            try:
                kind = filetype.guess(file_path)
                if kind:
                    return kind.extension
                break
            except PermissionError:
                if retry < max_retries - 1:
                    logger.warning(f"文件访问被拒绝，等待后重试 ({retry + 1}/{max_retries}): {file_path}")
                    await asyncio.sleep(2)  # 等待2秒再试
                else:
                    logger.error(f"文件访问被拒绝，跳过 filetype 检测: {file_path}")
        
        # 方法2: 使用 7z 测试
        try:
            result = await self._run_7z_command(['l', file_path])
            if result.returncode == 0:
                # 从输出中检测格式
                output = result.stdout.decode('utf-8', errors='ignore')
                if 'Type = 7z' in output:
                    return '7z'
                elif 'Type = zip' in output:
                    return 'zip'
                elif 'Type = rar' in output:
                    return 'rar'
        except Exception as e:
            logger.error(f"7z检测失败: {e}")
        
        # 方法3: 魔数检测
        magic_result = await self._detect_by_magic_bytes(file_path)
        return magic_result
    
    async def _detect_by_magic_bytes(self, file_path: str) -> Optional[str]:
        """通过魔数检测文件类型"""
        magic_bytes = {
            b'PK\x03\x04': 'zip',
            b'PK\x05\x06': 'zip',  # 空zip
            b'PK\x07\x08': 'zip',  # zip64
            b'Rar!': 'rar',
            b'7z\xBC\xAF\x27\x1C': '7z',
        }
        
        # 添加重试机制
        max_retries = 3
        for retry in range(max_retries):
            try:
                with open(file_path, 'rb') as f:
                    header = f.read(8)
                    for magic, file_type in magic_bytes.items():
                        if header.startswith(magic):
                            return file_type
                break
            except PermissionError:
                if retry < max_retries - 1:
                    logger.warning(f"魔数检测文件访问被拒绝，等待后重试 ({retry + 1}/{max_retries}): {file_path}")
                    await asyncio.sleep(2)
                else:
                    logger.error(f"魔数检测文件访问被拒绝: {file_path}")
            except Exception as e:
                logger.error(f"魔数检测失败: {e}")
                break
        
        return None
    
    def _get_correct_extension(self, file_type: str) -> str:
        """获取正确的后缀名"""
        extension_map = {
            'zip': 'zip',
            'rar': 'rar',
            '7z': '7z',
            'gz': 'gz',
            'bz2': 'bz2',
            'xz': 'xz',
        }
        return extension_map.get(file_type, file_type)
    
    def _rename_with_extension(self, file_path: str, new_ext: str) -> str:
        """重命名文件并修改后缀"""
        path = Path(file_path)
        new_name = f"{path.stem}.{new_ext}"
        new_path = path.parent / new_name
        
        # 如果目标已存在，添加序号
        counter = 1
        while new_path.exists():
            new_name = f"{path.stem}({counter}).{new_ext}"
            new_path = path.parent / new_name
            counter += 1
        
        os.rename(file_path, new_path)
        return str(new_path)
    
    def _detect_volume_set(self, file_path: str) -> Optional['VolumeSet']:
        """检测是否是分卷压缩包"""
        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        
        # 分卷模式识别
        patterns = [
            (r'\.part(\d+)\.(rar|zip|7z)$', 'part'),
            (r'\.z(\d{2})$', 'zip_volume'),
            (r'\.(\d{3})$', '7z_volume'),
            (r'\.(\d{2})$', 'generic'),
        ]
        
        for pattern, vtype in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                base_name = re.sub(pattern, '', filename)
                volumes = self._find_all_volumes(directory, base_name, pattern)
                if len(volumes) > 1:
                    return VolumeSet(base_name, volumes, vtype)
        
        return None
    
    def _find_all_volumes(self, directory: str, base_name: str, pattern: str) -> List[str]:
        """查找所有分卷文件"""
        volumes = []
        for file in os.listdir(directory):
            if file.startswith(base_name) and re.search(pattern, file, re.IGNORECASE):
                volumes.append(os.path.join(directory, file))
        return sorted(volumes)
    
    async def _wait_for_complete_set(self, volume_set: 'VolumeSet', task: Optional[Task] = None, max_wait: int = 3600) -> bool:
        """等待分卷组完整"""
        start_time = asyncio.get_event_loop().time()
        check_interval = 5
        
        while asyncio.get_event_loop().time() - start_time < max_wait:
            # 检查任务是否被取消
            if task and task.is_cancelled():
                logger.info(f"任务在等待分卷组时被取消")
                return False
            
            # 检查任务是否暂停
            if task:
                await task.wait_if_paused()
            
            all_stable = True
            for volume in volume_set.volumes:
                if not os.path.exists(volume):
                    all_stable = False
                    break
                if not await self._is_file_stable_quick(volume):
                    all_stable = False
                    break
            
            if all_stable:
                return True
            
            await asyncio.sleep(check_interval)
        
        return False
    
    async def _is_file_stable_quick(self, file_path: str) -> bool:
        """快速检查文件是否稳定（只检查一次）"""
        try:
            size1 = os.path.getsize(file_path)
            await asyncio.sleep(2)
            size2 = os.path.getsize(file_path)
            return size1 == size2
        except OSError:
            return False
    
    async def _get_passwords_for_archive(self, archive_path: str) -> List[str]:
        """从密码库查找适合该压缩包的密码列表
        
        返回按优先级排序的密码列表：
        1. RJ号匹配的密码
        2. 文件名匹配的密码
        3. 通用的密码（无RJ号和文件名）
        """
        from ..models.database import PasswordEntry, get_db
        from pathlib import Path
        
        filename = Path(archive_path).name
        
        # 提取RJ号
        rj_match = re.search(r'[RVB]J(\d{6}|\d{8})(?!\d)', filename, re.IGNORECASE)
        rjcode = rj_match.group(0).upper() if rj_match else None
        
        db = next(get_db())
        passwords = []
        
        try:
            # 1. 首先尝试精确匹配RJ号
            if rjcode:
                entries = db.query(PasswordEntry).filter(PasswordEntry.rjcode == rjcode).all()
                for entry in entries:
                    passwords.append(entry.password)
                    logger.info(f"找到RJ号匹配的密码: {rjcode}")
            
            # 2. 其次尝试文件名匹配
            entries = db.query(PasswordEntry).filter(PasswordEntry.filename == filename).all()
            for entry in entries:
                if entry.password not in passwords:
                    passwords.append(entry.password)
                    logger.info(f"找到文件名匹配的密码: {filename}")
            
            # 3. 最后添加通用密码（无RJ号和文件名的密码）
            generic_entries = db.query(PasswordEntry).filter(
                PasswordEntry.rjcode.is_(None),
                PasswordEntry.filename.is_(None)
            ).all()
            for entry in generic_entries:
                if entry.password not in passwords:
                    passwords.append(entry.password)
            
            return passwords
        finally:
            db.close()
    
    async def _record_password_usage(self, password: str, archive_path: str):
        """记录密码使用情况"""
        from ..models.database import PasswordEntry, get_db
        
        db = next(get_db())
        try:
            # 查找并更新使用记录
            entry = db.query(PasswordEntry).filter(PasswordEntry.password == password).first()
            if entry:
                # 使用 SQL 表达式更新，避免类型问题
                from sqlalchemy import func
                db.query(PasswordEntry).filter(PasswordEntry.id == entry.id).update({
                    'use_count': PasswordEntry.use_count + 1,
                    'last_used_at': func.now()
                })
                db.commit()
                logger.debug(f"记录密码使用: {entry.rjcode or entry.filename or '通用密码'}, 使用次数+1")
        except Exception as e:
            logger.warning(f"记录密码使用情况失败: {e}")
        finally:
            db.close()
    
    async def _get_archive_info(self, archive_path: str) -> Optional[ArchiveInfo]:
        """获取压缩包信息（文件列表、大小等）
        
        注意：这里只获取文件列表，不解压。真正能解压的密码在 _try_extract 中确定。
        为了不限制解压时的密码选择，这里尝试找一个能读取内容的密码即可。
        """
        # 从密码库查找所有相关密码
        vault_passwords = await self._get_passwords_for_archive(archive_path)
        
        # 构建密码列表：密码库密码优先，然后是配置中的默认密码
        password_list = []
        password_list.extend(vault_passwords)  # 密码库密码
        password_list.append("")  # 无密码
        password_list.extend(self.config.extract.password_list)  # 默认密码
        
        # 去重（保持顺序）
        seen = set()
        unique_passwords = []
        for pwd in password_list:
            if pwd not in seen:
                seen.add(pwd)
                unique_passwords.append(pwd)
        
        for password in unique_passwords:
            file_list = await self._list_archive_contents(archive_path, password)
            if file_list is not None:
                source = "密码库" if password in vault_passwords else ("默认" if password in self.config.extract.password_list else "无")
                logger.info(f"成功读取压缩包内容，使用密码来源: {source} ({password or '无密码'})")
                # 注意：这里返回的 password 只是能读取内容的密码，不一定能解压
                # 真正能解压的密码会在 _try_extract 中更新
                return ArchiveInfo(archive_path, file_list, password)
        
        return None
    
    async def _list_archive_contents(self, archive_path: str, password: str = "") -> Optional[List[Dict]]:
        """列出压缩包内容"""
        cmd = [self.seven_zip, 'l', '-ba', archive_path]
        if password:
            # Windows下使用 -p密码 格式（无空格），与7z官方用法一致
            cmd.append(f'-p{password}')
        else:
            cmd.append('-p')  # 空密码
        
        try:
            result = await self._run_7z_command(cmd)
            if result.returncode != 0:
                return None
            
            # 使用gbk解码，与原来代码一致
            return self._parse_7z_list_output(result.stdout.decode('gbk', errors='ignore'))
        except Exception as e:
            logger.error(f"列出压缩包内容失败: {e}")
            return None
    
    def _parse_7z_list_output(self, output: str) -> List[Dict]:
        """解析7z列表输出"""
        files = []
        # 7z l -ba 输出格式: 日期 时间 属性 大小 压缩大小 文件名
        pattern = r'^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+([D.][R.][H.][S.][A.])\s+(\d+)\s+(\d+)?\s+(.+)$'
        
        for line in output.strip().split('\n'):
            match = re.match(pattern, line)
            if match:
                size = int(match.group(4))
                name = match.group(6)
                files.append({
                    'name': name,
                    'size': size,
                    'is_dir': 'D' in match.group(3)
                })
        
        return files
    
    async def _try_extract(self, archive_info: ArchiveInfo, output_path: str, task: Task) -> tuple[bool, Optional[str]]:
        """尝试解压，返回 (是否成功, 成功使用的密码)"""
        # 再次从密码库查找所有相关密码（以防用户在处理过程中添加了新密码）
        vault_passwords = await self._get_passwords_for_archive(archive_info.path)
        
        # 构建密码列表：密码库密码优先，然后是已知密码，最后是默认密码
        password_list = []
        password_list.extend(vault_passwords)  # 密码库密码
        if archive_info.password and archive_info.password not in password_list:
            password_list.append(archive_info.password)
        password_list.append("")  # 无密码
        password_list.extend(self.config.extract.password_list)  # 默认密码
        
        # 去重（保持顺序）
        seen = set()
        unique_passwords = []
        for pwd in password_list:
            if pwd not in seen:
                seen.add(pwd)
                unique_passwords.append(pwd)
        
        for password in unique_passwords:
            cmd = [
                self.seven_zip, 'x',
                '-y',  # 自动确认
                '-o' + output_path,  # 输出目录
                archive_info.path
            ]
            
            if password:
                # Windows下使用 -p密码 格式（无空格）
                cmd.append(f'-p{password}')
            else:
                cmd.append('-p')  # 空密码
            
            try:
                password_source = "密码库" if password in vault_passwords else ("已知" if password == archive_info.password else "默认")
                task.update_progress(40, f"尝试解压 (密码来源: {password_source})")
                result = await self._run_7z_command(cmd)
                
                if result.returncode == 0:
                    # 记录成功使用的密码
                    if password and password in vault_passwords:
                        await self._record_password_usage(password, archive_info.path)
                    # 更新 archive_info 中的密码，用于传递给嵌套压缩包
                    archive_info.password = password
                    logger.info(f"解压成功，使用{password_source}密码: {password or '无密码'}")
                    return True, password
                
            except Exception as e:
                logger.warning(f"解压尝试失败: {e}")
                continue
        
        return False, None
    
    async def _verify_extraction(self, archive_info: ArchiveInfo, output_path: str) -> bool:
        """验证解压完整性"""
        if not self.config.extract.verify_after_extract:
            return True
        
        missing_files = []
        size_mismatch_files = []
        
        for expected in archive_info.file_list:
            if expected.get('is_dir'):
                continue
            
            # 尝试多种可能的路径（处理编码问题）
            possible_paths = [
                os.path.join(output_path, expected['name']),  # 原始路径
                os.path.join(output_path, expected['name'].encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')),  # UTF-8
                os.path.join(output_path, expected['name'].encode('cp932', errors='ignore').decode('cp932', errors='ignore')),  # Shift_JIS
            ]
            
            found = False
            for actual_path in set(possible_paths):  # 去重
                if os.path.exists(actual_path):
                    found = True
                    actual_size = os.path.getsize(actual_path)
                    if actual_size != expected['size']:
                        size_mismatch_files.append({
                            'name': expected['name'],
                            'expected': expected['size'],
                            'actual': actual_size
                        })
                    break
            
            if not found:
                missing_files.append(expected['name'])
        
        # 如果有文件缺失，记录警告但不失败（可能是编码问题）
        if missing_files:
            logger.warning(f"以下文件可能因编码问题无法验证: {missing_files[:5]}")
            if len(missing_files) > 5:
                logger.warning(f"... 还有 {len(missing_files) - 5} 个文件")
        
        if size_mismatch_files:
            for mismatch in size_mismatch_files[:5]:
                logger.warning(f"文件大小不匹配: {mismatch['name']} (期望: {mismatch['expected']}, 实际: {mismatch['actual']})")
        
        # 只要没有大小不匹配，就认为是成功的
        # （缺失文件可能是编码问题导致的误报）
        if size_mismatch_files:
            logger.error(f"有 {len(size_mismatch_files)} 个文件大小不匹配，解压可能不完整")
            return False
        
        return True
    
    def _cleanup_extract_path(self, output_path: str):
        """清理解压路径，包括所有残留文件和目录"""
        import shutil
        import time
        
        if not os.path.exists(output_path):
            return
        
        # 尝试3次删除
        for attempt in range(3):
            try:
                shutil.rmtree(output_path)
                logger.info(f"已清理解压目录: {output_path}")
                return
            except Exception as e:
                if attempt < 2:
                    logger.warning(f"清理尝试 {attempt + 1} 失败，1秒后重试: {output_path}")
                    time.sleep(1)
                else:
                    logger.error(f"清理解压目录失败: {output_path}, {e}")
    
    async def _run_7z_command(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """运行7z命令"""
        # 记录命令（显示密码用于调试）
        logger.info(f"执行7z命令: {' '.join(cmd)}")
        
        try:
            # 使用 asyncio.create_subprocess_exec 直接执行（与原来代码一致）
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"7z命令执行失败，返回码: {process.returncode}")
                # 使用 gbk 解码错误输出（与原来代码一致）
                try:
                    err_text = stderr.decode('gbk', errors='ignore')
                    logger.error(f"错误输出: {err_text[:200]}")
                except:
                    pass
            
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=process.returncode if process.returncode is not None else -1,
                stdout=stdout,
                stderr=stderr
            )
        except Exception as e:
            logger.error(f"执行7z命令异常: {e}")
            raise

class VolumeSet:
    """分卷组"""
    def __init__(self, base_name: str, volumes: List[str], volume_type: str):
        self.base_name = base_name
        self.volumes = volumes
        self.type = volume_type
        self.is_complete = False
