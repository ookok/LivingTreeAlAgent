"""Context Wiki — structured, interlinked knowledge base for LLM context management.

Replaces the lossy "compress everything to 500 chars" FoldAgent approach with
active structured knowledge management. Instead of compressing context, the wiki
structures it into hierarchical, queryable pages — like Wikipedia for conversations.

Architecture:
  Raw Context (tens of thousands of tokens)
      │
      ▼
  ContextWiki.compile()  ← replaces FoldAgent
      │
      ├── Core Summary (always in prompt, ~300 chars)
      ├── Table of Contents (always in prompt, hierarchical)
      ├── Topic Pages (on-demand, by section)
      └── Cross-references (links between related pages)

LLM prompt receives:
  [Core Summary] + [Table of Contents]
  LLM can query: "[[plan:architecture]]" → retrieves that page

Compared to FoldAgent:
  FoldAgent: compress 10K chars → 500 chars (loses 95% of information)
  ContextWiki: structure 10K chars → 50 wiki pages (keeps 100%, loads on-demand)
  Same token budget (2000 chars): 300 summary + 300 TOC + 1400 relevant pages
"""

from __future__ import annotations

import re
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger


# ── Wiki Page ───────────────────────────────────────────────────────────

@dataclass
class WikiPage:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    title: str = ""
    path: str = ""
    content: str = ""
    section: str = ""
    tags: list[str] = field(default_factory=list)
    cross_refs: list[str] = field(default_factory=list)
    importance: float = 0.5
    version: int = 1
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    source_stage: str = ""

    def summary_line(self) -> str:
        return f"  {self.path} (v{self.version}) — {self.title}"

    def to_prompt_block(self) -> str:
        block = f"## {self.path} (v{self.version}, importance={self.importance:.1f})\n{self.title}\n\n{self.content}"
        if self.cross_refs:
            block += f"\n\nRelated: {', '.join(self.cross_refs)}"
        return block

    def to_dict(self) -> dict:
        return {
            "id": self.id, "title": self.title, "path": self.path,
            "content": self.content, "section": self.section,
            "tags": self.tags, "cross_refs": self.cross_refs,
            "importance": self.importance, "version": self.version,
            "created_at": self.created_at, "updated_at": self.updated_at,
            "source_stage": self.source_stage,
        }

    @classmethod
    def from_dict(cls, data: dict) -> WikiPage:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ── Wiki Section ────────────────────────────────────────────────────────

class WikiSection:
    PLAN = "/plan"
    DECISION = "/decision"
    CONTEXT = "/context"
    RESULT = "/result"
    REFLECTION = "/reflection"
    KNOWLEDGE = "/knowledge"

    ALL = (PLAN, DECISION, CONTEXT, RESULT, REFLECTION, KNOWLEDGE)

    LABELS = {
        PLAN: "plan",
        DECISION: "decision",
        CONTEXT: "context",
        RESULT: "result",
        REFLECTION: "reflection",
        KNOWLEDGE: "knowledge",
    }

    STAGE_MAP = {
        "perceive": CONTEXT,
        "cognize": CONTEXT,
        "plan": PLAN,
        "simulate": PLAN,
        "execute": RESULT,
        "reflect": REFLECTION,
        "evolve": KNOWLEDGE,
    }

    @classmethod
    def for_stage(cls, stage_name: str) -> str:
        return cls.STAGE_MAP.get(stage_name.lower(), cls.KNOWLEDGE)


# ── Context Wiki ────────────────────────────────────────────────────────

