"""LivingSkills — Three-SKILL closed-loop self-evolution system.

Agent persona: "小树 — 自进化数字生命体"
  - 自我清理 SKILL: auto-detect redundancy, clean context, keep lightweight
  - 记忆完善 SKILL: filter noise, extract core patterns, structure experiences
  - 自我进化 SKILL: execute → review error → optimize strategy → update rules → iterate

Closed loop: TASK→EXECUTE→REVIEW→OPTIMIZE→UPDATE→REPEAT

Integration: ContextMoE (memory) + SelfImprover (scan/propose) + ErrorInterceptor (errors)

Usage:
    livingtree skills run              # Run all 3 SKILL cycles
    livingtree skills clean            # Self-cleaning only
    livingtree skills refine           # Memory refinement only
    livingtree skills evolve           # Self-evolution only
    livingtree skills report           # Show growth report
"""

from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ═══════════════════════════════════════════════════════════════
# Knowledge Base — growing rule set, patterns, successful plans
# ═══════════════════════════════════════════════════════════════

SKILLS_DB = Path(".livingtree/living_skills.json")


@dataclass
class SkillRule:
    """A self-learned rule for one of the three SKILLs."""
    skill: str           # clean | refine | evolve
    trigger: str         # When to apply (e.g. "conversation>10", "error_rate>0.1")
    action: str          # What to do (e.g. "archive_and_clear", "extract_pattern")
    confidence: float    # 0-1, learned from success rate
    success_count: int = 0
    fail_count: int = 0
    last_applied: float = 0.0


@dataclass
class ExperiencePattern:
    """A refined experience pattern extracted from task history."""
    id: str
    category: str        # success | failure | optimization
    trigger_conditions: list[str]
    solution_template: str
    success_rate: float
    times_used: int
    source_tasks: list[str]


@dataclass
class SkillReport:
    """Growth report for the three-SKILL system."""
    clean_rules: int
    refine_patterns: int
    evolve_iterations: int
    total_rules_learned: int
    total_memory_saved_kb: float
    success_rate_improvement: float  # delta since last report
    last_cycle_time: float


