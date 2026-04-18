"""
RelayFreeLLM 网关服务器
统一入口，动态加载厂商配置
"""

import json
import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from .providers.dynamic_provider import ProviderFactory
from .router import IntelligentRouter, register_router, get_router, RouterRegistry

logger = logging.getLogger(__name__)


class RelayFreeServer:
    """
    RelayFreeLLM 网关服务器
    
    职责:
    1. 加载厂商配置
    2. 动态注册 Provider
    3. 启动 HTTP/WebSocket 接口
    4. 管理路由策略
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
        
        self.config_dir = Path(__file__).parent / "config"
        self.providers_config_path = self.config_dir / "providers_config.json"
        self.env_file = self.config_dir / ".env"
        
        self.providers: Dict[str, Any] = {}
        self.router: Optional[IntelligentRouter] = None
        self._running = False
        
        self._initialized = True
        logger.info("[RelayFree] RelayFreeLLM 网关初始化")

    def load_config(self) -> Dict[str, Any]:
        """加载厂商配置"""
        if not self.providers_config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.providers_config_path}")
        
        with open(self.providers_config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        logger.info(f"[RelayFree] 加载配置: version={config.get('version')}")
        return config

    def load_env(self):
        """加载环境变量 (如果 .env 存在)"""
        if self.env_file.exists():
            logger.info(f"[RelayFree] 加载环境变量: {self.env_file}")
            with open(self.env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ.setdefault(key.strip(), value.strip())

    async def initialize(self):
        """
        初始化服务器
        
        1. 加载环境变量
        2. 加载厂商配置
        3. 创建 Provider 实例
        4. 初始化路由器
        """
        logger.info("[RelayFree] 开始初始化...")
        
        # 1. 加载环境变量
        self.load_env()
        
        # 2. 加载厂商配置
        config = self.load_config()
        
        # 3. 动态创建 Provider
        self.providers = ProviderFactory.create_all(config)
        logger.info(f"[RelayFree] 已加载 {len(self.providers)} 个 Provider")
        
        # 4. 初始化路由器
        routing_rules = config.get("routing_rules", {})
        self.router = IntelligentRouter(self.providers, routing_rules)
        register_router("default", self.router)
        
        # 5. 健康检查 (并行)
        await self._health_check_all()
        
        logger.info(f"[RelayFree] 初始化完成: {sum(1 for p in self.providers.values() if p.is_healthy)}/{len(self.providers)} Provider 健康")
        return self

    async def _health_check_all(self):
        """并发健康检查所有 Provider"""
        tasks = []
        for provider in self.providers.values():
            tasks.append(self._check_provider_health(provider))
        
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_provider_health(self, provider):
        """检查单个 Provider 健康状态"""
        try:
            is_healthy = await asyncio.wait_for(provider.health_check(), timeout=5)
            if not is_healthy:
                provider.status = provider.Status.DEGRADED if hasattr(provider, 'Status') else None
                logger.warning(f"[RelayFree] Provider {provider.provider_id} 健康检查失败")
        except asyncio.TimeoutError:
            logger.warning(f"[RelayFree] Provider {provider.provider_id} 健康检查超时")
        except Exception as e:
            logger.warning(f"[RelayFree] Provider {provider.provider_id} 健康检查异常: {e}")

    async def chat_completions(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        统一的 chat completions 接口
        
        兼容 OpenAI API 格式
        """
        if not self.router:
            raise Exception("服务器未初始化")
        
        provider, result = await self.router.route_and_execute(
            model=model,
            messages=messages,
            **kwargs
        )
        
        # 添加元信息
        result["_provider"] = provider.provider_id
        result["_routed_at"] = datetime.now().isoformat()
        
        return result

    async def chat_completions_stream(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        **kwargs
    ):
        """
        流式 chat completions
        """
        if not self.router:
            raise Exception("服务器未初始化")
        
        provider, generator = await self.router.route_and_execute(
            model=model,
            messages=messages,
            stream=True,
            **kwargs
        )
        
        # 包装生成器，添加元信息
        async for chunk in generator:
            chunk["_provider"] = provider.provider_id
            yield chunk

    def list_providers(self) -> List[Dict[str, Any]]:
        """列出所有 Provider"""
        return [p.to_dict() for p in self.providers.values()]

    def get_router_stats(self) -> Dict[str, Any]:
        """获取路由统计"""
        if self.router:
            return self.router.get_routing_stats()
        return {}

    async def shutdown(self):
        """关闭服务器"""
        logger.info("[RelayFree] 关闭服务器...")
        self._running = False
        
        # 关闭所有 Provider
        for provider in self.providers.values():
            if hasattr(provider, 'close'):
                await provider.close()
        
        logger.info("[RelayFree] 服务器已关闭")


# ==================== 快捷函数 ====================

_server_instance: Optional[RelayFreeServer] = None


async def get_server() -> RelayFreeServer:
    """获取服务器单例"""
    global _server_instance
    if _server_instance is None:
        _server_instance = RelayFreeServer()
        await _server_instance.initialize()
    return _server_instance


async def chat_completions(model: str, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
    """快捷调用"""
    server = await get_server()
    return await server.chat_completions(model, messages, **kwargs)


def list_providers() -> List[Dict[str, Any]]:
    """列出所有 Provider"""
    server = _server_instance
    if server:
        return server.list_providers()
    return []


# ==================== Flask/FastAPI 集成接口 ====================

"""
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/v1/chat/completions", methods=["POST"])
async def chat_completions():
    data = request.json
    result = await chat_completions(
        model=data.get("model", "gpt-3.5"),
        messages=data.get("messages", []),
        **{k: v for k, v in data.items() if k not in ["model", "messages"]}
    )
    return jsonify(result)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
"""