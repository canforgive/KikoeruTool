"""
改进的查重服务 - 支持关联作品检测和 Kikoeru 服务器查重
参考 VoiceLinks 的 SearchResult 和 LinkedWorks 实现
"""
import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import os

from ..models.database import LibrarySnapshot, ConflictWork, get_db
from ..core.dlsite_service import get_dlsite_service, LinkedWork
from ..core.kikoeru_duplicate_service import (
    get_kikoeru_service, 
    KikoeruCheckResult,
    KikoeruDuplicateService
)
from ..config.settings import get_config

logger = logging.getLogger(__name__)


@dataclass
class DuplicateCheckResult:
    """查重结果"""
    is_duplicate: bool = False
    direct_duplicate: Optional[Dict] = None  # 直接重复（相同 RJ 号）
    linked_works_found: List[Dict] = field(default_factory=list)  # 发现的关联作品
    conflict_type: str = "NONE"  # DUPLICATE, LINKED_WORK, LANGUAGE_VARIANT, MULTIPLE_VERSIONS
    related_rjcodes: List[str] = field(default_factory=list)  # 所有关联的 RJ 号
    analysis_info: Dict = field(default_factory=dict)  # 详细的分析信息
    kikoeru_result: Optional[KikoeruCheckResult] = None  # Kikoeru 服务器查重结果


@dataclass
class LinkedWorkInLibrary:
    """库中发现的关联作品"""
    rjcode: str
    work_type: str  # original, parent, child
    lang: str
    folder_path: str
    folder_size: int
    file_count: int
    work_name: str = ""
    is_in_library: bool = True


