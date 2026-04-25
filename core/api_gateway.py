"""
API Gateway - 统一API网关代理
===============================

解决"付费API不能分布式调用"的问题：

1. 所有设备将请求发给你的私有服务器
2. 服务器统一调用 OpenAI/Azure API
3. 外部API只看到一个IP，避免IP绑定限制
4. 密钥集中管理，避免多设备泄露风险

核心功能：
- 请求路由与负载均衡
- 密钥集中管理与审计
- 用量统计与限流
- 缓存与结果复用

Author: Hermes Desktop AI Assistant
"""

import json
import time
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
from enum import Enum

logger = logging.getLogger(__name__)

# 统一配置导入
try:
    from core.config.unified_config import get_api_gateway_config
except ImportError:
    get_api_gateway_config = None


def _get_gateway_timeout() -> int:
    """获取网关超时配置"""
    if get_api_gateway_config:
        try:
            return get_api_gateway_config().get("timeout", 60)
        except Exception:
            pass
    return 60


class GatewayProvider(Enum):
    """支持的API提供商"""
    OPENAI = "openai"
    AZURE = "azure"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    CUSTOM = "custom"


@dataclass
class APIKey:
    """API密钥配置"""
    provider: GatewayProvider
    key: str
    endpoint: str
    model: str
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    rate_limit: int = 60  # 每分钟请求数
    daily_limit: int = 1000  # 每日请求数


@dataclass
class UsageRecord:
    """使用记录"""
    timestamp: datetime
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    device_id: str
    cache_hit: bool = False


@dataclass
class GatewayRequest:
    """网关请求"""
    provider: str
    model: str
    messages: List[Dict[str, str]]
    max_tokens: int = 4096
    temperature: float = 0.7
    device_id: str = "unknown"
    request_id: str = ""


@dataclass
class GatewayResponse:
    """网关响应"""
    success: bool
    content: str = ""
    model: str = ""
    tokens_used: int = 0
    cost: float = 0.0
    cached: bool = False
    error: str = ""
    request_id: str = ""


