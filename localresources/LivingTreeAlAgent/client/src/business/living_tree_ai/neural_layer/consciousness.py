"""
Consciousness Merging - 意识流融合
====================================

两个节点深度连接时，临时共享思维上下文

核心概念：
- 共享工作记忆 (Shared Working Memory)
- 联合注意力 (Joint Attention)
- 上下文同步 (Context Sync)

Author: LivingTreeAI Community
"""

import asyncio
import time
import uuid
import hashlib
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Dict, Any, List
from enum import Enum


class MergeLevel(Enum):
    """融合级别"""
    LEVEL_1_SHARE_INTENTION = 1  # 共享意图
    LEVEL_2_SHARE_CONTEXT = 2    # 共享上下文
    LEVEL_3_SHARE_MEMORY = 3    # 共享工作记忆
    LEVEL_4_FULL_MERGE = 4      # 完全融合


@dataclass
class SharedContext:
    """共享上下文"""
    context_id: str
    participants: List[str]
    level: MergeLevel
    shared_data: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_sync: float = field(default_factory=time.time)

    # 联合注意力
    joint_attention_topic: Optional[str] = None
    attention_weights: Dict[str, float] = field(default_factory=dict)  # 节点 -> 注意力权重


@dataclass
class JointAttention:
    """联合注意力"""
    topic: str
    focus_area: Optional[str] = None
    confidence: float = 0.0
    contributors: List[str] = field(default_factory=list)


