"""
Base Proxy Manager
基础代理管理器，为所有代理相关模块提供通用功能。

使用方式：
    from business.base_proxy_manager import BaseProxyManager
    
    class MyProxyManager(BaseProxyManager):
        def fetch_proxies(self) -> list:
            # 实现具体的代理获取逻辑
            pass
"""
import logging
import time
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Callable
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ProxyStatus(Enum):
    """代理状态"""
    UNKNOWN = "unknown"
    ACTIVE = "active"
    INACTIVE = "inactive"
    BUSY = "busy"
    ERROR = "error"


class ProxySourceType(Enum):
    """代理源类型"""
    API = "api"
    SCRAPE = "scrape"
    FILE = "file"
    ENV = "env"


@dataclass
class BaseProxy:
    """基础代理数据类"""
    host: str
    port: int
    protocol: str = "http"  # http, https, socks5
    username: str = ""
    password: str = ""
    source: str = ""
    source_type: ProxySourceType = ProxySourceType.API
    
    # 状态
    status: ProxyStatus = ProxyStatus.UNKNOWN
    success_count: int = 0
    failure_count: int = 0
    last_used: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    avg_latency: float = 0.0
    
    def to_url(self) -> str:
        """转换为代理 URL"""
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "host": self.host,
            "port": self.port,
            "protocol": self.protocol,
            "username": self.username,
            "password": self.password,
            "source": self.source,
            "source_type": self.source_type.value,
            "status": self.status.value,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "avg_latency": self.avg_latency,
        }
    
    @classmethod
    def from_url(cls, url: str, **kwargs) -> "BaseProxy":
        """从 URL 创建代理"""
        parsed = urlparse(url)
        return cls(
            host=parsed.hostname or "",
            port=parsed.port or 8080,
            protocol=parsed.scheme or "http",
            username=parsed.username or "",
            password=parsed.password or "",
            **kwargs
        )
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 1.0
    
    @property
    def is_healthy(self) -> bool:
        """是否健康"""
        if self.status == ProxyStatus.ERROR:
            return False
        if self.failure_count > 5:
            # 检查失败窗口
            if self.last_failure:
                window = datetime.now() - self.last_failure
                if window < timedelta(minutes=10):
                    return False
        return True
    
    def record_success(self, latency: float = 0.0) -> None:
        """记录成功"""
        self.success_count += 1
        self.last_success = datetime.now()
        self.last_used = datetime.now()
        # 更新平均延迟
        if latency > 0:
            if self.avg_latency == 0:
                self.avg_latency = latency
            else:
                self.avg_latency = (self.avg_latency * 0.7 + latency * 0.3)
        # 重置失败计数
        if self.failure_count > 0:
            self.failure_count = max(0, self.failure_count - 1)
    
    def record_failure(self) -> None:
        """记录失败"""
        self.failure_count += 1
        self.last_failure = datetime.now()
        self.last_used = datetime.now()
        if self.failure_count >= 3:
            self.status = ProxyStatus.ERROR
    
    def score(self) -> float:
        """综合评分（越高越好）"""
        # 成功率权重 60%
        rate_score = self.success_rate * 0.6
        # 延迟权重 20%（越低越好）
        latency_score = max(0, 1 - self.avg_latency / 10) * 0.2 if self.avg_latency > 0 else 0.1
        # 稳定性权重 20%
        stability_score = (1 / (1 + self.failure_count)) * 0.2
        
        return rate_score + latency_score + stability_score


