"""
URL智能优化系统主模块
"""

import asyncio
import aiohttp
import time
from typing import Optional, List, Dict, Any
from datetime import datetime
import re
from concurrent.futures import ThreadPoolExecutor

from .models import (
    URLMetadata, MirrorSource, URLTestResult,
    URLOptimizationResult, AccessStatus, MirrorType
)
from .url_classifier import URLClassifier
from .mirror_registry import MirrorRegistry
from core.logger import get_logger
logger = get_logger('url_intelligence.url_optimizer')



class URLOptimizer:
    """URL优化器"""
    
    def __init__(self):
        self.classifier = URLClassifier()
        self.registry = MirrorRegistry()
        self._cache: Dict[str, URLOptimizationResult] = {}
        self._cache_ttl = 3600  # 缓存1小时
        
        # 异步HTTP客户端
        self._session: Optional[aiohttp.ClientSession] = None
        self._executor = ThreadPoolExecutor(max_workers=4)
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取HTTP会话"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=10)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self):
        """关闭会话"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def test_url_access(self, url: str) -> URLTestResult:
        """测试URL访问性"""
        start_time = time.time()
        result = URLTestResult(url=url, status=AccessStatus.UNKNOWN)
        
        try:
            session = await self._get_session()
            async with session.head(url, allow_redirects=True) as response:
                result.latency_ms = (time.time() - start_time) * 1000
                result.status_code = response.status
                
                if response.status == 200:
                    if result.latency_ms > 2000:
                        result.status = AccessStatus.SLOW
                    else:
                        result.status = AccessStatus.ACCESSIBLE
                elif response.status == 404:
                    result.status = AccessStatus.NOT_FOUND
                elif response.status in (403, 451):
                    result.status = AccessStatus.BLOCKED
                else:
                    result.status = AccessStatus.UNKNOWN
                    
        except asyncio.TimeoutError:
            result.latency_ms = (time.time() - start_time) * 1000
            result.status = AccessStatus.TIMEOUT
            result.error_message = "连接超时"
        except aiohttp.ClientError as e:
            result.latency_ms = (time.time() - start_time) * 1000
            result.status = AccessStatus.BLOCKED
            result.error_message = str(e)
        except Exception as e:
            result.latency_ms = (time.time() - start_time) * 1000
            result.status = AccessStatus.UNKNOWN
            result.error_message = str(e)
        
        return result
    
    async def test_mirror_access(self, mirror: MirrorSource) -> MirrorSource:
        """测试镜像源访问性"""
        test_result = await self.test_url_access(mirror.url)
        mirror.status = test_result.status
        mirror.latency_ms = test_result.latency_ms
        
        # 更新速度评分
        if test_result.status == AccessStatus.ACCESSIBLE:
            if test_result.latency_ms < 100:
                mirror.speed_score = 95
            elif test_result.latency_ms < 300:
                mirror.speed_score = 85
            elif test_result.latency_ms < 1000:
                mirror.speed_score = 70
            else:
                mirror.speed_score = 50
        elif test_result.status == AccessStatus.SLOW:
            mirror.speed_score = 40
        else:
            mirror.speed_score = 0
            mirror.reliability_score = max(0, mirror.reliability_score - 20)
        
        return mirror
    
    async def test_all_mirrors(
        self, original_url: str, mirrors: List[MirrorSource]
    ) -> List[MirrorSource]:
        """并行测试所有镜像源"""
        tasks = [self.test_mirror_access(mirror) for mirror in mirrors]
        return await asyncio.gather(*tasks)
    
    def apply_mirror_rule(self, url: str, rule) -> Optional[str]:
        """应用镜像规则"""
        return self.registry.apply_rule(rule, url)
    
    async def optimize(self, url: str, force_refresh: bool = False) -> URLOptimizationResult:
        """优化URL"""
        # 检查缓存
        if not force_refresh and url in self._cache:
            cached = self._cache[url]
            if (datetime.now() - cached.test_results[0].test_time).seconds < self._cache_ttl:
                return cached
        
        # 1. 分类URL
        metadata = self.classifier.classify(url)
        
        # 2. 测试原始URL访问性
        original_test = await self.test_url_access(url)
        metadata.is_blocked = original_test.status in (AccessStatus.BLOCKED, AccessStatus.TIMEOUT)
        
        # 3. 查找匹配的镜像规则
        rules = self.registry.find_rules(url)
        mirror_category = self.classifier.get_category_for_mirror(metadata)
        
        # 4. 获取候选镜像源
        candidate_mirrors: List[MirrorSource] = []
        if mirror_category:
            candidate_mirrors = self.registry.get_mirrors(mirror_category)
        
        # 应用规则生成新的URL
        optimized_url = url
        for rule in rules:
            new_url = self.apply_mirror_rule(url, rule)
            if new_url and new_url != url:
                # 创建新的镜像源
                mirror = MirrorSource(
                    name=rule.name,
                    url=new_url,
                    mirror_type=rule.mirror_type,
                    sync_frequency=rule.sync_frequency,
                    location=rule.location,
                    is_official=rule.is_official,
                )
                if mirror not in candidate_mirrors:
                    candidate_mirrors.append(mirror)
                if optimized_url == url:
                    optimized_url = new_url
        
        # 5. 并行测试所有镜像源
        all_tested = await self.test_all_mirrors(url, candidate_mirrors)
        
        # 6. 排序并选择最佳镜像
        all_tested.sort(key=lambda x: x.overall_score if x.status == AccessStatus.ACCESSIBLE else -100, reverse=True)
        
        # 7. 构建结果
        result = URLOptimizationResult(
            original_url=url,
            optimized_url=optimized_url,
            url_metadata=metadata,
            all_mirrors_tested=all_tested,
            test_results=[original_test],
            is_blocked=metadata.is_blocked,
            confidence=0.85,
        )
        
        # 选择推荐镜像
        accessible_mirrors = [m for m in all_tested if m.status == AccessStatus.ACCESSIBLE]
        if accessible_mirrors:
            result.recommended_mirror = accessible_mirrors[0]
            result.alternative_mirrors = accessible_mirrors[1:4]
            result.suggestions = self._generate_suggestions(result, original_test)
        
        # 更新缓存
        self._cache[url] = result
        
        return result
    
    def _generate_suggestions(
        self, result: URLOptimizationResult, original_test: URLTestResult
    ) -> List[str]:
        """生成建议"""
        suggestions = []
        
        if result.is_blocked:
            suggestions.append("原始链接访问受限，建议使用镜像源")
        
        if result.recommended_mirror:
            if result.recommended_mirror.is_official:
                suggestions.append(f"推荐使用官方镜像「{result.recommended_mirror.name}」")
            else:
                suggestions.append(f"推荐使用「{result.recommended_mirror.name}」镜像加速访问")
            
            if result.recommended_mirror.sync_frequency != "实时":
                suggestions.append(f"注意：{result.recommended_mirror.name}同步延迟约{result.recommended_mirror.sync_frequency}")
        
        if original_test.status == AccessStatus.SLOW:
            suggestions.append("原始链接访问缓慢，使用镜像可显著提升速度")
        
        # 如果有替代镜像
        if len(result.alternative_mirrors) > 0:
            suggestions.append(f"另有{len(result.alternative_mirrors)}个备用镜像可用")
        
        return suggestions
    
    def optimize_sync(self, url: str, force_refresh: bool = False) -> URLOptimizationResult:
        """同步版本优化"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.optimize(url, force_refresh))
    
    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "cache_size": len(self._cache),
            "classifier_stats": {
                "patterns_count": len(self.classifier.PATTERNS),
                "domain_map_count": len(self.classifier.DOMAIN_MAP),
            },
            "registry_stats": self.registry.get_statistics(),
        }


