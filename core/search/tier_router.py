"""
智能路由与调度系统

核心功能：
- 根据查询类型自动选择最优API
- 多API并发调用
- 失败自动降级
- 智能权重调整
"""

import asyncio
from typing import List, Optional, Dict, Tuple
from datetime import datetime
import time

from .models import (
    SearchResult, 
    TierLevel, 
    QueryType, 
    QueryContext,
    APIConfig,
    APIHealth,
    APIStatus,
    RateLimiter,
)
from .tier1_engines import (
    BaiduEngine, SogouEngine, So360Engine, 
    TiangongEngine, JuhuasuanEngine,
)
from .tier2_engines import (
    ZhihuEngine, DoubanEngine, GaodeEngine,
    HefengEngine, GithubEngine,
)
from .tier3_engines import (
    DuckDuckGoEngine, WikipediaEngine, OpenLibraryEngine,
)
from .tier4_engines import (
    LocalCacheEngine, KnowledgeBaseEngine, SemanticsCacheEngine,
)

from core.logger import get_logger
logger = get_logger('search.tier_router')


class TierRouter:
    """
    智能路由管理器
    
    根据查询类型、API健康状态、速率限制等因素
    自动选择最优的API组合进行搜索
    """
    
    def __init__(self):
        # 初始化所有引擎
        self._engines: Dict[str, any] = {}
        self._health: Dict[str, APIHealth] = {}
        self._rate_limiters: Dict[str, RateLimiter] = {}
        
        # 初始化Tier-1引擎（国内高稳定性）
        self._register_engine(BaiduEngine())
        self._register_engine(SogouEngine())
        self._register_engine(So360Engine())
        self._register_engine(TiangongEngine())
        self._register_engine(JuhuasuanEngine())
        
        # 初始化Tier-2引擎（国内专业垂直）
        self._register_engine(ZhihuEngine())
        self._register_engine(DoubanEngine())
        self._register_engine(GaodeEngine())
        self._register_engine(HefengEngine())
        self._register_engine(GithubEngine())
        
        # 初始化Tier-3引擎（国外免费）
        self._register_engine(DuckDuckGoEngine())
        self._register_engine(WikipediaEngine())
        self._register_engine(OpenLibraryEngine())
        
        # 初始化Tier-4引擎（备用方案）
        self._register_engine(LocalCacheEngine())
        self._register_engine(KnowledgeBaseEngine())
        self._register_engine(SemanticsCacheEngine())
        
        # 查询类型到API的映射
        self._type_to_apis: Dict[QueryType, List[str]] = {
            QueryType.NEWS: ["baidu", "sogou", "tiangong", "zhihu"],
            QueryType.KNOWLEDGE: ["baidu", "wikipedia", "sogou"],
            QueryType.TECHNICAL: ["github", "zhihu", "stackoverflow"],
            QueryType.LIFE: ["gaode", "hefeng", "baidu"],
            QueryType.ACADEMIC: ["zhihu", "wikipedia", "arxiv"],
            QueryType.ENTERTAINMENT: ["douban", "baidu", "sogou"],
            QueryType.POLICY: ["baidu", "sogou", "gov"],
            QueryType.GENERAL: ["baidu", "sogou", "duckduckgo"],
        }
        
        # API权重配置
        self._weights: Dict[str, float] = {}
        self._init_weights()
    
    def _init_weights(self):
        """初始化API权重"""
        # Tier-1权重（国内高稳定性）
        tier1_weights = {
            "baidu": 1.0,
            "sogou": 0.8,
            "so360": 0.6,
            "tiangong": 0.7,
            "juhuasuan": 0.5,
        }
        
        # Tier-2权重（专业垂直）
        tier2_weights = {
            "github": 1.0,
            "zhihu": 0.9,
            "douban": 0.8,
            "gaode": 0.7,
            "hefeng": 0.7,
        }
        
        # Tier-3权重（国外免费）
        tier3_weights = {
            "duckduckgo": 0.9,
            "wikipedia": 0.8,
            "openlibrary": 0.6,
        }
        
        # Tier-4权重（备用）
        tier4_weights = {
            "local_cache": 1.0,
            "knowledge_base": 0.8,
            "semantic_cache": 0.7,
        }
        
        self._weights = {**tier1_weights, **tier2_weights, **tier3_weights, **tier4_weights}
    
    def _register_engine(self, engine):
        """注册引擎"""
        name = engine.name
        self._engines[name] = engine
        self._health[name] = APIHealth(api_name=name)
        
        # 创建速率限制器
        config = getattr(engine, 'config', None)
        if config and hasattr(config, 'rate_limit'):
            rate_per_minute = config.get_rate_per_minute() if hasattr(config, 'get_rate_per_minute') else 100
            self._rate_limiters[name] = RateLimiter(
                max_requests=rate_per_minute,
                window_seconds=60
            )
        else:
            self._rate_limiters[name] = RateLimiter(max_requests=100, window_seconds=60)
    
    def get_engines_for_query(self, ctx: QueryContext) -> List[str]:
        """
        根据查询上下文获取适合的API列表
        
        优先级排序：
        1. 查询类型匹配
        2. API健康状态
        3. 速率限制余量
        4. 中文支持
        """
        # 获取该查询类型对应的API
        apis = self._type_to_apis.get(ctx.query_type, self._type_to_apis[QueryType.GENERAL])
        
        # 如果需要中文，排除不支持中文的API
        if ctx.require_cn:
            apis = [api for api in apis if getattr(self._engines.get(api), 'cn_support', True)]
        
        # 如果需要最新，排除知识库
        if ctx.require_recent:
            apis = [api for api in apis if api not in ["knowledge_base", "local_cache"]]
        
        # 过滤和排序
        ranked_apis = []
        for api in apis:
            if api not in self._engines:
                continue
            
            health = self._health.get(api)
            limiter = self._rate_limiters.get(api)
            
            # 检查API是否可用
            if health and health.status == APIStatus.DISABLED:
                continue
            
            # 检查速率限制
            if limiter and not limiter.is_allowed():
                continue
            
            # 计算综合得分
            score = self._calculate_api_score(api, ctx)
            ranked_apis.append((api, score))
        
        # 按得分排序
        ranked_apis.sort(key=lambda x: x[1], reverse=True)
        
        return [api for api, _ in ranked_apis]
    
    def _calculate_api_score(self, api: str, ctx: QueryContext) -> float:
        """计算API评分"""
        score = 0.0
        
        # 权重
        score += self._weights.get(api, 0.5) * 10
        
        # 健康状态
        health = self._health.get(api)
        if health:
            score += health.success_rate * 5
            score -= health.avg_response_time * 0.1  # 响应时间越短越好
        
        # 速率限制余量
        limiter = self._rate_limiters.get(api)
        if limiter:
            remaining = limiter.get_remaining()
            score += (remaining / limiter.max_requests) * 3
        
        # 偏好来源匹配
        if ctx.preferred_sources:
            engine = self._engines.get(api)
            if engine:
                config = getattr(engine, 'config', None)
                if config and hasattr(config, 'description'):
                    desc = config.description.lower()
                    if any(src in desc for src in ctx.preferred_sources):
                        score += 5
        
        return score
    
    async def search(
        self, 
        query: str, 
        num_results: int = 10,
        max_tier: TierLevel = TierLevel.TIER_3_GLOBAL,
        timeout: float = 10.0
    ) -> List[SearchResult]:
        """
        执行分布式搜索
        
        Args:
            query: 搜索查询
            num_results: 返回结果数量
            max_tier: 最大使用的API层级
            timeout: 超时时间（秒）
            
        Returns:
            搜索结果列表
        """
        # 构建查询上下文
        ctx = QueryContext.from_query(query)
        
        # 获取适合的API列表
        apis = self.get_engines_for_query(ctx)
        
        # 按层级分组
        tier_groups = {
            TierLevel.TIER_1_CN_HIGH: [],
            TierLevel.TIER_2_CN_VERTICAL: [],
            TierLevel.TIER_3_GLOBAL: [],
            TierLevel.TIER_4_FALLBACK: [],
        }
        
        for api in apis:
            engine = self._engines.get(api)
            if engine:
                tier = getattr(engine, 'tier', TierLevel.TIER_3_GLOBAL)
                if tier.value <= max_tier.value:
                    tier_groups[tier].append(api)
        
        # 并发搜索
        all_results = []
        results_collected = 0
        target_results = num_results
        
        for tier in [TierLevel.TIER_1_CN_HIGH, TierLevel.TIER_2_CN_VERTICAL, 
                     TierLevel.TIER_3_GLOBAL, TierLevel.TIER_4_FALLBACK]:
            
            if results_collected >= target_results:
                break
            
            if tier.value > max_tier.value:
                continue
            
            tier_apis = tier_groups.get(tier, [])
            if not tier_apis:
                continue
            
            # 同一层级的API并发调用
            tasks = []
            for api in tier_apis[:3]:  # 最多3个API
                if api in self._rate_limiters:
                    self._rate_limiters[api].record_request()
                
                engine = self._engines[api]
                need = target_results - results_collected
                tasks.append(self._search_with_engine(api, engine, query, need))
            
            # 等待结果
            try:
                tier_results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=timeout
                )
                
                for results in tier_results:
                    if isinstance(results, list):
                        all_results.extend(results)
                        results_collected += len(results)
                        
            except asyncio.TimeoutError:
                logger.info(f"[TierRouter] Tier {tier.value} timeout")
                continue
        
        return all_results[:num_results]
    
    async def _search_with_engine(
        self, 
        api_name: str, 
        engine, 
        query: str, 
        num_results: int
    ) -> List[SearchResult]:
        """使用指定引擎搜索"""
        start_time = time.time()
        
        try:
            results = await engine.search(query, num_results)
            
            # 更新健康状态
            elapsed = time.time() - start_time
            self._update_health(api_name, success=True, response_time=elapsed)
            
            return results
            
        except Exception as e:
            logger.info(f"[TierRouter] Engine {api_name} failed: {e}")
            self._update_health(api_name, success=False)
            return []
    
    def _update_health(self, api_name: str, success: bool, response_time: float = 0.0):
        """更新API健康状态"""
        health = self._health.get(api_name)
        if not health:
            return
        
        health.total_requests += 1
        
        if success:
            health.failed_requests = 0
            health.consecutive_failures = 0
            health.last_success = datetime.now()
            
            # 更新平均响应时间
            if response_time > 0:
                health.avg_response_time = (
                    health.avg_response_time * 0.7 + response_time * 0.3
                )
        else:
            health.failed_requests += 1
            health.consecutive_failures += 1
            health.last_failure = datetime.now()
        
        # 更新成功率
        health.success_rate = 1.0 - (health.failed_requests / max(health.total_requests, 1))
        
        # 判断状态
        if health.consecutive_failures >= 5:
            health.status = APIStatus.DISABLED
        elif health.consecutive_failures >= 2:
            health.status = APIStatus.FAILING
        elif health.success_rate < 0.8:
            health.status = APIStatus.DEGRADED
        else:
            health.status = APIStatus.HEALTHY
    
    def get_health_report(self) -> Dict[str, APIHealth]:
        """获取API健康报告"""
        return self._health.copy()
    
    def get_available_engines(self) -> List[str]:
        """获取所有可用的引擎名称"""
        return [
            name for name, health in self._health.items()
            if health.status != APIStatus.DISABLED
        ]
    
    def get_stats(self) -> Dict:
        """获取路由统计"""
        total_requests = sum(h.total_requests for h in self._health.values())
        total_failures = sum(h.failed_requests for h in self._health.values())
        
        return {
            "total_requests": total_requests,
            "total_failures": total_failures,
            "overall_success_rate": 1.0 - (total_failures / max(total_requests, 1)),
            "healthy_apis": sum(1 for h in self._health.values() if h.status == APIStatus.HEALTHY),
            "degraded_apis": sum(1 for h in self._health.values() if h.status == APIStatus.DEGRADED),
            "disabled_apis": sum(1 for h in self._health.values() if h.status == APIStatus.DISABLED),
        }


__all__ = ["TierRouter"]
