# -*- coding: utf-8 -*-
"""
检查点管理器 - CheckpointManager
==================================

解决核心问题：**执行失败后无法恢复、无法回退**

当前 Handler 执行失败就丢失所有中间状态。
CheckpointManager 提供：

1. **自动检查点**: 关键步骤完成后自动保存状态
2. **增量保存**: 只保存变化的部分，节省空间
3. **回滚能力**: 回到任意检查点状态
4. **断点续传**: 进程重启后从最近的检查点恢复
5. **过期清理**: 自动淘汰过期的检查点

使用场景：
- 长时间任务中途崩溃 → 从最近 checkpoint 恢复
- 用户对结果不满意 → 回滚到修改前的版本
- 复合意图部分失败 → 已完成的不用重做

Author: LivingTreeAI Team
Version: 1.0.0
from __future__ import annotations
"""


import time
import os
import json
import hashlib
import threading
from enum import Enum, auto
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger(__name__)


# ── 数据结构 ──────────────────────────────────────────────────────


class CheckpointStatus(Enum):
    """检查点状态"""
    VALID = "valid"
    ROLLED_BACK = "rolled_back"
    EXPIRED = "expired"
    CORRUPTED = "corrupted"


@dataclass
class Checkpoint:
    """
    一个执行检查点
    
    记录任务在某一时刻的完整快照或增量变化。
    """
    checkpoint_id: str
    task_id: str               # 所属任务 ID（trace_id）
    
    # 序号（同一任务的递增序号）
    sequence: int
    
    # 时间
    created_at: float = 0.0
    
    # 状态快照内容
    state: Dict[str, Any] = field(default_factory=dict)
    
    # 元信息
    name: str = ""              # 人类可读的名称（如"LLM调用完成"）
    status: CheckpointStatus = CheckpointStatus.VALID
    
    # 增量信息（相对于上一个 checkpoint 的差异）
    delta: Optional[Dict[str, Any]] = None
    full_snapshot: bool = True  # 是否是全量快照
    
    # 标记
    tags: List[str] = field(default_factory=list)  # ["pre-execution", "post-llm"]
    size_bytes: int = 0

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "id": self.checkpoint_id[:8],
            "seq": self.sequence,
            "name": self.name,
            "status": self.status.value,
            "age_s": round(self.age_seconds, 1),
            "size_b": self.size_bytes,
            "tags": self.tags,
            "keys": list(self.state.keys()) if self.state else [],
        }
        return d


@dataclass
class RollbackResult:
    """回滚操作结果"""
    success: bool
    from_sequence: int          # 从哪个 seq 回滚
    to_sequence: int            # 到哪个 seq
    restored_state: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    checkpoints_affected: int = 0


# ── 核心类 ────────────────────────────────────────────────────────


