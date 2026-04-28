"""
ContextBufferManager - 上下文Buffer管理器

借鉴 GSD 的核心哲学：Context Buffer管理，防止长任务上下文溢出。

核心功能：
1. 自动管理上下文buffer，超限时自动压缩
2. 结合L0/L1/L2三层摘要机制
3. 智能Token预算管理
4. 支持多会话隔离

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import time


class BufferCompressionStrategy(Enum):
    """Buffer压缩策略"""
    L0_ONLY = "l0_only"           # 仅保留L0摘要
    L0_L1 = "l0_l1"               # 保留L0+L1摘要
    TRUNCATE_RECENT = "truncate_recent"  # 截断最近消息
    TRUNCATE_OLD = "truncate_old"        # 截断最早消息
    HYBRID = "hybrid"             # 混合策略（默认）


@dataclass
class BufferStats:
    """Buffer统计信息"""
    message_count: int = 0
    total_tokens: int = 0
    compression_ratio: float = 0.0
    last_compression_time: float = 0.0
    compression_count: int = 0


@dataclass
class ContextBuffer:
    """上下文Buffer"""
    session_id: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    l0_summary: str = ""
    l1_summary: str = ""
    l2_summary: str = ""
    stats: BufferStats = field(default_factory=BufferStats)
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())


class ContextBufferManager:
    """
    上下文Buffer管理器
    
    核心特性：
    1. 自动管理上下文buffer，超限时自动压缩
    2. 结合L0/L1/L2三层摘要机制
    3. 智能Token预算管理
    4. 支持多会话隔离
    5. 防止长任务上下文溢出
    """
    
    def __init__(self, max_tokens: int = 8192, compression_threshold: float = 0.8):
        self._logger = logger.bind(component="ContextBufferManager")
        
        # Buffer存储
        self._buffers: Dict[str, ContextBuffer] = {}
        
        # 配置参数
        self._max_tokens = max_tokens
        self._compression_threshold = compression_threshold  # 超过80%触发压缩
        self._min_messages_for_compression = 10
        
        # 压缩策略
        self._compression_strategy = BufferCompressionStrategy.HYBRID
        
        self._logger.info(f"✅ ContextBufferManager 初始化完成 (max_tokens={max_tokens})")
    
    def add_message(self, session_id: str, message: Dict[str, Any]):
        """
        添加消息到buffer
        
        Args:
            session_id: 会话ID
            message: 消息字典（包含role和content）
        """
        if session_id not in self._buffers:
            self._buffers[session_id] = ContextBuffer(session_id=session_id)
        
        buffer = self._buffers[session_id]
        buffer.messages.append(message)
        buffer.updated_at = time.time()
        
        # 更新统计
        buffer.stats.message_count = len(buffer.messages)
        buffer.stats.total_tokens = self._estimate_tokens(buffer.messages)
        
        # 检查是否需要压缩
        self._check_compression(session_id)
    
    def add_messages(self, session_id: str, messages: List[Dict[str, Any]]):
        """批量添加消息"""
        for msg in messages:
            self.add_message(session_id, msg)
    
    def get_buffer(self, session_id: str) -> Optional[ContextBuffer]:
        """获取buffer"""
        return self._buffers.get(session_id)
    
    def get_context(self, session_id: str, max_tokens: int = None) -> List[Dict[str, Any]]:
        """
        获取上下文（自动处理压缩）
        
        Args:
            session_id: 会话ID
            max_tokens: 最大Token数（可选，默认使用全局配置）
        
        Returns:
            上下文消息列表
        """
        effective_max = max_tokens or self._max_tokens
        buffer = self._buffers.get(session_id)
        
        if not buffer:
            return []
        
        estimated_tokens = buffer.stats.total_tokens
        
        # 如果Token超限，先进行压缩
        if estimated_tokens > effective_max:
            self._compress_buffer(session_id, effective_max)
        
        return buffer.messages
    
    def _check_compression(self, session_id: str):
        """检查是否需要压缩"""
        buffer = self._buffers.get(session_id)
        if not buffer:
            return
        
        # 检查Token使用率
        usage_ratio = buffer.stats.total_tokens / self._max_tokens
        
        if usage_ratio >= self._compression_threshold:
            self._logger.debug(f"🔄 触发压缩: session={session_id}, usage={usage_ratio:.1%}")
            self._compress_buffer(session_id)
    
    def _compress_buffer(self, session_id: str, target_tokens: int = None):
        """
        压缩buffer
        
        Args:
            session_id: 会话ID
            target_tokens: 目标Token数（可选）
        """
        buffer = self._buffers.get(session_id)
        if not buffer:
            return
        
        target = target_tokens or int(self._max_tokens * self._compression_threshold)
        
        # 生成摘要（如果还没有）
        if not buffer.l0_summary:
            buffer.l0_summary = self._generate_l0_summary(session_id)
        if not buffer.l1_summary:
            buffer.l1_summary = self._generate_l1_summary(session_id)
        
        # 根据策略压缩
        if self._compression_strategy == BufferCompressionStrategy.L0_ONLY:
            self._compress_to_l0_only(session_id)
        elif self._compression_strategy == BufferCompressionStrategy.L0_L1:
            self._compress_to_l0_l1(session_id)
        elif self._compression_strategy == BufferCompressionStrategy.TRUNCATE_RECENT:
            self._truncate_recent(session_id, target)
        elif self._compression_strategy == BufferCompressionStrategy.TRUNCATE_OLD:
            self._truncate_old(session_id, target)
        else:
            self._compress_hybrid(session_id, target)
        
        # 更新统计
        buffer.stats.compression_count += 1
        buffer.stats.last_compression_time = time.time()
        buffer.stats.total_tokens = self._estimate_tokens(buffer.messages)
        buffer.stats.compression_ratio = 1 - buffer.stats.total_tokens / self._max_tokens
        
        self._logger.info(
            f"✅ 压缩完成: session={session_id}, "
            f"messages={len(buffer.messages)}, "
            f"tokens={buffer.stats.total_tokens}, "
            f"ratio={buffer.stats.compression_ratio:.1%}"
        )
    
    def _compress_to_l0_only(self, session_id: str):
        """压缩到仅保留L0摘要"""
        buffer = self._buffers.get(session_id)
        if not buffer or not buffer.l0_summary:
            return
        
        buffer.messages = [{
            "role": "system",
            "content": f"对话摘要（L0）：\n{buffer.l0_summary}"
        }]
    
    def _compress_to_l0_l1(self, session_id: str):
        """压缩到保留L0+L1摘要"""
        buffer = self._buffers.get(session_id)
        if not buffer:
            return
        
        summary_messages = []
        if buffer.l0_summary:
            summary_messages.append({
                "role": "system",
                "content": f"快速摘要（L0）：\n{buffer.l0_summary}"
            })
        if buffer.l1_summary:
            summary_messages.append({
                "role": "system",
                "content": f"详细摘要（L1）：\n{buffer.l1_summary}"
            })
        
        buffer.messages = summary_messages
    
    def _truncate_recent(self, session_id: str, target_tokens: int):
        """截断最近的消息"""
        buffer = self._buffers.get(session_id)
        if not buffer:
            return
        
        # 从后往前保留，直到达到目标Token数
        reversed_messages = list(reversed(buffer.messages))
        new_messages = []
        current_tokens = 0
        
        for msg in reversed_messages:
            msg_tokens = self._estimate_tokens([msg])
            if current_tokens + msg_tokens <= target_tokens:
                new_messages.insert(0, msg)
                current_tokens += msg_tokens
            else:
                break
        
        buffer.messages = new_messages
    
    def _truncate_old(self, session_id: str, target_tokens: int):
        """截断最早的消息"""
        buffer = self._buffers.get(session_id)
        if not buffer:
            return
        
        new_messages = []
        current_tokens = 0
        
        for msg in buffer.messages:
            msg_tokens = self._estimate_tokens([msg])
            if current_tokens + msg_tokens <= target_tokens:
                new_messages.append(msg)
                current_tokens += msg_tokens
            else:
                break
        
        buffer.messages = new_messages
    
    def _compress_hybrid(self, session_id: str, target_tokens: int):
        """混合压缩策略"""
        buffer = self._buffers.get(session_id)
        if not buffer:
            return
        
        # 保留L0摘要 + 最新的若干消息
        summary_token = self._estimate_tokens([{"role": "system", "content": buffer.l0_summary}])
        available_tokens = target_tokens - summary_token
        
        # 获取最新消息
        reversed_messages = list(reversed(buffer.messages))
        recent_messages = []
        current_tokens = 0
        
        for msg in reversed_messages:
            msg_tokens = self._estimate_tokens([msg])
            if current_tokens + msg_tokens <= available_tokens:
                recent_messages.insert(0, msg)
                current_tokens += msg_tokens
            else:
                break
        
        # 构建新buffer
        if buffer.l0_summary:
            buffer.messages = [{
                "role": "system",
                "content": f"对话摘要：\n{buffer.l0_summary}"
            }] + recent_messages
        else:
            buffer.messages = recent_messages
    
    def _generate_l0_summary(self, session_id: str) -> str:
        """生成L0快速摘要（100-200 tokens）"""
        buffer = self._buffers.get(session_id)
        if not buffer or not buffer.messages:
            return ""
        
        user_queries = []
        assistant_responses = []
        
        for msg in buffer.messages[-10:]:  # 只看最近10条
            role = msg.get("role", "")
            content = msg.get("content", "")[:100]
            
            if role == "user":
                user_queries.append(content)
            elif role == "assistant":
                assistant_responses.append(content)
        
        parts = []
        if user_queries:
            parts.append(f"用户：{'；'.join(user_queries[-3:])}")
        if assistant_responses:
            parts.append(f"助手：{'；'.join(assistant_responses[-3:])}")
        
        return " | ".join(parts)[:200]
    
    def _generate_l1_summary(self, session_id: str) -> str:
        """生成L1详细摘要（500-1000 tokens）"""
        buffer = self._buffers.get(session_id)
        if not buffer or not buffer.messages:
            return ""
        
        # 提取主题和关键要点
        topics = set()
        key_points = []
        
        for msg in buffer.messages:
            content = msg.get("content", "")
            role = msg.get("role", "")
            
            if role == "user":
                # 提取用户问题的主题
                if len(content) > 0:
                    topics.add(content[:50])
            elif role == "assistant":
                # 提取助手回答的关键点
                sentences = content.split('。')[:3]
                key_points.extend([s.strip() for s in sentences if s.strip()])
        
        summary_parts = []
        if topics:
            summary_parts.append(f"对话主题：{', '.join(list(topics)[:5])}")
        if key_points:
            summary_parts.append(f"关键要点：{'；'.join(key_points[:5])}")
        
        return " | ".join(summary_parts)[:800]
    
    def _estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """估算Token数量"""
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        return total_chars // 4  # 粗略估算
    
    def set_summary(self, session_id: str, l0_summary: str = "", l1_summary: str = "", l2_summary: str = ""):
        """设置摘要"""
        buffer = self._buffers.get(session_id)
        if buffer:
            if l0_summary:
                buffer.l0_summary = l0_summary
            if l1_summary:
                buffer.l1_summary = l1_summary
            if l2_summary:
                buffer.l2_summary = l2_summary
    
    def get_summary(self, session_id: str, level: str = "l0") -> str:
        """获取摘要"""
        buffer = self._buffers.get(session_id)
        if not buffer:
            return ""
        
        if level == "l0":
            return buffer.l0_summary
        elif level == "l1":
            return buffer.l1_summary
        elif level == "l2":
            return buffer.l2_summary
        
        return buffer.l0_summary
    
    def get_stats(self, session_id: str) -> Optional[BufferStats]:
        """获取buffer统计信息"""
        buffer = self._buffers.get(session_id)
        return buffer.stats if buffer else None
    
    def get_all_stats(self) -> Dict[str, BufferStats]:
        """获取所有buffer的统计信息"""
        return {sid: buf.stats for sid, buf in self._buffers.items()}
    
    def clear_buffer(self, session_id: str):
        """清除buffer"""
        if session_id in self._buffers:
            del self._buffers[session_id]
            self._logger.debug(f"🗑️ 清除buffer: {session_id}")
    
    def clear_all(self):
        """清除所有buffer"""
        self._buffers.clear()
        self._logger.info("🗑️ 清除所有buffer")
    
    def set_compression_strategy(self, strategy: BufferCompressionStrategy):
        """设置压缩策略"""
        self._compression_strategy = strategy
        self._logger.info(f"🔧 设置压缩策略: {strategy.value}")
    
    def set_max_tokens(self, max_tokens: int):
        """设置最大Token限制"""
        self._max_tokens = max_tokens
        self._logger.info(f"🔧 设置最大Token: {max_tokens}")
    
    def get_session_ids(self) -> List[str]:
        """获取所有会话ID"""
        return list(self._buffers.keys())
    
    def get_session_count(self) -> int:
        """获取会话数量"""
        return len(self._buffers)


# 创建全局实例
context_buffer_manager = ContextBufferManager()


def get_context_buffer_manager() -> ContextBufferManager:
    """获取上下文Buffer管理器实例"""
    return context_buffer_manager


# 测试函数
async def test_context_buffer_manager():
    """测试上下文Buffer管理器"""
    import sys
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 ContextBufferManager")
    print("=" * 60)
    
    manager = ContextBufferManager(max_tokens=500)  # 使用较小的限制便于测试
    
    # 1. 添加消息
    print("\n[1] 测试添加消息...")
    session_id = "test_session"
    
    for i in range(15):
        manager.add_message(session_id, {
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"这是测试消息 {i}，内容比较长以占用更多token。" * 5
        })
    
    stats = manager.get_stats(session_id)
    print(f"    ✓ 添加 {stats.message_count} 条消息")
    print(f"    ✓ Token数: {stats.total_tokens}")
    
    # 2. 测试自动压缩
    print("\n[2] 测试自动压缩...")
    if stats.compression_count > 0:
        print(f"    ✓ 自动压缩触发: {stats.compression_count} 次")
        print(f"    ✓ 压缩率: {stats.compression_ratio:.1%}")
    
    # 3. 测试手动压缩
    print("\n[3] 测试手动压缩...")
    manager._compress_buffer(session_id, target_tokens=200)
    stats = manager.get_stats(session_id)
    print(f"    ✓ 压缩后消息数: {stats.message_count}")
    print(f"    ✓ 压缩后Token数: {stats.total_tokens}")
    
    # 4. 测试摘要生成
    print("\n[4] 测试摘要生成...")
    l0_summary = manager.get_summary(session_id, "l0")
    l1_summary = manager.get_summary(session_id, "l1")
    print(f"    ✓ L0摘要长度: {len(l0_summary)}")
    print(f"    ✓ L1摘要长度: {len(l1_summary)}")
    
    # 5. 测试压缩策略
    print("\n[5] 测试压缩策略...")
    manager.set_compression_strategy(BufferCompressionStrategy.L0_ONLY)
    manager._compress_buffer(session_id)
    buffer = manager.get_buffer(session_id)
    print(f"    ✓ L0_ONLY策略后消息数: {len(buffer.messages)}")
    
    # 6. 测试多会话
    print("\n[6] 测试多会话...")
    manager.add_message("session2", {"role": "user", "content": "另一个会话"})
    print(f"    ✓ 会话数量: {manager.get_session_count()}")
    
    print("\n" + "=" * 60)
    print("🎉 所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_context_buffer_manager())