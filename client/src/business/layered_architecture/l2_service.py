"""L2 - 服务/逻辑层创新组件"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio

class ServiceType(Enum):
    CORE = "core"
    SEARCH = "search"
    MEMORY = "memory"
    TOOL = "tool"
    OPTIMIZATION = "optimization"

@dataclass
class ServiceDescriptor:
    """服务描述符"""
    id: str
    type: ServiceType
    name: str
    description: str
    handler: Callable
    availability: float = 1.0
    latency: float = 0.0
    version: str = "1.0"

@dataclass
class RouteDecision:
    """路由决策"""
    service_id: str
    reason: str
    confidence: float

class AdaptiveServiceComposition:
    """自适应服务组合"""
    
    def __init__(self):
        self._services: Dict[str, ServiceDescriptor] = {}
        self._compositions: Dict[str, List[str]] = {}
    
    def register_service(self, descriptor: ServiceDescriptor):
        """注册服务"""
        self._services[descriptor.id] = descriptor
    
    async def compose(self, intent: Dict[str, Any]) -> List[str]:
        """根据意图动态组合服务"""
        intent_type = intent.get("type", "unknown")
        
        if intent_type in self._compositions:
            return self._compositions[intent_type]
        
        return await self._generate_composition(intent)
    
    async def _generate_composition(self, intent: Dict[str, Any]) -> List[str]:
        """生成服务组合"""
        intent_type = intent.get("type")
        
        if intent_type == "search":
            return ["search_service", "memory_service"]
        elif intent_type == "create":
            return ["tool_service", "memory_service"]
        else:
            return ["core_service"]
    
    def get_service(self, service_id: str) -> Optional[ServiceDescriptor]:
        """获取服务"""
        return self._services.get(service_id)

class SmartAPIGateway:
    """智能API网关"""
    
    def __init__(self):
        self._router = IntentBasedRouter()
        self._load_balancer = SmartLoadBalancer()
        self._circuit_breaker = CircuitBreaker()
    
    async def route(self, request: Dict[str, Any]) -> RouteDecision:
        """智能路由请求"""
        intent = self._router.extract_intent(request)
        services = self._router.find_services(intent)
        
        if not services:
            return RouteDecision(service_id="fallback", reason="No service found", confidence=0.5)
        
        service = self._load_balancer.select(services)
        
        if self._circuit_breaker.is_open(service.id):
            return RouteDecision(service_id="fallback", reason="Circuit breaker open", confidence=0.5)
        
        return RouteDecision(service_id=service.id, reason="Normal routing", confidence=0.9)
    
    def get_gateway_stats(self) -> Dict[str, Any]:
        """获取网关统计"""
        return {
            "requests_routed": 0,
            "circuit_breaks": 0,
            "avg_latency": 0.0
        }

class IntentBasedRouter:
    """意图基于路由器"""
    
    def extract_intent(self, request: Dict[str, Any]) -> str:
        """提取意图"""
        return request.get("intent", "unknown")
    
    def find_services(self, intent: str) -> List[ServiceDescriptor]:
        """查找服务"""
        return []

class SmartLoadBalancer:
    """智能负载均衡器"""
    
    def select(self, services: List[ServiceDescriptor]) -> ServiceDescriptor:
        """选择服务"""
        return services[0] if services else None

class CircuitBreaker:
    """熔断器"""
    
    def __init__(self):
        self._open_circuits: set = set()
    
    def is_open(self, service_id: str) -> bool:
        """是否打开"""
        return service_id in self._open_circuits
    
    def open(self, service_id: str):
        """打开熔断器"""
        self._open_circuits.add(service_id)
    
    def close(self, service_id: str):
        """关闭熔断器"""
        self._open_circuits.discard(service_id)

# 全局单例
_adaptive_composition = AdaptiveServiceComposition()
_smart_gateway = SmartAPIGateway()

def get_adaptive_service_composition() -> AdaptiveServiceComposition:
    return _adaptive_composition

def get_smart_api_gateway() -> SmartAPIGateway:
    return _smart_gateway