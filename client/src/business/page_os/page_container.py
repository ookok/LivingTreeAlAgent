# =================================================================
# PageOS - PageContainer: 页面容器（进程抽象）
# =================================================================
# 每个页面是一个独立的"进程"，拥有自己的状态、能力和生命周期
# =================================================================

import uuid
import time
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
import asyncio


class PageState(Enum):
    """页面状态"""
    CREATING = "creating"           # 创建中
    LOADING = "loading"             # 加载中
    ACTIVE = "active"               # 活跃
    IDLE = "idle"                   # 空闲（用户离开）
    SUSPENDED = "suspended"         # 挂起（可见但无交互）
    CLOSED = "closed"               # 已关闭


class PageCapability(Enum):
    """页面能力"""
    DOM_READ = "dom:read"           # 读取 DOM
    DOM_WRITE = "dom:write"         # 修改 DOM
    OVERLAY = "overlay"             # 叠加层
    WORKFLOW = "workflow"           # 工作流参与
    STATE_SYNC = "state:sync"       # 状态同步
    SCRIPT_INJECT = "script:inject" # 脚本注入


@dataclass
class PageInfo:
    """页面信息"""
    page_id: str
    url: str
    title: str = ""
    favicon: str = ""
    domain: str = ""
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    state: PageState = PageState.CREATING

    # 能力列表
    capabilities: List[PageCapability] = field(default_factory=list)

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 标签（用于分组）
    tags: List[str] = field(default_factory=list)

    def update_activity(self):
        """更新最后活跃时间"""
        self.last_active = time.time()


