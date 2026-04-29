"""
ChannelManager - 通道管理器
===========================

四层回退通道：
- Channel0: 本地直连（默认）
- Channel1: 用户显式配置的代理
- Channel2: 官方API通道
- Channel3: 本地降级（离线韧性）

Author: LivingTreeAI Community
from __future__ import annotations
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime
from collections import deque
import asyncio
import logging
import json
import uuid

logger = logging.getLogger(__name__)


class ChannelType(Enum):
    """通道类型"""
    DIRECT = "direct"           # 本地直连
    USER_PROXY = "user_proxy"   # 用户配置的代理
    API_FALLBACK = "api"        # 官方API
    LOCAL_LLM = "local_llm"     # 本地LLM降级
    OFFLINE_QUEUE = "offline"   # 离线队列


class ChannelStatus(Enum):
    """通道状态"""
    AVAILABLE = "available"    # 可用
    UNAVAILABLE = "unavailable" # 不可用
    SKIPPED = "skipped"         # 跳过（未启用）
    ERROR = "error"             # 错误
    TIMEOUT = "timeout"         # 超时


@dataclass
class UserProxyConfig:
    """用户代理配置"""
    enabled: bool = False
    proxy_type: str = "http"    # http, socks5
    proxy_host: str = ""
    proxy_port: int = 0
    proxy_user: str = ""        # 可选
    proxy_pass: str = ""       # 可选

    def get_proxy_dict(self) -> Optional[Dict[str, Any]]:
        """获取代理字典（用于httpx/aiohttp）"""
        if not self.enabled or not self.proxy_host:
            return None

        server = f"{self.proxy_type}://{self.proxy_host}:{self.proxy_port}"

        proxy_auth = None
        if self.proxy_user and self.proxy_pass:
            proxy_auth = {
                "username": self.proxy_user,
                "password": self.proxy_pass
            }

        return {
            "server": server,
            "auth": proxy_auth
        }

    def is_valid(self) -> bool:
        """验证配置是否有效"""
        return (
            self.enabled and
            bool(self.proxy_host) and
            self.proxy_port > 0 and
            self.proxy_type in ("http", "socks5")
        )


@dataclass
class APIKeyConfig:
    """API Key配置"""
    service_name: str = ""      # openai, deepseek, anthropic, etc.
    api_key: str = ""
    base_url: str = ""
    enabled: bool = False

    def is_valid(self) -> bool:
        """验证配置是否有效"""
        return self.enabled and bool(self.api_key)


@dataclass
class LocalLLMConfig:
    """本地LLM配置"""
    enabled: bool = False
    endpoint: str = "http://localhost:11434"  # Ollama默认
    model: str = "llama3.2"
    timeout: float = 60.0

    def is_valid(self) -> bool:
        return self.enabled and bool(self.endpoint)


@dataclass
class ChannelResult:
    """通道执行结果"""
    success: bool
    channel_type: ChannelType
    data: Any = None
    error: str = ""
    latency_ms: float = 0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "channel_type": self.channel_type.value,
            "data": self.data,
            "error": self.error,
            "latency_ms": round(self.latency_ms, 2),
            "timestamp": self.timestamp.isoformat(),
        }


class ChannelManager:
    """
    外脑调用通道管理器

    核心职责：
    1. 按优先级尝试各通道
    2. 失败后自动降级
    3. 记录通道质量统计
    4. 管理离线任务队列
    """

    def __init__(self):
        # 用户配置
        self._user_proxy = UserProxyConfig()
        self._api_keys: Dict[str, APIKeyConfig] = {}
        self._local_llm = LocalLLMConfig()

        # 通道定义（按优先级排序）
        self._channels: List[ChannelType] = [
            ChannelType.DIRECT,
            ChannelType.USER_PROXY,
            ChannelType.API_FALLBACK,
            ChannelType.LOCAL_LLM,
            ChannelType.OFFLINE_QUEUE,
        ]

        # 通道状态缓存
        self._channel_status: Dict[ChannelType, ChannelStatus] = {}
        self._channel_latency: Dict[ChannelType, float] = {}
        self._channel_errors: Dict[ChannelType, int] = {}

        # 诊断器引用
        self._diagnoser = None

        # 离线队列引用
        self._offline_queue = None

        # 监听器
        self._listeners: List[Callable] = []

        # 心跳检测任务
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False

    def set_diagnoser(self, diagnoser):
        """设置网络诊断器"""
        self._diagnoser = diagnoser

    def set_offline_queue(self, queue):
        """设置离线队列"""
        self._offline_queue = queue

    # ==================== 配置管理 ====================

    def get_user_proxy(self) -> UserProxyConfig:
        """获取用户代理配置"""
        return self._user_proxy

    def set_user_proxy(self, config: UserProxyConfig):
        """设置用户代理配置"""
        self._user_proxy = config
        logger.info(f"用户代理配置已更新: enabled={config.enabled}, type={config.proxy_type}")
        self._notify_listeners("proxy_config_changed", config)

    def get_api_key(self, service_name: str) -> Optional[APIKeyConfig]:
        """获取API Key配置"""
        return self._api_keys.get(service_name.lower())

    def set_api_key(self, config: APIKeyConfig):
        """设置API Key配置"""
        key = config.service_name.lower()
        self._api_keys[key] = config
        logger.info(f"API Key配置已更新: service={config.service_name}, enabled={config.enabled}")
        self._notify_listeners("api_key_changed", config)

    def get_local_llm_config(self) -> LocalLLMConfig:
        """获取本地LLM配置"""
        return self._local_llm

    def set_local_llm_config(self, config: LocalLLMConfig):
        """设置本地LLM配置"""
        self._local_llm = config
        logger.info(f"本地LLM配置已更新: enabled={config.enabled}, endpoint={config.endpoint}")
        self._notify_listeners("local_llm_changed", config)

    # ==================== 核心执行 ====================

    async def execute(
        self,
        task_name: str,
        target_url: str,
        request_data: Dict[str, Any],
        method: str = "POST",
        headers: Dict[str, str] = None,
        timeout: float = 30.0,
    ) -> ChannelResult:
        """
        执行外脑调用，自动降级

        Args:
            task_name: 任务名称（用于日志和离线队列）
            target_url: 目标URL
            request_data: 请求数据
            method: HTTP方法
            headers: 请求头
            timeout: 超时时间

        Returns:
            ChannelResult: 执行结果
        """
        last_error = None

        for channel_type in self._channels:
            # 检查通道是否可用
            if not await self._is_channel_available(channel_type, target_url):
                logger.info(f"通道 {channel_type.value} 不可用，跳过")
                self._channel_status[channel_type] = ChannelStatus.SKIPPED
                continue

            try:
                logger.info(f"尝试通道: {channel_type.value}")
                result = await self._execute_channel(
                    channel_type, task_name, target_url,
                    request_data, method, headers, timeout
                )

                if result.success:
                    self._record_success(channel_type, result.latency_ms)
                    self._notify_listeners("call_success", result)
                    return result
                else:
                    last_error = result.error
                    self._record_failure(channel_type, result.error)

            except Exception as e:
                logger.error(f"通道 {channel_type.value} 执行异常: {e}")
                last_error = str(e)
                self._record_failure(channel_type, last_error)

        # 所有通道失败
        await self._handle_all_channels_failed(task_name, target_url, request_data, last_error)

        return ChannelResult(
            success=False,
            channel_type=ChannelType.OFFLINE_QUEUE,
            error=f"所有通道均失败: {last_error}",
        )

    async def _is_channel_available(self, channel_type: ChannelType, target_url: str) -> bool:
        """检查通道是否可用"""
        if channel_type == ChannelType.DIRECT:
            # 通道0：默认可用（通过诊断器验证）
            if self._diagnoser:
                diagnosis = await self._diagnoser.quick_diagnose([target_url])
                return diagnosis.get(target_url, False)
            return True

        elif channel_type == ChannelType.USER_PROXY:
            # 通道1：需要用户显式配置
            return self._user_proxy.is_valid()

        elif channel_type == ChannelType.API_FALLBACK:
            # 通道2：需要API Key
            service_name = self._extract_service_name(target_url)
            api_config = self._api_keys.get(service_name.lower())
            return api_config is not None and api_config.is_valid()

        elif channel_type == ChannelType.LOCAL_LLM:
            # 通道3：需要本地LLM配置
            return self._local_llm.is_valid()

        elif channel_type == ChannelType.OFFLINE_QUEUE:
            # 通道4：始终可用（最后保障）
            return True

        return False

    async def _execute_channel(
        self,
        channel_type: ChannelType,
        task_name: str,
        target_url: str,
        request_data: Dict[str, Any],
        method: str,
        headers: Dict[str, str],
        timeout: float,
    ) -> ChannelResult:
        """执行单个通道"""
        import time
        start_time = time.perf_counter()

        if channel_type == ChannelType.DIRECT:
            return await self._channel_direct(task_name, target_url, request_data, method, headers, timeout)
        elif channel_type == ChannelType.USER_PROXY:
            return await self._channel_user_proxy(task_name, target_url, request_data, method, headers, timeout)
        elif channel_type == ChannelType.API_FALLBACK:
            return await self._channel_api_fallback(task_name, target_url, request_data, method, headers, timeout)
        elif channel_type == ChannelType.LOCAL_LLM:
            return await self._channel_local_llm(task_name, request_data, timeout)
        elif channel_type == ChannelType.OFFLINE_QUEUE:
            return await self._channel_offline_queue(task_name, request_data)

        return ChannelResult(success=False, channel_type=channel_type, error="未知通道类型")

    # ==================== 通道实现 ====================

    async def _channel_direct(
        self,
        task_name: str,
        target_url: str,
        request_data: Dict[str, Any],
        method: str,
        headers: Dict[str, str],
        timeout: float,
    ) -> ChannelResult:
        """通道0：本地直连"""
        import time
        import aiohttp

        start_time = time.perf_counter()

        try:
            async with aiohttp.ClientSession() as session:
                kwargs = {
                    "timeout": aiohttp.ClientTimeout(total=timeout),
                }
                if headers:
                    kwargs["headers"] = headers

                if method == "POST":
                    async with session.post(target_url, json=request_data, **kwargs) as resp:
                        data = await resp.json()
                        latency = (time.perf_counter() - start_time) * 1000
                        return ChannelResult(
                            success=resp.status < 400,
                            channel_type=ChannelType.DIRECT,
                            data=data,
                            error="" if resp.status < 400 else f"HTTP {resp.status}",
                            latency_ms=latency,
                        )
                else:
                    async with session.get(target_url, **kwargs) as resp:
                        data = await resp.json()
                        latency = (time.perf_counter() - start_time) * 1000
                        return ChannelResult(
                            success=resp.status < 400,
                            channel_type=ChannelType.DIRECT,
                            data=data,
                            error="" if resp.status < 400 else f"HTTP {resp.status}",
                            latency_ms=latency,
                        )

        except asyncio.TimeoutError:
            latency = (time.perf_counter() - start_time) * 1000
            return ChannelResult(
                success=False,
                channel_type=ChannelType.DIRECT,
                error="连接超时",
                latency_ms=latency,
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return ChannelResult(
                success=False,
                channel_type=ChannelType.DIRECT,
                error=str(e),
                latency_ms=latency,
            )

    async def _channel_user_proxy(
        self,
        task_name: str,
        target_url: str,
        request_data: Dict[str, Any],
        method: str,
        headers: Dict[str, str],
        timeout: float,
    ) -> ChannelResult:
        """通道1：用户配置的代理（需用户显式启用）"""
        if not self._user_proxy.is_valid():
            return ChannelResult(
                success=False,
                channel_type=ChannelType.USER_PROXY,
                error="用户未配置代理或配置无效",
            )

        import time
        import aiohttp

        start_time = time.perf_counter()

        try:
            proxy_dict = self._user_proxy.get_proxy_dict()

            async with aiohttp.ClientSession() as session:
                kwargs = {
                    "timeout": aiohttp.ClientTimeout(total=timeout),
                    "proxy": proxy_dict["server"],
                }
                if headers:
                    kwargs["headers"] = headers
                if proxy_dict.get("auth"):
                    kwargs["proxy_auth"] = aiohttp.BasicAuth(
                        proxy_dict["auth"]["username"],
                        proxy_dict["auth"]["password"]
                    )

                if method == "POST":
                    async with session.post(target_url, json=request_data, **kwargs) as resp:
                        data = await resp.json()
                        latency = (time.perf_counter() - start_time) * 1000
                        return ChannelResult(
                            success=resp.status < 400,
                            channel_type=ChannelType.USER_PROXY,
                            data=data,
                            error="" if resp.status < 400 else f"HTTP {resp.status}",
                            latency_ms=latency,
                        )
                else:
                    async with session.get(target_url, **kwargs) as resp:
                        data = await resp.json()
                        latency = (time.perf_counter() - start_time) * 1000
                        return ChannelResult(
                            success=resp.status < 400,
                            channel_type=ChannelType.USER_PROXY,
                            data=data,
                            error="" if resp.status < 400 else f"HTTP {resp.status}",
                            latency_ms=latency,
                        )

        except asyncio.TimeoutError:
            latency = (time.perf_counter() - start_time) * 1000
            return ChannelResult(
                success=False,
                channel_type=ChannelType.USER_PROXY,
                error="代理连接超时",
                latency_ms=latency,
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return ChannelResult(
                success=False,
                channel_type=ChannelType.USER_PROXY,
                error=f"代理错误: {str(e)}",
                latency_ms=latency,
            )

    async def _channel_api_fallback(
        self,
        task_name: str,
        target_url: str,
        request_data: Dict[str, Any],
        method: str,
        headers: Dict[str, str],
        timeout: float,
    ) -> ChannelResult:
        """通道2：官方API通道"""
        service_name = self._extract_service_name(target_url)
        api_config = self._api_keys.get(service_name.lower())

        if not api_config or not api_config.is_valid():
            return ChannelResult(
                success=False,
                channel_type=ChannelType.API_FALLBACK,
                error=f"未配置 {service_name} 的API Key",
            )

        import time
        import aiohttp

        start_time = time.perf_counter()

        try:
            # 构建API请求
            api_url = api_config.base_url or self._get_default_api_url(service_name)
            headers = headers or {}
            headers["Authorization"] = f"Bearer {api_config.api_key}"
            headers["Content-Type"] = "application/json"

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    api_url,
                    json=request_data,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as resp:
                    data = await resp.json()
                    latency = (time.perf_counter() - start_time) * 1000
                    return ChannelResult(
                        success=resp.status < 400,
                        channel_type=ChannelType.API_FALLBACK,
                        data=data,
                        error="" if resp.status < 400 else f"API错误: {resp.status}",
                        latency_ms=latency,
                    )

        except asyncio.TimeoutError:
            latency = (time.perf_counter() - start_time) * 1000
            return ChannelResult(
                success=False,
                channel_type=ChannelType.API_FALLBACK,
                error="API请求超时",
                latency_ms=latency,
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return ChannelResult(
                success=False,
                channel_type=ChannelType.API_FALLBACK,
                error=str(e),
                latency_ms=latency,
            )

    async def _channel_local_llm(
        self,
        task_name: str,
        request_data: Dict[str, Any],
        timeout: float,
    ) -> ChannelResult:
        """通道3：本地LLM降级（Ollama等）"""
        import time
        import aiohttp

        if not self._local_llm.is_valid():
            return ChannelResult(
                success=False,
                channel_type=ChannelType.LOCAL_LLM,
                error="本地LLM未配置或不可用",
            )

        start_time = time.perf_counter()

        try:
            # Ollama API格式
            ollama_url = f"{self._local_llm.endpoint}/api/generate"

            payload = {
                "model": self._local_llm.model,
                "prompt": request_data.get("prompt", request_data.get("messages", [])),
                "stream": False,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    ollama_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=timeout or self._local_llm.timeout)
                ) as resp:
                    data = await resp.json()
                    latency = (time.perf_counter() - start_time) * 1000

                    return ChannelResult(
                        success=resp.status < 400,
                        channel_type=ChannelType.LOCAL_LLM,
                        data={"response": data.get("response", ""), "source": "local_llm"},
                        error="" if resp.status < 400 else f"本地LLM错误: {resp.status}",
                        latency_ms=latency,
                    )

        except asyncio.TimeoutError:
            latency = (time.perf_counter() - start_time) * 1000
            return ChannelResult(
                success=False,
                channel_type=ChannelType.LOCAL_LLM,
                error="本地LLM响应超时",
                latency_ms=latency,
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return ChannelResult(
                success=False,
                channel_type=ChannelType.LOCAL_LLM,
                error=str(e),
                latency_ms=latency,
            )

    async def _channel_offline_queue(
        self,
        task_name: str,
        request_data: Dict[str, Any],
    ) -> ChannelResult:
        """通道4：离线队列（最后保障）"""
        if self._offline_queue:
            task_id = await self._offline_queue.add_task(task_name, request_data)
            return ChannelResult(
                success=True,
                channel_type=ChannelType.OFFLINE_QUEUE,
                data={"task_id": task_id, "status": "queued"},
                error="任务已存入离线队列，待网络恢复后重试",
            )

        return ChannelResult(
            success=False,
            channel_type=ChannelType.OFFLINE_QUEUE,
            error="离线队列不可用",
        )

    # ==================== 辅助方法 ====================

    def _extract_service_name(self, url: str) -> str:
        """从URL提取服务名"""
        try:
            from urllib.parse import urlparse
            host = urlparse(url).netloc.lower()
            if "openai" in host:
                return "openai"
            elif "anthropic" in host:
                return "anthropic"
            elif "deepseek" in host:
                return "deepseek"
            elif "google" in host or "gemini" in host:
                return "google"
            elif "zhipu" in host:
                return "zhipu"
            elif "baidu" in host:
                return "baidu"
            elif "aliyun" in host or "dashscope" in host:
                return "aliyun"
            else:
                return "unknown"
        except:
            return "unknown"

    def _get_default_api_url(self, service_name: str) -> str:
        """获取默认API URL"""
        defaults = {
            "openai": "https://api.openai.com/v1/chat/completions",
            "deepseek": "https://api.deepseek.com/v1/chat/completions",
            "anthropic": "https://api.anthropic.com/v1/messages",
            "google": "https://generativelanguage.googleapis.com/v1beta/models",
            "zhipu": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        }
        return defaults.get(service_name, "")

    async def _handle_all_channels_failed(
        self,
        task_name: str,
        target_url: str,
        request_data: Dict[str, Any],
        last_error: str,
    ):
        """所有通道失败后的处理"""
        logger.error(f"所有通道均失败: {last_error}")

        # 尝试存入离线队列
        if self._offline_queue:
            await self._offline_queue.add_task(task_name, request_data)
            logger.info(f"任务已存入离线队列: {task_name}")

        self._notify_listeners("all_channels_failed", {
            "task_name": task_name,
            "target_url": target_url,
            "last_error": last_error,
        })

    # ==================== 状态管理 ====================

    def _record_success(self, channel_type: ChannelType, latency_ms: float):
        """记录成功"""
        self._channel_status[channel_type] = ChannelStatus.AVAILABLE
        # 滑动平均更新延迟
        if channel_type in self._channel_latency:
            self._channel_latency[channel_type] = self._channel_latency[channel_type] * 0.7 + latency_ms * 0.3
        else:
            self._channel_latency[channel_type] = latency_ms
        # 清除错误计数
        self._channel_errors[channel_type] = 0

    def _record_failure(self, channel_type: ChannelType, error: str):
        """记录失败"""
        self._channel_status[channel_type] = ChannelStatus.ERROR
        self._channel_errors[channel_type] = self._channel_errors.get(channel_type, 0) + 1

    def get_channel_stats(self) -> Dict[str, Any]:
        """获取通道统计"""
        stats = {}
        for channel_type in ChannelType:
            stats[channel_type.value] = {
                "status": self._channel_status.get(channel_type, ChannelStatus.SKIPPED).value,
                "latency_ms": round(self._channel_latency.get(channel_type, 0), 2),
                "error_count": self._channel_errors.get(channel_type, 0),
            }
        return stats

    def get_best_available_channel(self) -> Optional[ChannelType]:
        """获取最佳可用通道"""
        for channel_type in self._channels:
            if self._channel_status.get(channel_type) == ChannelStatus.AVAILABLE:
                return channel_type
        return None

    # ==================== 事件监听 ====================

    def subscribe(self, callback: Callable):
        """订阅事件"""
        self._listeners.append(callback)
        return lambda: self._listeners.remove(callback)

    def _notify_listeners(self, event: str, data: Any):
        """通知监听器"""
        for listener in self._listeners:
            try:
                listener(event, data)
            except Exception as e:
                logger.error(f"监听器回调错误: {e}")

    # ==================== 生命周期 ====================

    async def start(self):
        """启动通道管理器"""
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("通道管理器已启动")

    async def stop(self):
        """停止通道管理器"""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        logger.info("通道管理器已停止")

    async def _heartbeat_loop(self):
        """心跳检测：定期检测通道可用性"""
        while self._running:
            try:
                # 重置错误计数（连续成功则重置）
                for channel_type in self._channel_errors:
                    if self._channel_errors[channel_type] > 0:
                        self._channel_errors[channel_type] -= 1
            except Exception as e:
                logger.error(f"心跳检测错误: {e}")

            await asyncio.sleep(60)  # 每分钟一次


# 单例实例
_channel_manager: Optional[ChannelManager] = None


def get_channel_manager() -> ChannelManager:
    """获取通道管理器单例"""
    global _channel_manager
    if _channel_manager is None:
        _channel_manager = ChannelManager()
    return _channel_manager