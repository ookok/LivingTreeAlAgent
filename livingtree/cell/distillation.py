"""Distillation — Knowledge transfer via TreeLLM (no LiteLLM dep).

Replaced LiteLLM with aiohttp-based direct API calls. Uses TreeLLM
compatible provider format for unified model access.
"""

from __future__ import annotations

import asyncio, json
from typing import Any, AsyncIterator, Optional

import aiohttp
from loguru import logger
from pydantic import BaseModel, Field

from .cell_ai import CellAI, CellCapability


class ExpertConfig(BaseModel):
    name: str = "deepseek-v4-pro"
    model: str = "deepseek-v4-pro"
    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60


class DistillationResult(BaseModel):
    expert_model: str
    prompts_processed: int = 0
    tokens_generated: int = 0
    quality_score: float = 0.0
    topics: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class Distillation:

    @staticmethod
    async def query_expert(prompt: str, config: ExpertConfig | None = None) -> str:
        cfg = config or ExpertConfig()
        logger.debug(f"Expert query: {cfg.model} | {prompt[:60]}...")
        if not cfg.api_key:
            return _simulated_response(prompt, cfg.model)
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    f"{cfg.base_url}/chat/completions",
                    json={
                        "model": cfg.model.split("/")[-1],
                        "messages": [
                            {"role": "system", "content": "You are a domain expert providing detailed, accurate knowledge. Respond in Chinese when the prompt is in Chinese."},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": cfg.temperature,
                        "max_tokens": cfg.max_tokens,
                    },
                    headers={"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=cfg.timeout),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"] or ""
            return _simulated_response(prompt, cfg.model)
        except Exception as e:
            logger.warning(f"Expert error: {e}")
            return _simulated_response(prompt, cfg.model)

    @staticmethod
    async def distill_knowledge(cell: CellAI, expert_prompts: list[str],
                                config: ExpertConfig | None = None,
                                batch_size: int = 5) -> DistillationResult:
        cfg = config or ExpertConfig()
        result = DistillationResult(expert_model=cfg.model)
        outputs: list[str] = []

        for i in range(0, len(expert_prompts), batch_size):
            batch = expert_prompts[i:i + batch_size]
            tasks = [Distillation.query_expert(p, cfg) for p in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for j, r in enumerate(results):
                if isinstance(r, Exception):
                    result.errors.append(f"Batch {i}:{j} {r}")
                else:
                    outputs.append(str(r))
                    result.tokens_generated += len(r)
                    result.prompts_processed += 1

        if outputs and cell:
            try:
                q = max(0.3, sum(len(o) for o in outputs) / max(len(outputs), 1) / 1000)
                result.quality_score = min(1.0, q)
                result.topics = _extract_topics(outputs)
            except Exception as e:
                result.errors.append(f"Quality assessment: {e}")

        return result


    @staticmethod
    async def iterative_distillation(prompts: list[str], config: ExpertConfig | None = None,
                                     cell: Any = None, target_quality: float = 0.80,
                                     max_rounds: int = 3) -> DistillationResult:
        cfg = config or ExpertConfig()
        result = DistillationResult(expert_model=cfg.name)
        current_prompts = list(prompts)
        for rnd in range(max_rounds):
            outputs = []
            for batch in [current_prompts[i:i+cfg.max_tokens//500] for i in range(0, len(current_prompts), cfg.max_tokens//500)]:
                if not batch:
                    continue
                tasks = [Distillation.query_expert(p, cfg) for p in batch]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in batch_results:
                    if not isinstance(r, Exception):
                        outputs.append(str(r))
                        result.tokens_generated += len(str(r))
            if outputs:
                q = min(1.0, sum(len(str(o)) for o in outputs) / max(len(outputs), 1) / 800)
                result.quality_score = q
                result.topics = _extract_topics(outputs)
            if result.quality_score >= target_quality:
                break
            current_prompts = [f"[round {rnd+1} refine] {p}" for p in prompts if p]
        result.prompts_processed = len(outputs)
        return result

    @staticmethod
    def compression_ratio(original_tokens: int, distilled_model_params: int,
                          expert_model_params: int | None = None) -> dict:
        return {"token_compression": 1.0 - (distilled_model_params / max(original_tokens, 1)),
                "model_ratio": distilled_model_params / max(expert_model_params or 1, 1),
                "ratio": round(distilled_model_params / max(original_tokens, 1), 4)}


def _simulated_response(prompt: str, model: str) -> str:
    import hashlib
    h = hashlib.md5(prompt.encode()).hexdigest()[:8]
    return f"[Simulated {model}] Response for query hash {h}: {prompt[:80]}..."

def _extract_topics(outputs: list[str]) -> list[str]:
    topics = set()
    for o in outputs[:5]:
        for line in o.split("\n")[:3]:
            if len(line) > 10 and len(line) < 100:
                topics.add(line.strip()[:60])
    return list(topics)[:5]
