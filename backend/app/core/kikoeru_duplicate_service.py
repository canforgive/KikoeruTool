"""
Kikoeru 服务器查重服务
支持通过 API 和 Token 访问本地部署的 Kikoeru 服务器进行查重
"""
import logging
import asyncio
import re
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
import aiohttp
from datetime import datetime, timedelta

from ..config.settings import get_config, save_config
from ..core.dlsite_service import get_dlsite_service

logger = logging.getLogger(__name__)


@dataclass
class KikoeruServerConfig:
    """Kikoeru 服务器配置"""
    enabled: bool = False
    server_url: str = ""  # 例如: http://192.168.1.100:8088
    username: str = ""    # 登录用户名
    password: str = ""    # 登录密码
    api_token: str = ""   # API 访问令牌（自动获取）
    token_expires: int = 0  # Token 过期时间戳
    timeout: int = 10     # 请求超时(秒)
    cache_ttl: int = 300  # 缓存时间(秒)


@dataclass
class KikoeruCheckResult:
    """Kikoeru 服务器查重结果"""
    is_found: bool = False
    rjcode: str = ""
    work_id: int = 0
    title: str = ""
    circle_name: str = ""
    tags: List[str] = field(default_factory=list)
    total_count: int = 0
    source: str = "kikoeru"
    checked_at: datetime = None
    match_type: str = "exact"
    matched_rjcode: str = ""
    tolerance: int = 0
    
    def __post_init__(self):
        if self.checked_at is None:
            self.checked_at = datetime.now()
        if self.tags is None:
            self.tags = []


