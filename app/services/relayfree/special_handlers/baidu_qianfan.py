"""
百度千帆 Provider (AK/SK 签名鉴权)
非标准协议，需要特殊处理
"""

import time
import hashlib
import hmac
import base64
import urllib.parse
from typing import Dict, Any, List, Optional, AsyncIterator
import httpx
import json
import logging
import sys
import os

# 动态添加项目路径以支持跨模块导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from app.services.relayfree.providers.base import BaseProvider, BaseProviderConfig

logger = logging.getLogger(__name__)


class BaiduQianfanProvider(BaseProvider):
    """
    百度千帆 Provider
    
    鉴权方式: AK/SK 签名 (HMAC-SHA256)
    API: 需通过 Application 发起对话
    """

    def __init__(self, provider_id: str, config: Dict[str, Any]):
        base_config = BaseProviderConfig(
            provider_id=provider_id,
            base_url=config.get("base_url", "https://qianfan.baidubce.com"),
            auth="ak_sk",
            key_env_var=config.get("key_env_var"),
            secret_env_var=config.get("secret_env_var"),
            priority=config.get("priority", 480),
            timeout=config.get("timeout", 60),
            capabilities=["chat"],
            model_mapping=config.get("model_mapping", {}),
            enabled=config.get("enabled", True),
            description="百度千帆 (AK/SK鉴权)"
        )
        super().__init__(base_config)
        self._config = config
        self._client: Optional[httpx.AsyncClient] = None

    def _generate_signature(self, ak: str, sk: str, method: str, path: str, 
                           params: Dict[str, str], timestamp: int) -> str:
        """生成 AK/SK 签名"""
        # 1. 拼接签名字符串
        signed_headers = "host;x-bce-date"
        canonical_request = f"{method}\n{path}\n{urllib.parse.urlencode(params)}\nhost={'qianfan.baidubce.com'}\nx-bce-date={timestamp}"
        
        # 2. 使用 SK 进行 HMAC-SHA256
        signing_key = hmac.new(
            sk.encode("utf-8"),
            canonical_request.encode("utf-8"),
            hashlib.sha256
        ).digest()
        
        # 3. Base64 编码
        return base64.b64encode(signing_key).decode("utf-8")

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.config.timeout))
        return self._client

    async def create_completion(
        self, model: str, messages: List[Dict[str, Any]], **kwargs
    ) -> Dict[str, Any]:
        """
        百度千帆对话请求
        
        需要 AK/SK 签名鉴权
        """
        real_model = self.map_model(model)
        ak = self.get_api_key()
        sk = self.get_secret_key()
        
        if not ak or not sk:
            raise ValueError("百度千帆需要 AK 和 SK")
        
        timestamp = int(time.time())
        
        # 构建请求
        url = f"{self.config.base_url}/v2/app/conversation"
        headers = {
            "Content-Type": "application/json",
            "X-App-Id": ak,  # 使用 AK 作为 App-ID
            "X-Timestamp": str(timestamp)
        }
        
        payload = {
            "model": real_model,
            "messages": self._format_messages(messages),
            **kwargs
        }
        
        # 生成签名
        signature = self._generate_signature(ak, sk, "POST", "/v2/app/conversation", 
                                              {}, timestamp)
        headers["Authorization"] = f"bce-auth-v2/{ak}/{timestamp}/1800/{signature}"
        
        async def _do():
            client = await self._get_client()
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
        
        return await self.with_retry(_do())
    
    def _format_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """格式化消息为千帆格式"""
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "system":
                role = "user"  # 千帆不支持 system 角色
            formatted.append({"role": role, "content": msg.get("content", "")})
        return formatted

    async def create_completion_stream(
        self, model: str, messages: List[Dict[str, Any]], **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """流式请求 (SSE)"""
        # 千帆流式返回也是 SSE 格式
        real_model = self.map_model(model)
        ak = self.get_api_key()
        sk = self.get_secret_key()
        
        if not ak or not sk:
            raise ValueError("百度千帆需要 AK 和 SK")
        
        timestamp = int(time.time())
        url = f"{self.config.base_url}/v2/app/conversation"
        
        headers = {
            "Content-Type": "application/json",
            "X-App-Id": ak,
            "X-Timestamp": str(timestamp),
            "Accept": "text/event-stream"
        }
        
        payload = {
            "model": real_model,
            "messages": self._format_messages(messages),
            "stream": True,
            **kwargs
        }
        
        signature = self._generate_signature(ak, sk, "POST", "/v2/app/conversation", 
                                              {}, timestamp)
        headers["Authorization"] = f"bce-auth-v2/{ak}/{timestamp}/1800/{signature}"
        
        client = await self._get_client()
        
        try:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            yield json.loads(data)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"[{self.provider_id}] 流式请求失败: {e}")
            raise

    async def list_models(self) -> List[Dict[str, Any]]:
        """列出可用模型"""
        # 千帆需要通过特定接口获取模型列表
        return [
            {"id": "eb-4", "name": "文心一言4.0", "object": "model"},
            {"id": "eb-3.5", "name": "文心一言3.5", "object": "model"},
            {"id": "eb-turbo", "name": "文心一言Turbo", "object": "model"}
        ]

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            return bool(self.get_api_key() and self.get_secret_key())
        except Exception:
            return False

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()