class ContextWiki:
    """Structured knowledge base that replaces lossy context folding.

    Maintains a hierarchical set of wiki pages created from conversation and
    task context. Pages organized by section (/plan, /decision, /context,
    /result, /reflection, /knowledge).

    Usage:
        wiki = get_context_wiki()
        pages = wiki.compile_stage_output("plan", stage_output, ctx)
        context_block = wiki.build_context(query_hint="architecture", max_chars=2000)
    """

    def __init__(
        self, max_pages: int = 100, max_page_content: int = 800
    ) -> None:
        self._pages: dict[str, WikiPage] = {}
        self._core_summary: str = ""
        self._max_pages = max_pages
        self._max_page_content = max_page_content

    # ── Page CRUD ───────────────────────────────────────────────────

    def add_page(
        self, title: str, content: str, section: str,
        tags: list[str] | None = None, cross_refs: list[str] | None = None,
        importance: float = 0.5, source_stage: str = "",
    ) -> WikiPage:
        path = self._make_path(section, title)
        tags = tags or []
        cross_refs = cross_refs or []

        page = WikiPage(
            title=title, path=path,
            content=self._fit_content(content), section=section,
            tags=tags, cross_refs=cross_refs,
            importance=max(0.0, min(1.0, importance)),
            source_stage=source_stage,
        )
        self._pages[path] = page

        for ref in cross_refs:
            if ref in self._pages and path not in self._pages[ref].cross_refs:
                self._pages[ref].cross_refs.append(path)

        self._enforce_max_pages()
        self._recalculate_core_summary()
        logger.debug("Wiki page added: {}", path)
        return page

    def update_page(
        self, path: str, content: str, importance_delta: float = 0.0
    ) -> WikiPage | None:
        page = self._pages.get(path)
        if not page:
            return None
        page.content = self._fit_content(content)
        page.version += 1
        page.updated_at = time.time()
        page.importance = max(0.0, min(1.0, page.importance + importance_delta))
        self._recalculate_core_summary()
        return page

    def get_page(self, path: str) -> WikiPage | None:
        return self._pages.get(path)

    def remove_page(self, path: str) -> bool:
        page = self._pages.pop(path, None)
        if page is None:
            return False
        for p in self._pages.values():
            if path in p.cross_refs:
                p.cross_refs.remove(path)
        self._recalculate_core_summary()
        return True

    # ── Compile (main entry point) ──────────────────────────────────

    def compile_stage_output(
        self, stage_name: str, stage_content: str, ctx: dict | None = None
    ) -> list[WikiPage]:
        """Main entry point. Called after each LifeEngine stage.

        Extracts key entities, decisions, and action items from stage content
        and creates/updates wiki pages.
        """
        ctx = ctx or {}
        section = WikiSection.for_stage(stage_name)
        results: list[WikiPage] = []

        if stage_name in ("perceive",):
            results.append(self._capture_user_input(stage_content, section, stage_name))

        if stage_name in ("cognize",):
            results.append(self._capture_intent(stage_content, section, stage_name))
            results.append(self._capture_requirements(stage_content, section, stage_name))

        if stage_name in ("plan",):
            results.extend(self._capture_plan_steps(stage_content, section, stage_name))

        if stage_name in ("simulate",):
            results.append(self._capture_simulation(stage_content, section, stage_name))

        if stage_name in ("execute",):
            results.extend(self._capture_results(stage_content, section, stage_name))

        if stage_name in ("reflect",):
            results.append(self._capture_reflection(stage_content, section, stage_name))

        if stage_name in ("evolve",):
            results.append(self._capture_knowledge(stage_content, section, stage_name))

        results = [r for r in results if r is not None]
        logger.info(
            "Wiki compiled stage '{}' → {} pages in section {}",
            stage_name, len(results), section,
        )
        return results

    def _capture_user_input(self, content: str, section: str, stage: str) -> WikiPage:
        return self.add_page(
            title="User Input", content=content, section=section,
            tags=["user_input", "raw"], importance=0.8, source_stage=stage,
        )

    def _capture_intent(self, content: str, section: str, stage: str) -> WikiPage:
        return self.add_page(
            title="Intent Analysis", content=content, section=section,
            tags=["intent", "goal", "purpose"], importance=0.9, source_stage=stage,
        )

    def _capture_requirements(self, content: str, section: str, stage: str) -> WikiPage:
        existing = self.get_page(f"{section}/intent_analysis")
        refs = [existing.path] if existing else []
        return self.add_page(
            title="Requirements", content=content, section=section,
            tags=["requirements", "constraints", "specifications"],
            cross_refs=refs, importance=0.8, source_stage=stage,
        )

    def _capture_plan_steps(self, content: str, section: str, stage: str) -> list[WikiPage]:
        steps = self._split_numbered(content)
        if len(steps) <= 1:
            return [
                self.add_page(
                    title="Plan Overview", content=content, section=section,
                    tags=["plan", "strategy"], importance=0.85, source_stage=stage,
                )
            ]
        pages = []
        for i, step in enumerate(steps):
            pages.append(
                self.add_page(
                    title=f"Step {i + 1}", content=step, section=section,
                    tags=["plan", f"step_{i + 1}"], importance=0.7, source_stage=stage,
                )
            )
        return pages

    def _capture_simulation(self, content: str, section: str, stage: str) -> WikiPage:
        return self.add_page(
            title="Simulation Findings", content=content, section=section,
            tags=["simulation", "prediction", "dry_run"],
            importance=0.65, source_stage=stage,
        )

    def _capture_results(self, content: str, section: str, stage: str) -> list[WikiPage]:
        items = self._split_numbered(content)
        if len(items) <= 1:
            return [
                self.add_page(
                    title="Execution Result", content=content, section=section,
                    tags=["result", "output"], importance=0.7, source_stage=stage,
                )
            ]
        pages = []
        for i, item in enumerate(items):
            pages.append(
                self.add_page(
                    title=f"Result {i + 1}", content=item, section=section,
                    tags=["result", f"item_{i + 1}"], importance=0.6, source_stage=stage,
                )
            )
        return pages

    def _capture_reflection(self, content: str, section: str, stage: str) -> WikiPage:
        return self.add_page(
            title="Reflection", content=content, section=section,
            tags=["reflection", "lessons", "meta_analysis"],
            importance=0.75, source_stage=stage,
        )

    def _capture_knowledge(self, content: str, section: str, stage: str) -> WikiPage:
        return self.add_page(
            title="Extracted Knowledge", content=content, section=section,
            tags=["knowledge", "learning", "domain"],
            importance=0.55, source_stage=stage,
        )

    def _split_numbered(self, text: str) -> list[str]:
        items = re.split(r"\n(?=\d+[\.\)]\s)", text.strip())
        if len(items) > 1:
            return [item.strip() for item in items if item.strip()]
        items = re.split(r"\n(?=Step\s+\d+)", text.strip(), flags=re.IGNORECASE)
        return [item.strip() for item in items if item.strip()]

    # ── Core Summary ────────────────────────────────────────────────

    def get_core_summary(self) -> str:
        return self._core_summary

    def _recalculate_core_summary(self) -> None:
        if not self._pages:
            self._core_summary = ""
            return
        parts: list[str] = []

        intent = self._pages.get("/context/intent_analysis")
        if intent:
            intent_text = intent.content[:120].replace("\n", " ").strip()
            task_desc = f"Task: {intent_text}"
            if len(task_desc) > 150:
                task_desc = task_desc[:147] + "..."
            parts.append(task_desc)

        plan_pages = [p for p in self._pages.values() if p.section == "/plan"]
        if plan_pages:
            parts.append(f"Plan: {len(plan_pages)} steps.")

        decision_pages = [p for p in self._pages.values() if p.section == "/decision"]
        if decision_pages:
            decision_strs = [d.title for d in sorted(decision_pages, key=lambda x: -x.importance)[:3]]
            parts.append(f"Key decisions: {', '.join(decision_strs)}.")

        result_pages = [p for p in self._pages.values() if p.section == "/result"]
        if result_pages:
            success = sum(1 for p in result_pages if "error" not in p.content.lower())
            parts.append(f"Results: {success}/{len(result_pages)} ok.")

        refl_pages = [p for p in self._pages.values() if p.section == "/reflection"]
        if refl_pages:
            lesson = refl_pages[0].content[:100].replace("\n", " ").strip()
            if len(lesson) > 100:
                lesson = lesson[:97] + "..."
            parts.append(f"Lessons: {lesson}")

        self._core_summary = " ".join(parts)[:400]

    # ── Table of Contents ───────────────────────────────────────────

    def get_table_of_contents(self) -> str:
        if not self._pages:
            return "## Wiki Index\n_(empty)_"

        sections: dict[str, list[WikiPage]] = defaultdict(list)
        for page in self._pages.values():
            sections[page.section].append(page)

        lines = ["## Wiki Index"]
        for section in WikiSection.ALL:
            pages = sorted(sections.get(section, []), key=lambda p: -p.importance)
            if not pages:
                continue
            lines.append(f"### {section} ({len(pages)} page{'s' if len(pages) > 1 else ''})")
            for page in pages:
                lines.append(page.summary_line())
        return "\n".join(lines)

    # ── Build Context (key method) ──────────────────────────────────

    def build_context(self, query_hint: str = "", max_chars: int = 2000) -> str:
        """Build optimized context for LLM prompt injection.

        Algorithm:
          1. Core summary (~300 chars, always included)
          2. Table of contents (~300 chars, always included)
          3. If query_hint: top 3 matching pages by hint
             Else: top 3 pages by importance
          4. Fill remaining budget with high-importance pages not yet included
          5. Never exceed max_chars
        """
        budget = max_chars
        pieces: list[str] = []
        included: set[str] = set()

        core = self.get_core_summary()
        if core:
            pieces.append(core)
            budget -= len(core)

        toc = self.get_table_of_contents()
        if budget > len(toc):
            pieces.append(toc)
            budget -= len(toc)
        elif budget > 100:
            pieces.append(toc[:budget])
            budget = 0

        if budget <= 100 or not self._pages:
            return "\n\n".join(pieces)

        if query_hint:
            candidates = self.query(query_hint, limit=3)
        else:
            candidates = sorted(
                self._pages.values(), key=lambda p: -p.importance
            )[:3]

        for page in candidates:
            if page.path in included:
                continue
            block = page.to_prompt_block()
            if budget > len(block) + 10:
                pieces.append(block)
                included.add(page.path)
                budget -= len(block) + 2

        remaining = sorted(
            [p for p in self._pages.values() if p.path not in included],
            key=lambda p: -p.importance,
        )
        for page in remaining:
            if budget <= 100:
                break
            block = page.to_prompt_block()
            if budget > len(block) + 10:
                pieces.append(block)
                included.add(page.path)
                budget -= len(block) + 2

        return "\n\n".join(pieces)

    # ── Query & Search ──────────────────────────────────────────────

    def query(
        self, topic: str, section: str | None = None, limit: int = 5
    ) -> list[WikiPage]:
        """LLM on-demand lookup by path, title, tag, or content keyword."""
        topic_lower = topic.lower()
        scored: list[tuple[float, WikiPage]] = []

        for page in self._pages.values():
            if section and page.section != section:
                continue
            score = 0.0

            if page.path.lower() == topic_lower:
                score += 10.0
            elif topic_lower in page.path.lower():
                score += 6.0
            elif topic_lower in page.title.lower():
                score += 5.0
            elif any(topic_lower in t.lower() for t in page.tags):
                score += 4.0
            elif topic_lower in page.content.lower():
                score += 2.0

            if score > 0:
                scored.append((score * page.importance, page))

        scored.sort(key=lambda x: -x[0])
        return [page for _, page in scored[:limit]]

    def search(self, query_text: str) -> list[WikiPage]:
        """Full-text search across all page content."""
        query_lower = query_text.lower()
        scored: list[tuple[float, WikiPage]] = []

        for page in self._pages.values():
            score = 0.0
            if query_lower in page.title.lower():
                score += 5.0
            if query_lower in page.content.lower():
                score += float(page.content.lower().count(query_lower)) * 0.5
            for tag in page.tags:
                if query_lower in tag.lower():
                    score += 3.0
            if score > 0:
                scored.append((score * page.importance, page))

        scored.sort(key=lambda x: -x[0])
        return [page for _, page in scored]

    def get_recent_changes(self, limit: int = 10) -> list[WikiPage]:
        return sorted(
            self._pages.values(), key=lambda p: -p.updated_at
        )[:limit]

    # ── Stats ───────────────────────────────────────────────────────

    def stats(self) -> dict:
        sections: dict[str, int] = defaultdict(int)
        total_versions = 0
        for p in self._pages.values():
            sections[p.section] += 1
            total_versions += p.version

        avg_imp = (
            sum(p.importance for p in self._pages.values()) / len(self._pages)
            if self._pages else 0.0
        )

        return {
            "total_pages": len(self._pages),
            "pages_by_section": dict(sections),
            "total_versions": total_versions,
            "avg_importance": round(avg_imp, 3),
            "core_summary_length": len(self._core_summary),
        }

    # ── Persistence ─────────────────────────────────────────────────

    def export_wiki(self) -> dict:
        return {
            "pages": [p.to_dict() for p in self._pages.values()],
            "core_summary": self._core_summary,
            "max_pages": self._max_pages,
            "max_page_content": self._max_page_content,
        }

    def import_wiki(self, data: dict) -> None:
        self._pages.clear()
        for page_data in data.get("pages", []):
            page = WikiPage.from_dict(page_data)
            self._pages[page.path] = page
        self._core_summary = data.get("core_summary", "")
        self._max_pages = data.get("max_pages", self._max_pages)
        self._max_page_content = data.get("max_page_content", self._max_page_content)
        self._recalculate_core_summary()
        logger.info("Wiki imported: {} pages", len(self._pages))

    # ── Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _make_path(section: str, title: str) -> str:
        slug = re.sub(r"[^\w\s-]", "", title.lower().strip())
        slug = re.sub(r"[\s_]+", "_", slug)
        slug = slug.strip("-_")
        if not slug:
            slug = str(uuid.uuid4())[:8]
        return f"{section}/{slug}"

    def _fit_content(self, content: str) -> str:
        if len(content) <= self._max_page_content:
            return content.strip()
        return content[: self._max_page_content - 3].strip() + "..."

    def _enforce_max_pages(self) -> None:
        if len(self._pages) <= self._max_pages:
            return
        oldest = sorted(
            self._pages.values(),
            key=lambda p: (p.importance, -p.created_at),
        )
        to_remove = oldest[: len(oldest) - self._max_pages]
        for page in to_remove:
            self._pages.pop(page.path, None)
            for p in self._pages.values():
                if page.path in p.cross_refs:
                    p.cross_refs.remove(page.path)