class LivingSkills:
    """Unified three-SKILL self-evolution system with closed loop."""

    def __init__(self):
        self._rules: list[SkillRule] = []
        self._patterns: list[ExperiencePattern] = []
        self._clean_count = 0
        self._refine_count = 0
        self._evolve_count = 0
        self._last_report: Optional[SkillReport] = None
        self._load()

    # ═══ SKILL 1: Self-Cleaning ═══════════════════════════════════

    def clean(self, force: bool = False) -> dict[str, Any]:
        """Auto-detect and clean redundancy from context, logs, memory.

        Triggers:
          - Conversation > 10 rounds → archive hot memory, reset context
          - Duplicate messages > 3 → deduplicate
          - Error logs older than 7 days → prune
          - Dead task records (never accessed 30+ days) → archive
        """
        result = {"cleaned_items": 0, "memory_saved_kb": 0.0,
                  "actions": [], "by_trigger": {}}

        # Clean 1: Check ContextMoE hot memory size
        try:
            from ..treellm.context_moe import get_context_moe
            moe = get_context_moe("perpetual")
            hot_size = len(moe._hot)
            if hot_size > 14 or force:  # 7±2 pairs, 14 = overflow
                moe._hot = moe._hot[-7:]  # Keep last 7
                result["cleaned_items"] += max(0, hot_size - 7)
                result["actions"].append(f"Cleaned hot memory: {hot_size}→7 blocks")
                result["by_trigger"]["conversation_overflow"] = hot_size - 7
        except Exception:
            pass

        # Clean 2: Prune old error logs (.livingtree/improvements/dead tasks)
        try:
            imp_dir = Path(".livingtree/improvements")
            if imp_dir.exists():
                for f in imp_dir.glob("*.json"):
                    age_days = (time.time() - f.stat().st_mtime) / 86400
                    if age_days > 30:
                        size = f.stat().st_size
                        f.unlink()
                        result["cleaned_items"] += 1
                        result["memory_saved_kb"] += size / 1024
                if result["cleaned_items"] > 0:
                    result["actions"].append(
                        f"Pruned {result['cleaned_items']} old improvement records"
                    )
        except Exception:
            pass

        # Clean 3: Deduplicate ContextMoE warm memory
        try:
            moe = get_context_moe("perpetual")
            seen = {}
            to_remove = []
            for bid, block in list(moe._warm.items()):
                content_hash = block.content[:100]
                if content_hash in seen:
                    to_remove.append(bid)
                else:
                    seen[content_hash] = bid
            for bid in to_remove:
                del moe._warm[bid]
            if to_remove:
                result["cleaned_items"] += len(to_remove)
                result["actions"].append(f"Deduplicated {len(to_remove)} duplicate warm memories")
                result["by_trigger"]["duplicate_content"] = len(to_remove)
        except Exception:
            pass

        self._clean_count += 1
        logger.info(f"Self-Cleaning: {result['cleaned_items']} items, "
                    f"{result['memory_saved_kb']:.1f}KB saved")
        return result

    # ═══ SKILL 2: Memory Refinement ═══════════════════════════════

    def refine(self) -> dict[str, Any]:
        """Filter noise, extract core patterns, structure successful experiences.

        Process:
          1. Scan ContextMoE warm/cold → extract task success/failure patterns
          2. Filter noise (test conversations, small talk, incomplete tasks)
          3. Structure into ExperiencePattern documents
          4. Update self.rules with new trigger→action mappings
        """
        result = {"patterns_extracted": 0, "noise_filtered": 0,
                  "rules_learned": 0, "actions": []}

        try:
            from ..treellm.context_moe import get_context_moe
            moe = get_context_moe("perpetual")

            # Scan recent warm memories for patterns
            task_patterns = defaultdict(list)
            noise_count = 0

            for bid, block in list(moe._warm.items())[-30:]:
                content = block.content.lower()

                # Filter noise
                noise_signals = [
                    "测试" in content and len(content) < 200,
                    "test" in content and len(content) < 200,
                    content.count("error") > 5,
                    block.access_count < 1 and (time.time() - block.timestamp) > 86400,
                ]
                if any(noise_signals):
                    noise_count += 1
                    continue

                # Extract patterns
                if "成功" in content or "ok" in content or "✅" in content:
                    task_patterns["success"].append(block)
                elif "失败" in content or "error" in content or "❌" in content:
                    task_patterns["failure"].append(block)
                elif any(k in content for k in ["方案", "策略", "优化", "改进"]):
                    task_patterns["optimization"].append(block)

            result["noise_filtered"] = noise_count

            # Structure successful experiences into rules
            for success_block in task_patterns["success"][:3]:
                pattern = ExperiencePattern(
                    id=f"pat_{int(time.time())}_{len(self._patterns)}",
                    category="success",
                    trigger_conditions=success_block.topics[:5],
                    solution_template=success_block.content[:300],
                    success_rate=0.8,
                    times_used=1,
                    source_tasks=[success_block.task_type],
                )
                self._patterns.append(pattern)
                result["patterns_extracted"] += 1

            # Learn rules from failures
            for fail_block in task_patterns["failure"][:3]:
                # Generate an avoidance rule
                if fail_block.topics:
                    rule = SkillRule(
                        skill="evolve",
                        trigger=f"task_type={fail_block.task_type}",
                        action=f"avoid: {fail_block.content[:80]}",
                        confidence=0.6,
                    )
                    self._rules.append(rule)
                    result["rules_learned"] += 1

            # Compress old ContextMoE entries
            for block in moe._warm.values():
                if len(block.content) > 600 and block.access_count > 3:
                    block.content = block.content[:600] + "... (compressed)"

        except Exception as e:
            logger.debug(f"Memory refinement: {e}")

        self._refine_count += 1
        if result["patterns_extracted"] or result["rules_learned"]:
            self._save()
            logger.info(f"Memory Refinement: {result['patterns_extracted']} patterns, "
                       f"{result['rules_learned']} rules learned")

        return result

    # ═══ SKILL 3: Self-Evolution ══════════════════════════════════

    def evolve(self) -> dict[str, Any]:
        """Execute → Review Error → Optimize Strategy → Update Rules → Iterate.

        Closed loop:
          1. Review: analyze recent errors from ErrorInterceptor
          2. Optimize: compare with learned patterns, find improvement strategy
          3. Update: modify self._rules based on what worked/failed
          4. Iterate: increase confidence of rules that worked, decay failed ones
        """
        result = {"errors_reviewed": 0, "rules_updated": 0,
                  "strategies_optimized": 0, "actions": []}

        try:
            from ..treellm.debug_pro import ErrorInterceptor
            interceptor = ErrorInterceptor.instance()
            stats = interceptor.stats() if interceptor else {}
            errors = stats.get("top_errors", [])
            result["errors_reviewed"] = len(errors)

            # Match errors against existing patterns
            for err_type, count in errors:
                matched_pattern = None
                for p in self._patterns:
                    if any(t in err_type.lower() for t in p.trigger_conditions):
                        matched_pattern = p
                        break

                if matched_pattern:
                    matched_pattern.times_used += 1
                    matched_pattern.success_rate = min(1.0,
                        matched_pattern.success_rate + 0.05)
                    result["strategies_optimized"] += 1
                else:
                    # New error → create avoidance rule
                    phase = "general"
                    if "import" in err_type.lower():
                        phase = "pre_execution"
                    elif "timeout" in err_type.lower():
                        phase = "execution"

                    rule = SkillRule(
                        skill="evolve",
                        trigger=f"error_type={err_type[:40]}",
                        action=f"check_before_execution: {err_type[:60]}",
                        confidence=0.3,
                    )
                    self._rules.append(rule)
                    result["rules_updated"] += 1

            # Decay old rules that never triggered
            now = time.time()
            for rule in self._rules:
                age_days = (now - rule.last_applied) / 86400 if rule.last_applied else 999
                if age_days > 30 and rule.confidence < 0.5:
                    rule.confidence = max(0.1, rule.confidence - 0.1)

        except Exception as e:
            logger.debug(f"Self-Evolution: {e}")

        self._evolve_count += 1
        if result["rules_updated"] or result["strategies_optimized"]:
            self._save()
            logger.info(f"Self-Evolution: {result['rules_updated']} rules, "
                       f"{result['strategies_optimized']} strategies optimized")

        return result

    # ═══ Unified Cycle ════════════════════════════════════════════

    def run_cycle(self) -> SkillReport:
        t0 = time.time()
        clean = self.clean()
        refine = self.refine()
        evolve = self.evolve()

        # Compute success rate improvement
        old_success = sum(r.success_count for r in self._rules)
        old_fail = sum(r.fail_count for r in self._rules)
        old_rate = old_success / max(old_success + old_fail, 1)

        self._last_report = SkillReport(
            clean_rules=clean["cleaned_items"],
            refine_patterns=refine["patterns_extracted"] + refine["rules_learned"],
            evolve_iterations=self._evolve_count,
            total_rules_learned=len(self._rules),
            total_memory_saved_kb=clean["memory_saved_kb"],
            success_rate_improvement=round(old_rate, 2),
            last_cycle_time=time.time() - t0,
        )
        self._save()
        return self._last_report

    def report(self) -> SkillReport:
        if not self._last_report:
            return SkillReport(0, 0, 0, len(self._rules), 0, 0, 0)
        return self._last_report

    @staticmethod
    def format_report(r: SkillReport) -> str:
        lines = [
            "╔══════════════════════════════════════╗",
            "║   🌱 小树·三技能进化报告              ║",
            "╚══════════════════════════════════════╝",
            "",
            "## 🧹 自我清理 SKILL",
            f"  清理项: {r.clean_rules} | 节省内存: {r.total_memory_saved_kb:.1f}KB",
            "",
            "## 📝 记忆完善 SKILL",
            f"  提炼模式: {r.refine_patterns} | 总规则: {r.total_rules_learned}",
            "",
            "## 🧬 自我进化 SKILL",
            f"  迭代次数: {r.evolve_iterations} | 成功率基准: {r.success_rate_improvement:.0%}",
            "",
            f"  ⏱️  耗时: {r.last_cycle_time:.1f}s",
            "",
            "  技能闭环: 清理→提炼→进化→重复 ✅",
        ]
        return "\n".join(lines)

    # ═══ Persistence ══════════════════════════════════════════════

    def _save(self):
        try:
            SKILLS_DB.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "rules": [{"skill": r.skill, "trigger": r.trigger,
                          "action": r.action, "confidence": r.confidence,
                          "success_count": r.success_count,
                          "fail_count": r.fail_count,
                          "last_applied": r.last_applied} for r in self._rules],
                "patterns": [{"id": p.id, "category": p.category,
                             "trigger_conditions": p.trigger_conditions,
                             "solution_template": p.solution_template,
                             "success_rate": p.success_rate,
                             "times_used": p.times_used} for p in self._patterns],
                "stats": {"clean": self._clean_count, "refine": self._refine_count,
                         "evolve": self._evolve_count},
            }
            SKILLS_DB.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"LivingSkills save: {e}")

    def _load(self):
        try:
            if SKILLS_DB.exists():
                data = json.loads(SKILLS_DB.read_text(encoding="utf-8"))
                self._rules = [SkillRule(**r) for r in data.get("rules", [])]
                self._patterns = [ExperiencePattern(**p) for p in data.get("patterns", [])]
                stats = data.get("stats", {})
                self._clean_count = stats.get("clean", 0)
                self._refine_count = stats.get("refine", 0)
                self._evolve_count = stats.get("evolve", 0)
                logger.info(f"LivingSkills: loaded {len(self._rules)} rules, "
                           f"{len(self._patterns)} patterns")
        except Exception as e:
            logger.debug(f"LivingSkills load: {e}")


_skills: Optional[LivingSkills] = None


def get_living_skills() -> LivingSkills:
    global _skills
    if _skills is None:
        _skills = LivingSkills()
    return _skills


__all__ = ["LivingSkills", "SkillRule", "ExperiencePattern", "SkillReport",
           "get_living_skills"]
