"""
服务处理器基类
Base Service Handler
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class HandlerCapability(Enum):
    """处理器能力"""
    VIDEO = "video"
    AUDIO = "audio"
    SCREEN_SHARE = "screen_share"
    DATACHANNEL = "datachannel"
    EXECUTION = "execution"  # 可执行命令/脚本


@dataclass
class HandlerConfig:
    """处理器配置"""
    max_concurrent: int = 1
    session_timeout_seconds: int = 3600
    heartbeat_interval_seconds: int = 10
    heartbeat_timeout_seconds: int = 30

    # 能力
    capabilities: list = None

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []


class BaseServiceHandler(ABC):
    """
    服务处理器抽象基类

    所有服务类型(远程直播/AI计算/远程协助/知识咨询)
    都需实现此接口
    """

    def __init__(self, config: Optional[HandlerConfig] = None):
        self.config = config or HandlerConfig()
        self._sessions: Dict[str, Any] = {}
        self._active = False

    @property
    @abstractmethod
    def service_type(self) -> str:
        """服务类型标识"""
        pass

    @property
    def capabilities(self) -> list:
        """支持的能力列表"""
        return self.config.capabilities

    async def start(self) -> None:
        """启动处理器"""
        self._active = True
        logger.info(f"[{self.service_type}] Handler started")

    async def stop(self) -> None:
        """停止处理器"""
        self._active = False
        # 清理所有会话
        for session_id in list(self._sessions.keys()):
            await self.end_session(session_id)
        logger.info(f"[{self.service_type}] Handler stopped")

    @abstractmethod
    async def create_session(self, listing_id: str, seller_id: str, buyer_id: str, **kwargs) -> str:
        """
        创建服务会话

        Returns:
            session_id: 会话ID
        """
        pass

    @abstractmethod
    async def join_session(self, session_id: str, user_id: str, **kwargs) -> Dict[str, Any]:
        """
        用户加入会话

        Returns:
            包含room_id, ice_config等连接信息
        """
        pass

    @abstractmethod
    async def end_session(self, session_id: str) -> None:
        """结束会话"""
        pass

    @abstractmethod
    async def handle_heartbeat(self, session_id: str, user_id: str) -> bool:
        """
        处理心跳

        Returns:
            是否存活
        """
        pass

    async def on_session_data(self, session_id: str, user_id: str, data: bytes) -> Optional[bytes]:
        """
        处理DataChannel数据 (可选实现)

        默认返回None表示不处理
        """
        return None

    def get_active_sessions(self) -> list:
        """获取活跃会话列表"""
        return list(self._sessions.keys())


class ServiceHandlerRegistry:
    """
    服务处理器注册表

    管理所有服务类型的处理器实例
    """

    _instance = None
    _handlers: Dict[str, BaseServiceHandler] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> "ServiceHandlerRegistry":
        return cls()

    def register(self, handler_type: str, handler: BaseServiceHandler) -> None:
        """注册处理器"""
        self._handlers[handler_type] = handler
        logger.info(f"Registered handler: {handler_type}")

    def get(self, handler_type: str) -> Optional[BaseServiceHandler]:
        """获取处理器"""
        return self._handlers.get(handler_type)

    def get_all_types(self) -> list:
        """获取所有已注册的处理类型"""
        return list(self._handlers.keys())

    async def start_all(self) -> None:
        """启动所有处理器"""
        for handler in self._handlers.values():
            await handler.start()

    async def stop_all(self) -> None:
        """停止所有处理器"""
        for handler in self._handlers.values():
            await handler.stop()


# 全局注册表实例
_registry = ServiceHandlerRegistry.get_instance()


def get_handler_registry() -> ServiceHandlerRegistry:
    return _registry


def register_service_handler(handler_type: str, handler: BaseServiceHandler) -> None:
    """快捷注册函数"""
    _registry.register(handler_type, handler)