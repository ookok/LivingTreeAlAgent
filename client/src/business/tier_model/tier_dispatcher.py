"""
四级模型调度器
统一调度 L1-L4 四级处理引擎
"""

import time
import asyncio
from typing import Optional, Any, Dict, List, Callable
from dataclasses import dataclass
from enum import Enum
from threading import Lock
import logging

from .tier1_cache import Tier1Cache, CacheHit
from .tier2_lightweight import Tier2Lightweight, LightweightResult, QueryComplexity
from .tier3_standard import Tier3Standard, StandardResult, TaskType
from .tier4_enhanced import Tier4Enhanced, EnhancedResult, ProcessingMode
from .cache_manager import CacheManager


class DispatchResult:
    """调度结果"""
    
    def __init__(self, tier: str, response: Any, latency_ms: float = 0,
                 metadata: Dict = None):
        self.tier = tier
        self.response = response
        self.latency_ms = latency_ms
        self.metadata = metadata or {}
        self.timestamp = time.time()
    
    def to_dict(self) -> Dict:
        return {
            "tier": self.tier,
            "response": self.response,
            "latency_ms": self.latency_ms,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }


class DegradationMode(Enum):
    """降级模式"""
    NORMAL = "normal"
    HIGH_LOAD = "high_load"
    CRITICAL = "critical"
    FALLBACK = "fallback"


class TierDispatcher:
    """
    四级模型调度器
    统一管理 L1-L4 四级处理引擎
    """
    
    def __init__(self, cache_manager: CacheManager = None):
        self.tier1 = Tier1Cache()
        self.tier2 = Tier2Lightweight()
        self.tier3 = Tier3Standard()
        self.tier4 = Tier4Enhanced()
        self.cache_manager = cache_manager or CacheManager()
        
        self._current_load = 0.0
        self._degradation_mode = DegradationMode.NORMAL
        self._lock = Lock()
        self._request_counts = {"L1": 0, "L2": 0, "L3": 0, "L4": 0}
        self._latencies = {"L1": [], "L2": [], "L3": [], "L4": []}
        self.high_load_threshold = 0.7
        self.critical_load_threshold = 0.9
        self.logger = logging.getLogger(__name__)
    
    async def dispatch(self, query: str, context: str = None,
                      history: List[Dict] = None,
                      force_tier: str = None) -> DispatchResult:
        """调度请求到合适的层级"""
        start = time.perf_counter()
        
        if force_tier:
            target_tier = force_tier
        else:
            target_tier = await self._select_tier(query, context, history)
        
        try:
            if target_tier == "L1":
                result = await self._handle_tier1(query, context)
            elif target_tier == "L2":
                result = await self._handle_tier2(query, context)
            elif target_tier == "L3":
                result = await self._handle_tier3(query, context, history)
            else:
                result = await self._handle_tier4(query, context, history)
            
            latency = (time.perf_counter() - start) * 1000
            result.latency_ms = latency
            self._record_stats(target_tier, latency)
            
            if target_tier != "L1" and result.response:
                self.cache_manager.set(query, result.response, context)
            
            return result
            
        except Exception as e:
            self.logger.error(f"调度失败: {e}")
            return DispatchResult(
                tier="ERROR", response=f"处理出错: {str(e)}",
                latency_ms=(time.perf_counter() - start) * 1000,
                metadata={"error": str(e)}
            )
    
    async def _select_tier(self, query: str, context: str = None,
                          history: List[Dict] = None) -> str:
        """选择合适的处理层级"""
        mode = self._get_degradation_mode()
        
        if mode == DegradationMode.CRITICAL:
            return "L1"
        elif mode == DegradationMode.HIGH_LOAD:
            return "L1" if await self._is_cacheable(query) else "L2"
        
        if await self._is_cacheable(query):
            return "L1"
        
        complexity = self.tier2._classify_complexity(query)
        if complexity in (QueryComplexity.TRIVIAL, QueryComplexity.SIMPLE):
            return "L2"
        
        if len(query) < 500 and len(history or []) < 5:
            return "L3"
        
        return "L4"
    
    async def _is_cacheable(self, query: str) -> bool:
        """检查是否可缓存"""
        hit = self.tier1.get(query)
        return hit is not None
    
    def _get_degradation_mode(self) -> DegradationMode:
        """获取当前降级模式"""
        with self._lock:
            if self._current_load >= self.critical_load_threshold:
                return DegradationMode.CRITICAL
            elif self._current_load >= self.high_load_threshold:
                return DegradationMode.HIGH_LOAD
            return DegradationMode.NORMAL
    
    def update_load(self, load: float):
        """更新系统负载"""
        with self._lock:
            self._current_load = max(0, min(1, load))
    
    async def _handle_tier1(self, query: str, context: str = None) -> DispatchResult:
        """处理 L1 层请求"""
        hit = self.tier1.get(query, context)
        
        if hit:
            return DispatchResult(
                tier="L1", response=hit.response,
                latency_ms=hit.latency_ms, metadata={"cache_hit": True}
            )
        
        return DispatchResult(tier="L1", response=None, metadata={"cache_hit": False})
    
    async def _handle_tier2(self, query: str, context: str = None) -> DispatchResult:
        """处理 L2 层请求"""
        result = await self.tier2.process(query, context)
        
        if result.needs_upgrade:
            return await self._handle_tier3(query, context, None)
        
        return DispatchResult(
            tier="L2", response=result.response,
            metadata={"confidence": result.confidence, "complexity": result.complexity.value}
        )
    
    async def _handle_tier3(self, query: str, context: str = None,
                           history: List[Dict] = None) -> DispatchResult:
        """处理 L3 层请求"""
        result = await self.tier3.process(query, context, history)
        
        return DispatchResult(
            tier="L3", response=result.response,
            metadata={"task_type": result.task_type.value, "tokens": result.tokens_generated}
        )
    
    async def _handle_tier4(self, query: str, context: str = None,
                           history: List[Dict] = None) -> DispatchResult:
        """处理 L4 层请求"""
        result = await self.tier4.process(query, context, history)
        
        return DispatchResult(
            tier="L4", response=result.response,
            metadata={"model": result.model_used, "confidence": result.confidence}
        )
    
    def _record_stats(self, tier: str, latency: float):
        """记录统计信息"""
        with self._lock:
            self._request_counts[tier] = self._request_counts.get(tier, 0) + 1
            self._latencies[tier].append(latency)
            if len(self._latencies[tier]) > 100:
                self._latencies[tier] = self._latencies[tier][-100:]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            stats = {
                "current_load": self._current_load,
                "degradation_mode": self._get_degradation_mode().value,
                "request_counts": self._request_counts.copy(),
                "latencies": {}
            }
            
            for tier, latencies in self._latencies.items():
                if latencies:
                    sorted_lat = sorted(latencies)
                    stats["latencies"][tier] = {
                        "avg": sum(latencies) / len(latencies),
                        "min": min(latencies),
                        "max": max(latencies),
                        "p95": sorted_lat[int(len(sorted_lat) * 0.95)] if len(sorted_lat) >= 20 else max(latencies)
                    }
            
            stats["cache"] = self.cache_manager.get_combined_stats()
            return stats
    
    def interrupt(self):
        """中断当前处理"""
        self.tier4.interrupt()
