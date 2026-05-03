"""DualModelConsciousness — Routes tasks between flash (fast) and pro (deep) models.

DeepSeek API dual-model architecture:
- deepseek-v4-flash: Intent recognition, semantic understanding, quick self-questioning
- deepseek-v4-pro:  Deep chain-of-thought reasoning, hypothesis generation, thinking mode

The thinking mode (reasoning_content) from DeepSeek-v4-pro is separated from the
final answer (content), providing transparent deep reasoning to the pipeline.

Usage:
    from livingtree.dna.dual_consciousness import DualModelConsciousness
    c = DualModelConsciousness(
        flash_model="deepseek-v4-flash",
        pro_model="deepseek-v4-pro",
        api_key="sk-xxx",
    )
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import AsyncIterator, Optional

import aiohttp
from loguru import logger

from .consciousness import Consciousness


class DualModelConsciousness(Consciousness):
    """DeepSeek dual-model consciousness with thinking mode support.

    Task routing:
    - stream_of_thought  → flash model (fast, streaming)
    - chain_of_thought   → pro model (deep reasoning with thinking mode)
    - hypothesis_generation → pro model (creative deep thinking)
    - self_questioning   → flash model (quick knowledge gap detection)
    - intent_recognition → flash model (immediate understanding)

    Falls back between models if one is unavailable.
    """

    def __init__(
        self,
        flash_model: str = "deepseek-v4-flash",
        pro_model: str = "deepseek-v4-pro",
        api_key: str = "",
        base_url: str = "https://api.deepseek.com",
        thinking_enabled: bool = True,
        flash_temperature: float = 0.3,
        pro_temperature: float = 0.7,
        timeout: int = 120,
    ):
        self.flash_model = flash_model
        self.pro_model = pro_model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.thinking_enabled = thinking_enabled
        self.flash_temperature = flash_temperature
        self.pro_temperature = pro_temperature
        self.timeout = timeout
        self._available: Optional[bool] = None

    async def _check_available(self) -> bool:
        """Check if DeepSeek API is reachable."""
        if self._available is not None:
            return self._available

        if not self.api_key:
            logger.warning("DeepSeek API key not configured, using heuristic fallback")
            self._available = False
            return False

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                }
                payload = {
                    "model": self.flash_model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                }
                async with session.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    self._available = resp.status == 200
        except Exception as e:
            logger.warning(f"DeepSeek API check failed: {e}")
            self._available = False

        if self._available:
            logger.info(f"DeepSeek API available: flash={self.flash_model}, pro={self.pro_model}")
        return self._available

    # ── Core consciousness methods ──

    async def stream_of_thought(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """Fast streaming thought via flash model."""
        if not await self._check_available():
            async for token in self._heuristic_stream(prompt):
                yield token
            return

        messages = [
            {"role": "system", "content": "你是LivingTree数字生命体的感知层。请以意识流方式快速分析用户输入，提取关键意图和行动方向。"},
            {"role": "user", "content": prompt},
        ]

        try:
            async for token in self._stream_completion(
                model=kwargs.get("model", self.flash_model),
                messages=messages,
                temperature=kwargs.get("temperature", self.flash_temperature),
                max_tokens=min(kwargs.get("max_tokens", 1024), 4096),
            ):
                yield token
        except Exception as e:
            logger.warning(f"Flash model stream failed: {e}")
            async for token in self._heuristic_stream(prompt):
                yield token

    async def chain_of_thought(self, question: str, steps: int = 3, **kwargs) -> str:
        """Deep chain-of-thought reasoning via pro model with thinking mode."""
        if not await self._check_available():
            return self._heuristic_cot(question, steps)

        system_prompt = (
            "你是LivingTree数字生命体的深层推理引擎。请进行深度多步推理。\n"
            f"按照以下格式逐步推理，共{steps}步：\n"
            "首先分析问题的各个方面，然后逐步推导，最终给出结论。"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请深度推理以下问题（共{steps}步）：\n\n{question}"},
        ]

        try:
            result = await self._complete_with_thinking(
                messages=messages,
                temperature=kwargs.get("temperature", self.pro_temperature),
                max_tokens=min(kwargs.get("max_tokens", 8192), 8192),
            )
            if result.get("reasoning"):
                logger.debug(f"Pro model thinking: {len(result['reasoning'])} chars")
            return result.get("content", "") or result.get("reasoning", "") or self._heuristic_cot(question, steps)
        except Exception as e:
            logger.warning(f"Pro model CoT failed: {e}")
            return self._heuristic_cot(question, steps)

    async def hypothesis_generation(self, problem: str, count: int = 3, **kwargs) -> list[str]:
        """Generate multiple hypotheses via pro model."""
        if not await self._check_available():
            return self._heuristic_hypotheses(problem, count)

        system_prompt = (
            "你是创意推理引擎。请针对问题生成多个独立的、有洞见的假设或解决方案路径。"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请生成{count}个独立假设/方案来解决：\n\n{problem}\n\n格式：\n假设1: [方案]\n假设2: [方案]\n..."},
        ]

        try:
            result = await self._complete_with_thinking(
                messages=messages,
                temperature=0.9,
                max_tokens=min(kwargs.get("max_tokens", 4096), 8192),
            )
            content = result.get("content", "")
            hypotheses = []
            for line in content.split("\n"):
                stripped = line.strip()
                if stripped and (stripped.startswith("假设") or stripped.startswith("方案") or
                                 stripped.startswith("Hypothesis")):
                    hypotheses.append(stripped)
            if len(hypotheses) < count:
                non_empty = [l.strip() for l in content.split("\n") if len(l.strip()) > 20]
                hypotheses = non_empty[:count]
            return hypotheses[:count] if hypotheses else self._heuristic_hypotheses(problem, count)
        except Exception as e:
            logger.warning(f"Hypothesis generation failed: {e}")
            return self._heuristic_hypotheses(problem, count)

    async def self_questioning(self, context: str, **kwargs) -> list[str]:
        """Quick self-questioning via flash model."""
        if not await self._check_available():
            return self._heuristic_questions(context)

        messages = [
            {"role": "system", "content": "你是知识缺口检测器。请识别上下文中的信息空白、未证假设和边界情况。"},
            {"role": "user", "content": f"分析这段内容的知识缺口，生成3-5个问题：\n\n{context}"},
        ]

        try:
            result = await self._complete(
                model=self.flash_model,
                messages=messages,
                temperature=self.flash_temperature,
                max_tokens=1024,
            )
            questions = []
            for line in result.split("\n"):
                stripped = line.strip().lstrip("- ").rstrip("?")
                if "?" in stripped or any(q in stripped for q in ["如何", "是否", "能否", "哪些", "什么", "怎样"]):
                    questions.append(stripped + "?")
            return questions if questions else self._heuristic_questions(context)
        except Exception as e:
            logger.warning(f"Self-questioning failed: {e}")
            return self._heuristic_questions(context)

    async def recognize_intent(self, user_input: str, **kwargs) -> dict[str, any]:
        """Recognize user intent via flash model (returns structured intent)."""
        if not await self._check_available():
            return {"intent": "general", "domain": "general", "confidence": 0.5}

        messages = [
            {"role": "system", "content": (
                "你是意图识别引擎。分析用户输入，以JSON格式返回意图、领域和置信度。\n"
                '领域可选: general, eia(环评), emergency(应急), acceptance(验收), feasibility(可研), '
                'code(代码开发), knowledge(知识查询), training(训练), analysis(分析)\n'
                '格式: {"intent": "xxx", "domain": "xxx", "confidence": 0.0-1.0, "summary": "简短描述"}'
            )},
            {"role": "user", "content": user_input},
        ]

        try:
            result = await self._complete(
                model=self.flash_model,
                messages=messages,
                temperature=0.1,
                max_tokens=512,
            )
            json_start = result.find("{")
            json_end = result.rfind("}")
            if json_start >= 0 and json_end > json_start:
                return json.loads(result[json_start:json_end + 1])
            return {"intent": "general", "domain": "general", "confidence": 0.5, "summary": result[:100]}
        except Exception as e:
            logger.warning(f"Intent recognition failed: {e}")
            return {"intent": "general", "domain": "general", "confidence": 0.5}

    # ── LLM communication layer ──

    async def _complete(self, model: str, messages: list[dict],
                        temperature: float = 0.7, max_tokens: int = 4096) -> str:
        """Send a non-streaming completion request."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"API error {resp.status}: {error_text[:300]}")
                data = await resp.json()
                return data["choices"][0]["message"].get("content", "")

    async def _complete_with_thinking(self, messages: list[dict],
                                       temperature: float = 0.7,
                                       max_tokens: int = 8192) -> dict[str, str]:
        """Send to pro model and capture both reasoning_content (thinking) and content (answer).

        DeepSeek-v4-pro returns:
        - reasoning_content: the model's internal thinking process
        - content: the final answer

        Returns:
            {"reasoning": "...", "content": "..."}
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.pro_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"API error {resp.status}: {error_text[:300]}")
                data = await resp.json()
                choice = data["choices"][0]["message"]
                return {
                    "reasoning": choice.get("reasoning_content", ""),
                    "content": choice.get("content", ""),
                    "model": data.get("model", ""),
                    "usage": data.get("usage", {}),
                }

    async def _stream_completion(self, model: str, messages: list[dict],
                                  temperature: float = 0.7,
                                  max_tokens: int = 4096) -> AsyncIterator[str]:
        """Stream completion with incremental tokens."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"API stream error {resp.status}")
                buffer = b""
                async for chunk in resp.content.iter_any():
                    buffer += chunk
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        line_text = line.decode("utf-8").strip()
                        if line_text.startswith("data: "):
                            data_str = line_text[6:]
                            if data_str == "[DONE]":
                                return
                            try:
                                data = json.loads(data_str)
                                delta = data.get("choices", [{}])[0].get("delta", {})
                                token = delta.get("content", "")
                                if token:
                                    yield token
                            except (json.JSONDecodeError, KeyError, IndexError):
                                continue

    # ── Heuristic fallbacks ──

    async def _heuristic_stream(self, prompt: str) -> AsyncIterator[str]:
        thoughts = [
            f"[感知] 分析输入: {prompt[:60]}...\n",
            "[认知] 提取意图与关键概念...\n",
            "[规划] 匹配知识库与能力模块...\n",
            "[准备] 调用执行管道...\n",
        ]
        for thought in thoughts:
            await asyncio.sleep(0.05)
            yield thought

    def _heuristic_cot(self, question: str, steps: int) -> str:
        chain = []
        for i in range(steps):
            chain.append(f"步骤{i + 1}: 分析{question[:40]}的第{i + 1}个维度，拆解子问题，识别依赖关系")
        chain.append(f"结论: 经{steps}步推理，建议体系化方法处理该问题。")
        return "\n".join(chain)

    def _heuristic_hypotheses(self, problem: str, count: int) -> list[str]:
        approaches = ["系统性分解", "类比推理", "数据驱动分析", "专家规则匹配", "迭代优化"]
        return [f"假设{i + 1}: 采用{approaches[i % len(approaches)]}方法处理 {problem[:30]}" for i in range(count)]

    def _heuristic_questions(self, context: str) -> list[str]:
        return [
            f"关于'{context[:40]}'需要哪些关键领域知识?",
            "有哪些边界条件或约束尚未明确?",
            "当前推理的前提假设是否成立?",
            "是否存在更高效或更鲁棒的替代方案?",
        ]
