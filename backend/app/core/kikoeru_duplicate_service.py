"""
Kikoeru 服务器查重服务
支持通过 API 和 Token 访问本地部署的 Kikoeru 服务器进行查重
"""
import logging
import asyncio
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
import aiohttp
from datetime import datetime, timedelta

from ..config.settings import get_config
from ..core.dlsite_service import get_dlsite_service

logger = logging.getLogger(__name__)


@dataclass
class KikoeruServerConfig:
    """Kikoeru 服务器配置"""
    enabled: bool = False
    server_url: str = ""  # 例如: http://192.168.1.100:8088
    api_token: str = ""   # 访问令牌
    timeout: int = 10     # 请求超时(秒)
    cache_ttl: int = 300  # 缓存时间(秒)


@dataclass
class KikoeruCheckResult:
    """Kikoeru 服务器查重结果"""
    is_found: bool = False           # 是否在 Kikoeru 中找到
    rjcode: str = ""                 # RJ号
    work_id: int = 0                 # Kikoeru 中的作品ID
    title: str = ""                  # 作品标题
    circle_name: str = ""            # 社团名
    tags: List[str] = field(default_factory=list)  # 标签
    total_count: int = 0             # 搜索结果总数
    source: str = "kikoeru"          # 结果来源
    checked_at: datetime = field(default_factory=datetime.now)


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
        # 直接访问 Pydantic 模型的属性
        if hasattr(config, 'kikoeru_server'):
            kikoeru_config = config.kikoeru_server
            return KikoeruServerConfig(
                enabled=kikoeru_config.enabled,
                server_url=kikoeru_config.server_url.rstrip('/'),
                api_token=kikoeru_config.api_token,
                timeout=kikoeru_config.timeout,
                cache_ttl=kikoeru_config.cache_ttl
            )
        else:
            # 如果配置不存在，返回默认配置
            return KikoeruServerConfig()
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP Session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
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
        # 标准化 RJ 号
        rjcode = self._normalize_rjcode(rjcode)
        
        # 检查缓存
        if use_cache:
            cached = self._get_cache(rjcode)
            if cached:
                logger.debug(f"Kikoeru 查重缓存命中: {rjcode}")
                return cached
        
        # 检查服务是否启用
        if not self.config.enabled or not self.config.server_url:
            return KikoeruCheckResult(
                is_found=False,
                rjcode=rjcode,
                source="kikoeru_disabled"
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
                
                # 缓存结果
                if use_cache:
                    self._set_cache(rjcode, result)
                
                if result.is_found:
                    logger.info(f"[Kikoeru] ✓ 找到作品: {rjcode} - {result.title}")
                else:
                    logger.info(f"[Kikoeru] ✗ 未找到: {rjcode}")
                
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
            # 使用一个常见的 RJ 号进行测试
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
                        'message': '认证失败，请检查 API Token',
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
    
    async def check_duplicate_with_linkages(
        self, 
        rjcode: str,
        cue_languages: List[str] = None,
        use_cache: bool = True
    ) -> Dict[str, KikoeruCheckResult]:
        """
        检查作品及其所有关联作品是否在 Kikoeru 服务器中
        
        支持递归查询关联作品链（原作、翻译版、子版本等）
        
        Args:
            rjcode: RJ号
            cue_languages: 需要检查的语言列表
            use_cache: 是否使用缓存
        
        Returns:
            Dict[str, KikoeruCheckResult]: 所有关联作品及其查重结果
        """
        if cue_languages is None:
            cue_languages = ['CHI_HANS', 'CHI_HANT', 'ENG']
        
        results = {}
        
        # 1. 首先查询原始作品
        primary_result = await self.check_duplicate(rjcode, use_cache)
        results[rjcode] = primary_result
        
        if not self.config.enabled:
            return results
        
        try:
            # 2. 获取关联作品链
            logger.info(f"[Kikoeru关联查询] 开始获取 {rjcode} 的关联作品链")
            dlsite_service = get_dlsite_service()
            linked_works = await dlsite_service.get_full_linkage(rjcode, cue_languages)
            
            if len(linked_works) > 1:
                logger.info(f"[Kikoeru关联查询] 发现 {len(linked_works)} 个关联作品: {list(linked_works.keys())}")
                
                # 3. 查询所有关联作品（排除已查询的原始作品）
                linked_rjcodes = [w.workno for w in linked_works.values() if w.workno != rjcode]
                
                if linked_rjcodes:
                    logger.info(f"[Kikoeru关联查询] 将查询 {len(linked_rjcodes)} 个关联作品")
                    linked_results = await self.check_duplicates_batch(linked_rjcodes, use_cache)
                    results.update(linked_results)
                    
                    # 4. 记录找到的作品
                    found_works = [rj for rj, res in results.items() if res.is_found]
                    if found_works:
                        logger.info(f"[Kikoeru关联查询] 在关联作品中找到 {len(found_works)} 个: {found_works}")
            else:
                logger.info(f"[Kikoeru关联查询] {rjcode} 没有关联作品")
                
        except Exception as e:
            logger.error(f"[Kikoeru关联查询] 获取关联作品失败 {rjcode}: {e}")
        
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
