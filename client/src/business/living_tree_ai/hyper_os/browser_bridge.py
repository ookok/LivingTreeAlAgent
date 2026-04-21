"""
浏览器桥接服务 (BrowserBridge)
==============================

核心思想：通过WebSocket实现Python与浏览器JS的双向实时通信

┌─────────────┐     WebSocket      ┌─────────────┐
│  Python AI  │◄────────────────►│  Browser JS │
│   Engine    │   ws://localhost  │   Client    │
└─────────────┘      8765          └─────────────┘

功能：
1. 页面分析：JS发送页面内容，Python AI分析
2. 命令执行：Python发送命令，JS在浏览器执行
3. 数据同步：表单数据、页面状态实时同步
4. 绘图指令：Python生成SVG，JS渲染到Canvas
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class MessageType(Enum):
    """消息类型"""
    # 浏览器 -> Python
    PAGE_CONTENT = "page_content"          # 页面内容
    FORM_DATA = "form_data"                # 表单数据
    ELEMENT_CLICK = "element_click"        # 元素点击
    SELECTION_CHANGE = "selection_change"  # 选择变化
    JAVASCRIPT_ERROR = "js_error"         # JS错误

    # Python -> 浏览器
    ANALYZE_RESULT = "analyze_result"     # 分析结果
    AUTOFILL = "autofill"                 # 自动填表
    DRAW_COMMAND = "draw_command"          # 绘图命令
    HIGHLIGHT = "highlight"               # 高亮元素
    NOTIFICATION = "notification"          # 通知
    WORKFLOW_STEP = "workflow_step"       # 工作流步骤


@dataclass
class BrowserMessage:
    """浏览器消息"""
    type: MessageType
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: Optional[str] = None

    @classmethod
    def from_json(cls, json_str: str) -> "BrowserMessage":
        """从JSON创建"""
        data = json.loads(json_str)
        msg_type = MessageType(data.get("type", "notification"))
        return cls(
            type=msg_type,
            payload=data.get("payload", {}),
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
            session_id=data.get("session_id")
        )

    def to_json(self) -> str:
        """转为JSON"""
        return json.dumps({
            "type": self.type.value,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id
        })


@dataclass
class Session:
    """浏览器会话"""
    session_id: str
    tab_id: str
    url: str
    title: str
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)  # 会话上下文


class BrowserBridge:
    """
    浏览器桥接服务

    核心能力：
    1. WebSocket服务器，管理多个浏览器会话
    2. 消息路由：将浏览器消息分发给Python处理器
    3. 命令发送：向浏览器发送绘图、填表等命令
    4. 状态同步：维护浏览器状态
    """

    def __init__(self, port: int = 8765):
        self.port = port
        self.server = None
        self.is_running = False

        # 连接的客户端
        self.clients: Dict[str, asyncio.WebSocketServerProtocol] = {}

        # 会话管理
        self.sessions: Dict[str, Session] = {}

        # 消息处理器
        self.handlers: Dict[MessageType, Callable] = {}

        # WebSocket回调
        self.ws_handler: Optional[Callable] = None

        # 默认处理器
        self._register_default_handlers()

    def _register_default_handlers(self):
        """注册默认消息处理器"""

        async def handle_page_content(msg: BrowserMessage):
            """处理页面内容"""
            content = msg.payload.get("html", "")
            url = msg.payload.get("url", "")

            # 分析页面结构
            analysis = {
                "has_form": "<form" in content.lower(),
                "form_fields": self._extract_form_fields(content),
                "tables_count": content.lower().count("<table"),
                "links": self._extract_links(content),
                "title": msg.payload.get("title", ""),
            }

            return {
                "type": "page_analysis",
                "result": analysis,
                "suggestions": self._generate_suggestions(analysis)
            }

        async def handle_form_data(msg: BrowserMessage):
            """处理表单数据"""
            form_data = msg.payload.get("form_data", {})
            url = msg.payload.get("url", "")

            # 返回自动填充建议
            return {
                "type": "autofill_suggestion",
                "data": form_data
            }

        self.handlers[MessageType.PAGE_CONTENT] = handle_page_content
        self.handlers[MessageType.FORM_DATA] = handle_form_data

    def register_handler(self, msg_type: MessageType, handler: Callable):
        """注册消息处理器"""
        self.handlers[msg_type] = handler

    async def start(self):
        """启动WebSocket服务器"""
        import websockets

        async def handler(websocket, path):
            client_id = str(id(websocket))
            self.clients[client_id] = websocket

            # 创建会话
            session = Session(
                session_id=client_id,
                tab_id=client_id,
                url="",
                title=""
            )
            self.sessions[client_id] = session

            print(f"Browser connected: {client_id}")

            try:
                async for message in websocket:
                    await self._handle_message(client_id, message)
            except Exception as e:
                print(f"WebSocket error: {e}")
            finally:
                # 清理会话
                if client_id in self.clients:
                    del self.clients[client_id]
                if client_id in self.sessions:
                    del self.sessions[client_id]
                print(f"Browser disconnected: {client_id}")

        self.server = await websockets.serve(handler, '127.0.0.1', self.port)
        self.is_running = True
        print(f"HyperOS BrowserBridge running on ws://127.0.0.1:{self.port}")

    async def stop(self):
        """停止WebSocket服务器"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.is_running = False

    async def _handle_message(self, client_id: str, message: str):
        """处理收到的消息"""
        try:
            msg = BrowserMessage.from_json(message)

            # 更新会话
            if client_id in self.sessions:
                session = self.sessions[client_id]
                session.last_active = datetime.now()
                if "url" in msg.payload:
                    session.url = msg.payload["url"]
                if "title" in msg.payload:
                    session.title = msg.payload["title"]

            # 调用处理器
            if msg.type in self.handlers:
                result = await self.handlers[msg.type](msg)

                # 发送响应
                if result and client_id in self.clients:
                    response = BrowserMessage(
                        type=MessageType(result.get("type", "notification")),
                        payload=result,
                        session_id=client_id
                    )
                    await self.clients[client_id].send(response.to_json())
            else:
                # 默认响应
                if client_id in self.clients:
                    response = BrowserMessage(
                        type=MessageType.NOTIFICATION,
                        payload={"message": "Message received", "original_type": msg.type.value}
                    )
                    await self.clients[client_id].send(response.to_json())

        except Exception as e:
            print(f"Error handling message: {e}")

    # ============ 发送命令到浏览器 ============

    async def send_autofill(
        self,
        session_id: str,
        fields: List[Dict[str, str]]
    ):
        """发送自动填表命令"""
        if session_id not in self.clients:
            return

        msg = BrowserMessage(
            type=MessageType.AUTOFILL,
            payload={"fields": fields}
        )
        await self.clients[session_id].send(msg.to_json())

    async def send_draw_command(
        self,
        session_id: str,
        shape: str,
        coords: List[Dict[str, float]],
        style: Optional[Dict] = None
    ):
        """发送绘图命令"""
        if session_id not in self.clients:
            return

        msg = BrowserMessage(
            type=MessageType.DRAW_COMMAND,
            payload={
                "shape": shape,
                "coords": coords,
                "style": style or {}
            }
        )
        await self.clients[session_id].send(msg.to_json())

    async def send_highlight(
        self,
        session_id: str,
        selector: str,
        color: str = "#ff0000"
    ):
        """发送高亮命令"""
        if session_id not in self.clients:
            return

        msg = BrowserMessage(
            type=MessageType.HIGHLIGHT,
            payload={"selector": selector, "color": color}
        )
        await self.clients[session_id].send(msg.to_json())

    async def send_notification(
        self,
        session_id: str,
        title: str,
        message: str,
        level: str = "info"
    ):
        """发送通知"""
        if session_id not in self.clients:
            return

        msg = BrowserMessage(
            type=MessageType.NOTIFICATION,
            payload={
                "title": title,
                "message": message,
                "level": level
            }
        )
        await self.clients[session_id].send(msg.to_json())

    async def send_workflow_step(
        self,
        session_id: str,
        step: int,
        total: int,
        description: str
    ):
        """发送工作流步骤"""
        if session_id not in self.clients:
            return

        msg = BrowserMessage(
            type=MessageType.WORKFLOW_STEP,
            payload={
                "step": step,
                "total": total,
                "description": description,
                "progress": int(step / total * 100)
            }
        )
        await self.clients[session_id].send(msg.to_json())

    # ============ 辅助方法 ============

    def _extract_form_fields(self, html: str) -> List[Dict]:
        """提取表单字段"""
        fields = []
        # 简单的正则提取
        import re
        inputs = re.findall(r'<input[^>]+name="([^"]+)"[^>]*>', html)
        for name in inputs:
            fields.append({"name": name, "type": "input"})
        textareas = re.findall(r'<textarea[^>]+name="([^"]+)"', html)
        for name in textareas:
            fields.append({"name": name, "type": "textarea"})
        selects = re.findall(r'<select[^>]+name="([^"]+)"', html)
        for name in selects:
            fields.append({"name": name, "type": "select"})
        return fields

    def _extract_links(self, html: str) -> List[str]:
        """提取链接"""
        import re
        links = re.findall(r'<a[^>]+href="([^"]+)"', html)
        return links[:20]  # 只返回前20个

    def _generate_suggestions(self, analysis: Dict) -> List[str]:
        """生成建议"""
        suggestions = []

        if analysis.get("has_form"):
            suggestions.append("检测到表单，可使用自动填表功能")

        if analysis.get("tables_count", 0) > 5:
            suggestions.append("页面包含多个表格，建议提取结构化数据")

        return suggestions

    def get_active_sessions(self) -> List[Session]:
        """获取活跃会话"""
        return list(self.sessions.values())


# 全局实例
_bridge_instance: Optional[BrowserBridge] = None


def get_browser_bridge(port: int = 8765) -> BrowserBridge:
    """获取浏览器桥接全局实例"""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = BrowserBridge(port)
    return _bridge_instance