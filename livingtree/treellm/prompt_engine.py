"""PromptEngine — DSPy-style declarative prompt optimization for LivingTree.

Inspired by DSPy (Stanford NLP), adapted for LivingTree's unified architecture.

Core concepts:
  Signature   → typed input/output field specification for a capability
  Module      → composable prompt+execution component (ChainOfThought, ReAct)
  Optimizer   → feedback-driven prompt improvement (BootstrapFewShot)
  Compiler    → auto-optimize prompts against metrics (depth_grade, user_signal)

Integration with existing systems:
  CapabilityBus       → auto-discover Signatures from registered capabilities
  RecordingEngine     → use recorded traces as few-shot training examples
  DeepProbe           → strategy matrix for cognitive forcing (pre-inference)
  AutoPrompt          → Thompson Sampling for prompt selection (post-optimize)
  UserSignal          → implicit user satisfaction as optimization metric
  DepthGrading        → reasoning depth as quality metric
  PromptVersioning    → store compiled prompt versions with performance tracking

Architecture:
  1. Signature = define INPUT/OUTPUT fields for each capability
  2. Module = compose Signatures into executable prompt chains
  3. Optimizer = BootstrapFewShot from recording traces + metric feedback
  4. Compiler = select best prompt variant via Thompson Sampling
"""

from __future__ import annotations

import asyncio
import copy
import json
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger

PROMPTS_FILE = Path(".livingtree/compiled_prompts.json")
FEWSHOT_FILE = Path(".livingtree/fewshot_examples.json")


# ═══ Signatures ════════════════════════════════════════════════════


@dataclass
class InputField:
    name: str
    type: str = "str"       # str | int | float | bool | list | dict
    description: str = ""
    required: bool = True


@dataclass
class OutputField:
    name: str
    type: str = "str"
    description: str = ""
    validator: Callable = None  # Optional: validate output format


@dataclass
class Signature:
    """Declarative specification of what a prompt module should do."""
    name: str                          # "tool:web_search", "skill:tabular_reason"
    description: str = ""
    inputs: list[InputField] = field(default_factory=list)
    outputs: list[OutputField] = field(default_factory=list)
    examples: list[dict] = field(default_factory=list)   # Few-shot examples
    instructions: str = ""             # Base instructions (optimized over time)
    chain_of_thought: bool = True      # Enable reasoning chain
    strategy_hints: list[str] = field(default_factory=list)  # DeepProbe strategies

    def input_schema(self) -> dict:
        return {f.name: f.type for f in self.inputs}

    def output_schema(self) -> dict:
        return {f.name: f.type for f in self.outputs}

    def to_prompt(self, include_examples: bool = True, max_examples: int = 3) -> str:
        """Build a system prompt from this signature."""
        parts = [self.instructions]

        # Input/output specification
        if self.inputs:
            parts.append("\n输入参数:")
            for f in self.inputs:
                req = "(必填)" if f.required else "(可选)"
                parts.append(f"  - {f.name}: {f.type} {req} — {f.description}")

        if self.outputs:
            parts.append("\n输出格式 (严格遵循):")
            parts.append("{" + ", ".join(f'"{f.name}": {f.type}' for f in self.outputs) + "}")

        if self.chain_of_thought:
            parts.append("\n请先推理,再给出最终结果。")

        # Few-shot examples
        if include_examples and self.examples:
            parts.append("\n示例:")
            for ex in self.examples[-max_examples:]:
                parts.append(f"  输入: {json.dumps({k:v for k,v in ex.items() if k != 'output'}, ensure_ascii=False)}")
                parts.append(f"  输出: {json.dumps(ex.get('output', ex.get('result')), ensure_ascii=False)[:500]}")
                parts.append("")

        return "\n".join(parts)

    def add_example(self, input_data: dict, output_data: Any, score: float = 0.5) -> None:
        """Add a training example with quality score."""
        self.examples.append({
            **{k: v for k, v in input_data.items()},
            "output": str(output_data)[:2000],
            "score": score,
        })
        # Keep best 20 examples
        self.examples.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        if len(self.examples) > 20:
            self.examples = self.examples[:20]


