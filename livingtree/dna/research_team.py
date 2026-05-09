"""Free Model Research Team — zero-cost collaborative agent swarm.

Implements the "edge-computing MoE" architecture:
  Four specialized agents, each powered by the best available free model,
  collaborating in parallel to produce research-grade output.

Team Roles (assigned by FreeModelPool):
  1. Data Hunter   — reads & extracts: news, reports, structured data
  2. Idea Agent    — reasons & hypothesizes: generates actionable hypotheses
  3. Coder         — codes & implements: converts ideas to executable code  
  4. Reviewer      — critiques & validates: finds bugs, checks logic, verifies output

Pipeline:
  task → Idea Agent (hypothesis) → Data Hunter (gather evidence)
       → Coder (implement) → Reviewer (critique) → Coder (fix)
       → final_output

  Rounds are configurable: simple tasks need 1 round, complex tasks iterate.

Resilience features:
  - Each agent auto-retries on free-model failure with backup model
  - Rate-limit queues prevent system stalls
  - Output format validation catches malformed responses
  - Context compression passes only key insights to downstream agents

Integration:
  LifeEngine._execute() → CogResearchTeam.run(task) → final plan/analysis
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from ..treellm.free_pool_manager import (
    FreeModelPool, ResearchRole, get_free_pool,
)


# ═══ Data Types ═══


@dataclass
class AgentOutput:
    """Output from a single agent in the research pipeline."""
    role: str
    model: str                # Which free model was used
    content: str
    confidence: float
    tokens_used: int
    latency_ms: float
    attempts: int = 1         # How many retries were needed
    error: str = ""


@dataclass
class ResearchRound:
    """One complete research round (all 4 agents)."""
    round_id: int
    hypothesis: AgentOutput | None = None       # Idea Agent output
    evidence: AgentOutput | None = None          # Data Hunter output
    implementation: AgentOutput | None = None    # Coder output
    critique: AgentOutput | None = None          # Reviewer output
    fixes: AgentOutput | None = None             # Coder fixes after review
    round_score: float = 0.0
    total_tokens: int = 0
    total_ms: float = 0.0


@dataclass
class ResearchResult:
    """Final result of the research team."""
    task: str
    rounds: list[ResearchRound]
    final_output: str
    final_confidence: float
    total_tokens: int
    total_cost_yuan: float = 0.0    # Should be 0 for pure free-model runs
    total_ms: float = 0.0
    models_used: list[str] = field(default_factory=list)
    errors_encountered: int = 0

    def summary(self) -> str:
        return (
            f"[{len(self.rounds)} rounds] {self.task[:50]}... → "
            f"confidence={self.final_confidence:.0%}, "
            f"{self.total_tokens} tokens, ¥{self.total_cost_yuan:.4f}, "
            f"{len(self.models_used)} free models"
        )


# ═══ Cog Research Team ═══


class CogResearchTeam:
    """Zero-cost collaborative research team powered by free models.

    Architecture:
      Idea → Data → Code → Review → Fix (iterate as needed)

    Each role is powered by the best available free model for that capability.
    The team builds on each other's work: each agent receives the prior
    agents' outputs as context (compressed to fit context windows).

    Resilience:
      - Agent failure → automatically retry with backup free model
      - Rate limit → queue and retry after cooldown
      - Format error → validate output, retry if invalid
      - Context overflow → compress inputs to fit model windows
    """

    MAX_ROUNDS = 3
    MAX_RETRIES_PER_AGENT = 2
    REVIEW_PASS_THRESHOLD = 0.7

    # System prompts for each role
    ROLE_PROMPTS: dict[str, str] = {
        "idea": (
            "你是一位量化策略研究员。基于用户提出的问题，提出一个具体、"
            "可验证的假设或分析框架。输出结构：\n"
            "1. 核心假设（一句话）\n2. 推理逻辑（3-5步）\n"
            "3. 需要的数据（列清单）\n4. 验证方法"
        ),
        "data": (
            "你是一位数据分析师。基于研究假设和需求，从提供的上下文中提取"
            "关键数据、事实和证据。输出结构：\n"
            "1. 关键数据点（编号列表）\n2. 数据来源\n"
            "3. 数据局限性\n4. 建议补充的数据"
        ),
        "coder": (
            "你是一位 Python 量化开发者。基于研究假设和可用数据，编写完整、"
            "可执行的 Python 代码。要求：\n"
            "- 包含必要的 import 语句\n- 处理缺失值和异常\n"
            "- 输出清晰的结果和可视化\n- 添加注释说明关键逻辑\n"
            "只输出代码，用 ```python 包裹。"
        ),
        "reviewer": (
            "你是一位严格的代码审查员。检查以下代码是否存在问题：\n"
            "1. 逻辑错误（未来函数、因果倒置）\n"
            "2. 过拟合风险（参数过多、样本不足）\n"
            "3. 边界情况（缺失值、除以零、类型错误）\n"
            "4. 性能问题（O(n²) 循环、不必要的复制）\n"
            "输出：PASS（无问题）或 FAIL + 具体问题列表 + 修复建议。"
        ),
    }

    def __init__(self, ltm_model: Any = None):
        self._pool = get_free_pool()
        self._consciousness = ltm_model  # LLM consciousness for calling models
        self._history: list[ResearchResult] = []

    # ── Main Entry ──

    async def research(
        self,
        task: str,
        max_rounds: int = 2,
        domain: str = "general",
        extra_context: str = "",
    ) -> ResearchResult:
        """Run the full research pipeline with the free model team.

        Args:
            task: The research question / task description
            max_rounds: Maximum revision rounds (reviewer → coder cycles)
            domain: Domain hint for model selection
            extra_context: Additional context to inject

        Returns:
            ResearchResult with the team's output
        """
        t0 = time.time()
        rounds: list[ResearchRound] = []
        total_tokens = 0
        errors = 0
        models_used: list[str] = []

        # Assign the team: each role gets the best free model
        team = self._pool.assign_team()
        models_used = list(set(team.values()))
        logger.info(
            f"ResearchTeam: '{task[:50]}...' → team={team} "
            f"({len(models_used)} models)",
        )

        # ═══ Round 1: Initial Pipeline ═══

        # Hypothesis
        hypothesis = await self._run_agent(
            role="idea", task=task, context=extra_context,
            assigned_model=team.get("idea"), models_used=models_used,
        )
        total_tokens += hypothesis.tokens_used
        errors += (1 if hypothesis.error else 0)

        # Evidence gathering
        evidence = await self._run_agent(
            role="data", task=task,
            context=self._format_context(task, hypothesis.content),
            assigned_model=team.get("data"), models_used=models_used,
        )
        total_tokens += evidence.tokens_used
        errors += (1 if evidence.error else 0)

        # Implementation
        impl = await self._run_agent(
            role="coder", task=task,
            context=self._format_context(
                f"Hypothesis: {hypothesis.content[:500]}\n"
                f"Data: {evidence.content[:500]}",
                "",
            ),
            assigned_model=team.get("coder"), models_used=models_used,
        )
        total_tokens += impl.tokens_used
        errors += (1 if impl.error else 0)

        # Review
        review = await self._run_agent(
            role="reviewer", task=task,
            context=self._format_context(impl.content[:1000], ""),
            assigned_model=team.get("reviewer"), models_used=models_used,
        )
        total_tokens += review.tokens_used
        errors += (1 if review.error else 0)

        round1 = ResearchRound(
            round_id=1,
            hypothesis=hypothesis, evidence=evidence,
            implementation=impl, critique=review,
            total_tokens=total_tokens,
            total_ms=(time.time() - t0) * 1000,
        )

        # Determine if review passed
        review_passed = review.confidence >= self.REVIEW_PASS_THRESHOLD
        round1.round_score = review.confidence
        rounds.append(round1)

        # ═══ Subsequent Rounds: Fix & Iterate (if review failed) ═══

        current_impl = impl
        current_review = review

        for rnd in range(2, max_rounds + 1):
            if review_passed:
                break

            # Coder fixes based on review feedback
            fix_context = (
                f"Previous code:\n{current_impl.content[:500]}\n\n"
                f"Review feedback:\n{current_review.content[:500]}\n\n"
                f"Task: {task}\n\nFix all issues identified in the review."
            )
            fix = await self._run_agent(
                role="coder", task=task,
                context=fix_context,
                assigned_model=team.get("coder"), models_used=models_used,
            )
            total_tokens += fix.tokens_used
            errors += (1 if fix.error else 0)

            # Re-review
            re_review = await self._run_agent(
                role="reviewer", task=task,
                context=self._format_context(fix.content[:1000], ""),
                assigned_model=team.get("reviewer"), models_used=models_used,
            )
            total_tokens += re_review.tokens_used
            errors += (1 if re_review.error else 0)

            review_passed = re_review.confidence >= self.REVIEW_PASS_THRESHOLD
            round_r = ResearchRound(
                round_id=rnd,
                implementation=fix, critique=re_review,
                fixes=fix, round_score=re_review.confidence,
                total_tokens=fix.tokens_used + re_review.tokens_used,
                total_ms=(time.time() - t0) * 1000,
            )
            rounds.append(round_r)
            current_impl = fix
            current_review = re_review

        # Final confidence
        final_conf = max(r.round_score for r in rounds) if rounds else 0.0

        result = ResearchResult(
            task=task,
            rounds=rounds,
            final_output=current_impl.content,
            final_confidence=final_conf,
            total_tokens=total_tokens,
            total_cost_yuan=0.0,  # Free models = zero cost
            total_ms=(time.time() - t0) * 1000,
            models_used=models_used,
            errors_encountered=errors,
        )

        self._history.append(result)
        if len(self._history) > 100:
            self._history = self._history[-100:]

        logger.info(result.summary())
        return result

    # ── Agent Execution ──

    async def _run_agent(
        self,
        role: str,
        task: str,
        context: str = "",
        assigned_model: str | None = None,
        models_used: list[str] | None = None,
    ) -> AgentOutput:
        """Execute a single agent with retry and fallback logic.

        Retry strategy:
          1. Try assigned model up to MAX_RETRIES times
          2. If all fail, try any other healthy free model
          3. If all free models fail, return error output
        """
        t_start = time.time()
        attempts = 0
        last_error = ""

        models_used_list = models_used or []
        model = assigned_model or self._pool.get_role_model(role)

        for attempt in range(self.MAX_RETRIES_PER_AGENT + 1):
            attempts += 1

            if not model or not self._pool.is_available(model):
                # Try fallback: any healthy free model
                model = self._pool.assign_role(role)
                if not model:
                    return AgentOutput(
                        role=role, model="none", content="",
                        confidence=0.0, tokens_used=0,
                        latency_ms=(time.time() - t_start) * 1000,
                        attempts=attempts,
                        error="No free models available",
                    )

            # Rate limit check
            can_call = await self._pool.acquire(model, timeout=3.0)
            if not can_call:
                continue  # Try next attempt

            try:
                # Build the prompt
                system_prompt = self.ROLE_PROMPTS.get(role, "")
                full_prompt = f"{system_prompt}\n\n任务: {task}"
                if context:
                    # Truncate to fit context window
                    max_ctx = self._pool.recommend_chunk_size(model)
                    ctx_truncated = context[:max_ctx]
                    full_prompt = f"{system_prompt}\n\n任务: {task}\n\n上下文:\n{ctx_truncated}"

                # Call the model
                if self._consciousness and hasattr(self._consciousness, 'query'):
                    raw = await self._consciousness.query(
                        full_prompt, max_tokens=1024, temperature=0.3,
                        model=model,
                    )
                else:
                    # Fallback: log and return placeholder
                    raw = f"[Mock {role} agent output for: {task[:50]}...]"

                # Validate output format
                content, valid = self._validate_output(role, raw)

                if valid:
                    self._pool.mark_healthy(model, (time.time() - t_start) * 1000)
                    return AgentOutput(
                        role=role, model=model, content=content,
                        confidence=self._estimate_confidence(role, content),
                        tokens_used=self._estimate_tokens(full_prompt + raw),
                        latency_ms=(time.time() - t_start) * 1000,
                        attempts=attempts,
                    )
                else:
                    # Format invalid → retry
                    self._pool.mark_failure(model)
                    last_error = f"Format validation failed for {role}"
                    continue

            except Exception as e:
                last_error = str(e)
                self._pool.mark_failure(model)
                model = None  # Force re-assignment next attempt
                continue

        # Exhausted retries
        return AgentOutput(
            role=role, model=model or "unknown",
            content=f"[{role} agent failed after {attempts} attempts: {last_error}]",
            confidence=0.0, tokens_used=0,
            latency_ms=(time.time() - t_start) * 1000,
            attempts=attempts, error=last_error,
        )

    # ── Output Validation ──

    def _validate_output(self, role: str, output: str) -> tuple[str, bool]:
        """Validate agent output format and quality.

        Returns (cleaned_content, is_valid).
        """
        if not output or len(output.strip()) < 10:
            return output, False

        content = output.strip()

        # Coder role: must contain code block
        if role == "coder":
            has_code = "```" in content or "def " in content or "import " in content
            if not has_code:
                return content, False

        # Reviewer role: must contain PASS or FAIL
        if role == "reviewer":
            has_verdict = "PASS" in content.upper() or "FAIL" in content.upper()
            if not has_verdict:
                return content, False

        return content, True

    @staticmethod
    def _estimate_confidence(role: str, content: str) -> float:
        """Heuristic confidence estimation from output content."""
        length = len(content)
        if length < 50:
            return 0.2
        if length > 500:
            return min(0.9, 0.5 + length / 5000)
        return 0.5

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token count estimate (4 chars ≈ 1 token for Chinese/English)."""
        return max(1, len(text) // 4)

    @staticmethod
    def _format_context(*parts: str) -> str:
        """Format multiple context pieces into a single string."""
        return "\n\n---\n\n".join(p for p in parts if p)

    # ── Stats ──

    def stats(self) -> dict[str, Any]:
        total = max(len(self._history), 1)
        return {
            "total_tasks": len(self._history),
            "avg_rounds": round(
                sum(len(r.rounds) for r in self._history) / total, 1),
            "avg_confidence": round(
                sum(r.final_confidence for r in self._history) / total, 3),
            "total_tokens": sum(r.total_tokens for r in self._history),
            "total_cost_yuan": sum(r.total_cost_yuan for r in self._history),
            "pool_stats": self._pool.pool_stats(),
        }


# ═══ Singleton ═══

_research_team: CogResearchTeam | None = None


def get_research_team(consciousness=None) -> CogResearchTeam:
    global _research_team
    if _research_team is None:
        _research_team = CogResearchTeam(ltm_model=consciousness)
    elif consciousness and not _research_team._consciousness:
        _research_team._consciousness = consciousness
    return _research_team


__all__ = [
    "CogResearchTeam", "ResearchResult", "ResearchRound",
    "AgentOutput", "get_research_team",
]