class ConsciousnessMerging:
    """
    意识流融合

    功能：
    1. 上下文融合（多级别权限）
    2. 联合注意力建立
    3. 工作记忆同步
    4. 思维边界管理
    """

    # 配置
    SYNC_INTERVAL_MS = 100  # 同步间隔
    CONTEXT_TTL_SECONDS = 300  # 5分钟超时
    MAX_SHARED_CONTEXTS = 5

    def __init__(
        self,
        node_id: str,
        send_func: Optional[Callable[[str, dict], Awaitable]] = None,
    ):
        self.node_id = node_id

        # 共享上下文
        self.active_contexts: Dict[str, SharedContext] = {}
        self.pending_invitations: Dict[str, MergeLevel] = {}

        # 工作记忆
        self.working_memory: Dict[str, Any] = {}

        # 网络函数
        self._send_func = send_func

        # 任务
        self._sync_tasks: List[asyncio.Task] = []

        # 回调
        self._on_context_merged: Optional[Callable] = None
        self._on_context_severed: Optional[Callable] = None

    # ========== 融合请求 ==========

    async def request_merge(
        self,
        target_peer: str,
        level: MergeLevel = MergeLevel.LEVEL_3_SHARE_MEMORY,
        message: str = "",
    ) -> str:
        """
        请求与目标节点融合

        Args:
            target_peer: 目标节点ID
            level: 融合级别
            message: 附言

        Returns:
            融合请求ID
        """
        request_id = str(uuid.uuid4())[:16]

        # 发送融合请求
        if self._send_func:
            await self._send_func(target_peer, {
                "type": "merge_request",
                "request_id": request_id,
                "from": self.node_id,
                "level": level.value,
                "message": message,
            })

        # 记录待确认请求
        self.pending_invitations[request_id] = level

        return request_id

    async def accept_merge(self, request_id: str, from_peer: str) -> SharedContext:
        """
        接受融合请求

        Args:
            request_id: 请求ID
            from_peer: 请求方

        Returns:
            创建的共享上下文
        """
        level = self.pending_invitations.pop(request_id, MergeLevel.LEVEL_1_SHARE_INTENTION)

        return await self._create_shared_context([self.node_id, from_peer], level)

    async def reject_merge(self, request_id: str):
        """拒绝融合请求"""
        self.pending_invitations.pop(request_id, None)

    async def sever_merge(self, context_id: str):
        """断开融合"""
        if context_id in self.active_contexts:
            context = self.active_contexts[context_id]

            # 通知对方
            if self._send_func:
                for peer in context.participants:
                    if peer != self.node_id:
                        await self._send_func(peer, {
                            "type": "merge_severed",
                            "context_id": context_id,
                        })

            # 清理上下文
            del self.active_contexts[context_id]

            # 回调
            if self._on_context_severed:
                await self._on_context_severed(context)

    # ========== 内部实现 ==========

    async def _create_shared_context(
        self,
        participants: List[str],
        level: MergeLevel,
    ) -> SharedContext:
        """创建共享上下文"""
        context_id = str(uuid.uuid4())[:16]

        # 限制上下文数量
        if len(self.active_contexts) >= self.MAX_SHARED_CONTEXTS:
            # 移除最老的
            oldest = min(
                self.active_contexts.items(),
                key=lambda x: x[1].last_sync
            )
            await self.sever_merge(oldest[0])

        context = SharedContext(
            context_id=context_id,
            participants=participants,
            level=level,
            attention_weights={p: 1.0 / len(participants) for p in participants},
        )

        self.active_contexts[context_id] = context

        # 根据级别决定共享内容
        if level.value >= MergeLevel.LEVEL_2_SHARE_CONTEXT.value:
            # 启动上下文同步
            await self._start_context_sync(context)

        if level.value >= MergeLevel.LEVEL_3_SHARE_MEMORY.value:
            # 启动工作记忆同步
            await self._start_memory_sync(context)

        # 回调
        if self._on_context_merged:
            await self._on_context_merged(context)

        return context

    async def _start_context_sync(self, context: SharedContext):
        """启动上下文同步"""
        async def sync_loop():
            while context.context_id in self.active_contexts:
                try:
                    # 收集当前上下文
                    context_snapshot = self._collect_context_snapshot()

                    # 发送给对方
                    if self._send_func:
                        for peer in context.participants:
                            if peer != self.node_id:
                                await self._send_func(peer, {
                                    "type": "context_sync",
                                    "context_id": context.context_id,
                                    "snapshot": context_snapshot,
                                })

                    context.last_sync = time.time()
                    await asyncio.sleep(self.SYNC_INTERVAL_MS / 1000)

                except asyncio.CancelledError:
                    break
                except Exception:
                    pass

        task = asyncio.create_task(sync_loop())
        self._sync_tasks.append(task)

    async def _start_memory_sync(self, context: SharedContext):
        """启动工作记忆同步"""
        # 共享工作记忆的子集
        shared_keys = self._get_shared_memory_keys(context.level)

        async def memory_sync_loop():
            while context.context_id in self.active_contexts:
                try:
                    # 收集共享的内存
                    memory_snapshot = {
                        k: self.working_memory.get(k)
                        for k in shared_keys
                        if k in self.working_memory
                    }

                    # 广播
                    if self._send_func and memory_snapshot:
                        for peer in context.participants:
                            if peer != self.node_id:
                                await self._send_func(peer, {
                                    "type": "memory_sync",
                                    "context_id": context.context_id,
                                    "memory": memory_snapshot,
                                })

                    await asyncio.sleep(self.SYNC_INTERVAL_MS / 1000)

                except asyncio.CancelledError:
                    break
                except Exception:
                    pass

        task = asyncio.create_task(memory_sync_loop())
        self._sync_tasks.append(task)

    def _collect_context_snapshot(self) -> dict:
        """收集当前上下文快照"""
        return {
            "working_memory_keys": list(self.working_memory.keys()),
            "timestamp": time.time(),
        }

    def _get_shared_memory_keys(self, level: MergeLevel) -> List[str]:
        """根据级别获取可共享的内存键"""
        if level == MergeLevel.LEVEL_1_SHARE_INTENTION:
            return ["current_intention"]
        elif level == MergeLevel.LEVEL_2_SHARE_CONTEXT:
            return ["current_intention", "focus_topic", "task_state"]
        elif level == MergeLevel.LEVEL_3_SHARE_MEMORY:
            return ["current_intention", "focus_topic", "task_state", "temp_notes"]
        else:
            return list(self.working_memory.keys())

    # ========== 上下文接收 ==========

    async def receive_context_sync(self, data: dict):
        """接收上下文同步"""
        context_id = data.get("context_id")
        snapshot = data.get("snapshot", {})

        context = self.active_contexts.get(context_id)
        if not context:
            return

        # 更新联合注意力（如果对方正在关注某事）
        # 这里简化处理
        context.last_sync = time.time()

    async def receive_memory_sync(self, data: dict):
        """接收内存同步"""
        context_id = data.get("context_id")
        memory = data.get("memory", {})

        context = self.active_contexts.get(context_id)
        if not context:
            return

        # 合并内存（冲突解决：后者胜出）
        for key, value in memory.items():
            self.working_memory[key] = value

    async def receive_merge_request(self, data: dict):
        """接收融合请求"""
        request_id = data.get("request_id")
        from_peer = data.get("from")
        level = MergeLevel(data.get("level", 1))
        message = data.get("message", "")

        # 存储待确认请求
        self.pending_invitations[request_id] = level

        # 实际应该弹出UI让用户确认
        # 这里自动接受作为示例
        await self.accept_merge(request_id, from_peer)

    # ========== 工作记忆操作 ==========

    def set_working_memory(self, key: str, value: Any):
        """设置工作记忆"""
        self.working_memory[key] = value

    def get_working_memory(self, key: str) -> Any:
        """获取工作记忆"""
        return self.working_memory.get(key)

    def clear_working_memory(self, key: Optional[str] = None):
        """清除工作记忆"""
        if key:
            self.working_memory.pop(key, None)
        else:
            self.working_memory.clear()

    # ========== 联合注意力 ==========

    async def update_joint_attention(
        self,
        context_id: str,
        topic: str,
        focus_area: Optional[str] = None,
    ):
        """更新联合注意力焦点"""
        context = self.active_contexts.get(context_id)
        if not context:
            return

        context.joint_attention_topic = topic
        context.focus_area = focus_area

        # 广播更新
        if self._send_func:
            for peer in context.participants:
                if peer != self.node_id:
                    await self._send_func(peer, {
                        "type": "attention_update",
                        "context_id": context_id,
                        "topic": topic,
                        "focus_area": focus_area,
                    })

    # ========== 统计 ==========

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "active_contexts": len(self.active_contexts),
            "pending_requests": len(self.pending_invitations),
            "working_memory_items": len(self.working_memory),
            "contexts": [
                {
                    "id": ctx.context_id,
                    "level": ctx.level.value,
                    "participants": ctx.participants,
                    "joint_attention": ctx.joint_attention_topic,
                }
                for ctx in self.active_contexts.values()
            ],
        }


# 全局单例
_consciousness_instance: Optional[ConsciousnessMerging] = None


def get_consciousness_merger(node_id: str = "local") -> ConsciousnessMerging:
    """获取意识融合单例"""
    global _consciousness_instance
    if _consciousness_instance is None:
        _consciousness_instance = ConsciousnessMerging(node_id)
    return _consciousness_instance