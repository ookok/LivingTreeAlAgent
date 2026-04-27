#!/usr/bin/env python3
"""
SmartProxyGateway - 智能代理网关
Phase 4 核心：代理自动选择、负载均衡、故障转移

Author: LivingTreeAI Team
Version: 1.0.0
"""

import hashlib
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import threading


class ProxyStatus(Enum):
    """代理状态"""
    ACTIVE = "active"       # 活跃
    INACTIVE = "inactive"   # 非活跃
    BUSY = "busy"          # 繁忙
    ERROR = "error"        # 错误


class LoadBalanceStrategy(Enum):
    """负载均衡策略"""
    ROUND_ROBIN = "round_robin"     # 轮询
    LEAST_LOADED = "least_loaded"   # 最小负载
    RANDOM = "random"              # 随机
    WEIGHTED = "weighted"          # 加权


@dataclass
class ProxyEndpoint:
    """代理端点"""
    id: str
    name: str
    url: str
    status: ProxyStatus = ProxyStatus.ACTIVE
    weight: int = 1  # 权重
    max_load: int = 100  # 最大负载
    current_load: int = 0  # 当前负载
    success_count: int = 0
    error_count: int = 0
    avg_latency: float = 0.0
    last_health_check: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        total = self.success_count + self.error_count
        return self.success_count / total if total > 0 else 1.0
    
    @property
    def health_score(self) -> float:
        """健康分数"""
        rate_score = self.success_rate * 0.6
        latency_score = max(0, 1 - self.avg_latency / 5000) * 0.2  # 假设5秒为最大可接受延迟
        load_score = max(0, 1 - self.current_load / self.max_load) * 0.2
        return rate_score + latency_score + load_score


@dataclass
class ProxyRoute:
    """代理路由"""
    path: str
    endpoint_ids: List[str]
    strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN
    require_auth: bool = False
    timeout: float = 30.0
    retry_count: int = 3


class ProxyHealthChecker:
    """代理健康检查"""
    
    def __init__(self, check_interval: float = 30.0, timeout: float = 5.0):
        self._check_interval = check_interval
        self._timeout = timeout
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._endpoints: Dict[str, ProxyEndpoint] = {}
        self._lock = threading.Lock()
    
    def register_endpoint(self, endpoint: ProxyEndpoint) -> None:
        """注册端点"""
        with self._lock:
            self._endpoints[endpoint.id] = endpoint
    
    def unregister_endpoint(self, endpoint_id: str) -> None:
        """注销端点"""
        with self._lock:
            if endpoint_id in self._endpoints:
                del self._endpoints[endpoint_id]
    
    def start(self) -> None:
        """启动健康检查"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._check_loop, daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        """停止健康检查"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
    
    def _check_loop(self) -> None:
        """检查循环"""
        while self._running:
            try:
                self._perform_health_checks()
            except Exception:
                pass
            time.sleep(self._check_interval)
    
    def _perform_health_checks(self) -> None:
        """执行健康检查"""
        with self._lock:
            for endpoint in self._endpoints.values():
                self._check_endpoint(endpoint)
    
    def _check_endpoint(self, endpoint: ProxyEndpoint) -> None:
        """检查单个端点"""
        try:
            # 简化检查：实际应该发送HTTP请求
            import urllib.request
            
            start_time = time.time()
            # 这里应该检查端点是否可达
            # urllib.request.urlopen(endpoint.url, timeout=self._timeout)
            latency = (time.time() - start_time) * 1000
            
            endpoint.last_health_check = time.time()
            endpoint.status = ProxyStatus.ACTIVE
            endpoint.avg_latency = (endpoint.avg_latency + latency) / 2
            
        except Exception as e:
            endpoint.status = ProxyStatus.ERROR
            endpoint.error_count += 1


