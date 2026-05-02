"""
LivingTree 前端桥接层
=====================

连接 Vue 前端与后端 LifeEngine。

包含：
- FrontendChannel: QWebChannel / WebSocket 通信
- BridgeAPI: REST API 接口
"""

import json
import uuid
from typing import Dict, Any, Optional, List, Callable, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FrontendRequest:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: str = "chat"
    content: str = ""
    session_id: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class FrontendResponse:
    request_id: str = ""
    type: str = "chat_response"
    content: str = ""
    streaming: bool = False
    is_final: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""
    processing_times: Dict[str, float] = field(default_factory=dict)


class FrontendChannel:
    """
    QWebChannel / WebSocket 桥接

    桥接 PyQt6 QWebChannel 和 Vue 前端之间的通信。
    前端通过 backend.js 发送消息，后端通过此 Channel 响应。
    """

    def __init__(self):
        self._message_handlers: Dict[str, Callable] = {}
        self._pending_requests: Dict[str, FrontendRequest] = {}
        self._life_engine = None

    def bind_life_engine(self, engine):
        self._life_engine = engine

    def on_message(self, message_type: str):
        """装饰器：注册消息处理器"""
        def decorator(func):
            self._message_handlers[message_type] = func
            return func
        return decorator

    async def handle_message(self, message_json: str) -> str:
        """处理前端消息，返回响应 JSON"""
        try:
            data = json.loads(message_json)
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid JSON"})

        msg_type = data.get("type", "chat")
        handler = self._message_handlers.get(msg_type)

        if handler:
            try:
                result = await handler(data)
                return json.dumps(result, ensure_ascii=False, default=str)
            except Exception as e:
                return json.dumps({"error": str(e), "type": "error"})

        return json.dumps({"error": f"Unknown message type: {msg_type}"})

    async def handle_chat(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """处理聊天请求"""
        content = data.get("content", "")
        session_id = data.get("sessionId", "")

        if not content.strip():
            return {"type": "chat_response", "content": "", "error": "Empty message"}

        if self._life_engine:
            try:
                response = await self._life_engine.process(
                    type("Stimulus", (), {"user_input": content, "metadata": {}})
                )
                return {
                    "type": "chat_response",
                    "content": response.text,
                    "trace_id": response.trace_id,
                    "metadata": {
                        "tokens_input": response.result.tokens_input,
                        "tokens_output": response.result.tokens_output,
                        "duration_ms": response.result.duration_ms,
                    },
                }
            except Exception as e:
                return {"type": "chat_response", "content": f"Error: {e}", "error": str(e)}

        return {
            "type": "chat_response",
            "content": f"[LifeEngine 未绑定] 收到消息: {content[:100]}",
        }

    async def stream_chat(self, content: str) -> AsyncGenerator[FrontendResponse, None]:
        """流式返回聊天响应"""
        if self._life_engine:
            response = await self._life_engine.process(
                type("Stimulus", (), {"user_input": content, "metadata": {}})
            )
            response_text = response.text
        else:
            response_text = f"[LifeEngine 未绑定] 收到: {content[:100]}"

        # 模拟流式返回（实际应逐Token输出）
        words = response_text.split()
        chunk_size = max(1, len(words) // 20)

        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            is_final = (i + chunk_size >= len(words))
            yield FrontendResponse(
                content=chunk,
                streaming=True,
                is_final=is_final,
            )

    def register_default_handlers(self):
        self._message_handlers["chat"] = self.handle_chat
        self._message_handlers["ping"] = lambda data: {"type": "pong"}
        self._message_handlers["get_health"] = lambda data: {
            "type": "health",
            "status": "ok",
            "life_engine_bound": self._life_engine is not None,
        }


# ── Bridge API ────────────────────────────────────────────────────

class BridgeAPI:
    """
    前端 REST API 桥接

    提供标准 HTTP API，支持前端通过 fetch/axios 调用
    """

    def __init__(self, channel: Optional[FrontendChannel] = None):
        self.channel = channel or FrontendChannel()

    async def chat(self, message: str, session_id: str = "") -> FrontendResponse:
        req = FrontendRequest(type="chat", content=message, session_id=session_id)
        data = {
            "type": "chat",
            "content": message,
            "sessionId": session_id,
        }
        result = await self.channel.handle_chat(data)
        return FrontendResponse(
            request_id=req.id,
            content=result.get("content", ""),
            trace_id=result.get("trace_id", ""),
            metadata=result.get("metadata", {}),
        )

    def health_check(self) -> Dict[str, Any]:
        engine = self.channel._life_engine
        if engine:
            return {"status": "ok", **engine.get_health()}
        return {"status": "no_engine", "life_engine_bound": False}

    async def tools_list(self) -> List[Dict[str, Any]]:
        return [{"name": "chat", "description": "Send chat message"}]

    async def skills_list(self) -> List[Dict[str, Any]]:
        return [{"name": "general", "status": "available"}]


__all__ = [
    "FrontendChannel",
    "BridgeAPI",
    "FrontendRequest",
    "FrontendResponse",
]
