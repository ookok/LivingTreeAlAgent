"""
轻量级UI数据模型

定义组件、布局、状态等核心数据模型
from __future__ import annotations
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime


class ComponentType(Enum):
    """组件类型"""
    BUTTON = "button"
    INPUT = "input"
    SELECT = "select"
    CARD = "card"
    MODAL = "modal"
    TOAST = "toast"
    PROGRESS = "progress"
    LIST = "list"
    TABLE = "table"
    FORM = "form"
    CONTAINER = "container"
    TEXT = "text"
    IMAGE = "image"
    ICON = "icon"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SWITCH = "switch"
    SLIDER = "slider"
    TABS = "tabs"
    NAVIGATION = "navigation"


class LayoutType(Enum):
    """布局类型"""
    FLEX = "flex"
    GRID = "grid"
    STACK = "stack"
    WRAP = "wrap"
    ABSOLUTE = "absolute"
    FIXED = "fixed"


class ResponsiveBreakpoint(Enum):
    """响应式断点"""
    MOBILE = "mobile"           # < 576px
    TABLET = "tablet"           # 576px - 768px
    DESKTOP = "desktop"         # 768px - 992px
    LARGE = "large"             # 992px - 1200px
    EXTRA_LARGE = "extra_large" # > 1200px


class AnimationType(Enum):
    """动画类型"""
    FADE = "fade"
    SLIDE = "slide"
    SCALE = "scale"
    BOUNCE = "bounce"
    SPIN = "spin"
    PULSE = "pulse"
    SHAKE = "shake"


class ComponentEvent(Enum):
    """组件事件"""
    CLICK = "click"
    HOVER = "hover"
    FOCUS = "focus"
    BLUR = "blur"
    CHANGE = "change"
    INPUT = "input"
    SUBMIT = "submit"
    KEYDOWN = "keydown"
    KEYUP = "keyup"
    SCROLL = "scroll"
    RESIZE = "resize"
    LOAD = "load"
    ERROR = "error"


@dataclass
class UIState:
    """UI状态"""
    component_id: str
    props: Dict[str, Any] = field(default_factory=dict)
    children: List[str] = field(default_factory=list)
    style: Dict[str, str] = field(default_factory=dict)
    class_name: str = ""
    visible: bool = True
    disabled: bool = False
    loading: bool = False
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.component_id,
            "props": self.props,
            "children": self.children,
            "style": self.style,
            "class": self.class_name,
            "visible": self.visible,
            "disabled": self.disabled,
            "loading": self.loading,
            "error": self.error,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> UIState:
        """从字典创建"""
        return cls(
            component_id=data.get("id", ""),
            props=data.get("props", {}),
            children=data.get("children", []),
            style=data.get("style", {}),
            class_name=data.get("class", ""),
            visible=data.get("visible", True),
            disabled=data.get("disabled", False),
            loading=data.get("loading", False),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ComponentStyle:
    """组件样式"""
    width: Optional[str] = None
    height: Optional[str] = None
    min_width: Optional[str] = None
    min_height: Optional[str] = None
    max_width: Optional[str] = None
    max_height: Optional[str] = None
    margin: Optional[str] = None
    padding: Optional[str] = None
    border_radius: Optional[str] = None
    border: Optional[str] = None
    background: Optional[str] = None
    color: Optional[str] = None
    font_size: Optional[str] = None
    font_weight: Optional[str] = None
    text_align: Optional[str] = None
    display: Optional[str] = None
    flex_direction: Optional[str] = None
    flex_wrap: Optional[str] = None
    justify_content: Optional[str] = None
    align_items: Optional[str] = None
    gap: Optional[str] = None
    position: Optional[str] = None
    top: Optional[str] = None
    right: Optional[str] = None
    bottom: Optional[str] = None
    left: Optional[str] = None
    z_index: Optional[int] = None
    opacity: Optional[float] = None
    transform: Optional[str] = None
    transition: Optional[str] = None
    box_shadow: Optional[str] = None
    
    def to_dict(self) -> Dict[str, str]:
        """转换为样式字典"""
        result = {}
        for key, value in self.__dict__.items():
            if value is not None:
                # 转换驼峰为连字符
                css_key = "".join(
                    "-" + c.lower() if c.isupper() else c.lower()
                    for c in key
                )
                result[css_key] = str(value)
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> ComponentStyle:
        """从字典创建"""
        # 转换连字符为驼峰
        kwargs = {}
        for key, value in data.items():
            camel_key = "".join(
                c.upper() if i > 0 and key[i-1] == "-" else c.lower()
                for i, c in enumerate(key.replace("-", ""))
            )
            kwargs[camel_key] = value
        return cls(**kwargs)


@dataclass
class LayoutConfig:
    """布局配置"""
    layout_type: LayoutType = LayoutType.FLEX
    direction: str = "row"  # row, column
    wrap: bool = False
    justify: str = "flex-start"  # flex-start, center, flex-end, space-between, space-around
    align: str = "stretch"  # stretch, flex-start, center, flex-end, baseline
    gap: str = "0"
    grid_columns: int = 12
    grid_rows: int = 0
    grid_gap: str = "0"
    
    # 响应式配置
    breakpoints: Dict[ResponsiveBreakpoint, Dict[str, Any]] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "layout_type": self.layout_type.value,
            "direction": self.direction,
            "wrap": self.wrap,
            "justify": self.justify,
            "align": self.align,
            "gap": self.gap,
            "grid_columns": self.grid_columns,
            "grid_rows": self.grid_rows,
            "grid_gap": self.grid_gap,
            "breakpoints": {
                bp.value: config for bp, config in self.breakpoints.items()
            },
        }


@dataclass
class AnimationConfig:
    """动画配置"""
    animation_type: AnimationType = AnimationType.FADE
    duration: int = 300  # 毫秒
    easing: str = "ease"  # ease, linear, ease-in, ease-out, ease-in-out
    delay: int = 0
    iteration: int = 1  # 重复次数，-1表示无限
    direction: str = "normal"  # normal, reverse, alternate
    fill_mode: str = "none"  # none, forwards, backwards, both
    
    def to_css(self) -> str:
        """生成CSS动画"""
        return f"{self.animation_type.value} {self.duration}ms {self.easing} {self.delay}ms {self.iteration} {self.direction} {self.fill_mode}"


@dataclass
class EventHandler:
    """事件处理器"""
    event: ComponentEvent
    handler: Callable
    options: Dict[str, Any] = field(default_factory=dict)
    
    def execute(self, *args, **kwargs):
        """执行事件处理"""
        return self.handler(*args, **kwargs)


@dataclass
class ComponentMetadata:
    """组件元数据"""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: int = 1
    author: str = ""
    tags: List[str] = field(default_factory=list)
    description: str = ""
    
    def touch(self):
        """更新修改时间"""
        self.updated_at = datetime.now()
        self.version += 1


@dataclass
class ResponsiveRule:
    """响应式规则"""
    breakpoint: ResponsiveBreakpoint
    condition: Callable[[int], bool]  # 条件函数
    styles: Dict[str, str] = field(default_factory=dict)
    props: Dict[str, Any] = field(default_factory=dict)
    
    def matches(self, width: int) -> bool:
        """检查是否匹配"""
        return self.condition(width)


@dataclass
class PerformanceMetrics:
    """性能指标"""
    fps: int = 60
    memory_usage: int = 0  # bytes
    render_time: float = 0  # ms
    update_count: int = 0
    last_update: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "fps": self.fps,
            "memory_mb": round(self.memory_usage / 1024 / 1024, 2),
            "render_time_ms": round(self.render_time, 2),
            "update_count": self.update_count,
            "last_update": self.last_update.isoformat(),
        }


@dataclass
class RelayServer:
    """中继服务器配置"""
    id: str
    host: str
    port: int = 8888
    name: str = ""
    region: str = ""  # 区域：华北/华东/华南/北美/欧洲/亚洲
    is_primary: bool = False
    enabled: bool = True
    max_connections: int = 100
    current_connections: int = 0
    latency: float = 0  # 延迟ms
    bandwidth: float = 0  # 带宽Mbps
    success_rate: float = 1.0  # 成功率
    last_check: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)
    
    # 认证
    api_key: str = ""
    auth_token: str = ""
    
    # WebSocket配置
    ws_path: str = "/ws"
    ws_ping_interval: int = 30
    ws_ping_timeout: int = 10
    
    # 性能
    cpu_usage: float = 0
    memory_usage: float = 0
    uptime: float = 0  # 秒
    
    # 费用
    is_free: bool = True
    cost_per_gb: float = 0
    
    @property
    def is_healthy(self) -> bool:
        """检查服务器是否健康"""
        if not self.enabled:
            return False
        if self.success_rate < 0.5:
            return False
        if self.latency > 1000:  # 延迟超过1秒
            return False
        if self.cpu_usage > 90:  # CPU过高
            return False
        return True
    
    @property
    def quality_score(self) -> float:
        """计算质量分数 0-100"""
        score = 100
        # 延迟扣分 (延迟100ms以内满分)
        score -= min(self.latency / 10, 30)
        # 成功率扣分
        score -= (1 - self.success_rate) * 40
        # CPU扣分
        score -= min(self.cpu_usage / 5, 20)
        # 连接数扣分
        if self.current_connections >= self.max_connections * 0.9:
            score -= 10
        return max(0, min(100, score))


@dataclass
class RelayConnection:
    """中继连接信息"""
    connection_id: str
    relay_server_id: str
    connection_type: str = "websocket"  # websocket, http, tcp
    status: str = "connecting"  # connecting, connected, reconnecting, closed
    created_at: datetime = field(default_factory=datetime.now)
    connected_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    bytes_sent: int = 0
    bytes_received: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    error_count: int = 0
    reconnect_count: int = 0


@dataclass
class RelayMessage:
    """中继消息"""
    message_id: str
    from_peer: str
    to_peer: str
    content: Any
    timestamp: datetime = field(default_factory=datetime.now)
    relay_server_id: Optional[str] = None
    encrypted: bool = True
    compressed: bool = False
    priority: int = 0  # 0=低, 1=中, 2=高
    retry_count: int = 0
    max_retries: int = 3
    status: str = "pending"  # pending, sent, delivered, failed


@dataclass
class RelayPeer:
    """中继对等节点"""
    peer_id: str
    public_ip: str = ""
    public_port: int = 0
    local_ip: str = ""
    local_port: int = 0
    nat_type: str = "unknown"  # full_cone, restricted, port_restricted, symmetric
    online: bool = False
    last_seen: datetime = field(default_factory=datetime.now)
    connected_relay_id: Optional[str] = None


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    size: int = 0
    access_count: int = 0
    last_access: datetime = field(default_factory=datetime.now)
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def access(self):
        """访问缓存"""
        self.access_count += 1
        self.last_access = datetime.now()


__all__ = [
    "ComponentType",
    "LayoutType",
    "ResponsiveBreakpoint",
    "UIState",
    "ComponentEvent",
    "AnimationType",
    "UIState",
    "ComponentStyle",
    "LayoutConfig",
    "AnimationConfig",
    "EventHandler",
    "ComponentMetadata",
    "ResponsiveRule",
    "PerformanceMetrics",
    "CacheEntry",
    "RelayServer",
    "RelayConnection",
    "RelayMessage",
    "RelayPeer",
]
