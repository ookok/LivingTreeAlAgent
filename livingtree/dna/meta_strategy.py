"""MetaStrategy — DGM-H inspired editable meta-level improvement strategies.

The meta-level strategy (how the system observes, generates, and deploys
improvements) is itself a configuration that can be reviewed and rewritten
by the system. This eliminates the hardcoded "always observe hubs + uncovered
+ errors" limitation of the original SelfEvolvingEngine.

Strategy components:
  1. ObservationStrategy — what and how to observe for improvement signals
  2. GenerationStrategy — how to generate improvement candidates (temp, tokens, prompt)
  3. DeploymentStrategy — how to deploy and rollback

Self-review cycle:
  MetaStrategyEngine loads current strategy + MetaMemory history → asks LLM
  to analyze what works → proposes strategy edits → saves new version with
  version tracking.

Usage:
    engine = MetaStrategyEngine(consciousness)
    await engine.review_and_evolve()  # LLM reviews and proposes edits
    strategy = engine.current
    candidates = await strategy.observe(world)
"""

from __future__ import annotations

import copy
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from .meta_memory import get_meta_memory, MetaMemory

STRATEGY_DIR = Path(".livingtree/meta")
STRATEGY_FILE = STRATEGY_DIR / "meta_strategy.json"


@dataclass
class ObservationStrategy:
    """What the system observes when looking for improvement opportunities."""

    enabled: bool = True
    hub_analysis: bool = True
    hub_max_count: int = 2
    uncovered_functions: bool = True
    uncovered_max_count: int = 2
    error_patterns: bool = True
    error_max_count: int = 2
    meta_memory_patterns: bool = False
    meta_memory_max_count: int = 1
    custom_patterns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "hub_analysis": self.hub_analysis,
            "hub_max_count": self.hub_max_count,
            "uncovered_functions": self.uncovered_functions,
            "uncovered_max_count": self.uncovered_max_count,
            "error_patterns": self.error_patterns,
            "error_max_count": self.error_max_count,
            "meta_memory_patterns": self.meta_memory_patterns,
            "meta_memory_max_count": self.meta_memory_max_count,
            "custom_patterns": self.custom_patterns,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ObservationStrategy":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class GenerationStrategy:
    """How the system generates improvement candidates."""

    temperature: float = 0.8
    max_tokens: int = 8192
    cot_steps: int = 2
    mutation_rate: float = 0.3
    crossover_rate: float = 0.5
    population_size: int = 32
    max_generations: int = 24
    prompt_prefix: str = (
        "Improve the following code. Focus on: {description}\n\n"
        "File: {file_path}\n\n"
        "Original code:\n```\n{original}\n```\n\n"
        "Output ONLY the complete improved code. No explanations."
    )

    def to_dict(self) -> dict:
        return {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "cot_steps": self.cot_steps,
            "mutation_rate": self.mutation_rate,
            "crossover_rate": self.crossover_rate,
            "population_size": self.population_size,
            "max_generations": self.max_generations,
            "prompt_prefix": self.prompt_prefix,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GenerationStrategy":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class DeploymentStrategy:
    """How the system deploys and rollbacks improvements."""

    quality_threshold: float = 0.6
    require_hitl_approval: bool = True
    auto_deploy_min_score: float = 0.9
    max_auto_deploy_per_session: int = 3
    rollback_on_test_failure: bool = True
    max_consecutive_rollbacks: int = 3
    side_git_enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "quality_threshold": self.quality_threshold,
            "require_hitl_approval": self.require_hitl_approval,
            "auto_deploy_min_score": self.auto_deploy_min_score,
            "max_auto_deploy_per_session": self.max_auto_deploy_per_session,
            "rollback_on_test_failure": self.rollback_on_test_failure,
            "max_consecutive_rollbacks": self.max_consecutive_rollbacks,
            "side_git_enabled": self.side_git_enabled,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DeploymentStrategy":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class MetaStrategyVersion:
    """A versioned snapshot of the meta strategy at a point in time."""

    version: int
    observation: ObservationStrategy
    generation: GenerationStrategy
    deployment: DeploymentStrategy
    created_at: float = field(default_factory=time.time)
    reason: str = "initial"


class MetaStrategy:
    """The complete meta-level strategy that governs how the system improves itself.

    This is the artifact that the DGM-H Meta Agent can edit — it's stored as
    a JSON file that the system can read, modify, and reload at runtime.
    """

    def __init__(self):
        self.observation = ObservationStrategy()
        self.generation = GenerationStrategy()
        self.deployment = DeploymentStrategy()
        self._versions: list[MetaStrategyVersion] = []
        self._version_counter = 0

    def snapshot(self, reason: str = "") -> MetaStrategyVersion:
        """Save current strategy state as a new version."""
        self._version_counter += 1
        v = MetaStrategyVersion(
            version=self._version_counter,
            observation=copy.deepcopy(self.observation),
            generation=copy.deepcopy(self.generation),
            deployment=copy.deepcopy(self.deployment),
            reason=reason,
        )
        self._versions.append(v)
        if len(self._versions) > 50:
            self._versions = self._versions[-50:]
        return v

    def to_dict(self) -> dict:
        return {
            "observation": self.observation.to_dict(),
            "generation": self.generation.to_dict(),
            "deployment": self.deployment.to_dict(),
            "version": self._version_counter,
            "versions": [{
                "version": v.version, "reason": v.reason, "created_at": v.created_at,
                "observation": v.observation.to_dict(),
                "generation": v.generation.to_dict(),
                "deployment": v.deployment.to_dict(),
            } for v in self._versions[-10:]],
        }

    def from_dict(self, d: dict):
        if "observation" in d:
            self.observation = ObservationStrategy.from_dict(d["observation"])
        if "generation" in d:
            self.generation = GenerationStrategy.from_dict(d["generation"])
        if "deployment" in d:
            self.deployment = DeploymentStrategy.from_dict(d["deployment"])
        self._version_counter = d.get("version", 0)
        if "versions" in d:
            self._versions = []
            for vd in d["versions"]:
                self._versions.append(MetaStrategyVersion(
                    version=vd["version"],
                    observation=ObservationStrategy.from_dict(vd.get("observation", {})),
                    generation=GenerationStrategy.from_dict(vd.get("generation", {})),
                    deployment=DeploymentStrategy.from_dict(vd.get("deployment", {})),
                    created_at=vd.get("created_at", time.time()),
                    reason=vd.get("reason", ""),
                ))

    def apply(self, d: dict):
        """Apply a partial update dict to current strategy (from LLM output)."""
        changed = False
        for section in ("observation", "generation", "deployment"):
            if section in d and isinstance(d[section], dict):
                strategy = getattr(self, section)
                for key, value in d[section].items():
                    if hasattr(strategy, key):
                        old_val = getattr(strategy, key)
                        if old_val != value:
                            setattr(strategy, key, value)
                            changed = True
                            logger.info(f"MetaStrategy.{section}.{key}: {old_val} → {value}")
        return changed

    def describe_changes(self) -> str:
        """Generate a human-readable description of the current strategy."""
        obs = self.observation
        gen = self.generation
        dep = self.deployment
        parts = []
        parts.append(f"观察策略: hub={obs.hub_analysis}(x{obs.hub_max_count}), "
                     f"uncovered={obs.uncovered_functions}(x{obs.uncovered_max_count}), "
                     f"errors={obs.error_patterns}(x{obs.error_max_count})")
        parts.append(f"生成策略: temp={gen.temperature}, tokens={gen.max_tokens}, "
                     f"steps={gen.cot_steps}, pop={gen.population_size}, gens={gen.max_generations}")
        parts.append(f"部署策略: quality>={dep.quality_threshold}, HITL={dep.require_hitl_approval}, "
                     f"auto>={dep.auto_deploy_min_score}")
        return "\n".join(parts)


class MetaStrategyEngine:
    """DGM-H Meta Agent: reviews strategy performance and proposes edits.

    Uses the system's own LLM consciousness to:
    1. Look at MetaMemory success rates per strategy
    2. Identify underperforming observation/generation/deployment patterns
    3. Propose concrete edits to the MetaStrategy configuration
    4. Apply edits with versioning and rollback capability

    Engram [3] exploration reward: periodically forces cold/random strategy
    trials to prevent gating from over-specializing on historically successful
    strategies that may have decayed (the "hot-to-cold advantage flip").
    """

    DEFAULT_EXPLORATION_RATE = 0.15
    MIN_EXPLORATION_RATE = 0.05
    EXPLORATION_DECAY = 0.995

    def __init__(self, consciousness: Any = None):
        self.consciousness = consciousness
        self.strategy = MetaStrategy()
        self._memory = get_meta_memory()
        self.exploration_rate = self.DEFAULT_EXPLORATION_RATE
        self._exploration_count = 0
        self._exploitation_count = 0
        self._last_exploration_decay = time.time()
        self._load()

    @property
    def current(self) -> MetaStrategy:
        return self.strategy

    async def review_and_evolve(self, domain: str = "") -> dict[str, Any]:
        """The core DGM-H loop: review strategy performance and propose edits.

        Now includes gating calibration (Engram [3]) and exploration ratio.
        Returns a dict with: changed (bool), changes_applied (list), new_version (int)
        """
        stats = self._memory.get_stats()
        efficiency = self._memory.get_process_efficiency(domain)
        underperforming = self._memory.underperforming_strategies(domain)
        gating = self._memory.get_gating_stats()
        decaying = self._find_decaying_strategies(domain)

        if not self.consciousness:
            return {"changed": False, "reason": "no_consciousness"}

        context = self._build_review_prompt(stats, efficiency, underperforming,
                                              gating, decaying)

        try:
            response = await self.consciousness.chain_of_thought(
                context, steps=2, temperature=0.4, max_tokens=2048,
            )
            edits = self._parse_strategy_edits(response)
        except Exception as e:
            logger.warning(f"MetaStrategy review failed: {e}")
            return {"changed": False, "error": str(e)}

        if not edits:
            return {"changed": False, "reason": "no_edits_proposed"}

        result = {"changed": False, "edits": edits}
        reason_parts = []
        if edits:
            if "exploration_rate" in edits:
                self.exploration_rate = float(edits.pop("exploration_rate"))
                reason_parts.append(f"exploration_rate={self.exploration_rate}")
            if edits:
                reason_parts.append(f"efficiency={efficiency.get('deploy_rate', 0)}")

        reason = f"Auto-review: {', '.join(reason_parts)}" if reason_parts else (
            f"Auto-review: efficiency={efficiency.get('deploy_rate', 0)}, "
            f"underperforming={len(underperforming)}")

        self.strategy.snapshot(reason)
        changed = self.strategy.apply(edits)
        if changed:
            self._save()
        result["changed"] = changed
        result["changes_applied"] = edits
        result["new_version"] = self.strategy._version_counter
        result["reason"] = reason
        return result

    def should_explore(self) -> bool:
        """Decide whether to explore a cold strategy instead of the top recommendation.

        Engram [3]: periodic exploration prevents gating from decaying into
        always picking the historically best strategy.
        """
        import random
        if random.random() < self.exploration_rate:
            self._exploration_count += 1
            return True
        self._exploitation_count += 1
        self._decay_exploration()
        return False

    def force_cold_exploration(self, strategy_type: str = "mutation",
                                domain: str = "") -> str | None:
        """Force a cold (low-success) strategy trial.

        Picks a strategy with sample count >= 3 but success rate < 0.4
        that hasn't been tried recently. Returns the strategy name or None.
        """
        from .meta_memory import get_meta_memory
        memory = get_meta_memory()
        all_recs = memory.recommend(strategy_type, domain=domain, top=20)

        cold = [r for r in all_recs
                if r["samples"] >= 3 and r["success_rate"] < 0.5]

        decayed = []
        for r in cold:
            decay_info = memory.strategy_decay_tracker(r["strategy"])
            if decay_info["trend"] == "decaying":
                decayed.append((r["strategy"], 2.0))
            else:
                decayed.append((r["strategy"], r["success_rate"]))

        decayed.sort(key=lambda x: x[1])
        return decayed[0][0] if decayed else None

    def try_explore(self, strategy_type: str = "mutation",
                    domain: str = "") -> str | None:
        """Try exploration: returns a cold strategy name if we should explore,
        or None if we should exploit the top recommendation.

        Also records the gating decision for calibration tracking.
        """
        if not self.should_explore():
            return None
        cold = self.force_cold_exploration(strategy_type, domain)
        if cold:
            self._memory.record_gating(
                strategy_name=cold,
                context_snapshot=f"explore_{strategy_type}_{domain}",
                recommended_as_appropriate=False,
                actual_success=False,
                domain=domain,
            )
        return cold

    def record_exploration_outcome(self, strategy: str, success: bool,
                                    domain: str = ""):
        """Record the outcome of an exploration trial for gating calibration."""
        self._memory.record_gating(
            strategy_name=strategy,
            context_snapshot=f"exploration_trial_{domain}",
            recommended_as_appropriate=False,
            actual_success=success,
            domain=domain,
        )

    def record_exploitation_outcome(self, strategy: str, success: bool,
                                     domain: str = ""):
        """Record the outcome of an exploitation (top-pick) for gating calibration."""
        self._memory.record_gating(
            strategy_name=strategy,
            context_snapshot=f"exploitation_{domain}",
            recommended_as_appropriate=True,
            actual_success=success,
            domain=domain,
        )

    @property
    def exploration_ratio(self) -> float:
        total = self._exploration_count + self._exploitation_count
        return round(self._exploration_count / max(total, 1), 3)

    def _decay_exploration(self):
        """Decay exploration rate over time — explore less as system matures."""
        now = time.time()
        if now - self._last_exploration_decay > 300:
            self.exploration_rate = max(
                self.MIN_EXPLORATION_RATE,
                self.exploration_rate * self.EXPLORATION_DECAY,
            )
            self._last_exploration_decay = now

    def _build_review_prompt(self, stats: dict, efficiency: dict,
                              underperforming: list[dict],
                              gating: dict | None = None,
                              decaying: list[dict] | None = None) -> str:
        current = self.strategy.describe_changes()
        cal = gating.get("calibration", {}) if gating else {}
        misgated = gating.get("misgated", []) if gating else []
        prompt = (
            "你是DGM-H元代理(Meta Agent)。你的任务是审视当前系统的进化策略，"
            "并提出改进建议。\n\n"
            "=== 当前策略 ===\n"
            f"{current}\n"
            f"探索率: {self.exploration_rate} (探索/利用比: {self.exploration_ratio})\n\n"
            "=== 进化统计 ===\n"
            f"总记录: {stats.get('total_records', 0)}, "
            f"成功率: {stats.get('success_rate', 0)}, "
            f"总token: {stats.get('total_tokens', 0)}\n"
            f"每次成功部署消耗token: {efficiency.get('token_per_successful_deploy', 'N/A')}\n"
            f"部署率: {efficiency.get('deploy_rate', 'N/A')}\n"
            f"低效策略: {json.dumps(underperforming[:5], ensure_ascii=False) if underperforming else '无'}\n"
        )
        if cal:
            prompt += (
                f"门控校准分: {cal.get('score', '?')} (样本={cal.get('samples', 0)}), "
                f"误判率={cal.get('false_positives', 0) + cal.get('false_negatives', 0)}/"
                f"{cal.get('samples', 1)}\n"
            )
        if misgated:
            prompt += f"误判策略: {json.dumps(misgated[:3], ensure_ascii=False)}\n"
        if decaying:
            prompt += f"衰退策略: {json.dumps(decaying[:3], ensure_ascii=False)}\n"
        prompt += (
            "\n=== 任务 ===\n"
            "分析以上数据，提出具体的策略改进。输出JSON格式:\n"
            '{"observation": {"hub_max_count": 3}, "generation": {"temperature": 0.7}, '
            '"deployment": {"quality_threshold": 0.7}, "exploration_rate": 0.1}\n\n'
            "只修改需要调整的字段。指导原则:\n"
            "1. 门控校准分<0.7时，增加exploration_rate(最多0.3)以发现误判策略\n"
            "2. 如果有衰退策略，尝试将其从推荐中移除或降低观察权重\n"
            "3. 如果部署率高且稳定，降低exploration_rate至0.05\n"
            "4. 如果token消耗过高，降低temperature、增加cot_steps\n"
            "输出只包含JSON，不要有其他内容。"
        )
        return prompt

    def _find_decaying_strategies(self, domain: str = "") -> list[dict[str, Any]]:
        decaying = []
        for rec in self._memory.recommend("mutation", domain=domain, top=10):
            tracker = self._memory.strategy_decay_tracker(rec["strategy"])
            if tracker["decaying"]:
                decaying.append({
                    "strategy": rec["strategy"],
                    "early_rate": tracker["early_success_rate"],
                    "late_rate": tracker["late_success_rate"],
                    "samples": tracker["total_samples"],
                })
        return decaying

    def _parse_strategy_edits(self, response: str) -> dict:
        try:
            if "```json" in response:
                start = response.index("```json") + 7
                end = response.index("```", start)
                response = response[start:end]
            elif "```" in response:
                start = response.index("```") + 3
                end = response.index("```", start)
                response = response[start:end]
            response = response.strip()
            if response.startswith("{"):
                return json.loads(response)
        except (ValueError, json.JSONDecodeError) as e:
            logger.debug(f"Parse strategy edits failed: {e}")
        return {}

    def rollback(self, to_version: int | None = None) -> bool:
        """Rollback to a previous strategy version."""
        if not self._versions:
            return False
        target = None
        if to_version:
            for v in self._versions:
                if v.version == to_version:
                    target = v
                    break
        else:
            target = self._versions[-1]
        if not target:
            return False
        self.strategy.observation = copy.deepcopy(target.observation)
        self.strategy.generation = copy.deepcopy(target.generation)
        self.strategy.deployment = copy.deepcopy(target.deployment)
        self._version_counter += 1
        self.strategy._versions = self._versions
        self.strategy._version_counter = self._version_counter
        self._save()
        logger.info(f"MetaStrategy rolled back to v{target.version}: {target.reason}")
        return True

    def get_status(self) -> dict[str, Any]:
        return {
            "version": self.strategy._version_counter,
            "total_versions": len(self.strategy._versions),
            "observation": self.strategy.observation.to_dict(),
            "generation": self.strategy.generation.to_dict(),
            "deployment": self.strategy.deployment.to_dict(),
            "exploration_rate": self.exploration_rate,
            "exploration_ratio": self.exploration_ratio,
            "gating_calibration": self._memory.gating_calibration,
        }

    # ── MSM: Agent Spec Self-Evolution ──

    async def review_spec(self, domain: str = "") -> dict[str, Any]:
        """MSM-style: periodically review and evolve the Agent Spec.

        Uses LLM to analyze behavioral data (gating calibration, tool stats,
        misgated strategies) and propose edits to the Agent Spec principles
        — updating rules, rationale, boundaries, and priorities.

        This is the MSM "midtraining" equivalent for an Agent: instead of
        retraining the model, we refine the behavioral principles document
        that shapes how the LLM generalizes from instructions.
        """
        from .model_spec import get_agent_spec
        spec = get_agent_spec()

        if not self.consciousness:
            return {"reviewed": False, "reason": "no_consciousness"}

        gating = self._memory.get_gating_stats()
        cal = gating.get("calibration", {})
        tool_stats = self._memory.get_tool_stats()
        decaying = self._find_decaying_strategies(domain)
        misgated = self._memory.misgated_strategies()

        prompt = (
            "你是Agent Spec审查员。根据系统的实际行为数据，"
            "审视当前的Agent行为原则是否需要更新。\n\n"
            "=== 当前行为原则 ===\n"
            f"{spec.format_for_injection()}\n\n"
            "=== 实际行为数据 ===\n"
            f"门控校准分: {cal.get('score', '?')}/1.0 "
            f"(样本={cal.get('samples', 0)}, "
            f"误判={cal.get('false_positives', 0)+cal.get('false_negatives', 0)})\n"
            f"工具事件: {tool_stats.get('total_events', 0)}次, "
            f"错误={tool_stats.get('error_count', 0)}, "
            f"拦截={tool_stats.get('intercepted_count', 0)}\n"
            f"衰退策略: {len(decaying) if decaying else 0}个\n"
            f"误判策略: {len(misgated) if misgated else 0}个\n\n"
            "=== 任务 ===\n"
            "分析行为数据和原则之间的差距。如果某个原则被频繁违反，"
            "它的规则可能需要更明确，或优先级需要调整。\n"
            "如果某个原则从未触发问题，它的优先级可以降低。\n\n"
            "输出JSON格式(只修改需要调整的原则):\n"
            '{"A": {"rule": "新规则文本", "priority": 9}, "C": {"why": "新的理由"}}\n\n'
            "修改指导:\n"
            "1. 如果某类错误频繁(如工具误用)，加强对应原则的规则描述\n"
            "2. 如果某原则的'为什么'没有解释清楚后果，补充具体危害\n"
            "3. 如果某个原则从未被违反，可以降低优先级(减少token占用)\n"
            "4. 如果校准分<0.7，加强安全相关原则(C/D)的优先级\n"
            "输出只包含JSON，不要有其他内容。"
        )

        try:
            response = await self.consciousness.chain_of_thought(
                prompt, steps=2, temperature=0.3, max_tokens=2048,
            )
            edits = self._parse_spec_edits(response)
        except Exception as e:
            logger.warning(f"Spec review failed: {e}")
            return {"reviewed": False, "error": str(e)}

        if not edits:
            return {"reviewed": False, "reason": "no_edits_proposed"}

        changed = spec.apply_updates(edits)
        if changed:
            logger.info(f"AgentSpec updated: {changed} principles changed")
        return {
            "reviewed": True,
            "principles_changed": changed,
            "edits": edits,
            "spec_version": spec._version,
        }

    @staticmethod
    def _parse_spec_edits(response: str) -> dict:
        import json as _json
        try:
            if "```json" in response:
                start = response.index("```json") + 7
                end = response.index("```", start)
                response = response[start:end]
            elif "```" in response:
                start = response.index("```") + 3
                end = response.index("```", start)
                response = response[start:end]
            response = response.strip()
            if response.startswith("{"):
                return _json.loads(response)
        except (ValueError, _json.JSONDecodeError):
            pass
        return {}

    def _save(self):
        try:
            STRATEGY_DIR.mkdir(parents=True, exist_ok=True)
            strategy_dict = self.strategy.to_dict()
            strategy_dict["exploration_rate"] = self.exploration_rate
            strategy_dict["exploration_count"] = self._exploration_count
            strategy_dict["exploitation_count"] = self._exploitation_count
            STRATEGY_FILE.write_text(json.dumps(
                strategy_dict, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"MetaStrategy save: {e}")

    def _load(self):
        try:
            if STRATEGY_FILE.exists():
                data = json.loads(STRATEGY_FILE.read_text())
                self.strategy.from_dict(data)
                self.exploration_rate = data.get("exploration_rate",
                                                  self.DEFAULT_EXPLORATION_RATE)
                self._exploration_count = data.get("exploration_count", 0)
                self._exploitation_count = data.get("exploitation_count", 0)
                self.strategy._versions = []
                self.strategy._version_counter = 0
        except Exception as e:
            logger.debug(f"MetaStrategy load: {e}")


_meta_strategy_engine: MetaStrategyEngine | None = None


def get_meta_strategy_engine(consciousness=None) -> MetaStrategyEngine:
    global _meta_strategy_engine
    if _meta_strategy_engine is None:
        _meta_strategy_engine = MetaStrategyEngine(consciousness)
    elif consciousness and _meta_strategy_engine.consciousness is None:
        _meta_strategy_engine.consciousness = consciousness
    return _meta_strategy_engine
