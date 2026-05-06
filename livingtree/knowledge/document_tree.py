"""DocumentTree — hierarchical document structure representation.

Implements the DSHP (Document Section Hierarchical Parsing) tree from
MultiDocFusion (Shin et al., EMNLP 2025). Each node represents a
document section with metadata, text content, and child sections.

The tree enables:
  - Section-boundary-aware chunking (DFS grouping per MultiDocFusion)
  - Hierarchical context attachment to retrieval chunks
  - Multi-document cross-referencing at any tree depth
  - Layout-aware region-to-node mapping
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class DocSection:
    """A node in the DSHP document tree.

    Attributes:
        id: unique section identifier (e.g. "3", "3.2", "3.2.1")
        title: section heading text
        level: heading level (0=root/document, 1=H1, 2=H2, ...)
        text: full text content of this section (excluding children)
        children: subsections
        parent: parent section reference
        page_range: (start_page, end_page) for layout mapping
        bbox: bounding box on page for layout detection [(x0,y0,x1,y1), ...]
        metadata: arbitrary extra data (e.g. detected font styles)
    """
    id: str
    title: str = ""
    level: int = 0
    text: str = ""
    children: list[DocSection] = field(default_factory=list)
    parent: Optional[DocSection] = None
    page_range: tuple[int, int] = (0, 0)
    bbox: list[tuple[float, float, float, float]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def path(self) -> str:
        """Full hierarchical path (e.g. '1 > 1.2 > 1.2.3 Title')."""
        if self.parent is None or self.parent.level == 0:
            return f"{self.id} {self.title}".strip()
        return f"{self.parent.path} > {self.id} {self.title}".strip()

    @property
    def depth(self) -> int:
        """Tree depth from root."""
        if self.parent is None:
            return 0
        return self.parent.depth + 1

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0

    @property
    def full_text(self) -> str:
        """Full text including all descendant sections."""
        parts = [self.text]
        for child in self.children:
            parts.append(child.full_text)
        return "\n\n".join(p for p in parts if p)

    @property
    def char_count(self) -> int:
        return len(self.full_text)

    def get_section_path(self) -> list[str]:
        """Returns list of section titles from root to this node."""
        if self.parent is None:
            return [self.title] if self.title else []
        return self.parent.get_section_path() + ([self.title] if self.title else [])

    def find_by_id(self, section_id: str) -> Optional[DocSection]:
        if self.id == section_id:
            return self
        for child in self.children:
            found = child.find_by_id(section_id)
            if found:
                return found
        return None

    def find_by_title(self, title: str, fuzzy: bool = False) -> Optional[DocSection]:
        if fuzzy:
            if title.lower() in self.title.lower():
                return self
        elif self.title == title:
            return self
        for child in self.children:
            found = child.find_by_title(title, fuzzy)
            if found:
                return found
        return None

    def iter_leaves(self):
        if self.is_leaf:
            yield self
        else:
            for child in self.children:
                yield from child.iter_leaves()

    def iter_sections(self):
        yield self
        for child in self.children:
            yield from child.iter_sections()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "level": self.level,
            "text_preview": self.text[:200],
            "text_length": len(self.text),
            "char_count": self.char_count,
            "path": self.path,
            "depth": self.depth,
            "is_leaf": self.is_leaf,
            "page_range": list(self.page_range),
            "child_count": len(self.children),
            "children": [c.to_dict() for c in self.children],
        }

    def __repr__(self) -> str:
        return f"DocSection(id={self.id!r}, level={self.level}, title={self.title!r}, children={len(self.children)})"


@dataclass
class DocumentTree:
    """Full DSHP document tree with root and metadata.

    Represents the entire parsed document structure. The root is a
    virtual node (level=0) with document-level metadata.
    """

    root: DocSection
    title: str = ""
    source: str = ""
    total_chars: int = 0
    total_pages: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, title: str = "", source: str = "") -> DocumentTree:
        return cls(
            root=DocSection(id="root", level=0, title=title),
            title=title,
            source=source,
        )

    @property
    def section_count(self) -> int:
        return sum(1 for _ in self.root.iter_sections()) - 1  # exclude root

    @property
    def leaf_count(self) -> int:
        if not self.root.children:
            return 0
        return sum(1 for _ in self.root.iter_leaves())

    @property
    def max_depth(self) -> int:
        return max((s.depth for s in self.root.iter_sections()), default=0)

    def find_section(self, section_id: str) -> Optional[DocSection]:
        return self.root.find_by_id(section_id)

    def find_section_by_title(self, title: str, fuzzy: bool = False) -> Optional[DocSection]:
        return self.root.find_by_title(title, fuzzy)

    def add_section(
        self,
        parent: DocSection,
        section_id: str,
        title: str = "",
        text: str = "",
        level: int = 1,
    ) -> DocSection:
        section = DocSection(
            id=section_id,
            title=title,
            level=level,
            text=text,
            parent=parent,
        )
        parent.children.append(section)
        return section

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "source": self.source,
            "total_chars": self.total_chars,
            "total_pages": self.total_pages,
            "section_count": self.section_count,
            "leaf_count": self.leaf_count,
            "max_depth": self.max_depth,
            "root": self.root.to_dict(),
        }

    def print_tree(self, max_depth: int = 6) -> str:
        lines = [f"📄 {self.title}"]
        def _print(node: DocSection, indent: int = 0):
            if node.level == 0 and not node.title:
                for child in node.children:
                    _print(child, 0)
                return
            if indent > max_depth:
                return
            prefix = "  " * indent + ("├─ " if indent > 0 else "")
            lines.append(f"{prefix}{node.id} {node.title} ({node.char_count} chars)")
            for child in node.children:
                _print(child, indent + 1)
        _print(self.root)
        return "\n".join(lines)
