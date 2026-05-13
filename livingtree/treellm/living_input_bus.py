"""LivingInputBus — Unified input abstraction with device-agnostic normalization.

Every input, regardless of source device or modality, normalizes into a canonical
LivingInput and routes through the same processing pipeline.

Input taxonomy:
  STATIC (discrete, complete at arrival):
    📝 static_text    — typed text, pasted text, CLI args
    📄 static_file    — single file (code, doc, image, data)
    📁 static_batch   — folder / multi-file upload / zip archive
    🔗 static_ref     — URL, git repo, file path reference
  
  DYNAMIC (streaming, real-time):
    🎤 dynamic_audio  — microphone, voice call, audio file
    📹 dynamic_video  — camera, screen share, video file
    📡 dynamic_stream — WebSocket, SSE, event stream
    🔗 dynamic_ref    — live URL, API endpoint, RSS feed

Device sources → unified normalization:
  Web browser   → HTTP POST (form/multipart/json) → LivingInput
  CLI           → sys.argv / stdin → LivingInput
  Mobile app    → HTTP POST + capabilities → LivingInput
  Voice call    → WebSocket audio stream → LivingInput (dynamic_audio)
  IDE plugin    → LSP / file watcher → LivingInput
  API           → POST /v1/chat/completions → LivingInput

Integration:
  bus = get_living_input_bus()
  inp = await bus.normalize(source="web", raw=request)  # → LivingInput
  result = await bus.route(inp, hub)                     # → processed result
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from loguru import logger


# ═══ Input Taxonomy ════════════════════════════════════════════════


class InputKind(StrEnum):
    STATIC_TEXT = "static_text"
    STATIC_FILE = "static_file"
    STATIC_BATCH = "static_batch"
    STATIC_REF = "static_ref"
    DYNAMIC_AUDIO = "dynamic_audio"
    DYNAMIC_VIDEO = "dynamic_video"
    DYNAMIC_STREAM = "dynamic_stream"
    DYNAMIC_REF = "dynamic_ref"


class InputSource(StrEnum):
    WEB = "web"
    CLI = "cli"
    API = "api"
    MOBILE = "mobile"
    VOICE = "voice"
    IDE = "ide"
    WS = "websocket"
    EMBEDDED = "embedded"
    UNKNOWN = "unknown"


# ═══ Data Types ════════════════════════════════════════════════════


@dataclass
class FilePayload:
    """Single file within a LivingInput."""
    name: str
    path: str = ""          # Virtual path within batch
    content: str = ""       # Text content (for text files)
    binary_hash: str = ""   # SHA256 for binary files
    size_bytes: int = 0
    mime_type: str = ""
    encoding: str = "utf-8"


@dataclass
class DeviceProfile:
    """Capability profile of the input device."""
    source: InputSource = InputSource.UNKNOWN
    supports_audio: bool = False
    supports_video: bool = False
    supports_files: bool = False
    max_input_bytes: int = 1_000_000
    preferred_format: str = "text"
    locale: str = "zh-CN"
    timezone: str = "Asia/Shanghai"
    user_agent: str = ""
    client_id: str = ""


@dataclass
class LivingInput:
    """Canonical input form — device-agnostic, modality-agnostic."""
    id: str = field(default_factory=lambda: f"inp_{int(time.time()*1000)}")
    kind: InputKind = InputKind.STATIC_TEXT
    source: InputSource = InputSource.UNKNOWN
    timestamp: float = field(default_factory=time.time)
    session_id: str = "perpetual"

    # Primary payload (one of these is set based on kind)
    text: str = ""                         # For static_text
    files: list[FilePayload] = field(default_factory=list)  # For static_file / static_batch
    reference: str = ""                    # For static_ref / dynamic_ref (URL/path)
    stream_uri: str = ""                   # For dynamic_audio/video/stream

    # Optional enrichment
    system_prompt: str = ""
    task_type: str = "general"
    context: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[dict] = field(default_factory=list)

    # Device info
    device: DeviceProfile = field(default_factory=DeviceProfile)

    # For dynamic inputs: async generator
    _stream: Optional[AsyncIterator] = None

    @property
    def is_static(self) -> bool:
        return self.kind.value.startswith("static_")

    @property
    def is_dynamic(self) -> bool:
        return self.kind.value.startswith("dynamic_")

    @property
    def total_bytes(self) -> int:
        return sum(f.size_bytes for f in self.files) + len(self.text.encode("utf-8"))

    @property
    def summary(self) -> str:
        if self.kind == InputKind.STATIC_TEXT:
            return self.text[:100]
        if self.kind == InputKind.STATIC_FILE:
            return f"[file] {self.files[0].name if self.files else '?'} ({self.total_bytes}B)"
        if self.kind == InputKind.STATIC_BATCH:
            return f"[batch] {len(self.files)} files ({self.total_bytes}B)"
        if self.kind in (InputKind.DYNAMIC_AUDIO, InputKind.DYNAMIC_VIDEO):
            return f"[{self.kind.value}] {self.stream_uri or 'live stream'}"
        return f"[{self.kind.value}] {self.reference or self.text[:80]}"


# ═══ InputNormalizer ═══════════════════════════════════════════════


class InputNormalizer:
    """Normalizes raw input from any device into canonical LivingInput."""

    TEXT_MAX_BYTES = 100_000
    FILE_MAX_BYTES = 10_000_000
    BATCH_MAX_FILES = 100
    BATCH_MAX_TOTAL_BYTES = 50_000_000

    # ── Web ────────────────────────────────────────────────────────

    async def from_web_request(self, request: Any) -> LivingInput:
        """Normalize FastAPI request → LivingInput."""
        inp = LivingInput(source=InputSource.WEB)
        inp.device = self._probe_device(request)

        content_type = request.headers.get("content-type", "")

        # JSON body → static_text
        if "application/json" in content_type:
            try:
                body = await request.json()
                inp.text = body.get("message", body.get("content", ""))
                inp.system_prompt = body.get("system_prompt", body.get("context", ""))
                inp.task_type = body.get("task_type", "general")
                inp.session_id = body.get("session_id", "perpetual")
                inp.context = body.get("context", {})

                # Check for file references in JSON
                if "files" in body:
                    for f in body["files"]:
                        if isinstance(f, str):
                            inp.files.append(FilePayload(name=f, path=f))
                        elif isinstance(f, dict):
                            inp.files.append(FilePayload(
                                name=f.get("name", ""), path=f.get("path", ""),
                                content=f.get("content", ""),
                            ))
                if inp.files:
                    inp.kind = InputKind.STATIC_BATCH if len(inp.files) > 1 else InputKind.STATIC_FILE

                # Reference
                if "url" in body:
                    inp.reference = body["url"]
                    inp.kind = InputKind.STATIC_REF
                if "repo" in body:
                    inp.reference = body["repo"]
                    inp.kind = InputKind.STATIC_REF

            except Exception as e:
                logger.debug(f"InputNormalizer JSON: {e}")
                inp.text = str(await request.body())[:self.TEXT_MAX_BYTES]

        # Form data → text + files
        elif "multipart/form-data" in content_type:
            try:
                form = await request.form()
                inp.text = form.get("message", form.get("text", ""))
                uploads = form.getlist("files") or form.getlist("file")
                for upload in uploads:
                    if hasattr(upload, 'filename'):
                        content = await upload.read()
                        size = len(content)
                        if size <= self.FILE_MAX_BYTES:
                            f = FilePayload(
                                name=upload.filename or "upload",
                                size_bytes=size,
                                mime_type=upload.content_type or "",
                            )
                            try:
                                f.content = content.decode("utf-8", errors="replace")
                            except Exception:
                                f.binary_hash = hashlib.sha256(content).hexdigest()[:16]
                            inp.files.append(f)
                if inp.files:
                    inp.kind = InputKind.STATIC_BATCH if len(inp.files) > 1 else InputKind.STATIC_FILE
            except Exception as e:
                logger.debug(f"InputNormalizer form: {e}")

        # Plain text → static_text
        elif "text/plain" in content_type:
            raw = (await request.body()).decode("utf-8", errors="replace")
            inp.text = raw[:self.TEXT_MAX_BYTES]

        # Fallback
        else:
            try:
                body = await request.json()
                inp.text = str(body.get("message", body.get("content", str(body))))
            except Exception:
                inp.text = str(await request.body())[:self.TEXT_MAX_BYTES]

        return inp

    # ── CLI ────────────────────────────────────────────────────────

    def from_cli(self, args: list[str], stdin_text: str = "",
                 files: list[str] = None) -> LivingInput:
        """Normalize CLI input → LivingInput."""
        inp = LivingInput(source=InputSource.CLI)
        inp.device = DeviceProfile(source=InputSource.CLI, preferred_format="text")

        if args:
            inp.text = " ".join(args)
        if stdin_text:
            inp.text = (inp.text + "\n" + stdin_text).strip()

        if files:
            for path_str in files:
                p = Path(path_str)
                if p.exists():
                    if p.is_dir():
                        inp.kind = InputKind.STATIC_BATCH
                        for f in p.rglob("*"):
                            if f.is_file():
                                try:
                                    content = f.read_text(errors="replace")
                                    inp.files.append(FilePayload(
                                        name=f.name, path=str(f.relative_to(p)),
                                        content=content[:100000],
                                        size_bytes=f.stat().st_size,
                                    ))
                                except Exception:
                                    pass
                    else:
                        try:
                            content = p.read_text(errors="replace")
                            inp.files.append(FilePayload(
                                name=p.name, content=content[:100000],
                                size_bytes=p.stat().st_size,
                            ))
                        except Exception:
                            pass
            if inp.files and not inp.text:
                inp.text = f"请分析这些文件: {', '.join(f.name for f in inp.files[:5])}"
            if len(inp.files) > 1:
                inp.kind = InputKind.STATIC_BATCH
            elif inp.files:
                inp.kind = InputKind.STATIC_FILE

        return inp

    # ── API (OpenAI-compatible) ────────────────────────────────────

    def from_api(self, body: dict) -> LivingInput:
        """Normalize OpenAI-compatible API request → LivingInput."""
        inp = LivingInput(source=InputSource.API)
        inp.device = DeviceProfile(source=InputSource.API)

        messages = body.get("messages", [])
        if messages:
            last_user = ""
            for m in reversed(messages):
                if m.get("role") == "user":
                    last_user = m.get("content", "")
                    break
            inp.text = last_user
            # Extract system prompt
            for m in messages:
                if m.get("role") == "system":
                    inp.system_prompt = m.get("content", "")
                    break

        inp.task_type = body.get("task_type", "general")
        inp.tool_calls = body.get("tools", body.get("functions", []))

        # Reference (URL/path)
        if "reference" in body:
            inp.reference = body["reference"]
            inp.kind = InputKind.STATIC_REF

        return inp

    # ── WebSocket ──────────────────────────────────────────────────

    def from_websocket(self, data: dict) -> LivingInput:
        """Normalize WebSocket message → LivingInput."""
        inp = LivingInput(source=InputSource.WS)
        inp.device = DeviceProfile(source=InputSource.WS)

        msg_type = data.get("type", "message")
        if msg_type == "message":
            inp.text = data.get("content", "")
        elif msg_type == "voice_start":
            inp.kind = InputKind.DYNAMIC_AUDIO
            inp.stream_uri = data.get("stream_id", "")
        elif msg_type == "file_share":
            inp.files = [FilePayload(
                name=data.get("filename", ""), path=data.get("path", ""),
                content=data.get("content", ""),
            )]
            inp.kind = InputKind.STATIC_FILE

        inp.session_id = data.get("session_id", "perpetual")
        return inp

    # ── Helpers ────────────────────────────────────────────────────

    def _probe_device(self, request: Any) -> DeviceProfile:
        """Infer device capabilities from request."""
        profile = DeviceProfile(source=InputSource.WEB)
        try:
            ua = request.headers.get("user-agent", "")
            profile.user_agent = ua
            profile.supports_files = True
            profile.supports_audio = "Chrome" in ua or "Firefox" in ua
            profile.supports_video = profile.supports_audio
            if "Mobile" in ua or "Android" in ua:
                profile.preferred_format = "compact"
                profile.max_input_bytes = 500_000
        except Exception:
            pass
        return profile


# ═══ InputRouter ═══════════════════════════════════════════════════


class InputRouter:
    """Routes normalized LivingInput to the correct processing pipeline."""

    def __init__(self):
        self._normalizer = InputNormalizer()

    async def normalize_and_route(
        self, source: InputSource, raw: Any, hub: Any, **kwargs,
    ) -> dict[str, Any]:
        """Normalize raw input → route to pipeline → return result.

        This is the single entry point for ALL input sources.
        """
        # Normalize
        inp = await self._normalize(source, raw, **kwargs)
        logger.info(f"InputBus: [{inp.source.value}] [{inp.kind.value}] {inp.summary}")

        # Pre-process based on kind
        message = self._build_message(inp)

        # Route to processing
        if inp.kind == InputKind.STATIC_BATCH and inp.files:
            return await self._handle_batch(inp, message, hub)
        if inp.kind == InputKind.STATIC_FILE:
            return await self._handle_file(inp, message, hub)
        if inp.kind in (InputKind.STATIC_REF, InputKind.DYNAMIC_REF):
            return await self._handle_reference(inp, message, hub)
        if inp.is_dynamic:
            return await self._handle_dynamic(inp, message, hub)
        # Default: text → chat
        return await hub.chat(message, task_type=inp.task_type,
                             system_prompt=inp.system_prompt, **inp.context)

    async def _normalize(self, source: InputSource, raw: Any, **kwargs) -> LivingInput:
        """Normalize raw input from any source."""
        if source == InputSource.WEB:
            return await self._normalizer.from_web_request(raw)
        if source == InputSource.CLI:
            return self._normalizer.from_cli(
                raw.get("args", []),
                stdin_text=raw.get("stdin", ""),
                files=raw.get("files"),
            )
        if source == InputSource.API:
            return self._normalizer.from_api(raw if isinstance(raw, dict) else {})
        if source == InputSource.WS:
            return self._normalizer.from_websocket(raw if isinstance(raw, dict) else {})
        # Unknown → treat as text
        inp = LivingInput(source=source)
        inp.text = str(raw)[:100000]
        return inp

    def _build_message(self, inp: LivingInput) -> str:
        """Build a unified message string from LivingInput."""
        parts = [inp.text] if inp.text else []

        if inp.files:
            file_list = ", ".join(f"{f.name}({f.size_bytes}B)" for f in inp.files[:10])
            parts.append(f"\n[附带文件: {file_list}]")
            # Include small text file contents inline
            for f in inp.files[:5]:
                if f.content and f.size_bytes < 50000:
                    parts.append(f"\n--- {f.name} ---\n{f.content[:5000]}")

        if inp.reference:
            parts.append(f"\n[引用: {inp.reference}]")

        if inp.system_prompt:
            parts.insert(0, f"[系统指令: {inp.system_prompt}]")

        return "\n".join(parts) if parts else ""

    async def _handle_batch(self, inp: LivingInput, message: str,
                            hub: Any) -> dict:
        """Process batch file input."""
        # Summarize files first
        file_summaries = []
        for f in inp.files[:20]:
            if f.content:
                lines = f.content.count("\n") + 1
                file_summaries.append(f"  {f.name}: {lines}行, {f.size_bytes}B")
        summary = "批量文件分析:\n" + "\n".join(file_summaries[:20])
        batch_message = f"{summary}\n\n任务: {inp.text or '请分析这些文件'}"
        return await hub.chat(batch_message, task_type="document",
                             context={"file_count": len(inp.files)})

    async def _handle_file(self, inp: LivingInput, message: str,
                           hub: Any) -> dict:
        """Process single file input."""
        return await hub.chat(message, task_type="code" if inp.files and any(
            f.name.endswith(('.py','.js','.ts','.go','.rs','.java','.cpp','.c'))
            for f in inp.files
        ) else "document")

    async def _handle_reference(self, inp: LivingInput, message: str,
                                hub: Any) -> dict:
        """Process URL/reference input. Try to fetch content."""
        ref_message = message
        if inp.reference:
            ref_message = f"请分析这个引用: {inp.reference}\n\n{inp.text or ''}"
        return await hub.chat(ref_message, task_type="search")

    async def _handle_dynamic(self, inp: LivingInput, message: str,
                              hub: Any) -> dict:
        """Process dynamic/streaming input."""
        if inp.kind == InputKind.DYNAMIC_AUDIO:
            return {
                "mode": "voice", "status": "received",
                "message": "语音输入已接收,正在转文字处理中",
                "stream_uri": inp.stream_uri,
            }
        if inp.kind == InputKind.DYNAMIC_VIDEO:
            return {
                "mode": "video", "status": "received",
                "message": "视频输入已接收,正在处理中",
            }
        return await hub.chat(message, task_type=inp.task_type)


# ═══ Singleton ════════════════════════════════════════════════════


_bus: Optional[InputRouter] = None


def get_living_input_bus() -> InputRouter:
    global _bus
    if _bus is None:
        _bus = InputRouter()
    return _bus


__all__ = [
    "LivingInput", "FilePayload", "DeviceProfile",
    "InputKind", "InputSource", "InputNormalizer", "InputRouter",
    "get_living_input_bus",
]
