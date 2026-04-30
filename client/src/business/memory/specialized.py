"""
Specialized Memory - 特殊记忆类型

包含针对特定场景优化的记忆系统：

1. Error Memory - 错误学习记忆
   - 存储错误案例和恢复策略
   - 用于错误恢复和自我修复

2. Evolution Memory - 进化决策记忆
   - 存储进化决策历史
   - 用于自我进化和优化
"""

import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class ErrorEntry:
    """错误条目"""
    id: str
    error_type: str
    error_message: str
    context: Dict = field(default_factory=dict)
    recovery_steps: List[str] = field(default_factory=list)
    success_rate: float = 0.0
    occurrence_count: int = 1
    last_occurred: float = field(default_factory=lambda: time.time())
    created_at: float = field(default_factory=lambda: time.time())


@dataclass
class EvolutionEntry:
    """进化条目"""
    id: str
    phase: str
    decision: Dict
    outcome: str = ""
    metrics: Dict = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: time.time())


class ErrorMemory:
    """错误学习记忆 - 存储错误案例和恢复策略"""
    
    def __init__(self):
        self._logger = logger.bind(component="ErrorMemory")
        self._errors: Dict[str, ErrorEntry] = {}
        self._errors_by_type: Dict[str, List[str]] = {}
        
        # 尝试加载现有错误记忆系统
        self._error_memory = None
        self._init_error_memory()
        
        self._logger.info("ErrorMemory 初始化完成")
    
    def _init_error_memory(self):
        """初始化错误记忆连接"""
        try:
            from business.error_memory import ErrorLearningSystem, get_error_system
            self._error_memory = get_error_system()
            self._logger.info("✓ 集成 ErrorLearningSystem")
        except Exception as e:
            self._logger.warning(f"ErrorLearningSystem 加载失败，使用内存存储: {e}")
    
    def query(self, query: str, context: Dict = None) -> Dict:
        """
        查询错误记忆
        
        Args:
            query: 查询内容（错误类型或错误消息）
            context: 上下文
        
        Returns:
            查询结果
        """
        # 如果有外部错误记忆，优先使用
        if self._error_memory:
            try:
                result = self._error_memory.learn_and_fix_from_message(query, context)
                matched_pattern = result.get("matched_pattern")
                templates = result.get("recommended_templates", [])
                
                if matched_pattern or templates:
                    solutions = []
                    for template in templates[:3]:
                        fix_steps = template.get("fix_steps", [])
                        if isinstance(fix_steps, list):
                            solutions.extend(fix_steps)
                        elif isinstance(fix_steps, str):
                            solutions.append(fix_steps)
                    
                    confidence = result.get("confidence", 0.5)
                    
                    return {
                        "success": True,
                        "content": "\n".join(solutions) if solutions else str(result),
                        "confidence": confidence,
                        "type": "error_memory",
                        "source": "specialized",
                        "matched_pattern": matched_pattern,
                        "templates": templates,
                        "solutions": solutions
                    }
            except Exception as e:
                self._logger.warning(f"ErrorLearningSystem 查询失败，回退到内存存储: {e}")
        
        # 内存存储查询
        query_lower = query.lower()
        
        # 按错误类型查找
        matched_errors = []
        for err_type, error_ids in self._errors_by_type.items():
            if err_type.lower() in query_lower or query_lower in err_type.lower():
                matched_errors.extend(error_ids)
        
        # 按错误消息查找
        if not matched_errors:
            for error_id, entry in self._errors.items():
                if query_lower in entry.error_message.lower():
                    matched_errors.append(error_id)
        
        if matched_errors:
            # 选择成功率最高的
            best_error = None
            best_success_rate = 0.0
            
            for error_id in matched_errors:
                entry = self._errors[error_id]
                if entry.success_rate > best_success_rate:
                    best_success_rate = entry.success_rate
                    best_error = entry
            
            if best_error:
                return {
                    "success": True,
                    "content": "\n".join(best_error.recovery_steps),
                    "confidence": 0.7 + best_error.success_rate * 0.2,
                    "type": "error_memory",
                    "source": "specialized",
                    "error_type": best_error.error_type,
                    "success_rate": best_error.success_rate,
                    "occurrence_count": best_error.occurrence_count
                }
        
        return {"success": False, "content": "", "confidence": 0.0}
    
    def store(self, content: str, **kwargs) -> str:
        """
        存储错误记录
        
        Args:
            content: 错误消息
            **kwargs: 包含 error_type, recovery_steps, context 等
        
        Returns:
            存储的ID
        """
        entry_id = kwargs.get("id", f"err_{int(time.time())}")
        error_type = kwargs.get("error_type", "unknown")
        recovery_steps = kwargs.get("recovery_steps", [])
        context = kwargs.get("context", {})
        
        # 如果有外部错误记忆，优先使用
        if self._error_memory:
            try:
                # 使用 ErrorLearningSystem 的 learn_and_fix_from_message
                result = self._error_memory.learn_and_fix_from_message(content, context)
                return result.get("record_id", entry_id)
            except Exception as e:
                self._logger.warning(f"ErrorLearningSystem 存储失败，回退到内存存储: {e}")
        
        # 内存存储
        if error_type in self._errors_by_type:
            # 检查是否已有相同错误
            for existing_id in self._errors_by_type[error_type]:
                existing = self._errors[existing_id]
                if existing.error_message == content:
                    # 更新计数
                    existing.occurrence_count += 1
                    existing.last_occurred = time.time()
                    return existing_id
        else:
            self._errors_by_type[error_type] = []
        
        self._errors[entry_id] = ErrorEntry(
            id=entry_id,
            error_type=error_type,
            error_message=content,
            context=context,
            recovery_steps=recovery_steps
        )
        self._errors_by_type[error_type].append(entry_id)
        
        return entry_id
    
    def update_success_rate(self, error_id: str, success: bool):
        """更新错误恢复成功率"""
        if error_id not in self._errors:
            return
        
        entry = self._errors[error_id]
        total = entry.occurrence_count
        successful = int(entry.success_rate * total)
        
        if success:
            successful += 1
        
        entry.success_rate = successful / (total + 1)
        entry.occurrence_count = total + 1
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        total_errors = len(self._errors)
        total_occurrences = sum(e.occurrence_count for e in self._errors.values())
        avg_success_rate = sum(e.success_rate for e in self._errors.values()) / max(total_errors, 1)
        
        return {
            "total_errors": total_errors,
            "total_occurrences": total_occurrences,
            "error_types": list(self._errors_by_type.keys()),
            "avg_success_rate": avg_success_rate,
            "using_external_error_memory": self._error_memory is not None
        }


