"""
智能路由决策系统
"""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


class RouteDecision(Enum):
    L1_CACHE = "L1"
    L2_LIGHTWEIGHT = "L2"
    L3_STANDARD = "L3"
    L4_ENHANCED = "L4"


@dataclass
class RouteFeatures:
    query_length: int = 0
    query_complexity: float = 0.0
    context_relevance: float = 0.0
    realtime_score: float = 0.0
    resource_availability: float = 1.0


@dataclass
class RouteResult:
    decision: RouteDecision
    confidence: float
    features: RouteFeatures
    reasoning: str


class IntelligentRouter:
    """智能路由系统"""
    
    def __init__(self):
        self.system_load = 0.5
        self.gpu_memory = 0.8
        
        self.complex_keywords = ["分析", "评估", "设计", "比较", "证明", "深度", 
                                "analyze", "evaluate", "design", "complex"]
        self.realtime_keywords = ["现在", "今天", "当前", "最新", "now", "today"]
    
    def route(self, query: str, context: str = None, history: List[Dict] = None) -> RouteResult:
        """执行路由决策"""
        features = self._extract_features(query, history)
        return self._decide(features)
    
    def _extract_features(self, query: str, history: List[Dict] = None) -> RouteFeatures:
        """提取特征"""
        features = RouteFeatures()
        features.query_length = len(query)
        
        complex_count = sum(1 for kw in self.complex_keywords if kw in query)
        features.query_complexity = min(1.0, complex_count * 0.2 + len(query) / 1000)
        
        if history:
            features.context_relevance = min(1.0, len(history) / 10)
        
        features.realtime_score = sum(1 for kw in self.realtime_keywords if kw in query) * 0.3
        
        features.resource_availability = min(1.0, (1 - self.system_load) * 0.5 + self.gpu_memory * 0.5)
        
        return features
    
    def _decide(self, features: RouteFeatures) -> RouteResult:
        """做出决策"""
        instant_score = (1 - features.query_length / 500) * 0.3 + features.realtime_score * 0.7
        quality_score = features.query_complexity * 0.5 + features.context_relevance * 0.5
        
        if instant_score > 0.8:
            return RouteResult(RouteDecision.L1_CACHE, instant_score, features, "即时响应优先")
        elif features.resource_availability < 0.3:
            return RouteResult(RouteDecision.L2_LIGHTWEIGHT, 1 - features.resource_availability, features, "资源不足")
        elif quality_score < 0.3:
            return RouteResult(RouteDecision.L2_LIGHTWEIGHT, 1 - quality_score, features, "简单任务")
        elif 0.3 <= quality_score <= 0.7:
            return RouteResult(RouteDecision.L3_STANDARD, 1 - abs(quality_score - 0.5), features, "中等复杂度")
        else:
            return RouteResult(RouteDecision.L4_ENHANCED, quality_score, features, "复杂任务")
    
    def update_load(self, system_load: float, gpu_memory: float = 0.8):
        """更新系统状态"""
        self.system_load = max(0, min(1, system_load))
        self.gpu_memory = max(0, min(1, gpu_memory))