class EnhancedDuplicateService:
    """增强的查重服务 - 支持本地查重和 Kikoeru 服务器查重"""
    
    def __init__(self):
        self.config = get_config()
        self.dlsite_service = get_dlsite_service()
        self.kikoeru_service = get_kikoeru_service()
    
    async def check_duplicate_enhanced(
        self, 
        rjcode: str, 
        check_linked_works: bool = True,
        cue_languages: List[str] = None
    ) -> DuplicateCheckResult:
        """
        改进的查重检测
        
        Args:
            rjcode: 要检查的 RJ 号
            check_linked_works: 是否检查关联作品
            cue_languages: 需要检查的语言版本列表
        
        返回:
            DuplicateCheckResult: 详细的查重结果
        """
        if cue_languages is None:
            cue_languages = ['CHI_HANS', 'CHI_HANT', 'ENG']
        
        result = DuplicateCheckResult()
        result.related_rjcodes = [rjcode]
        
        # 1. 首先检查直接重复（相同 RJ 号）
        direct_dup = await self._check_direct_duplicate(rjcode)
        if direct_dup:
            result.is_duplicate = True
            result.direct_duplicate = direct_dup
            result.conflict_type = "DUPLICATE"
            logger.info(f"发现直接重复: {rjcode} -> {direct_dup['path']}")
            return result
        
        # 2. 检查关联作品（如果需要）
        if check_linked_works:
            try:
                # 获取作品的完整关联链
                linked_works = await self.dlsite_service.get_full_linkage(rjcode, cue_languages)
                
                if len(linked_works) > 1:
                    logger.info(f"发现关联作品链 {rjcode}: {list(linked_works.keys())}")
                    
                    # 检查这些关联作品是否在库中
                    found_in_library = await self._check_linked_works_in_library(linked_works, rjcode)
                    
                    if found_in_library:
                        result.is_duplicate = True
                        result.linked_works_found = [
                            {
                                'rjcode': w.rjcode,
                                'work_type': w.work_type,
                                'lang': w.lang,
                                'path': w.folder_path,
                                'size': w.folder_size,
                                'work_name': w.work_name
                            }
                            for w in found_in_library
                        ]
                        result.related_rjcodes = list(linked_works.keys())
                        
                        # 确定冲突类型
                        if len(found_in_library) == 1 and found_in_library[0].work_type == 'original':
                            result.conflict_type = "LINKED_WORK_ORIGINAL"
                        elif any(w.work_type == 'parent' for w in found_in_library):
                            result.conflict_type = "LINKED_WORK_TRANSLATION"
                        elif any(w.work_type == 'child' for w in found_in_library):
                            result.conflict_type = "LINKED_WORK_CHILD"
                        else:
                            result.conflict_type = "LINKED_WORK"
                        
                        # 生成详细的分析信息
                        result.analysis_info = self._analyze_linked_works(
                            rjcode, linked_works, found_in_library
                        )
                        
                        logger.info(
                            f"发现关联作品冲突: {rjcode}, 类型={result.conflict_type}, "
                            f"发现 {len(found_in_library)} 个关联作品"
                        )
            
            except Exception as e:
                logger.error(f"检查关联作品失败 {rjcode}: {e}")
        
        # 3. 检查 Kikoeru 服务器（如果启用）
        try:
            kikoeru_config = self.config.get('kikoeru_server', {})
            if kikoeru_config.get('enabled', False):
                logger.debug(f"正在查询 Kikoeru 服务器: {rjcode}")
                kikoeru_result = await self.kikoeru_service.check_duplicate(rjcode)
                result.kikoeru_result = kikoeru_result
                
                if kikoeru_result.is_found:
                    logger.info(f"✓ Kikoeru 服务器找到作品: {rjcode} - {kikoeru_result.title}")
                    # 如果本地未发现重复但 Kikoeru 中有，可以标记为外部库存在
                    if not result.is_duplicate:
                        result.analysis_info['in_kikoeru_server'] = {
                            'title': kikoeru_result.title,
                            'circle': kikoeru_result.circle_name,
                            'tags': kikoeru_result.tags
                        }
                else:
                    logger.debug(f"✗ Kikoeru 服务器未找到: {rjcode}")
        except Exception as e:
            logger.error(f"Kikoeru 服务器查重失败 {rjcode}: {e}")
        
        return result
    
    async def _check_direct_duplicate(self, rjcode: str) -> Optional[Dict]:
        """检查是否存在直接重复（相同 RJ 号）"""
        db = next(get_db())
        try:
            # 从数据库查询
            snapshot = db.query(LibrarySnapshot).filter(
                LibrarySnapshot.rjcode == rjcode
            ).first()
            
            if snapshot:
                folder_path = str(snapshot.folder_path)
                if os.path.exists(folder_path):
                    return {
                        'rjcode': rjcode,
                        'path': folder_path,
                        'size': snapshot.folder_size,
                        'file_count': snapshot.file_count
                    }
                else:
                    # 路径不存在，清理过期记录
                    logger.warning(f"清理过期记录: {rjcode}")
                    db.delete(snapshot)
                    db.commit()
            
            # 如果没有数据库记录，扫描库存目录
            library_path = Path(self.config.storage.library_path)
            for folder in library_path.rglob('*'):
                if folder.is_dir() and rjcode in folder.name:
                    return {
                        'rjcode': rjcode,
                        'path': str(folder),
                        'size': self._get_folder_size(str(folder)),
                        'file_count': self._get_file_count(str(folder))
                    }
            
            return None
        finally:
            db.close()
    
    async def _check_linked_works_in_library(
        self, 
        linked_works: Dict[str, LinkedWork], 
        exclude_rjcode: str
    ) -> List[LinkedWorkInLibrary]:
        """
        检查关联作品是否在库中
        
        返回:
            List[LinkedWorkInLibrary]: 在库中找到的关联作品列表（不包括当前检查的 RJ）
        """
        found = []
        db = next(get_db())
        
        try:
            for workno, linked_work in linked_works.items():
                # 跳过当前检查的 RJ 号
                if workno == exclude_rjcode:
                    continue
                
                # 检查数据库
                snapshot = db.query(LibrarySnapshot).filter(
                    LibrarySnapshot.rjcode == workno
                ).first()
                
                if snapshot:
                    folder_path = str(snapshot.folder_path)
                    if os.path.exists(folder_path):
                        # 获取作品信息
                        work_info = await self.dlsite_service.get_work_info(workno)
                        
                        found.append(LinkedWorkInLibrary(
                            rjcode=workno,
                            work_type=linked_work.work_type,
                            lang=linked_work.lang,
                            folder_path=folder_path,
                            folder_size=snapshot.folder_size,
                            file_count=snapshot.file_count,
                            work_name=work_info.get('title', '') if work_info else ""
                        ))
                        logger.debug(f"发现库中关联作品: {workno} ({linked_work.work_type})")
                else:
                    # 扫描目录
                    library_path = Path(self.config.storage.library_path)
                    for folder in library_path.rglob('*'):
                        if folder.is_dir() and workno in folder.name:
                            work_info = await self.dlsite_service.get_work_info(workno)
                            
                            found.append(LinkedWorkInLibrary(
                                rjcode=workno,
                                work_type=linked_work.work_type,
                                lang=linked_work.lang,
                                folder_path=str(folder),
                                folder_size=self._get_folder_size(str(folder)),
                                file_count=self._get_file_count(str(folder)),
                                work_name=work_info.get('title', '') if work_info else ""
                            ))
                            break
            
            return found
        finally:
            db.close()
    
    def _analyze_linked_works(
        self,
        current_rjcode: str,
        linked_works: Dict[str, LinkedWork],
        found_in_library: List[LinkedWorkInLibrary]
    ) -> Dict:
        """
        分析关联作品关系，生成详细的分析报告
        
        返回:
            Dict: 包含以下字段:
                - has_original: 是否有原作品
                - has_parent: 是否有翻译父级
                - has_child: 是否有翻译子级
                - has_translation: 是否有翻译版本
                - lang_stats: 各语言版本统计
                - library_summary: 库中已存在的作品摘要
        """
        current_work = linked_works.get(current_rjcode, LinkedWork(workno=current_rjcode, work_type='original'))
        
        analysis = {
            'current_work': {
                'rjcode': current_rjcode,
                'work_type': current_work.work_type,
                'lang': current_work.lang
            },
            'has_original': False,
            'has_parent': False,
            'has_child': False,
            'has_translation': False,
            'lang_stats': {},
            'library_summary': []
        }
        
        # 统计各类型
        for rj, work in linked_works.items():
            if work.work_type == 'original':
                analysis['has_original'] = True
            elif work.work_type == 'parent':
                analysis['has_parent'] = True
            elif work.work_type == 'child':
                analysis['has_child'] = True
            
            if work.work_type != 'original':
                analysis['has_translation'] = True
            
            # 统计语言
            lang = work.lang
            analysis['lang_stats'][lang] = analysis['lang_stats'].get(lang, 0) + 1
        
        # 库中作品摘要
        for found in found_in_library:
            analysis['library_summary'].append({
                'rjcode': found.rjcode,
                'work_type': found.work_type,
                'lang': found.lang,
                'work_name': found.work_name,
                'path': found.folder_path
            })
        
        return analysis
    
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
    
    def _get_lang_priority(self, lang: str) -> int:
        """获取语言优先级，数字越小优先级越高"""
        priorities = {
            'CHI_HANS': 1,  # 简体中文 - 最高优先级
            'CHI_HANT': 2,  # 繁体中文
            'JPN': 3,       # 日文
            'ENG': 4,       # 英文
            'KO_KR': 5,     # 韩语
            'SPA': 6,       # 西班牙语
            'FRE': 7,       # 法语
            'GER': 8,       # 德语
            'RUS': 9,       # 俄语
            'THA': 10,      # 泰语
            'VIE': 11,      # 越南语
            'ITA': 12,      # 意大利语
            'POR': 13,      # 葡萄牙语
        }
        return priorities.get(lang, 99)  # 未知语言最低优先级
    
    def _get_lang_name(self, lang: str) -> str:
        """获取语言名称"""
        names = {
            'CHI_HANS': '简体中文',
            'CHI_HANT': '繁体中文',
            'JPN': '日文',
            'ENG': '英文',
            'KO_KR': '韩语',
            'SPA': '西班牙语',
            'FRE': '法语',
            'GER': '德语',
            'RUS': '俄语',
            'THA': '泰语',
            'VIE': '越南语',
            'ITA': '意大利语',
            'POR': '葡萄牙语',
        }
        return names.get(lang, lang)
    
    async def get_conflict_resolution_options(
        self, 
        check_result: DuplicateCheckResult
    ) -> List[Dict]:
        """
        根据查重结果获取推荐的冲突解决选项
        
        智能推荐逻辑：
        1. 简体中文 > 繁体中文 > 日文 > 其他语言
        2. 如果新版语言优先级更高，推荐保留新版
        3. 如果旧版语言优先级更高，推荐抛弃新版
        4. 直接重复时，根据文件大小判断
        
        返回:
            List[Dict]: 推荐的解决选项列表
        """
        options = []
        
        if check_result.conflict_type == "DUPLICATE":
            # 直接重复 - 比较文件大小
            existing = check_result.direct_duplicate
            
            if existing:
                # 获取当前文件夹大小（如果在处理的是文件夹）
                # 这里简化处理，默认推荐保留新版（通常新版更好）
                options = [
                    {
                        'action': 'KEEP_NEW',
                        'label': '保留新版',
                        'description': '删除旧版本，保留新版本（通常新版质量更好）',
                        'recommend': True
                    },
                    {
                        'action': 'KEEP_OLD',
                        'label': '保留旧版',
                        'description': '删除新版本，保留现有版本（如果对当前版本满意）'
                    },
                    {
                        'action': 'MERGE',
                        'label': '合并保留',
                        'description': '保留两个版本，新版本添加编号后缀（如 RJxxx_v2）'
                    },
                    {
                        'action': 'SKIP',
                        'label': '抛弃新版',
                        'description': '删除新版本，不做任何更改（跳过处理）'
                    }
                ]
            else:
                options = [
                    {
                        'action': 'SKIP',
                        'label': '抛弃新版',
                        'description': '删除新版本，不做任何更改',
                        'recommend': True
                    }
                ]
        
        elif check_result.conflict_type in ["LINKED_WORK_ORIGINAL", "LINKED_WORK_TRANSLATION", "LINKED_WORK_CHILD"]:
            # 关联作品冲突 - 根据语言优先级推荐
            analysis = check_result.analysis_info
            current_lang = analysis['current_work']['lang']
            current_priority = self._get_lang_priority(current_lang)
            
            # 获取库中已存在的作品信息
            existing_works = check_result.linked_works_found
            
            if existing_works:
                # 找出优先级最高的已存在作品
                best_existing = min(existing_works, 
                                   key=lambda w: self._get_lang_priority(w.get('lang', 'JPN')))
                existing_priority = self._get_lang_priority(best_existing.get('lang', 'JPN'))
                existing_lang_name = self._get_lang_name(best_existing.get('lang', 'JPN'))
                
                # 根据优先级决定推荐
                if current_priority < existing_priority:
                    # 新版优先级更高（数字更小）
                    recommend_action = 'KEEP_NEW'
                    recommend_desc = f'新版语言({self._get_lang_name(current_lang)})优先级更高，建议保留'
                elif current_priority > existing_priority:
                    # 旧版优先级更高
                    recommend_action = 'SKIP'
                    recommend_desc = f'库中已存在更高优先级语言版本({existing_lang_name})，建议抛弃新版'
                else:
                    # 优先级相同
                    recommend_action = 'KEEP_BOTH'
                    recommend_desc = f'同一语言版本，建议保留两者作为备份'
                
                # 构建选项列表
                options = []
                
                # 1. 智能推荐选项
                if recommend_action == 'KEEP_NEW':
                    options.append({
                        'action': 'KEEP_NEW',
                        'label': f'保留新版（{self._get_lang_name(current_lang)}）',
                        'description': recommend_desc,
                        'recommend': True
                    })
                    options.append({
                        'action': 'SKIP',
                        'label': f'抛弃新版（保留{existing_lang_name}）',
                        'description': f'保留库中的{existing_lang_name}版本，删除新版'
                    })
                elif recommend_action == 'SKIP':
                    options.append({
                        'action': 'SKIP',
                        'label': f'抛弃新版（保留{existing_lang_name}）',
                        'description': recommend_desc,
                        'recommend': True
                    })
                    options.append({
                        'action': 'KEEP_NEW',
                        'label': f'保留新版（{self._get_lang_name(current_lang)}）',
                        'description': f'用新版{self._get_lang_name(current_lang)}替换{existing_lang_name}（不推荐）'
                    })
                else:  # KEEP_BOTH
                    options.append({
                        'action': 'KEEP_BOTH',
                        'label': '保留两者',
                        'description': recommend_desc,
                        'recommend': True
                    })
                
                # 2. 保留两者选项（如果不是默认推荐）
                if recommend_action != 'KEEP_BOTH':
                    options.append({
                        'action': 'KEEP_BOTH',
                        'label': '保留两者',
                        'description': '同时保留两个语言版本（占用更多空间）'
                    })
                
                # 3. 合并选项（仅当同一语言时显示）
                if current_priority == existing_priority:
                    options.append({
                        'action': 'MERGE_LANG',
                        'label': '合并语言版本',
                        'description': '合并到同一文件夹，保留最新文件'
                    })
            else:
                # 没有已存在的作品（不应该发生）
                options = [
                    {
                        'action': 'KEEP_NEW',
                        'label': f'保留新版（{self._get_lang_name(current_lang)}）',
                        'description': '保留当前版本',
                        'recommend': True
                    },
                    {
                        'action': 'SKIP',
                        'label': '抛弃新版',
                        'description': '删除新版本'
                    }
                ]
        
        return options
    
    async def close(self):
        """清理资源"""
        await self.dlsite_service.close()


# 全局服务实例
_duplicate_service: Optional[EnhancedDuplicateService] = None


def get_duplicate_service() -> EnhancedDuplicateService:
    """获取增强查重服务实例（单例）"""
    global _duplicate_service
    if _duplicate_service is None:
        _duplicate_service = EnhancedDuplicateService()
    return _duplicate_service