class PageContainer:
    """
    页面容器 - 每个标签页的核心抽象

    设计理念：
    - 类似操作系统的进程，每个页面有独立 ID、状态、能力
    - 页面之间可通信（通过 MessageBus）
    - 页面生命周期由 PageOS Kernel 管理
    """

    _instances: Dict[str, 'PageContainer'] = {}
    _message_bus: List[Dict[str, Any]] = []

    def __init__(
        self,
        page_id: str = None,
        url: str = "",
        title: str = "",
        tab_id: int = None
    ):
        self.page_id = page_id or str(uuid.uuid4())[:12]
        self.url = url
        self.title = title
        self.tab_id = tab_id

        self.info = PageInfo(
            page_id=self.page_id,
            url=url,
            title=title
        )

        # 状态
        self._state = PageState.CREATING
        self._listeners: Dict[str, List[Callable]] = {}
        self._child_messages: List[Dict[str, Any]] = []

        # 注册到全局实例表
        PageContainer._instances[self.page_id] = self

    @property
    def state(self) -> PageState:
        return self._state

    @state.setter
    def state(self, value: PageState):
        old_state = self._state
        self._state = value
        self.info.state = value
        self._emit("state_changed", {"old": old_state, "new": value})

    # ========== 生命周期 ==========

    def create(self) -> 'PageContainer':
        """创建页面"""
        self.state = PageState.LOADING
        self._emit("created", {"page_id": self.page_id})
        return self

    def load(self, url: str = None) -> 'PageContainer':
        """加载页面"""
        if url:
            self.url = url
            self.info.url = url
            self.info.domain = self._extract_domain(url)

        self.state = PageState.LOADING
        self._emit("loading", {"url": self.url})
        return self

    def activate(self) -> 'PageContainer':
        """激活页面"""
        self.state = PageState.ACTIVE
        self.info.update_activity()
        self._emit("activated", {"page_id": self.page_id})
        return self

    def idle(self) -> 'PageContainer':
        """页面空闲"""
        self.state = PageState.IDLE
        self._emit("idle", {"page_id": self.page_id})
        return self

    def suspend(self) -> 'PageContainer':
        """挂起页面"""
        self.state = PageState.SUSPENDED
        self._emit("suspended", {"page_id": self.page_id})
        return self

    def close(self) -> 'PageContainer':
        """关闭页面"""
        self.state = PageState.CLOSED
        self._emit("closed", {"page_id": self.page_id})

        # 从全局实例表移除
        if self.page_id in PageContainer._instances:
            del PageContainer._instances[self.page_id]

        return self

    # ========== 事件监听 ==========

    def on(self, event: str, callback: Callable):
        """监听事件"""
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(callback)

    def off(self, event: str, callback: Callable = None):
        """取消监听"""
        if callback is None:
            self._listeners[event] = []
        elif event in self._listeners:
            self._listeners[event] = [cb for cb in self._listeners[event] if cb != callback]

    def _emit(self, event: str, data: Dict[str, Any]):
        """触发事件"""
        self.info.update_activity()
        if event in self._listeners:
            for callback in self._listeners[event]:
                try:
                    callback(data)
                except Exception as e:
                    print(f"[PageContainer] Event handler error: {e}")

    # ========== 进程间通信 ==========

    def send_to(self, target_page_id: str, message: Dict[str, Any]) -> bool:
        """
        向其他页面发送消息

        Args:
            target_page_id: 目标页面 ID
            message: 消息内容

        Returns:
            是否发送成功
        """
        msg = {
            "from": self.page_id,
            "to": target_page_id,
            "type": message.get("type", "generic"),
            "payload": message,
            "timestamp": time.time()
        }

        PageContainer._message_bus.append(msg)

        # 如果目标页面存在，直接传递
        target = PageContainer._instances.get(target_page_id)
        if target:
            target._receive_message(msg)

        return True

    def broadcast(self, message: Dict[str, Any], exclude_self: bool = True) -> int:
        """
        广播消息给所有页面

        Returns:
            发送成功的页面数量
        """
        msg = {
            "from": self.page_id,
            "type": message.get("type", "broadcast"),
            "payload": message,
            "timestamp": time.time()
        }

        count = 0
        for page_id, container in PageContainer._instances.items():
            if exclude_self and page_id == self.page_id:
                continue
            full_msg = {**msg, "to": page_id}
            PageContainer._message_bus.append(full_msg)
            container._receive_message(full_msg)
            count += 1

        return count

    def _receive_message(self, message: Dict[str, Any]):
        """接收消息"""
        self._child_messages.append(message)
        self._emit("message", message)

    def get_messages(self, clear: bool = False) -> List[Dict[str, Any]]:
        """获取收到的消息"""
        messages = self._child_messages.copy()
        if clear:
            self._child_messages.clear()
        return messages

    # ========== 能力管理 ==========

    def has_capability(self, cap: PageCapability) -> bool:
        """检查是否有某能力"""
        return cap in self.info.capabilities

    def add_capability(self, cap: PageCapability):
        """添加能力"""
        if cap not in self.info.capabilities:
            self.info.capabilities.append(cap)
            self._emit("capability_added", {"capability": cap})

    def remove_capability(self, cap: PageCapability):
        """移除能力"""
        if cap in self.info.capabilities:
            self.info.capabilities.remove(cap)
            self._emit("capability_removed", {"capability": cap})

    # ========== 标签管理 ==========

    def add_tag(self, tag: str):
        """添加标签"""
        if tag not in self.info.tags:
            self.info.tags.append(tag)

    def remove_tag(self, tag: str):
        """移除标签"""
        if tag in self.info.tags:
            self.info.tags.remove(tag)

    def has_tag(self, tag: str) -> bool:
        """检查是否有标签"""
        return tag in self.info.tags

    # ========== 工具方法 ==========

    def _extract_domain(self, url: str) -> str:
        """提取域名"""
        if not url:
            return ""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except Exception:
            return ""

    @classmethod
    def get_all_pages(cls) -> Dict[str, 'PageContainer']:
        """获取所有页面实例"""
        return cls._instances.copy()

    @classmethod
    def get_page(cls, page_id: str) -> Optional['PageContainer']:
        """获取指定页面"""
        return cls._instances.get(page_id)

    @classmethod
    def get_pages_by_tag(cls, tag: str) -> List['PageContainer']:
        """按标签获取页面"""
        return [p for p in cls._instances.values() if p.has_tag(tag)]

    @classmethod
    def get_pages_by_domain(cls, domain: str) -> List['PageContainer']:
        """按域名获取页面"""
        return [p for p in cls._instances.values() if p.info.domain == domain]

    @classmethod
    def get_active_pages(cls) -> List['PageContainer']:
        """获取活跃页面"""
        return [p for p in cls._instances.values() if p.state == PageState.ACTIVE]

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "page_id": self.page_id,
            "url": self.url,
            "title": self.title,
            "tab_id": self.tab_id,
            "state": self.state.value,
            "info": {
                "domain": self.info.domain,
                "capabilities": [c.value for c in self.info.capabilities],
                "tags": self.info.tags,
                "created_at": self.info.created_at,
                "last_active": self.info.last_active,
            }
        }

    def __repr__(self):
        return f"<PageContainer {self.page_id} [{self.state.value}] {self.url[:40]}>"
