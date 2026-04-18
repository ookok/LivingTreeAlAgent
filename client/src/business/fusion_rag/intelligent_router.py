"""
智能路由引擎 (Intelligent Router)
动态选择最优检索策略和层级权重

功能:
- 基于意图的路由决策
- 动态权重调整
- 延迟预算分配
- 并行/串行策略选择
"""

import time
from typing import Dict, Any, List, Optional
from collections import defaultdict


class IntelligentRouter:
    """智能路由引擎"""
    
    def __init__(self):
        """初始化路由引擎"""
        
        # 各层层级配置
        self.layer_configs = {
            "exact_cache": {
                "max_latency_ms": 5,
                "weight_base": 0.35,
                "priority": 1,
                "parallel": True
            },
            "session_cache": {
                "max_latency_ms": 15,
                "weight_base": 0.25,
                "priority": 2,
                "parallel": True
            },
            "knowledge_base": {
                "max_latency_ms": 50,
                "weight_base": 0.30,
                "priority": 3,
                "parallel": True
            },
            "database": {
                "max_latency_ms": 100,
                "weight_base": 0.10,
                "priority": 4,
                "parallel": True
            }
        }
        
        # 意图到层级的映射
        self.intent_layer_map = {
            "factual": ["exact_cache", "knowledge_base", "database"],
            "conversational": ["exact_cache", "session_cache", "knowledge_base"],
            "procedural": ["exact_cache", "knowledge_base"],
            "creative": ["exact_cache", "session_cache"],
            "hybrid": ["exact_cache", "session_cache", "knowledge_base", "database"]
        }
        
        # 策略配置
        self.strategies = {
            "speed_first": {
                "description": "速度优先",
                "prefer_cache": True,
                "max_layers": 2,
                "llm_fallback_threshold": 0.7
            },
            "accuracy_first": {
                "description": "准确优先",
                "prefer_cache": False,
                "max_layers": 4,
                "llm_fallback_threshold": 0.9
            },
            "balanced": {
                "description": "平衡模式",
                "prefer_cache": True,
                "max_layers": 3,
                "llm_fallback_threshold": 0.8
            }
        }
        
        # 统计
        self.route_count = 0
        self.strategy_usage = defaultdict(int)
    
    def _adjust_weights_for_intent(
        self,
        base_weights: Dict[str, float],
        intent_result: Dict[str, Any]
    ) -> Dict[str, float]:
        """根据意图调整权重"""
        weights = base_weights.copy()
        primary = intent_result["primary"]
        confidence = intent_result["confidence"]
        features = intent_result.get("features", {})
        
        # 基础调整
        if primary == "factual":
            weights["knowledge_base"] = weights.get("knowledge_base", 0) + 0.15 * confidence
            weights["database"] = weights.get("database", 0) + 0.10 * confidence
        
        elif primary == "conversational":
            weights["session_cache"] = weights.get("session_cache", 0) + 0.20 * confidence
        
        elif primary == "procedural":
            weights["knowledge_base"] = weights.get("knowledge_base", 0) + 0.15 * confidence
            weights["exact_cache"] = weights.get("exact_cache", 0) + 0.10 * confidence
        
        elif primary == "creative":
            weights["session_cache"] = weights.get("session_cache", 0) + 0.15 * confidence
        
        # 特征调整
        if features.get("has_context_word"):
            weights["session_cache"] = weights.get("session_cache", 0) + 0.15
        
        if features.get("has_knowledge_word"):
            weights["knowledge_base"] = weights.get("knowledge_base", 0) + 0.10
        
        if features.get("has_technical_terms"):
            weights["database"] = weights.get("database", 0) + 0.05
        
        # 归一化
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        
        return weights
    
    def _estimate_latency(
        self,
        layers: List[str],
        weights: Dict[str, float]
    ) -> Dict[str, float]:
        """估算各层延迟"""
        latencies = {}
        
        for layer in layers:
            config = self.layer_configs.get(layer, {})
            base_latency = config.get("max_latency_ms", 50)
            
            # 根据权重调整 (权重越高，越值得等待)
            weight_factor = weights.get(layer, 0.5)
            adjusted_latency = base_latency * (1.2 - weight_factor * 0.4)
            
            latencies[layer] = adjusted_latency
        
        return latencies
    
    def _should_use_llm(
        self,
        intent: Dict[str, Any],
        fused_results: List[Dict],
        strategy: str
    ) -> tuple:
        """
        判断是否需要使用 LLM
        
        Returns:
            (needs_llm, reason)
        """
        strategy_config = self.strategies.get(strategy, self.strategies["balanced"])
        threshold = strategy_config["llm_fallback_threshold"]
        
        # 无检索结果
        if not fused_results:
            return True, "no_results"
        
        # 最高分数低于阈值
        max_score = max((r.get("fused_score", 0) for r in fused_results), default=0)
        if max_score < threshold:
            return True, f"low_confidence ({max_score:.2f} < {threshold})"
        
        # 创意类查询
        if intent["primary"] == "creative":
            return True, "creative_intent"
        
        # 检索结果不完整
        if intent["features"].get("complexity_score", 0) > 0.7:
            return True, "high_complexity"
        
        # 结果数量不足
        if len(fused_results) < 2:
            return True, "insufficient_results"
        
        return False, "good_retrieval"
    
    def route(
        self,
        query: str,
        intent: Optional[Dict[str, Any]] = None,
        strategy: str = "balanced",
        latency_budget_ms: float = 100
    ) -> Dict[str, Any]:
        """
        路由决策
        
        Args:
            query: 查询文本
            intent: 意图分类结果 (可选)
            strategy: 路由策略
            latency_budget_ms: 延迟预算
            
        Returns:
            {
                "strategy": "balanced",
                "enabled_layers": [...],
                "layer_weights": {...},
                "estimated_latencies": {...},
                "total_estimated_latency": 50.0,
                "needs_llm": False,
                "llm_reason": ""
            }
        """
        self.route_count += 1
        self.strategy_usage[strategy] += 1
        
        strategy_config = self.strategies.get(strategy, self.strategies["balanced"])
        
        # 确定启用的层级
        if intent:
            enabled_layers = self.intent_layer_map.get(
                intent["primary"],
                self.intent_layer_map["factual"]
            )
            # 限制层级数量
            max_layers = strategy_config["max_layers"]
            enabled_layers = enabled_layers[:max_layers]
        else:
            enabled_layers = list(self.layer_configs.keys())[:strategy_config["max_layers"]]
        
        # 调整权重
        base_weights = {
            layer: self.layer_configs[layer]["weight_base"]
            for layer in enabled_layers
        }
        
        if intent:
            adjusted_weights = self._adjust_weights_for_intent(base_weights, intent)
        else:
            adjusted_weights = base_weights
        
        # 估算延迟
        latencies = self._estimate_latency(enabled_layers, adjusted_weights)
        total_latency = max(latencies.values()) if latencies else 0  # 并行执行取最大值
        
        # 判断 LLM 使用
        needs_llm, llm_reason = self._should_use_llm(
            intent or {},
            [],  # 初始无融合结果
            strategy
        )
        
        return {
            "strategy": strategy,
            "strategy_description": strategy_config["description"],
            "enabled_layers": enabled_layers,
            "layer_weights": adjusted_weights,
            "estimated_latencies": latencies,
            "total_estimated_latency": total_latency,
            "latency_within_budget": total_latency <= latency_budget_ms,
            "needs_llm": needs_llm,
            "llm_reason": llm_reason,
            "prefer_parallel": strategy_config["prefer_cache"],
            "max_layers": strategy_config["max_layers"]
        }
    
    def route_batch(
        self,
        queries: List[str],
        intents: Optional[List[Dict]] = None
    ) -> List[Dict[str, Any]]:
        """
        批量路由
        
        Args:
            queries: 查询列表
            intents: 意图列表 (可选)
            
        Returns:
            路由决策列表
        """
        routes = []
        
        for i, query in enumerate(queries):
            intent = intents[i] if intents and i < len(intents) else None
            route = self.route(query, intent)
            routes.append(route)
        
        return routes
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_routes": self.route_count,
            "strategy_usage": dict(self.strategy_usage),
            "strategy_percentages": {
                k: v / self.route_count * 100 if self.route_count > 0 else 0
                for k, v in self.strategy_usage.items()
            }
        }
