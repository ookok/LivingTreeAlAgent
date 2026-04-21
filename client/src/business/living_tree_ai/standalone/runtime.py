"""
单机运行时核心 (Standalone Runtime Core)
======================================

管理运行时模式：standalone（单机）| distributed（分布式）

关键设计：
- 单机模式不是另一个 App，而是同一套代码的"运行时状态"
- 中心节点只是"网络加速器"，而非"系统启动器"
"""

import asyncio
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

# 全局运行时实例
_global_runtime: Optional["StandaloneRuntime"] = None
_runtime_lock = threading.Lock()


class RuntimeMode(Enum):
    """运行时模式"""
    STANDALONE = "standalone"     # 单机模式（默认）
    DISTRIBUTED = "distributed"   # 分布式模式


@dataclass
class RuntimeConfig:
    """运行时配置"""
    mode: RuntimeMode = RuntimeMode.STANDALONE
    data_dir: Path = field(default_factory=lambda: Path.home() / ".hermes-desktop" / "standalone")
    model_path: Optional[Path] = None
    enable_local_ai: bool = True
    enable_local_mail: bool = True
    enable_local_storage: bool = True
    # 分布式模式配置
    central_node_url: Optional[str] = None
    relay_servers: list[str] = field(default_factory=list)


class StandaloneRuntime:
    """
    单机运行时

    核心职责：
    1. 管理运行时模式（单机/分布式）
    2. 自举（Bootstrap）检查
    3. 组件生命周期管理
    4. 模式切换
    """

    def __init__(self, config: Optional[RuntimeConfig] = None):
        self.config = config or RuntimeConfig()
        self._mode = self.config.mode

        # 组件
        self._local_identity = None
        self._local_mailbox = None
        self._local_ai = None
        self._local_storage = None
        self._event_bus = None

        # 状态
        self._initialized = False
        self._startup_time: Optional[datetime] = None
        self._bootstrap_errors: list[str] = []

        # 锁
        self._lock = threading.RLock()

    @property
    def mode(self) -> RuntimeMode:
        """当前模式"""
        return self._mode

    @property
    def is_standalone(self) -> bool:
        """是否单机模式"""
        return self._mode == RuntimeMode.STANDALONE

    @property
    def is_distributed(self) -> bool:
        """是否分布式模式"""
        return self._mode == RuntimeMode.DISTRIBUTED

    async def bootstrap(self) -> bool:
        """
        自举（Bootstrap）

        启动流程：
        1. 环境自检：检测端口占用
        2. 密钥自举：检查/生成 identity.json
        3. 模型预热：加载本地 AI 模型
        """
        with self._lock:
            if self._initialized:
                return True

        self._startup_time = datetime.now()
        self._bootstrap_errors = []

        try:
            # 1. 确保数据目录存在
            self.config.data_dir.mkdir(parents=True, exist_ok=True)

            # 2. 初始化事件总线
            self._event_bus = create_event_bus()

            # 3. 初始化本地身份
            self._local_identity = create_local_identity(self.config.data_dir)
            identity_ok = await self._local_identity.bootstrap()
            if not identity_ok:
                self._bootstrap_errors.append("Local identity bootstrap failed")

            # 4. 初始化本地存储
            if self.config.enable_local_storage:
                self._local_storage = create_local_storage(self.config.data_dir)
                await self._local_storage.init()

            # 5. 初始化本地邮件
            if self.config.enable_local_mail:
                from .local_mailbox import create_local_mailbox
                self._local_mailbox = create_local_mailbox(
                    self.config.data_dir,
                    self._event_bus
                )
                await self._local_mailbox.init()

            # 6. 初始化本地 AI
            if self.config.enable_local_ai:
                from .local_ai import create_local_ai_engine
                self._local_ai = create_local_ai_engine(
                    model_path=self.config.model_path,
                    event_bus=self._event_bus
                )
                await self._local_ai.init()

            # 广播启动事件
            self._event_bus.publish(Event(
                type="runtime.bootstrapped",
                source="standalone_runtime",
                data={"mode": self._mode.value}
            ))

            self._initialized = True
            return True

        except Exception as e:
            self._bootstrap_errors.append(str(e))
            return False

    async def shutdown(self):
        """关闭运行时"""
        with self._lock:
            if not self._initialized:
                return

            # 关闭各组件
            if self._local_ai:
                await self._local_ai.shutdown()

            if self._local_mailbox:
                await self._local_mailbox.shutdown()

            if self._local_storage:
                await self._local_storage.shutdown()

            self._event_bus.publish(Event(
                type="runtime.shutdown",
                source="standalone_runtime",
                data={}
            ))

            self._initialized = False

    def switch_mode(self, new_mode: RuntimeMode):
        """
        切换运行时模式

        注意：这是一个同步操作，实际的切换可能需要重启组件
        """
        if self._mode == new_mode:
            return

        old_mode = self._mode
        self._mode = new_mode

        # 发布模式切换事件
        if self._event_bus:
            self._event_bus.publish(Event(
                type="runtime.mode_changed",
                source="standalone_runtime",
                data={"old_mode": old_mode.value, "new_mode": new_mode.value}
            ))

    def get_component(self, name: str) -> Any:
        """
        获取组件

        Args:
            name: 组件名 (identity/mailbox/ai/storage/event_bus)
        """
        components = {
            "identity": self._local_identity,
            "mailbox": self._local_mailbox,
            "ai": self._local_ai,
            "storage": self._local_storage,
            "event_bus": self._event_bus,
        }
        return components.get(name)

    def get_status(self) -> dict[str, Any]:
        """获取运行时状态"""
        return {
            "mode": self._mode.value,
            "initialized": self._initialized,
            "uptime_seconds": (datetime.now() - self._startup_time).total_seconds() if self._startup_time else 0,
            "bootstrap_errors": self._bootstrap_errors,
            "components": {
                "identity": self._local_identity is not None,
                "mailbox": self._local_mailbox is not None,
                "ai": self._local_ai is not None,
                "storage": self._local_storage is not None,
            }
        }

    # ========== 邮件发送（根据模式选择路径）==========

    async def send_mail(self, to: str, subject: str, content: str, attachments: Optional[list[str]] = None) -> dict[str, Any]:
        """
        发送邮件（自动根据模式选择路径）

        - 单机模式：写入本地数据库
        - 分布式模式：走 WebSocket 发送
        """
        if self.is_standalone:
            # 单机模式：本地事件总线
            if self._local_mailbox:
                return await self._local_mailbox.send_local(
                    to=to,
                    subject=subject,
                    content=content,
                    attachments=attachments
                )
            return {"success": False, "error": "Local mailbox not available"}
        else:
            # 分布式模式：通过中继发送
            # 实际实现中，这里会调用 distributed_ai 模块
            return {"success": False, "error": "Distributed mode not implemented"}

    # ========== AI 推理（根据模式选择模型）==========

    async def think(self, prompt: str, context: Optional[dict[str, Any]] = None) -> str:
        """
        AI 推理（自动根据模式选择模型）

        - 单机模式：使用本地 TinyLLM
        - 分布式模式：使用中心节点或海外集群
        """
        if self._local_ai and self.is_standalone:
            return await self._local_ai.think(prompt, context)
        elif self.is_distributed:
            # TODO: 调用分布式 AI
            return await self._local_ai.think(prompt, context) if self._local_ai else "AI not available"
        return "Runtime not initialized"

    def get_runtime_info(self) -> dict[str, Any]:
        """获取运行时信息"""
        return {
            "mode": self._mode.value,
            "mode_display": "单机模式" if self.is_standalone else "分布式模式",
            "capabilities": self._get_capabilities(),
            "limits": self._get_limits(),
        }

    def _get_capabilities(self) -> dict[str, bool]:
        """获取当前模式支持的能力"""
        base = {
            "local_identity": True,
            "local_storage": True,
            "local_mail": True,
        }

        if self.is_standalone:
            base.update({
                "full_ai": False,
                "local_ai": self._local_ai is not None,
                "network_recommendations": False,
                "overseas_search": False,
            })
        else:
            base.update({
                "full_ai": True,
                "local_ai": self._local_ai is not None,
                "network_recommendations": True,
                "overseas_search": True,
            })

        return base

    def _get_limits(self) -> dict[str, Any]:
        """获取当前模式的限制"""
        if self.is_standalone:
            return {
                "ai_model": "TinyLLM (3B-7B)",
                "recommendations": "Local only",
                "external_network": False,
                "sync_required": False,
            }
        else:
            return {
                "ai_model": "Full capability",
                "recommendations": "Network enhanced",
                "external_network": True,
                "sync_required": True,
            }


def create_runtime(config: Optional[RuntimeConfig] = None) -> StandaloneRuntime:
    """创建运行时实例"""
    global _global_runtime

    with _runtime_lock:
        if _global_runtime is None:
            _global_runtime = StandaloneRuntime(config)
        return _global_runtime


def get_runtime() -> Optional[StandaloneRuntime]:
    """获取全局运行时实例"""
    return _global_runtime