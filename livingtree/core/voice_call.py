"""Voice Call Engine — real-time bilateral voice conversation with 小树.

Backend priority chain:
  TTS:      edge-tts (primary) → VibeVoice (premium local) → MOSS-TTS GGUF (local)
  LLM:      TreeLLM providers (primary) → llama.cpp (local fallback) → Ollama
  STT:      edge-tts ASR → VibeVoice ASR → llama.cpp whisper → Ollama whisper

Audio is NEVER stored to disk. All processing is in-memory streaming.
Voice persona: 活跃可爱温暖的女声 (小树专用声线).
"""

from __future__ import annotations

import asyncio
import base64
import json as _json
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

XIAOSHU_VOICE = "xiaoshu"

# ── Voice identity: extends the base identity with voice-specific style ──
from ..dna.identity import get_identity_prompt, XIAOSHU_VOICE_STYLE
XIAOSHU_SYSTEM = get_identity_prompt() + "\n\n" + XIAOSHU_VOICE_STYLE


@dataclass
class CallState:
    ws: WebSocket
    session_id: str = ""
    user_talking: bool = False
    pending_text: str = ""
    created: float = field(default_factory=time.time)
    turn_count: int = 0
    history: list[dict] = field(default_factory=list)   # conversation context


class VoiceCallEngine:
    """Manages real-time voice calls between user and 小树.

    LLM:  llama.cpp server (primary) → Ollama (fallback)
    TTS:  MOSS-TTS-Nano GGUF (primary) → edge-tts (fallback)
    STT:  llama.cpp whisper (primary) → Ollama whisper (fallback)
    """

    def __init__(self):
        self._active: dict[str, CallState] = {}
        self._llamacpp = None          # lazy-init
        self._moss_tts = None          # lazy-init
        self._moss_loaded = False
        self._llamacpp_available = None   # tri-state: None=unchecked

    # ═══ Backend Lazy Init ═══

    async def _ensure_llamacpp(self) -> bool:
        if self._llamacpp_available is not None:
            return self._llamacpp_available

        from .llamacpp_backend import get_llamacpp
        self._llamacpp = get_llamacpp()
        health = await self._llamacpp.health()
        self._llamacpp_available = health.get("ok", False)
        if self._llamacpp_available:
            logger.info("Voice: llama.cpp backend active")
        else:
            logger.info("Voice: llama.cpp unavailable, using Ollama fallback")
        return self._llamacpp_available

    async def _ensure_moss_tts(self) -> bool:
        if self._moss_loaded:
            return self._moss_tts is not None and self._moss_tts._backend not in ("none", "")

        from .moss_tts_engine import get_moss_tts
        self._moss_tts = get_moss_tts()
        ok = await self._moss_tts.load()
        self._moss_loaded = True
        if ok:
            logger.info(f"Voice: MOSS-TTS active (backend={self._moss_tts._backend})")
        else:
            logger.info("Voice: MOSS-TTS unavailable, using edge-tts fallback")
        return ok

    # ═══ Session Management ═══

    async def handle(self, ws: WebSocket):
        await ws.accept()
        sid = str(time.time_ns())[-12:]
        state = CallState(ws=ws, session_id=sid)
        self._active[sid] = state

        logger.info(f"Voice call started: session={sid}")

        try:
            await ws.send_json({"type": "ready", "voice": XIAOSHU_VOICE})
            await ws.send_json({"type": "listening"})

            async for msg_text in ws.iter_text():
                try:
                    msg = _json.loads(msg_text)
                    msg_type = msg.get("type", "")

                    if msg_type == "text":
                        raw = msg.get("data", "").strip()
                        if not raw:
                            continue

                        # Auto-detect: if it looks like base64 audio (>200 chars, not JSON)
                        if len(raw) > 200 and raw[0] not in ('{', '[', '<', '"'):
                            audio_bytes = base64.b64decode(raw)
                            raw = await self._stt_transcribe(audio_bytes)
                            if raw:
                                logger.info(f"Voice STT: {raw[:60]}")
                            else:
                                await ws.send_json({"type": "error", "message": "语音识别失败"})
                                continue

                        state.pending_text = raw
                        if state.pending_text:
                            state.user_talking = True
                            await ws.send_json({"type": "hearing", "partial": state.pending_text[:50]})

                    elif msg_type == "end_turn":
                        state.user_talking = False
                        if state.pending_text:
                            await self._process_turn(state)

                    elif msg_type == "ping":
                        await ws.send_json({"type": "pong"})

                except _json.JSONDecodeError:
                    logger.debug(f"Voice WS: bad JSON: {msg_text[:80]}")

        except WebSocketDisconnect:
            logger.info(f"Voice call ended: session={sid}")
        except Exception as e:
            logger.warning(f"Voice call error {sid}: {e}")
        finally:
            self._active.pop(sid, None)
            try:
                await ws.close()
            except Exception:
                pass

    # ═══ Turn Processing ═══

    async def _process_turn(self, state: CallState):
        text = state.pending_text.strip()
        state.pending_text = ""
        state.turn_count += 1

        if not text or len(text) < 2:
            return

        try:
            await state.ws.send_json({"type": "thinking"})

            llm_text = await self._call_llm(text, state)
            if not llm_text:
                await state.ws.send_json({"type": "done"})
                return

            await state.ws.send_json({"type": "speaking", "text": llm_text[:200]})

            await self._stream_tts(state, llm_text)

            await state.ws.send_json({"type": "listening"})

        except Exception as e:
            logger.warning(f"Turn processing error: {e}")
            try:
                await state.ws.send_json({"type": "error", "message": str(e)})
            except Exception:
                pass

    # ═══ LLM (TreeLLM primary → llama.cpp → Ollama) ═══

    async def _call_llm(self, text: str, state: CallState) -> str:
        response = await self._call_llm_treellm(text)
        if response:
            state.history.append({"role": "user", "content": text})
            state.history.append({"role": "assistant", "content": response})
            return response

        if await self._ensure_llamacpp():
            response = await self._llamacpp.chat(
                user_text=text,
                system_prompt=XIAOSHU_SYSTEM,
                history=state.history[-6:],
            )
            if response:
                state.history.append({"role": "user", "content": text})
                state.history.append({"role": "assistant", "content": response})
                return response

        response = await self._call_llm_ollama(text)
        if response:
            state.history.append({"role": "user", "content": text})
            state.history.append({"role": "assistant", "content": response})
        return response

    async def _call_llm_treellm(self, text: str) -> str:
        """Route through TreeLLM provider election (DeepSeek / LongCat / etc.)."""
        import httpx
        try:
            from ..config import get_config
            cfg = get_config().model
            base = cfg.deepseek_base_url
            key = cfg.deepseek_api_key
            if not key:
                return ""
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{base}/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={
                        "model": cfg.flash_model,
                        "messages": [
                            {"role": "system", "content": XIAOSHU_SYSTEM},
                            {"role": "user", "content": text},
                        ],
                        "temperature": 0.8,
                        "max_tokens": 256,
                        "stream": False,
                    },
                )
                if resp.status_code == 200:
                    choices = resp.json().get("choices", [])
                    if choices:
                        return choices[0]["message"]["content"].strip()
        except Exception as e:
            logger.debug(f"TreeLLM voice: {e}")
        return ""

    async def _call_llm_ollama(self, text: str) -> str:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "http://localhost:11434/api/chat",
                    json={
                        "model": "qwen3.5:4b",
                        "messages": [
                            {"role": "system", "content": XIAOSHU_SYSTEM},
                            {"role": "user", "content": text},
                        ],
                        "stream": False,
                        "options": {"temperature": 0.8, "top_p": 0.9},
                    },
                )
                if resp.status_code == 200:
                    msg = resp.json().get("message", {})
                    return msg.get("content", "").strip()
        except Exception as e:
            logger.debug(f"Ollama LLM: {e}")
        return ""

    # ═══ STT (llama.cpp whisper primary, Ollama fallback) ═══

    async def _stt_transcribe(self, audio_bytes: bytes) -> str:
        if await self._ensure_llamacpp():
            text = await self._llamacpp.transcribe(audio_bytes, "webm")
            if text:
                return text

        from .unified_speech import get_speech_pipeline
        pipeline = get_speech_pipeline()
        result = await pipeline.transcribe_direct(audio_bytes, "webm")
        return result.get("text", "") if result.get("ok") else ""

    # ═══ TTS (MOSS-TTS GGUF primary, edge-tts fallback) ═══

    async def _stream_tts(self, state: CallState, text: str):
        """Stream TTS audio chunks to client via WebSocket."""
        sentences = _split_sentences(text)
        if not sentences:
            return

        moss_ok = await self._ensure_moss_tts()

        for sentence in sentences:
            if moss_ok:
                audio = await self._moss_tts.synthesize(sentence, XIAOSHU_VOICE)
                fmt = "wav"
            else:
                from .moss_tts_engine import synthesize_edge_tts
                audio = await synthesize_edge_tts(sentence, "zh-CN-XiaoxiaoNeural")
                fmt = "mp3"

            if audio:
                try:
                    await state.ws.send_json({
                        "type": "audio",
                        "data": base64.b64encode(audio).decode(),
                        "format": fmt,
                        "text": sentence[:100],
                    })
                except Exception:
                    break
                await asyncio.sleep(0.05)


def _split_sentences(text: str) -> list[str]:
    import re
    parts = re.split(r'(?<=[。！？.!?\n])', text)
    result = []
    buf = ""
    for p in parts:
        if len(buf) + len(p) < 80:
            buf += p
        else:
            if buf.strip():
                result.append(buf.strip())
            buf = p
    if buf.strip():
        result.append(buf.strip())
    return result if result else [text]


_engine: Optional[VoiceCallEngine] = None


def get_voice_call_engine() -> VoiceCallEngine:
    global _engine
    if _engine is None:
        _engine = VoiceCallEngine()
    return _engine
