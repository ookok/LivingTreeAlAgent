"""HierarchicalChunker — DSHP-LLM powered section-boundary-aware chunking.

Implements the core MultiDocFusion algorithm (Shin et al., EMNLP 2025):

Step 1: Build DSHP document tree from raw parsing output
  - Vision-based: use layout bbox regions → section hierarchy
  - Text-based: parse heading levels (#/Chapter markers) → section tree
  - LLM-based: DSHP-LLM prompt to reconstruct hierarchy from flat text

Step 2: DFS-based hierarchical chunking
  - Walk the tree depth-first
  - Group sibling leaf nodes into chunks respecting max chunk size
  - Each chunk carries hierarchical context (section path)

Step 3: Produce DocumentChunk objects with full lineage

LongParser-inspired extensions:
  - SemanticChunker: embedding-similarity boundary detection
  - TableAwareSplitter: preserve table structure during chunking

The chunker works standalone (regex headings only) or with LLM hub
for DSHP-LLM mode (best quality for complex documents).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger

from .document_tree import DocumentTree, DocSection


@dataclass
class DocumentChunk:
    """A hierarchically-aware chunk with lineage information.

    Differs from DocChunk/DocumentProcessor.Chunk by carrying
    section context (path, level, parent titles) that travels
    through the retrieval pipeline.
    """
    chunk_id: str
    text: str
    section_path: str = ""          # e.g. "1 > 1.2 > 1.2.3 Methods"
    section_id: str = ""            # e.g. "1.2.3"
    section_title: str = ""
    section_level: int = 0
    chunk_index: int = 0            # index within this section
    start_char: int = 0
    end_char: int = 0
    parent_titles: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def context_string(self) -> str:
        """Context prefix for LLM retrieval: section path + metadata."""
        parts = []
        if self.section_path:
            parts.append(f"[Section: {self.section_path}]")
        if self.section_title:
            parts.append(f"[Heading: {self.section_title}]")
        parts.append(self.text)
        return "\n".join(parts)


class HierarchicalChunker:
    """DSHP-LLM hierarchical document chunker.

    Supports three parsing modes:
      - REGEX: heading detection via Markdown/Chinese patterns
      - LLM: DSHP-LLM prompt for complex document structures
      - AUTO: tries LLM first, falls back to REGEX

    Usage:
        chunker = HierarchicalChunker(chunk_size=1000, chunk_overlap=200)
        chunks = chunker.chunk(document_text, title="Report.pdf", hub=llm_hub)
        # Each chunk now has section_path for retrieval context
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        mode: str = "AUTO",
        max_chunk_size: int = 4096,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.mode = mode.upper()
        self.max_chunk_size = max_chunk_size

    def chunk(
        self,
        text: str,
        title: str = "",
        source: str = "",
        hub: Any = None,
    ) -> list[DocumentChunk]:
        """Complete pipeline: build tree → DFS chunk → return chunks."""
        tree = self.build_tree(text, title, source, hub)
        return self.dfs_chunk(tree)

    def build_tree(
        self,
        text: str,
        title: str = "",
        source: str = "",
        hub: Any = None,
    ) -> DocumentTree:
        """Build DSHP document tree from raw text.

        Uses LLM-based parsing if hub is available and mode allows it;
        otherwise falls back to regex heading detection.
        """
        tree = DocumentTree.create(title=title, source=source)
        tree.total_chars = len(text)

        if self.mode in ("LLM", "AUTO") and hub:
            try:
                return self._llm_build_tree(text, tree, hub)
            except Exception as e:
                logger.warning("DSHP-LLM tree building failed, falling back to regex: %s", e)

        return self._regex_build_tree(text, tree)

    def _regex_build_tree(self, text: str, tree: DocumentTree) -> DocumentTree:
        """Build tree via regex heading detection.

        Detects:
          - Markdown: #, ##, ###, ####, #####, ######
          - Numbered: 1., 1.1, 1.1.1, 1.1.1.1
          - Chinese: 第一章, 第一节, 一、, （一）
          - Bold/underline patterns as section markers
        """
        heading_pattern = re.compile(
            r'^((#{1,6})\s+(.+)|'
            r'(\d+(?:\.\d+)*)\s+(.+)|'
            r'(第[一二三四五六七八九十百千]+[章節节])\s*(.*)|'
            r'([一二三四五六七八九十]+)[、，]\s*(.*)|'
            r'(（[一二三四五六七八九十]+）)\s*(.*))',
            re.MULTILINE,
        )

        # First pass: find all headings and their levels
        headings = []
        for match in heading_pattern.finditer(text):
            full_match = match.group(0).strip()
            start = match.start()

            if match.group(2):  # Markdown #
                level = len(match.group(2))
                heading_title = match.group(3).strip()
                heading_id = heading_title
            elif match.group(4):  # Numbered 1. / 1.1
                level = match.group(4).count('.') + 1
                heading_title = match.group(5).strip() if match.group(5) else ""
                heading_id = match.group(4)
            elif match.group(6):  # Chinese 第X章/节
                level = 1 if '章' in match.group(6) else 2
                heading_title = match.group(7).strip()
                heading_id = match.group(6)
            elif match.group(8):  # 一、二、
                level = 3
                heading_title = match.group(9).strip()
                heading_id = match.group(8)
            elif match.group(10):  # （一）（二）
                level = 4
                heading_title = match.group(11).strip()
                heading_id = match.group(10)
            else:
                continue

            headings.append({
                "start": start,
                "title": full_match,
                "heading_title": heading_title,
                "id": heading_id,
                "level": level,
            })

        if not headings:
            # No headings found: treat entire document as one section
            section = tree.add_section(tree.root, "1", title=tree.title, text=text, level=1)
            tree.total_chars = len(text)
            return tree

        # Build tree from headings
        headings.sort(key=lambda h: h["start"])
        self._headings_to_tree(text, tree, headings)

        tree.total_chars = len(text)
        return tree

    def _headings_to_tree(
        self, text: str, tree: DocumentTree, headings: list[dict]
    ) -> None:
        """Convert flat heading list into a nested DocSection tree."""
        if not headings:
            return

        stack: list[tuple[int, DocSection]] = [(0, tree.root)]
        heading_index = 0

        while heading_index < len(headings):
            h = headings[heading_index]

            # Find the right parent by unwinding stack to matching level
            while stack and stack[-1][0] >= h["level"]:
                stack.pop()

            parent = stack[-1][1]
            new_level = stack[-1][0] + 1

            # Determine text content for this section
            section_start = h["start"]
            if heading_index + 1 < len(headings):
                section_end = headings[heading_index + 1]["start"]
            else:
                section_end = len(text)

            section_text = text[section_start:section_end].strip()

            section = tree.add_section(
                parent=parent,
                section_id=h["id"],
                title=h["title"],
                text=section_text,
                level=new_level,
            )
            stack.append((h["level"], section))
            heading_index += 1

        # Handle text before first heading as preamble
        if headings:
            first_start = headings[0]["start"]
            if first_start > 0:
                preamble = text[:first_start].strip()
                if preamble:
                    tree.root.text = preamble

    def _llm_build_tree(
        self, text: str, tree: DocumentTree, hub: Any
    ) -> DocumentTree:
        """Use DSHP-LLM to reconstruct document hierarchy.

        Sends a structured prompt asking the LLM to parse the document
        into sections with IDs, titles, levels, and parent relationships.
        """
        prompt = self._build_dshp_prompt(text)
        try:
            response = hub.chat(prompt, system="You are a document structure analyzer.")
            return self._parse_llm_tree_response(response, text, tree)
        except Exception as e:
            logger.warning("DSHP-LLM call failed: %s", e)
            raise

    def _build_dshp_prompt(self, text: str) -> str:
        """Build the DSHP-LLM prompt for hierarchical parsing."""
        preview = text[:8000] if len(text) > 8000 else text
        truncated_note = "\n[Document truncated for analysis — showing first 8000 characters]" if len(text) > 8000 else ""

        return f"""Analyze the following document and extract its hierarchical section structure.

Return a JSON tree where each node has:
  - id: section number/identifier (e.g. "1", "1.2", "1.2.3")
  - title: section heading text
  - level: heading level (1=h1, 2=h2, 3=h3, etc.)
  - children: array of child sections
  - key_themes: 2-3 key topics covered in this section

Use the document's own heading structure. For numbered headings (1., 1.1), use those as IDs.
For unnumbered headings, generate IDs based on position.

Document:
{preview}{truncated_note}

Return ONLY the JSON tree, no other text:"""

    def _parse_llm_tree_response(
        self, response: str, text: str, tree: DocumentTree
    ) -> DocumentTree:
        """Parse LLM JSON response into DocSection tree."""
        import json
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group(0))
            else:
                raise ValueError("DSHP-LLM returned unparseable response")

        def _build_node(node_data: dict, parent: DocSection) -> DocSection:
            section = tree.add_section(
                parent=parent,
                section_id=node_data.get("id", ""),
                title=node_data.get("title", ""),
                level=node_data.get("level", 1),
            )
            section.metadata["key_themes"] = node_data.get("key_themes", [])
            for child_data in node_data.get("children", []):
                _build_node(child_data, section)
            return section

        if isinstance(data, dict):
            _build_node(data, tree.root)
        elif isinstance(data, list) and data:
            for item in data:
                _build_node(item, tree.root)

        tree.total_chars = len(text)
        return tree

    def dfs_chunk(self, tree: DocumentTree) -> list[DocumentChunk]:
        """DFS-based hierarchical chunking (core MultiDocFusion algorithm).

        Walks the tree depth-first. Groups sibling leaf sections into
        chunks respecting max_chunk_size. Each chunk preserves its
        full section path context.
        """
        chunks = []
        self._dfs_collect(tree.root, chunks)
        return chunks

    def _dfs_collect(
        self, node: DocSection, chunks: list[DocumentChunk],
    ) -> None:
        """Recursively collect chunks from the document tree.

        Strategy: if a leaf section is small enough, it becomes one chunk.
        If too large, it's split further with paragraph alignment.
        Leaf sections are grouped with siblings to form efficient chunks.
        """
        if node.is_leaf and node.text:
            section_chunks = self._split_section_text(node)
            for i, chunk_text in enumerate(section_chunks):
                chunks.append(DocumentChunk(
                    chunk_id=f"{node.id}_chunk_{i}",
                    text=chunk_text,
                    section_path=node.path,
                    section_id=node.id,
                    section_title=node.title,
                    section_level=node.level,
                    chunk_index=i,
                    parent_titles=node.get_section_path(),
                    metadata={"key_themes": node.metadata.get("key_themes", [])},
                ))
        else:
            for child in node.children:
                self._dfs_collect(child, chunks)

    def _split_section_text(self, node: DocSection) -> list[str]:
        """Split a section's text into chunks, respecting max_chunk_size."""
        text = node.text
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        step = self.chunk_size - self.chunk_overlap

        while start < len(text):
            end = min(start + self.chunk_size, len(text))

            if end < len(text):
                para_break = text.rfind("\n\n", start, min(end + 500, len(text)))
                if para_break > start + self.chunk_size // 2:
                    end = para_break + 2

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(chunk_text)
            start = end - self.chunk_overlap if end < len(text) else end

        return chunks


