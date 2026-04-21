"""
A2UI 兼容的生成式 UI 组件

遵循 Google A2UI 0.9 标准
为 AI 智能体提供标准化的 UI 生成协议
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import uuid


class UIComponentType(Enum):
    """UI 组件类型"""
    TEXT = "text"
    BUTTON = "button"
    INPUT = "input"
    LIST = "list"
    CARD = "card"
    CHART = "chart"
    TABLE = "table"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    PROGRESS = "progress"
    DIALOG = "dialog"
    NOTIFICATION = "notification"
    STREAMING_TEXT = "streaming_text"


@dataclass
class UIComponent:
    """UI 组件"""
    component_id: str
    component_type: UIComponentType
    props: Dict[str, Any]
    children: List['UIComponent'] = field(default_factory=list)
    layout: Optional[Dict] = None
    events: Optional[Dict] = None


@dataclass
class UIGeneratorConfig:
    """UI 生成器配置"""
    theme: str = "light"
    color_scheme: str = "default"
    font_family: str = "Microsoft YaHei"
    font_size_base: int = 14
    spacing_unit: int = 8
    border_radius: int = 8
    animation_enabled: bool = True


class A2UIProtocol:
    """
    A2UI 协议实现

    定义 AI 智能体与 UI 之间的标准通信协议
    """

    PROTOCOL_VERSION = "0.9"
    PROTOCOL_TYPES = [
        "component_render",
        "component_update",
        "component_remove",
        "component_event",
        "stream_start",
        "stream_chunk",
        "stream_end",
        "layout_update",
        "theme_change"
    ]

    @staticmethod
    def encode_component(component: UIComponent) -> Dict:
        """编码 UI 组件为协议格式"""
        return {
            "protocol_version": A2UIProtocol.PROTOCOL_VERSION,
            "type": "component_render",
            "payload": {
                "component_id": component.component_id,
                "component_type": component.component_type.value,
                "props": component.props,
                "children": [
                    A2UIProtocol.encode_component(child)
                    for child in component.children
                ],
                "layout": component.layout,
                "events": component.events
            },
            "timestamp": time.time()
        }

    @staticmethod
    def decode_component(data: Dict) -> Optional[UIComponent]:
        """从协议格式解码 UI 组件"""
        try:
            if data.get("type") != "component_render":
                return None

            payload = data.get("payload", {})
            children = [
                A2UIProtocol.decode_component(child)
                for child in payload.get("children", [])
                if child
            ]

            return UIComponent(
                component_id=payload.get("component_id", str(uuid.uuid4())),
                component_type=UIComponentType(payload.get("component_type", "text")),
                props=payload.get("props", {}),
                children=children,
                layout=payload.get("layout"),
                events=payload.get("events")
            )
        except:
            return None

    @staticmethod
    def create_streaming_text(
        text: str,
        speed: float = 1.0
    ) -> List[Dict]:
        """创建流式文本协议消息"""
        messages = []

        messages.append({
            "protocol_version": A2UIProtocol.PROTOCOL_VERSION,
            "type": "stream_start",
            "payload": {"text_length": len(text)},
            "timestamp": time.time()
        })

        chunk_size = max(1, int(10 * speed))
        for i in range(0, len(text), chunk_size):
            chunk = text[i:i + chunk_size]
            messages.append({
                "protocol_version": A2UIProtocol.PROTOCOL_VERSION,
                "type": "stream_chunk",
                "payload": {
                    "text": chunk,
                    "is_end": i + chunk_size >= len(text)
                },
                "timestamp": time.time()
            })

        return messages


class ComponentBuilder:
    """UI 组件构建器"""

    def __init__(self, config: Optional[UIGeneratorConfig] = None):
        self.config = config or UIGeneratorConfig()
        self._counter = 0

    def _generate_id(self) -> str:
        """生成唯一 ID"""
        self._counter += 1
        return f"comp_{self._counter}_{int(time.time() * 1000)}"

    def create_text(
        self,
        text: str,
        style: Optional[Dict] = None
    ) -> UIComponent:
        """创建文本组件"""
        return UIComponent(
            component_id=self._generate_id(),
            component_type=UIComponentType.TEXT,
            props={
                "text": text,
                "style": style or {}
            }
        )

    def create_button(
        self,
        text: str,
        on_click: str,
        style: Optional[Dict] = None,
        disabled: bool = False
    ) -> UIComponent:
        """创建按钮组件"""
        return UIComponent(
            component_id=self._generate_id(),
            component_type=UIComponentType.BUTTON,
            props={
                "text": text,
                "on_click": on_click,
                "disabled": disabled,
                "style": style or {}
            },
            events={"click": on_click}
        )

    def create_input(
        self,
        placeholder: str = "",
        on_change: Optional[str] = None,
        on_submit: Optional[str] = None,
        multiline: bool = False
    ) -> UIComponent:
        """创建输入框组件"""
        return UIComponent(
            component_id=self._generate_id(),
            component_type=UIComponentType.INPUT,
            props={
                "placeholder": placeholder,
                "multiline": multiline,
                "style": {}
            },
            events={
                "change": on_change,
                "submit": on_submit
            }
        )

    def create_list(
        self,
        items: List[Any],
        item_template: Optional[str] = None
    ) -> UIComponent:
        """创建列表组件"""
        children = []
        for item in items:
            if isinstance(item, UIComponent):
                children.append(item)
            else:
                children.append(self.create_text(str(item)))

        return UIComponent(
            component_id=self._generate_id(),
            component_type=UIComponentType.LIST,
            props={
                "items": items,
                "item_template": item_template
            },
            children=children
        )

    def create_card(
        self,
        title: str,
        content: str,
        actions: Optional[List[UIComponent]] = None,
        style: Optional[Dict] = None
    ) -> UIComponent:
        """创建卡片组件"""
        children = [
            self.create_text(title, {"font_weight": "bold", "font_size": 16}),
            self.create_text(content)
        ]

        if actions:
            children.extend(actions)

        return UIComponent(
            component_id=self._generate_id(),
            component_type=UIComponentType.CARD,
            props={
                "title": title,
                "style": style or {}
            },
            children=children
        )

    def create_progress(
        self,
        value: float,
        max_value: float = 100,
        label: Optional[str] = None,
        show_percentage: bool = True
    ) -> UIComponent:
        """创建进度条组件"""
        return UIComponent(
            component_id=self._generate_id(),
            component_type=UIComponentType.PROGRESS,
            props={
                "value": value,
                "max_value": max_value,
                "label": label,
                "show_percentage": show_percentage,
                "percentage": int((value / max_value) * 100) if max_value > 0 else 0
            }
        )

    def create_notification(
        self,
        message: str,
        notification_type: str = "info",
        duration: int = 3000
    ) -> UIComponent:
        """创建通知组件"""
        type_styles = {
            "info": {"background_color": "#e3f2fd", "border_color": "#2196f3"},
            "success": {"background_color": "#e8f5e9", "border_color": "#4caf50"},
            "warning": {"background_color": "#fff3e0", "border_color": "#ff9800"},
            "error": {"background_color": "#ffebee", "border_color": "#f44336"}
        }

        return UIComponent(
            component_id=self._generate_id(),
            component_type=UIComponentType.NOTIFICATION,
            props={
                "message": message,
                "type": notification_type,
                "duration": duration,
                "style": type_styles.get(notification_type, type_styles["info"])
            }
        )

    def create_streaming_text(
        self,
        placeholder: str = ""
    ) -> UIComponent:
        """创建流式文本组件"""
        return UIComponent(
            component_id=self._generate_id(),
            component_type=UIComponentType.STREAMING_TEXT,
            props={
                "text": "",
                "placeholder": placeholder,
                "is_streaming": False
            }
        )

    def create_dialog(
        self,
        title: str,
        content: UIComponent,
        confirm_text: str = "确定",
        cancel_text: str = "取消",
        on_confirm: Optional[str] = None,
        on_cancel: Optional[str] = None
    ) -> UIComponent:
        """创建对话框组件"""
        buttons = [
            self.create_button(cancel_text, on_cancel or "dialog.cancel()"),
            self.create_button(confirm_text, on_confirm or "dialog.confirm()")
        ]

        return UIComponent(
            component_id=self._generate_id(),
            component_type=UIComponentType.DIALOG,
            props={
                "title": title,
                "style": {
                    "backdrop_filter": "blur(4px)"
                }
            },
            children=[
                content,
                self.create_list(buttons)
            ]
        )


class A2UIComponentLibrary:
    """A2UI 组件库"""

    def __init__(self, config: Optional[UIGeneratorConfig] = None):
        self.config = config or UIGeneratorConfig()
        self.builder = ComponentBuilder(self.config)

    def render_message(
        self,
        sender: str,
        message: str,
        timestamp: Optional[float] = None
    ) -> UIComponent:
        """渲染消息"""
        time_str = time.strftime("%H:%M") if timestamp is None else time.strftime("%H:%M", time.localtime(timestamp))

        return self.builder.create_card(
            title=f"{sender} · {time_str}",
            content=message,
            style={"margin": "8px 0"}
        )

    def render_agent_status(
        self,
        name: str,
        status: str,
        avatar: Optional[str] = None
    ) -> UIComponent:
        """渲染 Agent 状态"""
        status_colors = {
            "idle": "#9e9e9e",
            "working": "#4caf50",
            "waiting": "#ff9800",
            "error": "#f44336"
        }

        return self.builder.create_card(
            title=name,
            content=f"状态: {status}",
            style={
                "border_left": f"4px solid {status_colors.get(status, '#9e9e9e')}"
            }
        )

    def render_task_progress(
        self,
        task_name: str,
        progress: float,
        sub_tasks: Optional[List[Dict]] = None
    ) -> UIComponent:
        """渲染任务进度"""
        progress_comp = self.builder.create_progress(
            value=progress,
            label=task_name
        )

        if not sub_tasks:
            return progress_comp

        sub_task_comps = []
        for task in sub_tasks:
            sub_task_comp = self.builder.create_text(
                f"{'✓' if task.get('completed') else '○'} {task.get('name', '')}"
            )
            sub_task_comps.append(sub_task_comp)

        return self.builder.create_card(
            title=task_name,
            content="",
            children=[progress_comp] + sub_task_comps
        )

    def render_streaming_response(
        self,
        text: str,
        is_complete: bool = False
    ) -> UIComponent:
        """渲染流式响应"""
        cursor = "▊" if not is_complete else ""

        return self.builder.create_streaming_text(text + cursor)

    def render_data_table(
        self,
        headers: List[str],
        rows: List[List[Any]]
    ) -> UIComponent:
        """渲染数据表格"""
        return self.builder.create_list(
            items=[headers] + rows
        )

    def render_collaboration_board(
        self,
        agents: List[Dict],
        shared_context: Dict[str, Any]
    ) -> UIComponent:
        """渲染协作面板"""
        agent_cards = []
        for agent in agents:
            card = self.render_agent_status(
                name=agent.get("name", "未知"),
                status=agent.get("status", "idle"),
                avatar=agent.get("avatar")
            )
            agent_cards.append(card)

        context_items = [f"{k}: {v}" for k, v in shared_context.items()]
        context_list = self.builder.create_list(context_items)

        return self.builder.create_card(
            title="协作面板",
            content="",
            children=[
                self.builder.create_text("参与者", {"font_weight": "bold"}),
                self.builder.create_list(agent_cards) if agent_cards else self.builder.create_text("无"),
                self.builder.create_text("共享上下文", {"font_weight": "bold"}),
                context_list
            ]
        )


class StreamRenderer:
    """流式渲染器"""

    def __init__(self, component_library: A2UIComponentLibrary):
        self.library = component_library
        self._subscribers: Dict[str, Callable] = {}
        self._active_streams: Dict[str, str] = {}

    def subscribe(self, stream_id: str, callback: Callable[[Dict], None]):
        """订阅流更新"""
        self._subscribers[stream_id] = callback

    def unsubscribe(self, stream_id: str):
        """取消订阅"""
        if stream_id in self._subscribers:
            del self._subscribers[stream_id]

    async def stream_text(
        self,
        stream_id: str,
        text: str,
        speed: float = 1.0
    ):
        """流式渲染文本"""
        self._active_streams[stream_id] = ""

        messages = A2UIProtocol.create_streaming_text(text, speed)

        for msg in messages:
            if stream_id not in self._active_streams:
                break

            if msg["type"] == "stream_chunk":
                self._active_streams[stream_id] += msg["payload"]["text"]

                if stream_id in self._subscribers:
                    component = self.library.render_streaming_response(
                        self._active_streams[stream_id],
                        msg["payload"]["is_end"]
                    )
                    self._subscribers[stream_id](A2UIProtocol.encode_component(component))

                await asyncio.sleep(0.05 / speed)

            elif msg["type"] == "stream_end":
                if stream_id in self._active_streams:
                    del self._active_streams[stream_id]

                if stream_id in self._subscribers:
                    component = self.library.render_streaming_response(
                        text, is_complete=True
                    )
                    self._subscribers[stream_id](A2UIProtocol.encode_component(component))

    def stop_stream(self, stream_id: str):
        """停止流"""
        if stream_id in self._active_streams:
            del self._active_streams[stream_id]


class A2UIRenderer:
    """A2UI 渲染器"""

    def __init__(self, config: Optional[UIGeneratorConfig] = None):
        self.config = config or UIGeneratorConfig()
        self.library = A2UIComponentLibrary(self.config)
        self.stream_renderer = StreamRenderer(self.library)

    def render_to_json(self, component: UIComponent) -> str:
        """渲染为 JSON"""
        return json.dumps(
            A2UIProtocol.encode_component(component),
            ensure_ascii=False,
            indent=2
        )

    def render_to_html(self, component: UIComponent) -> str:
        """渲染为 HTML"""
        return self._component_to_html(component)

    def _component_to_html(self, component: UIComponent) -> str:
        """将组件转换为 HTML"""
        comp_type = component.component_type
        props = component.props

        if comp_type == UIComponentType.TEXT:
            style = props.get("style", {})
            style_str = ";".join([f"{k}: {v}" for k, v in style.items()])
            return f'<div style="{style_str}">{props.get("text", "")}</div>'

        elif comp_type == UIComponentType.BUTTON:
            disabled = props.get("disabled", False)
            disabled_attr = "disabled" if disabled else ""
            return f'<button {disabled_attr} style="padding: 8px 16px; border-radius: {self.config.border_radius}px;">{props.get("text", "")}</button>'

        elif comp_type == UIComponentType.INPUT:
            multiline = props.get("multiline", False)
            placeholder = props.get("placeholder", "")
            if multiline:
                return f'<textarea placeholder="{placeholder}" style="width: 100%; min-height: 100px;"></textarea>'
            return f'<input placeholder="{placeholder}" />'

        elif comp_type == UIComponentType.CARD:
            children_html = "".join([self._component_to_html(c) for c in component.children])
            return f'<div style="border: 1px solid #ddd; border-radius: {self.config.border_radius}px; padding: 16px; margin: 8px 0;">{children_html}</div>'

        elif comp_type == UIComponentType.PROGRESS:
            percentage = props.get("percentage", 0)
            label = props.get("label", "")
            return f'<div><label>{label} {percentage}%</label><div style="width: 100%; height: 8px; background: #eee; border-radius: 4px;"><div style="width: {percentage}%; height: 100%; background: #4caf50; border-radius: 4px;"></div></div></div>'

        elif comp_type == UIComponentType.LIST:
            items_html = "".join([
                f'<li>{self._component_to_html(c) if isinstance(c, UIComponent) else str(c)}</li>'
                for c in component.children
            ])
            return f'<ul>{items_html}</ul>'

        elif comp_type == UIComponentType.NOTIFICATION:
            style = props.get("style", {})
            bg = style.get("background_color", "#e3f2fd")
            border = style.get("border_color", "#2196f3")
            return f'<div style="background: {bg}; border-left: 4px solid {border}; padding: 12px; margin: 8px 0; border-radius: {self.config.border_radius}px;">{props.get("message", "")}</div>'

        elif comp_type == UIComponentType.STREAMING_TEXT:
            text = props.get("text", "")
            return f'<div class="streaming-text" style="font-family: monospace;">{text}<span class="cursor" style="animation: blink 1s infinite;">▊</span></div>'

        return f'<div>{props.get("text", str(comp_type.value))}</div>'


_global_renderer: Optional[A2UIRenderer] = None


def get_a2ui_renderer() -> A2UIRenderer:
    """获取 A2UI 渲染器"""
    global _global_renderer
    if _global_renderer is None:
        _global_renderer = A2UIRenderer()
    return _global_renderer
