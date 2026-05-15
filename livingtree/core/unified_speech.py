"""Unified Speech Pipeline — speech-native auto-selector for LivingTree.

Inspired by MiniMind-O: a single small model replaces the traditional
STT → LLM → TTS three-stage pipeline with end-to-end speech understanding.

Modes (auto-selected by model availability):
  Mode A: Speech-Native (MiniMind-O, Qwen2.5-Omni) — audio bytes → model → response
  Mode B: STT→LLM→TTS (Whisper + Qwen + edge-tts) — traditional 3-stage fallback
  Mode C: STT→LLM (Whisper + Qwen, text response only) — minimal fallback

Integration:
  - PhenomenalConsciousness: voice-tone → VAD emotional vector (shared VADVector)
  - AnimePersona: voice-driven avatar expressions
  - IM Core: real-time voice calls with optimal mode routing
"""

from __future__ import annotations

from ..dna.identity import get_identity_prompt

import asyncio
import base64
import json as _json
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger

from ..dna.phenomenal_consciousness import VADVector


class SpeechMode(str, Enum):
    SPEECH_NATIVE = "speech_native"     # Model A: end-to-end speech model
    STT_LLM_TTS = "stt_llm_tts"         # Mode B: STT → LLM → TTS pipeline
    STT_LLM = "stt_llm"                 # Mode C: STT → LLM (text only)
    NONE = "none"                       # No speech capability


@dataclass
class SpeechResult:
    mode: SpeechMode
    text: str = ""
    audio_bytes: bytes = b""
    audio_format: str = "wav"
    vad: Optional[VADVector] = None       # voice-tone emotion
    model_used: str = ""
    latency_ms: float = 0.0
    ok: bool = False
    error: str = ""


# ═══ Unified Speech Pipeline ═══

