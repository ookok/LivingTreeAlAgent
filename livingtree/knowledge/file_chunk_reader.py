"""File Chunk Reader — range-based chunked file I/O with mmap support.

Enables true lazy loading: instead of loading entire files into memory,
this module provides zero-copy memory-mapped reads and seek-based ranged
reads. Inspired by dataset-viewer's StorageClient trait.

Core concepts:
  - FileChunkReader: wraps a file path, provides {read_range, mmap_range}
  - LineOffsetIndex: pre-computed byte offsets for O(1) line seeking
  - build_line_index(): scan file once to build position map

Usage:
    from livingtree.knowledge.file_chunk_reader import FileChunkReader

    reader = FileChunkReader(Path("large_report.md"))
    chunk = reader.mmap_range(start=1024, length=4096)  # zero-copy
"""

from __future__ import annotations

import contextlib
import mmap as _mmap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

CHUNK_SIZE = 4096  # bytes — standard page-aligned read size


# ═══════════════════════════════════════════════════════════════════
# FileChunkReader
# ═══════════════════════════════════════════════════════════════════

class FileChunkReader:
    """Range-based chunked file reader with mmap and seek backends.

    Provides the foundational I/O primitive for lazy document loading:
    read only the byte range you need, never the whole file.

    Usage:
        reader = FileChunkReader(Path("data.csv"))
        header = reader.mmap_range(0, 4096)             # zero-copy first 4KB
        chunk = reader.sync_read_range(8192, 4096)      # seek + read rows 512-768

    The caller is responsible for managing offsets; use build_line_index()
    to map logical line numbers to byte offsets.
    """

    def __init__(self, path: Path):
        self._path = path
        self._size = path.stat().st_size if path.exists() else 0
        self._mmap: Optional[_mmap.mmap] = None  # lazily opened, shared across reads

    @property
    def path(self) -> Path:
        return self._path

    @property
    def size(self) -> int:
        """File size in bytes. Returns 0 for missing files."""
        return self._size

    def get_file_size(self) -> int:
        """Return total file size in bytes."""
        return self._size

    # ── mmap (zero-copy) ──

    def mmap_range(self, start: int, length: int) -> bytes:
        """Zero-copy memory-mapped read for a byte range.

        Fast for random access within the OS page cache budget. The mmap
        handle is cached across calls and reused — the first call opens it,
        subsequent calls slice from the same mapping.

        Args:
            start: Byte offset to read from (0-based).
            length: Number of bytes to read.

        Returns:
            Byte slice [start:start+length]. May be shorter than requested
            if near EOF.

        Raises:
            FileNotFoundError: if the file does not exist.
        """
        if not self._path.exists():
            raise FileNotFoundError(f"File not found: {self._path}")

        # Clamp to valid range
        start = max(0, min(start, self._size))
        end = min(start + length, self._size)
        if start >= end:
            return b""

        # Open mmap lazily — reuses the same mapping for all reads
        if self._mmap is None:
            with open(self._path, 'rb') as f:
                self._mmap = _mmap.mmap(f.fileno(), 0, access=_mmap.ACCESS_READ)

        return self._mmap[start:end]

    # ── seek + read ──

    @contextlib.asynccontextmanager
    async def read_range(self, start: int, length: int):
        """Async seek-based ranged read. Safer for extremely large files
        that shouldn't be mmap'd.

        Usage:
            async with reader.read_range(1024, 4096) as data:
                process(data)
        """
        yield self.sync_read_range(start, length)

    def sync_read_range(self, start: int, length: int) -> bytes:
        """Synchronous seek-based ranged read.

        Args:
            start: Byte offset (0-based).
            length: Number of bytes to read.

        Returns:
            Bytes from [start:start+length], clamped to EOF.
        """
        if not self._path.exists():
            raise FileNotFoundError(f"File not found: {self._path}")

        start = max(0, min(start, self._size))
        end = min(start + length, self._size)
        if start >= end:
            return b""

        with open(self._path, 'rb') as f:
            f.seek(start)
            return f.read(end - start)

    # ── teardown ──

    def close(self):
        """Release the mmap handle if open."""
        if self._mmap is not None:
            try:
                self._mmap.close()
            except Exception:
                pass
            self._mmap = None

    def __del__(self):
        self.close()

    def __repr__(self) -> str:
        return f"FileChunkReader({self._path.name}, {self._size:,} bytes)"


# ═══════════════════════════════════════════════════════════════════
# LineOffsetIndex
# ═══════════════════════════════════════════════════════════════════

