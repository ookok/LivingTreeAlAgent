"""
AmphiLoop 容错回滚与检查点系统

实现双向循环调度、状态持久化、动态终止判定、容错回滚
"""

import json
import os
import time
import uuid
import shutil
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import threading
import copy


class CheckpointStatus(Enum):
    """检查点状态"""
    CREATED = "created"
    VALID = "valid"
    ROLLBACK = "rollback"
    EXPIRED = "expired"


class RollbackStrategy(Enum):
    """回滚策略"""
    FULL = "full"           # 完全回滚
    STEP = "step"          # 逐步回滚
    SKILL = "skill"        # 回滚到技能级别
    STABLE = "stable"      # 回滚到稳定状态


@dataclass
class Checkpoint:
    """检查点"""
    checkpoint_id: str
    task_id: str
    turn: int
    phase: str
    state_snapshot: Dict[str, Any]
    messages_snapshot: List[Dict[str, Any]]
    execution_records: List[Dict[str, Any]]
    created_at: float
    status: CheckpointStatus
    parent_checkpoint_id: Optional[str] = None
    description: str = ""


@dataclass
class RollbackPoint:
    """回滚点"""
    rollback_id: str
    checkpoint_id: str
    task_id: str
    reason: str
    created_at: float
    state_before: Optional[Dict[str, Any]] = None


