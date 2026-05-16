"""DocForge — IDE-like tools for document generation (code-dev analogue).

Maps the full code development toolchain to document generation:
  1. Auto-complete   (Copilot → Section Suggestion)
  2. Rename Entity   (IDE rename → entity propagation across docs)
  3. Live Preview    (hot reload → real-time document preview)
  4. Document Review (PR review → diff + comment + approve)
  5. Coverage Check  (code coverage → requirement coverage)
  6. Document Schema (OpenAPI → document structure validation)
  7. Dependency Graph (imports → cross-references)
  8. Publishing      (PyPI → format export + distribution)

All performance-critical paths use ContentGraph's O(1) property index.
"""

from __future__ import annotations

import asyncio
import difflib
import hashlib
import json
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ═══ 1. Section Auto-Complete (like Copilot) ══════════════════════

@dataclass
class SectionSuggestion:
    """A suggested next section with context."""
    heading: str
    template: str           # Section skeleton
    based_on: list[str]     # Which previous sections informed this
    confidence: float
    estimated_tokens: int


class SectionSuggester:
    """Suggest next section based on template + previous sections.

    Like Copilot: given what's already written, what should come next?
    """

    TEMPLATE_SEQUENCES = {
        "eia_report": [
            "总论", "工程分析", "环境现状调查与评价",
            "环境影响预测与评价", "环境保护措施",
            "环境风险评价", "环境经济损益分析",
            "环境管理与监测计划", "结论与建议",
        ],
        "emergency_plan": [
            "总则", "风险评估", "应急组织体系",
            "应急响应", "后期处置", "保障措施", "附则",
        ],
        "feasibility": [
            "总论", "市场分析", "技术方案",
            "投资估算", "财务评价", "风险分析", "结论",
        ],
    }

    SECTION_HINTS = {
        "环境影响预测与评价": {
            "subsections": ["大气环境影响", "水环境影响", "声环境影响", "固体废物影响", "生态环境影响"],
            "required_data": ["source_params", "water_params", "noise_params"],
            "models": ["gaussian_plume", "streeter_phelps", "noise_attenuation"],
        },
        "工程分析": {
            "subsections": ["生产工艺", "物料平衡", "污染源强核算", "总量控制"],
            "required_data": ["process_flow", "material_balance"],
        },
        "环境风险评价": {
            "subsections": ["风险识别", "源项分析", "后果预测", "风险防范措施"],
            "required_data": ["hazardous_materials", "max_credible_accident"],
            "models": ["hazard_quotient", "risk_matrix"],
        },
    }

    @classmethod
    def suggest_next(cls, template_type: str,
                     completed_sections: list[str],
                     available_data: dict = None) -> SectionSuggestion | None:
        """Suggest the next logical section to write."""
        sequence = cls.TEMPLATE_SEQUENCES.get(template_type, [])
        if not sequence:
            return None

        # Find where we are
        written = set(completed_sections)
        next_section = None
        for section in sequence:
            if section not in written:
                next_section = section
                break

        if not next_section:
            return None

        hints = cls.SECTION_HINTS.get(next_section, {})
        subsections = hints.get("subsections", [])
        required_data = hints.get("required_data", [])
        models = hints.get("models", [])

        # Check data availability
        data = available_data or {}
        data_ready = all(k in data for k in required_data)

        # Build template
        template_lines = [f"## {next_section}", ""]
        for sub in subsections:
            template_lines.append(f"### {sub}")
            template_lines.append("")  # Placeholder
            template_lines.append("")

        return SectionSuggestion(
            heading=next_section,
            template="\n".join(template_lines),
            based_on=completed_sections[-3:] if completed_sections else [],
            confidence=0.9 if data_ready else 0.5,
            estimated_tokens=len(subsections) * 200 + 500,
        )

    @classmethod
    def check_completeness(cls, template_type: str,
                           sections: list[str]) -> dict:
        """Check what's missing from the required sequence."""
        sequence = cls.TEMPLATE_SEQUENCES.get(template_type, [])
        completed = set(sections)
        missing = [s for s in sequence if s not in completed]
        extra = [s for s in sections if s not in set(sequence)]

        return {
            "total_required": len(sequence),
            "completed": len(sequence) - len(missing),
            "missing": missing,
            "extra_sections": extra,
            "completeness_pct": round((len(sequence) - len(missing)) / max(len(sequence), 1) * 100),
        }


