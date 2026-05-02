"""
分层上下文金字塔 (Layered Context Pyramid)

将长文本组织为多粒度层次：
- Layer 1: 篇章级 (全局概要)
- Layer 2: 段落级 (主题段落)
- Layer 3: 句子级 (关键句)
- Layer 4: 词汇级 (核心术语)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class GranularityLevel(Enum):
    DOCUMENT = 1
    SECTION = 2
    PARAGRAPH = 3
    SENTENCE = 4


@dataclass
class ContextBlock:
    block_id: str
    content: str
    level: GranularityLevel
    summary: str = ""
    keywords: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)


class LayeredContextPyramid:

    def __init__(self):
        self._blocks: Dict[str, ContextBlock] = {}
        self._root_id: Optional[str] = None
        self._level_blocks: Dict[GranularityLevel, List[str]] = {
            level: [] for level in GranularityLevel}

    def build(self, text: str) -> str:
        self._blocks.clear()
        self._level_blocks = {level: [] for level in GranularityLevel}

        root_id = self._add_block(text, GranularityLevel.DOCUMENT,
                                  "全文内容")
        self._root_id = root_id

        sections = text.split('\n\n')
        for i, section in enumerate(sections[:10]):
            section_id = self._add_block(
                section, GranularityLevel.SECTION,
                f"段落 {i+1}", parent_id=root_id)
            self._root_block().children_ids.append(section_id)

        return root_id

    def _add_block(self, content: str, level: GranularityLevel,
                   summary: str = "", parent_id: str = None) -> str:
        import uuid
        block_id = f"ctx_{uuid.uuid4().hex[:8]}"
        block = ContextBlock(
            block_id=block_id, content=content[:1000],
            level=level, summary=summary[:200],
            parent_id=parent_id)
        self._blocks[block_id] = block
        self._level_blocks[level].append(block_id)
        return block_id

    def _root_block(self) -> ContextBlock:
        return self._blocks.get(self._root_id)

    def get_summary(self, max_level: GranularityLevel = None,
                    max_chars: int = 500) -> str:
        if not self._root_id:
            return ""

        summary = "=== 上下文概要 ===\n"

        for level in GranularityLevel:
            if max_level and level.value > max_level.value:
                break
            blocks = [self._blocks[bid] for bid
                     in self._level_blocks.get(level, [])]
            if blocks:
                summary += f"\n[Level {level.value}]"
                for b in blocks[:3]:
                    preview = b.content[:100].replace('\n', ' ')
                    summary += f"\n  - {preview}"

        return summary[:max_chars]

    def get_context_for_query(self, query: str,
                              max_chars: int = 1000) -> str:
        query_lower = query.lower()
        relevant = []

        for block in self._blocks.values():
            if query_lower in block.content[:500].lower():
                relevant.append(block)

        if not relevant:
            if self._root_id:
                root = self._blocks[self._root_id]
                return root.content[:max_chars]
            return ""

        context = ""
        for block in relevant[:3]:
            snippet = block.content[:300] + "\n"
            if len(context) + len(snippet) > max_chars:
                break
            context += snippet

        return context


__all__ = ["GranularityLevel", "ContextBlock", "LayeredContextPyramid"]
