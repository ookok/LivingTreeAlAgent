"""Archive Previewer — in-memory archive inspection without disk writes.

Browse ZIP, TAR, GZ archives entirely in memory. List contents and extract
individual files on demand — no temporary files, no full extraction.

Inspired by dataset-viewer's ability to read ZIP central directory and
extract individual files without decompressing the entire archive.

Supported formats:
    .zip    — standard ZIP archives (central directory listing)
    .tar    — uncompressed TAR archives
    .tar.gz / .tgz — gzip-compressed TAR archives
    .gz     — single-file gzip compression

Usage:
    from livingtree.core.archive_preview import ArchivePreviewer

    previewer = ArchivePreviewer()
    entries = await previewer.list_files(zip_bytes, fmt="zip")
    content = await previewer.read_file(zip_bytes, "zip", "data.csv")
"""

from __future__ import annotations

import gzip
import io
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from loguru import logger

# ── Limits ──
MAX_ENTRIES = 10000       # Max files to enumerate in a single archive
MAX_PREVIEW_CHARS = 5000  # Default text preview limit


# ═══════════════════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ArchiveEntry:
    """A single file or directory inside an archive."""

    name: str                 # Relative path inside archive
    size: int                 # Uncompressed size in bytes
    compressed_size: int = 0  # Compressed size (0 if not available)
    is_dir: bool = False
    modified_time: float = 0.0

    @property
    def size_mb(self) -> float:
        return self.size / (1024 * 1024)

    @property
    def compression_ratio(self) -> float:
        """Compression ratio (0–1). 0 = no compression, 1 = 100% reduction."""
        if self.size == 0:
            return 0.0
        return round(1.0 - self.compressed_size / self.size, 3)


# ═══════════════════════════════════════════════════════════════════
# ArchivePreviewer
# ═══════════════════════════════════════════════════════════════════

