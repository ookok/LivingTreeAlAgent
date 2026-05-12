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
        except Exception:
            pass

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

            # ── Cache: return last elected if still valid ──
            if self._elected and (now - self._elected_at) < self._recheck_interval:
                return self._elected

            # ── Cache: don't re-elect on failure for FAILURE_COOLDOWN ──
            FAILURE_COOLDOWN = 30.0
            if (self._elected == "" and self._elected_at > 0
                    and (now - self._elected_at) < FAILURE_COOLDOWN):
                return ""

            # ── Priority 1: local opencode-serve (fastest) ──
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
                            name = "opencode-serve"
                            model = p.get("model", "opencode")
                            if name not in self._llm._providers:
                                from ..treellm.providers import OpenAILikeProvider
                                self._llm.add_provider(OpenAILikeProvider(
                                    name=name, base_url=p["base_url"],
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

                # Non-opencode_serve models from bridge → add to quick-try list
                from ..treellm.providers import OpenAILikeProvider
                name = f"oc-{p['name']}"
                if name not in self._llm._providers:
                    self._llm.add_provider(OpenAILikeProvider(
                        name=name, base_url=p["base_url"],
                        api_key=p["api_key"], default_model=p.get("model", ""),
                    ))

            # ── Priority 2: free online providers (freebuff/openrouter) ──
            # ── Priority 3: paid vault providers (skip ping — trust them) ──
            all_candidates = list(dict.fromkeys(
                self._free_models + self._paid_models
            ))  # deduplicate, preserve order
            all_candidates = [c for c in all_candidates if c != self._l4_provider]

            if all_candidates:
                elected = await self._llm.elect(all_candidates)
                if elected:
                    self._elected = elected
                    self._elected_at = now
                    logger.info(f"Elected: {elected} (pool={len(all_candidates)})")
                    return elected

            # ── Priority 4: L4 locked model ──
            if self._l4_provider:
                l4_p = self._llm.get_provider(self._l4_provider)
                if l4_p:
                    try:
                        ok, _ = await asyncio.wait_for(l4_p.ping(), timeout=3.0)
                    except Exception:
                        ok = True  # Trust L4 on timeout
                    if ok:
                        self._elected = self._l4_provider
                        self._elected_at = now
                        logger.info(f"Fallback to L4: {self._l4_provider}")
                        return self._l4_provider

            # ── Priority 5: first paid provider (trust without ping) ──
            if self._paid_models:
                first = self._paid_models[0]
                self._elected = first
                self._elected_at = now
                logger.info(f"Fallback to paid: {first} (trusted, no ping)")
                return first

            # ── All failed — cache failure ──
            self._elected = ""
            self._elected_at = now
            logger.warning(
                f"All {len(all_candidates)} providers unavailable"
                + (", will retry in {FAILURE_COOLDOWN}s" if all_candidates else "")
            )
            return ""

    # ═══ L0-L4 Tiered Election ═══

    async def _elect_tiers(self, force: bool = False) -> dict[int, str]:
        """Elect the best available provider for each L0-L4 tier.

        Unlike _elect() which picks ONE winner, this maintains a per-tier
        mapping so lightweight tasks (stream_of_thought) use flash models
        while deep reasoning (chain_of_thought) uses pro models.

        Tiers:
          L0: Heuristic / local fallback (always available, no API needed)
          L1: Flash/fast — stream_of_thought, recognize_intent, self_questioning
          L2: Pro/complex — chain_of_thought, hypothesis_generation, self_writing
          L3: Deep reasoning — system analysis, autonomous core, self_review
          L4: User-locked — never auto-elected, manual set_l4_model()

        Returns:
            Dict mapping tier number → provider name (empty string if unavailable).
        """
        async with self._election_lock:
            now = time.monotonic()

            # ── Cache: return cached tiers unless forced ──
            if not force and self._elected_tiers and (now - self._elected_at) < self._recheck_interval:
                return dict(self._elected_tiers)

            tiers: dict[int, str] = {}

            # ── L4: User-locked model (never auto-elected) ──
            if self._l4_provider:
                tiers[4] = self._l4_provider

            # ── Build candidate pool ──
            all_candidates = list(dict.fromkeys(
                self._free_models + self._paid_models
            ))  # deduplicate, free first
            all_candidates = [c for c in all_candidates if c != self._l4_provider]

            if not all_candidates:
                # No providers at all — all tiers empty
                self._elected_tiers = tiers
                self._elected_at = now
                self._elected = ""
                return tiers

            # ── Get ranked list from HolisticElection ──
            from ..treellm.holistic_election import get_election
            ranked = await get_election().score_providers(
                all_candidates, self._llm._providers, self._free_models,
            )

            if not ranked:
                # All providers ping-failed — trust first paid provider
                fallback = self._paid_models[0] if self._paid_models else (
                    self._free_models[0] if self._free_models else ""
                )
                tiers[1] = tiers[2] = tiers[3] = fallback
                self._elected_tiers = tiers
                self._elected_at = now
                self._elected = fallback
                if fallback:
                    logger.info(f"Tier election (trusted fallback): L1/L2/L3={fallback}")
                return tiers

            # ── Assign tiers from ranked list ──

            # L3 (deep reasoning): top-ranked overall
            tiers[3] = ranked[0].name

            # L2 (pro/complex): second-best, or same as L3 if only one
            if len(ranked) > 1:
                tiers[2] = ranked[1].name
            else:
                tiers[2] = ranked[0].name

            # L1 (flash/fast): lowest-latency provider
            ranked_by_latency = sorted(ranked, key=lambda s: s.latency_ms or 99999)
            tiers[1] = ranked_by_latency[0].name

            self._elected_tiers = tiers
            self._elected_at = now

            # Backward compatibility: set legacy _elected to L3 (best overall)
            self._elected = tiers[3]
            self._llm._elected = tiers[3]

            logger.info(
                f"Tier election: L1={tiers.get(1,'')} (flash) "
                f"L2={tiers.get(2,'')} (pro) "
                f"L3={tiers.get(3,'')} (deep) "
                + (f"L4={tiers.get(4,'')}" if 4 in tiers else "")
                + f" | pool={len(all_candidates)}"
            )
            return dict(tiers)

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
        except Exception:
            pass

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
        except Exception:
            pass

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
