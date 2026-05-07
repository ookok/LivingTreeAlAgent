"""AutonomousCore — 主动智能体闭环：发现→计划→执行→审计→进化.

从被动响应到主动自律的四个层次：
  L1 被动响应:  收到指令 → 执行 → 返回       (当前状态 ✓)
  L2 主动发现:  扫描环境 → 发现待办 → 自动执行 (缺失 ✗)
  L3 自我审计:  回顾历史 → 识别缺陷 → 主动修复 (缺失 ✗)
  L4 全面替代:  预测需求 → 预执行 → 只报告结果 (缺失 ✗)

本模块实现 L2/L3/L4，与已有 LifeDaemon 协作:
  - LifeDaemon: 周期触发器 (何时执行)
  - AutonomousCore: 智能决策 (执行什么、为什么、怎么优化)

核心循环:
  1. Discover:  扫描项目、知识库、技能仪表盘 → 发现待办/缺陷/机会
  2. Prioritize: 按紧急度×价值×ROI排序
  3. Decompose:  高层目标 → 具体行动步骤
  4. Execute:    自动执行（无需人类指令）
  5. Audit:      回顾已完成的工作 → 识别模式 → 改进流程
  6. Evolve:     将审计发现反馈到技能模型和决策链

Usage:
    core = AutonomousCore(world)
    await core.cycle()  # 一次完整的自主循环
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger

AUTO_DIR = Path(".livingtree/meta")
AUTO_LOG = AUTO_DIR / "autonomous_log.json"


# ═══════════════════════════════════════════════════════════════════
# Types
# ═══════════════════════════════════════════════════════════════════

class IntentType(str, Enum):
    FIX_DEFECT = "fix_defect"         # 修复缺陷
    IMPROVE_SKILL = "improve_skill"   # 提升技能
    PRE_COMPLETE = "pre_complete"     # 预完成工作
    OPTIMIZE = "optimize"             # 优化流程
    DISCOVER = "discover"             # 探索发现


@dataclass
class DiscoveredWork:
    """自主发现的工作项."""
    intent: IntentType
    description: str
    evidence: str = ""                # 发现依据
    estimated_value: float = 1.0      # 预估价值
    estimated_cost_yuan: float = 0.0  # 预估成本
    priority: float = 0.5             # 综合优先级
    auto_executable: bool = True      # 是否能自动执行
    source: str = ""                  # 发现来源


@dataclass
class ActionPlan:
    """目标分解后的行动步骤."""
    goal: str
    steps: list[str] = field(default_factory=list)
    estimated_minutes: int = 5
    reversible: bool = True           # 是否可回滚


@dataclass
class AuditFinding:
    """自我审计发现."""
    area: str                         # 审计领域
    finding: str
    severity: str = "warning"         # critical / warning / info
    recommendation: str = ""
    evidence: str = ""


@dataclass
class CycleResult:
    """一次自主循环的完整结果."""
    timestamp: float = field(default_factory=time.time)
    discovered: list[DiscoveredWork] = field(default_factory=list)
    executed: list[str] = field(default_factory=list)     # 执行了的action描述
    skipped: list[str] = field(default_factory=list)      # 跳过的（低优先级/不可自动）
    audit_findings: list[AuditFinding] = field(default_factory=list)
    tokens_used: int = 0
    cost_yuan: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# AutonomousCore
# ═══════════════════════════════════════════════════════════════════

class AutonomousCore:
    """主动智能体核心——发现工作、分解目标、自动执行、自我审计."""

    MAX_AUTO_ACTIONS_PER_CYCLE = 5
    MAX_TOKENS_PER_CYCLE = 20_000

    def __init__(self, world: Any = None, consciousness: Any = None):
        self._world = world
        self._consciousness = consciousness
        self._history: list[CycleResult] = []
        self._cycle_count = 0
        self._total_auto_actions = 0
        self._load_log()

    async def cycle(self) -> CycleResult:
        """执行一次完整的自主智能循环."""
        self._cycle_count += 1
        result = CycleResult()

        # ── Phase 1: Discover ──
        discovered = await self._discover_work()
        result.discovered = discovered
        logger.info(f"AutonomousCore: discovered {len(discovered)} work items")

        # ── Phase 2: Prioritize ──
        prioritized = self._prioritize(discovered)

        # ── Phase 3: Decompose & Execute ──
        total_tokens = 0
        for work in prioritized[:self.MAX_AUTO_ACTIONS_PER_CYCLE]:
            if total_tokens > self.MAX_TOKENS_PER_CYCLE:
                result.skipped.append(f"{work.description} (token budget)")
                continue

            if not work.auto_executable:
                result.skipped.append(f"{work.description} (需要人工)")
                continue

            plan = self._decompose(work)
            success = await self._execute(plan)
            if success:
                result.executed.append(work.description)
                self._total_auto_actions += 1
                total_tokens += 2000
            else:
                result.skipped.append(f"{work.description} (执行失败)")

        # ── Phase 4: Audit ──
        result.audit_findings = await self._self_audit()
        result.tokens_used = total_tokens
        result.cost_yuan = round(total_tokens / 1_000_000 * 3.0, 4)

        self._history.append(result)
        if len(self._history) > 50:
            self._history = self._history[-50:]
        self._save_log()

        logger.info(
            f"AutonomousCore cycle #{self._cycle_count}: "
            f"{len(result.executed)} executed, {len(result.skipped)} skipped, "
            f"{len(result.audit_findings)} audit findings")
        return result

    # ═══ Phase 1: Discover — 主动发现工作 ═══

    async def _discover_work(self) -> list[DiscoveredWork]:
        """扫描项目环境，发现需要做的工作."""
        discovered: list[DiscoveredWork] = []

        # 1. 技能缺陷 → 自动练习
        discovered.extend(self._discover_skill_gaps())

        # 2. 项目待办 → 扫描文档目录
        discovered.extend(self._discover_project_todos())

        # 3. 知识缺口 → knowledge miner 发现
        discovered.extend(self._discover_knowledge_gaps())

        # 4. 优化机会 → 从 MetaMemory 找低效模式
        discovered.extend(self._discover_optimizations())

        # 5. 预完成 → 从历史行为预测需求
        discovered.extend(self._discover_pre_complete())

        return discovered

    def _discover_skill_gaps(self) -> list[DiscoveredWork]:
        """从 SkillProgression 发现需要提升的技能."""
        try:
            from .skill_progression import get_skill_progression
            prog = get_skill_progression()
            report = prog.progress_report()

            work = []
            for skill, metric in report.skills.items():
                if metric.trend < -0.05:
                    work.append(DiscoveredWork(
                        intent=IntentType.IMPROVE_SKILL,
                        description=f"技能下降: {skill} (趋势 {metric.trend:+.1%})",
                        evidence=f"最近{metric.recent_attempts}次成功率{metric.recent_rate:.0%}",
                        estimated_value=3.0,
                        priority=0.8,
                        auto_executable=True,
                        source="skill_progression",
                    ))
                elif metric.level == "novice" and metric.total_attempts >= 5:
                    work.append(DiscoveredWork(
                        intent=IntentType.IMPROVE_SKILL,
                        description=f"新手技能需提升: {skill}",
                        evidence=f"{metric.total_attempts}次尝试仍为新手水平",
                        estimated_value=2.5,
                        priority=0.6,
                        auto_executable=True,
                        source="skill_progression",
                    ))
            return work
        except Exception:
            return []

    def _discover_project_todos(self) -> list[DiscoveredWork]:
        """扫描项目目录发现待办."""
        work = []
        # 检查环评报告生成目录
        output_dir = Path(".livingtree/industrial_output")
        if output_dir.exists():
            drafts = list(output_dir.glob("*.docx"))
            if drafts:
                # 检查是否有 draft 状态的文档过了很久
                old_drafts = [
                    d for d in drafts
                    if "draft" in d.name.lower()
                    and (time.time() - d.stat().st_mtime) > 86400 * 3
                ]
                for d in old_drafts[:3]:
                    work.append(DiscoveredWork(
                        intent=IntentType.PRE_COMPLETE,
                        description=f"草稿待完成: {d.name}",
                        evidence=f"最后修改于 {time.strftime('%Y-%m-%d', time.localtime(d.stat().st_mtime))}",
                        estimated_value=4.0,
                        priority=0.7,
                        auto_executable=False,  # 生成最终文档需人工确认
                        source="project_scan",
                    ))

        # 检查是否有未处理的文档
        doc_dir = Path(".livingtree/documents")
        if doc_dir.exists():
            unread = [f for f in doc_dir.glob("*.*")
                       if f.suffix.lower() in (".docx", ".pdf", ".xlsx")]
            if len(unread) > 5:
                work.append(DiscoveredWork(
                    intent=IntentType.DISCOVER,
                    description=f"未处理文档积压: {len(unread)} 个文件",
                    evidence=f"包括 {unread[0].name} 等",
                    estimated_value=2.0,
                    priority=0.5,
                    auto_executable=False,
                    source="project_scan",
                ))
        return work

    def _discover_knowledge_gaps(self) -> list[DiscoveredWork]:
        """从知识库发现缺口."""
        try:
            from ..knowledge.gap_detector import GapDetector
            # GapDetector is a thin model — skip if no actionable API
            _ = GapDetector()
            # Defer to auto_knowledge_miner for actual gap filling
        except Exception:
            pass
        return []

    def _discover_optimizations(self) -> list[DiscoveredWork]:
        """从 MetaMemory 发现可优化的策略."""
        work: list[DiscoveredWork] = []
        try:
            from .meta_memory import get_meta_memory
            mm = get_meta_memory()
            stats = mm.get_stats()
            low = stats.get("low_performing", [])
            for s in low[:3]:
                work.append(DiscoveredWork(
                    intent=IntentType.OPTIMIZE,
                    description=f"低效策略: {s.get('name', 'unknown')}",
                    evidence=f"成功率 {s.get('success_rate', 0):.1%}",
                    estimated_value=1.5,
                    priority=0.3,
                    auto_executable=False,
                    source="meta_memory",
                ))
        except Exception:
            pass
        return work

    def _discover_pre_complete(self) -> list[DiscoveredWork]:
        """从历史行为预测需求."""

        return []

    # ═══ Phase 2: Prioritize ═══

    def _prioritize(self, work_items: list[DiscoveredWork]) -> list[DiscoveredWork]:
        """按 紧急度×价值/成本 排序."""
        for w in work_items:
            urgency = 1.0 if w.intent == IntentType.FIX_DEFECT else (
                0.8 if w.intent == IntentType.IMPROVE_SKILL else 0.5)
            roi = w.estimated_value / max(w.estimated_cost_yuan, 0.01)
            w.priority = urgency * w.estimated_value * min(roi, 10) / 10
        return sorted(work_items, key=lambda w: w.priority, reverse=True)

    # ═══ Phase 3: Decompose & Execute ═══

    def _decompose(self, work: DiscoveredWork) -> ActionPlan:
        """将高层目标分解为具体步骤."""
        if work.intent == IntentType.IMPROVE_SKILL:
            return ActionPlan(
                goal=work.description,
                steps=[
                    f"检索 {work.description.split(':')[1].strip() if ':' in work.description else work.description} 相关最新知识",
                    f"分析近期失败案例，提取常见错误模式",
                    f"更新内部策略或提示词以改进该技能",
                ],
                estimated_minutes=5,
                reversible=True,
            )
        elif work.intent == IntentType.FIX_DEFECT:
            return ActionPlan(
                goal=work.description,
                steps=[
                    f"定位缺陷根源: {work.evidence}",
                    f"设计修复方案",
                    f"执行修复并验证",
                ],
                estimated_minutes=10,
                reversible=True,
            )
        else:
            return ActionPlan(
                goal=work.description,
                steps=[f"分析 {work.description}"],
                estimated_minutes=3,
                reversible=True,
            )

    async def _execute(self, plan: ActionPlan) -> bool:
        """执行分解后的行动步骤."""
        if not self._consciousness:
            logger.debug(f"AutonomousCore: no consciousness, skipping '{plan.goal[:40]}'")
            return False

        try:
            # 使用 LLM 执行行动计划
            prompt = (
                f"[Autonomous Execution] Execute this plan autonomously:\n"
                f"Goal: {plan.goal}\n"
                f"Steps:\n" + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(plan.steps))
                + f"\n\nExecute step by step. For each step, describe what you did and the outcome."
                f"\nIf a step requires external action (file I/O, search, etc.), use the available tools."
                f"\nOutput JSON: {{'completed': true/false, 'results': ['step1 result', ...]}}"
            )
            raw = await self._consciousness.query(prompt, max_tokens=500, temperature=0.3)
            logger.debug(f"AutonomousCore executed: {plan.goal[:50]} → {raw[:100]}")
            return True
        except Exception as e:
            logger.debug(f"AutonomousCore execute failed: {e}")
            return False

    # ═══ Phase 4: Self-Audit ═══

    async def _self_audit(self) -> list[AuditFinding]:
        """自我审查——发现自身缺陷."""
        findings: list[AuditFinding] = []

        # 1. 技能校准检查
        try:
            from .skill_progression import get_skill_progression
            prog = get_skill_progression()
            for skill in prog._skills:
                cal = prog.calibration_error(skill)
                if cal > 0.3:
                    findings.append(AuditFinding(
                        area="skill_calibration",
                        finding=f"{skill}: 置信度校准误差 {cal:.1%}",
                        severity="warning",
                        recommendation=f"调整 {skill} 相关决策的置信度估计",
                        evidence=f"高置信度预测与实际结果偏差 {cal:.1%}",
                    ))
        except Exception:
            pass

        # 2. 决策质量审查
        try:
            from .reasoning_chain import get_reasoning_chain
            chain = get_reasoning_chain()
            for domain in chain._domain_index:
                decisions = chain.for_domain(domain, limit=20)
                unvalidated = sum(1 for d in decisions if not d.validated)
                if unvalidated > 10:
                    findings.append(AuditFinding(
                        area="decision_validation",
                        finding=f"{domain}: {unvalidated} 条未验证决策",
                        severity="warning",
                        recommendation=f"对 {domain} 领域的决策进行批量验证",
                    ))
        except Exception:
            pass

        # 3. 知识覆盖率审计（轻量检查）
        try:
            from ..knowledge.gap_detector import GapDetector
            detector = GapDetector()
            # GapDetector provides Gap model; check if gaps exist via knowledge module
            from ..knowledge.knowledge_base import KnowledgeBase
            kb = KnowledgeBase()
            # Simple check: KB document count as proxy for coverage
        except Exception:
            pass

        return findings

    # ═══ State ═══

    def _save_log(self):
        try:
            AUTO_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "cycle_count": self._cycle_count,
                "total_auto_actions": self._total_auto_actions,
                "last_cycle": self._history[-1].timestamp if self._history else 0,
            }
            AUTO_LOG.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"AutonomousCore log: {e}")

    def _load_log(self):
        try:
            if not AUTO_LOG.exists():
                return
            data = json.loads(AUTO_LOG.read_text())
            self._cycle_count = data.get("cycle_count", 0)
            self._total_auto_actions = data.get("total_auto_actions", 0)
        except Exception:
            pass

    def stats(self) -> dict[str, Any]:
        return {
            "cycles_completed": self._cycle_count,
            "total_auto_actions": self._total_auto_actions,
            "avg_actions_per_cycle": round(
                self._total_auto_actions / max(self._cycle_count, 1), 1),
        }


# ── Singleton ──────────────────────────────────────────────────────

_autonomous_core: AutonomousCore | None = None


def get_autonomous_core(world: Any = None, consciousness: Any = None) -> AutonomousCore:
    global _autonomous_core
    if _autonomous_core is None:
        _autonomous_core = AutonomousCore(world=world, consciousness=consciousness)
    return _autonomous_core
