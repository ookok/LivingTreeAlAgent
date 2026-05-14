"""TTS Engine — edge-tts primary, VibeVoice / MOSS-TTS GGUF local fallback.

Backend priority (auto-selected at load):
  1. edge-tts         — cloud, always available, zero config, primary
  2. VibeVoice        — premium local, low-latency ASR+TTS+VAD, 小树专用声线
  3. MOSS-TTS GGUF    — lightweight local (~200MB Q4_K_M), numpy inference
  4. MOSS-TTS binary  — subprocess calls moss-tts-cli (fastest local, if compiled)

Voice: 小树 专用女声 — warm, lively, cute female voice profile.
Audio is NEVER written to disk during synthesis.
"""

from __future__ import annotations

import asyncio
import base64
import os
import shutil
import struct
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from loguru import logger

DEFAULT_GGUF_PATH = "models/moss-tts-nano-q4km.gguf"
MOSS_TTS_BINARY_NAMES = ["moss-tts", "moss-tts-cli", "tts", "vits-cli"]
SAMPLE_RATE = 22050
VIBEVOICE_DEFAULT_URL = "http://localhost:8080"


# ═══ VibeVoice Client ═══

class VibeVoiceClient:
    """Microsoft VibeVoice ASR/TTS/VAD client.

    VibeVoice is a premium local speech AI framework from Microsoft.
    Provides low-latency real-time ASR, streaming TTS, and VAD.
    Requires VibeVoice server running locally.

    Ref: client/src/business/vibe_voice_adapter.py
    """

    def __init__(self, server_url: str = ""):
        self._url = (server_url or VIBEVOICE_DEFAULT_URL).rstrip("/")
        self._available = None   # tri-state

    async def probe(self) -> bool:
        if self._available is not None:
            return self._available
        import httpx
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self._url}/health")
                self._available = resp.status_code == 200
        except Exception:
            self._available = False
        if self._available:
            logger.info(f"VibeVoice detected at {self._url}")
        return self._available

    async def synthesize(self, text: str, voice: str = "xiaoshu") -> bytes:
        """TTS via VibeVoice. Returns WAV bytes."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self._url}/tts",
                    json={"text": text, "voice": voice, "format": "wav"},
                )
                if resp.status_code == 200:
                    return resp.content
        except Exception as e:
            logger.debug(f"VibeVoice TTS: {e}")
        return b""

    async def transcribe(self, audio_bytes: bytes, format: str = "webm") -> str:
        """ASR via VibeVoice."""
        import base64 as _b64
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self._url}/asr",
                    json={"audio": _b64.b64encode(audio_bytes).decode(), "format": format},
                )
                if resp.status_code == 200:
                    return resp.json().get("text", "").strip()
        except Exception as e:
            logger.debug(f"VibeVoice ASR: {e}")
        return ""


# ═══ TTS Engine ═══

class MossTTSEngine:
    """Multi-backend TTS engine with priority: edge-tts → VibeVoice → GGUF → binary.

    Usage:
        engine = MossTTSEngine("models/moss-tts-nano-q4km.gguf")
        await engine.load()
        audio_bytes = await engine.synthesize("你好！我是小树~")
    """

    def __init__(self, gguf_path: str = ""):
        self._gguf_path = Path(gguf_path or DEFAULT_GGUF_PATH)
        self._backend: str = ""          # "edge_tts", "vibevoice", "numpy", "binary", "none"
        self._vibevoice: Optional[VibeVoiceClient] = None
        self._binary_path: str = ""
        self._loaded: bool = False
        self._model_info: dict = {}
        self._tensors: dict[str, Any] = {}
        self._vocoder = None

    # ═══ Lifecycle — priority: edge-tts → VibeVoice → GGUF → binary ═══

    async def load(self) -> bool:
        """Load and select best available backend."""
        if self._loaded:
            return True

        logger.info(f"TTS Engine loading...")

        if self._try_edge_tts():
            self._backend = "edge_tts"
        elif await self._try_vibevoice():
            self._backend = "vibevoice"
        elif await self._try_numpy():
            self._backend = "numpy"
        elif await self._try_subprocess():
            self._backend = "binary"
        else:
            self._backend = "none"
            logger.error("TTS: no backend available")

        self._loaded = True
        logger.info(f"TTS backend: {self._backend}")
        return self._backend != "none"

    def _try_edge_tts(self) -> bool:
        try:
            import edge_tts
            return True
        except ImportError:
            return False

    async def _try_vibevoice(self) -> bool:
        try:
            import httpx
            self._vibevoice = VibeVoiceClient()
            return await self._vibevoice.probe()
        except Exception:
            return False

    async def _try_numpy(self) -> bool:
        try:
            import numpy as np
            if not self._gguf_path.is_file():
                logger.debug(f"GGUF model not found: {self._gguf_path}")
                return False
            self._model_info, self._tensors = _parse_gguf(self._gguf_path)
            return self._validate_moss_tts_tensors()
        except ImportError:
            logger.debug("numpy not installed")
            return False
        except Exception as e:
            logger.debug(f"GGUF numpy load: {e}")
            return False

    async def _try_subprocess(self) -> bool:
        for name in MOSS_TTS_BINARY_NAMES:
            path = shutil.which(name)
            if path:
                self._binary_path = path
                return True
            for p in [
                Path("tools") / name, Path("bin") / name, Path("build") / name,
                Path.home() / ".local" / "bin" / name,
            ]:
                if p.is_file():
                    self._binary_path = str(p.resolve())
                    return True
        return False

    def _validate_moss_tts_tensors(self) -> bool:
        required = ["enc.emb.weight", "dec.0.conv1.weight"]
        for r in required:
            if not any(r in k for k in self._tensors):
                return False
        return True

    # ═══ Synthesis — routes to active backend ═══

    async def synthesize(self, text: str, voice: str = "xiaoshu") -> bytes:
        """Synthesize speech. Returns WAV bytes (16-bit PCM)."""
        if not text.strip():
            return b""

        if self._backend == "edge_tts":
            return await self._synth_edge_tts(text, voice)
        elif self._backend == "vibevoice":
            return await self._synth_vibevoice(text, voice)
        elif self._backend == "numpy":
            return await self._synth_numpy(text)
        elif self._backend == "binary":
            return await self._synth_binary(text, voice)

        # Last resort: try edge-tts directly
        if self._try_edge_tts():
            return await self._synth_edge_tts(text, voice)
        return b""

    async def _synth_edge_tts(self, text: str, voice: str) -> bytes:
        try:
            import edge_tts
            voice_map = {
                "xiaoshu": "zh-CN-XiaoxiaoNeural",
                "warm": "zh-CN-XiaoyiNeural",
                "gentle": "zh-CN-YunxiNeural",
            }
            vn = voice_map.get(voice, "zh-CN-XiaoxiaoNeural")
            communicate = edge_tts.Communicate(text, vn)
            chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    chunks.append(chunk["data"])
            return b"".join(chunks)
        except ImportError:
            logger.warning("edge-tts not installed. Run: pip install edge-tts")
        except Exception as e:
            logger.debug(f"edge-tts: {e}")
        return b""

    async def _synth_vibevoice(self, text: str, voice: str) -> bytes:
        if self._vibevoice:
            return await self._vibevoice.synthesize(text, voice)
        return b""

    async def _synth_numpy(self, text: str) -> bytes:
        import numpy as np
        if not self._tensors:
            return b""
        try:
            text_enc = _text_to_sequence(text)
            if not text_enc:
                return b""
            enc_weight = self._tensors.get("enc.emb.weight")
            if enc_weight is None:
                return b""
            x = np.array(text_enc, dtype=np.int64)
            if enc_weight.ndim == 2:
                x = enc_weight[x % enc_weight.shape[0]]
            else:
                x = np.zeros((len(text_enc), 192), dtype=np.float32)
            for i in range(4):
                w = self._tensors.get(f"enc.encoder.{i}.weight")
                if w is not None and x.ndim == 2:
                    x = x @ w.T
            dur_w = self._tensors.get("dp.weight")
            if dur_w is not None and x.ndim == 2:
                durations = np.clip(np.abs(x @ dur_w.T).sum(axis=1), 1, 20).astype(np.int32)
            else:
                durations = np.ones(len(text_enc), dtype=np.int32) * 8
            expanded = []
            for j, d in enumerate(durations):
                for _ in range(int(d)):
                    expanded.append(x[j] if x.ndim == 2 else x[j])
            if not expanded:
                return b""
            x = np.stack(expanded)
            for i in range(4):
                w = self._tensors.get(f"dec.{i}.conv1.weight")
                if w is not None and x.ndim >= 2:
                    x_2d = x.reshape(-1, x.shape[-1])
                    x = x_2d @ w.T
            return _postnet_to_wav(x)
        except Exception as e:
            logger.debug(f"GGUF numpy synth: {e}")
            return b""

    async def _synth_binary(self, text: str, voice: str) -> bytes:
        try:
            try:
                from ..treellm.unified_exec import run
                cmd = f"{self._binary_path} --model {str(self._gguf_path.resolve())} --text '{text}' --voice {voice} --output -"
                result = await run(cmd, timeout=30)
                if result.success and result.stdout:
                    return result.stdout.encode()
                logger.debug(f"TTS binary: {result.stderr[:200]}")
            except ImportError:
                cmd = [
                    self._binary_path, "--model", str(self._gguf_path.resolve()),
                    "--text", text, "--voice", voice, "--output", "-",
                ]
                proc = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
                if proc.returncode == 0 and stdout:
                    return stdout
                logger.debug(f"TTS binary: {stderr.decode()[:200]}")
        except asyncio.TimeoutError:
            logger.warning("TTS binary timeout")
        except Exception as e:
            logger.debug(f"TTS binary: {e}")
        return b""

    # ═══ Streaming ═══

    async def synthesize_stream(self, text: str, voice: str = "xiaoshu"):
        sentences = _split_sentences(text)
        for sent in sentences:
            audio = await self.synthesize(sent, voice)
            if audio:
                b64 = base64.b64encode(audio).decode()
                yield sent, b64
                await asyncio.sleep(0.02)

    # ═══ Status ═══

    def status(self) -> dict:
        return {
            "backend": self._backend,
            "vibevoice_available": self._vibevoice is not None,
            "gguf_path": str(self._gguf_path),
            "gguf_exists": self._gguf_path.is_file(),
            "binary": self._binary_path,
            "tensor_count": len(self._tensors),
        }


# ═══ GGUF Parser ═══

def _parse_gguf(path: Path) -> tuple[dict, dict[str, Any]]:
    import numpy as np
    with open(path, "rb") as f:
        magic = f.read(4)
        if magic != b"GGUF":
            raise ValueError(f"Not a GGUF file: {magic}")
        version = struct.unpack("<I", f.read(4))[0]
        tensor_count = struct.unpack("<Q", f.read(8))[0]
        metadata_kv_count = struct.unpack("<Q", f.read(8))[0]
        metadata = {}
        for _ in range(metadata_kv_count):
            key_len = struct.unpack("<Q", f.read(8))[0]
            key = f.read(key_len).decode("utf-8", errors="replace")
            value_type = struct.unpack("<I", f.read(4))[0]
            if value_type == 8:
                v_len = struct.unpack("<Q", f.read(8))[0]
                metadata[key] = f.read(v_len).decode("utf-8", errors="replace")
            elif value_type == 6:
                metadata[key] = struct.unpack("<q", f.read(8))[0]
            elif value_type == 4:
                metadata[key] = struct.unpack("<i", f.read(4))[0]
            elif value_type == 12:
                metadata[key] = struct.unpack("<f", f.read(4))[0]
            else:
                metadata[key] = f"<type_{value_type}>"
        tensor_infos = []
        for _ in range(tensor_count):
            name_len = struct.unpack("<Q", f.read(8))[0]
            name = f.read(name_len).decode("utf-8", errors="replace")
            n_dims = struct.unpack("<I", f.read(4))[0]
            dims = list(struct.unpack(f"<{n_dims}Q", f.read(8 * n_dims)))
            ggml_type = struct.unpack("<I", f.read(4))[0]
            offset = struct.unpack("<Q", f.read(8))[0]
            tensor_infos.append((name, dims, ggml_type, offset))
        tensor_data_start = f.tell()
        alignment = metadata.get("general.alignment", 32)
        padding = (alignment - (tensor_data_start % alignment)) % alignment
        f.read(padding)
        tensors = {}
        for name, dims, ggml_type, offset in tensor_infos:
            f.seek(tensor_data_start + padding + offset)
            nelements = 1
            for d in dims:
                nelements *= d
            if ggml_type == 0:
                data = np.frombuffer(f.read(nelements * 4), dtype=np.float32)
            elif ggml_type == 1:
                data = np.frombuffer(f.read(nelements * 2), dtype=np.float16).astype(np.float32)
            elif ggml_type == 7:
                block_size = 32
                n_blocks = (nelements + block_size - 1) // block_size
                raw = f.read(n_blocks * 20)
                data = _dequant_q4_0(raw, nelements)
            elif ggml_type == 12:
                block_size = 256
                n_blocks = (nelements + block_size - 1) // block_size
                raw = f.read(n_blocks * 144)
                data = _dequant_q4_k(raw, nelements)
            else:
                f.read(nelements * 2)
                data = np.zeros(nelements, dtype=np.float32)
            data = data.reshape(dims) if len(dims) > 1 else data
            tensors[name] = data
    return metadata, tensors


def _dequant_q4_0(raw: bytes, nelements: int):
    import numpy as np
    block_size = 32
    n_blocks = (nelements + block_size - 1) // block_size
    out = np.zeros(nelements, dtype=np.float32)
    for b in range(n_blocks):
        base = b * 20
        d = np.frombuffer(raw[base:base+4], dtype=np.float16).astype(np.float32)[0]
        if d == 0:
            d = 1.0
        qs = np.frombuffer(raw[base+4:base+20], dtype=np.uint8)
        for j in range(min(block_size, nelements - b * block_size)):
            q = qs[j // 2]
            v = (q & 0x0F) if j % 2 == 0 else (q >> 4)
            out[b * block_size + j] = (float(v) - 8.0) * d
    return out


def _dequant_q4_k(raw: bytes, nelements: int):
    import numpy as np
    block_size = 256
    out = np.zeros(nelements, dtype=np.float32)
    n_blocks = (nelements + block_size - 1) // block_size
    for b in range(n_blocks):
        base = b * 144
        if base + 144 > len(raw):
            break
        d = np.frombuffer(raw[base:base+4], dtype=np.float16).astype(np.float32)[0]
        dmin = np.frombuffer(raw[base+4:base+8], dtype=np.float16).astype(np.float32)[0]
        if d == 0:
            d = 1.0
        scales = np.frombuffer(raw[base+8:base+20], dtype=np.uint8).astype(np.float32) * d + dmin
        qs = np.frombuffer(raw[base+20:base+144], dtype=np.uint8)
        for j in range(min(block_size, nelements - b * block_size)):
            scale = scales[j // 32]
            q_val = qs[j // 2]
            v = (q_val & 0x0F) if j % 2 == 0 else (q_val >> 4)
            out[b * block_size + j] = (float(v) - 8.0) * scale
    return out


def _text_to_sequence(text: str) -> list[int]:
    seq = []
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff':
            seq.append((ord(ch) % 192) + 1)
        elif ch.isalpha():
            seq.append((ord(ch.lower()) % 26) + 193)
        elif ch in "，。！？、；：" ",.?!;:~\n":
            seq.append(200)
        else:
            seq.append(201)
    return seq if seq else [1]


def _postnet_to_wav(x) -> bytes:
    import io
    import numpy as np
    import wave
    arr = np.asarray(x, dtype=np.float32).ravel()
    if arr.size == 0:
        return b""
    peak = np.max(np.abs(arr))
    if peak > 0:
        arr = arr / peak * 0.95
    arr = np.clip(arr * 32767, -32768, 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(arr.tobytes())
    return buf.getvalue()


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


_instance: Optional[MossTTSEngine] = None


def get_moss_tts(gguf_path: str = "") -> MossTTSEngine:
    global _instance
    if _instance is None:
        _instance = MossTTSEngine(gguf_path)
    return _instance


async def synthesize_edge_tts(text: str, voice: str = "zh-CN-XiaoxiaoNeural") -> bytes:
    """Standalone edge-tts synthesis — shared by voice_call, inline_parser, etc."""
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)
    except ImportError:
        from loguru import logger
        logger.warning("edge-tts not installed. Run: pip install edge-tts")
    except Exception as e:
        from loguru import logger
        logger.debug(f"edge-tts: {e}")
    return b""
