"""
RelayFreeLLM - 清单驱动的多模型网关

核心思想: 拆除硬编码，换为清单驱动 + 动态注册

使用示例:
```python
import asyncio
from app.services.relayfree import get_server, chat_completions

async def main():
    # 初始化服务器
    server = await get_server()
    
    # 列出所有 Provider
    providers = server.list_providers()
    print(providers)
    
    # 发起请求 (自动路由)
    result = await chat_completions(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello!"}]
    )
    print(result)

asyncio.run(main())
```

架构:
- config/providers_config.json: 厂商配置清单 (可云端同步)
- providers/dynamic_provider.py: 万能 Provider (标准 OpenAI 协议)
- providers/special_handlers/: 非标准厂商特殊处理 (百度千帆、讯飞星火)
- router.py: 智能路由 (意图匹配 + 优先级 + 健康状态)
- server.py: 网关入口
"""

__version__ = "2026.04"
__author__ = "Hermes Desktop"

from .providers.base import BaseProvider, BaseProviderConfig, ProviderStatus, ProviderMetrics
from .providers.dynamic_provider import GenericProvider, ProviderFactory
from .router import IntelligentRouter, RouteContext, get_router, register_router
from .server import RelayFreeServer, get_server, chat_completions, list_providers

__all__ = [
    # 核心类
    "BaseProvider",
    "BaseProviderConfig", 
    "ProviderStatus",
    "ProviderMetrics",
    "GenericProvider",
    "ProviderFactory",
    "IntelligentRouter",
    "RouteContext",
    "RelayFreeServer",
    # 快捷函数
    "get_server",
    "chat_completions",
    "list_providers",
    "get_router",
    "register_router",
]