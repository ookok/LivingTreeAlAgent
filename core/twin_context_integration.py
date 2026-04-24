# -*- coding: utf-8 -*-
"""
数字分身上下文集成 - AI原生OS愿景 Phase 2

将数字分身与 Phase 1 的上下文管理能力集成：
- 数字分身记忆：学习用户上下文偏好
- 数字分身技能：继承用户的代码风格和偏好
- 上下文同步：数字分身自动管理上下文
- 学习与进化：从交互中学习改进

Author: AI Native OS Team
Date: 2026-04-24
"""

import json
import time
import uuid
from typing import Dict, List, Optional, Any, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
from enum import Enum


# ============================================================================
# 导入 Phase 1 模块
# ============================================================================

# 意图保持型压缩器
try:
    from core.intent_preserving_compressor import (
        IntentRecognizer, CodeSignatureExtractor, ContextPyramid,
        IntentPreservingCompressor
    )
    HAS_COMPRESSOR = True
except ImportError:
    HAS_COMPRESSOR = False

# 三级验证流水线
try:
    from core.three_level_verification import (
        ThreeLevelVerificationPipeline, VerifiedCompressionPipeline,
        VerificationStatus
    )
    HAS_VERIFIER = True
except ImportError:
    HAS_VERIFIER = False

# 语义索引
try:
    from core.semantic_index import (
        SemanticIndexer, VirtualFileSystem, SemanticChunk,
        LazySemanticLoader
    )
    HAS_INDEXER = True
except ImportError:
    HAS_INDEXER = False


# ============================================================================
# 数据结构
# ============================================================================

class MemoryType(Enum):
    """记忆类型"""
    CONTEXT_PREFERENCE = "context_preference"  # 上下文偏好
    CODE_STYLE = "code_style"                  # 代码风格
    WORKING_PATTERN = "working_pattern"       # 工作模式
    INTENT_PATTERN = "intent_pattern"         # 意图模式
    SEMANTIC_MEMORY = "semantic_memory"       # 语义记忆


@dataclass
class TwinContextMemory:
    """数字分身上下文记忆"""
    memory_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    memory_type: str = MemoryType.CONTEXT_PREFERENCE.value
    content: str = ""
    context_pattern: str = ""  # 触发该记忆的上下文模式
    usage_count: int = 0       # 使用次数
    success_rate: float = 1.0  # 成功率
    last_used: str = ""        # 上次使用时间
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: List[str] = field(default_factory=list)
    embedding: Optional[List[float]] = None  # 向量表示（可选）
    
    def record_usage(self, success: bool):
        """记录使用"""
        self.usage_count += 1
        self.last_used = datetime.now().isoformat()
        
        # 更新成功率
        total = self.usage_count
        prev_success = self.success_rate * (total - 1)
        new_success = prev_success + (1 if success else 0)
        self.success_rate = new_success / total


@dataclass
class ContextPreference:
    """上下文偏好"""
    user_id: str
    twin_id: str
    
    # 压缩偏好
    preferred_compression_ratio: float = 0.7  # 偏好的压缩率
    min_intent_preservation: float = 0.8      # 最小意图保留度
    
    # 验证偏好
    enable_syntax_check: bool = True           # 启用语法检查
    enable_semantic_check: bool = True        # 启用语义检查
    enable_integration_check: bool = True     # 启用集成检查
    
    # 索引偏好
    enable_semantic_index: bool = True         # 启用语义索引
    index_update_interval: int = 60           # 索引更新间隔（秒）
    
    # 代码偏好
    preferred_languages: List[str] = field(default_factory=lambda: ["python", "javascript"])
    code_style: str = "modern"                # 代码风格
    include_comments: bool = True             # 包含注释
    
    # 学习设置
    learning_enabled: bool = True             # 启用学习
    learning_rate: float = 0.1                # 学习率
    memory_retention_days: int = 30           # 记忆保留天数
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "twin_id": self.twin_id,
            "preferred_compression_ratio": self.preferred_compression_ratio,
            "min_intent_preservation": self.min_intent_preservation,
            "enable_syntax_check": self.enable_syntax_check,
            "enable_semantic_check": self.enable_semantic_check,
            "enable_integration_check": self.enable_integration_check,
            "enable_semantic_index": self.enable_semantic_index,
            "index_update_interval": self.index_update_interval,
            "preferred_languages": self.preferred_languages,
            "code_style": self.code_style,
            "include_comments": self.include_comments,
            "learning_enabled": self.learning_enabled,
            "learning_rate": self.learning_rate,
            "memory_retention_days": self.memory_retention_days
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContextPreference":
        return cls(**data)


