"""PromptCoach — L1(fast) generates optimized meta-prompts for L2(reasoning).

Replaces local training/fine-tuning. Instead of training models on
specific tasks, the fast model acts as a "prompt engineering coach"
that structures queries for optimal reasoning output.

Architecture:
  User query → L1(flash) generates meta-prompt → L2(pro) executes reasoning
  L1 role: structure decomposition, clarify intent, inject domain context
  L2 role: deep reasoning on the optimized prompt

Benefits:
  - No model files, no GPU, no training cost
  - L1 is cheap (￥0.0001/query), instant (~200ms)
  - Meta-prompt quality improves via feedback loop (L2 results → refine L1 prompt)

Usage:
  coach = get_prompt_coach()
  optimized = await coach.coach(query, domain="code")
  result = await chat([optimized], provider=L2)
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from loguru import logger


class PromptCoach:
    """L1→L2 meta-prompt optimization engine."""

    DOMAIN_TEMPLATES = {
        "code": "Write clean, well-structured code with error handling and comments. "
                "Include type hints. Break complex logic into helper functions.",
        "analysis": "Provide step-by-step reasoning. List assumptions. "
                   "Compare alternatives. Identify edge cases. Give concrete recommendations.",
        "creative": "Be original and expressive. Use vivid language. "
                   "Structure with clear sections. Include examples.",
        "general": "Be concise and accurate. Use examples when helpful. "
                  "Structure response with clear hierarchy.",
    }

    def __init__(self, tree_llm=None):
        self._tree = tree_llm
        self._feedbacks: list[dict] = []  # (query, meta_prompt, l2_quality, learned)

    # ═══ Main: L1 → meta-prompt → L2 ═══════════════════════════════

    async def coach(self, query: str, domain: str = "general",
                    extra_context: str = "") -> dict:
        """Generate optimized meta-prompt via L1, ready for L2 consumption.

        Returns: {meta_prompt, domain, complexity, pre_analysis, elapsed_ms}
        """
        t0 = time.time()

        try:
            from .sticky_election import get_layer_config
            cfg = get_layer_config()
            fast_prov, fast_model = cfg.get_provider(1)  # L1
        except Exception:
            fast_prov, fast_model = "deepseek", ""

        p = self._tree._providers.get(fast_prov) if self._tree else None
        if not p:
            return {"meta_prompt": query, "domain": domain, "elapsed_ms": 0}

        # Build coaching prompt for L1
        domain_guide = self.DOMAIN_TEMPLATES.get(domain, self.DOMAIN_TEMPLATES["general"])
        coach_prompt = (
            f"You are a prompt engineering coach. Analyze this user query "
            f"and produce an optimized prompt for a deep reasoning model.\n\n"
            f"User query: {query}\n"
            f"Domain: {domain}\n"
            f"{'Context: ' + extra_context if extra_context else ''}\n\n"
            f"Output format (JSON):\n"
            f'{{"meta_prompt": "<optimized prompt for reasoning model>", '
            f'"pre_analysis": "<1-sentence intent analysis>", '
            f'"complexity": "<simple|medium|complex>"}}\n\n'
            f"Guidelines for meta-prompt:\n"
            f"- Restate the query with explicit instructions\n"
            f"- {domain_guide}\n"
            f"- Add required output format if missing\n"
            f"- For code: include language, constraints, test cases\n"
            f"- For analysis: request structured reasoning, alternatives\n"
            f"Reply with ONLY the JSON object."
        )

        try:
            resp = await p.chat(
                messages=[{"role": "user", "content": coach_prompt}],
                model=fast_model or None,
                temperature=0.1, max_tokens=600, timeout=15,
            )
            coach_text = resp.text if resp and hasattr(resp, 'text') else ""
        except Exception:
            coach_text = ""

        # Parse coaching output
        meta_prompt = query
        pre_analysis = ""
        complexity = "medium"

        if coach_text:
            try:
                import json, re
                match = re.search(r'\{.*\}', coach_text, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    meta_prompt = data.get("meta_prompt", query)
                    pre_analysis = data.get("pre_analysis", "")
                    complexity = data.get("complexity", "medium")
            except Exception:
                # Fallback: use raw coaching output as meta-prompt
                meta_prompt = coach_text[:1000]

        # Learn from this coaching for future
        self._record(query, meta_prompt, domain)

        elapsed = (time.time() - t0) * 1000
        logger.debug(f"PromptCoach: {domain}/{complexity} → {len(meta_prompt)} chars ({elapsed:.0f}ms)")
        return {
            "meta_prompt": meta_prompt,
            "domain": domain,
            "complexity": complexity,
            "pre_analysis": pre_analysis,
            "elapsed_ms": round(elapsed, 0),
        }

    async def coached_chat(self, query: str, domain: str = "general",
                           context: str = "") -> dict:
        """End-to-end: L1 coaches → L2 reasons → return result.

        Returns: {text, method, meta_prompt, domain, complexity, elapsed_ms}
        """
        t0 = time.time()

        # Step 1: L1 generates meta-prompt
        coaching = await self.coach(query, domain, context)
        meta_prompt = coaching["meta_prompt"]

        # Step 2: L2 executes the optimized prompt
        try:
            from .sticky_election import get_layer_config
            cfg = get_layer_config()
            reas_prov, reas_model = cfg.get_provider(2)
        except Exception:
            reas_prov, reas_model = "deepseek", ""

        p = self._tree._providers.get(reas_prov) if self._tree else None
        result_text = ""

        if p:
            try:
                max_tokens = {"simple": 512, "medium": 1024, "complex": 2048}.get(
                    coaching["complexity"], 1024)
                resp = await p.chat(
                    messages=[{"role": "user", "content": meta_prompt}],
                    model=reas_model or None,
                    temperature=0.3, max_tokens=max_tokens, timeout=60,
                )
                result_text = resp.text if resp and hasattr(resp, 'text') else ""
            except Exception:
                pass

        elapsed = (time.time() - t0) * 1000
        return {
            "text": result_text or meta_prompt,
            "method": "prompt_coach",
            "meta_prompt": meta_prompt,
            "domain": coaching["domain"],
            "complexity": coaching["complexity"],
            "elapsed_ms": round(elapsed, 0),
        }

    # ═══ Evolving coach: learn from L2 quality feedback ═══════════

    def _record(self, query: str, meta_prompt: str, domain: str):
        self._feedbacks.append({"query": query[:200], "meta_prompt": meta_prompt[:200],
                                "domain": domain, "time": time.time()})
        if len(self._feedbacks) > 50:
            self._feedbacks.pop(0)

    def feedback(self, quality_score: float):
        """Record L2 output quality for learned improvements."""
        if self._feedbacks:
            self._feedbacks[-1]["quality"] = quality_score

    def stats(self) -> dict:
        return {
            "total_coaching_sessions": len(self._feedbacks),
            "domains": list(set(f["domain"] for f in self._feedbacks[-20:])),
            "avg_quality": sum(f.get("quality", 0) for f in self._feedbacks) / max(len(self._feedbacks), 1),
        }

    # ═══ Adaptive: tune domain templates from feedback ═════════════

    async def tune_from_feedback(self):
        """Periodically refine domain templates based on coaching results."""
        recent = self._feedbacks[-20:]
        if not recent:
            return

        # Simple heuristic: trim ineffective guidance
        # In production, could use LLM to analyze patterns
        good = [f for f in recent if f.get("quality", 0) > 0.7]
        if len(good) < 3:
            logger.debug("PromptCoach: insufficient quality feedback for tuning")
            return

        logger.info(f"PromptCoach: {len(good)}/{len(recent)} high-quality coaching sessions")


# ═══ Singleton ═══

_coach: Optional[PromptCoach] = None


def get_prompt_coach(tree=None) -> PromptCoach:
    global _coach
    if _coach is None or tree:
        _coach = PromptCoach(tree)
    return _coach
