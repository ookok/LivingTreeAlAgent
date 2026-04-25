# -*- coding: utf-8 -*-
"""
统一上下文管理器 - Unified Context Manager
============================================

统一管理会话上下文、历史记录、用户偏好等。

复用模块：
- MemoryManager (core/memory_manager.py)
- SessionDB (core/session_db.py)
- ConversationalClarifier (core/conversational_clarifier.py)

Author: Hermes Desktop Team
"""

from core.logger import get_logger
logger = get_logger('unified_context')

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── 数据结构 ────────────────────────────────────────────────────────────────


@dataclass
class ContextEntry:
    """上下文条目"""
    role: str = ""           # user / assistant / system
    content: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content[:100] + "..." if len(self.content) > 100 else self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }


@dataclass
class UnifiedContext:
    """
    统一上下文

    Attributes:
        session_id: 会话 ID
        user_id: 用户 ID
        history: 对话历史
        memory: 长期记忆
        user_profile: 用户画像
        variables: 临时变量
        metadata: 元数据
    """
    session_id: str = ""
    user_id: str = ""
    history: List[ContextEntry] = field(default_factory=list)
    memory: str = ""           # 长期记忆文本
    user_profile: str = ""    # 用户画像文本
    variables: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str, **metadata):
        """添加消息到历史"""
        entry = ContextEntry(
            role=role,
            content=content,
            metadata=metadata
        )
        self.history.append(entry)

    def get_recent_history(self, count: int = 10) -> List[ContextEntry]:
        """获取最近的 N 条历史"""
        return self.history[-count:] if len(self.history) > count else self.history

    def set_var(self, key: str, value: Any):
        """设置临时变量"""
        self.variables[key] = value

    def get_var(self, key: str, default: Any = None) -> Any:
        """获取临时变量"""
        return self.variables.get(key, default)

    def build_prompt_context(self, system_prompt: str = "") -> str:
        """
        构建完整的提示词上下文

        Args:
            system_prompt: 系统提示词

        Returns:
            str: 完整的上下文文本
        """
        parts = []

        # 系统提示词
        if system_prompt:
            parts.append(f"## 系统提示\n{system_prompt}")

        # 用户画像
        if self.user_profile:
            parts.append(f"## 用户画像\n{self.user_profile}")

        # 长期记忆
        if self.memory:
            parts.append(f"## 长期记忆\n{self.memory}")

        # 临时变量
        if self.variables:
            vars_text = "\n".join(f"- {k}: {v}" for k, v in self.variables.items())
            parts.append(f"## 当前上下文\n{vars_text}")

        # 对话历史（最近 10 条）
        if self.history:
            recent = self.get_recent_history(10)
            history_text = "\n".join(
                f"{'用户' if e.role == 'user' else '助手'}: {e.content}"
                for e in recent
            )
            parts.append(f"## 对话历史\n{history_text}")

        return "\n\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "history_count": len(self.history),
            "has_memory": bool(self.memory),
            "has_user_profile": bool(self.user_profile),
            "variables_count": len(self.variables),
        }


# ── 上下文提供者 ────────────────────────────────────────────────────────────


