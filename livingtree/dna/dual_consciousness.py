"""DualModelConsciousness — TreeLLM-backed multi-model reasoning.

Uses TreeLLM for all LLM calls (replaces LiteLLM). Features:
- Auto-election across all configured providers
- Built-in tiny classifier for smart routing
- DeepSeek Pro: chain-of-thought, hypotheses (with thinking mode)
- LongCat: intent, semantic, self-questioning (free)
- Fallback: heuristic when all providers unavailable
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import AsyncIterator

from loguru import logger

from .consciousness import Consciousness
from ..treellm import TreeLLM, create_deepseek_provider, create_longcat_provider


class DualModelConsciousness(Consciousness):

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
        longcat_flash_model: str = "LongCat-Flash-Lite",
        longcat_flash_temperature: float = 0.3,
        longcat_flash_max_tokens: int = 4096,
        longcat_models: str = "",
        longcat_chat_model: str = "",
        xiaomi_api_key: str = "",
        xiaomi_base_url: str = "",
        xiaomi_flash_model: str = "mimo-v2-flash",
        xiaomi_pro_model: str = "mimo-v2.5",
        aliyun_api_key: str = "",
        aliyun_base_url: str = "",
        aliyun_flash_model: str = "qwen-turbo",
        aliyun_pro_model: str = "qwen-max",
        zhipu_api_key: str = "",
        zhipu_base_url: str = "",
        zhipu_flash_model: str = "glm-4-flash",
        zhipu_pro_model: str = "glm-4-plus",
        dmxapi_api_key: str = "",
        dmxapi_base_url: str = "",
        dmxapi_default_model: str = "gpt-5-mini",
        spark_api_key: str = "",
        spark_base_url: str = "",
        spark_default_model: str = "xdeepseekv3",
    ):
        self.flash_model = flash_model
        self.pro_model = pro_model
        self.thinking_enabled = thinking_enabled
        self.flash_temperature = flash_temperature
        self.pro_temperature = pro_temperature
        self.timeout = timeout

        self._longcat_key = longcat_api_key
        self._longcat_base = longcat_base_url
        self._longcat_temp = longcat_flash_temperature
        self._longcat_max_tokens = longcat_flash_max_tokens

        models = [m.strip() for m in (longcat_models or "").split(",") if m.strip()]
        if not models:
            models = [longcat_flash_model]
            if longcat_chat_model and longcat_chat_model not in models:
                models.append(longcat_chat_model)
        self._longcat_models = models

        self._llm = TreeLLM()
        if api_key:
            self._llm.add_provider(create_deepseek_provider(api_key))
        if longcat_api_key:
            self._llm.add_provider(create_longcat_provider(longcat_api_key))
        if xiaomi_api_key:
            from ..treellm.providers import OpenAILikeProvider
            self._llm.add_provider(OpenAILikeProvider(
                name="xiaomi",
                base_url=xiaomi_base_url or "https://api.xiaomimimo.com/v1",
                api_key=xiaomi_api_key,
                default_model=xiaomi_flash_model,
            ))
        if aliyun_api_key:
            from ..treellm.providers import OpenAILikeProvider
            self._llm.add_provider(OpenAILikeProvider(
                name="aliyun",
                base_url=aliyun_base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key=aliyun_api_key,
                default_model=aliyun_flash_model,
            ))
        if zhipu_api_key:
            from ..treellm.providers import OpenAILikeProvider
            self._llm.add_provider(OpenAILikeProvider(
                name="zhipu",
                base_url=zhipu_base_url or "https://open.bigmodel.cn/api/paas/v4",
                api_key=zhipu_api_key,
                default_model=zhipu_flash_model,
            ))
        if dmxapi_api_key:
            from ..treellm.providers import OpenAILikeProvider
            self._llm.add_provider(OpenAILikeProvider(
                name="dmxapi",
                base_url=dmxapi_base_url or "https://www.dmxapi.cn/v1",
                api_key=dmxapi_api_key,
                default_model=dmxapi_default_model,
            ))
        if spark_api_key:
            from ..treellm.providers import OpenAILikeProvider
            self._llm.add_provider(OpenAILikeProvider(
                name="spark",
                base_url=spark_base_url or "https://maas-api.cn-huabei-1.xf-yun.com/v2",
                api_key=spark_api_key,
                default_model=spark_default_model,
            ))

        # ── Election order: free models first ──
        self._free_models = []
        self._paid_models = []
        if longcat_api_key:
            self._free_models.append("longcat")
        if zhipu_api_key:
            self._free_models.append("zhipu")
        if spark_api_key:
            self._free_models.append("spark")
        if xiaomi_api_key:
            self._paid_models.append("xiaomi")
        if aliyun_api_key:
            self._paid_models.append("aliyun")
        if dmxapi_api_key:
            self._paid_models.append("dmxapi")
        if spark_api_key:
            self._paid_models.append("spark")
        if api_key:
            self._paid_models.append("deepseek")

        self._elected: str = ""
        self._elected_at: float = 0.0
        self._election_lock = asyncio.Lock()
        self._recheck_interval = 300.0
        self._available: bool | None = None
        self._opencode_cache = []

    # ── Election ──

    async def _elect(self) -> str:
        async with self._election_lock:
            now = time.monotonic()
            if self._elected and (now - self._elected_at) < self._recheck_interval:
                return self._elected

            candidates = []
            candidates.extend(self._free_models)
            candidates.extend(self._paid_models)

            if not self._opencode_cache:
                try:
                    from ..integration.opencode_bridge import OpenCodeBridge
                    bridge = OpenCodeBridge()
                    self._opencode_cache = await bridge.discover_for_election()
                except Exception:
                    pass

            for p in self._opencode_cache:
                if p.get("source") == "opencode_serve":
                    try:
                        from ..integration.opencode_serve import OpenCodeServeAdapter
                        adapter = OpenCodeServeAdapter(base_url=p["base_url"])
                        if await adapter.ping():
                            self._elected = "opencode-serve"
                            self._elected_at = now
                            logger.info(f"Elected: opencode-serve")
                            return "opencode-serve"
                    except Exception:
                        pass
                    continue

                from ..treellm.providers import OpenAILikeProvider
                name = f"oc-{p['name']}"
                self._llm.add_provider(OpenAILikeProvider(
                    name=name, base_url=p["base_url"],
                    api_key=p["api_key"], default_model=p.get("model", ""),
                ))
                candidates.append(name)

            elected = await self._llm.elect(candidates)
            if elected:
                self._elected = elected
                self._elected_at = now
                logger.info(f"Elected: {elected} (pool={len(candidates)})")
                return elected

            self._elected = ""
            logger.warning(f"All {len(candidates)} providers unavailable")
            return ""

    async def _check_available(self) -> bool:
        if self._available is not None:
            return self._available
        ds = self._llm.get_provider("deepseek")
        if not ds:
            self._available = False
            return False
        ok, _ = await ds.ping()
        self._available = ok
        if ok:
            logger.info(f"DeepSeek: flash={self.flash_model} pro={self.pro_model}")
        return ok

    # ── Core methods ──

    async def stream_of_thought(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        elected = await self._elect()
        if elected:
            try:
                async for t in self._llm.stream(
                    messages=[
                        {"role": "system", "content": "快速分析用户意图。流式输出思考过程。"},
                        {"role": "user", "content": prompt},
                    ],
                    provider=elected,
                    temperature=self._longcat_temp,
                    max_tokens=self._longcat_max_tokens,
                    timeout=self.timeout,
                ):
                    yield t
                return
            except Exception:
                pass

        if not await self._check_available():
            async for t in self._heuristic_stream(prompt):
                yield t
            return

        try:
            async for t in self._llm.stream(
                messages=[
                    {"role": "system", "content": "快速分析用户意图。流式输出思考过程。"},
                    {"role": "user", "content": prompt},
                ],
                provider="deepseek",
                temperature=self.flash_temperature,
                max_tokens=min(kwargs.get("max_tokens", 1024), 4096),
                timeout=self.timeout,
            ):
                yield t
        except Exception as e:
            logger.debug(f"Flash stream: {e}")
            async for t in self._heuristic_stream(prompt):
                yield t

    async def chain_of_thought(self, question: str, steps: int = 3, **kwargs) -> str:
        if not await self._check_available():
            return self._heuristic_cot(question, steps)
        try:
            result = await self._llm.chat(
                messages=[
                    {"role": "system", "content": f"深度{steps}步推理。Output reasoning steps then final answer."},
                    {"role": "user", "content": f"深度推理以下问题 ({steps}步):\n\n{question}"},
                ],
                provider="deepseek",
                temperature=kwargs.get("temperature", self.pro_temperature),
                max_tokens=min(kwargs.get("max_tokens", 8192), 8192),
                timeout=self.timeout,
                model_extra="deepseek-v4-pro",
            )
            content = result.text
            reasoning = result.reasoning
            if reasoning:
                try:
                    from .thought_harvest import ThoughtHarvester
                    harvest = ThoughtHarvester().harvest(reasoning)
                    if harvest.found:
                        reasoning = harvest.cleaned_text
                except Exception:
                    pass
            return reasoning + "\n\n" + content if reasoning else content
        except Exception as e:
            logger.debug(f"CoT: {e}")
            return self._heuristic_cot(question, steps)

    async def hypothesis_generation(self, problem: str, count: int = 3, **kwargs) -> list[str]:
        if not await self._check_available():
            return self._heuristic_hypotheses(problem, count)
        try:
            result = await self._llm.chat(
                messages=[
                    {"role": "system", "content": f"Generate {count} distinct hypotheses. One per line."},
                    {"role": "user", "content": f"Problem:\n\n{problem}"},
                ],
                provider="deepseek",
                temperature=0.9,
                max_tokens=min(kwargs.get("max_tokens", 4096), 8192),
                timeout=self.timeout,
                model_extra="deepseek-v4-pro",
            )
            hypotheses = [l.strip() for l in result.text.split("\n") if l.strip() and len(l.strip()) > 20]
            return hypotheses[:count] if len(hypotheses) >= count else self._heuristic_hypotheses(problem, count)
        except Exception as e:
            logger.debug(f"Hypothesis: {e}")
            return self._heuristic_hypotheses(problem, count)

    async def self_questioning(self, context: str, **kwargs) -> list[str]:
        elected = await self._elect()
        if elected:
            try:
                result = await self._llm.chat(
                    messages=[
                        {"role": "system", "content": "Identify knowledge gaps. Output 3-5 questions."},
                        {"role": "user", "content": f"Context:\n\n{context}"},
                    ],
                    provider=elected,
                    temperature=self._longcat_temp,
                    max_tokens=1024,
                    timeout=self.timeout,
                )
                qs = [l.strip().lstrip("- ").rstrip("?") + "?"
                      for l in result.text.split("\n") if "?" in l or any(q in l for q in ["如何", "是否", "哪些", "什么", "怎样"])]
                return qs if qs else self._heuristic_questions(context)
            except Exception:
                pass

        if not await self._check_available():
            return self._heuristic_questions(context)
        try:
            result = await self._llm.chat(
                messages=[
                    {"role": "system", "content": "Identify knowledge gaps. Output 3-5 questions."},
                    {"role": "user", "content": f"Context:\n\n{context}"},
                ],
                provider="deepseek",
                temperature=self.flash_temperature,
                max_tokens=1024,
                timeout=self.timeout,
            )
            qs = [l.strip().lstrip("- ").rstrip("?") + "?"
                  for l in result.text.split("\n") if "?" in l or any(q in l for q in ["如何", "是否", "哪些", "什么", "怎样"])]
            return qs if qs else self._heuristic_questions(context)
        except Exception as e:
            logger.debug(f"Questions: {e}")
            return self._heuristic_questions(context)

    async def recognize_intent(self, user_input: str) -> dict[str, any]:
        elected = await self._elect()
        if elected:
            try:
                result = await self._llm.chat(
                    messages=[
                        {"role": "system", "content": (
                            "Return JSON: {\"intent\":str,\"domain\":str,\"confidence\":float,\"summary\":str}. "
                            "Domains: general/eia/emergency/acceptance/feasibility/code/knowledge/training/analysis"
                        )},
                        {"role": "user", "content": user_input},
                    ],
                    provider=elected,
                    temperature=0.1,
                    max_tokens=512,
                    timeout=self.timeout,
                )
                text = result.text
                start, end = text.find("{"), text.rfind("}")
                if start >= 0 and end > start:
                    return json.loads(text[start:end + 1])
                return {"intent": "general", "domain": "general", "confidence": 0.5, "summary": text[:100]}
            except Exception:
                pass

        if not await self._check_available():
            return {"intent": "general", "domain": "general", "confidence": 0.5}
        try:
            result = await self._llm.chat(
                messages=[
                    {"role": "system", "content": (
                        "Return JSON: {\"intent\":str,\"domain\":str,\"confidence\":float,\"summary\":str}. "
                        "Domains: general/eia/emergency/acceptance/feasibility/code/knowledge/training/analysis"
                    )},
                    {"role": "user", "content": user_input},
                ],
                provider="deepseek",
                temperature=0.1,
                max_tokens=512,
                timeout=self.timeout,
            )
            text = result.text
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start:end + 1])
            return {"intent": "general", "domain": "general", "confidence": 0.5, "summary": text[:100]}
        except Exception:
            return {"intent": "general", "domain": "general", "confidence": 0.5}

    def get_election_status(self) -> dict:
        return {
            "elected": self._elected or "none",
            "providers": list(self._llm.provider_names),
            "opencode_providers": [p["model"] for p in getattr(self, '_opencode_cache', [])],
            "stats": self._llm.get_stats(),
        }

    # ── Fallbacks ──

    async def _heuristic_stream(self, prompt: str) -> AsyncIterator[str]:
        import asyncio
        yield "[All providers offline — check network / API keys / opencode serve]\n"
        await asyncio.sleep(0.02)
        yield f"Query: {prompt[:100]}"

    def _heuristic_cot(self, q: str, steps: int) -> str:
        return f"[Offline] All LLM providers unavailable. Query: {q[:200]}. Steps: {steps}."

    def _heuristic_hypotheses(self, p: str, n: int) -> list[str]:
        return [f"[Offline] Cannot generate hypotheses for: {p[:80]}"]

    def _heuristic_questions(self, c: str) -> list[str]:
        return ["[Offline] Are API keys valid?", "[Offline] Is opencode serve running?", "[Offline] Check network connectivity"]