class EvolutionMemory:
    """进化决策记忆 - 存储进化决策历史"""
    
    def __init__(self):
        self._logger = logger.bind(component="EvolutionMemory")
        self._entries: Dict[str, EvolutionEntry] = {}
        self._entries_by_phase: Dict[str, List[str]] = {}
        
        # 尝试加载现有进化引擎记忆
        self._evolution_memory = None
        self._init_evolution_memory()
        
        self._logger.info("EvolutionMemory 初始化完成")
    
    def _init_evolution_memory(self):
        """初始化进化记忆连接"""
        try:
            from business.evolution_engine.memory.learning_engine import (
                get_learning_engine
            )
            self._evolution_memory = get_learning_engine()
            self._logger.info("✓ 集成 LearningEngine")
        except Exception as e:
            self._logger.warning(f"LearningEngine 加载失败，使用内存存储: {e}")
    
    def query(self, query: str, context: Dict = None) -> Dict:
        """
        查询进化记忆
        
        Args:
            query: 查询内容（阶段名称或决策类型）
            context: 上下文
        
        Returns:
            查询结果
        """
        # 如果有外部进化记忆，优先使用
        if self._evolution_memory:
            try:
                stats = self._evolution_memory.get_statistics()
                return {
                    "success": True,
                    "content": f"进化统计: {stats}",
                    "confidence": 0.8,
                    "type": "evolution_memory",
                    "source": "specialized",
                    "statistics": stats
                }
            except Exception as e:
                self._logger.warning(f"进化记忆查询失败，回退到内存存储: {e}")
        
        # 内存存储查询
        query_lower = query.lower()
        
        # 按阶段查找
        matched_entries = []
        for phase, entry_ids in self._entries_by_phase.items():
            if phase.lower() in query_lower or query_lower in phase.lower():
                matched_entries.extend(entry_ids)
        
        # 按决策内容查找
        if not matched_entries:
            for entry_id, entry in self._entries.items():
                if query_lower in str(entry.decision).lower():
                    matched_entries.append(entry_id)
        
        if matched_entries:
            recent_entries = sorted(
                matched_entries,
                key=lambda x: self._entries[x].created_at,
                reverse=True
            )[:5]
            
            results = []
            for entry_id in recent_entries:
                entry = self._entries[entry_id]
                results.append({
                    "phase": entry.phase,
                    "decision": entry.decision,
                    "outcome": entry.outcome,
                    "metrics": entry.metrics
                })
            
            return {
                "success": True,
                "content": str(results),
                "confidence": 0.75,
                "type": "evolution_memory",
                "source": "specialized",
                "entries": results
            }
        
        return {"success": False, "content": "", "confidence": 0.0}
    
    def store(self, content: str, **kwargs) -> str:
        """
        存储进化决策
        
        Args:
            content: 决策内容描述
            **kwargs: 包含 phase, decision, outcome, metrics 等
        
        Returns:
            存储的ID
        """
        entry_id = kwargs.get("id", f"evo_{int(time.time())}")
        phase = kwargs.get("phase", "unknown")
        decision = kwargs.get("decision", {})
        outcome = kwargs.get("outcome", "")
        metrics = kwargs.get("metrics", {})
        
        # 如果有外部进化记忆，优先使用
        if self._evolution_memory:
            try:
                self._evolution_memory.record_interaction({
                    "query": content,
                    "intent": "evolution_decision",
                    "source": "evolution_memory",
                    "response": str(decision),
                    "timestamp": time.time()
                })
                return entry_id
            except Exception as e:
                self._logger.warning(f"进化记忆存储失败，回退到内存存储: {e}")
        
        # 内存存储
        if phase not in self._entries_by_phase:
            self._entries_by_phase[phase] = []
        
        self._entries[entry_id] = EvolutionEntry(
            id=entry_id,
            phase=phase,
            decision=decision,
            outcome=outcome,
            metrics=metrics
        )
        self._entries_by_phase[phase].append(entry_id)
        
        return entry_id
    
    def record_outcome(self, entry_id: str, outcome: str, metrics: Dict):
        """记录决策结果"""
        if entry_id not in self._entries:
            return
        
        entry = self._entries[entry_id]
        entry.outcome = outcome
        entry.metrics = metrics
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        total_entries = len(self._entries)
        phases = list(self._entries_by_phase.keys())
        
        return {
            "total_entries": total_entries,
            "phases": phases,
            "entries_by_phase": {p: len(ids) for p, ids in self._entries_by_phase.items()},
            "using_external_evolution_memory": self._evolution_memory is not None
        }


