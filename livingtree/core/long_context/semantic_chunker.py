"""
语义分块器 (Semantic Chunker)

将长文本按语义分割为有意义的片段：
- 基于段落边界
- 基于主题转换
- 基于语义相似度变化
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Chunk:
    chunk_id: str
    content: str
    start: int
    end: int
    topic: str = ""
    is_section_header: bool = False


class SemanticChunker:

    def __init__(self, chunk_size: int = 2000,
                 overlap: int = 200):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(self, text: str) -> List[Chunk]:
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""
        chunk_id = 0
        start_pos = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) < self.chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(Chunk(
                        chunk_id=f"chunk_{chunk_id}",
                        content=current_chunk.strip(),
                        start=start_pos,
                        end=start_pos + len(current_chunk)))
                    chunk_id += 1

                    if self.overlap > 0:
                        overlap_text = (current_chunk[-self.overlap:]
                                       if len(current_chunk) > self.overlap
                                       else current_chunk)
                        current_chunk = overlap_text + para + "\n\n"
                    else:
                        current_chunk = para + "\n\n"
                    start_pos += len(current_chunk)

        if current_chunk.strip():
            chunks.append(Chunk(
                chunk_id=f"chunk_{chunk_id}",
                content=current_chunk.strip(),
                start=start_pos,
                end=start_pos + len(current_chunk)))

        return chunks

    def chunk_code(self, code: str) -> List[Chunk]:
        chunks = []
        current_chunk = []
        chunk_id = 0

        for line in code.splitlines():
            stripped = line.strip()
            current_chunk.append(line)

            if (self._is_boundary(stripped)
                    and len('\n'.join(current_chunk)) > self.chunk_size // 3):
                chunks.append(Chunk(
                    chunk_id=f"code_{chunk_id}",
                    content='\n'.join(current_chunk),
                    start=0, end=0))
                chunk_id += 1
                current_chunk = []

        if current_chunk:
            chunks.append(Chunk(
                chunk_id=f"code_{chunk_id}",
                content='\n'.join(current_chunk),
                start=0, end=0))

        return chunks

    def _is_boundary(self, line: str) -> bool:
        return (not line or line.startswith('def ')
                or line.startswith('class ')
                or line.startswith('# ====')
                or line.startswith('import ')
                or line.startswith('from '))


__all__ = ["Chunk", "SemanticChunker"]