class BaseProxyManager:
    """
    基础代理管理器
    
    提供通用功能：
    1. 代理获取（从多个源）
    2. 代理验证
    3. 代理池管理
    4. 代理选择（负载均衡）
    5. 健康检查
    
    子类可重写：
    - fetch_proxies()      ：从具体源获取代理
    - validate_proxy(proxy) ：验证代理可用性
    - health_check(proxy)   ：健康检查
    - score_proxy(proxy)    ：计算代理评分
    
    子类可使用的属性/方法：
    - self._pool            ：代理池（List[BaseProxy]）
    - self.get_best_proxy() ：获取最佳代理
    - self.get_round_robin()：轮询获取代理
    - self.mark_success()   ：标记成功
    - self.mark_failure()   ：标记失败
    """
    
    def __init__(self, max_pool_size: int = 100, validation_level: int = 1):
        """
        初始化代理管理器
        
        Args:
            max_pool_size: 代理池最大大小
            validation_level: 验证级别（0=不验证，1=基础验证，2=深度验证）
        """
        self.max_pool_size = max_pool_size
        self.validation_level = validation_level
        self._pool: List[BaseProxy] = []
        self._lock = None  # 子类可选用线程锁或异步锁
        self._observers: List[Callable[[BaseProxy, str], None]] = []
        self._round_robin_index: int = 0
        
        # 统计
        self.total_requests = 0
        self.successful_requests = 0
        
    # -------- 子类可重写的钩子方法 --------
    
    async def fetch_proxies(self) -> List[BaseProxy]:
        """
        获取代理（子类应重写此方法）
        
        Returns:
            List[BaseProxy]: 代理列表
        """
        raise NotImplementedError("Subclasses must implement fetch_proxies()")
    
    async def validate_proxy(self, proxy: BaseProxy) -> Tuple[bool, float]:
        """
        验证代理可用性（子类可重写此方法）
        
        Args:
            proxy: 代理对象
            
        Returns:
            Tuple[bool, float]: (是否可用, 延迟)
        """
        # 默认实现：简单连接测试
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((proxy.host, proxy.port))
            sock.close()
            if result == 0:
                return True, 0.0
        except Exception:
            pass
        return False, 0.0
    
    def score_proxy(self, proxy: BaseProxy) -> float:
        """
        计算代理评分（子类可重写）
        
        Returns:
            float: 评分（越高越好）
        """
        return proxy.score()
    
    # -------- 代理池管理 --------
    
    async def refresh_pool(self) -> int:
        """
        刷新代理池
        
        Returns:
            int: 新添加的代理数量
        """
        new_proxies = await self.fetch_proxies()
        
        added = 0
        for proxy in new_proxies:
            if len(self._pool) >= self.max_pool_size:
                break
            if not self._is_duplicate(proxy):
                if self.validation_level > 0:
                    is_valid, latency = await self.validate_proxy(proxy)
                    if is_valid:
                        proxy.avg_latency = latency
                        self._pool.append(proxy)
                        added += 1
                else:
                    self._pool.append(proxy)
                    added += 1
        
        logger.info(f"Pool refreshed: {added} new proxies added, {len(self._pool)} total")
        return added
    
    def _is_duplicate(self, proxy: BaseProxy) -> bool:
        """检查是否重复"""
        for existing in self._pool:
            if existing.host == proxy.host and existing.port == proxy.port:
                return True
        return False
    
    # -------- 代理选择（负载均衡）--------
    
    def get_best_proxy(self) -> Optional[BaseProxy]:
        """
        获取最佳代理（按评分排序）
        
        Returns:
            Optional[BaseProxy]: 最佳代理，如果没有则返回 None
        """
        if not self._pool:
            return None
        
        sorted_pool = sorted(self._pool, key=lambda p: self.score_proxy(p), reverse=True)
        
        for proxy in sorted_pool:
            if proxy.is_healthy:
                return proxy
        
        return None
    
    def get_round_robin(self) -> Optional[BaseProxy]:
        """
        轮询获取代理
        
        Returns:
            Optional[BaseProxy]: 代理
        """
        if not self._pool:
            return None
        
        proxy = self._pool[self._round_robin_index % len(self._pool)]
        self._round_robin_index += 1
        return proxy
    
    def get_by_strategy(self, strategy: str = "best") -> Optional[BaseProxy]:
        """
        按策略获取代理
        
        Args:
            strategy: "best"（最佳评分）、"round_robin"（轮询）、"random"（随机）
            
        Returns:
            Optional[BaseProxy]: 代理
        """
        if not self._pool:
            return None
        
        if strategy == "best":
            return self.get_best_proxy()
        elif strategy == "round_robin":
            return self.get_round_robin()
        elif strategy == "random":
            import random
            return self._pool[int(random.random() * len(self._pool))]
        
        return self.get_best_proxy()
    
    # -------- 代理状态标记 --------
    
    def mark_success(self, proxy: BaseProxy, latency: float = 0.0) -> None:
        """标记代理成功"""
        proxy.record_success(latency)
        self.successful_requests += 1
        self.total_requests += 1
        
    def mark_failure(self, proxy: BaseProxy) -> None:
        """标记代理失败"""
        proxy.record_failure()
        self.total_requests += 1
        
    # -------- 健康检查 --------
    
    async def health_check(self, proxy: BaseProxy) -> bool:
        """
        健康检查
        
        Args:
            proxy: 代理对象
            
        Returns:
            bool: 是否健康
        """
        is_valid, latency = await self.validate_proxy(proxy)
        if is_valid:
            proxy.record_success(latency)
            return True
        else:
            proxy.record_failure()
            return False
    
    async def health_check_all(self) -> None:
        """检查所有代理的健康状态"""
        for proxy in self._pool:
            await self.health_check(proxy)
    
    # -------- 代理池操作 --------
    
    def remove_proxy(self, proxy: BaseProxy) -> bool:
        """移除代理"""
        if proxy in self._pool:
            self._pool.remove(proxy)
            return True
        return False
    
    def clear_pool(self) -> None:
        """清空代理池"""
        self._pool.clear()
    
    # -------- 统计 --------
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_proxies": len(self._pool),
            "healthy_proxies": sum(1 for p in self._pool if p.is_healthy),
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "success_rate": self.successful_requests / self.total_requests if self.total_requests > 0 else 0,
            "avg_score": sum(self.score_proxy(p) for p in self._pool) / len(self._pool) if self._pool else 0,
        }
    
    # -------- 观察者模式 --------
    
    def register_observer(self, callback: Callable[[BaseProxy, str], None]) -> None:
        """注册观察者（代理状态变更时回调）"""
        self._observers.append(callback)
    
    def _notify_observers(self, proxy: BaseProxy, event: str) -> None:
        """通知观察者"""
        for observer in self._observers:
            try:
                observer(proxy, event)
            except Exception as e:
                logger.error(f"Observer callback failed: {e}")
        
    async def fetch_proxies(self) -> List[BaseProxy]:
        """
        获取代理（子类应重写此方法）
        
        Returns:
            List[BaseProxy]: 代理列表
        """
        raise NotImplementedError("Subclasses must implement fetch_proxies()")
    
    async def validate_proxy(self, proxy: BaseProxy) -> Tuple[bool, float]:
        """
        验证代理可用性（子类可重写此方法）
        
        Args:
            proxy: 代理对象
            
        Returns:
            Tuple[bool, float]: (是否可用, 延迟)
        """
        import aiohttp
        
        try:
            start = time.time()
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                proxy_url = proxy.to_url()
                async with session.get("http://httpbin.org/ip", proxy=proxy_url) as resp:
                    if resp.status == 200:
                        latency = time.time() - start
                        return True, latency
        except Exception:
            pass
        
        return False, 0.0
    
    async def refresh_pool(self) -> int:
        """
        刷新代理池
        
        Returns:
            int: 新添加的代理数量
        """
        new_proxies = await self.fetch_proxies()
        
        added = 0
        for proxy in new_proxies:
            if len(self._pool) >= self.max_pool_size:
                break
            if not self._is_duplicate(proxy):
                if self.validation_level > 0:
                    is_valid, latency = await self.validate_proxy(proxy)
                    if is_valid:
                        proxy.avg_latency = latency
                        self._pool.append(proxy)
                        added += 1
                else:
                    self._pool.append(proxy)
                    added += 1
        
        logger.info(f"Pool refreshed: {added} new proxies added, {len(self._pool)} total")
        return added
    
    def _is_duplicate(self, proxy: BaseProxy) -> bool:
        """检查是否重复"""
        for existing in self._pool:
            if existing.host == proxy.host and existing.port == proxy.port:
                return True
        return False
    
    def get_best_proxy(self) -> Optional[BaseProxy]:
        """
        获取最佳代理（按评分排序）
        
        Returns:
            Optional[BaseProxy]: 最佳代理，如果没有则返回 None
        """
        if not self._pool:
            return None
        
        # 按评分排序
        sorted_pool = sorted(self._pool, key=lambda p: p.score(), reverse=True)
        
        # 返回第一个健康的代理
        for proxy in sorted_pool:
            if proxy.is_healthy:
                return proxy
        
        return None
    
    def get_proxy_round_robin(self) -> Optional[BaseProxy]:
        """
        轮询获取代理
        
        Returns:
            Optional[BaseProxy]: 代理
        """
        if not self._pool:
            return None
        
        # 简单的轮询
        proxy = self._pool.pop(0)
        self._pool.append(proxy)
        return proxy
    
    def mark_success(self, proxy: BaseProxy, latency: float = 0.0) -> None:
        """标记代理成功"""
        proxy.record_success(latency)
        self.successful_requests += 1
        self.total_requests += 1
        
    def mark_failure(self, proxy: BaseProxy) -> None:
        """标记代理失败"""
        proxy.record_failure()
        self.total_requests += 1
        
    async def health_check(self, proxy: BaseProxy) -> bool:
        """
        健康检查
        
        Args:
            proxy: 代理对象
            
        Returns:
            bool: 是否健康
        """
        is_valid, latency = await self.validate_proxy(proxy)
        if is_valid:
            proxy.record_success(latency)
            return True
        else:
            proxy.record_failure()
            return False
    
    async def health_check_all(self) -> None:
        """检查所有代理的健康状态"""
        for proxy in self._pool:
            await self.health_check(proxy)
    
    def remove_proxy(self, proxy: BaseProxy) -> bool:
        """移除代理"""
        if proxy in self._pool:
            self._pool.remove(proxy)
            return True
        return False
    
    def clear_pool(self) -> None:
        """清空代理池"""
        self._pool.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_proxies": len(self._pool),
            "healthy_proxies": sum(1 for p in self._pool if p.is_healthy),
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "success_rate": self.successful_requests / self.total_requests if self.total_requests > 0 else 0,
            "avg_score": sum(p.score() for p in self._pool) / len(self._pool) if self._pool else 0,
        }
    
    def register_observer(self, callback: Callable[[BaseProxy, str], None]) -> None:
        """注册观察者（代理状态变更时回调）"""
        self._observers.append(callback)
    
    def _notify_observers(self, proxy: BaseProxy, event: str) -> None:
        """通知观察者"""
        for observer in self._observers:
            try:
                observer(proxy, event)
            except Exception as e:
                logger.error(f"Observer callback failed: {e}")