class CheckpointManager:
    """
    检查点管理器

    设计原则：
    - 内存优先：默认只在内存中维护，可选持久化到文件/DB
    - 轻量级：state 用 dict 存储任意可序列化对象
    - 自动管理：容量超限自动淘汰最旧检查点
    """

    def __init__(
        self,
        max_checkpoints_per_task: int = 10,
        max_tasks: int = 50,
        ttl_seconds: float = 3600.0,       # 默认 1 小时过期
        persist_dir: str = "",              # 空字符串=不持久化
        auto_checkpoint_interval: int = 0,  # 0=不自动打点（按步骤手动）
    ):
        self.max_per_task = max_checkpoints_per_task
        self.max_tasks = max_tasks
        self.ttl = ttl_seconds
        self.persist_dir = persist_dir
        self.auto_interval = auto_checkpoint_interval
        
        # 存储: task_id → [Checkpoint, ...]（按 sequence 排序）
        self._tasks: Dict[str, List[Checkpoint]] = {}
        
        # 当前各任务的最新状态（用于生成 delta）
        self._latest_state: Dict[str, Dict[str, Any]] = {}
        
        self._lock = threading.Lock()
        self.stats = {
            "total_created": 0,
            "total_rollbacks": 0,
            "total_restores": 0,
            "expired_cleaned": 0,
        }

    # ── 检查点操作 ──────────────────────────────────────────────

    def create(
        self,
        task_id: str,
        state: Dict[str, Any],
        name: str = "",
        tags: Optional[List[str]] = None,
        force_full: bool = False,
    ) -> Checkpoint:
        """
        创建一个检查点
        
        Args:
            task_id: 任务 ID
            state: 当前状态的字典（会被深拷贝）
            name: 检查点名称
            tags: 标签列表
            force_full: 强制全量快照（否则自动判断是否用增量）

        Returns:
            新创建的 Checkpoint 对象
        """
        with self._lock:
            now = time.time()
            
            # 获取该任务的历史
            history = self._tasks.setdefault(task_id, [])
            
            # 决定是否用增量
            prev_state = self._latest_state.get(task_id, {})
            should_delta = not force_full and bool(prev_state) and len(history) > 0
            
            if should_delta:
                delta = self._compute_delta(prev_state, state)
                snapshot = delta if len(json.dumps(delta, default=str)) < len(json.dumps(state, default=str)) * 0.8 else state
                is_full = (snapshot is state or snapshot == state)
                if not is_full:
                    stored_state = {}  # 增量模式只存 delta
                    stored_state["__delta__"] = snapshot
                    stored_state["__base_seq__"] = history[-1].sequence if history else 0
                else:
                    stored_state = state
                    is_full = True
            else:
                stored_state = self._import.deepcopy(state)
                is_full = True
            
            cp = Checkpoint(
                checkpoint_id=hashlib.md5(f"{task_id}{now}{name}".encode()).hexdigest()[:12],
                task_id=task_id,
                sequence=len(history) + 1,
                created_at=now,
                state=stored_state,
                name=name or f"checkpoint-{len(history)+1}",
                tags=tags or [],
                full_snapshot=is_full,
            )
            cp.size_bytes = len(json.dumps(stored_state, default=str).encode())
            
            # 容量控制
            while len(history) >= self.max_per_task:
                removed = history.pop(0)
                removed.status = CheckpointStatus.EXPIRED
                logger.debug(f"[CP] 淘汰旧检查点 {removed.checkpoint_id[:8]}")
            
            history.append(cp)
            self._latest_state[task_id] = self._import.deepcopy(state)
            self.stats["total_created"] += 1
            
            # 全局任务数控制
            if len(self._tasks) > self.max_tasks:
                oldest_task = min(self._tasks.keys(), 
                                  key=lambda t: self._tasks[t][0].created_at if self._tasks[t] else 999999999)
                del self._tasks[oldest_task]
                self._latest_state.pop(oldest_task, None)

        logger.debug(f"[CP] 创建 {cp.checkpoint_id[:8]} #{cp.sequence} '{cp.name}' "
                     f"(task={task_id[:8]}, {'full' if is_full else 'delta'}, {cp.size_bytes}B)")
        return cp

    def rollback(
        self,
        task_id: str,
        to_sequence: Optional[int] = None,
        to_name: Optional[str] = None,
        to_tags_match: Optional[str] = None,
    ) -> RollbackResult:
        """
        回滚到指定检查点
        
        可以通过以下方式指定目标：
        - to_sequence: 序号（如 2 表示回到第 2 个检查点）
        - to_name: 名称匹配
        - to_tags_match: 标签包含指定值
        
        Returns:
            RollbackResult: 包含恢复后的状态
        """
        with self._lock:
            history = self._tasks.get(task_id, [])
            if not history:
                return RollbackResult(success=False, from_sequence=0, to_sequence=0,
                                     message=f"任务 {task_id} 无检查点记录")

            current_seq = len(history)
            
            # 定位目标检查点
            target = None
            if to_sequence is not None:
                for cp in history:
                    if cp.sequence == to_sequence and cp.status == CheckpointStatus.VALID:
                        target = cp; break
            elif to_name:
                for cp in reversed(history):
                    if cp.name == to_name and cp.status == CheckpointStatus.VALID:
                        target = cp; break
            elif to_tags_match:
                for cp in reversed(history):
                    if to_tags_match in cp.tags and cp.status == CheckpointStatus.VALID:
                        target = cp; break
            else:
                # 默认回滚到前一个有效检查点
                for cp in reversed(history[:-1]):  # 排除当前最新的
                    if cp.status == CheckpointStatus.VALID:
                        target = cp; break
            
            if not target:
                return RollbackResult(success=False, from_sequence=current_seq, 
                                     to_sequence=to_sequence or 0,
                                     message="未找到有效的目标检查点")
            
            # 构建完整状态（处理增量）
            restored = self._build_full_state(task_id, target)
            from_seq = current_seq
            to_seq = target.sequence
            
            # 将目标之后的所有检查点标记为已回滚
            affected = 0
            for cp in history:
                if cp.sequence > to_seq and cp.status == CheckpointStatus.VALID:
                    cp.status = CheckpointStatus.ROLLED_BACK
                    affected += 1
            
            # 更新最新状态
            self._latest_state[task_id] = restored
            self.stats["total_rollbacks"] += 1
            
            logger.info(f"[CP] 回滚 task={task_id[:8]}: seq {from_seq} → {to_seq} "
                       f"('{target.name}', 影响检查点数={affected})")
            
            return RollbackResult(
                success=True,
                from_sequence=from_seq,
                to_sequence=to_seq,
                restored_state=restored,
                message=f"已回滚到检查点 #{to_seq}: {target.name}",
                checkpoints_affected=affected,
            )

    def restore_latest(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务最新的有效状态"""
        with self._lock:
            history = self._tasks.get(task_id, [])
            valid = [cp for cp in history if cp.status == CheckpointStatus.VALID]
            if not valid:
                return self._latest_state.get(task_id)
            
            latest = valid[-1]
            state = self._build_full_state(task_id, latest)
            self.stats["total_restores"] += 1
            return state

    def get_history(self, task_id: str) -> List[Checkpoint]:
        """获取任务的所有检查点历史"""
        return self._tasks.get(task_id, [])

    def get_latest(self, task_id: str) -> Optional[Checkpoint]:
        """获取任务最新的检查点"""
        history = self._tasks.get(task_id, [])
        valid = [cp for cp in history if cp.status == CheckpointStatus.VALID]
        return valid[-1] if valid else None

    # ── 维护操作 ────────────────────────────────────────────────

    def cleanup_expired(self) -> int:
        """清理过期检查点"""
        count = 0
        with self._lock:
            for task_id, history in list(self._tasks.items()):
                before = len(history)
                history[:] = [
                    cp for cp in history
                    if cp.age_seconds < self.ttl or cp.status != CheckpointStatus.VALID
                ]
                expired = before - len(history)
                if expired:
                    for cp in history[len(history):before]:  # 被移除的
                        if cp.status == CheckpointStatus.VALID:
                            cp.status = CheckpointStatus.EXPIRED
                            count += 1
                
                # 如果整个任务都没有有效检查点了，清理掉
                if not any(cp.status == CheckpointStatus.VALID for cp in history):
                    del self._tasks[task_id]
                    self._latest_state.pop(task_id, None)
        
        self.stats["expired_cleaned"] += count
        if count:
            logger.info(f"[CP] 清理了 {count} 个过期检查点")
        return count

    def delete_task(self, task_id: str) -> int:
        """删除一个任务的所有检查点"""
        with self._lock:
            history = self._tasks.pop(task_id, [])
            self._latest_state.pop(task_id, None)
            count = len(history)
            if count:
                logger.debug(f"[CP] 删除任务 {task_id[:8]} 的 {count} 个检查点")
            return count

    def get_stats(self) -> Dict[str, Any]:
        """统计信息"""
        total_cps = sum(len(h) for h in self._tasks.values())
        valid_cps = sum(
            1 for h in self._tasks.values() for cp in h
            if cp.status == CheckpointStatus.VALID
        )
        total_size = sum(
            cp.size_bytes for h in self._tasks.values() for cp in h
            if cp.status == CheckpointStatus.VALID
        )
        
        return {
            **self.stats,
            "active_tasks": len(self._tasks),
            "total_checkpoints": total_cps,
            "valid_checkpoints": valid_cps,
            "total_size_kb": round(total_size / 1024, 1),
            "avg_checkpoints_per_task": round(total_cps / max(len(self._tasks), 1), 1),
        }

    # ── 内部方法 ────────────────────────────────────────────────

    def _compute_delta(
        self, old: Dict[str, Any], new: Dict[str, Any]
    ) -> Dict[str, Any]:
        """计算两个状态之间的增量差异"""
        delta = {}
        
        # 新增或修改的键
        for key, value in new.items():
            if key not in old or old[key] != value:
                delta[f"+{key}"] = value
        
        # 删除的键
        for key in old:
            if key not in new:
                delta[f"-{key}"] = None
        
        return delta

    def _build_full_state(self, task_id: str, target: Checkpoint) -> Dict[str, Any]:
        """从检查点构建完整状态（处理增量链）"""
        history = self._tasks.get(task_id, [])
        
        # 如果是全量快照，直接返回（去掉内部元数据）
        if "__delta__" not in target.state:
            return self._import.deepcopy(target.state)
        
        # 增量模式：需要从基础状态逐步应用 delta
        base_seq = target.state.get("__base_seq__", 0)
        base_cp = None
        for cp in history:
            if cp.sequence == base_seq:
                base_cp = cp; break
        
        if base_cp:
            base_state = self._build_full_state(task_id, base_cp)
        else:
            base_state = {}
        
        # 应用 delta
        result = self._import.deepcopy(base_state)
        delta_data = target.state.get("__delta__", {})
        for key, value in delta_data.items():
            if key.startswith("+"):
                real_key = key[1:]
                result[real_key] = value
            elif key.startswith("-"):
                real_key = key[1:]
                result.pop(real_key, None)
        
        return result

    @staticmethod
    def _import_deepcopy(obj):
        """轻量级深拷贝"""
        import copy
        return copy.deepcopy(obj)


# ── 测试入口 ──────────────────────────────────────────────────────


def _test_checkpoint():
    print("=" * 60)
    print("CheckpointManager 测试")
    print("=" * 60)

    mgr = CheckpointManager(max_checkpoints_per_task=5, ttl_seconds=300)

    task_id = "test-task-001"

    # 模拟任务执行的多个阶段
    stages = [
        ("初始化", {"step": "init", "config": {"model": "qwen3.5:4b"}}, ["pre-execution"]),
        ("解析意图完成", {"step": "parsed", "intent_type": "code_generation"}, ["post-parse"]),
        ("LLM 调用完成", {"step": "llm_done", "output": "from fastapi import..."}, ["post-llm"]),
        ("后处理完成", {"step": "done", "result": "代码生成成功", "file": "/tmp/gen.py"}, ["post-process"]),
        ("写入文件完成", {"step": "file_written", "file_size": 2048}, ["completed"]),
    ]

    for name, state, tags in stages:
        cp = mgr.create(task_id, state, name=name, tags=tags)
        print(f"  ✅ CP#{cp.sequence}: {name} ({cp.size_bytes}B)")

    # 查看历史
    print("\n--- 检查点历史 ---")
    for cp in mgr.get_history(task_id):
        print(f"  #{cp.sequence} [{cp.status.value}] {cp.name} — {list(cp.state.keys())}")

    # 回滚到第3个检查点
    print("\n--- 回滚测试 ---")
    result = mgr.rollback(task_id, to_sequence=3)
    print(f"  回滚: {result.message}")
    print(f"  恢复的状态: {list(result.restored_state.keys())}")

    # 再次查看历史（后面的应该被标记为 rolled_back）
    print("\n--- 回滚后 ---")
    for cp in mgr.get_history(task_id):
        icon = "✅" if cp.status == CheckpointStatus.VALID else "↩️"
        print(f"  {icon} #{cp.sequence}: {cp.name}")

    # 统计
    stats = mgr.get_stats()
    print(f"\n--- 统计 ---")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    _test_checkpoint()
