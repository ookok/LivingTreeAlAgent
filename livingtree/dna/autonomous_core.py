"""AutonomousCore — 主动智能体闭环：发现→计划→前瞻治理→执行→审计→进化.

从被动响应到主动自律的四个层次：
  L1 被动响应:  收到指令 → 执行 → 返回       (当前状态 ✓)
  L2 主动发现:  扫描环境 → 发现待办 → 自动执行 (缺失 ✗)
  L3 自我审计:  回顾历史 → 识别缺陷 → 主动修复 (缺失 ✗)
  L4 全面替代:  预测需求 → 预执行 → 只报告结果 (缺失 ✗)

本模块实现 L2/L3/L4，与已有 LifeDaemon 协作:
  - LifeDaemon: 周期触发器 (何时执行)
  - AutonomousCore: 智能决策 (执行什么、为什么、怎么优化)

核心循环 (Qian et al. 2026 前瞻治理集成):
  1. Discover:  扫描项目、知识库、技能仪表盘 → 发现待办/缺陷/机会
  2. Prioritize: 按紧急度×价值×ROI排序
  2.5 Foresight: 前瞻治理 — 决定是否模拟、模拟几次、何时停止
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
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger

from .foresight_governance import (
    ForesightDecision,
    GovernanceDecisionReason,
    SimulationRecord,
    get_foresight_governance,
)

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
    governing_equations: list[str] = field(default_factory=list)  # Bosso et al. SDE discovered eqs
    foresight_decisions: list[str] = field(default_factory=list)  # Qian et al. 2026 governance decisions
    tokens_used: int = 0
    cost_yuan: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class VIGILDiagnostician:
    """VIGIL-inspired emotional self-diagnosis for autonomous agents.
    
    Ingests behavioral logs from AutonomousCore cycles, appraises
    events into structured emotional representations, and derives
    RBT (Retrospective Behavioral Taxonomy) diagnoses.
    
    RBT categories:
      - STRENGTH: repeated successes, reliable patterns
      - OPPORTUNITY: near-misses, fixable issues  
      - FAILURE: systematic errors, needs intervention
    """
    
    def __init__(self):
        self._emobank: deque[dict] = deque(maxlen=100)
        self._diagnosis_history: list[dict] = []
        self._emotion_decay = 0.95  # per cycle
    
    def appraise(self, event: dict) -> dict:
        """Convert a behavioral event to structured emotional representation.
        
        Event fields expected: type, success, latency_ms, tokens, error
        Returns: {emotion, intensity, confidence, valence}
        """
        if event.get("success", False):
            if event.get("latency_ms", 0) < 2000:
                emotion = "satisfaction"
                intensity = 0.7
            else:
                emotion = "relief"  # slow but succeeded
                intensity = 0.4
            valence = 0.6
        else:
            error = event.get("error", "")
            if "timeout" in str(error).lower():
                emotion = "frustration"
                intensity = 0.6
            elif "permission" in str(error).lower():
                emotion = "confusion"
                intensity = 0.5
            else:
                emotion = "disappointment"
                intensity = 0.4
            valence = -0.3
        
        appraisal = {
            "emotion": emotion,
            "intensity": intensity,
            "confidence": min(1.0, 0.5 + event.get("confidence", 0) * 0.5),
            "valence": valence,
            "timestamp": time.time(),
            "event_type": event.get("type", "unknown"),
        }
        self._emobank.append(appraisal)
        return appraisal
    
    def decay_emotions(self):
        """Apply exponential decay to all emotions in emobank."""
        for entry in self._emobank:
            entry["intensity"] *= self._emotion_decay
    
    def diagnose(self) -> dict:
        """Derive RBT diagnosis from recent emotional history.
        
        Returns: {strengths: [...], opportunities: [...], failures: [...]}
        """
        self.decay_emotions()
        
        if len(self._emobank) < 5:
            return {"strengths": [], "opportunities": [], "failures": [], "summary": "insufficient data"}
        
        recent = list(self._emobank)[-20:]
        
        strengths = []
        opportunities = []
        failures = []
        
        for entry in recent:
            if entry["valence"] > 0.3 and entry["intensity"] > 0.5:
                strengths.append(f"{entry['emotion']}: {entry['event_type']}")
            elif entry["valence"] < 0 and entry["intensity"] > 0.5:
                failures.append(f"{entry['emotion']}: {entry['event_type']} (intensity={entry['intensity']:.1f})")
            elif entry["valence"] > 0 and entry["intensity"] < 0.4:
                opportunities.append(f"可改进: {entry['event_type']} (低强度成功)")
        
        # Summarize
        summary_parts = []
        if len(failures) >= 3:
            summary_parts.append(f"⚠ {len(failures)} recent failures — consider intervention")
        if len(strengths) > len(failures):
            summary_parts.append(f"✓ {len(strengths)} strengths dominate — system healthy")
        if not summary_parts:
            summary_parts.append("steady state — no significant patterns")
        
        diagnosis = {
            "strengths": strengths[-3:],
            "opportunities": opportunities[-3:],
            "failures": failures[-5:],
            "summary": " | ".join(summary_parts),
            "emotion_trend": self._compute_emotion_trend(),
            "timestamp": time.time(),
        }
        self._diagnosis_history.append(diagnosis)
        return diagnosis
    
    def _compute_emotion_trend(self) -> str:
        """Compute whether emotional state is improving or degrading."""
        if len(self._emobank) < 10:
            return "stable"
        older = list(self._emobank)[-20:-10]
        newer = list(self._emobank)[-10:]
        old_valence = sum(e["valence"] for e in older) / max(len(older), 1)
        new_valence = sum(e["valence"] for e in newer) / max(len(newer), 1)
        if new_valence > old_valence + 0.1:
            return "improving"
        elif new_valence < old_valence - 0.1:
            return "degrading"
        return "stable"
    
    def get_emotional_state(self) -> dict:
        """Return current emotional summary for dashboard."""
        trend = self._compute_emotion_trend()
        current = list(self._emobank)[-5:] if self._emobank else []
        dominant = max(set(e["emotion"] for e in current), key=lambda x: sum(1 for e in current if e["emotion"]==x)) if current else "neutral"
        return {
            "dominant_emotion": dominant,
            "trend": trend,
            "bank_size": len(self._emobank),
            "diagnosis_count": len(self._diagnosis_history),
            "last_diagnosis": self._diagnosis_history[-1]["summary"] if self._diagnosis_history else "none",
        }


# ═══════════════════════════════════════════════════════════════════
# AutonomousCore
# ═══════════════════════════════════════════════════════════════════

class AutonomousCore:
    """主动智能体核心——发现工作、分解目标、前瞻治理、自动执行、自我审计."""

    MAX_AUTO_ACTIONS_PER_CYCLE = 5
    MAX_TOKENS_PER_CYCLE = 20_000
    MAX_SIMULATIONS_PER_CYCLE = 8          # Qian et al. 2026: cap total sims/cycle
    MAX_SIMULATIONS_PER_ITEM = 3           # Per-work-item simulation cap
    DIMINISHING_THRESHOLD = 0.02           # Confidence gain below this → stop

    def __init__(self, world: Any = None, consciousness: Any = None):
        self._world = world
        self._consciousness = consciousness
        self._history: list[CycleResult] = []
        self._cycle_count = 0
        self._total_auto_actions = 0
        self._governance = get_foresight_governance()
        self._vigil = VIGILDiagnostician()
        self._max_actions_per_cycle = self.MAX_AUTO_ACTIONS_PER_CYCLE
        self._sim_count_this_cycle = 0
        self._load_log()

    async def cycle(self) -> CycleResult:
        """执行一次完整的自主智能循环 (含 Qian et al. 2026 前瞻治理)."""
        self._cycle_count += 1
        self._sim_count_this_cycle = 0
        self._governance.record_cycle(self._cycle_count)
        result = CycleResult()

        # ── Phase 1: Discover ──
        discovered = await self._discover_work()
        result.discovered = discovered
        logger.info(f"AutonomousCore: discovered {len(discovered)} work items")

        # ── Phase 2: Prioritize ──
        prioritized = self._prioritize(discovered)

        # ── Phase 2.5: Foresight Governance (Qian et al. 2026) ──
        # 论文核心发现: 不加治理的模拟比不模拟更差。在每次执行前，
        # 评估是否需要模拟、多少次、何时停止。
        foresight_results: dict[str, dict[str, Any]] = {}
        for work in prioritized[:self._max_actions_per_cycle]:
            if not work.auto_executable:
                continue
            decision, reason = self._foresight_gate(work)
            rec = SimulationRecord(
                work_description=work.description[:100],
                decision=decision, reason=reason,
            )
            try:
                pe = self._get_pe()
                sde = pe.fit_sde_model("autonomous_cycle") if pe else {}
                rec.signal_to_noise = sde.get("signal_to_noise", 0) if isinstance(sde.get("signal_to_noise"), (int, float)) else 0
                pred_int = sde.get("prediction_interval_95", (0, 1))
                rec.pre_prediction_interval_width = (
                    (pred_int[1] - pred_int[0]) / max(abs(pred_int[1]), 1e-9)
                    if isinstance(pred_int, tuple) and len(pred_int) == 2 else 0
                )
            except Exception:
                pass

            if decision == ForesightDecision.SIMULATE_ONCE:
                sim_result = await self._run_single_simulation(work)
                rec.num_simulations_performed = 1
                rec.post_confidence = sim_result.get("confidence", 0.5)
                rec.confidence_gain = rec.post_confidence - rec.pre_confidence
                rec.was_helpful = rec.confidence_gain > 0.05
                self._sim_count_this_cycle += 1
                foresight_results[work.description] = {"simulated": True, **sim_result}

            elif decision == ForesightDecision.SIMULATE_MULTIPLE:
                confidence_history: list[float] = []
                sim_result: dict[str, Any] = {"confidence": 0.5, "simulated": False}
                for i in range(self.MAX_SIMULATIONS_PER_ITEM):
                    if self._sim_count_this_cycle >= self.MAX_SIMULATIONS_PER_CYCLE:
                        break
                    sim_result = await self._run_single_simulation(work)
                    conf = sim_result.get("confidence", 0.5)
                    confidence_history.append(conf)
                    rec.num_simulations_performed += 1
                    self._sim_count_this_cycle += 1
                    if self._should_stop_simulating(confidence_history):
                        rec.stopped_early = True
                        break

                # Evaluate counterfactuals for irreversible work
                if not self._decompose(work).reversible:
                    counterfactual = await self._evaluate_counterfactuals(work)
                    foresight_results[work.description] = {
                        "simulated": sim_result.get("simulated", False),
                        **sim_result, "counterfactual": counterfactual,
                    }

                rec.post_confidence = confidence_history[-1] if confidence_history else 0.5
                rec.confidence_gain = rec.post_confidence - rec.pre_confidence
                rec.was_helpful = rec.confidence_gain > 0.05
                rec.was_harmful = rec.confidence_gain < -0.05

            self._governance.record(rec)

        # ── Phase 3: Decompose & Execute ──
        total_tokens = 0
        for work in prioritized[:self._max_actions_per_cycle]:
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

        # ── Phase 5: Evolve — 方程发现 (Bosso et al. 2025 SDE) ──
        result.governing_equations = await self._discover_governing_equations()

        # ── Phase 6: Adaptive Diffusion (Qian et al. 2026) ──
        # 根据治理健康度自动调整 Consciousness 的扩散水平
        await self._adapt_diffusion()

        result.tokens_used = total_tokens
        result.cost_yuan = round(total_tokens / 1_000_000 * 3.0, 4)

        self._history.append(result)
        if len(self._history) > 50:
            self._history = self._history[-50:]
        self._save_log()
        self._governance._save()

        # ── VIGIL emotional diagnosis ──
        if hasattr(self, '_vigil'):
            event = {
                "type": "autonomous_cycle",
                "success": len(result.executed) > 0,
                "latency_ms": 0,
                "tokens": result.tokens_used,
                "error": "",
                "confidence": 0.5,
            }
            self._vigil.appraise(event)
            if len(self._vigil._emobank) >= 20:
                diagnosis = self._vigil.diagnose()
                result.metadata["vigil_diagnosis"] = diagnosis["summary"]
                if diagnosis["failures"] and len(diagnosis["failures"]) >= 3:
                    self._max_actions_per_cycle = max(1, self._max_actions_per_cycle - 1)
                elif not diagnosis["failures"] and diagnosis["strengths"]:
                    self._max_actions_per_cycle = min(10, self._max_actions_per_cycle + 1)

        gov_score = self._governance.metrics.governance_score
        logger.info(
            f"AutonomousCore cycle #{self._cycle_count}: "
            f"{len(result.executed)} executed, {len(result.skipped)} skipped, "
            f"{len(result.audit_findings)} audit findings, "
            f"governance={gov_score:.2f}")
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

    # ═══ Phase 5: Evolve — Governing Equation Discovery (Bosso et al. 2025) ═══

    async def _discover_governing_equations(self) -> list[str]:
        """Attempt to discover governing equations for the system's own dynamics.

        Bosso et al. (2025) — machine learning framework for uncovering
        stochastic nonlinear dynamics from noisy data. Here we apply the
        same spirit: ask the consciousness to analyze recent system metrics
        and hypothesize governing equations of the form:

            dX_t = f(X_t) dt + g(X_t) dW_t

        where f is deterministic drift and g is stochastic diffusion.

        Returns a list of hypothesized equation strings.
        """
        if not self._consciousness:
            return []

        try:
            pe = self._get_pe()
            ed = self._get_ed()
            stats = pe.stats() if pe else {}
            emergence_stats = ed.stats() if ed else {}

            prompt = (
                "[Self-Governing Equation Discovery — Bosso et al. 2025]\n"
                "Analyze the system's own dynamics and hypothesize governing equations:\n\n"
                f"Current state:\n"
                f"  - Predictability score (avg): {stats.get('avg_predictability', 'N/A')}\n"
                f"  - Series tracked: {stats.get('series_tracked', 0)}\n"
                f"  - Genuine emergence signals: {emergence_stats.get('latest_genuine_signals', 0)}\n"
                f"  - Phase transitions detected: {emergence_stats.get('has_phase_transition', False)}\n\n"
                "Task: Propose 1-3 possible SDEs of form dX_t = f(X_t)dt + g(X_t)dW_t "
                "that could govern the system's self-evolution.\n"
                "Consider:\n"
                "  - If emergence is detected → g(x) inherits from f(x) (intrinsic stochasticity)\n"
                "  - If low predictability → add stronger diffusion g(x)\n"
                "  - If phase transition → piecewise SDEs with regime switching\n\n"
                "Output as JSON list of strings, each a LaTeX-formatted equation."
            )

            raw = await self._consciousness.query(prompt, max_tokens=300, temperature=0.4)
            import json as _json
            try:
                equations = _json.loads(raw)
                if isinstance(equations, list):
                    logger.info(
                        f"AutonomousCore: discovered {len(equations)} governing equations"
                    )
                    return equations
            except _json.JSONDecodeError:
                if raw.strip():
                    return [raw.strip()[:200]]

            return []
        except Exception as e:
            logger.debug(f"AutonomousCore equation discovery: {e}")
            return []

    # ═══ Phase 2.5: Foresight Governance (Qian et al. 2026) ═══

    def _foresight_gate(self, work: DiscoveredWork) -> tuple[ForesightDecision, GovernanceDecisionReason]:
        """论文 Stage I (输入治理): 决定是否模拟再执行。

        Qian et al. (2026) 核心发现:
          - 不加区分地调用世界模型反而降低性能 (Fig 2, Fig 8)
          - 决策应基于: 可逆性、预测置信度、信号噪声比

        Returns:
            (decision, reason) — what to do and why.
        """
        plan = self._decompose(work)

        # Rule 1: Reversible actions → act directly
        # 论文: 可回滚操作不需要模拟，"模拟有害"模式在主任务中更常见
        if plan.reversible:
            return (ForesightDecision.ACT_DIRECTLY, GovernanceDecisionReason.REVERSIBLE)

        # Rule 2: Check simulation budget
        if self._sim_count_this_cycle >= self.MAX_SIMULATIONS_PER_CYCLE:
            return (ForesightDecision.ACT_DIRECTLY, GovernanceDecisionReason.BUDGET_EXHAUSTED)

        # Rule 3: Consult predictability engine for confidence calibration
        try:
            pe = self._get_pe()
            if pe is None:
                return (ForesightDecision.SIMULATE_ONCE, GovernanceDecisionReason.IRREVERSIBLE)

            sde = pe.fit_sde_model("autonomous_cycle")

            snr = sde.get("signal_to_noise", 0)
            if snr == "inf":
                snr_val = 10.0
            elif isinstance(snr, (int, float)):
                snr_val = float(snr)
            else:
                snr_val = 1.0

            pred_int = sde.get("prediction_interval_95", (0, 1))
            if isinstance(pred_int, tuple) and len(pred_int) == 2:
                interval_width = (pred_int[1] - pred_int[0]) / max(abs(pred_int[1]), 1e-9)
            else:
                interval_width = 1.0

            # 论文 Table: 置信区间窄 + 高SNR → 直接行动
            if snr_val > 5.0 and interval_width < 0.1:
                return (ForesightDecision.ACT_DIRECTLY, GovernanceDecisionReason.HIGH_CONFIDENCE)

            # 论文: 低SNR → 模拟可能有害 (噪声主导)
            if snr_val < 1.0:
                if self._governance.is_over_simulating():
                    return (ForesightDecision.ACT_DIRECTLY, GovernanceDecisionReason.LOW_SNR)
                return (ForesightDecision.SIMULATE_ONCE, GovernanceDecisionReason.HIGH_UNCERTAINTY)

            # 论文: 宽预测区间 → 需要多次模拟
            if interval_width > 0.3:
                return (ForesightDecision.SIMULATE_MULTIPLE, GovernanceDecisionReason.HIGH_UNCERTAINTY)

            # Default: simulate once for irreversible actions
            return (ForesightDecision.SIMULATE_ONCE, GovernanceDecisionReason.IRREVERSIBLE)

        except Exception:
            return (ForesightDecision.ACT_DIRECTLY, GovernanceDecisionReason.REVERSIBLE)

    def _should_stop_simulating(self, confidence_history: list[float]) -> bool:
        """论文 Stage I 补充: 模拟停止准则。

        Qian et al. (2026) Fig 7: 更多调用 = 更差结果 (负相关)。
        检测置信度递增是否已降至阈值以下。

        Args:
            confidence_history: 历次模拟后的置信度值序列 (按时间顺序)

        Returns:
            True if further simulation is unlikely to help.
        """
        if len(confidence_history) < 2:
            return False

        # 计算最近 N 次模拟的置信度增量
        recent = confidence_history[-3:]
        if len(recent) < 2:
            return False

        gains = [recent[i] - recent[i - 1] for i in range(1, len(recent))]

        # 条件 1: 最近的增量低于阈值
        if abs(gains[-1]) < self.DIMINISHING_THRESHOLD:
            return True

        # 条件 2: 连续两次增量为负或接近零 → 递减收益
        if len(gains) >= 2 and gains[-1] <= gains[-2] < self.DIMINISHING_THRESHOLD:
            return True

        # 条件 3: 已达到每项最大模拟次数
        if len(confidence_history) >= self.MAX_SIMULATIONS_PER_ITEM:
            return True

        return False

    def _calibrate_confidence(
        self, work: DiscoveredWork, sde_result: dict[str, Any],
    ) -> float:
        """论文 Stage II (意义治理): 将预测区间映射为可信度信号。

        将 predictability_engine 的输出转换为 governance 可用的置信度评分。

        Returns:
            Confidence score (0-1), where 1 = completely confident.
        """
        snr = sde_result.get("signal_to_noise", 0)
        if snr == "inf":
            snr_val = 10.0
        elif isinstance(snr, (int, float)):
            snr_val = float(snr)
        else:
            snr_val = 1.0

        pred_int = sde_result.get("prediction_interval_95", (0, 1))
        if isinstance(pred_int, tuple) and len(pred_int) == 2:
            interval_width = (pred_int[1] - pred_int[0]) / max(abs(pred_int[1]), 1e-9)
        else:
            interval_width = 1.0

        noise_type = sde_result.get("noise_type", "additive")

        # Base confidence from SNR (sigmoid-like)
        base = 2.0 / (1.0 + 2.71828 ** (-snr_val / 3.0)) - 1.0
        base = max(0.0, min(1.0, base))

        # Penalty for wide prediction intervals
        interval_penalty = min(0.3, interval_width * 0.3)

        # Bonus/penalty for noise type
        noise_factor = 0.05 if noise_type == "multiplicative" else 0.0

        return max(0.0, min(1.0, base - interval_penalty + noise_factor))

    async def _evaluate_counterfactuals(self, work: DiscoveredWork) -> dict[str, Any]:
        """论文 Stage II 补充: 反事实分支评估。

        Qian et al. (2026) Fig 5: Agent 失败于"产生单一确定性未来，
        用过度自信的内部推理覆盖模拟结果"。

        生成多个备选行动方案，评估每个方案的结果，返回最优路径。
        """
        if not self._consciousness:
            return {"counterfactuals": 0, "selected": None}

        try:
            # Generate alternative approaches
            hypotheses = await self._consciousness.hypothesis_generation(
                f"Alternative approaches for: {work.description}. "
                f"Evidence: {work.evidence}",
                count=3,
            )

            if not hypotheses or len(hypotheses) <= 1:
                return {"counterfactuals": 0, "selected": "single_path"}

            # Evaluate each hypothesis via predictability engine
            pe = self._get_pe()
            outcomes = []
            for h in hypotheses:
                if pe:
                    sde = pe.fit_sde_model("autonomous_cycle")
                    pred_int = sde.get("prediction_interval_95", (0, 1))
                    if isinstance(pred_int, tuple) and len(pred_int) == 2:
                        width = pred_int[1] - pred_int[0]
                    else:
                        width = float("inf")
                    confidence = self._calibrate_confidence(work, sde)
                else:
                    width = 1.0
                    confidence = 0.5
                outcomes.append({
                    "hypothesis": h[:100],
                    "interval_width": round(width, 4),
                    "confidence": round(confidence, 3),
                })

            # Select the hypothesis with narrowest prediction interval
            best = min(outcomes, key=lambda o: o["interval_width"])

            logger.debug(
                f"Foresight: counterfactuals evaluated {len(outcomes)} paths "
                f"→ selected '{best['hypothesis'][:50]}' (ci_width={best['interval_width']})"
            )

            return {
                "counterfactuals": len(outcomes),
                "selected": best["hypothesis"],
                "confidence": best["confidence"],
                "all_outcomes": outcomes,
            }
        except Exception as e:
            logger.debug(f"Counterfactual evaluation failed: {e}")
            return {"counterfactuals": 0, "error": str(e)}

    async def _run_single_simulation(self, work: DiscoveredWork) -> dict[str, Any]:
        """Run one foresight simulation via consciousness.

        Simulates the outcome of the proposed work without actually executing it.
        This is the ct=W path in Qian et al. (2026)'s interaction protocol.
        """
        if not self._consciousness:
            return {"confidence": 0.5, "simulated": False}

        try:
            pe = self._get_pe()
            sde_context = ""
            if pe:
                sde = pe.fit_sde_model("autonomous_cycle")
                if sde and "error" not in sde:
                    sde_context = (
                        f"SDE model: SNR={sde.get('signal_to_noise', 'N/A')}, "
                        f"noise_type={sde.get('noise_type', 'N/A')}, "
                        f"prediction_95={sde.get('prediction_interval_95', (0,1))}"
                    )

            prompt = (
                f"[Foresight Simulation — Qian et al. 2026 World Model as Tool]\n"
                f"You are simulating the outcome of this work BEFORE executing it.\n\n"
                f"Work: {work.description}\n"
                f"Intent: {work.intent.value}\n"
                f"Evidence: {work.evidence}\n"
                f"System context: {sde_context}\n\n"
                f"Simulate what would happen if this work were executed.\n"
                f"Return JSON: {{'predicted_outcome': '...', 'risks': [...], "
                f"'confidence': 0.0-1.0, 'recommendation': 'proceed'|'caution'|'abort'}}"
            )

            raw = await self._consciousness.query(prompt, max_tokens=200, temperature=0.3)
            try:
                result = json.loads(raw)
                if isinstance(result, dict):
                    return {
                        "confidence": result.get("confidence", 0.5),
                        "recommendation": result.get("recommendation", "proceed"),
                        "predicted_outcome": result.get("predicted_outcome", ""),
                        "risks": result.get("risks", []),
                        "simulated": True,
                    }
            except json.JSONDecodeError:
                pass

            return {"confidence": 0.5, "simulated": True, "raw": raw[:200]}
        except Exception as e:
            logger.debug(f"Single simulation failed: {e}")
            return {"confidence": 0.5, "simulated": False, "error": str(e)}

    async def _adapt_diffusion(self) -> None:
        """论文 Stage III (行动治理): 自适应扩散控制。

        Qian et al. (2026) Finding 3: 不同模型家族的调用行为差异源于
        对自身能力的不正确认知。大模型过度自信 (GPT-5 调用率 ~0%),
        小模型过度调用 (LLaMA ~99.6%)。

        根据治理健康度动态调整 Consciousness 的扩散水平:
          - 治理评分低 → 更保守 (降低扩散 = 减少随机探索)
          - 治理评分高 → 适度提高扩散 (更多创造性探索)
        """
        if not self._consciousness:
            return

        try:
            score = self._governance.metrics.governance_score

            # 映射: 治理评分 0-1 → 扩散水平 0.2-0.7 (保守区间)
            # 低于 0.5 的评分: 更保守 (0.2-0.4)
            # 高于 0.5 的评分: 适度探索 (0.4-0.7)
            target = 0.2 + score * 0.5

            current = getattr(self._consciousness, 'diffusion_level', 0.5)

            # 平滑过渡: 仅当差异超过阈值时调整
            if abs(target - current) > 0.1:
                self._consciousness.set_diffusion_level(round(target, 2))
                logger.debug(
                    f"Foresight: adapted diffusion {current:.2f} → {target:.2f} "
                    f"(governance_score={score:.2f})"
                )
        except Exception as e:
            logger.debug(f"Adaptive diffusion: {e}")

    # ── OrthoReg Disentanglement Verification (CVPR 2026) ──

    async def _verify_disentanglement(self) -> dict[str, Any]:
        """Verify Weight Disentanglement (WD) across system modules.

        OrthoReg (CVPR 2026) causal chain: TFS → WVO → WD.
        This is the Audit-phase verification that WD is maintained.
        Calls into emergence_detector for organ interference and
        system_sde for coupling analysis.

        Returns:
            dict with disentanglement score and recommendations.
        """
        result: dict[str, Any] = {
            "score": 1.0,
            "interference_detected": False,
            "details": [],
            "recommendation": "",
        }

        try:
            # Check 1: Organ interference via emergence detector
            ed = self._get_ed()
            if ed:
                # Collect organ states for interference analysis
                try:
                    from .system_sde import get_system_sde
                    sde = get_system_sde()
                    state = sde.get_state()
                    organ_vals = {
                        name: [s.current_value] * 5  # pseudo-history
                        for name, s in state.organs.items()
                    }
                    interference = ed.organ_interference_matrix(organ_vals)
                    if interference.get("avg_interference", 0) > 0.5:
                        result["interference_detected"] = True
                        result["details"].append({
                            "source": "organ_interference",
                            "score": interference["avg_interference"],
                            "interpretation": interference.get("interpretation", ""),
                        })
                except Exception:
                    pass

            # Check 2: SDE coupling heatmap
            try:
                from .system_sde import get_system_sde
                sde2 = get_system_sde()
                coupling = sde2.organ_coupling_heatmap()
                orthoreg_score = coupling.get("orthoreg_score", 1.0)
                result["details"].append({
                    "source": "sde_coupling",
                    "score": orthoreg_score,
                    "interpretation": coupling.get("interpretation", ""),
                })
                if orthoreg_score < 0.5:
                    result["interference_detected"] = True
            except Exception:
                pass

            # Check 3: Knowledge orthogonality (from hypergraph stats)
            try:
                from ..knowledge.hypergraph_store import HypergraphStore
                hg = HypergraphStore()
                hg_stats = hg.stats()
                edge_count = hg_stats.get("hyperedge_count", 0)
                if edge_count > 50:
                    result["details"].append({
                        "source": "hypergraph_density",
                        "edge_count": edge_count,
                        "note": f"Large hypergraph ({edge_count} edges) — "
                                "check for redundant knowledge via orthogonal_insert()",
                    })
            except Exception:
                pass

            # Aggregate score
            scores = [d.get("score", 1.0) for d in result["details"]
                      if isinstance(d.get("score"), (int, float))]
            if scores:
                result["score"] = round(
                    1.0 - max(0.0, 1.0 - min(scores)), 3)

            if result["interference_detected"]:
                result["recommendation"] = (
                    "WD violation detected. Apply OrthoReg-style "
                    "disentanglement: enforce weight vector orthogonality "
                    "via OrthogonalityGuard.enforce() on interfering modules."
                )
            else:
                result["recommendation"] = (
                    "WD maintained — OrthoReg condition satisfied. "
                    "No cross-module interference detected."
                )

        except Exception as e:
            logger.debug(f"OrthoReg verify: {e}")
            result["error"] = str(e)

        return result

    # ── Helpers ──

    @staticmethod
    def _get_pe():
        """Lazy-load predictability engine singleton."""
        try:
            from .predictability_engine import get_predictability_engine
            return get_predictability_engine()
        except Exception:
            return None

    @staticmethod
    def _get_ed():
        """Lazy-load emergence detector singleton."""
        try:
            from .emergence_detector import get_emergence_detector
            return get_emergence_detector()
        except Exception:
            return None

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

    async def _gather_system_metrics(self) -> dict[str, Any]:
        """Unified system metrics collection — aggregates signals from all modules.

        Collects SDE state, emergence detection, organ coupling, governance score,
        disentanglement status, and hypergraph density into a single metrics dict.

        Used by the autonomous cycle for adaptive decision-making and by the
        admin dashboard for real-time system visualization.

        Returns:
            dict with keys: sde, emergence, coupling, governance, orthoreg, knowledge
        """
        metrics: dict[str, Any] = {
            "timestamp": time.time(),
            "cycle": self._cycle_count,
        }

        # 1. System SDE state
        try:
            from .system_sde import get_system_sde
            sde = get_system_sde()
            sde_state = sde.get_state()
            metrics["sde"] = {
                "regime": sde_state.system_regime,
                "total_drift": sde_state.total_drift_magnitude,
                "total_diffusion": sde_state.total_diffusion_magnitude,
                "coupling_strength": sde_state.coupling_strength,
                "active_organs": len(sde_state.organs),
            }
            # Predict next 5 steps
            pred = sde.predict_horizon(steps=5)
            metrics["sde_forecast"] = {
                "steps": 5,
                "confidence": pred.confidence,
            }
        except Exception as e:
            logger.debug(f"Metrics: SDE unavailable — {e}")
            metrics["sde"] = {"status": "unavailable"}

        # 2. Emergence detection
        try:
            ed = self._get_ed()
            if ed:
                em_stats = ed.stats()
                metrics["emergence"] = {
                    "nonlinearity": em_stats.get("nonlinearity_score", 0),
                    "perturbation_robustness": em_stats.get("perturbation_robustness", 0),
                    "phase_transitions": em_stats.get("phase_transitions_detected", 0),
                }
        except Exception as e:
            logger.debug(f"Metrics: emergence unavailable — {e}")

        # 3. Organ coupling heatmap (OrthoReg)
        try:
            from .system_sde import get_system_sde
            sde2 = get_system_sde()
            coupling = sde2.organ_coupling_heatmap()
            metrics["orthoreg"] = {
                "score": coupling.get("orthoreg_score", 1.0),
                "coupling_strength": coupling.get("coupling_strength", 0.0),
                "high_coupling_pairs": len(coupling.get("high_coupling_pairs", [])),
                "interpretation": coupling.get("interpretation", ""),
            }
        except Exception as e:
            logger.debug(f"Metrics: orthoreg unavailable — {e}")

        # 4. Governance score (Qian et al. 2026)
        gov = self._governance.metrics
        metrics["governance"] = {
            "score": round(gov.governance_score, 3),
            "help_rate": round(gov.help_rate, 3),
            "harm_rate": round(gov.harm_rate, 3),
            "call_to_action_ratio": round(gov.call_to_action_ratio, 3),
            "is_over_simulating": self._governance.is_over_simulating(),
        }

        # 5. Knowledge hypergraph density
        try:
            from ..knowledge.hypergraph_store import HypergraphStore
            hg = HypergraphStore()
            hg_stats = hg.stats()
            metrics["knowledge"] = {
                "edge_count": hg_stats.get("hyperedge_count", 0),
                "node_count": hg_stats.get("node_count", 0),
            }
        except Exception:
            metrics["knowledge"] = {"status": "unavailable"}

        return metrics

    def stats(self) -> dict[str, Any]:
        gov = self._governance.metrics
        return {
            "cycles_completed": self._cycle_count,
            "total_auto_actions": self._total_auto_actions,
            "avg_actions_per_cycle": round(
                self._total_auto_actions / max(self._cycle_count, 1), 1),
            # Qian et al. 2026 Foresight Governance
            "governance_score": round(gov.governance_score, 3),
            "simulation_help_rate": round(gov.help_rate, 3),
            "simulation_harm_rate": round(gov.harm_rate, 3),
            "call_to_action_ratio": round(gov.call_to_action_ratio, 3),
            "is_over_simulating": self._governance.is_over_simulating(),
        }


# ── Singleton ──────────────────────────────────────────────────────

_autonomous_core: AutonomousCore | None = None


def get_autonomous_core(world: Any = None, consciousness: Any = None) -> AutonomousCore:
    global _autonomous_core
    if _autonomous_core is None:
        _autonomous_core = AutonomousCore(world=world, consciousness=consciousness)
    return _autonomous_core