@dataclass
class ExecutionFeedback:
    """执行反馈"""
    feedback_id: str
    turn: int
    success: bool
    score: float  # 0.0 - 1.0
    message: str
    suggestions: List[str] = field(default_factory=list)
    adjustments: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class CheckpointManager:
    """检查点管理器"""

    def __init__(self, storage_dir: str = "~/.living_tree_ai/checkpoints"):
        """初始化检查点管理器"""
        self.storage_dir = Path(os.path.expanduser(storage_dir))
        self.checkpoints_dir = self.storage_dir / "checkpoints"
        self.rollbacks_dir = self.storage_dir / "rollbacks"
        
        # 创建目录
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.rollbacks_dir.mkdir(parents=True, exist_ok=True)
        
        # 内存缓存
        self._checkpoint_cache: Dict[str, Checkpoint] = {}
        self._task_checkpoints: Dict[str, List[str]] = {}  # task_id -> [checkpoint_ids]
        
        # 配置
        self.max_checkpoints_per_task = 10
        self.checkpoint_interval = 5  # 每 N 轮创建检查点
        self.max_age_seconds = 3600  # 1小时后过期
        
        # 锁
        self._lock = threading.RLock()
        
        # 加载现有检查点
        self._load_checkpoints()

    def _load_checkpoints(self):
        """加载检查点"""
        for checkpoint_file in self.checkpoints_dir.glob("*.json"):
            try:
                with open(checkpoint_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                checkpoint = Checkpoint(
                    checkpoint_id=data["checkpoint_id"],
                    task_id=data["task_id"],
                    turn=data["turn"],
                    phase=data["phase"],
                    state_snapshot=data["state_snapshot"],
                    messages_snapshot=data["messages_snapshot"],
                    execution_records=data["execution_records"],
                    created_at=data["created_at"],
                    status=CheckpointStatus(data["status"]),
                    parent_checkpoint_id=data.get("parent_checkpoint_id"),
                    description=data.get("description", "")
                )
                
                self._checkpoint_cache[checkpoint.checkpoint_id] = checkpoint
                
                if checkpoint.task_id not in self._task_checkpoints:
                    self._task_checkpoints[checkpoint.task_id] = []
                self._task_checkpoints[checkpoint.task_id].append(checkpoint.checkpoint_id)
                
            except Exception as e:
                print(f"[CheckpointManager] 加载检查点失败: {e}")

    def _save_checkpoint(self, checkpoint: Checkpoint):
        """保存检查点到磁盘"""
        checkpoint_file = self.checkpoints_dir / f"{checkpoint.checkpoint_id}.json"
        
        data = {
            "checkpoint_id": checkpoint.checkpoint_id,
            "task_id": checkpoint.task_id,
            "turn": checkpoint.turn,
            "phase": checkpoint.phase,
            "state_snapshot": checkpoint.state_snapshot,
            "messages_snapshot": checkpoint.messages_snapshot,
            "execution_records": checkpoint.execution_records,
            "created_at": checkpoint.created_at,
            "status": checkpoint.status.value,
            "parent_checkpoint_id": checkpoint.parent_checkpoint_id,
            "description": checkpoint.description
        }
        
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # 更新缓存
        self._checkpoint_cache[checkpoint.checkpoint_id] = checkpoint
        
        if checkpoint.task_id not in self._task_checkpoints:
            self._task_checkpoints[checkpoint.task_id] = []
        if checkpoint.checkpoint_id not in self._task_checkpoints[checkpoint.task_id]:
            self._task_checkpoints[checkpoint.task_id].append(checkpoint.checkpoint_id)

    def create_checkpoint(
        self,
        task_id: str,
        turn: int,
        phase: str,
        state: Dict[str, Any],
        messages: List[Dict[str, Any]],
        execution_records: List[Any],
        description: str = ""
    ) -> Checkpoint:
        """
        创建检查点
        
        Args:
            task_id: 任务 ID
            turn: 当前轮次
            phase: 当前阶段
            state: 状态快照
            messages: 消息快照
            execution_records: 执行记录
            description: 描述
        
        Returns:
            Checkpoint: 检查点
        """
        with self._lock:
            # 查找父检查点
            parent_id = None
            if task_id in self._task_checkpoints and self._task_checkpoints[task_id]:
                parent_id = self._task_checkpoints[task_id][-1]
            
            # 创建检查点
            checkpoint = Checkpoint(
                checkpoint_id=str(uuid.uuid4()),
                task_id=task_id,
                turn=turn,
                phase=phase,
                state_snapshot=copy.deepcopy(state),
                messages_snapshot=copy.deepcopy(messages),
                execution_records=[
                    {
                        "id": r.id if hasattr(r, 'id') else str(r),
                        "tool_name": getattr(r, 'tool_name', ''),
                        "phase": getattr(r, 'phase', '').value if hasattr(getattr(r, 'phase', None), 'value') else '',
                        "success": getattr(r, 'success', False)
                    }
                    for r in execution_records
                ],
                created_at=time.time(),
                status=CheckpointStatus.VALID,
                parent_checkpoint_id=parent_id,
                description=description
            )
            
            self._save_checkpoint(checkpoint)
            
            # 清理旧检查点
            self._cleanup_old_checkpoints(task_id)
            
            print(f"[CheckpointManager] 创建检查点: {checkpoint.checkpoint_id} (turn={turn})")
            return checkpoint

    def _cleanup_old_checkpoints(self, task_id: str):
        """清理旧检查点"""
        if task_id not in self._task_checkpoints:
            return
        
        checkpoints = self._task_checkpoints[task_id]
        
        # 保留最新的 N 个检查点
        if len(checkpoints) > self.max_checkpoints_per_task:
            to_remove = checkpoints[:-self.max_checkpoints_per_task]
            
            for cp_id in to_remove:
                # 删除文件
                checkpoint_file = self.checkpoints_dir / f"{cp_id}.json"
                if checkpoint_file.exists():
                    checkpoint_file.unlink()
                
                # 从缓存移除
                if cp_id in self._checkpoint_cache:
                    del self._checkpoint_cache[cp_id]
            
            # 更新索引
            self._task_checkpoints[task_id] = checkpoints[-self.max_checkpoints_per_task:]

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """获取检查点"""
        return self._checkpoint_cache.get(checkpoint_id)

    def get_latest_checkpoint(self, task_id: str) -> Optional[Checkpoint]:
        """获取任务的最新检查点"""
        if task_id not in self._task_checkpoints or not self._task_checkpoints[task_id]:
            return None
        
        latest_id = self._task_checkpoints[task_id][-1]
        return self.get_checkpoint(latest_id)

    def get_task_checkpoints(self, task_id: str) -> List[Checkpoint]:
        """获取任务的所有检查点"""
        if task_id not in self._task_checkpoints:
            return []
        
        checkpoints = []
        for cp_id in self._task_checkpoints[task_id]:
            cp = self.get_checkpoint(cp_id)
            if cp:
                checkpoints.append(cp)
        
        return checkpoints

    def should_create_checkpoint(self, turn: int) -> bool:
        """判断是否应该创建检查点"""
        return turn > 0 and turn % self.checkpoint_interval == 0


class RollbackManager:
    """回滚管理器"""

    def __init__(self, checkpoint_manager: CheckpointManager):
        """初始化回滚管理器"""
        self.checkpoint_manager = checkpoint_manager
        self.rollback_history: List[RollbackPoint] = []
        self._lock = threading.RLock()

    def create_rollback_point(
        self,
        checkpoint_id: str,
        task_id: str,
        reason: str,
        state_before: Optional[Dict[str, Any]] = None
    ) -> RollbackPoint:
        """
        创建回滚点
        
        Args:
            checkpoint_id: 检查点 ID
            task_id: 任务 ID
            reason: 回滚原因
            state_before: 回滚前状态
        
        Returns:
            RollbackPoint: 回滚点
        """
        rollback = RollbackPoint(
            rollback_id=str(uuid.uuid4()),
            checkpoint_id=checkpoint_id,
            task_id=task_id,
            reason=reason,
            created_at=time.time(),
            state_before=state_before
        )
        
        self.rollback_history.append(rollback)
        
        # 保存到磁盘
        self._save_rollback(rollback)
        
        print(f"[RollbackManager] 创建回滚点: {rollback.rollback_id} - {reason}")
        return rollback

    def _save_rollback(self, rollback: RollbackPoint):
        """保存回滚点到磁盘"""
        rollback_file = self.checkpoint_manager.rollbacks_dir / f"{rollback.rollback_id}.json"
        
        data = {
            "rollback_id": rollback.rollback_id,
            "checkpoint_id": rollback.checkpoint_id,
            "task_id": rollback.task_id,
            "reason": rollback.reason,
            "created_at": rollback.created_at,
            "state_before": rollback.state_before
        }
        
        with open(rollback_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def rollback_to_checkpoint(
        self,
        checkpoint_id: str,
        reason: str
    ) -> Optional[Tuple[Checkpoint, RollbackPoint]]:
        """
        回滚到指定检查点
        
        Args:
            checkpoint_id: 检查点 ID
            reason: 回滚原因
        
        Returns:
            Optional[Tuple[Checkpoint, RollbackPoint]]: (检查点, 回滚点)
        """
        checkpoint = self.checkpoint_manager.get_checkpoint(checkpoint_id)
        if not checkpoint:
            print(f"[RollbackManager] 检查点不存在: {checkpoint_id}")
            return None
        
        # 创建回滚点
        rollback_point = self.create_rollback_point(
            checkpoint_id=checkpoint_id,
            task_id=checkpoint.task_id,
            reason=reason,
            state_before=copy.deepcopy(checkpoint.state_snapshot)
        )
        
        # 更新检查点状态
        checkpoint.status = CheckpointStatus.ROLLBACK
        self.checkpoint_manager._save_checkpoint(checkpoint)
        
        print(f"[RollbackManager] 回滚到检查点: {checkpoint_id}")
        return checkpoint, rollback_point

    def rollback_to_stable(
        self,
        task_id: str,
        reason: str
    ) -> Optional[Tuple[Checkpoint, RollbackPoint]]:
        """
        回滚到稳定状态（最后一个成功的检查点）
        
        Args:
            task_id: 任务 ID
            reason: 回滚原因
        
        Returns:
            Optional[Tuple[Checkpoint, RollbackPoint]]: (检查点, 回滚点)
        """
        checkpoints = self.checkpoint_manager.get_task_checkpoints(task_id)
        
        # 查找最后一个有效的检查点
        stable_checkpoint = None
        for cp in reversed(checkpoints):
            if cp.status == CheckpointStatus.VALID:
                stable_checkpoint = cp
                break
        
        if not stable_checkpoint:
            print(f"[RollbackManager] 未找到稳定检查点: {task_id}")
            return None
        
        return self.rollback_to_checkpoint(stable_checkpoint.checkpoint_id, reason)

    def get_rollback_history(self, task_id: Optional[str] = None) -> List[RollbackPoint]:
        """获取回滚历史"""
        if task_id:
            return [r for r in self.rollback_history if r.task_id == task_id]
        return self.rollback_history


class BidirectionalScheduler:
    """双向调度器"""

    def __init__(self):
        """初始化双向调度器"""
        self.feedback_history: List[ExecutionFeedback] = []
        self.adjustment_history: Dict[str, List[Dict]] = {}
        self._lock = threading.RLock()

    def record_feedback(
        self,
        turn: int,
        success: bool,
        score: float,
        message: str,
        suggestions: Optional[List[str]] = None,
        adjustments: Optional[Dict[str, Any]] = None
    ) -> ExecutionFeedback:
        """
        记录执行反馈
        
        Args:
            turn: 轮次
            success: 是否成功
            score: 评分 0.0-1.0
            message: 反馈消息
            suggestions: 建议
            adjustments: 调整
        
        Returns:
            ExecutionFeedback: 反馈
        """
        feedback = ExecutionFeedback(
            feedback_id=str(uuid.uuid4()),
            turn=turn,
            success=success,
            score=score,
            message=message,
            suggestions=suggestions or [],
            adjustments=adjustments or {}
        )
        
        self.feedback_history.append(feedback)
        
        # 记录调整历史
        if adjustments:
            self.adjustment_history[feedback.feedback_id] = copy.deepcopy(adjustments)
        
        print(f"[BidirectionalScheduler] 记录反馈: turn={turn}, score={score:.2f}")
        return feedback

    def should_adjust_strategy(self, window_size: int = 5) -> bool:
        """
        判断是否需要调整策略
        
        Args:
            window_size: 评估窗口大小
        
        Returns:
            bool: 是否需要调整
        """
        if len(self.feedback_history) < window_size:
            return False
        
        recent = self.feedback_history[-window_size:]
        avg_score = sum(f.score for f in recent) / len(recent)
        
        # 如果平均分低于阈值，建议调整
        return avg_score < 0.6

    def get_adjustment_suggestions(self, window_size: int = 10) -> Dict[str, Any]:
        """
        获取调整建议
        
        Args:
            window_size: 评估窗口大小
        
        Returns:
            Dict[str, Any]: 调整建议
        """
        if len(self.feedback_history) < window_size:
            return {}
        
        recent = self.feedback_history[-window_size:]
        
        # 分析失败模式
        failed = [f for f in recent if not f.success]
        successful = [f for f in recent if f.success]
        
        suggestions = {
            "should_adjust": len(failed) > len(successful) * 0.5,
            "avg_score": sum(f.score for f in recent) / len(recent),
            "failure_rate": len(failed) / len(recent),
            "common_issues": self._analyze_common_issues(failed),
            "recommended_adjustments": self._get_recommended_adjustments(recent)
        }
        
        return suggestions

    def _analyze_common_issues(self, failed_feedback: List[ExecutionFeedback]) -> List[str]:
        """分析常见问题"""
        issues = []
        
        for feedback in failed_feedback:
            if feedback.suggestions:
                issues.extend(feedback.suggestions)
        
        # 统计问题频率
        from collections import Counter
        issue_counts = Counter(issues)
        
        return [issue for issue, count in issue_counts.most_common(5)]

    def _get_recommended_adjustments(self, recent: List[ExecutionFeedback]) -> Dict[str, Any]:
        """获取推荐的调整"""
        avg_score = sum(f.score for f in recent) / len(recent)
        
        adjustments = {}
        
        # 根据评分调整参数
        if avg_score < 0.3:
            adjustments["reduce_turns"] = True
            adjustments["use_conservative_strategy"] = True
            adjustments["fallback_to_skill"] = True
        elif avg_score < 0.6:
            adjustments["increase_verification"] = True
            adjustments["add_checkpoints"] = True
        else:
            adjustments["maintain_strategy"] = True
        
        return adjustments

    def get_feedback_trend(self, window_size: int = 20) -> str:
        """
        获取反馈趋势
        
        Args:
            window_size: 窗口大小
        
        Returns:
            str: 趋势描述
        """
        if len(self.feedback_history) < window_size:
            return "insufficient_data"
        
        recent = self.feedback_history[-window_size:]
        scores = [f.score for f in recent]
        
        # 简单线性回归
        n = len(scores)
        x = list(range(n))
        y = scores
        
        x_mean = sum(x) / n
        y_mean = sum(y) / n
        
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            slope = 0
        else:
            slope = numerator / denominator
        
        if slope > 0.05:
            return "improving"
        elif slope < -0.05:
            return "declining"
        else:
            return "stable"


class DynamicTerminator:
    """动态终止判定器"""

    def __init__(self, config: Optional[Dict] = None):
        """初始化终止判定器"""
        self.config = config or {}
        
        # 配置参数
        self.max_turns = self.config.get("max_turns", 50)
        self.min_success_rate = self.config.get("min_success_rate", 0.7)
        self.max_consecutive_failures = self.config.get("max_consecutive_failures", 3)
        self.score_threshold = self.config.get("score_threshold", 0.5)
        self.stagnation_threshold = self.config.get("stagnation_threshold", 5)
        
        # 状态
        self._consecutive_failures = 0
        self._stagnation_count = 0
        self._last_best_score = 0.0
        self._termination_reasons: List[str] = []

    def should_terminate(
        self,
        turn: int,
        success_count: int,
        total_count: int,
        current_score: float,
        feedback_trend: str
    ) -> Tuple[bool, str]:
        """
        判断是否应该终止
        
        Args:
            turn: 当前轮次
            success_count: 成功次数
            total_count: 总次数
            current_score: 当前评分
            feedback_trend: 反馈趋势
        
        Returns:
            Tuple[bool, str]: (是否终止, 原因)
        """
        # 超时
        if turn >= self.max_turns:
            return True, f"达到最大轮次 {self.max_turns}"
        
        # 计算成功率
        success_rate = success_count / total_count if total_count > 0 else 0
        
        # 成功率过低
        if total_count >= 3 and success_rate < self.min_success_rate:
            return True, f"成功率过低 ({success_rate:.2%})"
        
        # 连续失败
        if self._consecutive_failures >= self.max_consecutive_failures:
            return True, f"连续失败 {self._consecutive_failures} 次"
        
        # 评分过低
        if current_score < self.score_threshold and total_count >= 3:
            return True, f"评分过低 ({current_score:.2f})"
        
        # 停滞检测
        if current_score <= self._last_best_score:
            self._stagnation_count += 1
        else:
            self._stagnation_count = 0
            self._last_best_score = current_score
        
        if self._stagnation_count >= self.stagnation_threshold:
            return True, f"性能停滞 {self._stagnation_count} 轮"
        
        # 趋势下降
        if feedback_trend == "declining" and self._stagnation_count >= 2:
            return True, "性能持续下降"
        
        return False, ""

    def record_outcome(self, success: bool):
        """记录结果"""
        if success:
            self._consecutive_failures = 0
        else:
            self._consecutive_failures += 1

    def reset(self):
        """重置状态"""
        self._consecutive_failures = 0
        self._stagnation_count = 0
        self._last_best_score = 0.0
        self._termination_reasons.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "consecutive_failures": self._consecutive_failures,
            "stagnation_count": self._stagnation_count,
            "last_best_score": self._last_best_score,
            "termination_reasons": self._termination_reasons
        }


class IncrementalLearning:
    """增量学习优化器"""

    def __init__(self, checkpoint_manager: CheckpointManager):
        """初始化增量学习"""
        self.checkpoint_manager = checkpoint_manager
        self.learned_patterns: Dict[str, List[Dict]] = {}
        self.optimization_history: List[Dict] = []

    def analyze_execution_pattern(
        self,
        execution_records: List[Any]
    ) -> Dict[str, Any]:
        """
        分析执行模式
        
        Args:
            execution_records: 执行记录
        
        Returns:
            Dict[str, Any]: 分析结果
        """
        if not execution_records:
            return {}
        
        # 统计工具使用频率
        tool_usage = {}
        success_by_tool = {}
        
        for record in execution_records:
            tool_name = getattr(record, 'tool_name', 'unknown')
            
            tool_usage[tool_name] = tool_usage.get(tool_name, 0) + 1
            
            if tool_name not in success_by_tool:
                success_by_tool[tool_name] = {"success": 0, "failure": 0}
            
            if getattr(record, 'success', False):
                success_by_tool[tool_name]["success"] += 1
            else:
                success_by_tool[tool_name]["failure"] += 1
        
        # 分析阶段转换
        phase_sequence = []
        prev_phase = None
        for record in execution_records:
            phase = getattr(record, 'phase', None)
            if phase and hasattr(phase, 'value'):
                phase = phase.value
            if phase != prev_phase:
                phase_sequence.append(phase)
                prev_phase = phase
        
        analysis = {
            "total_steps": len(execution_records),
            "tool_usage": tool_usage,
            "success_by_tool": success_by_tool,
            "phase_sequence": phase_sequence,
            "most_successful_tools": self._get_most_successful_tools(success_by_tool),
            "recommended_tool_order": self._get_recommended_tool_order(tool_usage, success_by_tool)
        }
        
        return analysis

    def _get_most_successful_tools(self, success_by_tool: Dict) -> List[str]:
        """获取最成功的工具"""
        tool_scores = []
        for tool, stats in success_by_tool.items():
            total = stats["success"] + stats["failure"]
            if total > 0:
                score = stats["success"] / total
                tool_scores.append((tool, score))
        
        tool_scores.sort(key=lambda x: x[1], reverse=True)
        return [tool for tool, score in tool_scores if score >= 0.7]

    def _get_recommended_tool_order(self, tool_usage: Dict, success_by_tool: Dict) -> List[str]:
        """获取推荐的工具顺序"""
        tool_priority = []
        
        for tool, usage_count in tool_usage.items():
            stats = success_by_tool.get(tool, {"success": 0, "failure": 0})
            total = stats["success"] + stats["failure"]
            
            if total > 0:
                success_rate = stats["success"] / total
                # 优先级 = 使用频率 * 成功率
                priority = usage_count * success_rate
                tool_priority.append((tool, priority))
        
        tool_priority.sort(key=lambda x: x[1], reverse=True)
        return [tool for tool, _ in tool_priority]

    def distill_knowledge(
        self,
        task_id: str,
        execution_records: List[Any]
    ) -> Dict[str, Any]:
        """
        提炼知识
        
        Args:
            task_id: 任务 ID
            execution_records: 执行记录
        
        Returns:
            Dict[str, Any]: 提炼的知识
        """
        analysis = self.analyze_execution_pattern(execution_records)
        
        knowledge = {
            "task_id": task_id,
            "timestamp": time.time(),
            "optimal_sequence": analysis.get("recommended_tool_order", []),
            "effective_tools": analysis.get("most_successful_tools", []),
            "lessons_learned": self._extract_lessons(execution_records),
            "anti_patterns": self._extract_anti_patterns(execution_records)
        }
        
        # 保存到模式库
        if task_id not in self.learned_patterns:
            self.learned_patterns[task_id] = []
        self.learned_patterns[task_id].append(knowledge)
        
        self.optimization_history.append(knowledge)
        
        print(f"[IncrementalLearning] 提炼知识: {len(knowledge.get('effective_tools', []))} 个有效工具")
        return knowledge

    def _extract_lessons(self, execution_records: List[Any]) -> List[str]:
        """提取经验教训"""
        lessons = []
        
        successful_records = [r for r in execution_records if getattr(r, 'success', False)]
        if successful_records:
            lessons.append(f"成功完成 {len(successful_records)} 个步骤")
        
        # 分析成功的工具组合
        if len(successful_records) >= 2:
            lessons.append("多步骤协作模式有效")
        
        return lessons

    def _extract_anti_patterns(self, execution_records: List[Any]) -> List[str]:
        """提取反模式"""
        anti_patterns = []
        
        failed_records = [r for r in execution_records if not getattr(r, 'success', True)]
        for record in failed_records:
            tool_name = getattr(record, 'tool_name', 'unknown')
            error = getattr(record, 'error_msg', 'Unknown error')
            anti_patterns.append(f"{tool_name}: {error}")
        
        return anti_patterns[:5]  # 最多5个

    def get_optimization_suggestions(self, task_id: str) -> Dict[str, Any]:
        """获取优化建议"""
        if task_id not in self.learned_patterns or not self.learned_patterns[task_id]:
            return {}
        
        patterns = self.learned_patterns[task_id]
        latest = patterns[-1]
        
        suggestions = {
            "optimal_sequence": latest.get("optimal_sequence", []),
            "effective_tools": latest.get("effective_tools", []),
            "avoid_tools": [tool for tool in latest.get("lessons_learned", []) if "失败" in tool]
        }
        
        return suggestions


class AmphiLoopEngine:
    """
    AmphiLoop 核心引擎
    
    整合双向循环调度、状态持久化、动态终止判定、容错回滚与增量学习
    """

    def __init__(
        self,
        storage_dir: str = "~/.living_tree_ai/amphiloop"
    ):
        """初始化 AmphiLoop 引擎"""
        self.storage_dir = Path(os.path.expanduser(storage_dir))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化子系统
        self.checkpoint_manager = CheckpointManager(str(self.storage_dir / "checkpoints"))
        self.rollback_manager = RollbackManager(self.checkpoint_manager)
        self.bidirectional_scheduler = BidirectionalScheduler()
        self.dynamic_terminator = DynamicTerminator()
        self.incremental_learning = IncrementalLearning(self.checkpoint_manager)
        
        # 状态
        self.current_task_id: Optional[str] = None
        self.is_running = False

    def on_turn_start(self, turn: int, phase: str) -> Optional[Checkpoint]:
        """轮次开始回调"""
        if not self.current_task_id:
            return None
        
        # 检查是否需要创建检查点
        if self.checkpoint_manager.should_create_checkpoint(turn):
            return self.checkpoint_manager.create_checkpoint(
                task_id=self.current_task_id,
                turn=turn,
                phase=phase,
                state={},  # 由调用者填充
                messages=[],  # 由调用者填充
                execution_records=[]  # 由调用者填充
            )
        
        return None

    def on_turn_end(
        self,
        turn: int,
        success: bool,
        score: float,
        message: str
    ) -> ExecutionFeedback:
        """轮次结束回调"""
        # 记录反馈
        feedback = self.bidirectional_scheduler.record_feedback(
            turn=turn,
            success=success,
            score=score,
            message=message
        )
        
        # 更新终止判定器
        self.dynamic_terminator.record_outcome(success)
        
        return feedback

    def check_termination(
        self,
        turn: int,
        success_count: int,
        total_count: int,
        current_score: float
    ) -> Tuple[bool, str]:
        """检查是否应该终止"""
        trend = self.bidirectional_scheduler.get_feedback_trend()
        
        return self.dynamic_terminator.should_terminate(
            turn=turn,
            success_count=success_count,
            total_count=total_count,
            current_score=current_score,
            feedback_trend=trend
        )

    def handle_failure(self, reason: str) -> Optional[Checkpoint]:
        """处理失败"""
        if not self.current_task_id:
            return None
        
        # 尝试回滚到稳定状态
        result = self.rollback_manager.rollback_to_stable(
            task_id=self.current_task_id,
            reason=reason
        )
        
        if result:
            return result[0]
        
        return None

    def distill_and_optimize(self, task_id: str, execution_records: List[Any]) -> Dict:
        """提炼和优化"""
        return self.incremental_learning.distill_knowledge(task_id, execution_records)


# 全局实例
_global_engine: Optional[AmphiLoopEngine] = None


def get_amphiloop_engine() -> AmphiLoopEngine:
    """获取 AmphiLoop 引擎"""
    global _global_engine
    if _global_engine is None:
        _global_engine = AmphiLoopEngine()
    return _global_engine