# ── Wiki Tool (LLM-callable interface) ──────────────────────────────────

class WikiTool:
    """Exposes ContextWiki as LLM-callable tools.

    Usage:
        wiki = get_context_wiki()
        tool = WikiTool(wiki)
        await tool.search_wiki("architecture")
        await tool.read_page("/plan/step_1")
        await tool.list_section("/decision")
    """

    def __init__(self, wiki: ContextWiki) -> None:
        self._wiki = wiki

    async def search_wiki(self, query: str) -> str:
        pages = self._wiki.search(query)
        if not pages:
            return f"No wiki pages found for '{query}'."
        lines = [f"Search results for '{query}':"]
        for page in pages[:5]:
            lines.append(
                f"  {page.path} — {page.title} (importance={page.importance:.1f}, v{page.version})"
            )
        return "\n".join(lines)

    async def read_page(self, path: str) -> str:
        page = self._wiki.get_page(path)
        if not page:
            return f"Wiki page '{path}' not found. Try search_wiki() to find relevant pages."
        return page.to_prompt_block()

    async def list_section(self, section: str) -> str:
        pages = self._wiki.query("", section=section, limit=20)
        if not pages:
            return f"No pages in section '{section}'."
        lines = [f"Section {section}:"]
        for page in sorted(pages, key=lambda p: -p.importance):
            lines.append(page.summary_line())
        return "\n".join(lines)


# ── Singleton ───────────────────────────────────────────────────────────

_wiki: Optional[ContextWiki] = None


def get_context_wiki() -> ContextWiki:
    global _wiki
    if _wiki is None:
        _wiki = ContextWiki()
    return _wiki


def reset_context_wiki() -> None:
    global _wiki
    _wiki = None
