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
        siliconflow_api_key: str = "",
        siliconflow_base_url: str = "",
        siliconflow_flash_model: str = "Qwen/Qwen2.5-7B-Instruct",
        siliconflow_default_model: str = "Qwen/Qwen2.5-7B-Instruct",
        siliconflow_pro_model: str = "deepseek-ai/DeepSeek-V3",
        siliconflow_reasoning_model: str = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
        siliconflow_small_model: str = "Qwen/Qwen2.5-1.5B-Instruct",
        mofang_api_key: str = "",
        mofang_base_url: str = "",
        mofang_flash_model: str = "Qwen/Qwen2.5-7B-Instruct",
        mofang_default_model: str = "Qwen/Qwen2.5-7B-Instruct",
        mofang_pro_model: str = "deepseek-ai/DeepSeek-V3",
        mofang_reasoning_model: str = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
        mofang_small_model: str = "Qwen/Qwen2.5-1.5B-Instruct",
        # NVIDIA NIM
        nvidia_api_key: str = "",
        nvidia_base_url: str = "",
        nvidia_default_model: str = "deepseek-ai/deepseek-r1",
        # L4: user-specified locked model (not auto-elected)
        l4_provider: str = "",
        l4_model: str = "",
    ):
        self.flash_model = flash_model
        self.pro_model = pro_model
        self.thinking_enabled = thinking_enabled
        self.flash_temperature = flash_temperature
        self.pro_temperature = pro_temperature
        self.timeout = timeout

        # L4 locked model — user-specified, never auto-switched
        self._l4_provider = l4_provider
        self._l4_model = l4_model

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
        if siliconflow_api_key:
            from ..treellm.providers import OpenAILikeProvider
            self._llm.add_provider(OpenAILikeProvider(
                name="siliconflow-flash",
                base_url=siliconflow_base_url or "https://api.siliconflow.cn/v1",
                api_key=siliconflow_api_key,
                default_model=siliconflow_flash_model or "Qwen/Qwen2.5-7B-Instruct",
            ))
            self._llm.add_provider(OpenAILikeProvider(
                name="siliconflow-reasoning",
                base_url=siliconflow_base_url or "https://api.siliconflow.cn/v1",
                api_key=siliconflow_api_key,
                default_model=siliconflow_reasoning_model or "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
            ))
            self._llm.add_provider(OpenAILikeProvider(
                name="siliconflow-pro",
                base_url=siliconflow_base_url or "https://api.siliconflow.cn/v1",
                api_key=siliconflow_api_key,
                default_model=siliconflow_pro_model or "deepseek-ai/DeepSeek-V3",
            ))
            self._llm.add_provider(OpenAILikeProvider(
                name="siliconflow-small",
                base_url=siliconflow_base_url or "https://api.siliconflow.cn/v1",
                api_key=siliconflow_api_key,
                default_model=siliconflow_small_model or "Qwen/Qwen2.5-1.5B-Instruct",
            ))

        if mofang_api_key:
            from ..treellm.providers import OpenAILikeProvider
            self._llm.add_provider(OpenAILikeProvider(
                name="mofang-flash",
                base_url=mofang_base_url or "https://ai.gitee.com/v1",
                api_key=mofang_api_key,
                default_model=mofang_flash_model or "Qwen/Qwen2.5-7B-Instruct",
            ))
            self._llm.add_provider(OpenAILikeProvider(
                name="mofang-reasoning",
                base_url=mofang_base_url or "https://ai.gitee.com/v1",
                api_key=mofang_api_key,
                default_model=mofang_reasoning_model or "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
            ))
            self._llm.add_provider(OpenAILikeProvider(
                name="mofang-small",
                base_url=mofang_base_url or "https://ai.gitee.com/v1",
                api_key=mofang_api_key,
                default_model=mofang_small_model or "Qwen/Qwen2.5-1.5B-Instruct",
            ))
            self._llm.add_provider(OpenAILikeProvider(
                name="mofang-pro",
                base_url=mofang_base_url or "https://ai.gitee.com/v1",
                api_key=mofang_api_key,
                default_model=mofang_pro_model or "deepseek-ai/DeepSeek-V3",
            ))

        if nvidia_api_key:
            from ..treellm.providers import OpenAILikeProvider
            nvidia_url = nvidia_base_url or "https://integrate.api.nvidia.com/v1"
            # Reasoning tier: deepseek-r1 — strongest free reasoning model
            self._llm.add_provider(OpenAILikeProvider(
                name="nvidia-reasoning",
                base_url=nvidia_url,
                api_key=nvidia_api_key,
                default_model="deepseek-ai/deepseek-r1",
            ))
            # Pro tier: nemotron ultra — 253B flagship
            self._llm.add_provider(OpenAILikeProvider(
                name="nvidia-pro",
                base_url=nvidia_url,
                api_key=nvidia_api_key,
                default_model="nvidia/llama-3.1-nemotron-ultra-253b-v1",
            ))
            # Flash tier: llama 70B — fast general purpose
            self._llm.add_provider(OpenAILikeProvider(
                name="nvidia-flash",
                base_url=nvidia_url,
                api_key=nvidia_api_key,
                default_model="meta/llama-3.3-70b-instruct",
            ))
            # Small tier: phi-3.5-mini — lightweight fast
            self._llm.add_provider(OpenAILikeProvider(
                name="nvidia-small",
                base_url=nvidia_url,
                api_key=nvidia_api_key,
                default_model="microsoft/phi-3.5-mini-instruct",
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
        if siliconflow_api_key:
            self._free_models.append("siliconflow-flash")
            self._free_models.append("siliconflow-reasoning")
            self._free_models.append("siliconflow-small")
        if mofang_api_key:
            self._free_models.append("mofang-flash")
            self._free_models.append("mofang-reasoning")
            self._free_models.append("mofang-small")
        if nvidia_api_key:
            self._free_models.append("nvidia-reasoning")
            self._free_models.append("nvidia-flash")
            self._free_models.append("nvidia-small")
        if xiaomi_api_key:
            self._paid_models.append("xiaomi")
        if aliyun_api_key:
            self._paid_models.append("aliyun")
        if dmxapi_api_key:
            self._paid_models.append("dmxapi")
        if spark_api_key:
            self._paid_models.append("spark")
        if siliconflow_api_key:
            self._paid_models.append("siliconflow")
        if api_key:
            self._paid_models.append("deepseek")

        self._elected: str = ""
        self._elected_at: float = 0.0
        self._election_lock = asyncio.Lock()
        self._recheck_interval = 300.0
        self._available: bool | None = None
        self._opencode_cache = []

    # ── Election ──

    # ═══ L4 locked model ── user-specified, never auto-elected ═══

    @property
    def l4_provider(self) -> str:
        return self._l4_provider

    @property
    def l4_model(self) -> str:
        return self._l4_model

    def set_l4_model(self, provider: str, model: str):
        self._l4_provider = provider
        self._l4_model = model
        logger.info(f"L4 model locked: {provider}/{model}")

    def get_l4_provider(self):
        """Get the L4 provider instance, or None."""
        if self._l4_provider:
            return self._llm.get_provider(self._l4_provider)
        for name in self._free_models + self._paid_models:
            p = self._llm.get_provider(name)
            if p:
                return p
        return None

    # ═══ Local model registration ═══

    async def register_local_models(self):
        """Scan local device for LLM services and auto-register."""
        try:
            from ..treellm.local_scanner import LocalScanner
            from ..treellm.providers import OpenAILikeProvider
            scanner = LocalScanner()
            services = await scanner.scan()

            for svc in services:
                for model in svc.models:
                    provider_name = f"local-{svc.name}-{model['id'].replace('/', '-').replace(':', '-')[:30]}"
                    self._llm.add_provider(OpenAILikeProvider(
                        name=provider_name,
                        base_url=svc.base_url,
                        api_key=svc.api_key or "local",
                        default_model=model["id"],
                    ))
                    self._free_models.insert(0, provider_name)
                    logger.info(f"  local: {provider_name}")
        except Exception as e:
            logger.debug(f"Local scan failed: {e}")

    # ═══ Election ═══

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
                        from ..treellm.providers import OpenAILikeProvider
                        adapter = OpenCodeServeAdapter(base_url=p["base_url"])
                        if await adapter.ping():
                            # Register opencode-serve as a real provider so it can be used
                            name = "opencode-serve"
                            model = p.get("model", "opencode")
                            if name not in self._llm._providers:
                                self._llm.add_provider(OpenAILikeProvider(
                                    name=name,
                                    base_url=p["base_url"],
                                    api_key=p.get("api_key", "opencode-local"),
                                    default_model=model,
                                ))
                            self._elected = name
                            self._elected_at = now
                            logger.info(f"Elected: opencode-serve ({model})")
                            return name
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

            # ── Filter L4 from candidates (user-locked, not auto-elected) ──
            candidates = [c for c in candidates if c != self._l4_provider]

            elected = await self._llm.elect(candidates)
            if elected:
                self._elected = elected
                self._elected_at = now
                logger.info(f"Elected: {elected} (pool={len(candidates)})")
                return elected

            # ── Fallback: use L4 model if configured ──
            if self._l4_provider:
                l4_p = self._llm.get_provider(self._l4_provider)
                if l4_p:
                    ok, _ = await l4_p.ping()
                    if ok:
                        self._elected = self._l4_provider
                        self._elected_at = now
                        logger.info(f"Fallback to L4: {self._l4_provider}")
                        return self._l4_provider

            self._elected = ""
            logger.warning(f"All {len(candidates)} providers unavailable, no L4 fallback")
            return ""

    async def _check_available(self) -> bool:
        if self._available is not None:
            return self._available
        elected = self._llm._elected
        if elected:
            p = self._llm.get_provider(elected)
            if p:
                ok, _ = await p.ping()
                self._available = ok
                if ok:
                    logger.info(f"Provider elected: {elected}")
                return ok
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
        """Stream thinking tokens. Priority: elected free model → any free reasoning model → any alive."""
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

        for fallback in self._free_models + self._paid_models:
            if fallback == elected:
                continue
            try:
                p = self._llm.get_provider(fallback)
                if not p:
                    continue
                ok, _ = await p.ping()
                if not ok:
                    continue
                async for t in self._llm.stream(
                    messages=[
                        {"role": "system", "content": "快速分析用户意图。流式输出思考过程。"},
                        {"role": "user", "content": prompt},
                    ],
                    provider=fallback,
                    temperature=self.flash_temperature,
                    max_tokens=min(kwargs.get("max_tokens", 1024), 4096),
                    timeout=self.timeout,
                ):
                    yield t
                return
            except Exception:
                continue

        async for t in self._heuristic_stream(prompt):
            yield t

    async def chain_of_thought(self, question: str, steps: int = 3, **kwargs) -> str:
        """L4 reasoning: free reasoning models first, deepseek-pro last resort."""
        system_msg = f"深度{steps}步推理。Output reasoning steps then final answer."
        user_msg = f"深度推理以下问题 ({steps}步):\n\n{question}"

        # Step 1: Use elected free model
        elected = self._llm._elected
        if elected:
            try:
                result = await self._llm.chat(
                    messages=[{"role": "system", "content": system_msg},
                              {"role": "user", "content": user_msg}],
                    provider=elected,
                    temperature=kwargs.get("temperature", self.pro_temperature),
                    max_tokens=min(kwargs.get("max_tokens", 8192), 8192),
                    timeout=self.timeout,
                )
                if result and result.text:
                    reasoning = getattr(result, 'reasoning', None)
                    content = result.text
                    if reasoning:
                        reasoning = self._harvest_reasoning(reasoning)
                    return f"{reasoning}\n\n{content}" if reasoning else content
            except Exception:
                pass

        # Step 2: Try dedicated reasoning providers (free tier)
        reasoning_providers = [
            "siliconflow-reasoning", "mofang-reasoning",
            "siliconflow-pro", "mofang-pro",
            "modelscope",
            "bailing",
            "stepfun",
            "internlm",
        ]
        # L4 last (user-specified)
        if self._l4_provider:
            reasoning_providers.append(self._l4_provider)
        for provider_name in reasoning_providers:
            if provider_name == elected:
                continue
            p = self._llm.get_provider(provider_name)
            if not p:
                continue
            if provider_name == "deepseek":
                await self._check_available()
                if not self._available:
                    continue
            try:
                result = await self._llm.chat(
                    messages=[{"role": "system", "content": system_msg},
                              {"role": "user", "content": user_msg}],
                    provider=provider_name,
                    temperature=kwargs.get("temperature", self.pro_temperature),
                    max_tokens=min(kwargs.get("max_tokens", 8192), 8192),
                    timeout=self.timeout,
                )
                if result and result.text:
                    reasoning = getattr(result, 'reasoning', None)
                    content = result.text
                    if reasoning:
                        reasoning = self._harvest_reasoning(reasoning)
                    return f"{reasoning}\n\n{content}" if reasoning else content
            except Exception:
                continue

        return self._heuristic_cot(question, steps)

    def _harvest_reasoning(self, reasoning: str) -> str:
        try:
            from .thought_harvest import ThoughtHarvester
            harvest = ThoughtHarvester().harvest(reasoning)
            if harvest.found:
                return harvest.cleaned_text
        except Exception:
            pass
        return reasoning

    async def hypothesis_generation(self, problem: str, count: int = 3, **kwargs) -> list[str]:
        """Generate hypotheses. Uses elected free model first, falls back through providers."""
        system_msg = f"Generate {count} distinct hypotheses. One per line."
        user_msg = f"Problem:\n\n{problem}"

        elected = self._llm._elected
        if elected:
            try:
                result = await self._llm.chat(
                    messages=[{"role": "system", "content": system_msg},
                              {"role": "user", "content": user_msg}],
                    provider=elected,
                    temperature=0.9,
                    max_tokens=min(kwargs.get("max_tokens", 4096), 8192),
                    timeout=self.timeout,
                )
                hypotheses = [l.strip() for l in result.text.split("\n") if l.strip() and len(l.strip()) > 20]
                if len(hypotheses) >= count:
                    return hypotheses[:count]
            except Exception:
                pass

        for fallback in self._free_models + self._paid_models + ["deepseek"]:
            if fallback == elected:
                continue
            try:
                p = self._llm.get_provider(fallback)
                if not p:
                    continue
                result = await self._llm.chat(
                    messages=[{"role": "system", "content": system_msg},
                              {"role": "user", "content": user_msg}],
                    provider=fallback,
                    temperature=0.9,
                    max_tokens=min(kwargs.get("max_tokens", 4096), 8192),
                    timeout=self.timeout,
                )
                hypotheses = [l.strip() for l in result.text.split("\n") if l.strip() and len(l.strip()) > 20]
                if len(hypotheses) >= count:
                    return hypotheses[:count]
            except Exception:
                continue

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

        for fallback in self._free_models + self._paid_models:
            if fallback == elected:
                continue
            try:
                p = self._llm.get_provider(fallback)
                if not p:
                    continue
                result = await self._llm.chat(
                    messages=[
                        {"role": "system", "content": "Identify knowledge gaps. Output 3-5 questions."},
                        {"role": "user", "content": f"Context:\n\n{context}"},
                    ],
                    provider=fallback,
                    temperature=self.flash_temperature,
                    max_tokens=1024,
                    timeout=self.timeout,
                )
                qs = [l.strip().lstrip("- ").rstrip("?") + "?"
                      for l in result.text.split("\n") if "?" in l or any(q in l for q in ["如何", "是否", "哪些", "什么", "怎样"])]
                if qs:
                    return qs
            except Exception:
                continue

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
