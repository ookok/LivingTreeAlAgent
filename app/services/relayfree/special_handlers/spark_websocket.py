"""
讯飞星火 WebSocket Provider
非标准协议，需要 WebSocket 特殊处理
"""

import asyncio
import json
import hashlib
import base64
import time
import hmac
from typing import Dict, Any, List, Optional, AsyncIterator
import logging
import sys
import os

# 动态添加项目路径以支持跨模块导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from app.services.relayfree.providers.base import BaseProvider, BaseProviderConfig

logger = logging.getLogger(__name__)


class SparkWebSocketProvider(BaseProvider):
    """
    讯飞星火 Provider
    
    协议: WebSocket (RFC 6455)
    鉴权: AppID + APIKey + APISecret 签名
    """

    def __init__(self, provider_id: str, config: Dict[str, Any]):
        base_config = BaseProviderConfig(
            provider_id=provider_id,
            base_url=config.get("base_url", "wss://spark-api.xf-yun.com/v3.5/chat"),
            auth="spark_ws",
            key_env_var=config.get("key_env_var"),      # AppID
            secret_env_var=config.get("secret_env_var"),  # APIKey
            secret2_env_var=config.get("secret2_env_var"),  # APISecret
            priority=config.get("priority", 460),
            timeout=config.get("timeout", 120),
            capabilities=["chat"],
            model_mapping=config.get("model_mapping", {}),
            enabled=config.get("enabled", True),
            description="讯飞星火 (WebSocket)"
        )
        super().__init__(base_config)
        self._config = config
        self._ws_pool: Dict[str, Any] = {}

    def _generate_auth_url(self) -> str:
        """
        生成讯飞鉴权 URL
        
        签名算法:
        RFC2104 HMAC-SHA256
        """
        app_id = self.get_api_key()      # AppID
        api_key = self.get_secret_key() # APIKey
        api_secret = self.get_secret2_key()  # APISecret
        
        if not all([app_id, api_key, api_secret]):
            raise ValueError("讯飞星火需要 AppID, APIKey 和 APISecret")
        
        # 生成 RFC1123 格式时间戳
        now = time.time()
        ts = time.strftime("%a %b %d %H:%M:%S GMT", time.gmtime(now))
        
        # 构造签名原文
        signature_origin = f"host: spark-api.xf-yun.com\ndate: {ts}\nGET /v3.5/chat HTTP/1.1"
        
        # HMAC-SHA256 签名
        signature_sha = hmac.new(
            api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        signature_sha_b64 = base64.b64encode(signature_sha).decode("utf-8")
        
        # 构造 authorization_origin
        authorization_origin = (
            f'api_key="{api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", '
            f'signature="{signature_sha_b64}"'
        )
        authorization_b64 = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")
        
        # 构造 URL
        url = (
            f"{self.config.base_url}"
            f"?authorization={authorization_b64}"
            f"&date={ts.replace(' ', '%20')}"
            f"&host=spark-api.xf-yun.com"
        )
        
        return url

    async def create_completion(
        self, model: str, messages: List[Dict[str, Any]], **kwargs
    ) -> Dict[str, Any]:
        """
        讯飞星火对话请求 (WebSocket)
        
        返回 OpenAI 兼容格式
        """
        real_model = self.map_model(model)
        app_id = self.get_api_key()
        
        # 构建讯飞消息格式
        payload = {
            "header": {"app_id": app_id},
            "parameter": {
                "chat": {
                    "domain": real_model,
                    "temperature": kwargs.get("temperature", 0.5),
                    "max_tokens": kwargs.get("max_tokens", 2048),
                    "top_k": kwargs.get("top_k", 4)
                }
            },
            "payload": {
                "message": {
                    "text": self._format_messages(messages)
                }
            }
        }
        
        # WebSocket 连接
        url = self._generate_auth_url()
        
        try:
            import websockets
            async with websockets.connect(url) as ws:
                await ws.send(json.dumps(payload))
                
                full_content = ""
                async for msg in ws:
                    data = json.loads(msg)
                    
                    # 解析讯飞响应
                    code = data.get("header", {}).get("code", 0)
                    if code != 0:
                        raise Exception(f"讯飞 API 错误: {data}")
                    
                    choices = data.get("payload", {}).get("choices", {})
                    status = choices.get("status", 0)
                    content_list = choices.get("text", [])
                    
                    for content in content_list:
                        full_content += content.get("content", "")
                    
                    if status == 2:  # 完成
                        break
                
                # 转换为 OpenAI 格式
                return {
                    "choices": [{
                        "message": {"role": "assistant", "content": full_content},
                        "finish_reason": "stop",
                        "index": 0
                    }],
                    "model": model,
                    "object": "chat.completion"
                }
                
        except ImportError:
            raise ImportError("需要安装 websockets 库: pip install websockets")
        except Exception as e:
            logger.error(f"[{self.provider_id}] 请求失败: {e}")
            self.mark_unhealthy(str(e))
            raise

    def _format_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        格式化消息为讯飞文本聊天格式
        
        讯飞要求 text 格式:
        [{"role": "user", "content": "xxx"}, {"role": "assistant", "content": "xxx"}]
        """
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "system":
                role = "user"  # 讯飞不支持 system
            formatted.append({
                "role": role,
                "content": msg.get("content", "")
            })
        return formatted

    async def create_completion_stream(
        self, model: str, messages: List[Dict[str, Any]], **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        讯飞星火流式请求 (SSE via WebSocket)
        """
        real_model = self.map_model(model)
        app_id = self.get_api_key()
        
        payload = {
            "header": {"app_id": app_id},
            "parameter": {
                "chat": {
                    "domain": real_model,
                    "temperature": kwargs.get("temperature", 0.5),
                    "max_tokens": kwargs.get("max_tokens", 2048),
                    "top_k": kwargs.get("top_k", 4),
                    "stream": True
                }
            },
            "payload": {
                "message": {
                    "text": self._format_messages(messages)
                }
            }
        }
        
        url = self._generate_auth_url()
        
        try:
            import websockets
            async with websockets.connect(url) as ws:
                await ws.send(json.dumps(payload))
                
                async for msg in ws:
                    data = json.loads(msg)
                    
                    code = data.get("header", {}).get("code", 0)
                    if code != 0:
                        raise Exception(f"讯飞 API 错误: {data}")
                    
                    choices = data.get("payload", {}).get("choices", {})
                    status = choices.get("status", 0)
                    content_list = choices.get("text", [])
                    
                    for content in content_list:
                        yield {
                            "choices": [{
                                "delta": {"content": content.get("content", "")},
                                "index": 0,
                                "finish_reason": None
                            }]
                        }
                    
                    if status == 2:
                        yield {"choices": [{"delta": {}, "index": 0, "finish_reason": "stop"}]}
                        break
                        
        except ImportError:
            raise ImportError("需要安装 websockets 库")
        except Exception as e:
            logger.error(f"[{self.provider_id}] 流式请求失败: {e}")
            raise

    async def list_models(self) -> List[Dict[str, Any]]:
        """列出可用模型"""
        return [
            {"id": "spark4.0 Ultra", "name": "星火4.0 Ultra", "object": "model"},
            {"id": "spark4.0", "name": "星火4.0", "object": "model"},
            {"id": "spark3.5", "name": "星火3.5", "object": "model"},
            {"id": "spark3.0", "name": "星火3.0", "object": "model"}
        ]

    async def health_check(self) -> bool:
        try:
            return bool(self.get_api_key() and self.get_secret_key() and self.get_secret2_key())
        except Exception:
            return False