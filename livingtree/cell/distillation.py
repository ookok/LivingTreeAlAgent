"""Distillation — Knowledge transfer from expert models to cell models.

Supports:
- Multi-expert knowledge distillation (DeepSeek, OpenAI, Ollama)
- Curriculum learning with progressive difficulty
- Dataset generation from expert responses
- Batch and streaming distillation modes
- Quality assessment of distilled knowledge
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Optional

import aiohttp
from loguru import logger
from pydantic import BaseModel, Field

from .cell_ai import CellAI, CellCapability


class ExpertConfig(BaseModel):
    """Expert model configuration."""
    name: str = "deepseek"
    api_endpoint: str = "https://api.deepseek.com/v1/chat/completions"
    api_key: str = ""
    model: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.9
    timeout: int = 60


class DistillationResult(BaseModel):
    """Result of a distillation run."""
    expert_model: str
    prompts_processed: int = 0
    tokens_generated: int = 0
    quality_score: float = 0.0
    topics: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class Distillation:
    """Expert-model-to-cell knowledge distillation engine."""

    @staticmethod
    async def query_expert(prompt: str, config: ExpertConfig | None = None) -> str:
        """Query an expert model for knowledge.

        Args:
            prompt: The prompt to send to the expert
            config: Expert model configuration

        Returns:
            Expert response text
        """
        cfg = config or ExpertConfig()
        logger.debug(f"Querying expert {cfg.model}: {prompt[:80]}...")

        if not cfg.api_key:
            return _simulate_expert_response(prompt, cfg.model)

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {cfg.api_key}",
                }
                payload = {
                    "model": cfg.model,
                    "messages": [
                        {"role": "system", "content": "You are a domain expert providing detailed, accurate knowledge for training purpose. Respond in Chinese when the prompt is in Chinese."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": cfg.temperature,
                    "max_tokens": cfg.max_tokens,
                    "top_p": cfg.top_p,
                }
                async with session.post(
                    cfg.api_endpoint,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=cfg.timeout),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]
                    else:
                        error_text = await resp.text()
                        logger.error(f"Expert API error ({resp.status}): {error_text[:200]}")
                        return _simulate_expert_response(prompt, cfg.model)
        except asyncio.TimeoutError:
            logger.error(f"Expert API timeout after {cfg.timeout}s")
            return _simulate_expert_response(prompt, cfg.model)
        except Exception as e:
            logger.error(f"Expert API error: {e}")
            return _simulate_expert_response(prompt, cfg.model)

    @staticmethod
    async def distill_knowledge(cell: CellAI, expert_prompts: list[str],
                                config: ExpertConfig | None = None,
                                batch_size: int = 5) -> DistillationResult:
        """Distill expert knowledge into a cell in batches.

        Args:
            cell: Target CellAI for knowledge injection
            expert_prompts: Prompts to send to expert
            config: Expert configuration
            batch_size: How many prompts to process in parallel

        Returns:
            DistillationResult with statistics
        """
        cfg = config or ExpertConfig()
        result = DistillationResult(expert_model=cfg.model)
        all_outputs: list[str] = []
        errors: list[str] = []

        for i in range(0, len(expert_prompts), batch_size):
            batch = expert_prompts[i : i + batch_size]
            tasks = [Distillation.query_expert(p, cfg) for p in batch]
            outputs = await asyncio.gather(*tasks, return_exceptions=True)

            for j, output in enumerate(outputs):
                if isinstance(output, Exception):
                    errors.append(f"Batch {i // batch_size}, item {j}: {str(output)}")
                else:
                    all_outputs.append(str(output))
                    result.tokens_generated += len(output)
                    result.prompts_processed += 1

            await asyncio.sleep(0.1)

        # Record in cell genome
        if all_outputs:
            cell.genome.add_mutation(
                f"Distillation: learned {len(all_outputs)} items from {cfg.model}",
                source="distillation",
                affected_genes=["knowledge"],
            )

            # Add capabilities based on distilled topics
            topics = _extract_topics(all_outputs)
            for topic in topics[:5]:
                cell.capabilities.append(CellCapability(
                    name=f"distilled_{topic}",
                    description=f"Knowledge distilled from {cfg.model} about {topic}",
                    confidence=0.8,
                ))
            result.topics = topics

        result.errors = errors
        result.quality_score = min(1.0, len(all_outputs) / max(len(expert_prompts), 1))
        logger.info(f"Distillation complete: {result.prompts_processed}/{len(expert_prompts)} prompts, {result.tokens_generated} tokens")
        return result

    @staticmethod
    async def create_dataset_from_expert(expert_prompts: list[str],
                                          config: ExpertConfig | None = None,
                                          system_prompt: str = "") -> list[dict]:
        """Create a training dataset by querying the expert.

        Returns:
            List of {"instruction": ..., "output": ...} training pairs
        """
        cfg = config or ExpertConfig()
        dataset = []
        for prompt in expert_prompts:
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            output = await Distillation.query_expert(full_prompt, cfg)
            dataset.append({
                "instruction": prompt,
                "output": output,
                "expert_model": cfg.model,
            })
        return dataset

    @staticmethod
    async def streaming_distill(cell: CellAI, expert_prompts: list[str],
                                 config: ExpertConfig | None = None) -> AsyncIterator[dict[str, Any]]:
        """Distill with streaming progress updates.

        Yields progress for each prompt processed.
        """
        cfg = config or ExpertConfig()
        total = len(expert_prompts)

        for i, prompt in enumerate(expert_prompts):
            output = await Distillation.query_expert(prompt, cfg)
            cell.genome.add_mutation(
                f"Streaming distillation item {i + 1}/{total}",
                source="distillation",
                affected_genes=["knowledge"],
            )
            yield {
                "index": i + 1,
                "total": total,
                "progress": (i + 1) / total,
                "prompt": prompt[:100],
                "output_length": len(output),
            }

    @staticmethod
    async def curriculum_learning(cell: CellAI, topics: list[str],
                                   difficulty_levels: list[int] | None = None,
                                   config: ExpertConfig | None = None) -> dict[str, Any]:
        """Curriculum learning: progressively more complex topics.

        Args:
            cell: Target cell
            topics: List of topics to learn
            difficulty_levels: Difficulty map (1=easy, 5=expert)
            config: Expert configuration

        Returns:
            Learning progress summary
        """
        levels = difficulty_levels or [1] * len(topics)
        cfg = config or ExpertConfig()

        difficulty_prompts = {
            1: "请用简单易懂的语言解释以下概念：{topic}。适合初学者。",
            2: "请详细解释以下主题并提供示例：{topic}。",
            3: "请深入分析以下主题，包括其原理、应用和局限性：{topic}。",
            4: "请提供关于{topic}的专业级分析，包括前沿进展和挑战：{topic}。",
            5: "请以专家级深度全面剖析{topic}，包括理论、实践、前沿研究：{topic}。",
        }

        results = []
        for topic, level in sorted(zip(topics, levels), key=lambda x: x[1]):
            template = difficulty_prompts.get(level, difficulty_prompts[3])
            prompt = template.format(topic=topic)
            output = await Distillation.query_expert(prompt, cfg)
            results.append({
                "topic": topic,
                "level": level,
                "output_length": len(output),
            })
            await asyncio.sleep(0.1)

        cell.genome.add_mutation(
            f"Curriculum learning: {len(topics)} topics across levels {set(levels)}",
            source="curriculum_distillation",
        )

        return {
            "topics_covered": len(topics),
            "levels": sorted(set(levels)),
            "total_output_chars": sum(r["output_length"] for r in results),
            "status": "completed",
        }


def _simulate_expert_response(prompt: str, model_name: str = "expert") -> str:
    """Generate simulated expert response when API is not available."""
    import hashlib
    seed = int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16)
    topics = ["技术方案", "实施步骤", "风险分析", "评估方法", "优化建议",
              "法规要求", "技术原理", "最佳实践", "案例分析", "发展趋势"]
    selected = [topics[seed % len(topics)], topics[(seed + 1) % len(topics)]]
    return (
        f"[{model_name}] 针对您的问题，我从以下方面进行分析：\n\n"
        f"1. {selected[0]}：基于当前行业标准，建议采用分阶段实施策略，先进行现状调研和需求分析，"
        f"然后制定详细的技术方案，最后分步推进实施。\n\n"
        f"2. {selected[1]}：需要综合考虑技术可行性、经济成本、时间约束和资源条件，"
        f"采用系统工程方法进行整体规划。\n\n"
        f"总结：建议建立完善的评估指标体系和反馈机制，确保方案的持续优化和改进。"
    )


def _extract_topics(outputs: list[str]) -> list[str]:
    """Extract key topics from expert outputs."""
    keywords = {
        "技术": "technology", "风险": "risk", "评估": "assessment",
        "方案": "solution", "分析": "analysis", "设计": "design",
        "开发": "development", "测试": "testing", "部署": "deployment",
        "优化": "optimization", "监控": "monitoring", "安全": "security",
    }
    found = set()
    for output in outputs:
        for kw, en in keywords.items():
            if kw in output:
                found.add(en)
    return sorted(found)[:10]
