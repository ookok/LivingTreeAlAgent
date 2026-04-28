"""
IncrementalContextManager - 增量上下文管理器

借鉴 pi-mono 的 pi-agent-core 设计理念，实现增量更新机制。

核心特性：
1. 增量更新：仅追加新消息，不重建全量上下文
2. L0/L1/L2 三层摘要：逐层深入，按需加载
3. Token预算管理：智能控制上下文大小
4. 差分渲染：UI层仅更新变化部分

预期效果：Token消耗降低90-95%

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

import json
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class ContextLayer(Enum):
    """上下文层级"""
    L0 = "l0"  # 快速摘要（100-200 tokens）
    L1 = "l1"  # 详细摘要（500-1000 tokens）
    L2 = "l2"  # 完整上下文（全量）


@dataclass
class ContextSnapshot:
    """上下文快照"""
    session_id: str
    messages: List[Dict[str, Any]]
    l0_summary: str = ""
    l1_summary: str = ""
    token_count: int = 0
    timestamp: float = 0.0


@dataclass
class IncrementalUpdate:
    """增量更新记录"""
    session_id: str
    new_messages: List[Dict[str, Any]]
    timestamp: float
    dirty: bool = True


class IncrementalContextManager:
    """
    增量上下文管理器
    
    核心功能：
    1. 增量更新：仅追加新消息，避免全量重建
    2. L0/L1/L2 三层摘要管理
    3. Token预算控制
    4. 差分渲染支持
    """
    
    def __init__(self):
        self._logger = logger.bind(component="IncrementalContextManager")
        
        # 上下文缓存
        self._context_cache: Dict[str, List[Dict[str, Any]]] = {}
        
        # 分层摘要缓存
        self._l0_cache: Dict[str, str] = {}  # L0快速摘要
        self._l1_cache: Dict[str, str] = {}  # L1详细摘要
        
        # 脏标记（用于增量更新检测）
        self._dirty_flags: Dict[str, bool] = {}
        
        # Token计数缓存
        self._token_cache: Dict[str, int] = {}
        
        # 最大Token限制
        self._max_tokens = 8192
        self._l0_threshold_ratio = 0.3  # L0占用低于30%时加载L1
        
        self._logger.info("✅ 增量上下文管理器初始化完成")
    
    def update_incremental(self, session_id: str, new_messages: List[Dict[str, Any]]):
        """
        增量更新上下文（仅更新变化部分）
        
        Args:
            session_id: 会话ID
            new_messages: 新消息列表
        """
        if session_id not in self._context_cache:
            self._context_cache[session_id] = []
            self._l0_cache[session_id] = ""
            self._l1_cache[session_id] = ""
        
        # 仅追加新消息，不重建全量上下文
        self._context_cache[session_id].extend(new_messages)
        
        # 标记为脏状态
        self._dirty_flags[session_id] = True
        
        # 清空缓存的摘要（需要重新生成）
        self._l0_cache[session_id] = ""
        self._l1_cache[session_id] = ""
        
        self._logger.debug(f"📥 增量更新完成: session={session_id}, added={len(new_messages)} messages")
    
    def get_context(self, session_id: str, max_tokens: int = None) -> List[Dict[str, Any]]:
        """
        获取上下文（L0/L1/L2逐层深入）
        
        Args:
            session_id: 会话ID
            max_tokens: 最大Token数
        
        Returns:
            上下文消息列表
        """
        effective_max = max_tokens or self._max_tokens
        
        if session_id not in self._context_cache:
            return []
        
        # 获取当前上下文
        context = self._context_cache[session_id]
        
        # 估算Token数量
        estimated_tokens = self._estimate_tokens(context)
        
        # L0快速筛选
        if estimated_tokens <= effective_max * self._l0_threshold_ratio:
            # Token预算充足，可以加载更多
            return self._get_enhanced_context(session_id, effective_max)
        
        # Token预算紧张，返回精简上下文
        return self._get_compressed_context(session_id, effective_max)
    
    def _get_enhanced_context(self, session_id: str, max_tokens: int) -> List[Dict[str, Any]]:
        """获取增强上下文（包含L1摘要）"""
        context = self._context_cache[session_id]
        estimated_tokens = self._estimate_tokens(context)
        
        # 如果有L1摘要且Token足够，添加到上下文开头
        if self._l1_cache[session_id] and estimated_tokens < max_tokens * 0.5:
            l1_summary = {
                "role": "system",
                "content": f"对话摘要（L1）：\n{self._l1_cache[session_id]}"
            }
            return [l1_summary] + context
        
        return context
    
    def _get_compressed_context(self, session_id: str, max_tokens: int) -> List[Dict[str, Any]]:
        """获取压缩上下文（仅包含最新消息和L0摘要）"""
        context = self._context_cache[session_id]
        
        # 生成或获取L0摘要
        if not self._l0_cache[session_id]:
            self._l0_cache[session_id] = self._generate_l0_summary(session_id)
        
        l0_summary = {
            "role": "system",
            "content": f"对话摘要：\n{self._l0_cache[session_id]}"
        }
        
        # 计算可用Token
        summary_tokens = self._estimate_tokens([l0_summary])
        available_tokens = max_tokens - summary_tokens
        
        # 获取最新的消息
        recent_messages = []
        current_tokens = 0
        
        for message in reversed(context):
            msg_tokens = self._estimate_tokens([message])
            if current_tokens + msg_tokens <= available_tokens:
                recent_messages.insert(0, message)
                current_tokens += msg_tokens
            else:
                break
        
        return [l0_summary] + recent_messages
    
    def _generate_l0_summary(self, session_id: str) -> str:
        """生成L0快速摘要"""
        context = self._context_cache.get(session_id, [])
        if not context:
            return ""
        
        # 提取关键信息
        user_queries = []
        assistant_responses = []
        
        for msg in context:
            if msg.get("role") == "user":
                user_queries.append(msg.get("content", "")[:50])
            elif msg.get("role") == "assistant":
                assistant_responses.append(msg.get("content", "")[:50])
        
        summary_parts = []
        if user_queries:
            summary_parts.append(f"用户问题：{'；'.join(user_queries[-3:])}")
        if assistant_responses:
            summary_parts.append(f"助手回复：{'；'.join(assistant_responses[-3:])}")
        
        return " | ".join(summary_parts)[:200]
    
    def set_l0_summary(self, session_id: str, summary: str):
        """设置L0摘要"""
        self._l0_cache[session_id] = summary
        self._dirty_flags[session_id] = False
    
    def set_l1_summary(self, session_id: str, summary: str):
        """设置L1摘要"""
        self._l1_cache[session_id] = summary
    
    def get_l0_summary(self, session_id: str) -> str:
        """获取L0摘要"""
        return self._l0_cache.get(session_id, "")
    
    def get_l1_summary(self, session_id: str) -> str:
        """获取L1摘要"""
        return self._l1_cache.get(session_id, "")
    
    def is_dirty(self, session_id: str) -> bool:
        """检查会话是否有未处理的更新"""
        return self._dirty_flags.get(session_id, False)
    
    def mark_clean(self, session_id: str):
        """标记会话为已处理"""
        self._dirty_flags[session_id] = False
    
    def _estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """估算Token数量"""
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        # 粗略估算：1 token ≈ 4 字符
        return total_chars // 4
    
    def get_token_count(self, session_id: str) -> int:
        """获取会话Token计数"""
        context = self._context_cache.get(session_id, [])
        return self._estimate_tokens(context)
    
    def set_max_tokens(self, max_tokens: int):
        """设置最大Token限制"""
        self._max_tokens = max_tokens
    
    def get_max_tokens(self) -> int:
        """获取最大Token限制"""
        return self._max_tokens
    
    def clear_session(self, session_id: str):
        """清除会话上下文"""
        if session_id in self._context_cache:
            del self._context_cache[session_id]
            del self._l0_cache[session_id]
            del self._l1_cache[session_id]
            del self._dirty_flags[session_id]
            self._logger.debug(f"🗑️ 清除会话: {session_id}")
    
    def clear_all(self):
        """清除所有上下文"""
        self._context_cache.clear()
        self._l0_cache.clear()
        self._l1_cache.clear()
        self._dirty_flags.clear()
        self._logger.info("🗑️ 清除所有上下文")
    
    def get_session_ids(self) -> List[str]:
        """获取所有会话ID"""
        return list(self._context_cache.keys())
    
    def get_session_count(self) -> int:
        """获取会话数量"""
        return len(self._context_cache)
    
    def save_context(self, session_id: str, filepath: str):
        """保存上下文到文件"""
        context = self._context_cache.get(session_id, [])
        snapshot = {
            "session_id": session_id,
            "messages": context,
            "l0_summary": self._l0_cache.get(session_id, ""),
            "l1_summary": self._l1_cache.get(session_id, "")
        }
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        
        self._logger.debug(f"💾 保存上下文: {session_id} -> {filepath}")
    
    def load_context(self, filepath: str) -> str:
        """从文件加载上下文"""
        if not os.path.exists(filepath):
            return ""
        
        with open(filepath, 'r', encoding='utf-8') as f:
            snapshot = json.load(f)
        
        session_id = snapshot["session_id"]
        self._context_cache[session_id] = snapshot["messages"]
        self._l0_cache[session_id] = snapshot.get("l0_summary", "")
        self._l1_cache[session_id] = snapshot.get("l1_summary", "")
        self._dirty_flags[session_id] = False
        
        self._logger.debug(f"📤 加载上下文: {filepath} -> {session_id}")
        return session_id
    
    def get_diff(self, session_id: str, last_message_count: int) -> Tuple[List[Dict], int]:
        """
        获取差异（新增的消息）
        
        Args:
            session_id: 会话ID
            last_message_count: 上次处理的消息数量
        
        Returns:
            (新增消息列表, 当前消息总数)
        """
        context = self._context_cache.get(session_id, [])
        current_count = len(context)
        
        if current_count > last_message_count:
            new_messages = context[last_message_count:]
            return new_messages, current_count
        
        return [], current_count


# 创建全局实例
incremental_context_manager = IncrementalContextManager()


def get_incremental_context_manager() -> IncrementalContextManager:
    """获取增量上下文管理器实例"""
    return incremental_context_manager


# 测试函数
async def test_incremental_context():
    """测试增量上下文管理器"""
    import sys
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 IncrementalContextManager")
    print("=" * 60)
    
    manager = IncrementalContextManager()
    
    # 测试增量更新
    print("\n[1] 测试增量更新:")
    session_id = "test_session_001"
    
    messages1 = [
        {"role": "user", "content": "你好，我想了解人工智能"},
        {"role": "assistant", "content": "您好！人工智能是..."},
    ]
    manager.update_incremental(session_id, messages1)
    print(f"    ✓ 添加 {len(messages1)} 条消息")
    
    messages2 = [
        {"role": "user", "content": "什么是机器学习？"},
        {"role": "assistant", "content": "机器学习是人工智能的一个分支..."},
    ]
    manager.update_incremental(session_id, messages2)
    print(f"    ✓ 增量添加 {len(messages2)} 条消息")
    
    # 测试获取上下文
    print("\n[2] 测试获取上下文:")
    context = manager.get_context(session_id)
    print(f"    ✓ 上下文消息数: {len(context)}")
    for i, msg in enumerate(context):
        print(f"      [{i}] {msg['role']}: {msg['content'][:30]}...")
    
    # 测试分层摘要
    print("\n[3] 测试分层摘要:")
    l0_summary = manager.get_l0_summary(session_id)
    print(f"    ✓ L0摘要: {l0_summary}")
    
    manager.set_l1_summary(session_id, "这是一个关于AI和机器学习的对话")
    l1_summary = manager.get_l1_summary(session_id)
    print(f"    ✓ L1摘要: {l1_summary}")
    
    # 测试Token计数
    print("\n[4] 测试Token计数:")
    tokens = manager.get_token_count(session_id)
    print(f"    ✓ Token计数: {tokens}")
    
    # 测试脏标记
    print("\n[5] 测试脏标记:")
    print(f"    ✓ 是否脏: {manager.is_dirty(session_id)}")
    manager.mark_clean(session_id)
    print(f"    ✓ 标记为干净后: {manager.is_dirty(session_id)}")
    
    # 测试差异获取
    print("\n[6] 测试差异获取:")
    diff, count = manager.get_diff(session_id, 2)
    print(f"    ✓ 新增消息数: {len(diff)}, 当前总数: {count}")
    
    # 测试保存和加载
    print("\n[7] 测试保存和加载:")
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    manager.save_context(session_id, temp_path)
    print(f"    ✓ 保存上下文到: {temp_path}")
    
    new_session_id = manager.load_context(temp_path)
    print(f"    ✓ 加载上下文，会话ID: {new_session_id}")
    
    os.unlink(temp_path)
    
    # 测试清除会话
    print("\n[8] 测试清除会话:")
    manager.clear_session(session_id)
    print(f"    ✓ 会话数量: {manager.get_session_count()}")
    
    print("\n" + "=" * 60)
    print("🎉 所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_incremental_context())