class UnifiedContextProvider:
    """
    统一上下文提供者

    从多个来源聚合上下文：
    1. SessionDB - 会话历史
    2. MemoryManager - 长期记忆
    3. 用户配置 - 用户偏好

    使用示例：
    ```python
    provider = UnifiedContextProvider(session_id="sess_001", user_id="user_001")
    context = provider.get_context()

    # 构建提示词
    prompt_context = context.build_prompt_context(
        system_prompt="你是一个有帮助的助手"
    )
    ```
    """

    def __init__(
        self,
        session_id: str = "",
        user_id: str = "",
        history_limit: int = 20,
        memory_limit: int = 5000,
        **kwargs
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.history_limit = history_limit
        self.memory_limit = memory_limit

        # 组件延迟初始化
        self._session_db = None
        self._memory_manager = None
        self._memory_palace = None

        logger.info(f"UnifiedContextProvider 初始化 (session_id={session_id}, user_id={user_id})")

    # ── 属性懒加载 ──────────────────────────────────────────────────────────

    @property
    def session_db(self):
        """会话数据库"""
        if self._session_db is None:
            try:
                from core.session_db import SessionDB
                self._session_db = SessionDB()
            except ImportError:
                logger.warning("SessionDB 不可用")
                self._session_db = None
        return self._session_db

    @property
    def memory_manager(self):
        """记忆管理器"""
        if self._memory_manager is None:
            try:
                from core.memory_manager import MemoryManager
                self._memory_manager = MemoryManager()
            except ImportError:
                logger.warning("MemoryManager 不可用")
                self._memory_manager = None
        return self._memory_manager

    @property
    def memory_palace(self):
        """记忆宫殿"""
        if self._memory_palace is None:
            try:
                from core.memory_palace import MemoryPalace

                self._memory_palace = MemoryPalace()
            except ImportError:
                logger.warning("MemoryPalace 不可用")
                self._memory_palace = None
        return self._memory_palace

    # ── 核心接口 ────────────────────────────────────────────────────────────

    def get_context(self) -> UnifiedContext:
        """
        获取完整的统一上下文

        Returns:
            UnifiedContext: 包含所有来源的上下文
        """
        context = UnifiedContext(
            session_id=self.session_id,
            user_id=self.user_id,
        )

        # 获取会话历史
        if self.session_db and self.session_id:
            history = self._load_session_history()
            for msg in history:
                context.history.append(ContextEntry(
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                    timestamp=msg.get("timestamp", time.time()),
                    metadata=msg.get("metadata", {})
                ))

        # 获取长期记忆
        if self.memory_manager:
            context.memory = self.memory_manager.get_memory()
            context.user_profile = self.memory_manager.get_user_profile()

        # 获取记忆宫殿数据（如果有）
        if self.memory_palace and self.user_id:
            palace_data = self._load_palace_data()
            if palace_data:
                context.set_var("palace_data", palace_data)

        # 截断过长的记忆
        if len(context.memory) > self.memory_limit:
            context.memory = context.memory[:self.memory_limit] + "\n[截断]"

        logger.debug(f"加载上下文: {context.to_dict()}")
        return context

    def _load_session_history(self) -> List[Dict]:
        """加载会话历史"""
        try:
            if hasattr(self.session_db, 'get_messages'):
                return self.session_db.get_messages(self.session_id, limit=self.history_limit)
        except Exception as e:
            logger.warning(f"加载会话历史失败: {e}")
        return []

    def _load_palace_data(self) -> Optional[str]:
        """加载记忆宫殿数据"""
        try:
            if hasattr(self.memory_palace, 'recall'):
                return self.memory_palace.recall(self.user_id, top_k=5)
        except Exception as e:
            logger.warning(f"加载记忆宫殿数据失败: {e}")
        return None

    def save_message(self, role: str, content: str, **metadata):
        """保存消息到会话"""
        if self.session_db and self.session_id:
            try:
                if hasattr(self.session_db, 'add_message'):
                    self.session_db.add_message(
                        session_id=self.session_id,
                        role=role,
                        content=content,
                        metadata=metadata
                    )
            except Exception as e:
                logger.warning(f"保存消息失败: {e}")

    def update_memory(self, content: str):
        """更新长期记忆"""
        if self.memory_manager:
            try:
                self.memory_manager.append_memory(content)
            except Exception as e:
                logger.warning(f"更新记忆失败: {e}")

    # ── 便捷方法 ────────────────────────────────────────────────────────────

    def build_prompt(
        self,
        user_query: str,
        system_prompt: str = "",
        include_history: bool = True,
        include_memory: bool = True,
        include_profile: bool = True,
    ) -> str:
        """
        构建提示词

        Args:
            user_query: 用户问题
            system_prompt: 系统提示词
            include_history: 是否包含历史
            include_memory: 是否包含记忆
            include_profile: 是否包含用户画像

        Returns:
            str: 格式化的提示词
        """
        parts = []

        # 系统提示词
        if system_prompt:
            parts.append(f"## 系统提示\n{system_prompt}")

        # 用户画像
        if include_profile and self.user_id:
            context = self.get_context()
            if context.user_profile:
                parts.append(f"## 用户画像\n{context.user_profile}")

        # 长期记忆
        if include_memory:
            context = self.get_context()
            if context.memory:
                parts.append(f"## 长期记忆\n{context.memory}")

        # 对话历史
        if include_history:
            context = self.get_context()
            if context.history:
                recent = context.get_recent_history(self.history_limit)
                history_parts = []
                for e in recent:
                    role_text = "用户" if e.role == "user" else "助手"
                    history_parts.append(f"{role_text}: {e.content}")
                parts.append(f"## 对话历史\n" + "\n".join(history_parts))

        # 当前问题
        parts.append(f"## 当前问题\n用户: {user_query}")

        return "\n\n".join(parts)

    def add_to_history(self, role: str, content: str):
        """添加消息到历史"""
        entry = ContextEntry(role=role, content=content)
        # 如果有 context 对象，追加到它
        if hasattr(self, '_current_context'):
            self._current_context.history.append(entry)
        self.save_message(role, content)


# ── 入口点 ──────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)

    provider = UnifiedContextProvider(
        session_id="test_session",
        user_id="test_user"
    )

    # 测试获取上下文
    context = provider.get_context()
    logger.info(f"Context loaded: {context.to_dict()}")

    # 测试构建提示词
    prompt = provider.build_prompt(
        user_query="你好，请介绍一下自己",
        system_prompt="你是一个友好的 AI 助手"
    )
    logger.info(f"\n=== Prompt ===\n{prompt}")