# ═══ 2. Entity Rename (like IDE rename symbol) ═══════════════════

class EntityRenamer:
    """Rename an entity across all documents (like IDE 'rename symbol').

    Uses ContentGraph to find all occurrences and suggests edits.
    """

    @classmethod
    def rename(cls, old_name: str, new_name: str,
               content_graph=None, vfs=None) -> dict:
        """Rename entity across all indexed documents."""
        if not content_graph:
            try:
                from .content_graph import get_content_graph
                content_graph = get_content_graph()
            except Exception:
                return {"error": "ContentGraph unavailable"}

        # Find all occurrences
        entities = content_graph._entities
        matches = []
        for key, entity in entities.items():
            if entity.name == old_name:
                for occ in entity.occurrences:
                    matches.append({
                        "file": occ.file,
                        "line": occ.line,
                        "context": occ.context,
                    })

        # Generate edits (like IDE refactoring preview)
        edits = []
        files_affected = set()
        for m in matches:
            files_affected.add(m["file"])
            old_text = m["context"]
            if old_name in old_text:
                new_text = old_text.replace(old_name, new_name)
                edits.append({
                    "file": m["file"],
                    "line": m["line"],
                    "edit": f"s/{old_name}/{new_name}/g",
                    "before": old_text[:80],
                    "after": new_text[:80],
                })

        # Apply if vfs provided
        applied = 0
        if vfs and edits:
            for edit in edits:
                try:
                    # Read current content
                    content = vfs.read_file(edit["file"])
                    # Simple replacement (full implementation would use difflib)
                    new_content = content.replace(old_name, new_name)
                    if new_content != content:
                        vfs.write_file(edit["file"], new_content)
                        applied += 1
                except Exception:
                    pass

        return {
            "old_name": old_name,
            "new_name": new_name,
            "occurrences": len(matches),
            "files_affected": len(files_affected),
            "edits": edits[:20],
            "applied": applied,
            "dry_run": not bool(vfs),
        }


# ═══ 3. Live Preview (like hot reload) ════════════════════════════

class LivePreview:
    """Real-time document preview with auto-refresh on VFS changes.

    Like web dev hot reload: edit document → see rendered output instantly.
    """

    def __init__(self, vfs_path: str = "/disk/report.md",
                 output_path: str = "/tmp/preview.html"):
        self._vfs_path = vfs_path
        self._output_path = output_path
        self._last_hash = ""
        self._callbacks: list[callable] = []

    async def watch_and_render(self, vfs=None, interval: float = 1.0):
        """Watch VFS file for changes and re-render preview."""
        if not vfs:
            try:
                from ..capability.virtual_fs import get_virtual_fs
                vfs = get_virtual_fs()
            except Exception:
                return

        while True:
            await asyncio.sleep(interval)
            try:
                content = await vfs.read_file(self._vfs_path)
                current_hash = hashlib.md5(content.encode()).hexdigest()
                if current_hash != self._last_hash:
                    self._last_hash = current_hash
                    html = self._render_preview(content)
                    # Write preview
                    Path(self._output_path).write_text(html, encoding="utf-8")
                    # Notify callbacks
                    for cb in self._callbacks:
                        try:
                            await cb(html) if asyncio.iscoroutinefunction(cb) else cb(html)
                        except Exception:
                            pass
            except Exception:
                pass

    def on_change(self, callback: callable):
        self._callbacks.append(callback)

    @staticmethod
    def _render_preview(markdown: str) -> str:
        """Render markdown to HTML preview."""
        # Simple markdown→HTML for preview
        html = markdown
        # Headers
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        # Bold
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        # Tables (simple)
        html = re.sub(r'\|(.+)\|', lambda m: '<tr>' + ''.join(
            f'<td>{c.strip()}</td>' for c in m.group(1).split('|') if c.strip()
        ) + '</tr>', html)
        # Paragraphs
        html = re.sub(r'\n\n', '<br><br>', html)

        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>body{{font-family:system-ui;max-width:800px;margin:40px auto;padding:0 20px;line-height:1.8}}
