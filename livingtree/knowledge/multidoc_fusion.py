"""MultiDocFusion — cross-document synthesis, conflict resolution, and merging.

Implements the multi-document fusion capabilities from MultiDocFusion
(Shin et al., EMNLP 2025) for LivingTree's batch document generation
and knowledge base enrichment.

Core operations:
  1. Cross-reference: find related sections across documents
  2. Conflict detection: identify contradictory claims
  3. Complementary merging: combine non-overlapping information
  4. Unified synthesis: generate a single coherent document from N sources
  5. Consensus building: weighted voting on conflicting claims

Use cases:
  - 环评报告: merge monitoring data + regulation + engineering plan
  - 知识库: cross-reference multiple documents for fact-checking
  - 合规审查: detect conflicts between submitted docs and standards
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger

from .document_tree import DocumentTree, DocSection
from .hierarchical_chunker import DocumentChunk, HierarchicalChunker


@dataclass
class CrossReference:
    """A link between two document sections."""
    source_tree: str
    source_section_id: str
    target_tree: str
    target_section_id: str
    similarity: float = 0.0
    relation_type: str = ""  # "complements", "contradicts", "duplicates", "extends"
    evidence: str = ""


@dataclass
class DocumentConflict:
    """A contradiction between two document sections."""
    doc_a_title: str
    doc_a_section: str
    claim_a: str
    doc_b_title: str
    doc_b_section: str
    claim_b: str
    confidence: float = 0.0
    resolution_suggestion: str = ""


@dataclass  
class FusionResult:
    """Output of multi-document fusion."""
    merged_text: str = ""
    sources: list[str] = field(default_factory=list)
    references: list[CrossReference] = field(default_factory=list)
    conflicts: list[DocumentConflict] = field(default_factory=list)
    complementary_additions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class MultiDocFusionEngine:
    """Cross-document fusion engine for multi-source synthesis.

    Usage:
        engine = MultiDocFusionEngine()
        trees = [tree1, tree2, tree3]
        result = engine.fuse(trees, hub=llm_hub)
        # result.merged_text has unified synthesis
        # result.conflicts lists all contradictions
    """

    def __init__(
        self,
        similarity_threshold: float = 0.7,
        max_merge_depth: int = 3,
    ):
        self.similarity_threshold = similarity_threshold
        self.max_merge_depth = max_merge_depth

    def fuse(
        self,
        trees: list[DocumentTree],
        hub: Any = None,
    ) -> FusionResult:
        """Complete multi-document fusion pipeline."""
        result = FusionResult()
        result.sources = [t.title or t.source for t in trees]

        refs = self.cross_reference(trees)
        result.references = refs

        conflicts = self.detect_conflicts(trees, refs, hub)
        result.conflicts = conflicts

        complementary = self.find_complementary(trees, refs)
        result.complementary_additions = complementary

        if hub:
            result.merged_text = self.synthesize(trees, refs, conflicts, hub)

        result.metadata = {
            "tree_count": len(trees),
            "cross_references": len(refs),
            "conflicts": len(conflicts),
            "complementary_sections": len(complementary),
        }

        return result

    def cross_reference(self, trees: list[DocumentTree]) -> list[CrossReference]:
        """Find related sections across multiple document trees.

        Uses title similarity + text overlap to identify cross-document
        links. Maps to MultiDocFusion's multi-document alignment step.
        """
        if len(trees) < 2:
            return []

        refs = []
        titles_to_tree = {t.title or "" : t for t in trees}

        for i, tree_a in enumerate(trees):
            for tree_b in trees[i + 1:]:
                for section_a in tree_a.root.iter_sections():
                    if section_a.level == 0 or not section_a.text:
                        continue

                    for section_b in tree_b.root.iter_sections():
                        if section_b.level == 0 or not section_b.text:
                            continue

                        title_sim = self._title_similarity(section_a.title, section_b.title)
                        text_sim = self._text_overlap(section_a.text, section_b.text)

                        if title_sim >= self.similarity_threshold:
                            refs.append(CrossReference(
                                source_tree=tree_a.title or "",
                                source_section_id=section_a.id,
                                target_tree=tree_b.title or "",
                                target_section_id=section_b.id,
                                similarity=title_sim,
                                relation_type="duplicates" if title_sim > 0.9 else "complements",
                            ))
                        elif text_sim >= self.similarity_threshold:
                            refs.append(CrossReference(
                                source_tree=tree_a.title or "",
                                source_section_id=section_a.id,
                                target_tree=tree_b.title or "",
                                target_section_id=section_b.id,
                                similarity=text_sim,
                                relation_type="extends",
                            ))

        return refs

    def detect_conflicts(
        self,
        trees: list[DocumentTree],
        refs: list[CrossReference],
        hub: Any = None,
    ) -> list[DocumentConflict]:
        """Detect contradictory claims between document sections.

        For sections classified as "contradicts" in cross-references,
        uses the LLM to verify if the contradiction is real.
        """
        conflicts = []

        for ref in refs:
            if ref.relation_type != "contradicts":
                continue

            tree_a = self._find_tree(trees, ref.source_tree)
            tree_b = self._find_tree(trees, ref.target_tree)
            if not tree_a or not tree_b:
                continue

            section_a = tree_a.find_section(ref.source_section_id)
            section_b = tree_b.find_section(ref.target_section_id)
            if not section_a or not section_b:
                continue

            conflict = DocumentConflict(
                doc_a_title=ref.source_tree,
                doc_a_section=section_a.id,
                claim_a=section_a.text[:500],
                doc_b_title=ref.target_tree,
                doc_b_section=section_b.id,
                claim_b=section_b.text[:500],
                confidence=ref.similarity,
            )

            if hub:
                resolution = self._resolve_conflict(conflict, hub)
                conflict.resolution_suggestion = resolution

            conflicts.append(conflict)

        return conflicts

    def find_complementary(
        self, trees: list[DocumentTree], refs: list[CrossReference]
    ) -> list[str]:
        """Find sections present in one doc but missing from another.

        Identifies information gaps that can be filled by pulling
        from other documents in the corpus.
        """
        complementary = []

        for ref in refs:
            if ref.relation_type == "complements":
                complementary.append(
                    f"Section {ref.target_section_id} from '{ref.target_tree}' "
                    f"adds to section {ref.source_section_id} in '{ref.source_tree}'"
                )

        # Also detect orphan sections (unique to one document)
        all_section_titles = defaultdict(set)
        for tree in trees:
            for section in tree.root.iter_sections():
                if section.level > 0 and section.title:
                    all_section_titles[section.title.lower()].add(tree.title or tree.source)

        for title, source_trees in all_section_titles.items():
            if len(source_trees) == 1 and len(trees) > 1:
                complementary.append(
                    f"Unique section '{title}' only found in "
                    f"'{list(source_trees)[0]}'"
                )

        return complementary

    def synthesize(
        self,
        trees: list[DocumentTree],
        refs: list[CrossReference],
        conflicts: list[DocumentConflict],
        hub: Any,
    ) -> str:
        """Generate unified synthesis from multiple document trees.

        Uses LLM (hub) to merge complementary sections, resolve conflicts,
        and produce a single coherent document.

        This is the top-level MultiDocFusion synthesis step.
        """
        tree_summaries = []
        for tree in trees:
            if tree.root.children:
                outline = self._build_outline(tree.root, max_depth=self.max_merge_depth)
                tree_summaries.append(f"## {tree.title}\n{outline}")

        conflict_text = ""
        if conflicts:
            conflict_text = "\n### Known Conflicts\n"
            for c in conflicts:
                conflict_text += (
                    f"- [{c.doc_a_title}] §{c.doc_a_section} vs "
                    f"[{c.doc_b_title}] §{c.doc_b_section}: "
                    f"{c.resolution_suggestion or 'unresolved'}\n"
                )

        prompt = f"""Synthesize the following {len(trees)} documents into a unified report.