# 全局单例
_url_system: Optional[URLOptimizer] = None


def get_url_system() -> URLOptimizer:
    """获取URL智能系统单例"""
    global _url_system
    if _url_system is None:
        _url_system = URLOptimizer()
    return _url_system


async def optimize_url_async(url: str) -> URLOptimizationResult:
    """异步优化URL"""
    system = get_url_system()
    return await system.optimize(url)


def optimize_url(url: str) -> URLOptimizationResult:
    """同步优化URL"""
    system = get_url_system()
    return system.optimize_sync(url)


class URLIntelligenceSystem:
    """URL智能系统封装类"""
    
    def __init__(self):
        self._optimizer = get_url_system()
    
    async def optimize_async(self, url: str) -> URLOptimizationResult:
        """异步优化"""
        return await self._optimizer.optimize(url)
    
    def optimize(self, url: str) -> URLOptimizationResult:
        """同步优化"""
        return self._optimizer.optimize_sync(url)
    
    def process_urls(self, urls: List[str]) -> List[URLOptimizationResult]:
        """批量处理URL"""
        results = []
        for url in urls:
            try:
                result = self.optimize(url)
                results.append(result)
            except Exception as e:
                logger.info(f"处理URL失败 {url}: {e}")
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计"""
        return self._optimizer.get_statistics()
    
    def clear_cache(self):
        """清除缓存"""
        self._optimizer.clear_cache()