h1{{border-bottom:2px solid #333}}h2{{border-bottom:1px solid #ccc}}table{{border-collapse:collapse;width:100%}}
td{{border:1px solid #ddd;padding:8px}}</style></head>
<body>{html}</body></html>"""


# ═══ 4. Document Review (like PR review) ═══════════════════════════

@dataclass
class ReviewComment:
    """A review comment on a document section."""
    file: str
    line: int
    severity: str       # blocker | major | minor | suggestion
    category: str       # accuracy | completeness | style | consistency | data
    comment: str
    suggestion: str = ""
    author: str = "auto"
    resolved: bool = False


class DocumentReviewer:
    """Automated document review with diff, comment, and approval.

    Like PR review but for documents: shows what changed, flags issues.
    """

    @classmethod
    def review(cls, content: str, template_type: str = "",
               previous_version: str = "",
               content_graph=None) -> dict:
        """Review a document and generate comments."""
        comments: list[ReviewComment] = []

        # Diff against previous version
        if previous_version:
            diff = list(difflib.unified_diff(
                previous_version.splitlines(keepends=True),
                content.splitlines(keepends=True),
            ))
            changed_lines = [i for i, l in enumerate(diff) if l.startswith('+')]
            if len(changed_lines) > 20:
                comments.append(ReviewComment(
                    file="document", line=0, severity="minor",
                    category="style",
                    comment=f"大量变更 ({len(changed_lines)} 行)，建议分多次提交",
                ))

        # Structural checks
        lines = content.split('\n')
        headings = [l for l in lines if l.startswith('#')]
        if not headings:
            comments.append(ReviewComment(
                file="document", line=0, severity="blocker",
                category="completeness", comment="文档缺少章节标题",
                suggestion="添加至少一个 # 一级标题",
            ))

        # Check heading hierarchy
        prev_level = 0
        for h in headings:
            level = len(h) - len(h.lstrip('#'))
            if level > prev_level + 1:
                comments.append(ReviewComment(
                    file="document", line=lines.index(h) + 1, severity="major",
                    category="style", comment=f"标题层级跳跃: {h.strip()}",
                    suggestion="标题层级应连续 (H1→H2→H3)",
                ))
            prev_level = level

        # Data consistency check via ContentGraph
        if content_graph:
            issues = content_graph.check_all()
            for issue in issues[:10]:
                comments.append(ReviewComment(
                    file=issue.files[0] if issue.files else "document",
                    line=0, severity="major" if issue.severity == "error" else "minor",
                    category="consistency",
                    comment=issue.description,
                    suggestion=issue.suggestion,
                ))

        # Count by severity
        blockers = sum(1 for c in comments if c.severity == "blocker")
        majors = sum(1 for c in comments if c.severity == "major")

        return {
            "total_comments": len(comments),
            "blockers": blockers,
            "majors": majors,
            "approved": blockers == 0,
            "comments": [{
                "file": c.file, "line": c.line, "severity": c.severity,
                "category": c.category, "comment": c.comment,
                "suggestion": c.suggestion,
            } for c in comments[:20]],
        }


# ═══ 5. Requirement Coverage (like code coverage) ═════════════════

class RequirementCoverage:
    """Check if document addresses all requirements (like test coverage)."""

    REQUIREMENTS = {
        "eia_report": [
            {"id": "R1", "desc": "项目概况与工程分析",
             "check": lambda t: "工程分析" in t or "项目概况" in t},
            {"id": "R2", "desc": "环境现状调查与评价",
             "check": lambda t: "环境现状" in t or "现状调查" in t},
            {"id": "R3", "desc": "大气环境影响预测",
             "check": lambda t: any(k in t for k in ("大气", "空气", "废气", "PM", "SO2", "NOx"))},
            {"id": "R4", "desc": "水环境影响预测",
             "check": lambda t: any(k in t for k in ("水环境", "地表水", "地下水", "BOD", "COD", "DO"))},
            {"id": "R5", "desc": "声环境影响预测",
             "check": lambda t: any(k in t for k in ("噪声", "声环境", "dB"))},
            {"id": "R6", "desc": "固体废物影响分析",
             "check": lambda t: any(k in t for k in ("固体废物", "固废", "生活垃圾", "危险废物"))},
            {"id": "R7", "desc": "生态环境影响",
             "check": lambda t: any(k in t for k in ("生态", "植被", "动物", "生物多样性"))},
            {"id": "R8", "desc": "环境风险评价",
             "check": lambda t: any(k in t for k in ("风险", "事故", "泄漏", "爆炸"))},
            {"id": "R9", "desc": "污染防治措施",
             "check": lambda t: any(k in t for k in ("防治", "措施", "治理", "减排"))},
            {"id": "R10", "desc": "环境经济损益分析",
             "check": lambda t: any(k in t for k in ("经济", "损益", "投资", "成本", "效益"))},
            {"id": "R11", "desc": "结论与建议",
             "check": lambda t: any(k in t for k in ("结论", "建议", "总结"))},
        ],
    }

    @classmethod
    def check(cls, content: str, template_type: str = "eia_report") -> dict:
        """Check requirement coverage."""
        requirements = cls.REQUIREMENTS.get(template_type, [])
        results = []

        for req in requirements:
            covered = req["check"](content)
            results.append({
                "id": req["id"],
                "description": req["desc"],
                "covered": covered,
            })

        covered_count = sum(1 for r in results if r["covered"])
        return {
            "template": template_type,
            "total_requirements": len(requirements),
            "covered": covered_count,
            "coverage_pct": round(covered_count / max(len(requirements), 1) * 100),
            "uncovered": [r for r in results if not r["covered"]],
            "all_results": results,
        }


# ═══ 6. Document Schema (like OpenAPI) ═════════════════════════════

class DocumentSchema:
    """Define and validate document structure (like OpenAPI for APIs)."""

    SCHEMAS = {
        "eia_report": {
            "version": "1.0",
            "required_sections": [
                "总论", "工程分析", "环境影响预测与评价", "结论",
            ],
            "required_metadata": ["project_name", "assessment_date", "prepared_by"],
            "max_sections": 20,
            "min_chars_per_section": 100,
            "data_requirements": {
                "大气": ["emission_rate", "wind_speed", "stack_height"],
                "水": ["bod_initial", "do_initial", "flow_velocity"],
                "噪声": ["source_level"],
            },
        },
    }

    @classmethod
    def validate(cls, content: str, schema_name: str = "eia_report") -> dict:
        """Validate document against schema."""
        schema = cls.SCHEMAS.get(schema_name, {})
        errors = []
        warnings = []

        # Check required sections
        for section in schema.get("required_sections", []):
            if section not in content:
                errors.append(f"缺少必需章节: {section}")

        # Check required metadata
        for meta in schema.get("required_metadata", []):
            if meta not in content:
                warnings.append(f"缺少元数据: {meta}")

        # Check max sections
        sections = [l for l in content.split('\n') if l.startswith('##')]
        max_sections = schema.get("max_sections", 999)
        if len(sections) > max_sections:
            warnings.append(f"章节过多 ({len(sections)} > {max_sections})")

        # Check data requirements
        data_check = {}
        for category, required_data in schema.get("data_requirements", {}).items():
            available = [d for d in required_data if d in content.lower()]
            data_check[category] = {
                "required": len(required_data),
                "available": len(available),
                "missing": [d for d in required_data if d not in available],
            }

        return {
            "schema": schema_name,
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "data_check": data_check,
        }


# ═══ Singleton ════════════════════════════════════════════════════

__all__ = [
    "SectionSuggester", "SectionSuggestion",
    "EntityRenamer",
    "LivePreview",
    "DocumentReviewer", "ReviewComment",
    "RequirementCoverage",
    "DocumentSchema",
]
