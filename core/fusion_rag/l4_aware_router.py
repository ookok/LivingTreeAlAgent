"""
智能路由引擎增强版 (L4 穿透支持)
在原有路由决策基础上，增加 LLM/L4 执行层穿透支持
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
from enum import Enum

logger = logging.getLogger(__name__)


class LLMRouteDecision(Enum):
    """LLM 路由决策"""
    CACHE_HIT = "cache_hit"           # 缓存命中，无需 LLM
    LOW_CONFIDENCE = "low_confidence"  # 置信度低，需要 LLM
    NO_RESULTS = "no_results"          # 无检索结果，需要 LLM
    CREATIVE_INTENT = "creative"       # 创意意图，需要 LLM
    HIGH_COMPLEXITY = "complexity"    # 高复杂度，需要 LLM
    FORCE_L4 = "force_l4"             # 强制穿透 L4


class L4AwareRouter:
    """
    L4 感知路由引擎

    在原有 IntelligentRouter 基础上增加:
    1. L4 层配置（RelayFreeLLM）
    2. LLM 执行决策
    3. L4 穿透回调
    4. 零配置裸跑支持
    """

    def __init__(
        self,
        base_router: Optional[Any] = None,
        l4_executor: Optional[Any] = None,
        intent_classifier: Optional[Any] = None
    ):
        """
        Args:
            base_router: 基础路由引擎 (IntelligentRouter)
            l4_executor: L4 执行器 (L4RelayExecutor)
            intent_classifier: 意图分类器
        """
        self.base_router = base_router
        self.l4_executor = l4_executor
        self.intent_classifier = intent_classifier

        # L4 层配置
        self.l4_config = {
            "max_latency_ms": 5000,
            "weight_base": 0.0,  # 默认不启用 LLM
            "priority": 99,      # 最后执行
            "always_on": True,  # Ollama 默认启用
            "timeout": 120
        }

        # LLM 触发阈值
        self.llm_thresholds = {
            "speed_first": 0.7,
            "accuracy_first": 0.9,
            "balanced": 0.8
        }

        # 策略配置
        self.strategies = {
            "speed_first": {
                "description": "速度优先",
                "prefer_cache": True,
                "max_layers": 2,
                "llm_threshold": 0.7,
                "force_l4_on_cache_miss": False
            },
            "accuracy_first": {
                "description": "准确优先",
                "prefer_cache": False,
                "max_layers": 4,
                "llm_threshold": 0.9,
                "force_l4_on_cache_miss": True
            },
            "balanced": {
                "description": "平衡模式",
                "prefer_cache": True,
                "max_layers": 3,
                "llm_threshold": 0.8,
                "force_l4_on_cache_miss": True
            },
            "cache_only": {
                "description": "仅缓存",
                "prefer_cache": True,
                "max_layers": 4,
                "llm_threshold": 1.0,  # 永远不触发 LLM
                "force_l4_on_cache_miss": False
            },
            "llm_first": {
                "description": "LLM 优先",
                "prefer_cache": False,
                "max_layers": 0,  # 跳过缓存
                "llm_threshold": 0.0,  # 始终触发 LLM
                "force_l4_on_cache_miss": True
            }
        }

        # 意图到 LLM 路由的映射
        self.intent_llm_map = {
            "factual": {"threshold_adjust": 0.1, "prefer_l4": False},
            "conversational": {"threshold_adjust": -0.1, "prefer_l4": False},
            "procedural": {"threshold_adjust": 0.05, "prefer_l4": False},
            "creative": {"threshold_adjust": -0.2, "prefer_l4": True},
            "hybrid": {"threshold_adjust": 0.0, "prefer_l4": False}
        }

        # L4 穿透回调
        self._l4_callback: Optional[Callable] = None

        # 统计
        self._stats = {
            "total_routes": 0,
            "l4_executions": 0,
            "cache_hits": 0,
            "llm_triggered": 0,
            "strategies_used": {}
        }

        logger.info("[L4Router] L4 感知路由引擎初始化")

    def set_l4_callback(self, callback: Callable):
        """设置 L4 穿透回调"""
        self._l4_callback = callback

    def decide_llm_execution(
        self,
        query: str,
        fused_results: List[Dict],
        strategy: str = "balanced",
        intent: Optional[Dict[str, Any]] = None
    ) -> LLMRouteDecision:
        """
        决定是否需要穿透到 L4 执行

        Args:
            query: 查询文本
            fused_results: 融合后的检索结果
            strategy: 路由策略
            intent: 意图分类结果

        Returns:
            LLMRouteDecision 枚举
        """
        self._stats["total_routes"] += 1

        strategy_config = self.strategies.get(strategy, self.strategies["balanced"])
        threshold = strategy_config["llm_threshold"]

        # 意图调整
        if intent:
            intent_adjust = self.intent_llm_map.get(intent["primary"], {}).get("threshold_adjust", 0)
            threshold = max(0, min(1, threshold + intent_adjust))

        # 1. 缓存命中（高置信度）
        if fused_results:
            max_score = max((r.get("fused_score", 0) for r in fused_results), default=0)
            if max_score >= threshold:
                self._stats["cache_hits"] += 1
                return LLMRouteDecision.CACHE_HIT

            # 低置信度
            self._stats["llm_triggered"] += 1
            return LLMRouteDecision.LOW_CONFIDENCE

        # 2. 无检索结果
        self._stats["llm_triggered"] += 1
        if strategy_config.get("force_l4_on_cache_miss"):
            return LLMRouteDecision.FORCE_L4
        return LLMRouteDecision.NO_RESULTS

    async def execute_via_l4(
        self,
        messages: List[Dict[str, Any]],
        model: str = "auto",
        intent: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        通过 L4 执行

        Args:
            messages: 对话消息
            model: 模型
            intent: 意图
            **kwargs: 其他参数

        Returns:
            L4 执行结果
        """
        if self.l4_executor is None:
            raise L4RouterError("L4 执行器未配置")

        self._stats["l4_executions"] += 1

        # 执行 L4
        result = await self.l4_executor.execute(
            messages=messages,
            model=model,
            intent=intent,
            **kwargs
        )

        # 触发回调
        if self._l4_callback:
            try:
                if asyncio.iscoroutinefunction(self._l4_callback):
                    await self._l4_callback(messages, result)
                else:
                    self._l4_callback(messages, result)
            except Exception as e:
                logger.warning(f"[L4Router] L4 回调失败: {e}")

        return result

    def route_with_l4_decision(
        self,
        query: str,
        fused_results: List[Dict],
        strategy: str = "balanced",
        intent: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        路由决策（包含 L4 决策）

        Returns:
            {
                "enabled_layers": [...],
                "needs_l4": bool,
                "l4_decision": LLMRouteDecision,
                "l4_model": str,
                "l4_intent": str,
                ...
            }
        """
        # 基础路由决策
        base_route = {}
        if self.base_router:
            base_route = self.base_router.route(query, intent, strategy)

        # L4 决策
        l4_decision = self.decide_llm_execution(
            query, fused_results, strategy, intent
        )

        needs_l4 = l4_decision in [
            LLMRouteDecision.LOW_CONFIDENCE,
            LLMRouteDecision.NO_RESULTS,
            LLMRouteDecision.CREATIVE_INTENT,
            LLMRouteDecision.HIGH_COMPLEXITY,
            LLMRouteDecision.FORCE_L4
        ]

        # 确定 L4 模型
        l4_model = self._decide_l4_model(intent)

        # 确定 L4 意图标签
        l4_intent = self._decide_l4_intent(intent, l4_decision)

        return {
            **base_route,
            "needs_l4": needs_l4,
            "l4_decision": l4_decision.value,
            "l4_model": l4_model,
            "l4_intent": l4_intent,
            "l4_available": self.l4_executor is not None
        }

    def _decide_l4_model(self, intent: Optional[Dict[str, Any]]) -> str:
        """决定 L4 使用哪个模型"""
        if not intent:
            return "auto"

        primary = intent.get("primary", "")
        features = intent.get("features", {})

        # 代码类
        if features.get("has_code") or "code" in primary:
            return "deepseek-coder"

        # 推理类
        if features.get("has_math") or "reasoning" in primary:
            return "deepseek"

        # 创意类
        if primary == "creative":
            return "gpt-4"

        # 中文偏好
        if features.get("is_chinese"):
            return "zhipu"

        # 快速响应
        if features.get("is_short_query"):
            return "qwen2.5"

        return "auto"

    def _decide_l4_intent(
        self,
        intent: Optional[Dict[str, Any]],
        decision: LLMRouteDecision
    ) -> str:
        """决定 L4 意图标签"""
        if not intent:
            return "general"

        primary = intent.get("primary", "general")

        # 映射到 L4 路由意图
        intent_map = {
            "factual": "knowledge",
            "conversational": "chat",
            "procedural": "instruction",
            "creative": "creative",
            "hybrid": "general"
        }

        return intent_map.get(primary, "general")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            **self._stats,
            "l4_available": self.l4_executor is not None,
            "strategy_usage": dict(self._stats.get("strategies_used", {}))
        }


class L4RouterError(Exception):
    """L4 路由异常"""
    pass


# ==================== 快捷函数 ====================

_l4_router_instance: Optional[L4AwareRouter] = None


def get_l4_aware_router(
    base_router: Optional[Any] = None,
    l4_executor: Optional[Any] = None
) -> L4AwareRouter:
    """获取 L4 感知路由单例"""
    global _l4_router_instance
    if _l4_router_instance is None:
        _l4_router_instance = L4AwareRouter(
            base_router=base_router,
            l4_executor=l4_executor
        )
    return _l4_router_instance