# 单例模式
_error_memory_instance = None
_evolution_memory_instance = None

def get_error_memory() -> ErrorMemory:
    """获取错误记忆实例"""
    global _error_memory_instance
    if _error_memory_instance is None:
        _error_memory_instance = ErrorMemory()
    return _error_memory_instance

def get_evolution_memory() -> EvolutionMemory:
    """获取进化记忆实例"""
    global _evolution_memory_instance
    if _evolution_memory_instance is None:
        _evolution_memory_instance = EvolutionMemory()
    return _evolution_memory_instance


if __name__ == "__main__":
    print("=" * 60)
    print("Specialized Memory 测试")
    print("=" * 60)
    
    # 测试 ErrorMemory
    error_mem = get_error_memory()
    
    error_mem.store(
        "Connection timeout",
        error_type="network_error",
        recovery_steps=["检查网络连接", "重试连接", "切换备用服务器"]
    )
    
    result = error_mem.query("network_error")
    print(f"错误记忆查询 'network_error':")
    print(f"  成功: {result['success']}")
    print(f"  置信度: {result['confidence']:.2f}")
    print(f"  内容: {result.get('content')}")
    
    # 测试 EvolutionMemory
    evo_mem = get_evolution_memory()
    
    evo_mem.store(
        "模型升级决策",
        phase="model_upgrade",
        decision={"model": "qwen3.6", "reason": "性能提升"},
        outcome="success",
        metrics={"accuracy": 0.92, "speedup": 1.5}
    )
    
    result = evo_mem.query("model_upgrade")
    print(f"\n进化记忆查询 'model_upgrade':")
    print(f"  成功: {result['success']}")
    print(f"  置信度: {result['confidence']:.2f}")
    
    print("\n" + "=" * 60)