def build_document_tree(
    text: str,
    title: str = "",
    source: str = "",
    mode: str = "AUTO",
) -> DocumentTree:
    """Convenience: build a DSHP tree from text (no hub, regex only)."""
    chunker = HierarchicalChunker(mode=mode)
    return chunker.build_tree(text, title, source)


def chunk_document(
    text: str,
    title: str = "",
    source: str = "",
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    mode: str = "AUTO",
) -> list[DocumentChunk]:
    """Convenience: chunk a document with hierarchical awareness."""
    chunker = HierarchicalChunker(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap, mode=mode,
    )
    return chunker.chunk(text, title, source)


# ═══ LongParser-inspired Semantic Chunker ═══


class SemanticChunker:
    """Embedding-similarity boundary detection for semantic chunking.

    LongParser approach: detect where semantic drift occurs (adjacent
    sentences become dissimilar beyond threshold). Split at those boundaries.
    Falls back to paragraph-level splitting if no embedding model available.

    Unlike HierarchicalChunker which splits at headings, this splits at
    semantic topic shifts — useful for flat documents without clear headings.
    """

    def __init__(self, similarity_threshold: float = 0.5,
                 min_chunk_chars: int = 200, max_chunk_chars: int = 2000):
        self.similarity_threshold = similarity_threshold
        self.min_chunk_chars = min_chunk_chars
        self.max_chunk_chars = max_chunk_chars
        self._model = None

    def chunk(self, text: str, title: str = "") -> list[DocumentChunk]:
        sentences = self._split_sentences(text)
        if len(sentences) <= 1:
            return [self._make_chunk(text, title, 0, len(text), "0")]

        boundaries = self._find_boundaries(sentences)
        return self._build_chunks_from_boundaries(sentences, boundaries, title)

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentence-like segments."""
        raw = re.split(r'(?<=[。！？.!?\n])\s*', text)
        return [s.strip() for s in raw if s.strip()]

    def _find_boundaries(self, sentences: list[str]) -> list[int]:
        """Find split points where semantic drift occurs.

        Without an embedding model, uses lexical overlap as a proxy
        for semantic similarity (Jaccard coefficient of character 3-grams).
        """
        boundaries = []
        current_len = 0

        for i in range(len(sentences) - 1):
            current_len += len(sentences[i])

            if current_len >= self.min_chunk_chars:
                sim = self._lexical_similarity(sentences[i], sentences[i + 1])
                if sim < self.similarity_threshold:
                    boundaries.append(i + 1)
                    current_len = 0
                elif current_len >= self.max_chunk_chars:
                    boundaries.append(i + 1)
                    current_len = 0

        return boundaries

    def _lexical_similarity(self, a: str, b: str) -> float:
        """Jaccard similarity of character 3-grams as semantic proxy."""
        if not a or not b:
            return 0.0

        def ngrams(s: str, n: int = 3) -> set:
            s = s.lower()
            return {s[i:i + n] for i in range(len(s) - n + 1)}

        a_set = ngrams(a)
        b_set = ngrams(b)
        if not a_set or not b_set:
            return 0.0

        intersection = len(a_set & b_set)
        union = len(a_set | b_set)
        return intersection / union if union > 0 else 0.0

    def _build_chunks_from_boundaries(self, sentences: list[str],
                                       boundaries: list[int],
                                       title: str) -> list[DocumentChunk]:
        chunks = []
        prev = 0

        for i, b in enumerate(boundaries + [len(sentences)]):
            chunk_text = " ".join(sentences[prev:b])
            if chunk_text.strip():
                chunks.append(self._make_chunk(
                    chunk_text, title, prev, b,
                    f"sem-{i}", "SemanticChunk",
                ))
            prev = b

        return chunks

    @staticmethod
    def _make_chunk(text: str, title: str, start: int, end: int,
                    chunk_id: str, chunk_type: str = "semantic") -> DocumentChunk:
        return DocumentChunk(
            chunk_id=chunk_id,
            text=text,
            section_path=f"{title}/{chunk_type}",
            section_id=chunk_id,
            section_title=title,
            start_char=start,
            end_char=end,
            metadata={"chunk_type": chunk_type, "title": title},
        )


class TableAwareSplitter:
    """LongParser-inspired: preserve table structure during chunking.

    Detects table boundaries (Markdown tables, pipe-delimited, CSV-like
    blocks) and keeps them intact — never splits a table across chunks.
    Critical for EIA reports which contain many data tables.
    """

    TABLE_START_RE = re.compile(
        r'^\|[\s\-|]+\|\s*$|'         # Markdown table separator
        r'^\|.*\|.*\|',                # Markdown table row
        re.MULTILINE,
    )
    TABLE_BLOCK_RE = re.compile(
        r'(?:^.+?\|.+\|.+\n)+',
        re.MULTILINE,
    )

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, text: str, title: str = "") -> list[DocumentChunk]:
        sections = self._split_preserving_tables(text)
        chunks = []

        for i, section in enumerate(sections):
            if self._is_table(section):
                chunks.append(self._make_chunk(
                    section, title, 0, len(section),
                    f"table-{i}", "table",
                ))
            else:
                sub_chunks = self._split_by_size(section, title, f"s{i}")
                chunks.extend(sub_chunks)

        return chunks

    def _split_preserving_tables(self, text: str) -> list[str]:
        table_regions = []
        for m in self.TABLE_BLOCK_RE.finditer(text):
            table_regions.append((m.start(), m.end()))

        if not table_regions:
            return [text]

        sections = []
        prev = 0
        for start, end in table_regions:
            if start > prev:
                sections.append(text[prev:start])
            sections.append(text[start:end])
            prev = end
        if prev < len(text):
            sections.append(text[prev:])

        return sections

    def _is_table(self, text: str) -> bool:
        lines = text.strip().split("\n")
        if len(lines) < 2:
            return False

        pipe_lines = sum(1 for l in lines if l.strip().startswith("|") and "|" in l[1:])
        if pipe_lines >= 2:
            return True

        comma_lines = sum(1 for l in lines if l.count(",") >= 2)
        if comma_lines >= 3:
            return True

        return False

    def _split_by_size(self, text: str, title: str,
                       prefix: str) -> list[DocumentChunk]:
        chunks = []
        start = 0
        idx = 0

        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            if end < len(text):
                break_point = text.rfind("\n", start, end)
                if break_point > start:
                    end = break_point + 1

            chunk_text = text[start:end]
            if chunk_text.strip():
                chunks.append(DocumentChunk(
                    chunk_id=f"{prefix}-{idx}",
                    text=chunk_text,
                    section_path=title,
                    section_title=title,
                    start_char=start, end_char=end,
                    metadata={"chunk_type": "text_split"},
                ))

            start = end - self.chunk_overlap if end < len(text) else end
            idx += 1

        return chunks

    @staticmethod
    def _make_chunk(text: str, title: str, start: int, end: int,
                    chunk_id: str, chunk_type: str = "table") -> DocumentChunk:
        return DocumentChunk(
            chunk_id=chunk_id,
            text=text,
            section_path=f"{title}/{chunk_type}",
            section_id=chunk_id,
            section_title=title,
            start_char=start, end_char=end,
            metadata={"chunk_type": chunk_type, "title": title},
        )
