"""AutoKnowledgeMiner — reverse-engineer templates & patterns from existing artifacts.

No user intervention needed. Feed it a directory of finalized documents and
production projects. It auto-extracts:

  1. Document Templates: parse DOCX/PDF/MD → extract common structure → synthesize template
  2. Domain Glossary: mine terminology, abbreviations, standard references across documents
  3. Pattern Library: discover recurring paragraph structures, formula usage, table layouts
  4. Code Architecture: scan project trees → infer tech stack, module boundaries, idioms
  5. Cross-Reference Map: link documents ↔ standards ↔ code entities ↔ domain concepts

Continuous learning: every ingested file updates the knowledge model without
user prompts. The system becomes smarter just by being pointed at existing work.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

MINER_DIR = Path(".livingtree/auto_miner")
CONFIDENCE_HIGH = 0.8


@dataclass
class ExtractedTemplate:
    name: str
    sections: list[str] = field(default_factory=list)
    boilerplate: dict[str, str] = field(default_factory=dict)  # section → common text
    structure_skeleton: str = ""
    source_docs: list[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class DomainTerm:
    term: str
    category: str = ""  # "standard", "abbreviation", "metric", "legal", "technical"
    frequency: int = 0
    contexts: list[str] = field(default_factory=list)


@dataclass
class CodePattern:
    name: str
    pattern_type: str = ""  # "module_layout", "import_cluster", "api_pattern", "naming_convention"
    description: str = ""
    examples: list[str] = field(default_factory=list)
    frequency: int = 0


class AutoKnowledgeMiner:
    """Autonomous knowledge extraction from existing enterprise artifacts.

    Point it at any directory. It scans, parses, extracts, links — fully autonomous.
    """

    def __init__(self, hub=None):
        self._hub = hub
        self._templates: dict[str, ExtractedTemplate] = {}
        self._terms: dict[str, DomainTerm] = {}
        self._code_patterns: dict[str, CodePattern] = {}
        self._cross_refs: dict[str, list[str]] = defaultdict(list)  # entity → [related entities]
        self._stats = {"docs_parsed": 0, "projects_scanned": 0, "terms_mined": 0, "templates_extracted": 0}
        self._load()

    # ═══ Main autonomous entry ═══

    async def mine_directory(self, root: str | Path) -> dict:
        """Autonomously mine all knowledge from a directory.

        Detects if it's a document repository, code project, or mixed.
        Returns mining statistics.
        """
        root = Path(root)
        t0 = time.time()

        # Phase 1: Document mining
        doc_files = list(root.rglob("*.docx")) + list(root.rglob("*.pdf")) + list(root.rglob("*.md"))
        if doc_files:
            await self._mine_documents(doc_files)

        # Phase 2: Code project mining
        code_indicators = list(root.glob("*.py")) + list(root.glob("package.json")) + list(root.glob("Cargo.toml"))
        if code_indicators:
            self._mine_code_project(root)

        # Phase 3: Cross-reference building
        self._build_cross_refs()

        # Phase 4: Template synthesis from extracted patterns
        self._synthesize_templates()

        self._stats["_last_mining_duration"] = time.time() - t0
        self._save()
        return self._stats

    # ═══ Phase 1: Document pattern mining ═══

    async def _mine_documents(self, files: list[Path]):
        """Extract common structure, boilerplate, and terms from documents."""
        all_sections: dict[str, Counter] = defaultdict(Counter)
        all_boilerplate: dict[str, list[str]] = defaultdict(list)
        term_counter: Counter = Counter()
        term_contexts: dict[str, list[str]] = defaultdict(list)

        for path in files[:200]:  # Safety cap
            try:
                text = self._extract_text(path)
                if not text or len(text) < 100:
                    continue

                # Extract sections (headers)
                sections = re.findall(r'^#+\s*(.+)$|^第[一二三四五六七八九十百千]+[章节条]\s*(.+)$|^(\d+[\.\、])\s*(.+)$', text, re.MULTILINE)
                for m in sections:
                    heading = next(s for s in m if s).strip()
                    all_sections[path.suffix][heading] += 1
                    # Extract boilerplate: text immediately after heading
                    start = text.find(heading)
                    if start >= 0:
                        content = text[start + len(heading):start + len(heading) + 300]
                        all_boilerplate[heading].append(content.strip())

                # Extract terms
                terms = self._extract_terms(text)
                for term, cat in terms:
                    term_counter[(term, cat)] += 1
                    # Store surrounding context
                    idx = text.find(term)
                    if idx >= 0:
                        ctx = text[max(0, idx - 30):idx + len(term) + 30]
                        term_contexts[term].append(ctx)

                self._stats["docs_parsed"] += 1
            except Exception as e:
                logger.debug(f"Mine doc {path}: {e}")

        # Build domain glossary
        for (term, cat), freq in term_counter.most_common(500):
            if freq >= 2:  # Must appear in at least 2 docs
                self._terms[term] = DomainTerm(
                    term=term, category=cat, frequency=freq,
                    contexts=term_contexts.get(term, [])[:5],
                )
        self._stats["terms_mined"] = len(self._terms)

        # Store section patterns for template synthesis
        self._raw_sections = all_sections
        self._raw_boilerplate = all_boilerplate

    def _extract_terms(self, text: str) -> list[tuple[str, str]]:
        """Extract domain-specific terms with category classification."""
        terms = []
        patterns = [
            (r'GB/?T?\s*\d+[\.-]\d+', "standard"),
            (r'[A-Z]{2,8}(?:\s*\d+)?', "abbreviation"),
            (r'\d+\.?\d*\s*(?:μg/m³|mg/m³|mg/L|dB|t/a|m³/h)', "metric"),
            (r'《([^》]+)》', "legal"),
            (r'(?:环评|环境影响|排放标准|总量控制|清洁生产|风险评价)', "technical"),
        ]
        for pat, cat in patterns:
            for m in re.finditer(pat, text):
                terms.append((m.group(0), cat))
        return terms

    # ═══ Phase 2: Code project mining ═══

    def _mine_code_project(self, root: Path):
        """Scan project structure and extract patterns."""
        patterns = []

        # Detect tech stack
        tech = []
        if (root / "pyproject.toml").exists():
            tech.append("Python")
        if (root / "package.json").exists():
            tech.append("Node.js")
        if (root / "go.mod").exists():
            tech.append("Go")
        if (root / "Cargo.toml").exists():
            tech.append("Rust")

        if tech:
            patterns.append(CodePattern(
                name="tech_stack", pattern_type="project_meta",
                description="Tech stack: " + ", ".join(tech),
            ))

        # Detect module structure
        py_files = list(root.rglob("*.py"))
        if py_files:
            # Import clustering
            imports = Counter()
            for f in py_files[:50]:
                try:
                    for line in f.read_text(errors="replace").splitlines()[:100]:
                        m = re.match(r'^(?:from|import)\s+(\w+)', line.strip())
                        if m:
                            imports[m.group(1)] += 1
                except Exception:
                    continue

            top_imports = imports.most_common(10)
            if top_imports:
                patterns.append(CodePattern(
                    name="dependency_cluster", pattern_type="import_cluster",
                    description="Top imports: " + ", ".join(f"{n}({c})" for n, c in top_imports[:5]),
                ))

            # Detect naming conventions
            func_names = Counter()
            class_names = Counter()
            for f in py_files[:30]:
                try:
                    for line in f.read_text(errors="replace").splitlines()[:50]:
                        fm = re.match(r'def\s+([a-z_]\w*)', line)
                        if fm: func_names[fm.group(1)] += 1
                        cm = re.match(r'class\s+([A-Z]\w*)', line)
                        if cm: class_names[cm.group(1)] += 1
                except Exception:
                    continue

            if func_names:
                patterns.append(CodePattern(
                    name="function_naming", pattern_type="naming_convention",
                    description=f"Functions ({len(func_names)} unique): " + ", ".join(n for n, _ in func_names.most_common(5)),
                ))

        self._code_patterns = {p.name: p for p in patterns}
        self._stats["projects_scanned"] += 1

    # ═══ Phase 3: Cross-reference building ═══

    def _build_cross_refs(self):
        """Link entities across documents, standards, and code."""
        # Term → Standard references
        for term_name, term_obj in self._terms.items():
            for std in ["GB3095", "GB3096", "GB3838", "GB/T3840"]:
                if std in term_name or any(std in ctx for ctx in term_obj.contexts):
                    self._cross_refs[std].append(term_name)

        # Code imports → Domain terms
        for pattern in self._code_patterns.values():
            if pattern.pattern_type == "import_cluster":
                for imp in re.findall(r'(\w+)\(\d+\)', pattern.description):
                    self._cross_refs["code"].append(imp)

    # ═══ Phase 4: Template synthesis ═══

    def _synthesize_templates(self):
        """Synthesize document templates from mined patterns."""
        raw_sec = getattr(self, '_raw_sections', {})
        raw_bp = getattr(self, '_raw_boilerplate', {})

        if not raw_sec or not raw_bp:
            return

        # Find common sections across documents
        for fmt, section_counts in raw_sec.items():
            # Sections appearing in >= 50% of documents
            total_docs = max(max(section_counts.values()), 1)
            common = {s: c for s, c in section_counts.items() if c / total_docs >= 0.5}
            if not common:
                continue

            name = f"auto-template-{fmt.strip('.')}"
            template = ExtractedTemplate(
                name=name,
                sections=list(common.keys()),
                source_docs=[f"{fmt} x{self._stats['docs_parsed']}"],
                confidence=min(1.0, len(common) / 10.0),
            )

            # Extract boilerplate for each common section
            for section in common:
                examples = raw_bp.get(section, [])
                if examples:
                    template.boilerplate[section] = examples[0][:200]

            # Build structure skeleton
            template.structure_skeleton = "\n".join(
                f"## {s}\n{template.boilerplate.get(s, '...')}" for s in common
            )

            self._templates[name] = template
        self._stats["templates_extracted"] = len(self._templates)

    # ═══ Helpers ═══

    def _extract_text(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".md":
            return path.read_text(errors="replace")[:50000]
        elif suffix == ".docx":
            try:
                from docx import Document
                doc = Document(str(path))
                return "\n".join(p.text for p in doc.paragraphs if p.text)[:50000]
            except ImportError:
                return ""
        elif suffix == ".pdf":
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(str(path))
                return "\n".join(p.extract_text() or "" for p in reader.pages[:20])
            except ImportError:
                return ""
        elif suffix in (".txt", ".py", ".json", ".yaml", ".xml"):
            return path.read_text(errors="replace")[:50000]
        return ""

    # ═══ Query API ═══

    def get_templates(self) -> list[ExtractedTemplate]:
        return sorted(self._templates.values(), key=lambda t: -t.confidence)

    def get_terms(self, category: str = "") -> list[DomainTerm]:
        terms = list(self._terms.values())
        if category:
            terms = [t for t in terms if t.category == category]
        return sorted(terms, key=lambda t: -t.frequency)

    def get_patterns(self) -> list[CodePattern]:
        return list(self._code_patterns.values())

    def get_cross_refs(self, entity: str) -> list[str]:
        return self._cross_refs.get(entity, [])

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ═══ Persistence ═══

    def _save(self):
        try:
            MINER_DIR.mkdir(parents=True, exist_ok=True)
            (MINER_DIR / "knowledge.json").write_text(json.dumps({
                "templates": {n: {"name": t.name, "sections": t.sections,
                                  "structure_skeleton": t.structure_skeleton,
                                  "confidence": t.confidence}
                              for n, t in self._templates.items()},
                "terms": {n: {"term": t.term, "category": t.category, "frequency": t.frequency}
                          for n, t in self._terms.items()},
                "code_patterns": {n: {"name": p.name, "pattern_type": p.pattern_type,
                                      "description": p.description}
                                  for n, p in self._code_patterns.items()},
                "cross_refs": dict(self._cross_refs),
                "stats": dict(self._stats),
            }, indent=2, ensure_ascii=False))
        except Exception:
            pass

    def _load(self):
        try:
            path = MINER_DIR / "knowledge.json"
            if path.exists():
                data = json.loads(path.read_text())
                for n, d in data.get("templates", {}).items():
                    self._templates[n] = ExtractedTemplate(**d)
                for n, d in data.get("terms", {}).items():
                    self._terms[n] = DomainTerm(**d)
                for n, d in data.get("code_patterns", {}).items():
                    self._code_patterns[n] = CodePattern(**d)
                self._cross_refs = defaultdict(list, data.get("cross_refs", {}))
                self._stats = data.get("stats", {})
        except Exception:
            pass


# ═══ Global ═══

_miner: AutoKnowledgeMiner | None = None


def get_miner(hub=None) -> AutoKnowledgeMiner:
    global _miner
    if _miner is None:
        _miner = AutoKnowledgeMiner(hub)
    return _miner