class APIGateway:
    """
    API统一网关

    作为单一入口，将所有AI请求路由到正确的API提供商
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "~/.hermes/gateway_config.json"
        self.config_path = Path(self.config_path).expanduser()
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # 密钥存储
        self.keys: Dict[GatewayProvider, APIKey] = {}

        # 用量统计
        self.usage_records: List[UsageRecord] = []
        self.daily_usage: Dict[str, int] = defaultdict(int)  # provider -> count
        self.monthly_cost: Dict[str, float] = defaultdict(float)

        # 请求缓存 (request_hash -> response)
        self.response_cache: Dict[str, GatewayResponse] = {}

        # 限流器
        self.minute_requests: Dict[str, List[float]] = defaultdict(list)  # provider -> timestamps

        # 设备注册
        self.registered_devices: Dict[str, Dict[str, Any]] = {}

        # 加载配置
        self._load_config()

        logger.info("API Gateway initialized")

    def _load_config(self):
        """加载配置"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 加载密钥
                for provider_str, key_data in data.get("keys", {}).items():
                    try:
                        provider = GatewayProvider(provider_str)
                        self.keys[provider] = APIKey(
                            provider=provider,
                            key=key_data.get("key", ""),
                            endpoint=key_data.get("endpoint", ""),
                            model=key_data.get("model", ""),
                            cost_per_1k_input=key_data.get("cost_input", 0.001),
                            cost_per_1k_output=key_data.get("cost_output", 0.002),
                            rate_limit=key_data.get("rate_limit", 60),
                            daily_limit=key_data.get("daily_limit", 1000)
                        )
                    except ValueError:
                        pass

                # 加载设备
                self.registered_devices = data.get("devices", {})

                logger.info(f"Loaded {len(self.keys)} API keys and {len(self.registered_devices)} devices")

            except Exception as e:
                logger.error(f"Failed to load gateway config: {e}")

    def _save_config(self):
        """保存配置"""
        try:
            data = {
                "keys": {
                    provider.value: {
                        "key": key.key,
                        "endpoint": key.endpoint,
                        "model": key.model,
                        "cost_input": key.cost_per_1k_input,
                        "cost_output": key.cost_per_1k_output,
                        "rate_limit": key.rate_limit,
                        "daily_limit": key.daily_limit
                    }
                    for provider, key in self.keys.items()
                },
                "devices": self.registered_devices
            }

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Failed to save gateway config: {e}")

    def register_key(self, provider: GatewayProvider, key: str,
                    endpoint: str, model: str,
                    cost_input: float = 0.001,
                    cost_output: float = 0.002):
        """注册API密钥"""
        self.keys[provider] = APIKey(
            provider=provider,
            key=key,
            endpoint=endpoint,
            model=model,
            cost_per_1k_input=cost_input,
            cost_per_1k_output=cost_output
        )
        self._save_config()
        logger.info(f"Registered API key for {provider.value}")

    def register_device(self, device_id: str, device_info: Dict[str, Any]):
        """注册设备"""
        self.registered_devices[device_id] = {
            **device_info,
            "registered_at": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat()
        }
        self._save_config()
        logger.info(f"Registered device: {device_id}")

    def _check_rate_limit(self, provider: GatewayProvider) -> bool:
        """检查限流"""
        if provider not in self.keys:
            return False

        key = self.keys[provider]
        now = time.time()

        # 清理过期记录
        self.minute_requests[provider.value] = [
            ts for ts in self.minute_requests[provider.value]
            if now - ts < 60
        ]

        # 检查每分钟限流
        if len(self.minute_requests[provider.value]) >= key.rate_limit:
            return False

        # 检查每日限流
        today = datetime.now().strftime("%Y-%m-%d")
        if self.daily_usage.get(f"{provider.value}_{today}", 0) >= key.daily_limit:
            return False

        return True

    def _record_request(self, provider: GatewayProvider, tokens: int, cost: float):
        """记录请求"""
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        self.minute_requests[provider.value].append(time.time())
        self.daily_usage[f"{provider.value}_{today}"] += 1
        self.monthly_cost[provider.value] += cost

    def _get_cache_key(self, request: GatewayRequest) -> str:
        """生成缓存键"""
        data = json.dumps({
            "model": request.model,
            "messages": request.messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    async def forward_request(self, request: GatewayRequest) -> GatewayResponse:
        """
        转发请求到API提供商

        Args:
            request: 网关请求

        Returns:
            GatewayResponse: 网关响应
        """
        # 1. 确定provider
        try:
            provider = GatewayProvider(request.provider)
        except ValueError:
            return GatewayResponse(
                success=False,
                error=f"Unknown provider: {request.provider}",
                request_id=request.request_id
            )

        # 2. 检查密钥
        if provider not in self.keys:
            return GatewayResponse(
                success=False,
                error=f"No API key registered for {request.provider}",
                request_id=request.request_id
            )

        key = self.keys[provider]

        # 3. 检查限流
        if not self._check_rate_limit(provider):
            return GatewayResponse(
                success=False,
                error="Rate limit exceeded",
                request_id=request.request_id
            )

        # 4. 检查缓存
        cache_key = self._get_cache_key(request)
        if cache_key in self.response_cache:
            cached = self.response_cache[cache_key]
            cached.cached = True
            logger.info(f"Cache hit for request {request.request_id}")
            return cached

        # 5. 转发请求
        try:
            if provider == GatewayProvider.OPENAI:
                response = await self._call_openai(request, key)
            elif provider == GatewayProvider.AZURE:
                response = await self._call_azure(request, key)
            elif provider == GatewayProvider.ANTHROPIC:
                response = await self._call_anthropic(request, key)
            else:
                response = await self._call_custom(request, key)

            # 6. 缓存结果
            self.response_cache[cache_key] = response

            # 7. 记录用量
            self._record_request(provider, response.tokens_used, response.cost)

            return response

        except Exception as e:
            logger.error(f"API call failed: {e}")
            return GatewayResponse(
                success=False,
                error=str(e),
                request_id=request.request_id
            )

    async def _call_openai(self, request: GatewayRequest, key: APIKey) -> GatewayResponse:
        """调用OpenAI API"""
        import aiohttp

        headers = {
            "Authorization": f"Bearer {key.key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": request.model or key.model,
            "messages": request.messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature
        }

        url = f"{key.endpoint}/chat/completions" if key.endpoint else "https://api.openai.com/v1/chat/completions"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=_get_gateway_timeout()) as resp:
                result = await resp.json()

        if resp.status != 200:
            return GatewayResponse(
                success=False,
                error=result.get("error", {}).get("message", "Unknown error"),
                request_id=request.request_id
            )

        choices = result.get("choices", [])
        content = choices[0].get("message", {}).get("content", "") if choices else ""

        usage = result.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        cost = (input_tokens / 1000 * key.cost_per_1k_input +
               output_tokens / 1000 * key.cost_per_1k_output)

        return GatewayResponse(
            success=True,
            content=content,
            model=result.get("model", key.model),
            tokens_used=input_tokens + output_tokens,
            cost=cost,
            request_id=request.request_id
        )

    async def _call_azure(self, request: GatewayRequest, key: APIKey) -> GatewayResponse:
        """调用Azure OpenAI API"""
        import aiohttp

        headers = {
            "api-key": key.key,
            "Content-Type": "application/json"
        }

        payload = {
            "messages": request.messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature
        }

        url = f"{key.endpoint}/chat/completions?api-version=2024-02-01"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=_get_gateway_timeout()) as resp:
                result = await resp.json()

        if resp.status != 200:
            return GatewayResponse(
                success=False,
                error=result.get("error", {}).get("message", "Unknown error"),
                request_id=request.request_id
            )

        choices = result.get("choices", [])
        content = choices[0].get("message", {}).get("content", "") if choices else ""

        usage = result.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        cost = (input_tokens / 1000 * key.cost_per_1k_input +
               output_tokens / 1000 * key.cost_per_1k_output)

        return GatewayResponse(
            success=True,
            content=content,
            model=result.get("model", key.model),
            tokens_used=input_tokens + output_tokens,
            cost=cost,
            request_id=request.request_id
        )

    async def _call_anthropic(self, request: GatewayRequest, key: APIKey) -> GatewayResponse:
        """调用Anthropic API"""
        import aiohttp

        headers = {
            "x-api-key": key.key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }

        # 转换消息格式
        system_msg = ""
        user_msgs = []
        for msg in request.messages:
            if msg.get("role") == "system":
                system_msg = msg.get("content", "")
            else:
                user_msgs.append(msg)

        payload = {
            "model": request.model or key.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "system": system_msg,
            "messages": [{"role": m.get("role"), "content": m.get("content")} for m in user_msgs]
        }

        url = f"{key.endpoint}/v1/messages" if key.endpoint else "https://api.anthropic.com/v1/messages"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=_get_gateway_timeout()) as resp:
                result = await resp.json()

        if resp.status != 200:
            return GatewayResponse(
                success=False,
                error=result.get("error", {}).get("message", "Unknown error"),
                request_id=request.request_id
            )

        content = result.get("content", [{}])[0].get("text", "")

        usage = result.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cost = (input_tokens / 1000 * key.cost_per_1k_input +
               output_tokens / 1000 * key.cost_per_1k_output)

        return GatewayResponse(
            success=True,
            content=content,
            model=result.get("model", key.model),
            tokens_used=input_tokens + output_tokens,
            cost=cost,
            request_id=request.request_id
        )

    async def _call_custom(self, request: GatewayRequest, key: APIKey) -> GatewayResponse:
        """调用自定义API"""
        # 扩展支持其他API
        return GatewayResponse(
            success=False,
            error="Custom provider not implemented",
            request_id=request.request_id
        )

    def get_usage_stats(self, provider: Optional[str] = None,
                       days: int = 30) -> Dict[str, Any]:
        """获取用量统计"""
        now = datetime.now()
        cutoff = now - timedelta(days=days)

        filtered = [r for r in self.usage_records if r.timestamp > cutoff]

        if provider:
            filtered = [r for r in filtered if r.provider == provider]

        total_cost = sum(r.cost for r in filtered)
        total_tokens = sum(r.tokens_used for r in filtered)
        cache_hits = sum(1 for r in filtered if r.cache_hit)

        # 按设备统计
        by_device = defaultdict(lambda: {"requests": 0, "cost": 0.0, "tokens": 0})
        for r in filtered:
            by_device[r.device_id]["requests"] += 1
            by_device[r.device_id]["cost"] += r.cost
            by_device[r.device_id]["tokens"] += r.tokens_used

        return {
            "period_days": days,
            "total_requests": len(filtered),
            "total_cost": total_cost,
            "total_tokens": total_tokens,
            "cache_hit_rate": cache_hits / len(filtered) if filtered else 0,
            "by_device": dict(by_device),
            "daily_cost": dict(self.monthly_cost)
        }

    def get_registered_devices(self) -> List[Dict[str, Any]]:
        """获取注册设备列表"""
        return [
            {**info, "device_id": device_id}
            for device_id, info in self.registered_devices.items()
        ]

    def clear_cache(self, max_age_hours: int = 24):
        """清理缓存"""
        cutoff = time.time() - (max_age_hours * 3600)
        original_size = len(self.response_cache)

        self.response_cache = {
            k: v for k, v in self.response_cache.items()
            if hasattr(v, '_timestamp') and v._timestamp > cutoff
        }

        removed = original_size - len(self.response_cache)
        logger.info(f"Cleared {removed} cached responses")
        return removed


# 全局实例
_gateway: Optional[APIGateway] = None


def get_api_gateway() -> APIGateway:
    """获取全局API网关"""
    global _gateway
    if _gateway is None:
        _gateway = APIGateway()
    return _gateway