class UnifiedSpeechPipeline:
    """Auto-selecting speech pipeline for LivingTree.

    Detects available speech models via Ollama and routes audio input
    through the optimal processing mode.

    Usage:
        pipeline = get_speech_pipeline()
        await pipeline.probe()
        result = await pipeline.hear(audio_bytes)
        # result.text    — transcribed/understood text
        # result.audio   — synthesized response audio (if TTS available)
        # result.vad     — voice-tone emotion vector
        # result.mode    — which pipeline was used
    """

    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self._ollama_url = ollama_url.rstrip("/")
        self._mode: SpeechMode = SpeechMode.NONE
        self._speech_native_model: str = ""
        self._text_model: str = "qwen3.5:4b"
        self._stt_model: str = "whisper:latest"
        self._tts_enabled: bool = False
        self._probed: bool = False
        self._vad_history: deque[VADVector] = deque(maxlen=32)

    # ═══ Probe & Auto-Select ═══

    async def probe(self) -> dict:
        """Detect available speech models and select optimal mode."""
        if self._probed:
            return self.status()

        import httpx

        mode = SpeechMode.NONE
        speech_model = ""
        stt_available = False

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._ollama_url}/api/tags")
                if resp.status_code != 200:
                    return self.status()

                tags = resp.json().get("models", [])
                model_names = [m.get("name", "") for m in tags]

                for name in model_names:
                    nl = name.lower()
                    if "minimind-o" in nl or ("omni" in nl and "qwen" in nl):
                        mode = SpeechMode.SPEECH_NATIVE
                        speech_model = name
                        logger.info(f"Speech-native model found: {name}")
                        break

                if mode == SpeechMode.NONE:
                    for name in model_names:
                        nl = name.lower()
                        if "whisper" in nl or "sensevoice" in nl:
                            stt_available = True
                            self._stt_model = name
                            break

                    if stt_available:
                        mode = SpeechMode.STT_LLM_TTS
                        self._probe_tts()
                        if not self._tts_enabled:
                            mode = SpeechMode.STT_LLM

        except Exception as e:
            logger.debug(f"Speech model probe: {e}")

        self._mode = mode
        self._speech_native_model = speech_model
        self._probed = True
        logger.info(f"Speech pipeline mode: {mode.value} (model={speech_model or self._stt_model})")
        return self.status()

    def _probe_tts(self):
        try:
            import edge_tts
            self._tts_enabled = True
        except ImportError:
            self._tts_enabled = False

    def status(self) -> dict:
        return {
            "mode": self._mode.value,
            "speech_native_model": self._speech_native_model,
            "text_model": self._text_model,
            "stt_model": self._stt_model,
            "tts_enabled": self._tts_enabled,
            "vad_samples": len(self._vad_history),
        }

    # ═══ Main API ═══

    async def hear(self, audio_bytes: bytes, sample_rate: int = 16000) -> SpeechResult:
        """Process audio input through the optimal pipeline.

        Args:
            audio_bytes: Raw 16-bit PCM audio data
            sample_rate: Audio sample rate (default 16kHz)

        Returns:
            SpeechResult with text, optional audio response, and VAD emotion
        """
        t0 = time.time()

        if not self._probed:
            await self.probe()

        vad = VADVector.from_audio(audio_bytes, sample_rate)
        if vad.confidence > 0.3:
            self._vad_history.append(vad)

        if self._mode == SpeechMode.SPEECH_NATIVE:
            result = await self._hear_speech_native(audio_bytes)
        elif self._mode in (SpeechMode.STT_LLM_TTS, SpeechMode.STT_LLM):
            result = await self._hear_stt_pipeline(audio_bytes, sample_rate)
        else:
            result = SpeechResult(mode=SpeechMode.NONE, ok=False, error="No speech model available")

        result.vad = vad
        result.latency_ms = (time.time() - t0) * 1000
        return result

    async def _hear_speech_native(self, audio_bytes: bytes) -> SpeechResult:
        """Mode A: Send audio directly to a speech-native model via Ollama."""
        import httpx

        audio_b64 = base64.b64encode(audio_bytes).decode()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self._ollama_url}/api/generate",
                    json={
                        "model": self._speech_native_model,
                        "prompt": f"<audio>{audio_b64}</audio>",
                        "stream": False,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    text = data.get("response", "")
                    return SpeechResult(
                        mode=SpeechMode.SPEECH_NATIVE,
                        text=text,
                        model_used=self._speech_native_model,
                        ok=True,
                    )
                return SpeechResult(
                    mode=SpeechMode.SPEECH_NATIVE,
                    ok=False,
                    error=f"HTTP {resp.status_code}",
                )
        except Exception as e:
            return SpeechResult(mode=SpeechMode.SPEECH_NATIVE, ok=False, error=str(e))

    async def _hear_stt_pipeline(self, audio_bytes: bytes, sample_rate: int) -> SpeechResult:
        """Mode B/C: STT → LLM → (optional TTS) fallback pipeline."""
        text = await self._transcribe(audio_bytes, sample_rate)
        if not text:
            return SpeechResult(mode=SpeechMode.STT_LLM, ok=False, error="STT produced no text")

        llm_response = await self._llm_respond(text)
        if not llm_response:
            return SpeechResult(mode=SpeechMode.STT_LLM, text=text, ok=False, error="LLM produced no response")

        result = SpeechResult(
            mode=self._mode,
            text=llm_response,
            model_used=self._text_model,
            ok=True,
        )

        if self._mode == SpeechMode.STT_LLM_TTS:
            try:
                result.audio_bytes = await self._synthesize(llm_response)
                result.audio_format = "mp3"
            except Exception as e:
                logger.debug(f"TTS synthesis failed: {e}")

        return result

    async def _transcribe(self, audio_bytes: bytes, sample_rate: int) -> str:
        """STT via Ollama Whisper."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                audio_b64 = base64.b64encode(audio_bytes).decode()
                resp = await client.post(
                    f"{self._ollama_url}/api/generate",
                    json={
                        "model": self._stt_model,
                        "prompt": f"[transcribe audio: {audio_b64}]",
                        "stream": False,
                    },
                )
                if resp.status_code == 200:
                    return resp.json().get("response", "").strip()
        except Exception as e:
            logger.debug(f"STT failed: {e}")
        return ""

    async def _llm_respond(self, text: str) -> str:
        """Generate LLM response to transcribed text."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self._ollama_url}/api/chat",
                    json={
                        "model": self._text_model,
                        "messages": [
                            {"role": "system", "content": get_identity_prompt()},
                            {"role": "user", "content": text},
                        ],
                        "stream": False,
                    },
                )
                if resp.status_code == 200:
                    msg = resp.json().get("message", {})
                    return msg.get("content", "")
        except Exception as e:
            logger.debug(f"LLM call failed: {e}")
        return ""

    async def _synthesize(self, text: str) -> bytes:
        """TTS via edge-tts."""
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
            chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    chunks.append(chunk["data"])
            return b"".join(chunks)
        except ImportError:
            raise RuntimeError("edge-tts not installed. Run: pip install edge-tts")
        except Exception as e:
            raise RuntimeError(f"TTS failed: {e}")

    # ═══ Direct Transcribe (for chat voice input) ═══

    async def transcribe_direct(self, audio_bytes: bytes, format: str = "webm") -> dict:
        """Transcribe audio directly — for real-time chat voice input.

        Audio is NOT stored on disk. Processing is in-memory only.
        Routes to Ollama Whisper or returns error with guidance.

        Args:
            audio_bytes: Raw audio bytes (webm, wav, pcm)
            format: Source format hint (webm, wav, pcm)

        Returns:
            {"ok": bool, "text": str, "vad": dict, "error": str}
        """
        if not audio_bytes or len(audio_bytes) < 500:
            return {"ok": False, "text": "", "error": "audio too short", "vad": {}}

        import httpx
        audio_b64 = base64.b64encode(audio_bytes).decode()

        vad = VADVector.from_audio(audio_bytes)
        if vad.confidence > 0.3:
            self._vad_history.append(vad)

        if self._mode == SpeechMode.NONE:
            await self.probe()

        if self._stt_model:
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        f"{self._ollama_url}/api/generate",
                        json={
                            "model": self._stt_model,
                            "prompt": f"Transcribe this audio to text: [base64:{audio_b64}]",
                            "stream": False,
                            "options": {"temperature": 0.0},
                        },
                    )
                    if resp.status_code == 200:
                        text = resp.json().get("response", "").strip()
                        if text:
                            return {"ok": True, "text": text, "vad": vad.to_dict()}
            except Exception as e:
                logger.warning(f"Whisper STT failed: {e}")

        # Fallback: try browser-side Whisper via Transformers.js hint
        return {
            "ok": False,
            "text": "",
            "error": "Whisper model not available. Pull it with: ollama pull whisper",
            "vad": vad.to_dict(),
            "hint": "Install whisper: ollama pull whisper",
        }

    # ═══ Voice Tone Emotion ═══

    def get_vad_vector(self) -> Optional[VADVector]:
        """Get the most recent voice-tone VAD vector."""
        return self._vad_history[-1] if self._vad_history else None

    def get_vad_trend(self, window: int = 8) -> dict:
        """Get VAD trend over recent utterances."""
        history = list(self._vad_history)[-window:]
        if not history:
            return {"valence": 0, "arousal": 0, "dominance": 0, "samples": 0}

        return {
            "valence": round(sum(v.valence for v in history) / len(history), 3),
            "arousal": round(sum(v.arousal for v in history) / len(history), 3),
            "dominance": round(sum(v.dominance for v in history) / len(history), 3),
            "samples": len(history),
        }


_instance: Optional[UnifiedSpeechPipeline] = None


def get_speech_pipeline(ollama_url: str = "http://localhost:11434") -> UnifiedSpeechPipeline:
    global _instance
    if _instance is None:
        _instance = UnifiedSpeechPipeline(ollama_url)
    return _instance
