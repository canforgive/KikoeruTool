import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
import logging

from ..config.settings import get_config
from ..core.task_engine import Task

logger = logging.getLogger(__name__)

class RenameService:
    """重命名服务"""
    
    def __init__(self):
        self.config = get_config()
    
    async def rename(self, path: str, task: Task):
        """
        重命名文件夹
        """
        metadata = task.task_metadata
        logger.info(f"重命名服务 - 原始路径: {path}")
        logger.info(f"重命名服务 - 任务元数据: {metadata}")

        if not metadata:
            raise Exception("缺少元数据，无法重命名")

        if not metadata.get('rjcode'):
            raise Exception(f"元数据中缺少RJ号，无法重命名。可用字段: {list(metadata.keys())}")
        
        task.update_progress(60, "重命名文件夹")

        # 生成新名称
        new_name = self._compile_name(metadata)
        logger.info(f"重命名服务 - 生成的新名称: {new_name}")
        
        # 清理非法字符
        new_name = self._sanitize_filename(new_name)
        
        # 获取目标路径
        dir_path = Path(path)
        parent = dir_path.parent
        new_path = parent / new_name
        
        # 如果名称相同，跳过
        if dir_path.name == new_name:
            logger.info(f"重命名服务 - 名称相同，跳过重命名: {new_name}")
            return path
        
        # 处理重名
        counter = 1
        original_new_path = new_path
        while new_path.exists():
            new_name = f"{original_new_path.name}({counter})"
            new_path = parent / new_name
            counter += 1
        
        # 执行重命名
        shutil.move(str(dir_path), str(new_path))
        logger.info(f"重命名: {dir_path} -> {new_path}")
        
        return str(new_path)
    
    def _flatten_single_subfolder(self, path: str) -> str:
        """
        扁平化单一层级文件夹
        递归检查所有子文件夹，如果某个文件夹只有一个子文件夹（没有文件或其他内容），
        则将子文件夹内容移出。支持配置扁平化深度。
        """
        root_path = Path(path)
        max_depth = self.config.rename.flatten_depth

        def flatten_single_path(current_path: Path, current_depth: int) -> bool:
            """
            对单个路径进行扁平化，返回是否执行了扁平化
            current_depth: 当前已经扁平化的层数
            """
            if current_depth >= max_depth:
                return False

            if not current_path.is_dir():
                return False

            try:
                # 获取当前目录的所有内容
                items = list(current_path.iterdir())

                # 如果只有一个项目且是文件夹，则扁平化
                if len(items) == 1 and items[0].is_dir():
                    subfolder = items[0]
                    logger.info(f"扁平化 (层 {current_depth + 1}/{max_depth}): {current_path.name} 只有一个子文件夹 {subfolder.name}，正在合并...")

                    # 创建临时路径
                    temp_path = current_path.parent / f"{current_path.name}_temp_{os.urandom(4).hex()}"

                    # 先将子文件夹移动到临时位置
                    shutil.move(str(subfolder), str(temp_path))

                    # 删除空的原文件夹
                    current_path.rmdir()

                    # 将临时文件夹重命名为原文件夹名
                    shutil.move(str(temp_path), str(current_path))

                    logger.info(f"扁平化完成 (层 {current_depth + 1}): {current_path}")

                    # 继续检查是否还需要扁平化（同一链条继续，深度+1）
                    flatten_single_path(current_path, current_depth + 1)
                    return True
                return False

            except Exception as e:
                logger.error(f"扁平化文件夹失败 {current_path}: {e}")
                return False

        def flatten_recursive(current_path: Path) -> None:
            """
            递归遍历所有文件夹，对每个文件夹尝试扁平化
            每个分支的扁平化深度独立计算
            """
            if not current_path.is_dir():
                return

            try:
                # 首先尝试扁平化当前路径（从深度0开始）
                flatten_single_path(current_path, 0)

                # 然后递归处理所有子文件夹
                items = list(current_path.iterdir())
                for item in items:
                    if item.is_dir():
                        flatten_recursive(item)

            except Exception as e:
                logger.error(f"递归扁平化失败 {current_path}: {e}")

        # 从根目录开始递归扁平化
        flatten_recursive(root_path)

        return str(root_path)

    def remove_empty_folders(self, path: str, remove_root: bool = False) -> None:
        """
        递归移除空文件夹
        :param path: 要处理的目录路径
        :param remove_root: 是否移除根目录（如果为空），默认为False保留根目录
        """
        if not os.path.isdir(path):
            return

        # 先递归处理子目录
        try:
            items = list(Path(path).iterdir())
        except Exception as e:
            logger.warning(f"无法读取目录内容 {path}: {e}")
            return

        for item in items:
            if item.is_dir():
                self.remove_empty_folders(str(item), remove_root=True)

        # 重新检查当前目录是否为空
        try:
            items = list(Path(path).iterdir())
            if len(items) == 0:
                if remove_root:
                    try:
                        Path(path).rmdir()
                        logger.info(f"移除空文件夹: {path}")
                    except Exception as e:
                        logger.warning(f"移除空文件夹失败 {path}: {e}")
        except Exception as e:
            logger.warning(f"检查空文件夹失败 {path}: {e}")
    
    def _compile_name(self, metadata: dict) -> str:
        """根据模板编译名称"""
        template = self.config.rename.template
        logger.info(f"[RENAME] 原始模板: '{template}' (长度: {len(template)})")
        
        # 替换变量
        name = template
        rjcode = metadata.get('rjcode', '')
        work_name = metadata.get('work_name', '')
        maker_id = metadata.get('maker_id', '')
        maker_name = metadata.get('maker_name', '')
        
        logger.info(f"[RENAME] 替换前 - rjcode='{rjcode}', work_name='{work_name[:30]}...'")
        
        name = name.replace('{rjcode}', rjcode)
        logger.info(f"[RENAME] 替换rjcode后: '{name}'")
        
        name = name.replace('{work_name}', work_name)
        logger.info(f"[RENAME] 替换work_name后: '{name}'")
        
        name = name.replace('{maker_id}', maker_id)
        name = name.replace('{maker_name}', maker_name)
        
        # 日期
        if '{release_date}' in name:
            date_str = metadata.get('release_date', '')
            if date_str:
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    name = name.replace('{release_date}', date_obj.strftime(self.config.rename.date_format))
                except:
                    name = name.replace('{release_date}', '')
            else:
                name = name.replace('{release_date}', '')
        
        # CV列表
        if '{cvs}' in name:
            cvs = metadata.get('cvs', [])
            if cvs:
                cv_str = self.config.rename.delimiter.join(cvs)
                cv_str = f"{self.config.rename.cv_list_left}{cv_str}{self.config.rename.cv_list_right}"
                name = name.replace('{cvs}', cv_str)
            else:
                name = name.replace('{cvs}', '')
        
        # 标签列表
        if '{tags}' in name:
            tags = metadata.get('tags', [])
            if tags:
                # 限制标签数量
                tags = tags[:self.config.rename.tags_max_number]
                tag_str = self.config.rename.delimiter.join(tags)
                name = name.replace('{tags}', tag_str)
            else:
                name = name.replace('{tags}', '')
        
        # 移除work_name中的方括号内容
        if self.config.rename.exclude_square_brackets:
            name = re.sub(r'【.*?】', '', name)
        
        return name.strip()
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名中的非法字符"""
        # Windows保留字符: < > : " / \ | ? *
        reserved_chars = r'[<>"/\\|?*]'
        
        if self.config.rename.illegal_char_to_full_width:
            # 转换为全角字符
            replace_map = {
                '<': '＜', '>': '＞', ':': '：', '"': '＂',
                '/': '／', '\\': '＼', '|': '｜', '?': '？', '*': '＊'
            }
            for char, replacement in replace_map.items():
                filename = filename.replace(char, replacement)
        else:
            # 直接移除
            filename = re.sub(reserved_chars, '', filename)
        
        # 移除首尾空格和点
        filename = filename.strip(' .')
        
        # 限制长度
        if len(filename) > 200:
            filename = filename[:200]
        
        return filename
