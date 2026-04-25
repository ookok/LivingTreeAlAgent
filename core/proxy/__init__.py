"""
SmartProxyGateway - 统一代理配置中心
管理所有模块的代理请求

功能：
- 统一代理配置
- 代理请求路由
- 代理健康检查
- 请求重试和熔断

Author: LivingTreeAI Team
"""

import os
import time
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# 导入新配置系统（Nanochat 风格）
from core.config.nanochat_config import config



class ProxyType(Enum):
    """代理类型"""
    DIRECT = "direct"                     # 直连
    HTTP = "http"                         # HTTP 代理
    HTTPS = "https"                       # HTTPS 代理
    SOCKS5 = "socks5"                     # SOCKS5 代理


class RequestPriority(Enum):
    """请求优先级"""
    LOW = 1
    NORMAL = 5
    HIGH = 7
    CRITICAL = 9


@dataclass
class ProxyConfig:
    """代理配置"""
    proxy_type: ProxyType = ProxyType.DIRECT
    host: str = ""
    port: int = 0
    username: str = ""
    password: str = ""
    enabled: bool = True
    
    # 健康检查
    last_check: float = 0
    is_healthy: bool = True
    response_time: float = 0
    
    @property
    def url(self) -> str:
        """生成代理 URL"""
        if self.proxy_type == ProxyType.DIRECT:
            return ""
        
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        
        return f"{self.proxy_type.value}://{auth}{self.host}:{self.port}"
    
    @property
    def is_valid(self) -> bool:
        """检查配置是否有效"""
        if self.proxy_type == ProxyType.DIRECT:
            return True
        return bool(self.host and self.port > 0)


@dataclass
class EndpointConfig:
    """服务端点配置"""
    name: str
    url: str
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    enabled: bool = True
    weight: int = 1  # 负载均衡权重
    
    # 熔断器
    failure_count: int = 0
    last_failure: float = 0
    circuit_open: bool = False
    circuit_open_time: float = 0
    
    @property
    def is_available(self) -> bool:
        """检查端点是否可用"""
        if not self.enabled:
            return False
        
        # 熔断器：5分钟内失败超过5次则熔断
        if self.circuit_open:
            if time.time() - self.circuit_open_time > 300:
                self.circuit_open = False
                self.failure_count = 0
                return True
            return False
        
        return True