@dataclass
class LineOffsetIndex:
    """Periodic byte-offset index for O(1) approximate line seeking.

    Stores the byte position of every N-th line (default 1000). Given a
    logical line number, returns the byte offset of the nearest indexed
    line, from which a linear scan can find the exact position.

    This is the building block for lazy CSV loading — seek to the right
    chunk, load only what you need.

    Attributes:
        file_path: Path to the indexed file.
        line_positions: Byte offset of every N-th line.
        lines_per_bucket: How many lines between each stored position.
        total_lines: Total number of lines in the file.
        total_bytes: File size in bytes at time of indexing.
    """

    file_path: str = ""
    line_positions: list[int] = field(default_factory=list)
    lines_per_bucket: int = 1000
    total_lines: int = 0
    total_bytes: int = 0

    def seek_to_line(self, line_num: int) -> int:
        """Return approximate byte offset for a given line number.

        The returned offset points to the start of the nearest indexed
        bucket. Caller should scan forward from this position to find
        the exact line.

        Args:
            line_num: 0-based line number.

        Returns:
            Byte offset of the nearest indexed line at or before line_num.
            Returns 0 for line_num < 0, or the last known position for
            line_num beyond the index.
        """
        if not self.line_positions:
            return 0
        bucket = max(0, line_num // self.lines_per_bucket)
        if bucket >= len(self.line_positions):
            return self.line_positions[-1]
        return self.line_positions[bucket]

    def line_range(self, start_line: int, end_line: int) -> tuple[int, int]:
        """Return (start_byte, end_byte) for a line range.

        The end_byte is an approximation — always scan to the exact end
        line from the returned position.

        Note: total_bytes is used as end_byte when seeking beyond the
        last indexed line. This means the caller will read to EOF, which
        is always safe (just needs a boundary check).
        """
        start_off = self.seek_to_line(start_line)
        end_off = self.seek_to_line(end_line + 1)
        if end_off <= start_off:
            end_off = self.total_bytes
        return start_off, end_off

    @property
    def bucket_count(self) -> int:
        return len(self.line_positions)

    def to_dict(self) -> dict[str, str | int]:
        return {
            "file_path": self.file_path,
            "lines_per_bucket": self.lines_per_bucket,
            "total_lines": self.total_lines,
            "total_bytes": self.total_bytes,
            "bucket_count": len(self.line_positions),
        }

    def __repr__(self) -> str:
        return (
            f"LineOffsetIndex({self.file_path!r}, "
            f"{self.total_lines:,} lines, "
            f"{len(self.line_positions)} buckets × {self.lines_per_bucket})"
        )


# ═══════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════

def build_line_index(
    file_path: Path,
    lines_per_bucket: int = 1000,
) -> LineOffsetIndex:
    """Scan a text file and build a periodic line-offset index.

    Reads the file once in CHUNK_SIZE blocks, recording the byte offset
    at every lines_per_bucket line boundary. The resulting index enables
    O(1) approximate line seeking without loading the file into memory.

    Args:
        file_path: Path to the text file.
        lines_per_bucket: Record a position every N lines (default 1000).

    Returns:
        LineOffsetIndex with pre-computed positions.

    Raises:
        FileNotFoundError: if the file does not exist.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    positions: list[int] = [0]  # Line 0 always at byte 0
    total_bytes = file_path.stat().st_size
    line_count = 0
    byte_offset = 0
    residual = b""  # Partial line carried across chunk boundaries

    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break

            # Combine with residual from previous chunk
            data = residual + chunk
            residual = b""

            # Count complete lines in this chunk
            lines = data.split(b'\n')
            # The last element is either a partial line (if chunk didn't end
            # on a newline boundary) or an empty string (if it did)
            for i, line_bytes in enumerate(lines[:-1]):
                line_count += 1
                byte_offset += len(line_bytes) + 1  # +1 for \n
                if line_count % lines_per_bucket == 0:
                    positions.append(byte_offset)

            # Carry partial line to next chunk
            residual = lines[-1]
            byte_offset += len(lines[-1])

    # Handle trailing content without final newline
    if residual:
        line_count += 1

    return LineOffsetIndex(
        file_path=str(file_path),
        line_positions=positions,
        lines_per_bucket=lines_per_bucket,
        total_lines=line_count,
        total_bytes=total_bytes,
    )


__all__ = [
    "FileChunkReader",
    "LineOffsetIndex",
    "build_line_index",
    "CHUNK_SIZE",
]