@dataclass
class LearningRecord:
    """学习记录"""
    twin_id: str
    session_id: str
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    intent_signature: Dict[str, Any] = field(default_factory=dict)
    context_before: str = ""
    context_after: str = ""
    action_taken: str = ""
    outcome: str = ""  # success, failure, partial
    feedback: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    improvement_score: float = 0.0  # 改进评分


# ============================================================================
# 数字分身上下文管理器
# ============================================================================

class TwinContextManager:
    """
    数字分身上下文管理器
    
    整合 Phase 1 的上下文管理能力与数字分身：
    1. 管理数字分身的上下文记忆
    2. 根据用户偏好调整上下文处理
    3. 从交互中学习改进
    4. 提供智能上下文建议
    """
    
    def __init__(self, twin_id: str, user_id: str):
        """
        初始化
        
        Args:
            twin_id: 数字分身ID
            user_id: 用户ID
        """
        self.twin_id = twin_id
        self.user_id = user_id
        
        # 记忆存储
        self.memories: Dict[str, TwinContextMemory] = {}
        self.preference: ContextPreference = ContextPreference(
            user_id=user_id,
            twin_id=twin_id
        )
        
        # 学习记录
        self.learning_records: List[LearningRecord] = []
        
        # Phase 1 组件
        self._init_phase1_components()
        
        # 虚拟文件系统
        self.vfs: Optional[VirtualFileSystem] = None
        
        # 统计
        self.stats = {
            "total_processed": 0,
            "successful_compressions": 0,
            "failed_compressions": 0,
            "memory_hits": 0,
            "memory_misses": 0,
            "learning_updates": 0
        }
    
    def _init_phase1_components(self):
        """初始化 Phase 1 组件"""
        self.intent_recognizer = IntentRecognizer() if HAS_COMPRESSOR else None
        self.code_extractor = CodeSignatureExtractor() if HAS_COMPRESSOR else None
        self.pyramid = ContextPyramid() if HAS_COMPRESSOR else None
        self.compressor = IntentPreservingCompressor() if HAS_COMPRESSOR else None
        
        self.verifier = ThreeLevelVerificationPipeline() if HAS_VERIFIER else None
        
        self.indexer = SemanticIndexer() if HAS_INDEXER else None
    
    # -------------------------------------------------------------------------
    # 上下文处理
    # -------------------------------------------------------------------------
    
    def process_context(self, query: str, context: str, code: str = "",
                       original_query: str = "") -> Dict[str, Any]:
        """
        处理上下文（整合 Phase 1 的所有能力）
        
        Args:
            query: 用户查询
            context: 原始上下文
            code: 代码内容
            original_query: 原始查询
        
        Returns:
            处理结果
        """
        self.stats["total_processed"] += 1
        
        result = {
            "compressed": context,
            "intent_signature": {},
            "verification_report": None,
            "vfs_path": None,
            "memories_used": [],
            "success": True
        }
        
        # 1. 意图识别
        if self.intent_recognizer:
            intent_sig = self.intent_recognizer.recognize(query)
            result["intent_signature"] = {
                "type": intent_sig.intent_type.value,
                "action": intent_sig.action,
                "target": intent_sig.target,
                "constraints": intent_sig.constraints
            }
        else:
            result["intent_signature"] = {"type": "unknown"}
        
        # 2. 压缩
        if self.compressor:
            compression_result = self.compressor.compress(
                query=query,
                context=context,
                code=code
            )
            result["compressed"] = compression_result.get("compressed", context)
        
        # 3. 验证
        if self.verifier and self.preference.learning_enabled:
            verification_report = self.verifier.verify(
                context=result["compressed"],
                intent_signature=result["intent_signature"],
                original_query=original_query or query
            )
            result["verification_report"] = {
                "status": verification_report.overall_status.value,
                "summary": verification_report.get_summary(),
                "duration_ms": verification_report.total_duration_ms
            }
            
            if verification_report.overall_status == VerificationStatus.PASSED:
                self.stats["successful_compressions"] += 1
            else:
                self.stats["failed_compressions"] += 1
        
        # 4. 语义索引
        if self.indexer and self.preference.enable_semantic_index:
            self.vfs = self.indexer.index(
                context=result["compressed"],
                intent_signature=result["intent_signature"]
            )
            result["vfs_path"] = f"/twin/{self.twin_id}/context"
        
        # 5. 记忆匹配
        matched_memories = self._find_relevant_memories(query, result["intent_signature"])
        result["memories_used"] = [m.memory_id for m in matched_memories]
        
        # 更新统计
        if matched_memories:
            self.stats["memory_hits"] += 1
        else:
            self.stats["memory_misses"] += 1
        
        # 6. 学习（异步）
        if self.preference.learning_enabled:
            self._record_learning(
                intent_sig=result["intent_signature"],
                context_before=context,
                context_after=result["compressed"]
            )
        
        return result
    
    def quick_process(self, query: str, context: str) -> str:
        """
        快速上下文处理（仅压缩）
        
        Args:
            query: 用户查询
            context: 上下文
        
        Returns:
            压缩后的上下文
        """
        if self.compressor:
            result = self.compressor.compress(query=query, context=context, code="")
            return result.get("compressed", context)
        return context
    
    # -------------------------------------------------------------------------
    # 记忆管理
    # -------------------------------------------------------------------------
    
    def add_memory(self, memory_type: str, content: str, 
                   context_pattern: str = "", tags: List[str] = None) -> TwinContextMemory:
        """
        添加记忆
        
        Args:
            memory_type: 记忆类型
            content: 记忆内容
            context_pattern: 触发模式
            tags: 标签
        
        Returns:
            创建的记忆
        """
        memory = TwinContextMemory(
            memory_type=memory_type,
            content=content,
            context_pattern=context_pattern,
            tags=tags or []
        )
        
        self.memories[memory.memory_id] = memory
        self._prune_old_memories()
        
        return memory
    
    def _find_relevant_memories(self, query: str, 
                                intent_signature: Dict) -> List[TwinContextMemory]:
        """查找相关记忆"""
        query_lower = query.lower()
        relevant = []
        
        for memory in self.memories.values():
            score = 0.0
            
            # 标签匹配
            if memory.tags:
                for tag in memory.tags:
                    if tag.lower() in query_lower:
                        score += 0.3
            
            # 意图类型匹配
            if memory.memory_type == intent_signature.get("type"):
                score += 0.3
            
            # 模式匹配
            if memory.context_pattern and memory.context_pattern.lower() in query_lower:
                score += 0.4
            
            # 成功率加权
            score *= memory.success_rate
            
            if score > 0.3:
                relevant.append((memory, score))
        
        # 按得分排序
        relevant.sort(key=lambda x: x[1], reverse=True)
        return [m for m, _ in relevant[:5]]
    
    def get_memories(self, memory_type: Optional[str] = None,
                     min_usage: int = 0) -> List[TwinContextMemory]:
        """获取记忆"""
        memories = list(self.memories.values())
        
        if memory_type:
            memories = [m for m in memories if m.memory_type == memory_type]
        
        if min_usage > 0:
            memories = [m for m in memories if m.usage_count >= min_usage]
        
        return sorted(memories, key=lambda m: m.success_rate, reverse=True)
    
    def _prune_old_memories(self):
        """清理过期记忆"""
        retention_days = self.preference.memory_retention_days
        cutoff = datetime.now().timestamp() - (retention_days * 24 * 3600)
        
        to_remove = []
        for memory in self.memories.values():
            if memory.usage_count == 0:
                created = datetime.fromisoformat(memory.created_at).timestamp()
                if created < cutoff:
                    to_remove.append(memory.memory_id)
        
        for mid in to_remove:
            del self.memories[mid]
    
    def clear_memories(self, memory_type: Optional[str] = None):
        """清除记忆"""
        if memory_type:
            self.memories = {
                k: v for k, v in self.memories.items()
                if v.memory_type != memory_type
            }
        else:
            self.memories.clear()
    
    # -------------------------------------------------------------------------
    # 学习系统
    # -------------------------------------------------------------------------
    
    def _record_learning(self, intent_sig: Dict, context_before: str,
                         context_after: str):
        """记录学习"""
        record = LearningRecord(
            twin_id=self.twin_id,
            session_id="",  # 可以在会话开始时设置
            intent_signature=intent_sig,
            context_before=context_before[:500],  # 限制长度
            context_after=context_after[:500]
        )
        
        self.learning_records.append(record)
        self.stats["learning_updates"] += 1
        
        # 自动创建相关记忆
        if len(self.learning_records) >= 5:
            self._consolidate_learning()
    
    def _consolidate_learning(self):
        """整合学习（生成新记忆）"""
        recent = self.learning_records[-10:]
        
        # 统计意图模式
        intent_types = defaultdict(int)
        for record in recent:
            itype = record.intent_signature.get("type", "unknown")
            intent_types[itype] += 1
        
        # 最常见的意图
        if intent_types:
            most_common = max(intent_types.items(), key=lambda x: x[1])
            if most_common[1] >= 3:
                # 创建意图模式记忆
                self.add_memory(
                    memory_type=MemoryType.INTENT_PATTERN.value,
                    content=f"常见意图类型: {most_common[0]} (出现 {most_common[1]} 次)",
                    context_pattern=most_common[0],
                    tags=[most_common[0], "pattern"]
                )
    
    def learn_from_feedback(self, record_id: str, feedback: str,
                           outcome: str = "success"):
        """
        从反馈中学习
        
        Args:
            record_id: 学习记录ID
            feedback: 反馈内容
            outcome: 结果 (success/failure/partial)
        """
        # 找到记录
        record = None
        for r in self.learning_records:
            if r.record_id == record_id:
                record = r
                break
        
        if not record:
            return
        
        # 更新记录
        record.feedback = feedback
        record.outcome = outcome
        
        # 计算改进评分
        if outcome == "success":
            record.improvement_score = 1.0
        elif outcome == "partial":
            record.improvement_score = 0.5
        else:
            record.improvement_score = 0.0
        
        # 更新相关记忆
        for memory in self.memories.values():
            if memory.context_pattern == record.intent_signature.get("type"):
                memory.record_usage(outcome == "success")
        
        # 根据反馈调整偏好
        self._adjust_preferences_from_feedback(feedback, outcome)
    
    def _adjust_preferences_from_feedback(self, feedback: str, outcome: str):
        """根据反馈调整偏好"""
        feedback_lower = feedback.lower()
        lr = self.preference.learning_rate
        
        # 压缩率调整
        if "too much" in feedback_lower or "lost" in feedback_lower:
            self.preference.preferred_compression_ratio -= lr * 0.1
            self.preference.preferred_compression_ratio = max(0.5, self.preference.preferred_compression_ratio)
        
        elif "too little" in feedback_lower or "verbose" in feedback_lower:
            self.preference.preferred_compression_ratio += lr * 0.1
            self.preference.preferred_compression_ratio = min(0.9, self.preference.preferred_compression_ratio)
        
        # 意图保留度调整
        if "intent lost" in feedback_lower or "missing" in feedback_lower:
            self.preference.min_intent_preservation += lr * 0.05
            self.preference.min_intent_preservation = min(0.95, self.preference.min_intent_preservation)
    
    # -------------------------------------------------------------------------
    # 智能建议
    # -------------------------------------------------------------------------
    
    def suggest_context_improvements(self, query: str) -> List[str]:
        """
        建议上下文改进
        
        Args:
            query: 当前查询
        
        Returns:
            改进建议列表
        """
        suggestions = []
        
        # 基于记忆的建议
        memories = self._find_relevant_memories(query, {})
        
        if memories:
            # 基于历史成功的建议
            for memory in memories[:3]:
                if memory.success_rate >= 0.8:
                    if memory.memory_type == MemoryType.CODE_STYLE.value:
                        suggestions.append(f"根据历史，建议使用 {memory.content} 风格")
                    elif memory.memory_type == MemoryType.CONTEXT_PREFERENCE.value:
                        suggestions.append(f"这种查询通常使用 {memory.content} 配置")
        
        # 基于统计的建议
        if self.stats["memory_misses"] > self.stats["memory_hits"]:
            suggestions.append("记忆命中率较低，考虑增加相关记忆")
        
        success_rate = self.stats["successful_compressions"] / max(1, self.stats["total_processed"])
        if success_rate < 0.7:
            suggestions.append("压缩成功率偏低，建议放宽压缩要求")
        
        return suggestions
    
    def get_context_summary(self) -> Dict[str, Any]:
        """获取上下文摘要"""
        return {
            "twin_id": self.twin_id,
            "user_id": self.user_id,
            "stats": self.stats,
            "memory_count": len(self.memories),
            "memory_types": list(set(m.memory_type for m in self.memories.values())),
            "learning_records": len(self.learning_records),
            "preferences": self.preference.to_dict()
        }
    
    # -------------------------------------------------------------------------
    # 序列化
    # -------------------------------------------------------------------------
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "twin_id": self.twin_id,
            "user_id": self.user_id,
            "preference": self.preference.to_dict(),
            "memories": {k: {
                "memory_id": v.memory_id,
                "memory_type": v.memory_type,
                "content": v.content,
                "context_pattern": v.context_pattern,
                "usage_count": v.usage_count,
                "success_rate": v.success_rate,
                "last_used": v.last_used,
                "created_at": v.created_at,
                "tags": v.tags
            } for k, v in self.memories.items()},
            "stats": self.stats
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TwinContextManager":
        """从字典创建"""
        manager = cls(
            twin_id=data["twin_id"],
            user_id=data["user_id"]
        )
        
        if "preference" in data:
            manager.preference = ContextPreference.from_dict(data["preference"])
        
        if "memories" in data:
            for k, v in data["memories"].items():
                memory = TwinContextMemory(**v)
                manager.memories[k] = memory
        
        if "stats" in data:
            manager.stats.update(data["stats"])
        
        return manager