# ═══ Prompt Modules ════════════════════════════════════════════════


class PromptModule:
    """A composable prompt+execution unit. Like DSPy Module but async."""

    def __init__(self, signature: Signature, name: str = ""):
        self.signature = signature
        self.name = name or signature.name
        self.prompt_template: str = ""   # Optimized prompt text
        self._optimize_count = 0

    def build_prompt(self, **inputs) -> str:
        """Build the full prompt for execution."""
        if self.prompt_template:
            base = self.prompt_template
        else:
            base = self.signature.to_prompt()

        # Inject input values
        for k, v in inputs.items():
            placeholder = f"{{{k}}}"
            if placeholder in base:
                base = base.replace(placeholder, str(v)[:2000])

        return base

    async def __call__(self, executor: Callable, **inputs) -> Any:
        """Execute the module: build prompt → call executor → return result."""
        prompt = self.build_prompt(**inputs)
        result = await executor(prompt, **inputs)
        return result


class ChainOfThought(PromptModule):
    """Module that forces step-by-step reasoning before final output."""

    def __init__(self, signature: Signature):
        super().__init__(signature)
        self.signature.chain_of_thought = True
        self.signature.instructions += (
            "\n请按以下步骤推理:"
            "\n1. 理解输入目标和约束"
            "\n2. 列出可能的方案和权衡"
            "\n3. 选择最优方案并执行"
            "\n4. 验证结果并输出"
        )


class ReAct(PromptModule):
    """Module that interleaves reasoning and tool actions."""

    def __init__(self, signature: Signature, available_tools: list[str] = None):
        super().__init__(signature)
        self.available_tools = available_tools or []
        tool_desc = "\n".join(f"  - {t}" for t in self.available_tools[:10])
        self.signature.instructions += (
            f"\n可用工具:\n{tool_desc}"
            "\n使用格式: <tool_call name=\"工具名\">参数</tool_call>"
            "\n每次工具调用后继续推理,直到得到最终答案。"
        )


# ═══ PromptOptimizer ══════════════════════════════════════════════


