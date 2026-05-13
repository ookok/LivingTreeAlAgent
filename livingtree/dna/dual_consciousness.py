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
            self._free_models.append("kiro")
            self._free_models.append("opencode-free")
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
        self._elected_tiers: dict[int, str] = {}  # L0-L4 → provider name
        self._election_lock = asyncio.Lock()
        self._recheck_interval = 60.0     # Start aggressive, double on stable cache hits
        self._recheck_max = 300.0          # Cap at 5 minutes
        self._elected_at_stability = 0     # Counts stable cache hits
        self._failure_count = 0            # Tracks consecutive failures for adaptive cooldown
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

    # ═══ Per-stage provider election (Mythos-inspired dynamic expert meeting) ═══

    def _elect_stage_provider(self, stage_name: str, ctx=None) -> None:
        """Elect the best provider for a specific pipeline stage.

        Mythos-inspired: different stages need different experts.
        - perceive/cognize → fast flash model (low latency, broad knowledge)
        - plan/simulate → pro model (reasoning depth)
        - execute → code-optimized provider if available
        - reflect/evolve → cheapest available (local if possible)

        Sets ctx.metadata["elected_provider"] so downstream code can use it.
        """
        stage_preference = {
            "perceive":  ("flash", "Fast perception needs low latency"),
            "cognize":   ("flash", "Intent analysis benefits from broad knowledge"),
            "ontogrow":  ("flash", "Lightweight ontology extraction"),
            "plan":      ("pro",   "Planning needs deep reasoning"),
            "simulate":  ("pro",   "Simulation needs counterfactual reasoning"),
            "execute":   ("pro",   "Execution may need code capability"),
            "reflect":   ("flash", "Reflection benefits from fresh perspective"),
            "evolve":    ("local", "Evolution should use cheapest available"),
        }
        tier, reason = stage_preference.get(stage_name, ("flash", ""))
        try:
            if hasattr(self, '_tiers') and tier in self._tiers:
                elected = self._tiers[tier]
                if elected and ctx:
                    ctx.metadata["elected_provider"] = elected
                    ctx.metadata["election_reason"] = reason
        except Exception as e:
            logger.debug(f"Stage provider election failed: {e}")

    # ═══ Local model registration ═══

    async def register_local_models(self):
        """Scan local device for LLM services and auto-register.
        
        Uses ModelRegistry to discover and register locally running models
        (replaces deleted local_scanner module)."""
        try:
            from ..treellm.model_registry import ModelRegistry
            from ..treellm.providers import OpenAILikeProvider
            registry = ModelRegistry.instance()
            for provider_name, pm in registry._providers.items():
                if not pm.models:
                    continue
                for model_info in pm.models:
                    if not model_info.enabled:
                        continue
                    provider_key = f"local-{provider_name}-{model_info.short_name[:30]}"
                    self._llm.add_provider(OpenAILikeProvider(
                        name=provider_key,
                        base_url=pm.base_url,
                        api_key=pm.api_key or "local",
                        default_model=model_info.id,
                    ))
                    self._free_models.insert(0, provider_key)
                    logger.info(f"  local: {provider_key}")
        except Exception as e:
            logger.debug(f"Local model registration skipped: {e}")

    # ═══ Election ═══

    async def _elect_tiers(self, force: bool = False) -> dict[int, str]:
        """Elect L1(flash)/L2(pro)/L3(deep)/L4(user-locked) providers.
        
        Returns dict mapping tier number to provider name.
        Backward compat: also sets self._elected = L3 provider.
        """
        async with self._election_lock:
            now = time.monotonic()
            tiers: dict[int, str] = {}

            # ── Cache: return last elected tiers if still valid ──
            if not force and self._elected_tiers and (now - self._elected_at) < self._recheck_interval:
                self._elected_at_stability += 1
                if self._elected_at_stability % 10 == 0:
                    self._recheck_interval = min(self._recheck_interval * 2, self._recheck_max)
                return dict(self._elected_tiers)

            self._elected_at_stability = 0

            # ── Cache: adaptive cooldown on failures ──
            base_cooldown = 10.0
            max_cooldown = 120.0
            failure_cooldown = min(base_cooldown * (2 ** min(self._failure_count, 4)), max_cooldown)
            if (self._elected == "" and self._elected_at > 0
                    and (now - self._elected_at) < failure_cooldown):
                return dict(self._elected_tiers) if self._elected_tiers else {}

            # ── Priority 1: local opencode-serve (fastest) ──
            if not self._opencode_cache:
                try:
                    from ..integration.opencode_bridge import OpenCodeBridge
                    bridge = OpenCodeBridge()
                    self._opencode_cache = await bridge.discover_for_election()
                except Exception as e:
                    logger.debug(f"OpenCode bridge discovery failed: {e}")

            for p in self._opencode_cache:
                if p.get("source") == "opencode_serve":
                    try:
                        from ..integration.opencode_serve import OpenCodeServeAdapter
                        adapter = OpenCodeServeAdapter(base_url=p["base_url"])
                        if await adapter.ping():
                            name = "opencode-serve"
                            model = p.get("model", "opencode")
                            if name not in self._llm._providers:
                                from ..treellm.providers import OpenAILikeProvider
                                self._llm.add_provider(OpenAILikeProvider(
                                    name=name, base_url=p["base_url"],
                                    api_key=p.get("api_key", "opencode-local"),
                                    default_model=model,
                                ))
                            tiers[1] = tiers[2] = tiers[3] = name
                            self._set_tiers(tiers, now)
                            logger.info(f"Elected tiers (opencode): L1/L2/L3={name} ({model})")
                            return dict(tiers)
                    except Exception as e:
                        logger.debug(f"OpenCode serve adapter ping failed: {e}")
                    continue

                from ..treellm.providers import OpenAILikeProvider
                name = f"oc-{p['name']}"
                if name not in self._llm._providers:
                    self._llm.add_provider(OpenAILikeProvider(
                        name=name, base_url=p["base_url"],
                        api_key=p["api_key"], default_model=p.get("model", ""),
                    ))

            # ── Priority 2+3: free + paid providers via holistic election ──
            all_candidates = list(dict.fromkeys(
                self._free_models + self._paid_models
            ))
            all_candidates = [c for c in all_candidates if c != self._l4_provider]

            if all_candidates:
                # ── Get ranked list from unified ElectionBus ──
                ranked = []
                try:
                    from ..treellm.election_bus import get_election_bus
                    bus = get_election_bus()
                    ranked = await bus.get_scores(
                        self._llm._providers, self._free_models,
                    )
                except Exception as e:
                    logger.warning(f"ElectionBus failed: {e}")

                if ranked:
                    tiers[3] = ranked[0].name
                    if len(ranked) > 1:
                        tiers[2] = ranked[1].name
                    else:
                        tiers[2] = ranked[0].name
                    ranked_by_latency = sorted(ranked, key=lambda s: s.latency_ms or 99999)
                    tiers[1] = ranked_by_latency[0].name
                    self._set_tiers(tiers, now)
                    self._failure_count = 0
                    logger.info(
                        f"Tier election: L1={tiers.get(1,'')} (flash) "
                        f"L2={tiers.get(2,'')} (pro) "
                        f"L3={tiers.get(3,'')} (deep) "
                        f"| pool={len(all_candidates)}"
                    )
                    return dict(tiers)

            # ── Priority 4: L4 locked model ──
            if self._l4_provider:
                l4_p = self._llm.get_provider(self._l4_provider)
                if l4_p:
                    try:
                        ok, _ = await asyncio.wait_for(l4_p.ping(), timeout=3.0)
                    except Exception:
                        ok = True
                    if ok:
                        tiers[1] = tiers[2] = tiers[3] = self._l4_provider
                        self._set_tiers(tiers, now)
                        logger.info(f"Tier election (L4): L1/L2/L3={self._l4_provider}")
                        return dict(tiers)

            # ── Priority 5: first paid provider (trust without ping) ──
            if self._paid_models:
                first = self._paid_models[0]
                tiers[1] = tiers[2] = tiers[3] = first
                self._set_tiers(tiers, now)
                logger.info(f"Tier election (paid fallback): L1/L2/L3={first}")
                return dict(tiers)

            # ── Priority 5b: first free provider ──
            if self._free_models:
                first = self._free_models[0]
                tiers[1] = tiers[2] = tiers[3] = first
                self._set_tiers(tiers, now)
                logger.info(f"Tier election (free fallback): L1/L2/L3={first}")
                return dict(tiers)

            # ── All failed — cache failure ──
            self._elected = ""
            self._elected_at = now
            self._failure_count += 1
            logger.warning("Tier election failed: no providers available")
            return {}

    def _set_tiers(self, tiers: dict[int, str], now: float) -> None:
        """Update internal state after tier election success."""
        self._elected_tiers = tiers
        self._elected_at = now
        self._elected = tiers.get(3, "")
        if hasattr(self._llm, '_elected'):
            self._llm._elected = tiers.get(3, "")
        self._failure_count = 0

    async def get_l1_provider(self) -> str:
        """Get the currently elected L1 (flash) provider."""
        tiers = await self._elect_tiers()
        return tiers.get(1, self._elected)

    async def get_l2_provider(self) -> str:
        """Get the currently elected L2 (pro) provider."""
        tiers = await self._elect_tiers()
        return tiers.get(2, self._elected)

    async def get_l3_provider(self) -> str:
        """Get the currently elected L3 (deep reasoning) provider."""
        tiers = await self._elect_tiers()
        return tiers.get(3, self._elected)

    # ═══ Health Check ═══

    async def _check_available(self) -> bool:
        """Check if a working provider is available."""
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
        """Stream thinking tokens. Uses L1 (flash/fast) provider for lightweight streaming."""
        from ..core.model_spec import get_spec
        constitution = get_spec().get_system_context()
        system_msg = f"{constitution}\n\n快速分析用户意图。流式输出思考过程。"
        temperature = self._longcat_temp
        # ── Entropy Drive: boost temperature when deadlock detected ──
        try:
            from .entropy_drive import get_entropy_drive
            ed = get_entropy_drive()
            boost = ed.get_temperature_boost()
            if boost > 0:
                temperature = min(1.5, temperature + boost)
                prompt = ed.inject_entropy_prompt() or prompt
        except Exception as e:
            logger.debug(f"Entropy drive (stream) failed: {e}")

        elected = await self.get_l1_provider()
        if elected:
            try:
                async for t in self._llm.stream(
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": prompt},
                    ],
                    provider=elected,
                    temperature=temperature,
                    max_tokens=self._longcat_max_tokens,
                    timeout=self.timeout,
                ):
                    yield t
                return
            except Exception as e:
                logger.debug(f"Stream elected provider failed: {e}")

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
        """L2 (pro) reasoning. Uses tier-elected pro model, falls back through reasoning providers."""
        system_msg = f"深度{steps}步推理。Output reasoning steps then final answer."
        user_msg = f"深度推理以下问题 ({steps}步):\n\n{question}"

        # Step 1: Use L2 (pro) tier-elected provider
        temperature = kwargs.get("temperature", self.pro_temperature)
        # ── Entropy Drive: boost temperature when deadlock detected ──
        try:
            from .entropy_drive import get_entropy_drive
            ed = get_entropy_drive()
            boost = ed.get_temperature_boost()
            if boost > 0:
                temperature = min(1.5, temperature + boost)
                user_msg = ed.inject_entropy_prompt() or user_msg
        except Exception as e:
            logger.debug(f"Entropy drive (chain) failed: {e}")

        elected = await self.get_l2_provider()
        if elected:
            try:
                result = await self._llm.chat(
                    messages=[{"role": "system", "content": system_msg},
                              {"role": "user", "content": user_msg}],
                    provider=elected,
                    temperature=temperature,
                    max_tokens=min(kwargs.get("max_tokens", 8192), 8192),
                    timeout=self.timeout,
                )
                if result and result.text:
                    reasoning = getattr(result, 'reasoning', None)
                    content = result.text
                    if reasoning:
                        reasoning = self._harvest_reasoning(reasoning)
                    return f"{reasoning}\n\n{content}" if reasoning else content
            except Exception as e:
                logger.debug(f"Chain of thought elected provider failed: {e}")

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
        except Exception as e:
            logger.debug(f"Thought harvest failed: {e}")
        return reasoning

    async def hypothesis_generation(self, problem: str, count: int = 3, **kwargs) -> list[str]:
        """Generate hypotheses. Uses L2 (pro) tier-elected provider, falls back through pool."""
        system_msg = f"Generate {count} distinct hypotheses. One per line."
        user_msg = f"Problem:\n\n{problem}"

        elected = await self.get_l2_provider()
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
            except Exception as e:
                logger.debug(f"Hypothesis generation elected provider failed: {e}")

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
        """Identify knowledge gaps. Uses L1 (flash/fast) tier-elected provider."""
        elected = await self.get_l1_provider()
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
            except Exception as e:
                logger.debug(f"Self questioning elected provider failed: {e}")

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
        """Classify user intent. Uses L1 (flash/fast) tier-elected provider."""
        elected = await self.get_l1_provider()
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
            except Exception as e:
                logger.debug(f"Recognize intent elected provider failed: {e}")

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
            "elected_tiers": {
                "L1_flash": self._elected_tiers.get(1, ""),
                "L2_pro": self._elected_tiers.get(2, ""),
                "L3_deep": self._elected_tiers.get(3, ""),
                "L4_locked": self._elected_tiers.get(4, ""),
            },
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
