# -*- coding: utf-8 -*-
"""
意图追踪器 - IntentTracker
===========================

在 IntentStateMachine 的基础上，提供更高层次的**意图生命周期管理**：

1. **意图链追踪**: 记录同一目标从提出到完成的全路径
2. **中断/恢复**: 用户打断当前任务后可以恢复
3. **分支检测**: 同一目标的多个修改方向（如"方案A vs 方案B"）
4. **意图统计**: 聚合分析用户行为模式
5. **回溯能力**: 任意时刻查看"我们是怎么走到这里的"

与 IntentStateMachine 的关系：
- SM 管理单轮状态（State Machine）
- Tracker 管理跨轮次的目标（Goal Tracking）
- 两者配合：SM.process() → Tracker.track()

Author: LivingTreeAI Team
Version: 1.0.0
"""

from __future__ import annotations

import time
import uuid
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Iterator

from .intent_types import Intent, IntentType

logger = logging.getLogger(__name__)


# ── 数据结构 ──────────────────────────────────────────────────────


class GoalStatus(Enum):
    """目标状态"""
    ACTIVE = auto()           # 进行中
    PAUSED = auto()           # 暂停（被打断）
    COMPLETED = auto()        # 已完成
    ABANDONED = auto()        # 已放弃
    BLOCKED = auto()          # 被阻塞（依赖其他目标）


@dataclass
class GoalNode:
    """
    目标节点 — 追踪一个完整意图的生命周期

    一个 Goal 可以跨多轮对话存在，记录：
    - 提出时间、最后活跃时间
    - 意图演变历史（如"写接口"→"改接口"→"加缓存"）
    - 关联的执行结果
    - 与其他 Goal 的关系（父/子/兄弟）
    """
    goal_id: str
    root_intent: Intent          # 初始意图
    current_intent: Intent       # 最新意图（可能已演变）

    # 时间线
    created_at: float = 0.0
    updated_at: float = 0.0
    completed_at: float = 0.0

    # 状态
    status: GoalStatus = GoalStatus.ACTIVE
    priority: int = 0            # 数字越小优先级越高

    # 历史轨迹
    intent_history: List[Dict[str, Any]] = field(default_factory=list)
    turn_ids: List[int] = field(default_factory=list)

    # 结果聚合
    results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    # 关系
    parent_id: Optional[str] = None
    child_ids: List[str] = field(default_factory=list)
    sibling_id: Optional[str] = None   # 分支目标

    # 元数据
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        now = time.time()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def add_turn(self, turn_id: int, intent: Intent):
        """添加一轮对话"""
        self.turn_ids.append(turn_id)
        self.intent_history.append({
            "turn": turn_id,
            "type": intent.intent_type.value,
            "target": intent.target or "",
            "action": intent.action or "",
            "confidence": intent.confidence,
            "timestamp": time.time(),
        })
        self.current_intent = intent
        self.updated_at = time.time()

    def complete(self, summary: str = ""):
        """标记完成"""
        self.status = GoalStatus.COMPLETED
        self.completed_at = time.time()
        self.results.append({"summary": summary, "at": self.completed_at})

    def pause(self, reason: str = ""):
        """暂停"""
        self.status = GoalStatus.PAUSED
        self.metadata["pause_reason"] = reason

    def resume(self):
        """恢复"""
        self.status = GoalStatus.ACTIVE
        self.metadata.pop("pause_reason", None)
        self.updated_at = time.time()

    def abandon(self, reason: str = ""):
        """放弃"""
        self.status = GoalStatus.ABANDONED
        self.metadata["abandon_reason"] = reason

    @property
    def duration(self) -> float:
        """持续时间"""
        end = self.completed_at or self.updated_at
        return end - self.created_at

    @property
    def turn_count(self) -> int:
        return len(self.turn_ids)

    @property
    def intent_evolution(self) -> List[str]:
        """意图类型演变序列"""
        return [h["type"] for h in self.intent_history]

    def to_summary(self) -> Dict[str, Any]:
        return {
            "id": self.goal_id[:8],
            "target": self.root_intent.target or self.current_intent.action or "未命名",
            "status": self.status.name,
            "turns": self.turn_count,
            "duration_s": round(self.duration, 1),
            "evolution": " → ".join(self.intent_evolution[:5]),
            "tags": self.tags,
        }


