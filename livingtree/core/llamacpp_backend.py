"""llama.cpp Backend — optimized local LLM inference.

Replaces Ollama with a llama.cpp server for improved performance.
Uses llama-server's OpenAI-compatible /v1/chat/completions endpoint.

Optimized parameters:
  - repeat_penalty: 1.1    (reduce repetition)
  - top_k: 40              (narrow sampling)
  - top_p: 0.9             (nucleus)
  - temperature: 0.8       (creative for voice)
  - context_size: 8192     (server-side)
  - threads: auto           (server-side)
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from loguru import logger

DEFAULT_LLAMACPP_URL = "http://localhost:8080"
DEFAULT_CHAT_MODEL = "qwen3.5-4b"


class LlamacppBackend:
    """Client for llama.cpp server (llama-server).

    llama-server provides an OpenAI-compatible API at /v1/chat/completions.
    Start it with:
        llama-server -m model.gguf -c 8192 -t 8 --port 8080

    Optimization flags for voice:
        --mlock          keep model in RAM
        --no-mmap        disable mmap (lower latency on some systems)
        --flash-attn     flash attention (faster)
        -ngl 99          offload all layers to GPU
    """

    def __init__(
        self,
        base_url: str = "",
        model: str = "",
        temperature: float = 0.8,
        top_p: float = 0.9,
        top_k: int = 40,
        repeat_penalty: float = 1.1,
        max_tokens: int = 512,
        timeout: float = 30.0,
    ):
        self._base_url = (base_url or DEFAULT_LLAMACPP_URL).rstrip("/")
        self._model = model or DEFAULT_CHAT_MODEL
        self._temperature = temperature
        self._top_p = top_p
        self._top_k = top_k
        self._repeat_penalty = repeat_penalty
        self._max_tokens = max_tokens
        self._timeout = timeout

    # ═══ Config ═══

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._base_url

    def configure(
        self,
        *,
        temperature: float = None,
        top_p: float = None,
        top_k: int = None,
        repeat_penalty: float = None,
        max_tokens: int = None,
    ):
        if temperature is not None:
            self._temperature = temperature
        if top_p is not None:
            self._top_p = top_p
        if top_k is not None:
            self._top_k = top_k
        if repeat_penalty is not None:
            self._repeat_penalty = repeat_penalty
        if max_tokens is not None:
            self._max_tokens = max_tokens

    # ═══ Core API ═══

    async def chat(
        self,
        user_text: str,
        system_prompt: str = "",
        history: list[dict] = None,
    ) -> str:
        """Send a chat message and get the text response.

        Args:
            user_text: User's message
            system_prompt: System prompt (persona)
            history: Previous messages [{"role":"user","content":"..."}, ...]

        Returns:
            Model response text, or empty string on failure
        """
        import httpx

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_text})

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "top_p": self._top_p,
            "top_k": self._top_k,
            "repeat_penalty": self._repeat_penalty,
            "max_tokens": self._max_tokens,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/v1/chat/completions",
                    json=payload,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "").strip()
                else:
                    logger.warning(f"llama.cpp: HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"llama.cpp chat failed: {e}")

        return ""

    async def health(self) -> dict:
        """Check if llama.cpp server is reachable."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self._base_url}/health")
                return {"ok": resp.status_code == 200, "status": resp.status_code}
        except Exception:
            return {"ok": False, "status": "unreachable"}

    # ═══ STT via llama.cpp ═══

    async def transcribe(self, audio_bytes: bytes, format: str = "webm") -> str:
        """Transcribe audio via llama.cpp (if it has whisper support).

        Note: llama.cpp has built-in whisper support when compiled with
        WHISPER=ON and loaded with a Whisper GGUF model.
        """
        import base64
        import httpx

        audio_b64 = base64.b64encode(audio_bytes).decode()

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self._base_url}/v1/audio/transcriptions",
                    json={"audio": audio_b64, "format": format},
                )
                if resp.status_code == 200:
                    return resp.json().get("text", "").strip()
        except Exception as e:
            logger.debug(f"llama.cpp STT: {e}")
        return ""


_instance: Optional[LlamacppBackend] = None


def get_llamacpp() -> LlamacppBackend:
    global _instance
    if _instance is None:
        _instance = LlamacppBackend()
    return _instance