class SmartProxyGateway:
    """
    SmartProxyGateway - 统一代理网关
    
    功能：
    - 统一代理配置管理
    - 代理健康检查
    - 智能路由和负载均衡
    - 请求重试和熔断
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        
        # 代理配置
        self.default_proxy = ProxyConfig()
        
        # 端点配置
        self.endpoints: Dict[str, EndpointConfig] = {}
        
        # 健康检查
        self.health_check_interval = 60  # 秒
        self.health_check_task: Optional[asyncio.Task] = None
        
        # 统计
        self.request_stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "retried": 0
        }
        
        # 请求拦截器
        self.request_interceptors: List[Callable] = []
        self.response_interceptors: List[Callable] = []
        
        # 初始化
        self._load_config()
    
    def _load_config(self):
        """从环境变量加载配置"""
        # 代理配置
        proxy_url = os.getenv("LIVINGTREE_PROXY", "")
        if proxy_url:
            self.set_proxy(proxy_url)
        
        # 端点配置
        default_endpoints = {
            "github": EndpointConfig(
                name="GitHub",
                url="https://api.github.com",
                timeout=30,
                max_retries=config.retries.api
            ),
            "openai": EndpointConfig(
                name="OpenAI",
                url="https://api.openai.com",
                timeout=60,
                max_retries=config.retries.api
            ),
            "anthropic": EndpointConfig(
                name="Anthropic",
                url="https://api.anthropic.com",
                timeout=60,
                max_retries=config.retries.api
            ),
            "deepseek": EndpointConfig(
                name="DeepSeek",
                url="https://api.deepseek.com",
                timeout=60,
                max_retries=config.retries.api
            )
        }
        
        for key, endpoint in default_endpoints.items():
            self.endpoints[key] = endpoint
    
    # ==================== 代理管理 ====================
    
    def set_proxy(self, proxy_url: str) -> bool:
        """设置代理"""
        if not proxy_url:
            self.default_proxy = ProxyConfig()
            logger.info("Proxy disabled (direct connection)")
            return True
        
        try:
            # 解析代理 URL
            if proxy_url.startswith("http://"):
                proxy_type = ProxyType.HTTP
                url = proxy_url[7:]
            elif proxy_url.startswith("https://"):
                proxy_type = ProxyType.HTTPS
                url = proxy_url[8:]
            elif proxy_url.startswith("socks5://"):
                proxy_type = ProxyType.SOCKS5
                url = proxy_url[9:]
            else:
                proxy_type = ProxyType.HTTP
                url = proxy_url
            
            # 解析认证信息
            auth = ""
            if "@" in url:
                auth, url = url.rsplit("@", 1)
                username, password = auth.split(":", 1)
            else:
                username = ""
                password = ""
            
            # 解析主机和端口
            if ":" in url:
                host, port_str = url.split(":", 1)
                port = int(port_str)
            else:
                host = url
                port = 8080 if proxy_type == ProxyType.HTTP else 443
            
            self.default_proxy = ProxyConfig(
                proxy_type=proxy_type,
                host=host,
                port=port,
                username=username,
                password=password,
                enabled=True
            )
            
            logger.info(f"Proxy set: {proxy_type.value}://{host}:{port}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to parse proxy URL: {e}")
            return False
    
    def get_proxy(self) -> ProxyConfig:
        """获取当前代理配置"""
        return self.default_proxy
    
    def enable_proxy(self):
        """启用代理"""
        self.default_proxy.enabled = True
    
    def disable_proxy(self):
        """禁用代理"""
        self.default_proxy.enabled = False
    
    # ==================== 端点管理 ====================
    
    def add_endpoint(self, key: str, endpoint: EndpointConfig):
        """添加端点"""
        self.endpoints[key] = endpoint
        logger.info(f"Endpoint added: {key} -> {endpoint.url}")
    
    def get_endpoint(self, key: str) -> Optional[EndpointConfig]:
        """获取端点"""
        return self.endpoints.get(key)
    
    def remove_endpoint(self, key: str) -> bool:
        """移除端点"""
        if key in self.endpoints:
            del self.endpoints[key]
            logger.info(f"Endpoint removed: {key}")
            return True
        return False
    
    def get_available_endpoints(self) -> List[EndpointConfig]:
        """获取所有可用端点"""
        return [ep for ep in self.endpoints.values() if ep.is_available]
    
    # ==================== 请求执行 ====================
    
    async def request(
        self,
        method: str,
        url: str,
        endpoint_key: str = None,
        priority: RequestPriority = RequestPriority.NORMAL,
        timeout: int = None,
        retries: int = None,
        **kwargs
    ) -> Optional[Dict]:
        """
        执行代理请求
        
        Args:
            method: HTTP 方法
            url: 请求 URL
            endpoint_key: 端点键，用于获取基础配置
            priority: 请求优先级
            timeout: 超时时间
            retries: 重试次数
            
        Returns:
            响应数据
        """
        self.request_stats["total"] += 1
        
        # 获取端点配置
        endpoint = None
        if endpoint_key:
            endpoint = self.endpoints.get(endpoint_key)
        
        # 使用默认配置
        timeout = timeout or (endpoint.timeout if endpoint else 30)
        retries = retries or (endpoint.max_retries if endpoint else 3)
        
        # 获取代理
        proxy = self.default_proxy if self.default_proxy.enabled else None
        
        # 执行请求
        last_error = None
        for attempt in range(retries + 1):
            try:
                start_time = time.time()
                
                async with aiohttp.ClientSession() as session:
                    async with session.request(
                        method=method,
                        url=url,
                        proxy=proxy.url if proxy else None,
                        timeout=aiohttp.ClientTimeout(total=timeout),
                        **kwargs
                    ) as response:
                        response.raise_for_status()
                        data = await response.json()
                        
                        # 更新统计
                        self.request_stats["success"] += 1
                        
                        # 更新端点健康状态
                        if endpoint:
                            endpoint.failure_count = 0
                            endpoint.response_time = time.time() - start_time
                        
                        return data
            
            except aiohttp.ClientError as e:
                last_error = e
                self.request_stats["failed"] += 1
                
                if endpoint:
                    endpoint.failure_count += 1
                    endpoint.last_failure = time.time()
                    
                    # 检查是否需要熔断
                    if endpoint.failure_count >= 5:
                        endpoint.circuit_open = True
                        endpoint.circuit_open_time = time.time()
                        logger.warning(f"Circuit breaker opened for {endpoint.name}")
                
                if attempt < retries:
                    self.request_stats["retried"] += 1
                    delay = (endpoint.retry_delay if endpoint else 1.0) * (2 ** attempt)
                    logger.warning(f"Request failed, retrying in {delay}s...")
                    await asyncio.sleep(delay)
            
            except asyncio.TimeoutError:
                last_error = "Timeout"
                self.request_stats["failed"] += 1
                if attempt < retries:
                    self.request_stats["retried"] += 1
                    await asyncio.sleep(1)
        
        logger.error(f"Request failed after {retries + 1} attempts: {last_error}")
        return None
    
    async def get(self, url: str, **kwargs) -> Optional[Dict]:
        """GET 请求"""
        return await self.request("GET", url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> Optional[Dict]:
        """POST 请求"""
        return await self.request("POST", url, **kwargs)
    
    # ==================== GitHub API ====================
    
    async def github_search(
        self,
        query: str,
        type: str = "repositories",
        max_results: int = 10
    ) -> Optional[List[Dict]]:
        """
        GitHub 搜索
        
        Args:
            query: 搜索关键词
            type: 搜索类型 (repositories, users, issues, code)
            max_results: 最大结果数
            
        Returns:
            搜索结果列表
        """
        endpoint = self.endpoints.get("github")
        if not endpoint or not endpoint.is_available:
            logger.error("GitHub endpoint not available")
            return None
        
        url = f"{endpoint.url}/search/{type}"
        params = {
            "q": query,
            "per_page": min(max_results, 100)
        }
        
        data = await self.get(url, params=params, endpoint_key="github")
        
        if data and "items" in data:
            return data["items"]
        return None
    
    async def github_get_repo(self, owner: str, repo: str) -> Optional[Dict]:
        """获取仓库信息"""
        url = f"{self.endpoints['github'].url}/repos/{owner}/{repo}"
        return await self.get(url, endpoint_key="github")
    
    # ==================== LLM API ====================
    
    async def openai_chat(
        self,
        messages: List[Dict],
        model: str = "gpt-4",
        **kwargs
    ) -> Optional[Dict]:
        """OpenAI Chat API"""
        endpoint = self.endpoints.get("openai")
        if not endpoint or not endpoint.is_available:
            return None
        
        url = f"{endpoint.url}/v1/chat/completions"
        data = {
            "model": model,
            "messages": messages,
            **kwargs
        }
        
        return await self.post(url, json=data, endpoint_key="openai")
    
    async def deepseek_chat(
        self,
        messages: List[Dict],
        model: str = "deepseek-chat",
        **kwargs
    ) -> Optional[Dict]:
        """DeepSeek Chat API"""
        endpoint = self.endpoints.get("deepseek")
        if not endpoint or not endpoint.is_available:
            return None
        
        url = f"{endpoint.url}/chat/completions"
        data = {
            "model": model,
            "messages": messages,
            **kwargs
        }
        
        return await self.post(url, json=data, endpoint_key="deepseek")
    
    # ==================== 健康检查 ====================
    
    async def check_endpoint_health(self, key: str) -> bool:
        """检查端点健康状态"""
        endpoint = self.endpoints.get(key)
        if not endpoint:
            return False
        
        try:
            start_time = time.time()
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    endpoint.url,
                    proxy=self.default_proxy.url if self.default_proxy.enabled else None,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    endpoint.is_healthy = response.status < 500
                    endpoint.response_time = time.time() - start_time
                    endpoint.last_check = time.time()
                    return endpoint.is_healthy
        except Exception as e:
            endpoint.is_healthy = False
            endpoint.last_check = time.time()
            logger.error(f"Health check failed for {key}: {e}")
            return False
    
    async def start_health_check(self):
        """启动健康检查"""
        if self.health_check_task and not self.health_check_task.done():
            return
        
        async def check_loop():
            while True:
                for key in self.endpoints:
                    await self.check_endpoint_health(key)
                await asyncio.sleep(self.health_check_interval)
        
        self.health_check_task = asyncio.create_task(check_loop())
        logger.info("Health check started")
    
    async def stop_health_check(self):
        """停止健康检查"""
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
        logger.info("Health check stopped")
    
    # ==================== 统计 ====================
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = self.request_stats["total"]
        success = self.request_stats["success"]
        failed = self.request_stats["failed"]
        
        return {
            "total_requests": total,
            "success": success,
            "failed": failed,
            "retried": self.request_stats["retried"],
            "success_rate": success / total if total > 0 else 0,
            "proxy_enabled": self.default_proxy.enabled,
            "proxy_url": self.default_proxy.url if self.default_proxy.enabled else None,
            "endpoints": {
                key: {
                    "url": ep.url,
                    "available": ep.is_available,
                    "response_time": ep.response_time,
                    "failure_count": ep.failure_count
                }
                for key, ep in self.endpoints.items()
            }
        }
    
    def reset_stats(self):
        """重置统计"""
        self.request_stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "retried": 0
        }


# 全局实例
_proxy_gateway: Optional[SmartProxyGateway] = None


def get_proxy_gateway() -> SmartProxyGateway:
    """获取代理网关全局实例"""
    global _proxy_gateway
    if _proxy_gateway is None:
        _proxy_gateway = SmartProxyGateway()
    return _proxy_gateway


__all__ = [
    'ProxyType',
    'RequestPriority',
    'ProxyConfig',
    'EndpointConfig',
    'SmartProxyGateway',
    'get_proxy_gateway'
]
