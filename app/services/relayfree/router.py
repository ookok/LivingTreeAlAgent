"""
RelayFreeLLM 智能路由
基于意图、优先级、健康状态的动态路由选择
"""

import re
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import logging

from .providers.base import BaseProvider, ProviderStatus

logger = logging.getLogger(__name__)


@dataclass
class RouteContext:
    """路由上下文"""
    model: str
    intent: Optional[str] = None  # code, reasoning, chinese, privacy, fast, cheap
    preferred_providers: List[str] = None
    fallback_enabled: bool = True


class IntelligentRouter:
    """
    智能路由 - 自动选择最优 Provider
    
    路由策略:
    1. 意图匹配 (Intent Routing)
    2. 优先级排序 (Priority)
    3. 健康状态过滤 (Health)
    4. 负载均衡 (Round-Robin)
    """

    def __init__(self, providers: Dict[str, BaseProvider], routing_rules: Dict[str, Any]):
        self.providers = providers
        self.routing_rules = routing_rules
        self._intent_map = routing_rules.get("intent_routing", {})
        self._priority_order = routing_rules.get("default_priority_order", list(providers.keys()))
        self._request_count: Dict[str, int] = {}  # 用于简单负载均衡

    def detect_intent(self, messages: List[Dict[str, Any]], model: str) -> str:
        """
        检测用户意图
        
        基于消息内容和模型名推断
        """
        # 合并所有消息文本
        full_text = " ".join([
            msg.get("content", "") for msg in messages
        ]).lower()
        
        # 意图关键词检测
        intent_keywords = {
            "code": ["code", "python", "javascript", "function", "class", "def ", "import ", "bug", "debug", "api", "sql"],
            "reasoning": ["think", "reason", "analyze", "explain", "why", "logic", "solve", "思考", "分析"],
            "chinese": ["中文", " chinese", "中国", "什么", "怎么", "如何", "为什么"],
            "privacy": ["private", "local", "离线", "本地", "隐私", "secret", "confidential"],
            "fast": ["quick", "fast", "simple", "short", "快", "简单", "快速"],
            "cheap": ["free", "cheap", "cost", "budget", "免费", "省钱"]
        }
        
        scores: Dict[str, int] = {}
        for intent, keywords in intent_keywords.items():
            score = sum(1 for kw in keywords if kw in full_text)
            if score > 0:
                scores[intent] = score
        
        # 如果模型名包含提示
        model_lower = model.lower()
        if any(x in model_lower for x in ["code", "coder"]):
            scores["code"] = scores.get("code", 0) + 3
        if any(x in model_lower for x in ["reason", "think"]):
            scores["reasoning"] = scores.get("reasoning", 0) + 3
        
        # 返回得分最高的意图
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        
        return "general"

    def get_available_providers(
        self, 
        context: RouteContext,
        exclude_unhealthy: bool = True
    ) -> List[BaseProvider]:
        """
        获取可用 Provider 列表
        
        按优先级排序，过滤不健康的
        """
        available = []
        
        # 1. 如果有意图，按意图路由
        if context.intent and context.intent in self._intent_map:
            intent_providers = self._intent_map[context.intent]
            for pid in intent_providers:
                if pid in self.providers:
                    p = self.providers[pid]
                    if not exclude_unhealthy or p.is_healthy:
                        available.append(p)
        
        # 2. 否则按默认优先级
        if not available:
            for pid in self._priority_order:
                if pid in self.providers:
                    p = self.providers[pid]
                    if not exclude_unhealthy or p.is_healthy:
                        available.append(p)
        
        # 3. 按优先级排序 (从高到低)
        available.sort(key=lambda p: p.priority, reverse=True)
        
        # 4. 简单负载均衡 - 轮询分配请求
        for p in available:
            self._request_count[p.provider_id] = self._request_count.get(p.provider_id, 0) + 1
        
        return available

    async def route_and_execute(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        **kwargs
    ) -> Tuple[BaseProvider, Dict[str, Any]]:
        """
        路由并执行请求
        
        自动选择可用 Provider，失败时自动切换
        
        Returns:
            (使用的 provider, 响应数据)
        """
        # 检测意图
        intent = self.detect_intent(messages, model)
        context = RouteContext(model=model, intent=intent)
        
        # 获取可用 Provider 列表
        providers = self.get_available_providers(context)
        
        if not providers:
            raise Exception("没有可用的 Provider")
        
        last_error = None
        
        # 尝试每个 Provider
        for provider in providers:
            try:
                logger.info(f"[Router] 尝试 Provider: {provider.provider_id} (intent={intent})")
                
                if kwargs.get("stream"):
                    # 流式请求 - 返回生成器
                    return provider, provider.create_completion_stream(model, messages, **kwargs)
                else:
                    result = await provider.create_completion(model, messages, **kwargs)
                    return provider, result
                    
            except Exception as e:
                last_error = e
                logger.warning(f"[Router] Provider {provider.provider_id} 失败: {e}")
                provider.mark_unhealthy(str(e))
                continue
        
        raise Exception(f"所有 Provider 均失败: {last_error}")

    async def batch_route(
        self,
        requests: List[Tuple[str, List[Dict[str, Any]], Dict[str, Any]]]
    ) -> List[Tuple[BaseProvider, Dict[str, Any]]]:
        """
        批量路由 - 并行处理多个请求
        """
        tasks = [
            self.route_and_execute(model, messages, **kwargs)
            for model, messages, kwargs in requests
        ]
        return await asyncio.gather(*tasks)

    def get_routing_stats(self) -> Dict[str, Any]:
        """获取路由统计"""
        stats = {
            "total_providers": len(self.providers),
            "healthy_providers": sum(1 for p in self.providers.values() if p.is_healthy),
            "providers": {}
        }
        
        for pid, p in self.providers.items():
            stats["providers"][pid] = {
                "status": p.status.value,
                "is_healthy": p.is_healthy,
                "priority": p.priority,
                "request_count": self._request_count.get(pid, 0),
                "metrics": p.metrics.__dict__
            }
        
        return stats


class RouterRegistry:
    """路由注册表 - 管理多个路由实例"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._routers: Dict[str, IntelligentRouter] = {}
            cls._instance._active_router: Optional[IntelligentRouter] = None
        return cls._instance
    
    def register(self, name: str, router: IntelligentRouter):
        self._routers[name] = router
        if self._active_router is None:
            self._active_router = router
    
    def get(self, name: str = None) -> Optional[IntelligentRouter]:
        if name:
            return self._routers.get(name)
        return self._active_router
    
    def get_active_router(self) -> IntelligentRouter:
        if self._active_router is None:
            raise Exception("没有活跃的 Router")
        return self._active_router


# 全局注册表
_registry = RouterRegistry()


def get_router(name: str = None) -> IntelligentRouter:
    return _registry.get(name)


def register_router(name: str, router: IntelligentRouter):
    _registry.register(name, router)