class SmartProxyGateway:
    """
    智能代理网关
    
    核心功能：
    - 多代理端点管理
    - 智能路由选择
    - 负载均衡
    - 故障转移
    - 健康检查
    - 流量控制
    """
    
    def __init__(self):
        # 端点管理
        self._endpoints: Dict[str, ProxyEndpoint] = {}
        self._routes: Dict[str, ProxyRoute] = {}
        
        # 负载均衡状态
        self._round_robin_counters: Dict[str, int] = defaultdict(int)
        
        # 健康检查器
        self._health_checker = ProxyHealthChecker()
        
        # 锁
        self._lock = threading.RLock()
        
        # 统计
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_latency": 0.0,
        }
    
    def register_endpoint(self, endpoint: ProxyEndpoint) -> None:
        """
        注册代理端点
        
        Args:
            endpoint: 代理端点
        """
        with self._lock:
            self._endpoints[endpoint.id] = endpoint
            self._health_checker.register_endpoint(endpoint)
    
    def unregister_endpoint(self, endpoint_id: str) -> bool:
        """
        注销代理端点
        
        Args:
            endpoint_id: 端点ID
            
        Returns:
            是否成功
        """
        with self._lock:
            if endpoint_id in self._endpoints:
                del self._endpoints[endpoint_id]
                self._health_checker.unregister_endpoint(endpoint_id)
                return True
            return False
    
    def add_route(self, route: ProxyRoute) -> None:
        """
        添加路由
        
        Args:
            route: 代理路由
        """
        with self._lock:
            self._routes[route.path] = route
    
    def select_endpoint(
        self,
        path: str,
        strategy: Optional[LoadBalanceStrategy] = None,
    ) -> Optional[ProxyEndpoint]:
        """
        选择最佳端点
        
        Args:
            path: 请求路径
            strategy: 负载均衡策略
            
        Returns:
            选中的端点
        """
        with self._lock:
            # 获取路由
            route = self._routes.get(path)
            if not route:
                # 尝试匹配前缀
                for route_path, r in self._routes.items():
                    if path.startswith(route_path):
                        route = r
                        break
            
            if not route:
                # 使用所有活跃端点
                endpoints = [
                    e for e in self._endpoints.values()
                    if e.status == ProxyStatus.ACTIVE
                ]
            else:
                # 使用路由指定的端点
                endpoints = [
                    self._endpoints[eid] for eid in route.endpoint_ids
                    if eid in self._endpoints and self._endpoints[eid].status == ProxyStatus.ACTIVE
                ]
            
            if not endpoints:
                return None
            
            # 选择策略
            strategy = strategy or (route.strategy if route else LoadBalanceStrategy.ROUND_ROBIN)
            
            if strategy == LoadBalanceStrategy.ROUND_ROBIN:
                return self._select_round_robin(path, endpoints)
            elif strategy == LoadBalanceStrategy.LEAST_LOADED:
                return self._select_least_loaded(endpoints)
            elif strategy == LoadBalanceStrategy.RANDOM:
                return self._select_random(endpoints)
            elif strategy == LoadBalanceStrategy.WEIGHTED:
                return self._select_weighted(endpoints)
            
            return endpoints[0]
    
    def _select_round_robin(self, path: str, endpoints: List[ProxyEndpoint]) -> ProxyEndpoint:
        """轮询选择"""
        counter = self._round_robin_counters[path]
        selected = endpoints[counter % len(endpoints)]
        self._round_robin_counters[path] = counter + 1
        return selected
    
    def _select_least_loaded(self, endpoints: List[ProxyEndpoint]) -> ProxyEndpoint:
        """最小负载选择"""
        return min(endpoints, key=lambda e: e.current_load / e.max_load)
    
    def _select_random(self, endpoints: List[ProxyEndpoint]) -> ProxyEndpoint:
        """随机选择"""
        import random
        return endpoints[int(random.random() * len(endpoints))]
    
    def _select_weighted(self, endpoints: List[ProxyEndpoint]) -> ProxyEndpoint:
        """加权选择"""
        total_weight = sum(e.weight for e in endpoints)
        import random
        r = random.random() * total_weight
        
        cumulative = 0
        for endpoint in endpoints:
            cumulative += endpoint.weight
            if r <= cumulative:
                return endpoint
        
        return endpoints[0]
    
    def record_success(self, endpoint_id: str, latency: float) -> None:
        """
        记录成功请求
        
        Args:
            endpoint_id: 端点ID
            latency: 延迟(ms)
        """
        with self._lock:
            endpoint = self._endpoints.get(endpoint_id)
            if endpoint:
                endpoint.success_count += 1
                endpoint.current_load = max(0, endpoint.current_load - 1)
                endpoint.avg_latency = (endpoint.avg_latency + latency) / 2
            
            self._stats["total_requests"] += 1
            self._stats["successful_requests"] += 1
    
    def record_failure(self, endpoint_id: str) -> None:
        """
        记录失败请求
        
        Args:
            endpoint_id: 端点ID
        """
        with self._lock:
            endpoint = self._endpoints.get(endpoint_id)
            if endpoint:
                endpoint.error_count += 1
                endpoint.current_load = max(0, endpoint.current_load - 1)
                
                # 连续失败过多则标记为错误
                if endpoint.error_count > 10:
                    endpoint.status = ProxyStatus.ERROR
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息
        """
        with self._lock:
            return {
                **self._stats,
                "endpoints": {
                    eid: {
                        "status": e.status.value,
                        "load": f"{e.current_load}/{e.max_load}",
                        "success_rate": f"{e.success_rate:.2%}",
                        "avg_latency": f"{e.avg_latency:.2f}ms",
                        "health_score": f"{e.health_score:.2f}",
                    }
                    for eid, e in self._endpoints.items()
                },
                "routes": len(self._routes),
            }
    
    def get_healthy_endpoints(self) -> List[ProxyEndpoint]:
        """
        获取健康端点列表
        
        Returns:
            健康端点列表
        """
        with self._lock:
            return [
                e for e in self._endpoints.values()
                if e.status == ProxyStatus.ACTIVE and e.health_score > 0.5
            ]
    
    def start_health_checker(self) -> None:
        """启动健康检查"""
        self._health_checker.start()
    
    def stop_health_checker(self) -> None:
        """停止健康检查"""
        self._health_checker.stop()


# 全局网关实例
_global_gateway: Optional[SmartProxyGateway] = None
_gateway_lock = threading.Lock()


def get_proxy_gateway() -> SmartProxyGateway:
    """获取全局代理网关实例"""
    global _global_gateway
    
    with _gateway_lock:
        if _global_gateway is None:
            _global_gateway = SmartProxyGateway()
        return _global_gateway


# 便捷函数
def register_proxy(
    proxy_id: str,
    name: str,
    url: str,
    weight: int = 1,
    max_load: int = 100,
) -> None:
    """注册代理"""
    endpoint = ProxyEndpoint(
        id=proxy_id,
        name=name,
        url=url,
        weight=weight,
        max_load=max_load,
    )
    get_proxy_gateway().register_endpoint(endpoint)


def route(path: str, endpoint_ids: List[str], strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN) -> None:
    """添加路由"""
    route = ProxyRoute(
        path=path,
        endpoint_ids=endpoint_ids,
        strategy=strategy,
    )
    get_proxy_gateway().add_route(route)