# ── 核心类 ────────────────────────────────────────────────────────


class IntentTracker:
    """
    意图追踪器

    管理 GoalNode 集合，提供：
    - 目标创建 / 更新 / 完成 / 放弃
    - 当前活跃目标查询
    - 意图演变分析
    - 分支合并建议
    """

    def __init__(self, max_goals: int = 50):
        self._goals: Dict[str, GoalNode] = {}
        self.max_goals = max_goals
        self.stats = {
            "total_created": 0,
            "total_completed": 0,
            "total_abandoned": 0,
            "branch_count": 0,
        }

    # ── 核心操作 ────────────────────────────────────────────────

    def track(
        self,
        intent: Intent,
        turn_id: int,
        session_state: str = "ACTIVE",
        response_summary: str = "",
    ) -> GoalNode:
        """
        追踪一轮意图

        自动匹配已有 Goal 或创建新 Goal。

        Args:
            intent: 解析后的意图
            turn_id: 轮次 ID（来自 StateMachine）
            session_state: 会话状态（来自 StateMachine）
            response_summary: 执行结果摘要

        Returns:
            GoalNode: 匹配或新建的目标节点
        """
        # 尝试匹配活跃的 Goal
        matched_goal = self._find_matching_goal(intent, session_state)

        if matched_goal:
            # 更新已有 Goal
            matched_goal.add_turn(turn_id, intent)
            if response_summary:
                matched_goal.results.append({"turn": turn_id, "summary": response_summary})
                # 如果是问答类，直接完成
                if intent.intent_type in (
                    IntentType.KNOWLEDGE_QUERY,
                    IntentType.CONCEPT_EXPLANATION,
                    IntentType.CODE_EXPLANATION,
                ):
                    matched_goal.complete(response_summary)
            logger.debug(f"[Tracker] 更新 Goal {matched_goal.goal_id[:8]} → {intent.intent_type.value}")
            return matched_goal

        # 创建新 Goal
        goal = self._create_goal(intent, turn_id)
        if response_summary:
            goal.complete(response_summary)
        logger.debug(f"[Tracker] 创建 Goal {goal.goal_id[:8]} ({intent.intent_type.value})")
        return goal

    def complete_goal(self, goal_id: str, summary: str = "") -> Optional[GoalNode]:
        """完成一个目标"""
        goal = self._goals.get(goal_id)
        if goal:
            goal.complete(summary)
            self.stats["total_completed"] += 1
        return goal

    def pause_goal(self, goal_id: str, reason: str = "") -> Optional[GoalNode]:
        """暂停一个目标"""
        goal = self._goals.get(goal_id)
        if goal:
            goal.pause(reason)
        return goal

    def resume_goal(self, goal_id: str) -> Optional[GoalNode]:
        """恢复一个暂停的目标"""
        goal = self._goals.get(goal_id)
        if goal and goal.status == GoalStatus.PAUSED:
            goal.resume()
        return goal

    def abandon_goal(self, goal_id: str, reason: str = "") -> Optional[GoalNode]:
        """放弃一个目标"""
        goal = self._goals.get(goal_id)
        if goal:
            goal.abandon(reason)
            self.stats["total_abandoned"] += 1
        return goal

    def branch_goal(
        self,
        parent_goal_id: str,
        new_intent: Intent,
        turn_id: int,
    ) -> Optional[GoalNode]:
        """
        从现有目标分支出新目标
        
        场景：用户说"换个思路，用 Redis 做缓存"
        """
        parent = self._goals.get(parent_goal_id)
        if not parent:
            return None

        new_goal = self._create_goal(new_intent, turn_id)
        new_goal.parent_id = parent_goal_id
        parent.child_ids.append(new_goal.goal_id)
        new_goal.sibling_id = None  # 可扩展为多分支
        new_goal.tags.append(f"branch-of-{parent.goal_id[:6]}")

        self.stats["branch_count"] += 1
        logger.info(f"[Tracker] 分支: {parent.goal_id[:8]} → {new_goal.goal_id[:8]}")
        return new_goal

    # ── 查询接口 ────────────────────────────────────────────────

    def get_active_goals(self) -> List[GoalNode]:
        """获取所有活跃目标（按更新时间排序）"""
        active = [g for g in self._goals.values() if g.status == GoalStatus.ACTIVE]
        active.sort(key=lambda g: g.updated_at, reverse=True)
        return active

    def get_recently_completed(self, limit: int = 5) -> List[GoalNode]:
        """最近完成的目标"""
        completed = [
            g for g in self._goals.values()
            if g.status == GoalStatus.COMPLETED
        ]
        completed.sort(key=lambda g: g.completed_at, reverse=True)
        return completed[:limit]

    def get_goal_chain(self, goal_id: str) -> List[GoalNode]:
        """获取目标的完整链条（含父子）"""
        chain = []
        current = self._goals.get(goal_id)
        while current:
            chain.append(current)
            current = self._goals.get(current.parent_id) if current.parent_id else None
        return list(reversed(chain))  # 根→叶

    def get_goal_tree(self) -> List[Dict[str, Any]]:
        """获取目标树（用于可视化）"""
        roots = [g for g in self._goals.values() if not g.parent_id]
        result = []
        for r in roots:
            result.append(self._build_node(r))
        return result

    def find_by_target(self, keyword: str) -> List[GoalNode]:
        """按关键词搜索目标"""
        kw_lower = keyword.lower()
        matches = []
        for g in self._goals.values():
            target_str = (g.root_intent.target + g.current_intent.target).lower()
            action_str = g.current_intent.action.lower()
            if kw_lower in target_str or kw_lower in action_str:
                matches.append(g)
        return sorted(matches, key=lambda g: g.updated_at, reverse=True)

    def get_stats(self) -> Dict[str, Any]:
        """统计信息"""
        by_status = {}
        for s in GoalStatus:
            count = sum(1 for g in self._goals.values() if g.status == s)
            if count:
                by_status[s.name] = count

        return {
            **self.stats,
            "total_goals": len(self._goals),
            "by_status": by_status,
            "active_count": len(self.get_active_goals()),
            "avg_turns_per_goal": (
                sum(g.turn_count for g in self._goals.values()) / max(len(self._goals), 1)
            ),
        }

    def to_report(self) -> str:
        """生成人类可读的报告"""
        lines = ["## 意图追踪报告\n"]
        
        stats = self.get_stats()
        lines.append(f"| 指标 | 数值 |")
        lines.append(f"|------|------|")
        lines.append(f"| 总目标数 | {stats['total_goals']} |")
        lines.append(f"| 活跃目标 | {stats['active_count']} |")
        lines.append(f"| 已完成 | {stats['total_completed']} |")
        lines.append(f)| 已放弃 | {stats['total_abandoned']} |")
        lines.append(f"| 分支数 | {stats['branch_count']} |")
        lines.append(f"| 平均轮次/目标 | {stats['avg_turns_per_goal']:.1f} |")

        # 活跃目标
        active = self.get_active_goals()
        if active:
            lines.append("\n### 活跃目标")
            for g in active:
                s = g.to_summary()
                lines.append(
                    f"- **{s['target']}** "
                    f"(#{g.turn_count}轮, {s['evolution']})"
                )

        return "\n".join(lines)

    # ── 内部方法 ────────────────────────────────────────────────

    def _find_matching_goal(
        self,
        intent: Intent,
        session_state: str,
    ) -> Optional[GoalNode]:
        """
        匹配已有 Goal

        匹配策略：
        1. 目标字符串相似（target 重叠）
        2. 技术栈一致
        3. 最近活跃过
        """
        active_goals = self.get_active_goals()
        if not active_goals:
            return None

        best_match = None
        best_score = 0.0

        for goal in active_goals:
            score = self._compute_match_score(intent, goal)
            if score > best_score:
                best_score = score
                best_match = goal

        # 相似度阈值：0.4 以上才认为匹配
        return best_match if best_score >= 0.4 else None

    def _compute_match_score(self, intent: Intent, goal: GoalNode) -> float:
        """计算意图与目标的匹配分数 (0~1)"""
        score = 0.0

        # 1. Target 文本重叠 (权重 0.5)
        if intent.target and goal.current_intent.target:
            target_kws = set(intent.target.split())
            goal_kws = set(goal.current_intent.target.split())
            overlap = len(target_kws & goal_kws)
            score += 0.5 * (overlap / max(len(target_kws), len(goal_kws), 1))

        # 2. Action 文本重叠 (权重 0.2)
        if intent.action and goal.current_intent.action:
            if intent.action in goal.current_intent.action or \
               goal.current_intent.action in intent.action:
                score += 0.2

        # 3. 技术栈一致性 (权重 0.2)
        if intent.tech_stack and goal.current_intent.tech_stack:
            common = set(intent.tech_stack) & set(goal.current_intent.tech_stack)
            score += 0.2 * (len(common) / max(len(intent.tech_stack), len(goal.current_intent.tech_stack), 1))

        # 4. 时间衰减 (权重 0.1)：越近的目标优先
        age = time.time() - goal.updated_at
        decay = max(0, 1 - age / 3600)  # 1 小时内线性衰减
        score += 0.1 * decay

        return min(score, 1.0)

    def _create_goal(self, intent: Intent, turn_id: int) -> GoalNode:
        """创建新目标"""
        goal = GoalNode(
            goal_id=uuid.uuid4().hex[:12],
            root_intent=intent,
            current_intent=intent,
        )
        goal.add_turn(turn_id, intent)

        # 容量控制
        if len(self._goals) >= self.max_goals:
            # 淘汰最旧的已完成/放弃目标
            candidates = [
                g for g in self._goals.values()
                if g.status in (GoalStatus.COMPLETED, GoalStatus.ABANDONED)
            ]
            if candidates:
                oldest = min(candidates, key=lambda g: g.completed_at or g.updated_at)
                del self._goals[oldest.goal_id]

        self._goals[goal.goal_id] = goal
        self.stats["total_created"] += 1
        return goal

    def _build_node(self, goal: GoalNode, depth: int = 0) -> Dict[str, Any]:
        """递归构建树节点"""
        children = []
        for cid in goal.child_ids:
            child = self._goals.get(cid)
            if child:
                children.append(self._build_node(child, depth + 1))
        return {
            "id": goal.goal_id[:8],
            "target": goal.root_intent.target or goal.current_intent.action or "?",
            "status": goal.status.name,
            "turns": goal.turn_count,
            "children": children,
        }


# ── 测试入口 ──────────────────────────────────────────────────────


def _test_tracker():
    print("=" * 60)
    print("IntentTracker 测试")
    print("=" * 60)

    tracker = IntentTracker()

    # 模拟 StateMachine 的输出
    from .intent_parser import IntentParser
    parser = IntentParser()

    turns = [
        ("帮我写一个 FastAPI 登录接口", "ACTIVE"),
        ("改成用 JWT 认证", "ACTIVE"),
        ("加一个角色权限中间件", "ACTIVE"),
        ("Python GIL 是什么", "ACTIVE"),     # 新话题
        ("怎么避免 GIL 影响", "ACTIVE"),
        ("回到登录接口，加上验证码", "ACTIVE"),
    ]

    for q, state in turns:
        intent = parser.parse(q)
        goal = tracker.track(intent, turn_id=len(turns) + 1, session_state=state)
        print(f"\nQ: {q}")
        print(f"  → Goal {goal.goal_id[:8]} [{goal.status.name}] #{goal.turn_count}轮")

    # 报告
    print("\n" + tracker.to_report())


if __name__ == "__main__":
    _test_tracker()
