"""
智能上下文压缩管理器

创新设计：
1. 语义感知压缩 - 根据消息重要性动态调整
2. 层次化压缩 - 不同层级采用不同策略
3. 增量压缩 - 只压缩新增内容
4. 上下文摘要 - 自动生成对话摘要
5. 知识蒸馏 - 提取关键信息存储

Author: LivingTreeAI Agent
Date: 2026-04-30
"""

import asyncio
from typing import Dict, Any, Optional, List, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
from collections import OrderedDict

from business.tools.caveman_tool import get_caveman_tool, CompressionLevel


class MessageImportance(Enum):
    """消息重要性级别"""
    CRITICAL = "critical"    # 关键信息
    HIGH = "high"            # 高重要性
    MEDIUM = "medium"        # 中等重要性
    LOW = "low"              # 低重要性
    NOISE = "noise"          # 噪音


class CompressionTier(Enum):
    """压缩层级"""
    TIER_0 = "tier_0"        # 完整保留
    TIER_1 = "tier_1"        # 轻度压缩
    TIER_2 = "tier_2"        # 中度压缩
    TIER_3 = "tier_3"        # 重度压缩
    TIER_4 = "tier_4"        # 摘要/丢弃


@dataclass
class ContextMessage:
    """上下文消息"""
    id: str
    role: str
    content: str
    importance: MessageImportance = MessageImportance.MEDIUM
    timestamp: float = 0.0
    compressed: bool = False
    original_length: int = 0


@dataclass
class ContextSnapshot:
    """上下文快照"""
    messages: List[ContextMessage]
    summary: str
    key_points: List[str]
    timestamp: float
    token_count: int