# ============================================================================
# 数字分身上下文工厂
# ============================================================================

class TwinContextFactory:
    """
    数字分身上下文工厂
    
    创建和管理多个数字分身的上下文管理器。
    """
    
    def __init__(self):
        self.managers: Dict[str, TwinContextManager] = {}
        self._lock = __import__('threading').Lock()
    
    def create_manager(self, twin_id: str, user_id: str) -> TwinContextManager:
        """创建管理器"""
        with self._lock:
            if twin_id not in self.managers:
                self.managers[twin_id] = TwinContextManager(twin_id, user_id)
            return self.managers[twin_id]
    
    def get_manager(self, twin_id: str) -> Optional[TwinContextManager]:
        """获取管理器"""
        return self.managers.get(twin_id)
    
    def get_or_create(self, twin_id: str, user_id: str) -> TwinContextManager:
        """获取或创建"""
        manager = self.get_manager(twin_id)
        if not manager:
            manager = self.create_manager(twin_id, user_id)
        return manager
    
    def delete_manager(self, twin_id: str) -> bool:
        """删除管理器"""
        with self._lock:
            if twin_id in self.managers:
                del self.managers[twin_id]
                return True
            return False
    
    def list_managers(self) -> List[str]:
        """列出所有管理器"""
        return list(self.managers.keys())
    
    def save_state(self, path: str) -> bool:
        """保存状态"""
        try:
            data = {
                twin_id: manager.to_dict()
                for twin_id, manager in self.managers.items()
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存失败: {e}")
            return False
    
    def load_state(self, path: str) -> bool:
        """加载状态"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for twin_id, twin_data in data.items():
                self.managers[twin_id] = TwinContextManager.from_dict(twin_data)
            
            return True
        except Exception as e:
            print(f"加载失败: {e}")
            return False


# ============================================================================
# 全局实例
# ============================================================================

_twin_context_factory: Optional[TwinContextFactory] = None


def get_twin_context_factory() -> TwinContextFactory:
    """获取工厂实例"""
    global _twin_context_factory
    if _twin_context_factory is None:
        _twin_context_factory = TwinContextFactory()
    return _twin_context_factory


def create_twin_context_manager(twin_id: str, user_id: str) -> TwinContextManager:
    """创建数字分身上下文管理器"""
    return get_twin_context_factory().create_manager(twin_id, user_id)


# ============================================================================
# 便捷函数
# ============================================================================

def quick_process(twin_id: str, query: str, context: str) -> str:
    """
    快速处理上下文
    
    用法:
        result = quick_process("twin_123", "帮我写登录函数", large_context)
    """
    factory = get_twin_context_factory()
    manager = factory.get_or_create(twin_id, "default_user")
    return manager.quick_process(query, context)


def full_process(twin_id: str, query: str, context: str, 
                code: str = "") -> Dict[str, Any]:
    """
    完整处理上下文
    
    用法:
        result = full_process("twin_123", query, context, code)
        print(result["compressed"])
        print(result["verification_report"])
    """
    factory = get_twin_context_factory()
    manager = factory.get_or_create(twin_id, "default_user")
    return manager.process_context(query, context, code)


def learn_from_interaction(twin_id: str, record_id: str, 
                          feedback: str, outcome: str = "success"):
    """
    从交互中学习
    
    用法:
        learn_from_interaction("twin_123", record_id, "很好！", "success")
    """
    factory = get_twin_context_factory()
    manager = factory.get_or_create(twin_id, "default_user")
    manager.learn_from_feedback(record_id, feedback, outcome)


def add_twin_memory(twin_id: str, memory_type: str, content: str,
                    context_pattern: str = "", tags: List[str] = None):
    """
    添加数字分身记忆
    
    用法:
        add_twin_memory("twin_123", "code_style", "Python 现代风格", 
                       context_pattern="python", tags=["python", "modern"])
    """
    factory = get_twin_context_factory()
    manager = factory.get_or_create(twin_id, "default_user")
    manager.add_memory(memory_type, content, context_pattern, tags)
