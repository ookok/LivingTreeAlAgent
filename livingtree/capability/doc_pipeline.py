"""DocPipeline — CI/CD, pre-commit hooks, template registry for documents.

Maps the remaining code dev tools to document generation:
  1. CI/CD Pipeline    (GitHub Actions → auto-build+check+deploy on save)
  2. Pre-save Hooks    (pre-commit → lint+consistency before write)
  3. Template Registry (PyPI → searchable document template hub)
  4. Semantic Version  (semver → major.minor.patch for docs)
  5. Generation Budget (rate limiting → token quota per section)
  6. Dead Content Det  (dead code → unreferenced sections)
  7. Document Rollback (git revert → restore previous version)
  8. Dependency Visual (import graph → section reference map)

All performance-critical paths use ContentGraph O(1) index + VFS.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ═══ 1. Document CI/CD Pipeline ═══════════════════════════════════

@dataclass
class PipelineStage:
    """A single stage in the document pipeline."""
    name: str
    passed: bool = False
    duration_ms: float = 0
    output: dict = field(default_factory=dict)
    error: str = ""


@dataclass
class PipelineResult:
    """Complete pipeline execution result."""
    stages: list[PipelineStage]
    total_ms: float = 0
    passed: bool = False
    artifact_path: str = ""


class DocumentPipeline:
    """CI/CD pipeline for documents — auto-build, check, deploy.

    Like GitHub Actions but for document generation:
      on: push → lint → consistency → coverage → build → deploy
    """

    @classmethod
    async def run(cls, content: str, template_type: str = "eia_report",
                  output_dir: str = "", auto_deploy: bool = False) -> PipelineResult:
        """Run full CI/CD pipeline on a document."""
        stages = []
        t0 = time.time()

        # Stage 1: Lint
        t1 = time.time()
        try:
            from .content_graph import ContentGraph
            cg = ContentGraph()
            lint_issues = cg.lint_document(content, template_type)
            passed = len([i for i in lint_issues if i.severity == "error"]) == 0
            stages.append(PipelineStage(
                name="lint", passed=passed,
                duration_ms=(time.time()-t1)*1000,
                output={"issues": len(lint_issues)},
            ))
        except Exception as e:
            stages.append(PipelineStage(name="lint", passed=False, error=str(e)[:100]))

        # Stage 2: Consistency
        t1 = time.time()
        try:
            from .content_graph import get_content_graph
            cg = get_content_graph()
            issues = cg.check_all()
            passed = len(issues) == 0
            stages.append(PipelineStage(
                name="consistency", passed=passed,
                duration_ms=(time.time()-t1)*1000,
                output={"issues": len(issues)},
            ))
        except Exception as e:
            stages.append(PipelineStage(name="consistency", passed=False, error=str(e)[:100]))

        # Stage 3: Coverage
        t1 = time.time()
        try:
            from .doc_forge import RequirementCoverage
            cov = RequirementCoverage.check(content, template_type)
            passed = cov["coverage_pct"] >= 80
            stages.append(PipelineStage(
                name="coverage", passed=passed,
                duration_ms=(time.time()-t1)*1000,
                output=cov,
            ))
        except Exception as e:
            stages.append(PipelineStage(name="coverage", passed=False, error=str(e)[:100]))

        # Stage 4: Schema validation
        t1 = time.time()
        try:
            from .doc_forge import DocumentSchema
            schema = DocumentSchema.validate(content, template_type)
            passed = schema["valid"]
            stages.append(PipelineStage(
                name="schema", passed=passed,
                duration_ms=(time.time()-t1)*1000,
                output=schema,
            ))
        except Exception as e:
            stages.append(PipelineStage(name="schema", passed=False, error=str(e)[:100]))

        # Stage 5: Build artifact
        t1 = time.time()
        artifact_path = ""
        try:
            from .report_enhancer import FormatPipeline
            out_dir = Path(output_dir or ".livingtree/pipeline_output")
            out_dir.mkdir(parents=True, exist_ok=True)
            artifact_path = FormatPipeline.export_docx(
                {"title": template_type, "sections": [{"heading": "Main", "body": content}]},
                template_type, str(out_dir / f"{template_type}_{int(time.time())}.docx"),
            )
            stages.append(PipelineStage(
                name="build", passed=True,
                duration_ms=(time.time()-t1)*1000,
                output={"artifact": artifact_path},
            ))
        except Exception as e:
            stages.append(PipelineStage(name="build", passed=False, error=str(e)[:100]))

        all_passed = all(s.passed for s in stages)
        return PipelineResult(
            stages=stages,
            total_ms=(time.time()-t0)*1000,
            passed=all_passed,
            artifact_path=artifact_path if all_passed else "",
        )

    @classmethod
    def format_result(cls, result: PipelineResult) -> str:
        icons = {True: "✅", False: "❌"}
        lines = ["## 📋 Document CI/CD Pipeline", "", "| Stage | Status | Time | Details |", "|-------|--------|------|---------|"]
        for s in result.stages:
            detail = s.error or json.dumps(s.output, ensure_ascii=False)[:60]
            lines.append(f"| {s.name} | {icons[s.passed]} | {s.duration_ms:.0f}ms | {detail} |")
        lines.append(f"\n**Result: {'✅ PASSED' if result.passed else '❌ FAILED'}** ({result.total_ms:.0f}ms)")
        if result.artifact_path:
            lines.append(f"\n📄 Artifact: {result.artifact_path}")
        return "\n".join(lines)


# ═══ 2. Pre-save Hooks (like pre-commit) ══════════════════════════

class PreSaveHook:
    """Auto-check document before saving (like git pre-commit hooks).

    Registered hooks run sequentially. Any failure can block the save.
    """

    _hooks: list[callable] = []

    @classmethod
    def register(cls, name: str, check_fn: callable, blocking: bool = True):
        cls._hooks.append({"name": name, "check": check_fn, "blocking": blocking})

    @classmethod
    async def run_all(cls, content: str, template_type: str = "",
                      filepath: str = "") -> dict:
        """Run all registered pre-save hooks."""
        results = []
        blocked = False
        for hook in cls._hooks:
            try:
                result = hook["check"](content, template_type, filepath)
                if asyncio.iscoroutinefunction(hook["check"]):
                    result = await result
                passed = result.get("passed", True) if isinstance(result, dict) else bool(result)
                results.append({"hook": hook["name"], "passed": passed, "result": result})
                if not passed and hook["blocking"]:
                    blocked = True
            except Exception as e:
                results.append({"hook": hook["name"], "passed": False, "error": str(e)[:100]})

        return {"passed": not blocked, "blocked": blocked, "results": results}

    @classmethod
    def register_defaults(cls):
        """Register the standard set of pre-save hooks."""
        from .content_graph import ContentGraph

        def _lint_check(content, template_type, filepath):
            cg = ContentGraph()
            issues = cg.lint_document(content, template_type)
            errors = [i for i in issues if i.severity == "error"]
            return {"passed": len(errors) == 0, "errors": len(errors)}

        def _consistency_check(content, template_type, filepath):
            return {"passed": True, "message": "no cross-doc check on single file"}

        def _spell_check(content, template_type, filepath):
            from .text_craft import SpellChecker
            issues = SpellChecker.check(content)
            errors = [i for i in issues if i.severity == "error"]
            return {"passed": len(errors) == 0, "errors": len(errors)}

        def _size_check(content, template_type, filepath):
            size = len(content)
            return {"passed": size > 50, "size": size,
                    "message": "内容过短" if size < 50 else "ok"}

        cls.register("lint", _lint_check, blocking=True)
        cls.register("spell", _spell_check, blocking=False)  # Warning only
        cls.register("size", _size_check, blocking=True)
        cls.register("consistency", _consistency_check, blocking=False)


# ═══ 3. Template Registry (like PyPI) ═════════════════════════════

@dataclass
class TemplateEntry:
    """A document template in the registry."""
    name: str
    category: str         # eia | emergency | feasibility | meeting | custom
    description: str
    sections: list[str]
    version: str = "1.0.0"
    author: str = ""
    downloads: int = 0
    rating: float = 0.0
    tags: list[str] = field(default_factory=list)


class TemplateRegistry:
    """Searchable document template hub (like PyPI for packages)."""

    _templates: dict[str, TemplateEntry] = {}
    _registry_file = Path(".livingtree/template_registry.json")

    @classmethod
    def _load(cls):
        if cls._templates: return
        # Built-in templates
        cls.register(TemplateEntry("eia_report", "eia", "环境影响评价报告书",
            ["总论","工程分析","环境现状","影响预测","防治措施","风险评价","结论"], "2.0"))
        cls.register(TemplateEntry("emergency_plan", "emergency", "突发环境事件应急预案",
            ["总则","风险评估","应急组织","应急响应","后期处置","保障措施","附则"], "1.5"))
        cls.register(TemplateEntry("feasibility", "feasibility", "可行性研究报告",
            ["总论","市场分析","技术方案","投资估算","财务评价","风险分析","结论"], "1.0"))
        cls.register(TemplateEntry("meeting_minutes", "meeting", "会议纪要",
            ["基本信息","议题","讨论","决议","待办事项"], "1.0"))
        cls.register(TemplateEntry("monthly_report", "report", "月度工作报告",
            ["概述","关键指标","项目进展","问题与风险","下月计划"], "1.0"))

        # Load user-created templates
        if cls._registry_file.exists():
            try:
                data = json.loads(cls._registry_file.read_text())
                for t in data:
                    cls.register(TemplateEntry(**t))
            except Exception: pass

    @classmethod
    def register(cls, template: TemplateEntry):
        cls._templates[template.name] = template

    @classmethod
    def search(cls, query: str = "", category: str = "") -> list[TemplateEntry]:
        cls._load()
        results = list(cls._templates.values())
        if category:
            results = [t for t in results if t.category == category]
        if query:
            ql = query.lower()
            results = [t for t in results if ql in t.name.lower() or ql in t.description.lower()
                      or any(ql in s.lower() for s in t.sections)]
        return sorted(results, key=lambda t: -t.downloads)

    @classmethod
    def install(cls, name: str, output_dir: str = "") -> str:
        """Instantiate a template — create the document skeleton."""
        cls._load()
        tpl = cls._templates.get(name)
        if not tpl: return ""
        tpl.downloads += 1
        lines = [f"# {tpl.description}", f"", f"*模板: {name} v{tpl.version}*", ""]
        for section in tpl.sections:
            lines.append(f"## {section}")
            lines.append("")
            lines.append("<!-- TODO: fill content -->")
            lines.append("")
        out = Path(output_dir or ".") / f"{name}_{int(time.time())}.md"
        out.write_text("\n".join(lines), encoding="utf-8")
        return str(out)

    @classmethod
    def save_custom(cls, name: str, sections: list[str], category: str = "custom",
                    description: str = ""):
        tpl = TemplateEntry(name, category, description or name, sections)
        cls.register(tpl)
        # Persist
        data = [{"name": t.name, "category": t.category, "description": t.description,
                 "sections": t.sections, "version": t.version}
                for t in cls._templates.values() if t.category == "custom"]
        cls._registry_file.parent.mkdir(parents=True, exist_ok=True)
        cls._registry_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))


# ═══ 4. Semantic Versioning ═══════════════════════════════════════

class DocVersion:
    """Semantic versioning for documents (like semver)."""

    @staticmethod
    def bump_major(version: str) -> str:
        parts = version.split(".")
        return f"{int(parts[0])+1}.0.0"

    @staticmethod
    def bump_minor(version: str) -> str:
        parts = version.split(".")
        return f"{parts[0]}.{int(parts[1])+1}.0" if len(parts) > 1 else f"{parts[0]}.1.0"

    @staticmethod
    def bump_patch(version: str) -> str:
        parts = version.split(".")
        if len(parts) > 2:
            return f"{parts[0]}.{parts[1]}.{int(parts[2])+1}"
        return f"{parts[0]}.0.1" if len(parts) == 1 else f"{parts[0]}.{parts[1]}.1"

    @classmethod
    def auto_bump(cls, old_content: str, new_content: str,
                  current_version: str = "1.0.0") -> tuple[str, str]:
        """Auto-bump version based on change magnitude."""
        import difflib
        diff = list(difflib.unified_diff(old_content.splitlines(), new_content.splitlines()))
        added = sum(1 for l in diff if l.startswith('+') and not l.startswith('+++'))
        removed = sum(1 for l in diff if l.startswith('-') and not l.startswith('---'))

        total_changes = added + removed
        if total_changes > 200:
            return cls.bump_major(current_version), "major"
        elif total_changes > 50:
            return cls.bump_minor(current_version), "minor"
        else:
            return cls.bump_patch(current_version), "patch"


# ═══ 5. Generation Budget (rate limiting) ═════════════════════════

class GenerationBudget:
    """Token budget management across document sections (like API rate limiting)."""

    def __init__(self, total_budget: int = 50000):
        self._total = total_budget
        self._used = 0
        self._by_section: dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()

    async def allocate(self, section: str, requested: int) -> int:
        async with self._lock:
            remaining = self._total - self._used
            allocated = min(requested, remaining)
            self._used += allocated
            self._by_section[section] += allocated
            return allocated

    def section_usage(self, section: str) -> int:
        return self._by_section.get(section, 0)

    @property
    def remaining(self) -> int:
        return self._total - self._used

    @property
    def usage_pct(self) -> float:
        return self._used / max(self._total, 1) * 100

    def suggest_allocation(self, sections: list[str]) -> dict[str, int]:
        """Suggest token allocation across sections."""
        if not sections: return {}
        per_section = self._total // len(sections)
        return {s: per_section for s in sections}


# ═══ 6. Dead Content Detection ════════════════════════════════════

class DeadContentDetector:
    """Detect unreferenced content sections (like dead code elimination)."""

    @classmethod
    def detect(cls, content: str, reference_graph: dict = None) -> dict:
        """Find sections that are not referenced by any other section."""
        sections = {}
        current_section = ""
        current_content = []
        for line in content.split('\n'):
            if line.startswith('## '):
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = line[3:].strip()
                current_content = []
            elif current_section:
                current_content.append(line)
        if current_section:
            sections[current_section] = '\n'.join(current_content)

        # Check which sections are referenced
        referenced = set()
        for name, body in sections.items():
            for other_name in sections:
                if other_name != name and any(
                    keyword in body for keyword in [other_name[:4], other_name[:6]]
                ):
                    referenced.add(other_name)

        unreferenced = {k: v for k, v in sections.items() if k not in referenced}
        return {
            "total_sections": len(sections),
            "referenced": len(referenced),
            "unreferenced": len(unreferenced),
            "unreferenced_sections": list(unreferenced.keys()),
            "suggestion": "Consider removing or linking these sections" if unreferenced else "All sections are referenced",
        }


# ═══ 7. Document Rollback ═════════════════════════════════════════

class DocumentRollback:
    """Version history with instant rollback (like git revert)."""

    def __init__(self):
        self._history: list[dict] = []
        self._storage = Path(".livingtree/doc_versions")
        self._storage.mkdir(parents=True, exist_ok=True)

    def save(self, content: str, label: str = "") -> int:
        ver = len(self._history) + 1
        path = self._storage / f"doc_v{ver:04d}.md"
        path.write_text(content, encoding="utf-8")
        self._history.append({
            "version": ver, "label": label, "path": str(path),
            "timestamp": datetime.now().isoformat(), "size": len(content),
        })
        return ver

    def rollback(self, to_version: int) -> str:
        for h in self._history:
            if h["version"] == to_version:
                return Path(h["path"]).read_text(encoding="utf-8")
        return ""

    def history(self) -> list[dict]:
        return self._history[-20:]

    def diff_versions(self, v1: int, v2: int) -> str:
        import difflib
        c1 = self.rollback(v1)
        c2 = self.rollback(v2)
        return '\n'.join(difflib.unified_diff(
            c1.splitlines(), c2.splitlines(),
            fromfile=f"v{v1}", tofile=f"v{v2}",
        ))

    def auto_save_on_change(self, content: str, old_content: str):
        if content != old_content:
            self.save(content, "auto")


# ═══ 8. Dependency Visual ════════════════════════════════════════

class SectionDependencyMap:
    """Visual dependency graph for document sections (like import graph)."""

    @classmethod
    def build_mermaid(cls, sections: list[str],
                      references: dict[str, list[str]] = None) -> str:
        """Generate Mermaid graph of section dependencies."""
        refs = references or {}
        lines = ["graph TD"]
        node_ids = {}

        for i, section in enumerate(sections):
            nid = f"S{i}"
            node_ids[section] = nid
            lines.append(f"    {nid}[{section[:20]}]")

        for section, ref_list in (refs or {}).items():
            if section in node_ids:
                for ref in ref_list:
                    if ref in node_ids and node_ids[section] != node_ids[ref]:
                        lines.append(f"    {node_ids[section]} --> {node_ids[ref]}")

        return "```mermaid\n" + "\n".join(lines) + "\n```"


# ═══ Singleton ════════════════════════════════════════════════════

# Register default pre-save hooks on import
PreSaveHook.register_defaults()


__all__ = [
    "DocumentPipeline", "PipelineStage", "PipelineResult",
    "PreSaveHook", "TemplateRegistry", "TemplateEntry",
    "DocVersion", "GenerationBudget",
    "DeadContentDetector", "DocumentRollback",
    "SectionDependencyMap",
]
