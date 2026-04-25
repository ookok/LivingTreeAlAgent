"""
A2A Webhook 服务器
支持 HMAC 签名的即时唤醒
"""

import hashlib
import hmac
import json
import time
import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass

try:
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from client.src.business.logger import get_logger

logger = get_logger('a2a_webhook')


@dataclass
class WebhookConfig:
    """Webhook 配置"""
    host: str = "0.0.0.0"
    port: int = 8765
    secret_key: str = ""


class WebhookHandler:
    """Webhook 请求处理器"""
    
    def __init__(self, gateway, secret_key: str):
        self._gateway = gateway
        self._secret_key = secret_key
        self._request_count = 0
    
    def _verify_signature(self, payload: bytes, signature: str) -> bool:
        """验证 HMAC 签名"""
        try:
            parts = signature.split('.')
            if len(parts) != 2:
                return False
            
            timestamp_str, sig = parts
            timestamp = int(timestamp_str)
            
            # 5分钟容差
            if abs(int(time.time() * 1000) - timestamp) > 300000:
                return False
            
            expected = hmac.new(
                self._secret_key.encode(),
                timestamp_str.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(sig, expected)
            
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False
    
    async def handle_request(self, request: web.Request) -> web.Response:
        """处理 Webhook 请求"""
        self._request_count += 1
        path = request.path
        
        if path == '/health':
            return web.json_response({'status': 'ok', 'requests': self._request_count})
        
        signature = request.headers.get('X-A2A-Signature', '')
        
        try:
            body = await request.read()
            payload = json.loads(body) if body else {}
            
            if path == '/webhook/instant_wake':
                success, message = await self._gateway.handle_webhook(payload, signature)
                if success:
                    return web.json_response({'status': 'ok', 'message': message})
                return web.json_response({'error': message}, status=400)
            
            elif path == '/webhook/task':
                result = await self._gateway.process_message(payload)
                return web.json_response(result or {'status': 'processed'})
            
            return web.json_response({'error': 'Unknown endpoint'}, status=404)
                
        except json.JSONDecodeError:
            return web.json_response({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return web.json_response({'error': str(e)}, status=500)


class A2AWebhookServer:
    """A2A Webhook 服务器"""
    
    def __init__(self, gateway, config: Optional[WebhookConfig] = None):
        if not AIOHTTP_AVAILABLE:
            raise ImportError("aiohttp required. Install: pip install aiohttp")
        
        self._gateway = gateway
        self._config = config or WebhookConfig()
        self._app = web.Application()
        self._handler = WebhookHandler(gateway, self._config.secret_key)
        self._runner = None
        self._site = None
        self._running = False
        
        self._app.router.add_route('*', '/{tail:.*}', self._handle_request)
    
    async def _handle_request(self, request: web.Request) -> web.Response:
        return await self._handler.handle_request(request)
    
    async def start(self):
        if self._running:
            return
        
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        
        self._site = web.TCPSite(self._runner, self._config.host, self._config.port)
        await self._site.start()
        
        self._running = True
        logger.info(f"A2A Webhook Server started on {self._config.host}:{self._config.port}")
    
    async def stop(self):
        if not self._running:
            return
        
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
        
        self._running = False
        logger.info("A2A Webhook Server stopped")


def create_webhook_server(gateway, host: str = "0.0.0.0", port: int = 8765, secret_key: str = "") -> A2AWebhookServer:
    """创建 Webhook 服务器"""
    config = WebhookConfig(host=host, port=port, secret_key=secret_key)
    return A2AWebhookServer(gateway, config)