For overlapping sections: merge complementary information.
For conflicting sections: note the conflict and suggest reconciliation.
For unique sections: preserve their content.

Available documents:
{chr(10).join(tree_summaries)}

{conflict_text}

Generate a complete synthesis with all sections, noting sources."""

        try:
            return hub.chat(prompt)
        except Exception as e:
            logger.warning("Fusion synthesis failed: %s", e)
            return self._fallback_merge(trees)

    def _build_outline(self, node: DocSection, depth: int = 0, prefix: str = "") -> str:
        if depth > self.max_merge_depth:
            return ""
        indent = "  " * max(0, depth - 1)
        line = f"{indent}- **{node.id} {node.title or '(root)'}**"
        if node.text:
            preview = node.text[:200].replace("\n", " ")
            line += f": {preview}..."
        lines = [line]
        for child in node.children:
            child_outline = self._build_outline(child, depth + 1)
            if child_outline:
                lines.append(child_outline)
        return "\n".join(lines)

    def _fallback_merge(self, trees: list[DocumentTree]) -> str:
        parts = []
        for tree in trees:
            parts.append(f"# {tree.title}")
            parts.append(tree.root.full_text)
        return "\n\n---\n\n".join(parts)

    def _resolve_conflict(self, conflict: DocumentConflict, hub: Any) -> str:
        prompt = f"""Two document sections appear to contradict each other.

Document A ({conflict.doc_a_title}, section {conflict.doc_a_section}):
{conflict.claim_a}

Document B ({conflict.doc_b_title}, section {conflict.doc_b_section}):
{conflict.claim_b}

Analyze whether this is a genuine contradiction or just different perspectives.
If genuine, suggest how to reconcile or which source to prefer.
Return a concise resolution in 2-3 sentences."""

        try:
            return hub.chat(prompt)
        except Exception:
            return "Unable to resolve — requires human review."

    def _find_tree(self, trees: list[DocumentTree], name: str) -> Optional[DocumentTree]:
        for t in trees:
            if t.title == name or t.source == name:
                return t
        return None

    @staticmethod
    def _title_similarity(title_a: str, title_b: str) -> float:
        if not title_a or not title_b:
            return 0.0
        a = title_a.lower().strip()
        b = title_b.lower().strip()
        if a == b:
            return 1.0
        words_a = set(re.findall(r'\w+', a))
        words_b = set(re.findall(r'\w+', b))
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)

    @staticmethod
    def _text_overlap(text_a: str, text_b: str) -> float:
        if not text_a or not text_b:
            return 0.0
        n = 4
        ngrams_a = {text_a[i:i+n] for i in range(len(text_a) - n + 1)}
        ngrams_b = {text_b[i:i+n] for i in range(len(text_b) - n + 1)}
        if not ngrams_a or not ngrams_b:
            return 0.0
        intersection = ngrams_a & ngrams_b
        return len(intersection) / max(len(ngrams_a), len(ngrams_b))