class KikoeruDuplicateService:
    """
    Kikoeru 服务器查重服务
    
    通过调用 Kikoeru API 检查作品是否已存在于 Kikoeru 库中
    支持 API Token 认证
    """
    
    def __init__(self, config: Optional[KikoeruServerConfig] = None):
        self.config = config or self._load_config()
        self._cache: Dict[str, tuple] = {}  # 缓存: rjcode -> (result, timestamp)
        self._session: Optional[aiohttp.ClientSession] = None
    
    def _load_config(self) -> KikoeruServerConfig:
        """从系统配置加载 Kikoeru 服务器配置"""
        config = get_config()
        if hasattr(config, 'kikoeru_server'):
            kikoeru_config = config.kikoeru_server
            return KikoeruServerConfig(
                enabled=kikoeru_config.enabled,
                server_url=kikoeru_config.server_url.rstrip('/'),
                username=kikoeru_config.username,
                password=kikoeru_config.password,
                api_token=kikoeru_config.api_token,
                token_expires=kikoeru_config.token_expires,
                timeout=kikoeru_config.timeout,
                cache_ttl=kikoeru_config.cache_ttl
            )
        else:
            return KikoeruServerConfig()
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP Session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    def _is_token_expired(self) -> bool:
        """检查 Token 是否过期"""
        if not self.config.api_token:
            return True
        if self.config.token_expires <= 0:
            return True
        now = int(time.time())
        return now >= self.config.token_expires - 60
    
    async def _login(self) -> bool:
        """通过账号密码登录获取 Token"""
        if not self.config.username or not self.config.password:
            logger.warning("[Kikoeru] 未配置用户名或密码，无法自动获取 Token")
            return False
        
        try:
            session = await self._get_session()
            login_url = f"{self.config.server_url}/api/auth/me"
            
            logger.info(f"[Kikoeru] 正在登录: {self.config.username}")
            logger.info(f"[Kikoeru] 登录URL: {login_url}")
            
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            login_data = {
                "name": self.config.username,
                "password": self.config.password
            }
            
            async with session.post(
                login_url,
                json=login_data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as response:
                logger.info(f"[Kikoeru] 登录响应状态: {response.status}")
                content_type = response.headers.get('Content-Type', '')
                logger.info(f"[Kikoeru] 响应Content-Type: {content_type}")
                
                if response.status == 200:
                    if 'application/json' in content_type:
                        data = await response.json()
                        logger.info(f"[Kikoeru] 登录响应keys: {list(data.keys())}")
                        
                        token = data.get('token')
                        
                        if token:
                            self.config.api_token = token
                            self.config.token_expires = int(time.time()) + 86400
                            self._save_token_to_config(token, self.config.token_expires)
                            logger.info(f"[Kikoeru] 登录成功，Token 已保存")
                            return True
                        else:
                            logger.error(f"[Kikoeru] 未找到token，可用字段: {list(data.keys())}")
                            return False
                    else:
                        text = await response.text()
                        logger.error(f"[Kikoeru] 响应非JSON: {text[:300]}")
                        return False
                        
                elif response.status == 401:
                    error_text = await response.text()
                    logger.error(f"[Kikoeru] 登录401错误: 用户名或密码错误")
                    return False
                elif response.status == 422:
                    error_text = await response.text()
                    logger.error(f"[Kikoeru] 登录422错误: 参数格式错误 - {error_text[:300]}")
                    return False
                else:
                    error_text = await response.text()
                    logger.error(f"[Kikoeru] 登录失败 {response.status}: {error_text[:300]}")
                    return False
                    
        except Exception as e:
            logger.error(f"[Kikoeru] 登录异常: {e}")
            return False
    
    def _save_token_to_config(self, token: str, expires: int):
        """保存 Token 到配置文件"""
        try:
            config_to_save = {
                'kikoeru_server': {
                    'api_token': token,
                    'token_expires': expires
                }
            }
            save_config(config_to_save)
            logger.info("[Kikoeru] Token 已保存到配置文件")
        except Exception as e:
            logger.error(f"[Kikoeru] 保存 Token 失败: {e}")
    
    async def _ensure_valid_token(self) -> bool:
        """确保有有效的 Token，如果没有或过期则自动获取"""
        if not self._is_token_expired():
            return True
        
        if self.config.username and self.config.password:
            return await self._login()
        
        return bool(self.config.api_token)
    
    def _get_cache(self, rjcode: str) -> Optional[KikoeruCheckResult]:
        """从缓存获取结果"""
        if rjcode not in self._cache:
            return None
        
        result, timestamp = self._cache[rjcode]
        if datetime.now() - timestamp > timedelta(seconds=self.config.cache_ttl):
            # 缓存过期
            del self._cache[rjcode]
            return None
        
        return result
    
    def _set_cache(self, rjcode: str, result: KikoeruCheckResult):
        """设置缓存"""
        self._cache[rjcode] = (result, datetime.now())
    
    def _build_search_url(self, rjcode: str) -> str:
        """构建搜索 URL"""
        # Kikoeru 标准搜索 API: /api/search?page=1&sort=desc&order=release&nsfw=0&keyword={rjcode}
        return f"{self.config.server_url}/api/search?page=1&sort=desc&order=release&nsfw=0&keyword={rjcode}"
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头，包含 API Token"""
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        if self.config.api_token:
            # 支持 Bearer Token 认证
            headers['Authorization'] = f'Bearer {self.config.api_token}'
            logger.debug(f"[Kikoeru] 使用 Token 认证: {self.config.api_token[:20]}...")
        else:
            logger.debug("[Kikoeru] 未配置 API Token，使用无认证请求")
        
        return headers
    
    async def check_duplicate(
        self, 
        rjcode: str,
        use_cache: bool = True
    ) -> KikoeruCheckResult:
        """
        检查作品是否在 Kikoeru 服务器中
        
        Args:
            rjcode: RJ号 (格式: RJ123456 或 123456)
            use_cache: 是否使用缓存
        
        Returns:
            KikoeruCheckResult: 查重结果
        """
        rjcode = self._normalize_rjcode(rjcode)
        
        if use_cache:
            cached = self._get_cache(rjcode)
            if cached:
                logger.debug(f"Kikoeru 查重缓存命中: {rjcode}")
                return cached
        
        if not self.config.enabled or not self.config.server_url:
            return KikoeruCheckResult(
                is_found=False,
                rjcode=rjcode,
                source="kikoeru_disabled"
            )
        
        if not await self._ensure_valid_token():
            if not self.config.api_token:
                logger.warning("[Kikoeru] 无法获取有效 Token")
                return KikoeruCheckResult(
                    is_found=False,
                    rjcode=rjcode,
                    source="kikoeru_no_token"
                )
        
        try:
            url = self._build_search_url(rjcode)
            headers = self._get_headers()
            
            session = await self._get_session()
            
            logger.info(f"[Kikoeru] 正在查询: {rjcode}")
            logger.info(f"[Kikoeru] 请求 URL: {url}")
            logger.info(f"[Kikoeru] 请求头: {headers}")
            
            async with session.get(
                url, 
                headers=headers, 
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as response:
                logger.info(f"[Kikoeru] 响应状态: {response.status}")
                
                if response.status == 401:
                    error_text = await response.text()
                    logger.warning(f"[Kikoeru] Token 过期或无效，尝试重新登录: {rjcode}")
                    
                    if self.config.username and self.config.password:
                        if await self._login():
                            headers = self._get_headers()
                            async with session.get(
                                url, 
                                headers=headers, 
                                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                            ) as retry_response:
                                if retry_response.status == 200:
                                    data = await retry_response.json()
                                    result = self._parse_search_result(rjcode, data)
                                    if use_cache:
                                        self._set_cache(rjcode, result)
                                    return result
                    
                    logger.error(f"[Kikoeru] 认证失败: {rjcode}")
                    logger.error(f"[Kikoeru] 响应内容: {error_text[:500]}")
                    return KikoeruCheckResult(
                        is_found=False,
                        rjcode=rjcode,
                        source="kikoeru_auth_error"
                    )
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.warning(f"[Kikoeru] 服务器返回错误: {response.status}")
                    logger.warning(f"[Kikoeru] 错误响应: {error_text[:500]}")
                    return KikoeruCheckResult(
                        is_found=False,
                        rjcode=rjcode,
                        source=f"kikoeru_error_{response.status}"
                    )
                
                data = await response.json()
                logger.info(f"[Kikoeru] 响应数据: {data}")
                
                result = self._parse_search_result(rjcode, data)
                
                if not result.is_found:
                    logger.info(f"[Kikoeru] 精确匹配未找到，尝试宽容搜索（±1）")
                    fuzzy_result = await self._check_fuzzy(rjcode, session, headers, use_cache)
                    if fuzzy_result.is_found:
                        logger.info(f"[Kikoeru] ✓ 宽容匹配成功: {rjcode} -> {fuzzy_result.matched_rjcode}")
                        return fuzzy_result
                
                if use_cache:
                    self._set_cache(rjcode, result)
                
                if result.is_found:
                    logger.info(f"[Kikoeru] ✓ 精确匹配成功: {rjcode} - {result.title}")
                else:
                    logger.info(f"[Kikoeru] ✗ 未找到: {rjcode}（包括±1宽容搜索）")
                
                return result
                
        except asyncio.TimeoutError:
            logger.warning(f"Kikoeru 服务器查询超时: {rjcode}")
            return KikoeruCheckResult(
                is_found=False,
                rjcode=rjcode,
                source="kikoeru_timeout"
            )
        except Exception as e:
            logger.error(f"Kikoeru 服务器查询失败: {rjcode}, 错误: {e}")
            return KikoeruCheckResult(
                is_found=False,
                rjcode=rjcode,
                source="kikoeru_exception"
            )
    
    def _normalize_rjcode(self, rjcode: str) -> str:
        """标准化 RJ 号"""
        rjcode = rjcode.upper().strip()
        if not rjcode.startswith('RJ') and not rjcode.startswith('BJ') and not rjcode.startswith('VJ'):
            rjcode = 'RJ' + rjcode
        return rjcode
    
    async def _check_fuzzy(
        self, 
        rjcode: str, 
        session: aiohttp.ClientSession, 
        headers: Dict[str, str],
        use_cache: bool
    ) -> KikoeruCheckResult:
        """
        宽容搜索：尝试 RJ 号 ±1
        
        Args:
            rjcode: 原始 RJ 号
            session: HTTP Session
            headers: 请求头
            use_cache: 是否使用缓存
        
        Returns:
            KikoeruCheckResult: 查重结果（包含模糊匹配信息）
        """
        # 提取数字部分
        import re
        match = re.match(r'(RJ|BJ|VJ)(\d+)', rjcode.upper())
        if not match:
            return KikoeruCheckResult(rjcode=rjcode)
        
        prefix = match.group(1)
        num = int(match.group(2))
        
        # 尝试 ±1
        for delta in [-1, 1]:
            fuzzy_num = num + delta
            if fuzzy_num < 0:
                continue
            
            # 构建模糊 RJ 号（保持相同位数）
            original_len = len(match.group(2))
            fuzzy_rjcode = f"{prefix}{fuzzy_num:0{original_len}d}"
            
            try:
                url = self._build_search_url(fuzzy_rjcode)
                logger.info(f"[Kikoeru] 尝试模糊匹配: {fuzzy_rjcode}")
                
                async with session.get(
                    url, 
                    headers=headers, 
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = self._parse_search_result(fuzzy_rjcode, data)
                        
                        if result.is_found:
                            # 找到模糊匹配
                            result.rjcode = rjcode  # 保持原始 RJ 号
                            result.match_type = "fuzzy"
                            result.matched_rjcode = fuzzy_rjcode
                            result.tolerance = delta
                            
                            if use_cache:
                                self._set_cache(rjcode, result)
                            
                            logger.info(f"[Kikoeru] 模糊匹配成功: {rjcode} -> {fuzzy_rjcode}")
                            return result
                            
            except Exception as e:
                logger.debug(f"[Kikoeru] 模糊匹配失败 {fuzzy_rjcode}: {e}")
                continue
        
        # 未找到模糊匹配
        return KikoeruCheckResult(rjcode=rjcode)
    
    def _parse_search_result(self, rjcode: str, data: dict) -> KikoeruCheckResult:
        """解析 Kikoeru 搜索结果"""
        result = KikoeruCheckResult(rjcode=rjcode)
        
        # 检查是否有 works 字段
        if not isinstance(data, dict) or 'works' not in data:
            logger.warning(f"Kikoeru 返回格式异常: {rjcode}")
            return result
        
        works = data.get('works', [])
        if not isinstance(works, list):
            return result
        
        result.total_count = len(works)
        
        # 查找匹配的作品
        # Kikoeru 中 id 是纯数字，需要转换 RJ 号
        search_id = self._rjcode_to_id(rjcode)
        
        for work in works:
            if not isinstance(work, dict):
                continue
            
            work_id = work.get('id', 0)
            
            # 检查是否匹配
            if work_id == search_id:
                result.is_found = True
                result.work_id = work_id
                result.title = work.get('title', '')
                
                # 获取社团名
                circle = work.get('circle', {})
                if isinstance(circle, dict):
                    result.circle_name = circle.get('name', '')
                
                # 获取标签
                tags = work.get('tags', [])
                if isinstance(tags, list):
                    result.tags = [tag.get('name', '') for tag in tags if isinstance(tag, dict)]
                
                break
        
        return result
    
    def _rjcode_to_id(self, rjcode: str) -> int:
        """将 RJ 号转换为 Kikoeru 的 ID"""
        # 去掉前缀，转换为整数
        # RJ01011249 -> 1011249
        # RJ123456 -> 123456
        rjcode = rjcode.upper()
        for prefix in ['RJ', 'BJ', 'VJ']:
            if rjcode.startswith(prefix):
                try:
                    return int(rjcode[len(prefix):])
                except ValueError:
                    return 0
        return 0
    
    async def check_duplicates_batch(
        self, 
        rjcodes: List[str],
        use_cache: bool = True
    ) -> Dict[str, KikoeruCheckResult]:
        """
        批量检查多个 RJ 号
        
        Args:
            rjcodes: RJ 号列表
            use_cache: 是否使用缓存
        
        Returns:
            Dict[str, KikoeruCheckResult]: RJ号到结果的映射
        """
        if not self.config.enabled:
            return {rj: KikoeruCheckResult(is_found=False, rjcode=rj, source="kikoeru_disabled") 
                    for rj in rjcodes}
        
        tasks = [self.check_duplicate(rj, use_cache) for rj in rjcodes]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            rj: result if not isinstance(result, Exception) else KikoeruCheckResult(
                is_found=False, 
                rjcode=rj, 
                source="kikoeru_exception"
            )
            for rj, result in zip(rjcodes, results)
        }
    
    async def test_connection(self) -> Dict[str, any]:
        """
        测试与 Kikoeru 服务器的连接
        
        Returns:
            Dict: 包含 success, message, latency 等信息
        """
        if not self.config.enabled:
            return {
                'success': False,
                'message': 'Kikoeru 服务器查重未启用',
                'latency': 0
            }
        
        if not self.config.server_url:
            return {
                'success': False,
                'message': 'Kikoeru 服务器 URL 未配置',
                'latency': 0
            }
        
        start_time = datetime.now()
        
        try:
            if not await self._ensure_valid_token():
                if not self.config.api_token:
                    return {
                        'success': False,
                        'message': '无法获取有效的认证 Token，请检查用户名和密码',
                        'latency': 0
                    }
            
            test_rjcode = "RJ123456"
            url = self._build_search_url(test_rjcode)
            headers = self._get_headers()
            
            session = await self._get_session()
            
            async with session.get(
                url, 
                headers=headers, 
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as response:
                latency = (datetime.now() - start_time).total_seconds() * 1000
                
                if response.status == 200:
                    return {
                        'success': True,
                        'message': f'连接成功 (延迟: {latency:.0f}ms)',
                        'latency': latency,
                        'status_code': response.status
                    }
                elif response.status == 401:
                    return {
                        'success': False,
                        'message': '认证失败，请检查用户名和密码',
                        'latency': latency,
                        'status_code': response.status
                    }
                else:
                    return {
                        'success': False,
                        'message': f'服务器返回错误: {response.status}',
                        'latency': latency,
                        'status_code': response.status
                    }
                    
        except asyncio.TimeoutError:
            latency = (datetime.now() - start_time).total_seconds() * 1000
            return {
                'success': False,
                'message': f'连接超时 ({self.config.timeout}秒)',
                'latency': latency
            }
        except Exception as e:
            latency = (datetime.now() - start_time).total_seconds() * 1000
            return {
                'success': False,
                'message': f'连接失败: {str(e)}',
                'latency': latency
            }
    
    def _normalize_lang_code(self, lang: str) -> str:
        """将 DLsite 语言代码转换为标准格式"""
        lang_map = {
            'JPN': 'JPN',
            'CHN': 'CHI_HANS',  # 简体中文
            'TWN': 'CHI_HANT',  # 繁体中文
            'ENG': 'ENG',
            'KOR': 'KOR',
        }
        return lang_map.get(lang.upper(), lang.upper())

    async def check_duplicate_with_linkages(
        self,
        rjcode: str,
        cue_languages: List[str] = None,
        use_cache: bool = True
    ) -> Dict[str, KikoeruCheckResult]:
        """
        检查作品及其关联作品是否在 Kikoeru 服务器中

        只查询直接关联的作品（原作、翻译版），避免递归查询过多无关作品

        Args:
            rjcode: RJ号
            cue_languages: 需要检查的语言列表（支持 CHI_HANS/CHN, CHI_HANT/TWN, ENG, JPN 等）
            use_cache: 是否使用缓存

        Returns:
            Dict[str, KikoeruCheckResult]: 所有关联作品及其查重结果
        """
        if cue_languages is None:
            cue_languages = ['CHI_HANS', 'CHI_HANT', 'ENG', 'JPN']
        
        results = {}
        
        # 1. 首先查询原始作品
        primary_result = await self.check_duplicate(rjcode, use_cache)
        results[rjcode] = primary_result
        
        if not self.config.enabled:
            return results
        
        try:
            # 2. 获取关联作品（只获取直接关联的，不递归）
            logger.info(f"[Kikoeru关联查询] 开始获取 {rjcode} 的关联作品")
            dlsite_service = get_dlsite_service()
            linked_works = await dlsite_service.get_linked_works(rjcode)
            
            if len(linked_works) > 1:
                logger.info(f"[Kikoeru关联查询] 发现 {len(linked_works)} 个关联作品: {list(linked_works.keys())}")
                
                # 3. 筛选需要查询的语言版本（只查询 cue_languages 中指定的语言）
                linked_rjcodes = []
                for workno, work_info in linked_works.items():
                    if workno != rjcode:
                        # 转换语言代码并检查
                        normalized_lang = self._normalize_lang_code(work_info.lang)
                        if normalized_lang in cue_languages or work_info.lang in cue_languages:
                            linked_rjcodes.append(workno)
                        else:
                            logger.debug(f"[Kikoeru关联查询] 跳过 {workno}，语言 {work_info.lang}({normalized_lang}) 不在目标列表中")
                
                if linked_rjcodes:
                    logger.info(f"[Kikoeru关联查询] 将查询 {len(linked_rjcodes)} 个关联作品（语言匹配）: {linked_rjcodes}")
                    linked_results = await self.check_duplicates_batch(linked_rjcodes, use_cache)
                    results.update(linked_results)
                    
                    # 4. 记录找到的作品
                    found_works = [rj for rj, res in results.items() if res.is_found and rj != rjcode]
                    if found_works:
                        logger.info(f"[Kikoeru关联查询] 在关联作品中找到 {len(found_works)} 个: {found_works}")
                else:
                    logger.info(f"[Kikoeru关联查询] 没有符合语言要求的关联作品")
            else:
                logger.info(f"[Kikoeru关联查询] {rjcode} 没有关联作品")
                
        except Exception as e:
            logger.error(f"[Kikoeru关联查询] 获取关联作品失败 {rjcode}: {e}")
            logger.exception(e)
        
        return results

    async def close(self):
        """关闭 HTTP Session"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()
        logger.info("Kikoeru 查重缓存已清除")


# 全局服务实例
_kikoeru_service: Optional[KikoeruDuplicateService] = None


def get_kikoeru_service() -> KikoeruDuplicateService:
    """获取 Kikoeru 查重服务实例（单例）"""
    global _kikoeru_service
    if _kikoeru_service is None:
        _kikoeru_service = KikoeruDuplicateService()
    return _kikoeru_service


async def check_kikoeru_duplicate(rjcode: str, use_cache: bool = True) -> KikoeruCheckResult:
    """
    快捷函数：检查作品是否在 Kikoeru 服务器中
    
    Args:
        rjcode: RJ号
        use_cache: 是否使用缓存
    
    Returns:
        KikoeruCheckResult: 查重结果
    """
    service = get_kikoeru_service()
    return await service.check_duplicate(rjcode, use_cache)