class PromptOptimizer:
    """Metric-driven prompt optimization using BootstrapFewShot pattern.

    Leverages RecordingEngine traces as training data, uses UserSignal +
    DepthGrading as optimization metrics, and updates prompts via a simple
    candidate-generation-and-selection loop.
    """

    def __init__(self):
        self._signatures: dict[str, Signature] = {}
        self._optimize_count = 0
        self._load()

    # ── Signature Management ───────────────────────────────────────

    def register(self, sig: Signature) -> None:
        self._signatures[sig.name] = sig

    def get(self, name: str) -> Optional[Signature]:
        return self._signatures.get(name)

    def list_all(self) -> list[str]:
        return list(self._signatures.keys())

    async def discover_from_capabilities(self) -> int:
        """Auto-generate Signatures from CapabilityBus."""
        try:
            from .capability_bus import get_capability_bus
            bus = get_capability_bus()
            caps = await bus.list_all()
            count = 0
            for cap in caps:
                if cap["id"] in self._signatures:
                    continue
                sig = Signature(
                    name=cap["id"],
                    description=cap.get("description", ""),
                    inputs=[InputField(name="input", type="str", description=cap.get("description", ""))],
                    outputs=[OutputField(name="result", type="str", description="执行结果")],
                )
                self._signatures[sig.name] = sig
                count += 1
            if count:
                self._save()
            return count
        except Exception as e:
            logger.debug(f"PromptEngine discover: {e}")
            return 0

    # ── Bootstrap Few-Shot from Recordings ─────────────────────────

    async def bootstrap_from_recordings(self) -> int:
        """Compile few-shot examples from RecordingEngine traces."""
        try:
            from .recording_engine import get_recording_engine
            engine = get_recording_engine()
            recordings = engine.list_recordings()
            bootstrapped = 0

            for rec in recordings[-20:]:
                for evt_data in engine._recordings.get(rec["id"], None) and [] or []:
                    pass

                # Load full recording
                rec_obj = engine._recordings.get(rec["id"])
                if not rec_obj:
                    continue

                for evt in rec_obj.events:
                    if not evt.capability:
                        continue
                    sig = self._signatures.get(evt.capability)
                    if not sig:
                        continue
                    if evt.result_error or not evt.result:
                        continue
                    # Add as few-shot example with quality from metadata
                    quality = evt.metadata.get("user_signal", 0.5) if evt.metadata else 0.5
                    sig.add_example(
                        input_data=evt.params,
                        output_data=evt.result,
                        score=quality,
                    )
                    bootstrapped += 1

            if bootstrapped:
                self._save()
                logger.info(f"PromptEngine: bootstrapped {bootstrapped} examples from recordings")
            return bootstrapped
        except Exception as e:
            logger.debug(f"PromptEngine bootstrap: {e}")
            return 0

    # ── Optimize ───────────────────────────────────────────────────

    async def optimize(self, signature_name: str, metric_fn: Callable = None,
                       rounds: int = 3) -> Optional[Signature]:
        """Optimize a signature's prompt instructions via candidate generation.

        Generates candidate instruction variants, evaluates each against examples
        using the metric function, and selects the best performer.
        """
        sig = self._signatures.get(signature_name)
        if not sig:
            return None

        self._optimize_count += 1

        # Generate candidate instruction variants
        candidates = self._generate_candidates(sig, rounds)

        # Evaluate each candidate against examples
        best_sig = sig
        best_score = 0.0

        for candidate in candidates:
            test_sig = copy.deepcopy(sig)
            test_sig.instructions = candidate

            # Score this candidate against stored examples
            if metric_fn:
                score = await metric_fn(test_sig)
            else:
                score = self._default_metric(test_sig)

            if score > best_score:
                best_score = score
                best_sig = test_sig

        if best_sig != sig:
            self._signatures[signature_name] = best_sig
            logger.info(
                f"PromptEngine: optimized '{signature_name}' "
                f"(score: {best_score:.3f}, candidates: {len(candidates)})"
            )
            self._save()

        return best_sig

    def _generate_candidates(self, sig: Signature, rounds: int) -> list[str]:
        """Generate instruction variants by heuristics (real DSPy would use LLM)."""
        candidates = [sig.instructions]

        strategies = [
            ("Be concise and direct. Prioritize accuracy over verbosity.",
             lambda i: i + "\n核心原则: 简洁准确,直击要点。"),
            ("Use step-by-step reasoning. Show your work before concluding.",
             lambda i: i + "\n推理要求: 逐步分析,展示推理过程,再给结论。"),
            ("Consider edge cases and alternatives. What could go wrong?",
             lambda i: i + "\n反思要求: 考虑边界情况和替代方案,说明潜在风险。"),
            ("Provide actionable output. The result should be immediately usable.",
             lambda i: i + "\n输出要求: 结果可直接使用,格式规范,无冗余。"),
            ("Include confidence assessment. How sure are you about each part?",
             lambda i: i + "\n置信度: 对每个关键结论标注确信程度。"),
        ]

        for _, apply_fn in strategies[:rounds]:
            candidates.append(apply_fn(sig.instructions))

        return candidates[:rounds + 1]

    async def _default_metric(self, sig: Signature) -> float:
        """Default metric: example quality average."""
        if not sig.examples:
            return 0.5
        return sum(e.get("score", 0.5) for e in sig.examples) / len(sig.examples)

    def feedback(self, signature_name: str, input_data: dict,
                 output_data: Any, success: bool, depth_grade: float = 0.5) -> None:
        """Record feedback to update examples and metrics."""
        sig = self._signatures.get(signature_name)
        if not sig:
            return
        quality = 0.6 * depth_grade + 0.4 * (1.0 if success else 0.0)
        sig.add_example(input_data, output_data, quality)
        if len(sig.examples) % 10 == 0:
            self._save()

    # ── Persistence ────────────────────────────────────────────────

    def _save(self):
        try:
            PROMPTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                name: {
                    "instructions": s.instructions,
                    "examples": s.examples[-20:],
                    "chain_of_thought": s.chain_of_thought,
                    "strategy_hints": s.strategy_hints,
                }
                for name, s in self._signatures.items()
                if s.examples or s.instructions
            }
            PROMPTS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"PromptEngine save: {e}")

    def _load(self):
        try:
            if PROMPTS_FILE.exists():
                data = json.loads(PROMPTS_FILE.read_text())
                for name, sd in data.items():
                    sig = Signature(
                        name=name,
                        instructions=sd.get("instructions", ""),
                        examples=sd.get("examples", []),
                        chain_of_thought=sd.get("chain_of_thought", True),
                        strategy_hints=sd.get("strategy_hints", []),
                    )
                    self._signatures[name] = sig
                logger.info(f"PromptEngine: loaded {len(self._signatures)} signatures")
        except Exception:
            pass


