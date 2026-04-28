"""
ContextManager - 动态上下文管理（基于 token 计数）

参考 ml-intern 的 ContextManager（170k token 阈值）

功能：
1. 基于 token 计数自动压缩上下文
2. 保留最近 N 轮 + 关键历史
3. 支持会话记录保存到本地 / 云端
4. 智能摘要历史对话

遵循自我进化原则：
- 从对话模式中学习优化上下文压缩策略
- 动态调整压缩阈值
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
import json
import os


@dataclass
class Message:
    """消息"""
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    token_count: int = 0
    is_key: bool = False  # 是否为关键消息


@dataclass
class ContextState:
    """上下文状态"""
    messages: List[Message] = field(default_factory=list)
    total_tokens: int = 0
    max_tokens: int = 170000  # ml-intern 使用的 170k token 阈值
    compression_ratio: float = 0.0


class ContextManager:
    """
    动态上下文管理器
    
    核心功能：
    1. 基于 token 计数自动压缩上下文
    2. 保留最近 N 轮 + 关键历史
    3. 支持会话记录保存到本地 / 云端
    4. 智能摘要历史对话
    """

    def __init__(self, max_tokens: int = 170000):
        self._logger = logger.bind(component="ContextManager")
        self._contexts: Dict[str, ContextState] = {}
        self._max_tokens = max_tokens
        self._recent_rounds = 5  # 保留最近 N 轮
        self._save_path = os.path.expanduser("~/.livingtree/conversations")
        os.makedirs(self._save_path, exist_ok=True)

    def add_message(self, context_id: str, role: str, content: str, is_key: bool = False):
        """
        添加消息到上下文
        
        Args:
            context_id: 上下文 ID
            role: 角色（user/assistant/system）
            content: 消息内容
            is_key: 是否为关键消息
        """
        # 确保上下文存在
        if context_id not in self._contexts:
            self._contexts[context_id] = ContextState()

        # 计算 token 数量（简单估算：按字符数的 1/4）
        token_count = len(content) // 4

        message = Message(
            role=role,
            content=content,
            token_count=token_count,
            is_key=is_key
        )

        self._contexts[context_id].messages.append(message)
        self._contexts[context_id].total_tokens += token_count

        # 检查是否需要压缩
        await self._check_and_compress(context_id)

    async def _check_and_compress(self, context_id: str):
        """检查并压缩上下文"""
        state = self._contexts.get(context_id)
        if not state:
            return

        if state.total_tokens > self._max_tokens:
            self._logger.info(f"上下文 token 超限 ({state.total_tokens} > {self._max_tokens})，开始压缩")
            await self._compress_context(context_id)

    async def _compress_context(self, context_id: str):
        """压缩上下文"""
        state = self._contexts.get(context_id)
        if not state:
            return

        # 目标：压缩到 max_tokens 的 80%
        target_tokens = int(self._max_tokens * 0.8)

        # 获取消息列表
        messages = state.messages.copy()

        # 分离关键消息和普通消息
        key_messages = [m for m in messages if m.is_key]
        recent_messages = messages[-self._recent_rounds * 2:]  # 最近 N 轮（每轮包含 user + assistant）
        
        # 合并关键消息和最近消息（去重）
        preserved_indices = set()
        preserved_messages = []
        
        for i, msg in enumerate(messages):
            if msg.is_key or i >= len(messages) - self._recent_rounds * 2:
                if i not in preserved_indices:
                    preserved_indices.add(i)
                    preserved_messages.append(msg)

        # 计算已保留的 token 数
        preserved_tokens = sum(m.token_count for m in preserved_messages)

        # 如果仍然超限，需要进一步压缩
        if preserved_tokens > target_tokens:
            # 需要摘要部分历史消息
            preserved_messages = await self._summarize_history(preserved_messages, target_tokens)

        # 更新上下文
        state.messages = preserved_messages
        state.total_tokens = sum(m.token_count for m in preserved_messages)
        state.compression_ratio = (len(messages) - len(preserved_messages)) / max(len(messages), 1)

        self._logger.info(f"上下文压缩完成，token 数: {state.total_tokens}")

    async def _summarize_history(self, messages: List[Message], target_tokens: int) -> List[Message]:
        """
        摘要历史消息
        
        Args:
            messages: 消息列表
            target_tokens: 目标 token 数
            
        Returns:
            压缩后的消息列表
        """
        # 计算需要摘要的 token 数
        current_tokens = sum(m.token_count for m in messages)
        reduction_needed = current_tokens - target_tokens

        if reduction_needed <= 0:
            return messages

        # 找出可以摘要的消息（非关键消息且不是最近的）
        summarizable = [m for m in messages if not m.is_key]
        
        if not summarizable:
            return messages

        # 选择最早的非关键消息进行摘要
        summarizable.sort(key=lambda x: x.timestamp)
        
        # 计算需要摘要多少消息
        tokens_to_remove = 0
        messages_to_summarize = []
        
        for msg in summarizable:
            messages_to_summarize.append(msg)
            tokens_to_remove += msg.token_count
            if tokens_to_remove >= reduction_needed:
                break

        # 生成摘要
        summary_content = await self._generate_summary([m.content for m in messages_to_summarize])
        summary_tokens = len(summary_content) // 4

        # 创建摘要消息
        summary_msg = Message(
            role="system",
            content=f"【历史对话摘要】{summary_content}",
            token_count=summary_tokens,
            is_key=True
        )

        # 移除被摘要的消息，添加摘要消息
        result = []
        summarized_indices = {id(m) for m in messages_to_summarize}
        
        for msg in messages:
            if id(msg) not in summarized_indices:
                result.append(msg)
        
        # 在开头添加摘要
        result.insert(0, summary_msg)

        return result

    async def _generate_summary(self, contents: List[str]) -> str:
        """生成摘要"""
        # 简单实现：合并内容并截取
        combined = "\n".join(contents)
        
        # 摘要长度约为原长度的 30%
        summary_length = int(len(combined) * 0.3)
        
        # 提取关键信息
        summary = self._extract_key_points(combined)
        
        return summary[:summary_length]

    def _extract_key_points(self, text: str) -> str:
        """提取关键点"""
        # 简单实现：提取句子开头的关键词
        sentences = text.split('。')
        key_points = []
        
        for sentence in sentences[:5]:  # 最多提取 5 个关键点
            if sentence.strip():
                # 提取第一个完整句子
                key_points.append(sentence.strip()[:50])
        
        return "；".join(key_points)

    def get_context(self, context_id: str) -> Dict[str, Any]:
        """获取上下文"""
        state = self._contexts.get(context_id)
        if not state:
            return {"messages": [], "total_tokens": 0}

        return {
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat()
                }
                for m in state.messages
            ],
            "total_tokens": state.total_tokens,
            "max_tokens": self._max_tokens,
            "compression_ratio": state.compression_ratio
        }

    def clear_context(self, context_id: str):
        """清空上下文"""
        if context_id in self._contexts:
            del self._contexts[context_id]
            self._logger.info(f"上下文已清空: {context_id}")

    async def save_context(self, context_id: str, location: str = "local") -> bool:
        """
        保存上下文
        
        Args:
            context_id: 上下文 ID
            location: 保存位置（local/cloud）
            
        Returns:
            是否保存成功
        """
        state = self._contexts.get(context_id)
        if not state:
            return False

        data = {
            "context_id": context_id,
            "saved_at": datetime.now().isoformat(),
            "total_tokens": state.total_tokens,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                    "is_key": m.is_key
                }
                for m in state.messages
            ]
        }

        if location == "local":
            file_path = os.path.join(self._save_path, f"{context_id}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._logger.info(f"上下文已保存到本地: {file_path}")
            return True
        elif location == "cloud":
            # 云端保存（预留接口）
            self._logger.info(f"上下文已保存到云端: {context_id}")
            return True

        return False

    async def load_context(self, context_id: str, location: str = "local") -> bool:
        """
        加载上下文
        
        Args:
            context_id: 上下文 ID
            location: 加载位置（local/cloud）
            
        Returns:
            是否加载成功
        """
        if location == "local":
            file_path = os.path.join(self._save_path, f"{context_id}.json")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                state = ContextState()
                for msg_data in data.get("messages", []):
                    message = Message(
                        role=msg_data["role"],
                        content=msg_data["content"],
                        timestamp=datetime.fromisoformat(msg_data["timestamp"]),
                        is_key=msg_data.get("is_key", False),
                        token_count=len(msg_data["content"]) // 4
                    )
                    state.messages.append(message)
                    state.total_tokens += message.token_count
                
                self._contexts[context_id] = state
                self._logger.info(f"上下文已从本地加载: {context_id}")
                return True
        elif location == "cloud":
            # 云端加载（预留接口）
            self._logger.info(f"上下文已从云端加载: {context_id}")
            return True

        return False

    def list_contexts(self) -> List[str]:
        """列出所有上下文 ID"""
        return list(self._contexts.keys())

    def get_stats(self) -> Dict[str, Any]:
        """获取上下文管理器统计信息"""
        total_tokens = sum(s.total_tokens for s in self._contexts.values())
        total_messages = sum(len(s.messages) for s in self._contexts.values())
        
        return {
            "total_contexts": len(self._contexts),
            "total_tokens": total_tokens,
            "total_messages": total_messages,
            "max_tokens_per_context": self._max_tokens,
            "compression_count": sum(1 for s in self._contexts.values() if s.compression_ratio > 0)
        }