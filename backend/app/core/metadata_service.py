import os
import re
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import requests
import logging
import json

from ..config.settings import get_config
from ..models.database import WorkMetadata as WorkMetadataModel, get_db
from ..core.task_engine import Task

logger = logging.getLogger(__name__)

class WorkMetadata:
    """作品元数据"""
    def __init__(self):
        self.rjcode: str = ""
        self.work_name: str = ""
        self.maker_id: str = ""
        self.maker_name: str = ""
        self.release_date: str = ""
        self.series_name: Optional[str] = None
        self.series_id: Optional[str] = None
        self.age_category: str = ""
        self.tags: list = []
        self.cvs: list = []
        self.cover_url: str = ""
    
    def to_dict(self) -> dict:
        return {
            'rjcode': self.rjcode,
            'work_name': self.work_name,
            'maker_id': self.maker_id,
            'maker_name': self.maker_name,
            'release_date': self.release_date,
            'series_name': self.series_name,
            'series_id': self.series_id,
            'age_category': self.age_category,
            'tags': self.tags,
            'cvs': self.cvs,
            'cover_url': self.cover_url
        }

class MetadataService:
    """元数据服务"""
    
    def __init__(self):
        self.config = get_config()
        self.session = requests.Session()
        if self.config.metadata.http_proxy:
            self.session.proxies = {
                'http': self.config.metadata.http_proxy,
                'https': self.config.metadata.http_proxy
            }
    
    async def fetch(self, path: str, task: Task) -> dict:
        """
        从路径中提取RJ号并获取元数据
        """
        # 从路径中提取RJ号
        rjcode = self._extract_rjcode(path)
        if not rjcode:
            raise Exception(f"无法从路径中提取RJ号: {path}")
        
        task.update_progress(65, f"获取元数据: {rjcode}")
        
        # 检查缓存
        if self.config.metadata.cache_enabled:
            cached = self._get_cached_metadata(rjcode)
            if cached:
                logger.info(f"使用缓存的元数据: {rjcode}")
                return cached.to_dict()
        
        # 从DLsite获取
        metadata = await self._fetch_from_dlsite(rjcode)
        
        # 缓存到数据库
        if self.config.metadata.cache_enabled:
            self._cache_metadata(metadata)
        
        return metadata.to_dict()
    
    def _extract_rjcode(self, path: str) -> Optional[str]:
        """从路径中提取RJ号"""
        # RJ123456 或 RJ12345678
        pattern = r'[RVB]J(\d{6}|\d{8})(?!\d)'
        match = re.search(pattern, path, re.IGNORECASE)
        if match:
            return match.group(0).upper()
        return None
    
    def _get_cached_metadata(self, rjcode: str) -> Optional[WorkMetadataModel]:
        """从缓存获取元数据"""
        db = next(get_db())
        try:
            cached = db.query(WorkMetadataModel).filter(
                WorkMetadataModel.rjcode == rjcode
            ).first()
            
            if cached is not None and cached.expires_at > datetime.utcnow():
                return cached
            return None
        finally:
            db.close()
    
    def _cache_metadata(self, metadata: WorkMetadata):
        """缓存元数据到数据库"""
        db = next(get_db())
        try:
            # 删除旧缓存
            db.query(WorkMetadataModel).filter(
                WorkMetadataModel.rjcode == metadata.rjcode
            ).delete()
            
            # 创建新缓存
            cached = WorkMetadataModel(
                rjcode=metadata.rjcode,
                work_name=metadata.work_name,
                maker_id=metadata.maker_id,
                maker_name=metadata.maker_name,
                release_date=metadata.release_date,
                series_name=metadata.series_name,
                series_id=metadata.series_id,
                age_category=metadata.age_category,
                tags=metadata.tags,
                cvs=metadata.cvs,
                cover_url=metadata.cover_url,
                expires_at=datetime.utcnow() + timedelta(days=30)
            )
            db.add(cached)
            db.commit()
        except Exception as e:
            logger.error(f"缓存元数据失败: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def _fetch_from_dlsite(self, rjcode: str) -> WorkMetadata:
        """从DLsite API获取元数据（支持大家翻译）"""
        await asyncio.sleep(self.config.metadata.sleep_interval)
        
        # 获取基础数据（使用配置的语言）
        url = f"https://www.dlsite.com/maniax/api/=/product.json?workno={rjcode}&locale={self.config.metadata.locale}"
        
        try:
            response = self.session.get(
                url,
                timeout=(self.config.metadata.connect_timeout, self.config.metadata.read_timeout)
            )
            response.raise_for_status()
            
            data = response.json()
            if not data or len(data) == 0:
                raise Exception(f"作品未找到: {rjcode}")
            
            product = data[0]
            metadata = WorkMetadata()
            metadata.rjcode = product.get('workno', rjcode)
            metadata.work_name = product.get('work_name', '')
            
            metadata.maker_id = product.get('maker_id', '')
            metadata.maker_name = product.get('maker_name', '')
            metadata.release_date = product.get('regist_date', '')[:10]
            metadata.series_name = product.get('series_name')
            metadata.series_id = product.get('series_id')
            metadata.cover_url = 'https:' + product.get('image_main', {}).get('url', '')
            
            # 年龄分级
            age_category = product.get('age_category', 3)
            if age_category == 1:
                metadata.age_category = 'GEN'
            elif age_category == 2:
                metadata.age_category = 'R15'
            else:
                metadata.age_category = 'ADL'
            
            # 标签
            for genre in product.get('genres', []):
                metadata.tags.append(genre.get('name', ''))
            
            # 声优
            creators = product.get('creaters', {})
            if isinstance(creators, dict) and 'voice_by' in creators:
                for cv in creators['voice_by']:
                    metadata.cvs.append(cv.get('name', ''))
            
            # 检查是否有大家翻译的中文标题
            translation_info = product.get('translation_info')
            if translation_info:
                logger.info(f"[{rjcode}] 发现翻译信息: {translation_info}")
                
                # 语言代码映射
                locale_map = {
                    'CHI_HANS': 'zh-CN',
                    'CHI_HANT': 'zh-TW',
                    'ENG': 'en-US',
                    'KOR': 'ko-KR',
                    'SPA': 'es-ES',
                    'DEU': 'de-DE',
                    'FRA': 'fr-FR',
                    'IND': 'id-ID',
                    'ITA': 'it-IT',
                    'POR': 'pt-PT',
                    'SWE': 'sv-SE',
                    'THA': 'th-TH',
                    'VIE': 'vi-VN'
                }
                
                translated_name = None
                
                # 情况1: 翻译作品（子作品）
                if not translation_info.get('is_original', True):
                    lang_code = translation_info.get('lang')
                    if lang_code:
                        try:
                            logger.info(f"[{rjcode}] 处理翻译作品，原语言: {lang_code}")
                            
                            # 优先尝试简体中文，然后是繁体中文，最后是作品本身的语言
                            tried_locales = []
                            
                            # 策略1: 如果原语言不是简体中文，先尝试简体中文
                            if lang_code != 'CHI_HANS':
                                logger.info(f"[{rjcode}] 尝试获取简体中文标题")
                                translated_name = await self._fetch_translated_title(rjcode, 'zh-CN', validate_chinese=True)
                                tried_locales.append('zh-CN')
                                if translated_name:
                                    logger.info(f"[{rjcode}] 成功获取简体中文翻译标题: {translated_name}")
                            
                            # 策略2: 如果简体中文失败且原语言不是繁体中文，尝试繁体中文
                            if not translated_name and lang_code != 'CHI_HANT':
                                logger.info(f"[{rjcode}] 简体中文不可用，尝试获取繁体中文标题")
                                translated_name = await self._fetch_translated_title(rjcode, 'zh-TW', validate_chinese=True)
                                tried_locales.append('zh-TW')
                                if translated_name:
                                    logger.info(f"[{rjcode}] 成功获取繁体中文翻译标题: {translated_name}")
                            
                            # 策略3: 使用作品本身的翻译语言
                            if not translated_name:
                                dlsite_locale = locale_map.get(lang_code, lang_code)
                                logger.info(f"[{rjcode}] 已尝试{tried_locales}，使用作品原locale {dlsite_locale}")
                                should_validate = lang_code in ['CHI_HANS', 'CHI_HANT']
                                translated_name = await self._fetch_translated_title(rjcode, str(dlsite_locale), validate_chinese=should_validate)
                                if translated_name:
                                    logger.info(f"[{rjcode}] 使用{lang_code}翻译标题: {translated_name}")
                        except Exception as e:
                            logger.warning(f"[{rjcode}] 获取翻译标题失败: {e}")
                
                # 情况2: 原作但有"大家来翻译"申请
                elif translation_info.get('is_translation_agree', False):
                    logger.info(f"[{rjcode}] 原作但有翻译申请，检查是否有可用的中文翻译")
                    
                    translation_status = translation_info.get('translation_status_for_translator', {})
                    logger.info(f"[{rjcode}] 翻译状态: {translation_status}")
                    
                    # 检查简体中文是否可用
                    chi_hans_status = translation_status.get('CHI_HANS', {})
                    if chi_hans_status.get('is_available', False) and not chi_hans_status.get('is_denied', True):
                        logger.info(f"[{rjcode}] 简体中文翻译申请可用，尝试获取")
                        try:
                            translated_name = await self._fetch_translated_title(rjcode, 'zh-CN', validate_chinese=True)
                            if translated_name:
                                logger.info(f"[{rjcode}] 成功获取简体中文翻译标题: {translated_name}")
                        except Exception as e:
                            logger.warning(f"[{rjcode}] 获取简体中文翻译标题失败: {e}")
                    
                    # 如果简体中文不可用或获取失败，尝试繁体中文
                    if not translated_name:
                        chi_hant_status = translation_status.get('CHI_HANT', {})
                        if chi_hant_status.get('is_available', False) and not chi_hant_status.get('is_denied', True):
                            logger.info(f"[{rjcode}] 繁体中文翻译申请可用，尝试获取")
                            try:
                                translated_name = await self._fetch_translated_title(rjcode, 'zh-TW', validate_chinese=True)
                                if translated_name:
                                    logger.info(f"[{rjcode}] 成功获取繁体中文翻译标题: {translated_name}")
                            except Exception as e:
                                logger.warning(f"[{rjcode}] 获取繁体中文翻译标题失败: {e}")
                
                if translated_name:
                    metadata.work_name = translated_name
            
            return metadata
            
        except requests.exceptions.RequestException as e:
            logger.error(f"请求DLsite失败: {e}")
            raise Exception(f"获取元数据失败: {e}")
    
    async def _fetch_translated_title(self, rjcode: str, lang: str, validate_chinese: bool = True) -> Optional[str]:
        """获取指定语言的翻译标题
        
        Args:
            rjcode: RJ号
            lang: 语言代码 (如 'zh-CN', 'zh-TW')
            validate_chinese: 是否验证标题不包含日文假名（中文翻译标题通常不包含假名）
        """
        await asyncio.sleep(self.config.metadata.sleep_interval)
        
        url = f"https://www.dlsite.com/maniax/api/=/product.json?workno={rjcode}&locale={lang}"
        logger.info(f"[{rjcode}] 调用翻译标题API: {url}")
        
        try:
            response = self.session.get(
                url,
                timeout=(self.config.metadata.connect_timeout, self.config.metadata.read_timeout)
            )
            response.raise_for_status()
            
            data = response.json()
            if data and len(data) > 0:
                title = data[0].get('work_name')
                if title:
                    logger.info(f"[{rjcode}] API返回标题: {title}")
                    
                    # 验证是否包含日文假名（如果需要）
                    # 中文翻译标题通常不包含日文假名，如果包含说明可能是日文原文
                    if validate_chinese and self._contains_japanese_kana(title):
                        logger.warning(f"[{rjcode}] 标题包含日文假名，可能是日文原文而非翻译: {title}")
                        return None
                    
                    return title
            
            return None
            
        except Exception as e:
            logger.error(f"[{rjcode}] 获取翻译标题失败: {e}")
            return None
    
    def _contains_japanese_kana(self, text: str) -> bool:
        """检查文本是否包含日文假名（平假名或片假名）
        
        日文标题通常包含假名，而中文翻译标题通常不包含
        返回True表示可能是日文标题，False表示可能是中文标题
        """
        import re
        # 平假名范围: \u3040-\u309F
        # 片假名范围: \u30A0-\u30FF
        # 日文标点符号: \u3000-\u303F (包含全角标点)
        kana_pattern = r'[\u3040-\u309F\u30A0-\u30FF]'
        
        kana_count = len(re.findall(kana_pattern, text))
        total_chars = len(text.replace(' ', ''))  # 排除空格
        
        if total_chars == 0:
            return False
        
        # 如果假名占比超过5%，认为是日文标题
        kana_ratio = kana_count / total_chars
        return kana_ratio > 0.05
