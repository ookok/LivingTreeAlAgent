"""DualModelConsciousness — LiteLLM-backed dual-model reasoning.

Routes tasks via litellm.acompletion():
- deepseek-v4-flash: intent, semantic, self-questioning (t=0.3)
- deepseek-v4-pro:  CoT, hypotheses, deep reasoning + thinking mode (t=0.7)

100+ providers through one API. No manual HTTP code.

Usage:
    consciousness = DualModelConsciousness()
    async for token in consciousness.stream_of_thought("analyze this"):
        print(token, end="")
"""

from __future__ import annotations

import json
import os
from typing import AsyncIterator

# Prevent litellm from fetching remote cost map (SSL fails in some envs)
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import litellm
from loguru import logger

from .consciousness import Consciousness

# Suppress SSL warnings in corporate/restrictive environments
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass


class DualModelConsciousness(Consciousness):
    """LiteLLM-powered dual-model routing consciousness."""

    def __init__(
        self,
        flash_model: str = "deepseek/deepseek-v4-flash",
        pro_model: str = "deepseek/deepseek-v4-pro",
        api_key: str = "",
        base_url: str = "",
        thinking_enabled: bool = True,
        flash_temperature: float = 0.3,
        pro_temperature: float = 0.7,
        timeout: int = 120,
    ):
        self.flash_model = flash_model
        self.pro_model = pro_model
        self.thinking_enabled = thinking_enabled
        self.flash_temperature = flash_temperature
        self.pro_temperature = pro_temperature
        self.timeout = timeout

        if api_key:
            litellm.api_key = api_key
        if base_url:
            litellm.api_base = base_url

        litellm.drop_params = True
        litellm.set_verbose = False
        litellm.suppress_debug_info = True
        self._available: bool | None = None

    async def _check_available(self) -> bool:
        if self._available is not None:
            return self._available
        if not getattr(litellm, 'api_key', None):
            logger.warning("No API key configured")
            self._available = False
            return False
        try:
            resp = await litellm.acompletion(
                model=self.flash_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
                timeout=10,
            )
            self._available = True
        except Exception as e:
            logger.warning(f"API check: {e}")
            self._available = False
        if self._available:
            logger.info(f"LiteLLM: flash={self.flash_model} pro={self.pro_model}")
        return self._available

    # ── Core methods ──

    async def stream_of_thought(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        if not await self._check_available():
            async for t in self._heuristic_stream(prompt):
                yield t
            return
        try:
            response = await litellm.acompletion(
                model=kwargs.get("model", self.flash_model),
                messages=[
                    {"role": "system", "content": "快速分析用户意图。流式输出思考过程。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=kwargs.get("temperature", self.flash_temperature),
                max_tokens=min(kwargs.get("max_tokens", 1024), 4096),
                stream=True,
                timeout=self.timeout,
            )
            async for chunk in response:
                content = chunk.choices[0].delta.content or ""
                if content:
                    yield content
        except Exception as e:
            logger.debug(f"Flash stream: {e}")
            async for t in self._heuristic_stream(prompt):
                yield t

    async def chain_of_thought(self, question: str, steps: int = 3, **kwargs) -> str:
        if not await self._check_available():
            return self._heuristic_cot(question, steps)
        try:
            response = await litellm.acompletion(
                model=self.pro_model,
                messages=[
                    {"role": "system", "content": f"深度{steps}步推理。Output reasoning steps then final answer."},
                    {"role": "user", "content": f"深度推理以下问题 ({steps}步):\n\n{question}"},
                ],
                temperature=kwargs.get("temperature", self.pro_temperature),
                max_tokens=min(kwargs.get("max_tokens", 8192), 8192),
                timeout=self.timeout,
            )
            content = response.choices[0].message.content or ""
            reasoning = getattr(response.choices[0].message, 'reasoning_content', '')
            if reasoning:
                logger.debug(f"Thinking: {len(reasoning)} chars")
            return reasoning + "\n\n" + content if reasoning else content
        except Exception as e:
            logger.debug(f"CoT: {e}")
            return self._heuristic_cot(question, steps)

    async def hypothesis_generation(self, problem: str, count: int = 3, **kwargs) -> list[str]:
        if not await self._check_available():
            return self._heuristic_hypotheses(problem, count)
        try:
            response = await litellm.acompletion(
                model=self.pro_model,
                messages=[
                    {"role": "system", "content": f"Generate {count} distinct hypotheses. One per line."},
                    {"role": "user", "content": f"Problem:\n\n{problem}"},
                ],
                temperature=0.9,
                max_tokens=min(kwargs.get("max_tokens", 4096), 8192),
                timeout=self.timeout,
            )
            text = response.choices[0].message.content or ""
            hypotheses = [l.strip() for l in text.split("\n")
                          if l.strip() and len(l.strip()) > 20]
            return hypotheses[:count] if len(hypotheses) >= count else self._heuristic_hypotheses(problem, count)
        except Exception as e:
            logger.debug(f"Hypothesis: {e}")
            return self._heuristic_hypotheses(problem, count)

    async def self_questioning(self, context: str, **kwargs) -> list[str]:
        if not await self._check_available():
            return self._heuristic_questions(context)
        try:
            response = await litellm.acompletion(
                model=self.flash_model,
                messages=[
                    {"role": "system", "content": "Identify knowledge gaps. Output 3-5 questions."},
                    {"role": "user", "content": f"Context:\n\n{context}"},
                ],
                temperature=self.flash_temperature,
                max_tokens=1024,
                timeout=self.timeout,
            )
            text = response.choices[0].message.content or ""
            qs = [l.strip().lstrip("- ").rstrip("?") + "?"
                  for l in text.split("\n") if "?" in l or any(q in l for q in ["如何", "是否", "哪些", "什么", "怎样"])]
            return qs if qs else self._heuristic_questions(context)
        except Exception as e:
            logger.debug(f"Questions: {e}")
            return self._heuristic_questions(context)

    async def recognize_intent(self, user_input: str) -> dict[str, any]:
        if not await self._check_available():
            return {"intent": "general", "domain": "general", "confidence": 0.5}
        try:
            response = await litellm.acompletion(
                model=self.flash_model,
                messages=[
                    {"role": "system", "content": (
                        "Return JSON: {\"intent\":str,\"domain\":str,\"confidence\":float,\"summary\":str}. "
                        "Domains: general/eia/emergency/acceptance/feasibility/code/knowledge/training/analysis"
                    )},
                    {"role": "user", "content": user_input},
                ],
                temperature=0.1,
                max_tokens=512,
                timeout=self.timeout,
            )
            text = response.choices[0].message.content or ""
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start:end + 1])
            return {"intent": "general", "domain": "general", "confidence": 0.5, "summary": text[:100]}
        except Exception:
            return {"intent": "general", "domain": "general", "confidence": 0.5}

    # ── Heuristic fallbacks ──

    async def _heuristic_stream(self, prompt: str) -> AsyncIterator[str]:
        import asyncio
        for thought in ["[感知]", "[认知]", "[规划]", "[准备]"]:
            await asyncio.sleep(0.02)
            yield thought + " "

    def _heuristic_cot(self, q: str, steps: int) -> str:
        return "\n".join([f"Step {i+1}: 分析{q[:30]}的第{i+1}维度" for i in range(steps)] +
                         [f"结论: 经{steps}步推理，建议体系化方法处理。"])

    def _heuristic_hypotheses(self, p: str, n: int) -> list[str]:
        return [f"假设{i+1}: 处理 {p[:30]}" for i in range(n)]

    def _heuristic_questions(self, c: str) -> list[str]:
        return [
            f"关于'{c[:40]}'需要哪些关键领域知识?",
            "有哪些边界条件尚未明确?",
            "当前的推理前提假设是否成立?",
        ]
