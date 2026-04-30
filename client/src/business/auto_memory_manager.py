"""
自动记忆管理器 (Auto Memory Manager)
===================================

借鉴 Claude Managed Agents 的自动记忆管理能力：
1. 自动存储 - 对话结束自动保存历史记录
2. 自动检索 - 智能判断何时需要检索记忆
3. 自动摘要 - 长对话自动生成摘要
4. 自动清理 - 基于相关性自动清理无关记忆

核心特性：
- 无需显式调用，全自动管理
- 支持多种记忆类型（会话、短期、长期）
- 智能判断是否需要记忆检索
- 增量摘要更新

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import json
import time
import asyncio
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from uuid import uuid4

from business.unified_memory import (
    MemoryRouter,
    MemoryItem,
    MemoryType,
    MemoryQuery,
)
from business.intelligent_memory import get_memory_system

logger = __import__('logging').getLogger(__name__)


class MemoryContextType(Enum):
    """记忆上下文类型"""
    CHAT = "chat"           # 聊天对话
    TASK = "task"           # 任务执行
    CODE = "code"           # 代码编辑
    DOCUMENT = "document"   # 文档处理


@dataclass
class ConversationTurn:
    """对话回合"""
    role: str              # user / assistant / system
    content: str           # 内容
    timestamp: float       # 时间戳
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemorySummary:
    """记忆摘要"""
    summary_id: str
    conversation_id: str
    content: str
    key_points: List[str]
    entities: List[str]
    created_at: float
    updated_at: float
    message_count: int


class AutoMemoryManager:
    """
    自动记忆管理器
    
    核心功能：
    1. 自动存储对话历史
    2. 自动生成和更新摘要
    3. 智能判断是否需要检索记忆
    4. 自动清理过期记忆
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._memory_router = MemoryRouter.get_instance()
        self._intelligent_memory = get_memory_system()
        
        # 当前对话状态
        self._active_conversations: Dict[str, List[ConversationTurn]] = {}
        
        # 记忆摘要缓存
        self._summaries: Dict[str, MemorySummary] = {}
        
        # 配置参数
        self._config = {
            "auto_store_enabled": True,
            "auto_summary_enabled": True,
            "auto_retrieval_enabled": True,
            "summary_frequency": 5,  # 每5条消息生成/更新一次摘要
            "short_term_limit": 100,  # 短期记忆最大条目数
            "long_term_limit": 1000,  # 长期记忆最大条目数
            "retention_days": 30,     # 记忆保留天数
        }
        
        # LLM 调用函数（延迟加载）
        self._llm_callable = None
        
        self._initialized = True
        logger.info("[AutoMemoryManager] 自动记忆管理器初始化完成")
    
    def set_llm_callable(self, llm_callable: Callable[[str], str]):
        """设置 LLM 调用函数"""
        self._llm_callable = llm_callable
    
    def configure(self, **kwargs):
        """配置自动记忆管理器"""
        self._config.update(kwargs)
        logger.info(f"[AutoMemoryManager] 配置更新: {kwargs}")
    
    def start_conversation(self, conversation_id: str, context_type: MemoryContextType = MemoryContextType.CHAT):
        """
        开始新对话
        
        Args:
            conversation_id: 对话ID
            context_type: 上下文类型
        """
        if conversation_id not in self._active_conversations:
            self._active_conversations[conversation_id] = []
            logger.debug(f"[AutoMemoryManager] 开始对话: {conversation_id}")
    
    def end_conversation(self, conversation_id: str):
        """
        结束对话（自动存储和生成摘要）
        
        Args:
            conversation_id: 对话ID
        """
        if conversation_id not in self._active_conversations:
            return
        
        turns = self._active_conversations[conversation_id]
        
        if self._config["auto_store_enabled"]:
            # 存储对话历史
            self._store_conversation(conversation_id, turns)
            
            # 生成/更新摘要
            if self._config["auto_summary_enabled"] and len(turns) > 0:
                self._generate_or_update_summary(conversation_id, turns)
        
        # 清理活跃对话
        del self._active_conversations[conversation_id]
        logger.debug(f"[AutoMemoryManager] 结束对话: {conversation_id}, 消息数: {len(turns)}")
    
    def add_message(self, conversation_id: str, role: str, content: str, **kwargs):
        """
        添加消息（自动触发存储和摘要更新）
        
        Args:
            conversation_id: 对话ID
            role: 角色 (user/assistant/system)
            content: 消息内容
            **kwargs: 额外元数据
        """
        # 确保对话已启动
        if conversation_id not in self._active_conversations:
            self.start_conversation(conversation_id)
        
        # 添加对话回合
        turn = ConversationTurn(
            role=role,
            content=content,
            timestamp=time.time(),
            metadata=kwargs
        )
        self._active_conversations[conversation_id].append(turn)
        
        # 检查是否需要更新摘要
        turns = self._active_conversations[conversation_id]
        if self._config["auto_summary_enabled"]:
            if len(turns) % self._config["summary_frequency"] == 0:
                self._generate_or_update_summary(conversation_id, turns)
    
    async def add_message_async(self, conversation_id: str, role: str, content: str, **kwargs):
        """异步添加消息"""
        self.add_message(conversation_id, role, content, **kwargs)
        await asyncio.sleep(0)
    
    def should_retrieve_memory(self, query: str, conversation_id: str = None) -> bool:
        """
        智能判断是否需要检索记忆
        
        根据查询内容自动判断是否需要从记忆系统检索相关信息
        
        Args:
            query: 用户查询
            conversation_id: 当前对话ID（可选）
            
        Returns:
            bool: 是否需要检索记忆
        """
        if not self._config["auto_retrieval_enabled"]:
            return False
        
        query_lower = query.lower()
        
        # 关键词判断 - 需要记忆的场景
        memory_keywords = [
            "记得", "回忆", "之前", "上次", "之前说", "之前讨论",
            "历史", "过去", "以前", "曾经", "之前提到", "之前的",
            "总结", "概括", "回顾", "整理", "复述"
        ]
        
        # 如果包含这些关键词，肯定需要检索
        if any(keyword in query_lower for keyword in memory_keywords):
            return True
        
        # 检查当前对话是否足够长，可能需要上下文
        if conversation_id and conversation_id in self._active_conversations:
            turns = self._active_conversations[conversation_id]
            if len(turns) > 10:  # 超过10条消息可能需要检索
                return True
        
        # 检查查询是否涉及实体（可能在记忆中）
        if self._detect_entity_reference(query):
            return True
        
        return False
    
    def retrieve_memory(self, query: str, conversation_id: str = None, limit: int = 10) -> Dict[str, Any]:
        """
        智能检索记忆
        
        Args:
            query: 查询内容
            conversation_id: 对话ID（可选）
            limit: 返回结果数量限制
            
        Returns:
            检索结果
        """
        if not self.should_retrieve_memory(query, conversation_id):
            return {"items": [], "summary": None, "need_memory": False}
        
        # 构建查询
        memory_query = MemoryQuery(
            query=query,
            memory_types=[MemoryType.SESSION, MemoryType.SEMANTIC, MemoryType.LONG_TERM],
            limit=limit
        )
        
        # 执行查询
        result = self._memory_router.query(memory_query)
        
        # 获取相关摘要
        summary = None
        if conversation_id and conversation_id in self._summaries:
            summary = self._summaries[conversation_id]
        
        return {
            "items": [item.to_dict() for item in result.items],
            "sources": result.sources,
            "summary": summary.content if summary else None,
            "need_memory": True,
            "total_count": len(result.items)
        }
    
    async def retrieve_memory_async(self, query: str, conversation_id: str = None, limit: int = 10) -> Dict[str, Any]:
        """异步检索记忆"""
        return self.retrieve_memory(query, conversation_id, limit)
    
    def get_conversation_summary(self, conversation_id: str) -> Optional[MemorySummary]:
        """
        获取对话摘要
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            记忆摘要（如果存在）
        """
        return self._summaries.get(conversation_id)
    
    def cleanup_expired_memory(self):
        """
        自动清理过期记忆
        
        根据 retention_days 配置清理过期的记忆
        """
        cutoff_time = time.time() - (self._config["retention_days"] * 24 * 60 * 60)
        
        # 清理活跃对话中过期的消息
        for conv_id, turns in list(self._active_conversations.items()):
            self._active_conversations[conv_id] = [
                turn for turn in turns if turn.timestamp > cutoff_time
            ]
        
        # 清理过期的摘要
        expired_summaries = [
            sid for sid, summary in self._summaries.items()
            if summary.updated_at < cutoff_time
        ]
        for sid in expired_summaries:
            del self._summaries[sid]
        
        logger.info(f"[AutoMemoryManager] 清理过期记忆完成，移除 {len(expired_summaries)} 个摘要")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "active_conversations": len(self._active_conversations),
            "total_summaries": len(self._summaries),
            "config": self._config,
        }
    
    # ========== 私有方法 ==========
    
    def _store_conversation(self, conversation_id: str, turns: List[ConversationTurn]):
        """存储对话历史到记忆系统"""
        try:
            # 构建记忆项内容
            conversation_data = {
                "conversation_id": conversation_id,
                "turns": [
                    {
                        "role": turn.role,
                        "content": turn.content,
                        "timestamp": turn.timestamp,
                        "metadata": turn.metadata
                    }
                    for turn in turns
                ],
                "total_turns": len(turns),
                "created_at": turns[0].timestamp if turns else time.time(),
                "updated_at": turns[-1].timestamp if turns else time.time(),
            }
            
            # 存储到会话记忆
            item = MemoryItem(
                id=f"conv_{conversation_id}",
                content=json.dumps(conversation_data),
                memory_type=MemoryType.SESSION,
                tags=["conversation", conversation_id],
                metadata={
                    "turn_count": len(turns),
                    "last_update": time.time()
                }
            )
            
            self._memory_router.store(item)
            logger.debug(f"[AutoMemoryManager] 存储对话: {conversation_id}, {len(turns)} 条消息")
            
        except Exception as e:
            logger.error(f"[AutoMemoryManager] 存储对话失败: {e}")
    
    def _generate_or_update_summary(self, conversation_id: str, turns: List[ConversationTurn]):
        """生成或更新对话摘要"""
        try:
            if not self._llm_callable:
                # 尝试获取默认的 LLM 调用
                try:
                    from business.global_model_router import call_model_sync, ModelCapability
                    llm_response = call_model_sync(ModelCapability.CHAT, self._build_summary_prompt(turns))
                except ImportError:
                    logger.warning("[AutoMemoryManager] LLM 不可用，跳过摘要生成")
                    return
            else:
                llm_response = self._llm_callable(self._build_summary_prompt(turns))
            
            # 解析摘要
            summary_data = self._parse_summary_response(llm_response)
            
            # 更新或创建摘要
            if conversation_id in self._summaries:
                existing = self._summaries[conversation_id]
                self._summaries[conversation_id] = MemorySummary(
                    summary_id=existing.summary_id,
                    conversation_id=conversation_id,
                    content=summary_data.get("summary", ""),
                    key_points=summary_data.get("key_points", []),
                    entities=summary_data.get("entities", []),
                    created_at=existing.created_at,
                    updated_at=time.time(),
                    message_count=len(turns)
                )
            else:
                self._summaries[conversation_id] = MemorySummary(
                    summary_id=f"sum_{uuid4().hex[:8]}",
                    conversation_id=conversation_id,
                    content=summary_data.get("summary", ""),
                    key_points=summary_data.get("key_points", []),
                    entities=summary_data.get("entities", []),
                    created_at=time.time(),
                    updated_at=time.time(),
                    message_count=len(turns)
                )
            
            # 存储摘要到长期记忆
            self._store_summary(conversation_id, self._summaries[conversation_id])
            
            logger.debug(f"[AutoMemoryManager] 更新摘要: {conversation_id}")
            
        except Exception as e:
            logger.error(f"[AutoMemoryManager] 生成摘要失败: {e}")
    
    def _build_summary_prompt(self, turns: List[ConversationTurn]) -> str:
        """构建摘要生成提示"""
        conversation_text = "\n".join([
            f"{turn.role}: {turn.content}"
            for turn in turns
        ])
        
        prompt = f"""请对以下对话进行总结：

{conversation_text}

请输出：
1. 摘要（用简洁的语言概括对话内容）
2. 要点（列出3-5个关键要点）
3. 实体（列出提到的重要人物、地点、事物）

格式要求：
- 摘要：[摘要内容]
- 要点：[要点1]；[要点2]；[要点3]
- 实体：[实体1]、[实体2]、[实体3]
"""
        return prompt
    
    def _parse_summary_response(self, response: str) -> Dict[str, Any]:
        """解析摘要响应"""
        result = {
            "summary": "",
            "key_points": [],
            "entities": []
        }
        
        lines = response.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("摘要："):
                result["summary"] = line[3:].strip()
            elif line.startswith("要点："):
                points = line[3:].strip().split("；")
                result["key_points"] = [p.strip() for p in points if p.strip()]
            elif line.startswith("实体："):
                entities = line[3:].strip().split("、")
                result["entities"] = [e.strip() for e in entities if e.strip()]
        
        return result
    
    def _store_summary(self, conversation_id: str, summary: MemorySummary):
        """存储摘要到长期记忆"""
        item = MemoryItem(
            id=summary.summary_id,
            content=summary.content,
            memory_type=MemoryType.LONG_TERM,
            tags=["summary", conversation_id] + summary.entities,
            metadata={
                "key_points": summary.key_points,
                "entities": summary.entities,
                "message_count": summary.message_count,
                "updated_at": summary.updated_at
            }
        )
        self._memory_router.store(item)
    
    def _detect_entity_reference(self, query: str) -> bool:
        """检测查询中是否涉及实体引用"""
        # 简单的实体检测：检查是否有大写开头的单词或特定名词
        import re
        
        # 匹配可能的实体（大写开头的单词）
        entity_pattern = r'\b[A-Z][a-zA-Z]+\b'
        entities = re.findall(entity_pattern, query)
        
        # 如果有多个大写开头的单词，可能涉及实体
        if len(entities) >= 2:
            return True
        
        # 检查是否有特定的实体类型关键词
        entity_type_keywords = ["公司", "产品", "项目", "系统", "功能", "模块"]
        if any(keyword in query for keyword in entity_type_keywords):
            return True
        
        return False


# 便捷函数
def get_auto_memory_manager() -> AutoMemoryManager:
    """获取自动记忆管理器单例"""
    return AutoMemoryManager()


__all__ = [
    "AutoMemoryManager",
    "MemoryContextType",
    "ConversationTurn",
    "MemorySummary",
    "get_auto_memory_manager",
]