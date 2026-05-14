"""MultiModalPipeline — Unified facade for all input modalities.

Wires together the scattered multimodal infrastructure into a single pipeline:
  Image → modern_ocr → text (or VLM description)
  PDF → multimodal_parser → text + tables
  Audio → inline_parser STT → text
  Video → inline_parser audio extract → STT → text
  Speech → unified_speech TTS/STT pipeline

All outputs normalize to LivingInput for the unified architecture.

Integration:
  pipe = get_multimodal_pipeline()
  content = await pipe.process(file_path)          # auto-detect type
  content = await pipe.process(file_path, "image") # force type
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Optional

from loguru import logger


class MultiModalPipeline:
    """Unified multimodal processing facade."""

    _instance: Optional["MultiModalPipeline"] = None

    @classmethod
    def instance(cls) -> "MultiModalPipeline":
        if cls._instance is None:
            cls._instance = MultiModalPipeline()
        return cls._instance

    def __init__(self):
        self._processed = 0

    async def process(self, source: str | bytes,
                       mime_type: str = "") -> dict:
        """Process any input type into structured text. Returns {text, type, metadata}."""
        self._processed += 1

        if isinstance(source, bytes):
            return await self._process_bytes(source, mime_type)

        path = Path(source)
        if not path.exists():
            return {"text": f"[File not found: {source}]", "type": "error"}

        mime = mime_type or mimetypes.guess_type(str(path))[0] or ""
        suffix = path.suffix.lower()

        # Route to correct processor
        if suffix in ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff'):
            return await self._process_image(path)
        elif suffix == '.pdf':
            return await self._process_pdf(path)
        elif suffix in ('.mp3', '.wav', '.ogg', '.m4a', '.webm', '.flac', '.aac'):
            return await self._process_audio(path)
        elif suffix in ('.mp4', '.mkv', '.avi', '.mov', '.webm'):
            return await self._process_video(path)
        elif suffix in ('.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'):
            return await self._process_document(path)
        else:
            return {"text": path.read_text(errors="replace")[:100000], "type": "text"}

    # ── Processors ─────────────────────────────────────────────────

    async def _process_image(self, path: Path) -> dict:
        """OCR or VLM description for images."""
        try:
            from ..capability.modern_ocr import ModernOCR
            ocr = ModernOCR()
            text = ocr.extract_text(str(path))
            return {"text": text[:5000], "type": "image", "engine": "ocr"}
        except Exception:
            pass

        try:
            from ..capability.unified_visual_port import get_visual_port
            port = get_visual_port()
            result = port.render(str(path), format="text")
            return {"text": str(result)[:5000], "type": "image", "engine": "vlm"}
        except Exception:
            pass

        return {"text": f"[Image: {path.name}]", "type": "image", "engine": "none"}

    async def _process_pdf(self, path: Path) -> dict:
        """Extract text from PDF."""
        try:
            from ..capability.multimodal_parser import MultimodalParser
            parser = MultimodalParser()
            result = parser.parse(str(path))
            return {"text": str(result)[:100000], "type": "pdf"}
        except Exception:
            return {"text": f"[PDF: {path.name}]", "type": "pdf"}

    async def _process_audio(self, path: Path) -> dict:
        """Speech-to-text for audio files."""
        try:
            from ..core.unified_speech import UnifiedSpeech
            speech = UnifiedSpeech()
            result = speech.transcribe(str(path))
            return {"text": str(result)[:10000], "type": "audio"}
        except Exception:
            return {"text": f"[Audio: {path.name}]", "type": "audio"}

    async def _process_video(self, path: Path) -> dict:
        """Extract audio and transcribe for video."""
        try:
            from ..core.inline_parser import InlineParser
            parser = InlineParser()
            result = parser.extract_audio_text(str(path))
            return {"text": str(result)[:10000], "type": "video"}
        except Exception:
            return {"text": f"[Video: {path.name}]", "type": "video"}

    async def _process_document(self, path: Path) -> dict:
        """Extract text from Office documents."""
        try:
            from ..capability.multimodal_parser import MultimodalParser
            parser = MultimodalParser()
            result = parser.parse(str(path))
            return {"text": str(result)[:100000], "type": "document"}
        except Exception:
            return {"text": f"[Document: {path.name}]", "type": "document"}

    async def _process_bytes(self, data: bytes, mime_type: str) -> dict:
        import tempfile
        suffix = mimetypes.guess_extension(mime_type) or ".bin"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(data)
            tmp_path = f.name
        try:
            return await self.process(tmp_path, mime_type)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def stats(self) -> dict:
        return {"processed": self._processed}


_pipe: Optional[MultiModalPipeline] = None


def get_multimodal_pipeline() -> MultiModalPipeline:
    global _pipe
    if _pipe is None:
        _pipe = MultiModalPipeline()
    return _pipe


__all__ = ["MultiModalPipeline", "get_multimodal_pipeline"]