# ═══ PromptCompiler ═══════════════════════════════════════════════


class PromptCompiler:
    """Compile the best prompt for a given capability + context.

    Uses Thompson Sampling (leverages AutoPrompt's existing mechanism)
    to select the optimal prompt variant. Falls back to signature.instructions
    if no compiled variant exists.
    """

    def __init__(self, optimizer: PromptOptimizer):
        self._optimizer = optimizer
        self._variant_stats: dict[str, dict[str, dict]] = defaultdict(
            lambda: {"alpha": 2.0, "beta": 2.0, "text": ""}
        )
        self._last_variant: dict[str, str] = {}

    def compile(self, capability_id: str, context: dict = None) -> str:
        """Compile (select) the best prompt for this capability."""
        sig = self._optimizer.get(capability_id)
        if not sig:
            return ""

        # Get cached variant stats for this capability
        variants = self._variant_stats.get(capability_id, {})

        if not variants:
            # First call: use signature instructions directly
            prompt = sig.to_prompt(include_examples=True, max_examples=3)
            self._variant_stats[capability_id]["default"] = {
                "alpha": 3.0, "beta": 2.0, "text": prompt,
            }
            self._last_variant[capability_id] = "default"
            return prompt

        # Thompson Sampling: select best variant
        samples = []
        for vid, v in variants.items():
            score = random.betavariate(max(v["alpha"], 0.1), max(v["beta"], 0.1))
            samples.append((vid, score))

        samples.sort(key=lambda x: -x[1])
        best_vid = samples[0][0]
        self._last_variant[capability_id] = best_vid
        return variants[best_vid]["text"]

    def feedback(self, capability_id: str, quality: float) -> None:
        """Update variant stats based on execution quality."""
        vid = self._last_variant.get(capability_id, "default")
        v = self._variant_stats[capability_id][vid]
        reward = min(1.0, max(0.0, quality))
        v["alpha"] += reward * 3.0
        v["beta"] += (1.0 - reward) * 3.0

    def stats(self) -> dict:
        return {
            name: {vid: round(s["alpha"] / max(s["alpha"] + s["beta"], 0.01), 2)
                   for vid, s in variants.items()}
            for name, variants in self._variant_stats.items()
        }


# ═══ Singleton ════════════════════════════════════════════════════

_engine: Optional[PromptOptimizer] = None
_compiler: Optional[PromptCompiler] = None


def get_prompt_engine() -> PromptOptimizer:
    global _engine
    if _engine is None:
        _engine = PromptOptimizer()
    return _engine


def get_prompt_compiler() -> PromptCompiler:
    global _compiler
    if _compiler is None:
        _compiler = PromptCompiler(get_prompt_engine())
    return _compiler


__all__ = [
    "Signature", "InputField", "OutputField",
    "PromptModule", "ChainOfThought", "ReAct",
    "PromptOptimizer", "PromptCompiler",
    "get_prompt_engine", "get_prompt_compiler",
]
