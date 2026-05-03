"""LLM-based Consciousness — Real model-powered reasoning for the digital life form.

Provides concrete implementations of Consciousness backed by:
- Ollama (local, free)
- OpenAI-compatible APIs (DeepSeek, etc.)
- Configurable fallback chains

Usage:
    from livingtree.dna.llm_consciousness import LLMConsciousness
    consciousness = LLMConsciousness(model="qwen3:latest", base_url="http://localhost:11434")
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, Optional

import aiohttp
from loguru import logger

from .consciousness import Consciousness


class LLMConsciousness(Consciousness):
    """LLM-backed consciousness with streaming and chain-of-thought reasoning.

    Supports Ollama (local) and OpenAI-compatible remote APIs.
    Falls back to heuristic responses when LLM is unavailable.
    """

    def __init__(self, model: str = "qwen3:latest", base_url: str = "http://localhost:11434",
                 api_key: str = "", provider: str = "ollama",
                 temperature: float = 0.7, max_tokens: int = 4096,
                 context_window: int = 32768):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.provider = provider
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.context_window = context_window
        self._available = False
        self._checked = False

    async def _check_available(self) -> bool:
        """Check if the LLM backend is reachable."""
        if self._checked:
            return self._available

        try:
            if self.provider == "ollama":
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{self.base_url}/api/tags",
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        self._available = resp.status == 200
            else:
                self._available = bool(self.base_url)
        except Exception:
            self._available = False
        finally:
            self._checked = True

        if self._available:
            logger.info(f"LLM Consciousness: {self.model} available via {self.provider}")
        else:
            logger.warning(f"LLM Consciousness: {self.model} unavailable, using heuristic fallback")

        return self._available

    async def stream_of_thought(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """Stream token-by-token thought generation."""
        if not await self._check_available():
            async for token in self._heuristic_stream(prompt):
                yield token
            return

        messages = [
            {"role": "system", "content": "You are a thinking entity. Think step by step about the user's request. Output your thinking process in a stream-of-consciousness style."},
            {"role": "user", "content": prompt},
        ]

        try:
            async for token in self._stream_chat(messages, max_tokens=min(kwargs.get("max_tokens", 1024), self.max_tokens)):
                yield token
        except Exception as e:
            logger.warning(f"LLM stream_of_thought failed: {e}, using fallback")
            async for token in self._heuristic_stream(prompt):
                yield token

    async def chain_of_thought(self, question: str, steps: int = 3, **kwargs) -> str:
        """Multi-step chain-of-thought reasoning."""
        prompt = (
            f"Please perform chain-of-thought reasoning in {steps} steps for this question:\n\n"
            f"{question}\n\n"
            f"Format your response as:\n"
            f"Step 1: [first step reasoning]\n"
            f"Step 2: [second step reasoning]\n"
            f"Final Answer: [conclusion]"
        )

        if not await self._check_available():
            return self._heuristic_cot(question, steps)

        try:
            response = await self._complete(prompt, max_tokens=min(kwargs.get("max_tokens", 2048), self.max_tokens))
            return response
        except Exception as e:
            logger.warning(f"LLM chain_of_thought failed: {e}, using fallback")
            return self._heuristic_cot(question, steps)

    async def hypothesis_generation(self, problem: str, count: int = 3, **kwargs) -> list[str]:
        """Generate multiple hypotheses for a problem."""
        prompt = (
            f"Generate {count} distinct hypotheses or solution approaches for this problem:\n\n"
            f"{problem}\n\n"
            f"For each hypothesis, provide a distinct approach. Format:\n"
            f"Hypothesis 1: [approach]\n"
            f"Hypothesis 2: [approach]"
        )

        if not await self._check_available():
            return self._heuristic_hypotheses(problem, count)

        try:
            response = await self._complete(prompt, max_tokens=min(kwargs.get("max_tokens", 1024), self.max_tokens))
            hypotheses = []
            for line in response.split("\n"):
                if line.strip().startswith(("Hypothesis", "假设", "方案")):
                    hypotheses.append(line.strip())
            if len(hypotheses) < count:
                hypotheses.extend([line.strip() for line in response.split("\n") if len(line.strip()) > 20])
            return hypotheses[:count] if hypotheses else self._heuristic_hypotheses(problem, count)
        except Exception as e:
            logger.warning(f"LLM hypothesis_generation failed: {e}, using fallback")
            return self._heuristic_hypotheses(problem, count)

    async def self_questioning(self, context: str, **kwargs) -> list[str]:
        """Identify knowledge gaps through self-questioning."""
        prompt = (
            f"Based on this context, identify knowledge gaps and generate self-reflective questions:\n\n"
            f"{context}\n\n"
            f"Generate 3-5 questions about what information is missing, what assumptions are being made, "
            f"and what edge cases should be considered. Output one question per line."
        )

        if not await self._check_available():
            return self._heuristic_questions(context)

        try:
            response = await self._complete(prompt, max_tokens=min(kwargs.get("max_tokens", 1024), self.max_tokens))
            questions = [line.strip().lstrip("- ").rstrip("?") + "?" for line in response.split("\n") if "?" in line]
            return questions if questions else self._heuristic_questions(context)
        except Exception as e:
            logger.warning(f"LLM self_questioning failed: {e}, using fallback")
            return self._heuristic_questions(context)

    # ── LLM communication ──

    async def _complete(self, prompt: str, max_tokens: int = 2048) -> str:
        """Send a completion request to the LLM."""
        if self.provider == "ollama":
            return await self._ollama_complete(prompt, max_tokens)
        else:
            return await self._openai_compatible_complete(prompt, max_tokens)

    async def _ollama_complete(self, prompt: str, max_tokens: int) -> str:
        """Send completion to Ollama."""
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": max_tokens,
                },
            }
            async with session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                data = await resp.json()
                return data.get("response", "")

    async def _openai_compatible_complete(self, prompt: str, max_tokens: int) -> str:
        """Send completion to OpenAI-compatible API."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": max_tokens,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                data = await resp.json()
                return data["choices"][0]["message"]["content"]

    async def _stream_chat(self, messages: list[dict], max_tokens: int = 1024) -> AsyncIterator[str]:
        """Stream chat completion tokens."""
        if self.provider == "ollama":
            payload = {
                "model": self.model,
                "prompt": messages[-1]["content"] if messages else "",
                "system": messages[0]["content"] if messages and messages[0]["role"] == "system" else "",
                "stream": True,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": max_tokens,
                },
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    async for line in resp.content:
                        if line:
                            try:
                                data = json.loads(line)
                                token = data.get("response", "")
                                if token:
                                    yield token
                            except Exception:
                                continue
        else:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    async for line in resp.content:
                        line_text = line.decode("utf-8").strip()
                        if line_text.startswith("data: "):
                            data_str = line_text[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                delta = data.get("choices", [{}])[0].get("delta", {})
                                token = delta.get("content", "")
                                if token:
                                    yield token
                            except Exception:
                                continue

    # ── Heuristic fallbacks ──

    async def _heuristic_stream(self, prompt: str) -> AsyncIterator[str]:
        """Fallback heuristic stream of thought."""
        thoughts = [
            f"分析: {prompt[:60]}...",
            f"处理中: 正在理解输入意图...",
            f"推理: 提取关键信息并匹配知识库...",
            f"规划: 制定解决方案路线图...",
            f"执行: 准备调用所需能力...",
        ]
        for thought in thoughts:
            await asyncio.sleep(0.05)
            yield thought + "\n"

    def _heuristic_cot(self, question: str, steps: int) -> str:
        """Fallback chain-of-thought."""
        result = []
        for i in range(steps):
            result.append(f"Step {i + 1}: 分析维度 {i + 1}，{question[:40]} 的第{i + 1}个方面")
        result.append(f"结论: 经过{steps}步推理，建议系统性地分析和解决该问题。")
        return "\n".join(result)

    def _heuristic_hypotheses(self, problem: str, count: int) -> list[str]:
        """Fallback hypothesis generation."""
        approaches = ["分解方法", "类比推理", "专家系统", "数据驱动", "迭代优化"]
        return [f"假设{i + 1}: 使用{approaches[i % len(approaches)]}处理 {problem[:30]}" for i in range(count)]

    def _heuristic_questions(self, context: str) -> list[str]:
        """Fallback self-questioning."""
        return [
            f"关于'{context[:40]}'需要哪些领域知识?",
            "有哪些边界情况尚未考虑?",
            "当前假设是否正确?",
            "是否有更高效的方法?",
        ]