class IntelligentContextCompressor:
    """
    智能上下文压缩管理器
    
    创新特性：
    1. 语义重要性评估 - 自动识别消息重要性
    2. 分层压缩策略 - 根据重要性应用不同压缩级别
    3. 增量压缩机制 - 只处理新增消息
    4. 动态窗口调整 - 根据上下文大小自动调整
    5. 知识蒸馏 - 提取关键信息到知识库
    """
    
    def __init__(self):
        self._logger = logger.bind(component="IntelligentContextCompressor")
        self._caveman = get_caveman_tool()
        self._messages: OrderedDict[str, ContextMessage] = OrderedDict()
        self._compressed_messages: OrderedDict[str, ContextMessage] = OrderedDict()
        self._key_points: Set[str] = set()
        self._summary = ""
        self._last_compression_time = 0.0
        self._compression_interval = 30.0  # 30秒自动压缩一次
    
    def _evaluate_importance(self, message: ContextMessage) -> MessageImportance:
        """评估消息重要性"""
        content = message.content.lower()
        role = message.role.lower()
        
        if role == "system":
            return MessageImportance.CRITICAL
        
        if role == "assistant":
            if any(keyword in content for keyword in ["重要", "警告", "错误", "注意", "必须", "关键"]):
                return MessageImportance.CRITICAL
            if any(keyword in content for keyword in ["代码", "函数", "def", "class", "import"]):
                return MessageImportance.HIGH
            return MessageImportance.HIGH
        
        if role == "user":
            if any(keyword in content for keyword in ["问题", "错误", "修复", "异常"]):
                return MessageImportance.HIGH
            if len(content) > 500:
                return MessageImportance.HIGH
        
        if len(content) < 20:
            return MessageImportance.LOW
        
        if any(keyword in content for keyword in ["好的", "是的", "明白", "收到", "谢谢", "不客气"]):
            return MessageImportance.NOISE
        
        return MessageImportance.MEDIUM
    
    def _get_compression_level(self, importance: MessageImportance) -> CompressionLevel:
        """根据重要性获取压缩级别"""
        mapping = {
            MessageImportance.CRITICAL: CompressionLevel.LITE,
            MessageImportance.HIGH: CompressionLevel.LITE,
            MessageImportance.MEDIUM: CompressionLevel.FULL,
            MessageImportance.LOW: CompressionLevel.ULTRA,
            MessageImportance.NOISE: CompressionLevel.ULTRA,
        }
        return mapping.get(importance, CompressionLevel.FULL)
    
    async def _compress_single(self, message: ContextMessage) -> ContextMessage:
        """压缩单条消息"""
        if message.compressed:
            return message
        
        importance = self._evaluate_importance(message)
        level = self._get_compression_level(importance)
        
        if level == CompressionLevel.LITE:
            return message
        
        result = await self._caveman.execute(message.content, level=level.value)
        
        if result.get("success"):
            return ContextMessage(
                id=message.id,
                role=message.role,
                content=result["compressed_text"],
                importance=importance,
                timestamp=message.timestamp,
                compressed=True,
                original_length=len(message.content)
            )
        
        return message
    
    async def add_message(self, message: Dict[str, Any]) -> ContextMessage:
        """
        添加新消息并自动压缩
        
        Args:
            message: 消息字典（包含 id, role, content）
        
        Returns:
            处理后的消息
        """
        ctx_msg = ContextMessage(
            id=message.get("id", str(hash(message))),
            role=message.get("role", "user"),
            content=message.get("content", ""),
            timestamp=message.get("timestamp", asyncio.get_event_loop().time()),
            original_length=len(message.get("content", ""))
        )
        
        ctx_msg.importance = self._evaluate_importance(ctx_msg)
        compressed_msg = await self._compress_single(ctx_msg)
        
        self._messages[ctx_msg.id] = ctx_msg
        self._compressed_messages[ctx_msg.id] = compressed_msg
        
        await self._update_summary()
        await self._extract_key_points(compressed_msg)
        
        return compressed_msg
    
    async def _update_summary(self):
        """更新对话摘要"""
        recent_messages = list(self._compressed_messages.values())[-10:]
        summary_text = "对话摘要：\n"
        
        for msg in recent_messages:
            summary_text += f"{msg.role}: {msg.content[:50]}...\n"
        
        self._summary = summary_text
    
    async def _extract_key_points(self, message: ContextMessage):
        """从消息中提取关键点"""
        content = message.content
        
        keywords = [
            "问题", "错误", "修复", "解决方案", "步骤", "代码",
            "function", "class", "method", "import", "def",
            "API", "接口", "服务", "组件", "模块"
        ]
        
        for keyword in keywords:
            if keyword in content:
                self._key_points.add(keyword)
    
    async def compress_context(self, max_token_count: int = 8192) -> List[Dict[str, Any]]:
        """
        智能压缩整个上下文
        
        策略：
        - 最近的消息保持完整
        - 较早的消息根据重要性进行压缩
        - 超过token限制时进行分层裁剪
        
        Args:
            max_token_count: 最大token数
        
        Returns:
            压缩后的消息列表
        """
        result = []
        total_tokens = 0
        
        recent_messages = list(self._compressed_messages.values())
        
        for i, msg in enumerate(reversed(recent_messages)):
            content = msg.content
            tokens = len(content) // 4
            
            if total_tokens + tokens > max_token_count:
                if i < 5:
                    result.insert(0, {"role": msg.role, "content": content[:50] + "..."})
                break
            
            result.insert(0, {"role": msg.role, "content": content})
            total_tokens += tokens
        
        return result
    
    async def get_snapshot(self) -> ContextSnapshot:
        """获取上下文快照"""
        return ContextSnapshot(
            messages=list(self._compressed_messages.values()),
            summary=self._summary,
            key_points=list(self._key_points),
            timestamp=asyncio.get_event_loop().time(),
            token_count=self.get_token_count()
        )
    
    def get_token_count(self) -> int:
        """计算当前token总数"""
        return sum(len(msg.content) // 4 for msg in self._compressed_messages.values())
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取压缩统计"""
        original_total = sum(msg.original_length for msg in self._messages.values())
        compressed_total = sum(len(msg.content) for msg in self._compressed_messages.values())
        
        importance_dist = {}
        for msg in self._messages.values():
            key = msg.importance.value
            importance_dist[key] = importance_dist.get(key, 0) + 1
        
        return {
            "total_messages": len(self._messages),
            "compressed_messages": sum(1 for m in self._compressed_messages.values() if m.compressed),
            "original_size": original_total,
            "compressed_size": compressed_total,
            "compression_ratio": 1 - (compressed_total / original_total) if original_total > 0 else 0,
            "token_count": self.get_token_count(),
            "importance_distribution": importance_dist,
            "key_points_count": len(self._key_points)
        }
    
    def clear(self):
        """清空上下文"""
        self._messages.clear()
        self._compressed_messages.clear()
        self._key_points.clear()
        self._summary = ""


# 全局实例
_context_compressor = IntelligentContextCompressor()


def get_context_compressor() -> IntelligentContextCompressor:
    """获取智能上下文压缩器实例"""
    return _context_compressor
