"""DualModelConsciousness — LiteLLM-backed dual-model reasoning.

Routes tasks via litellm.acompletion():
- LongCat (free): intent, semantic, self-questioning (auto-election Lite↔Chat)
- DeepSeek Pro:   CoT, hypotheses, deep reasoning + thinking mode (t=0.7)

Auto-election: tests all configured LongCat models (Lite→Chat→...),
picks first healthy one, re-tests on failure.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import AsyncIterator

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import litellm
from loguru import logger

from .consciousness import Consciousness

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass


class _FakeChoice:
    def __init__(self, content: str):
        self.delta = _FakeDelta(content)
        self.message = _FakeMessage(content)

class _FakeDelta:
    def __init__(self, content: str):
        self.content = content

class _FakeMessage:
    def __init__(self, content: str):
        self.content = content

class _FakeResponse:
    def __init__(self, text: str):
        self.choices = [_FakeChoice(text)]

class _FakeStream:
    def __init__(self, text: str):
        self._tokens = text.split()
        self._idx = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._idx >= len(self._tokens):
            raise StopAsyncIteration
        token = self._tokens[self._idx] + " "
        self._idx += 1
        return _FakeChoice(token)


class DualModelConsciousness(Consciousness):
    """LiteLLM-powered dual-model routing with auto-election."""

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
        longcat_api_key: str = "",
        longcat_base_url: str = "",
        longcat_flash_model: str = "openai/LongCat-Flash-Lite",
        longcat_flash_temperature: float = 0.3,
        longcat_flash_max_tokens: int = 4096,
        longcat_models: str = "",
        longcat_chat_model: str = "",
    ):
        self.flash_model = flash_model
        self.pro_model = pro_model
        self.thinking_enabled = thinking_enabled
        self.flash_temperature = flash_temperature
        self.pro_temperature = pro_temperature
        self.timeout = timeout

        self._longcat_key = longcat_api_key
        self._longcat_base = longcat_base_url

        models = [m.strip() for m in (longcat_models or "").split(",") if m.strip()]
        if not models:
            models = [longcat_flash_model]
            if longcat_chat_model and longcat_chat_model not in models:
                models.append(longcat_chat_model)

        self._longcat_models = models
        self._longcat_temp = longcat_flash_temperature
        self._longcat_max_tokens = longcat_flash_max_tokens

        self._elected_model: str = ""
        self._elected_at: float = 0.0
        self._election_lock = asyncio.Lock()
        self._recheck_interval = 300.0

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

    async def _elect_longcat(self) -> str:
        async with self._election_lock:
            now = time.monotonic()
            if self._elected_model and (now - self._elected_at) < self._recheck_interval:
                return self._elected_model

            candidates = []
            for m in self._longcat_models:
                candidates.append({
                    "model": m, "api_key": self._longcat_key,
                    "api_base": self._longcat_base, "source": "longcat",
                })

            if not hasattr(self, '_opencode_cache'):
                self._opencode_cache = []
            if not self._opencode_cache:
                try:
                    from ..integration.opencode_bridge import OpenCodeBridge
                    bridge = OpenCodeBridge()
                    self._opencode_cache = await bridge.discover_for_election()
                except Exception:
                    pass

            for p in self._opencode_cache:
                source = p.get("source", "opencode")
                if source == "opencode_serve":
                    try:
                        from ..integration.opencode_serve import OpenCodeServeAdapter
                        adapter = OpenCodeServeAdapter(base_url=p["base_url"])
                        if await adapter.ping():
                            self._elected_model = "opencode-serve"
                            self._elected_key = ""
                            self._elected_base = p["base_url"]
                            self._elected_at = now
                            self._elected_serve_adapter = adapter
                            logger.info(f"Elected: opencode-serve ({p['base_url']})")
                            return "opencode-serve"
                    except Exception as e:
                        logger.debug(f"Skip serve: {e}")
                    continue

                candidates.append({
                    "model": p["model"], "api_key": p["api_key"],
                    "api_base": p["base_url"], "source": source,
                })

            for c in candidates:
                try:
                    resp = await litellm.acompletion(
                        model=c["model"],
                        messages=[{"role": "user", "content": "ping"}],
                        max_tokens=1, timeout=10,
                        api_key=c["api_key"],
                        api_base=c["api_base"],
                    )
                    self._elected_model = c["model"]
                    self._elected_key = c["api_key"]
                    self._elected_base = c["api_base"]
                    self._elected_at = now
                    logger.info(f"Elected: {c['model']} ({c['source']}, pool={len(candidates)})")
                    return c["model"]
                except Exception as e:
                    logger.debug(f"Skip {c['model']}: {e}")

            self._elected_model = ""
            logger.warning(f"All {len(candidates)} providers unavailable")
            return ""

    async def _use_longcat(self, model: str, messages: list[dict], stream: bool = False,
                           temperature: float | None = None, max_tokens: int | None = None,
                           **kwargs) -> litellm.ModelResponse | litellm.CustomStreamWrapper:
        if model == "opencode-serve":
            adapter = getattr(self, '_elected_serve_adapter', None)
            if adapter:
                prompt = messages[-1].get("content", "") if messages else ""
                result = await adapter.chat(prompt)
                if stream:
                    return _FakeStream(result)
                return _FakeResponse(result)
            raise RuntimeError("opencode-serve adapter not available")

        api_key = getattr(self, '_elected_key', self._longcat_key) or self._longcat_key
        api_base = getattr(self, '_elected_base', self._longcat_base) or self._longcat_base
        return await litellm.acompletion(
            model=model,
            messages=messages,
            temperature=temperature if temperature is not None else self._longcat_temp,
            max_tokens=min(max_tokens or self._longcat_max_tokens, self._longcat_max_tokens),
            stream=stream,
            timeout=self.timeout,
            api_key=api_key,
            api_base=api_base,
            **kwargs,
        )

    async def _use_longcat_stream(self, model: str, prompt: str, **kwargs) -> AsyncIterator[str]:
        try:
            resp = await self._use_longcat(
                model=model,
                messages=[
                    {"role": "system", "content": "快速分析用户意图。流式输出思考过程。"},
                    {"role": "user", "content": prompt},
                ],
                stream=True,
            )
            async for chunk in resp:
                content = chunk.choices[0].delta.content or ""
                if content:
                    yield content
        except Exception as e:
            logger.debug(f"LongCat stream ({model}): {e}")
            self._invalidate_elected()
            async for t in self._heuristic_stream(prompt):
                yield t

    async def _use_longcat_intent(self, model: str, user_input: str) -> dict[str, any]:
        try:
            resp = await self._use_longcat(
                model=model,
                messages=[
                    {"role": "system", "content": (
                        "Return JSON: {\"intent\":str,\"domain\":str,\"confidence\":float,\"summary\":str}. "
                        "Domains: general/eia/emergency/acceptance/feasibility/code/knowledge/training/analysis"
                    )},
                    {"role": "user", "content": user_input},
                ],
                temperature=0.1,
                max_tokens=512,
            )
            text = resp.choices[0].message.content or ""
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start:end + 1])
            return {"intent": "general", "domain": "general", "confidence": 0.5, "summary": text[:100]}
        except Exception as e:
            logger.debug(f"LongCat intent ({model}): {e}")
            self._invalidate_elected()
            return {"intent": "general", "domain": "general", "confidence": 0.5}

    async def _use_longcat_questions(self, model: str, context: str) -> list[str]:
        try:
            resp = await self._use_longcat(
                model=model,
                messages=[
                    {"role": "system", "content": "Identify knowledge gaps. Output 3-5 questions."},
                    {"role": "user", "content": f"Context:\n\n{context}"},
                ],
                max_tokens=1024,
            )
            text = resp.choices[0].message.content or ""
            qs = [l.strip().lstrip("- ").rstrip("?") + "?"
                  for l in text.split("\n") if "?" in l or any(q in l for q in ["如何", "是否", "哪些", "什么", "怎样"])]
            return qs if qs else self._heuristic_questions(context)
        except Exception as e:
            logger.debug(f"LongCat questions ({model}): {e}")
            self._invalidate_elected()
            return self._heuristic_questions(context)

    def _invalidate_elected(self) -> None:
        if self._elected_model:
            logger.warning(f"LongCat {self._elected_model} failed, will re-elect next call")
            self._elected_model = ""

    def _get_elected_or_elect(self) -> str:
        return self._elected_model

    def get_election_status(self) -> dict:
        return {
            "elected_model": self._elected_model or "none",
            "source": "longcat" if self._elected_model in self._longcat_models else "opencode",
            "models": self._longcat_models,
            "opencode_providers": [p["model"] for p in getattr(self, '_opencode_cache', [])],
            "elected_seconds_ago": int(time.monotonic() - self._elected_at) if self._elected_at else -1,
            "recheck_interval": self._recheck_interval,
        }

    # ── Core methods ──

    async def stream_of_thought(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        model = await self._elect_longcat()
        if model:
            try:
                async for t in self._use_longcat_stream(model, prompt, **kwargs):
                    yield t
                return
            except Exception:
                pass

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
            messages = [
                {"role": "system", "content": f"深度{steps}步推理。Output reasoning steps then final answer."},
                {"role": "user", "content": f"深度推理以下问题 ({steps}步):\n\n{question}"},
            ]
            cache_opt = kwargs.pop("_cache_opt", None)
            if cache_opt:
                messages = cache_opt.prepare(messages[0]["content"], messages[1:])

            response = await litellm.acompletion(
                model=self.pro_model,
                messages=messages,
                temperature=kwargs.get("temperature", self.pro_temperature),
                max_tokens=min(kwargs.get("max_tokens", 8192), 8192),
                timeout=self.timeout,
            )
            content = response.choices[0].message.content or ""
            reasoning = getattr(response.choices[0].message, 'reasoning_content', '')

            if reasoning:
                try:
                    from .thought_harvest import ThoughtHarvester
                    harvest = ThoughtHarvester().harvest(reasoning)
                    if harvest.found:
                        logger.debug(f"Harvested {len(harvest.tool_calls)} tool calls from CoT")
                        reasoning = harvest.cleaned_text
                except Exception:
                    pass

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
        model = await self._elect_longcat()
        if model:
            try:
                return await self._use_longcat_questions(model, context)
            except Exception:
                pass

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
        model = await self._elect_longcat()
        if model:
            try:
                return await self._use_longcat_intent(model, user_input)
            except Exception:
                pass

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
