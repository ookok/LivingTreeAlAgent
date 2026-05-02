"""
统一搜索调度器

整合所有组件，提供统一的搜索接口
"""

import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
import hashlib
import json
from pathlib import Path

from .models import SearchResult, TierLevel, QueryType, QueryContext, FusionResult
from .tier_router import TierRouter
from .result_fusion import ResultFusion
from .api_monitor import APIMonitor, MonitorConfig
from .tier4_engines import LocalCacheEngine


class SearchScheduler:
    """
    统一搜索调度器
    
    整合TierRouter、ResultFusion、APIMonitor
    提供端到端的搜索服务
    """
    
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        enable_monitoring: bool = True
    ):
        # 核心组件
        self.router = TierRouter()
        self.fusion = ResultFusion()
        self.monitor = APIMonitor() if enable_monitoring else None
        
        # 本地缓存
        self.cache_engine = LocalCacheEngine(cache_dir)
        
        # 配置
        self.cache_dir = cache_dir or Path.home() / ".hermes-desktop" / "tiered_search"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 缓存配置
        self.cache_ttl = {
            QueryType.NEWS: 3600,  # 1小时
            QueryType.KNOWLEDGE: 86400,  # 24小时
            QueryType.TECHNICAL: 604800,  # 7天
            QueryType.LIFE: 43200,  # 12小时
            QueryType.ACADEMIC: 86400,  # 24小时
            QueryType.ENTERTAINMENT: 86400,  # 24小时
            QueryType.POLICY: 86400,  # 24小时
            QueryType.GENERAL: 43200,  # 12小时
        }
        
        # 内存缓存
        self._memory_cache: Dict[str, tuple[FusionResult, datetime]] = {}
        self._memory_cache_max = 1000
    
    async def search(
        self,
        query: str,
        num_results: int = 10,
        max_tier: TierLevel = TierLevel.TIER_3_GLOBAL,
        use_cache: bool = True,
        timeout: float = 15.0
    ) -> FusionResult:
        """
        执行统一搜索
        
        Args:
            query: 搜索查询
            num_results: 返回结果数量
            max_tier: 最大使用的API层级
            use_cache: 是否使用缓存
            timeout: 超时时间（秒）
            
        Returns:
            FusionResult: 融合后的搜索结果
        """
        # 构建查询上下文
        ctx = QueryContext.from_query(query)
        
        # 检查缓存
        if use_cache:
            cached = self._get_from_cache(query, ctx.query_type)
            if cached:
                return cached
        
        # 执行搜索
        all_results: List[SearchResult] = []
        
        try:
            # 1. 首先检查本地缓存引擎
            local_results = await self.cache_engine.search(query, num_results)
            all_results.extend(local_results)
            
            # 2. 如果本地缓存不足，调用TierRouter
            if len(all_results) < num_results:
                need = num_results - len(all_results)
                router_results = await self.router.search(
                    query, 
                    num_results=need,
                    max_tier=max_tier,
                    timeout=timeout
                )
                all_results.extend(router_results)
                
                # 保存到本地缓存
                if router_results:
                    await self._save_to_cache(query, router_results)
            
        except Exception as e:
            print(f"[SearchScheduler] Search failed: {e}")
        
        # 3. 融合结果
        fusion_result = self.fusion.fuse(
            all_results,
            query=query,
            query_type=ctx.query_type,
            max_results=num_results
        )
        
        # 4. 更新缓存
        if use_cache and fusion_result.results:
            self._save_to_memory_cache(query, ctx.query_type, fusion_result)
        
        # 5. 记录监控数据
        if self.monitor:
            for result in fusion_result.results:
                self.monitor.record_request(
                    result.api_name,
                    success=True,
                    response_time=0.0
                )
        
        return fusion_result
    
    def _get_cache_key(self, query: str, query_type: QueryType) -> str:
        """生成缓存键"""
        key = f"{query}:{query_type.value}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def _get_from_cache(self, query: str, query_type: QueryType) -> Optional[FusionResult]:
        """从缓存获取"""
        cache_key = self._get_cache_key(query, query_type)
        ttl = self.cache_ttl.get(query_type, 43200)
        
        # 检查内存缓存
        if cache_key in self._memory_cache:
            result, cached_at = self._memory_cache[cache_key]
            if (datetime.now() - cached_at).total_seconds() < ttl:
                result.cached = True
                result.cache_timestamp = cached_at
                return result
        
        # 检查磁盘缓存
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                if (datetime.now() - mtime).total_seconds() < ttl:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 转换为FusionResult
                    results = [
                        SearchResult(
                            title=r["title"],
                            url=r["url"],
                            snippet=r["snippet"],
                            source=r["source"],
                            date=r.get("date"),
                        )
                        for r in data.get("results", [])
                    ]
                    
                    fusion_result = self.fusion.fuse(
                        results,
                        query=query,
                        query_type=query_type,
                    )
                    fusion_result.cached = True
                    fusion_result.cache_timestamp = mtime
                    
                    # 更新内存缓存
                    self._update_memory_cache(cache_key, query_type, fusion_result)
                    
                    return fusion_result
            except Exception as e:
                print(f"[SearchScheduler] Load cache failed: {e}")
        
        return None
    
    async def _save_to_cache(self, query: str, results: List[SearchResult]):
        """保存到本地缓存"""
        self.cache_engine.save_to_cache(query, results)
    
    def _save_to_memory_cache(
        self, 
        query: str, 
        query_type: QueryType, 
        result: FusionResult
    ):
        """保存到内存缓存"""
        cache_key = self._get_cache_key(query, query_type)
        self._update_memory_cache(cache_key, query_type, result)
    
    def _update_memory_cache(
        self, 
        cache_key: str, 
        query_type: QueryType, 
        result: FusionResult
    ):
        """更新内存缓存（LRU）"""
        if len(self._memory_cache) >= self._memory_cache_max:
            # 移除最老的
            oldest_key = min(
                self._memory_cache.keys(),
                key=lambda k: self._memory_cache[k][1]
            )
            del self._memory_cache[oldest_key]
        
        self._memory_cache[cache_key] = (result, datetime.now())
    
    def clear_cache(self):
        """清空缓存"""
        # 内存缓存
        self._memory_cache.clear()
        
        # 磁盘缓存
        for f in self.cache_dir.glob("*.json"):
            try:
                f.unlink()
            except Exception:
                pass
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "memory_cache_size": len(self._memory_cache),
            "router_stats": self.router.get_stats(),
            "fusion_stats": {},
        }
        
        if self.monitor:
            stats["monitor_summary"] = self.monitor.get_summary()
        
        return stats
    
    def get_health_report(self) -> Dict[str, Any]:
        """获取健康报告"""
        return {
            "router_health": {
                name: {
                    "status": h.status.value,
                    "success_rate": h.success_rate,
                    "avg_response_time": h.avg_response_time,
                    "consecutive_failures": h.consecutive_failures,
                }
                for name, h in self.router.get_health_report().items()
            },
            "summary": self.monitor.get_summary() if self.monitor else {},
        }
    
    async def health_check(self) -> Dict[str, bool]:
        """执行健康检查"""
        health_status = {}
        
        for api_name in self.router.get_available_engines():
            if self.monitor:
                health_status[api_name] = self.monitor.is_api_available(api_name)
            else:
                health_status[api_name] = True
        
        return health_status


__all__ = ["SearchScheduler"]