class ArchivePreviewer:
    """In-memory archive browser — list, extract, preview without disk I/O.

    All methods operate on bytes in memory. No temporary files are created.
    """

    # ── Format Detection ──

    #: Mapping of file extensions → format identifier
    EXTENSION_MAP = {
        ".zip": "zip",
        ".tar": "tar",
        ".tar.gz": "tar.gz",
        ".tgz": "tar.gz",
        ".gz": "gz",
    }

    @staticmethod
    def detect_format(data: bytes, filename: str = "") -> str:
        """Detect archive format from magic bytes and/or file extension.

        Priority: magic bytes > extension.

        Returns:
            "zip", "tar", "tar.gz", "gz", or "" (unknown).
        """
        if not data or len(data) < 4:
            return ""

        # ── Magic byte checks ──
        # ZIP: PK\x03\x04
        if data[:4] == b'PK\x03\x04':
            return "zip"

        # Gzip: \x1f\x8b
        if data[:2] == b'\x1f\x8b':
            # Check for tar inside gzip by looking at the decompressed head
            try:
                decompressed = gzip.decompress(data[:1024])
                if len(decompressed) >= 262:
                    # Check for ustar magic at byte 257
                    if decompressed[257:262] == b'ustar':
                        return "tar.gz"
                return "gz"
            except Exception:
                return "gz"

        # TAR: ustar magic at byte 257 (uncompressed tar only)
        if len(data) >= 262 and data[257:262] == b'ustar':
            return "tar"

        # ── Fallback: extension ──
        ext = Path(filename).suffix.lower()
        if ext in ArchivePreviewer.EXTENSION_MAP:
            return ArchivePreviewer.EXTENSION_MAP[ext]
        if filename.lower().endswith(".tar.gz") or filename.lower().endswith(".tgz"):
            return "tar.gz"

        return ""

    # ── List Files ──

    async def list_files(
        self, data: bytes, fmt: str = "",
    ) -> list[ArchiveEntry]:
        """List all entries in an archive without extracting anything.

        For ZIP: reads the central directory (fast, no decompression).
        For TAR: reads the header blocks (fast, no file content).

        Args:
            data: Raw archive bytes.
            fmt: Format string ("zip", "tar", "tar.gz", "gz").
                 Auto-detected from magic bytes if empty.

        Returns:
            List of ArchiveEntry objects. Returns empty list for
            corrupted or unsupported archives.
        """
        if not data:
            return []

        fmt = fmt or self.detect_format(data)
        if not fmt:
            logger.debug("ArchivePreviewer: unknown format")
            return []

        try:
            handler = getattr(self, f"_list_{fmt.replace('.', '_')}", None)
            if handler is None:
                logger.debug(f"ArchivePreviewer: no handler for format '{fmt}'")
                return []
            return handler(data)
        except Exception as e:
            logger.warning(f"ArchivePreviewer: list failed for {fmt}: {e}")
            return []

    # ── Format-specific list implementations ──

    def _list_zip(self, data: bytes) -> list[ArchiveEntry]:
        """List ZIP contents via central directory (no decompression)."""
        entries: list[ArchiveEntry] = []
        with zipfile.ZipFile(io.BytesIO(data), 'r') as zf:
            for info in zf.infolist():
                if len(entries) >= MAX_ENTRIES:
                    logger.warning(
                        f"ArchivePreviewer: ZIP has >{MAX_ENTRIES} entries, "
                        f"truncating. Total entries unknown."
                    )
                    break
                entries.append(ArchiveEntry(
                    name=info.filename,
                    size=info.file_size,
                    compressed_size=info.compress_size,
                    is_dir=info.is_dir(),
                    modified_time=info.date_time[0] if info.date_time else 0.0,
                ))
        logger.debug(f"ArchivePreviewer: ZIP listed {len(entries)} entries")
        return entries

    def _list_tar(self, data: bytes) -> list[ArchiveEntry]:
        """List TAR contents from header blocks."""
        entries: list[ArchiveEntry] = []
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as tf:
            for member in tf.getmembers():
                if len(entries) >= MAX_ENTRIES:
                    logger.warning(
                        f"ArchivePreviewer: TAR has >{MAX_ENTRIES} entries, "
                        f"truncating."
                    )
                    break
                entries.append(ArchiveEntry(
                    name=member.name,
                    size=member.size,
                    compressed_size=0,  # TAR has no per-file compression info
                    is_dir=member.isdir(),
                    modified_time=member.mtime,
                ))
        logger.debug(f"ArchivePreviewer: TAR listed {len(entries)} entries")
        return entries

    def _list_tar_gz(self, data: bytes) -> list[ArchiveEntry]:
        """List tar.gz contents (decompress + read TAR headers)."""
        try:
            decompressed = gzip.decompress(data)
            return self._list_tar(decompressed)
        except Exception as e:
            logger.warning(f"ArchivePreviewer: tar.gz decompress failed: {e}")
            return []

    def _list_gz(self, data: bytes) -> list[ArchiveEntry]:
        """Gzip single file — return as single entry."""
        try:
            # Try to get uncompressed size from the gzip footer
            # (last 4 bytes are the original size modulo 2^32)
            uncompressed_size = int.from_bytes(data[-4:], 'little') if len(data) >= 4 else 0
        except Exception:
            uncompressed_size = 0

        return [ArchiveEntry(
            name="compressed_content",  # Generic name for bare .gz
            size=uncompressed_size,
            compressed_size=len(data),
            is_dir=False,
        )]

    # ── Read Single File ──

    async def read_file(
        self, data: bytes, fmt: str, entry_path: str,
    ) -> bytes | None:
        """Extract a single file from an archive entirely in memory.

        Only the target file is decompressed — the rest of the archive
        is untouched. For ZIP, this uses the central directory to seek
        directly to the target file's data.

        Args:
            data: Raw archive bytes.
            fmt: Format string ("zip", "tar", "tar.gz", "gz").
            entry_path: Relative path of the file to extract.

        Returns:
            File contents as bytes, or None if not found.
        """
        if not data or not entry_path:
            return None

        handler = getattr(self, f"_read_{fmt.replace('.', '_')}", None)
        if handler is None:
            logger.debug(f"ArchivePreviewer: no read handler for '{fmt}'")
            return None

        try:
            return handler(data, entry_path)
        except Exception as e:
            logger.warning(
                f"ArchivePreviewer: read '{entry_path}' from {fmt} failed: {e}"
            )
            return None

    def _read_zip(self, data: bytes, entry_path: str) -> bytes | None:
        """Read single file from ZIP using central directory lookup."""
        with zipfile.ZipFile(io.BytesIO(data), 'r') as zf:
            try:
                return zf.read(entry_path)
            except KeyError:
                logger.debug(f"ArchivePreviewer: '{entry_path}' not found in ZIP")
                return None

    def _read_tar(self, data: bytes, entry_path: str) -> bytes | None:
        """Read single file from TAR."""
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as tf:
            try:
                member = tf.getmember(entry_path)
                f = tf.extractfile(member)
                if f is None:
                    return None
                return f.read()
            except KeyError:
                logger.debug(f"ArchivePreviewer: '{entry_path}' not found in TAR")
                return None

    def _read_tar_gz(self, data: bytes, entry_path: str) -> bytes | None:
        """Read single file from tar.gz (decompress + extract)."""
        try:
            decompressed = gzip.decompress(data)
            return self._read_tar(decompressed, entry_path)
        except Exception as e:
            logger.warning(f"ArchivePreviewer: tar.gz read failed: {e}")
            return None

    def _read_gz(self, data: bytes, entry_path: str) -> bytes | None:
        """Decompress single gzip file."""
        try:
            return gzip.decompress(data)
        except Exception as e:
            logger.warning(f"ArchivePreviewer: gzip decompress failed: {e}")
            return None

    # ── Text Preview ──

    async def preview_text(
        self, data: bytes, fmt: str, entry_path: str,
        max_chars: int = MAX_PREVIEW_CHARS,
    ) -> str | None:
        """Extract and decode a text preview of a single file from an archive.

        Only reads the target file; nothing else is touched. The preview
        is truncated to max_chars to avoid loading large files.

        Args:
            data: Raw archive bytes.
            fmt: Format string.
            entry_path: File to preview.
            max_chars: Max characters to return (default 5000).

        Returns:
            Decoded text preview, or None if the file cannot be read.
        """
        content = await self.read_file(data, fmt, entry_path)
        if content is None:
            return None

        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            text = content.decode('utf-8', errors='replace')

        if len(text) > max_chars:
            return text[:max_chars] + f"\n\n... [truncated at {max_chars} chars, {len(content):,} bytes total]"
        return text

    # ── Entry Search ──

    async def find_entries(
        self, data: bytes, fmt: str, pattern: str,
    ) -> list[ArchiveEntry]:
        """Search archive entries by name pattern (case-insensitive substring).

        Useful for finding specific file types: pattern=".csv", ".json".

        Args:
            data: Raw archive bytes.
            fmt: Format string.
            pattern: Case-insensitive substring to match.

        Returns:
            Matching ArchiveEntry objects.
        """
        entries = await self.list_files(data, fmt)
        pattern_lower = pattern.lower()
        return [e for e in entries if pattern_lower in e.name.lower()]


# ═══════════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════════

_instance: Optional[ArchivePreviewer] = None


def get_archive_previewer() -> ArchivePreviewer:
    """Get or create the singleton ArchivePreviewer instance."""
    global _instance
    if _instance is None:
        _instance = ArchivePreviewer()
    return _instance


__all__ = [
    "ArchivePreviewer",
    "ArchiveEntry",
    "get_archive_previewer",
    "MAX_ENTRIES",
    "MAX_PREVIEW_CHARS",
]
