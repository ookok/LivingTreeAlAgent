"""ReportEnhancer — Professional document features: citations, data binding, docx pipeline.

Adds to DocEngine:
  1. CitationTracker: auto-number tables, figures, cross-references
  2. DataBinder: real-time data from CSV/JSON/DB sources
  3. FormatPipeline: native .docx output with inherited styles
  4. MultiLang: template-based localization support

Usage:
    from livingtree.capability.report_enhancer import ReportEnhancer
    enhancer = ReportEnhancer()
    doc = enhancer.generate("eia_report", data, format="docx", 
                           data_source="data/site_measurements.csv")
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ═══ 1. Citation Tracker — auto-number tables, figures, references ═══

class CitationTracker:
    """Auto-number and cross-reference tables, figures, and sections.

    Supports: 表1-1, 图2-3, 参见表3.2, 参考文献[1]
    GB/T 7714 and APA-style citation formatting.
    """

    def __init__(self):
        self._tables: dict[str, int] = {}
        self._figures: dict[str, int] = {}
        self._refs: list[str] = []
        self._chapter = 1

    def chapter(self, num: int) -> "CitationTracker":
        self._chapter = num
        return self

    def table(self, label: str) -> str:
        """Register a table. Returns formatted label like '表3-1'."""
        key = f"{self._chapter}"
        num = self._tables.get(key, 0) + 1
        self._tables[key] = num
        return f"表{self._chapter}-{num}"

    def figure(self, label: str) -> str:
        """Register a figure. Returns formatted label like '图2-3'."""
        key = f"{self._chapter}"
        num = self._figures.get(key, 0) + 1
        self._figures[key] = num
        return f"图{self._chapter}-{num}"

    def ref(self, citation: str, style: str = "gb7714") -> str:
        """Add a reference. Returns formatted citation number like '[1]'."""
        self._refs.append(citation)
        idx = len(self._refs)
        return f"[{idx}]" if style == "gb7714" else f"({idx})"

    def ref_list(self, style: str = "gb7714") -> str:
        """Generate formatted reference list."""
        lines = ["## 参考文献", ""]
        for i, ref in enumerate(self._refs, 1):
            lines.append(f"[{i}] {ref}")
        return "\n".join(lines)

    def cross_ref(self, target_type: str, chapter: int, num: int) -> str:
        """Cross-reference: '参见表3-2' or '如图1-1所示'."""
        prefixes = {"table": "表", "figure": "图", "section": "节"}
        prefix = prefixes.get(target_type, "")
        if target_type == "section":
            return f"参见{prefix}{chapter}.{num}节"
        return f"参见{prefix}{chapter}-{num}"

    def process_document(self, content: str) -> str:
        """Process document content, replacing citation placeholders with numbered references.

        Placeholders:
          {tbl:label} → 表1-1
          {fig:label} → 图1-2
          {ref:GB3095-2012} → [1]
        """
        def _replace_table(m):
            return self.table(m.group(1))
        def _replace_figure(m):
            return self.figure(m.group(1))
        def _replace_ref(m):
            return self.ref(m.group(1))

        content = re.sub(r'\{tbl:([^}]+)\}', _replace_table, content)
        content = re.sub(r'\{fig:([^}]+)\}', _replace_figure, content)
        content = re.sub(r'\{ref:([^}]+)\}', _replace_ref, content)
        return content


# ═══ 2. Data Binder — real-time data from CSV/JSON/DB/sensors ═══

class DataBinder:
    """Bind real-time data sources into report generation.

    Sources: CSV files, JSON APIs, SQLite databases, environment variables.
    """

    @staticmethod
    def from_csv(path: str, key_column: str = None) -> dict:
        """Load CSV as dict. If key_column, returns {key: row_dict} mapping."""
        data = {}
        try:
            with open(path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if key_column and key_column in (reader.fieldnames or []):
                    return {row[key_column]: dict(row) for row in rows}
                return {"rows": rows, "columns": reader.fieldnames or [], "count": len(rows)}
        except Exception as e:
            return {"error": str(e), "source": path}

    @staticmethod
    def from_json(path: str) -> dict:
        """Load JSON file as dict."""
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as e:
            return {"error": str(e), "source": path}

    @staticmethod
    def from_db(db_path: str, query: str) -> dict:
        """Execute SQL query and return results as dict."""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(query)
            columns = [d[0] for d in cursor.description] if cursor.description else []
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            conn.close()
            return {"rows": rows, "columns": columns, "count": len(rows)}
        except Exception as e:
            return {"error": str(e), "query": query}

    @staticmethod
    def from_api(url: str, headers: dict = None, method: str = "GET") -> dict:
        """Fetch data from REST API endpoint. Returns parsed JSON."""
        try:
            import urllib.request
            req = urllib.request.Request(url, headers=headers or {}, method=method)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return {"error": str(e), "url": url}

    @staticmethod
    def merge_sources(sources: list[dict]) -> dict:
        """Merge multiple data sources into one dict."""
        merged = {}
        for i, src in enumerate(sources):
            source_type = src.get("type", "inline")
            source_path = src.get("path", "") or src.get("url", "") or src.get("db", "")
            label = src.get("label", f"source_{i}")

            if source_type == "csv":
                merged[label] = DataBinder.from_csv(source_path, src.get("key_column"))
            elif source_type == "json":
                merged[label] = DataBinder.from_json(source_path)
            elif source_type == "db":
                merged[label] = DataBinder.from_db(source_path, src.get("query", "SELECT * FROM sqlite_master"))
            elif source_type == "api":
                merged[label] = DataBinder.from_api(source_path, src.get("headers"))
            elif source_type == "inline":
                merged[label] = src.get("data", {})

        return merged


# ═══ 3. Format Pipeline — native .docx output ═══

class FormatPipeline:
    """Bridge DocEngine to document_intelligence for native .docx generation.

    Integrates the existing document_intelligence._generate_docx() pipeline
    with DocEngine's template system for professional Word document output.
    """

    @staticmethod
    def export_docx(content: dict, template_name: str = "report",
                    output_path: str = "", citation_tracker: CitationTracker = None) -> str:
        """Generate a formatted .docx file from report content.

        Uses document_intelligence.DocumentIntelligence for native formatting:
        - Inherits styles from .docx templates (fonts, margins, headers)
        - Auto-generates Table of Contents
        - Page numbers and headers
        - Approval stamps and compliance markers
        - Table data with proper borders and formatting
        """
        try:
            from .document_intelligence import DocumentIntelligence
            di = DocumentIntelligence()

            params = {
                "title": content.get("title", template_name),
                "sections": content.get("sections", []),
                "tables": content.get("tables", []),
                "figures": content.get("figures", []),
                "metadata": content.get("metadata", {}),
                "timestamp": datetime.now().isoformat(),
            }

            if citation_tracker:
                params["references"] = citation_tracker._refs
                params["table_count"] = sum(citation_tracker._tables.values())
                params["figure_count"] = sum(citation_tracker._figures.values())

            result = di.generate(template=template_name, params=params,
                                output_path=output_path, format="docx")
            return result.output_path or output_path
        except ImportError:
            # Fallback: generate markdown
            return FormatPipeline._export_markdown(content, template_name, output_path)
        except Exception as e:
            logger.warning(f"FormatPipeline docx: {e}")
            return FormatPipeline._export_markdown(content, template_name, output_path)

    @staticmethod
    def _export_markdown(content: dict, template_name: str, output_path: str) -> str:
        """Fallback: generate markdown file."""
        out_path = Path(output_path or f"/tmp/{template_name}_{int(datetime.now().timestamp())}.md")
        lines = [f"# {content.get('title', template_name)}", ""]
        for section in content.get("sections", []):
            lines.append(f"## {section.get('heading', '')}")
            lines.append(section.get("body", ""))
            lines.append("")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(lines), encoding="utf-8")
        return str(out_path)

    @staticmethod
    def export_pdf(content: dict, template_name: str = "report",
                   output_path: str = "") -> str:
        """Generate PDF via markdown → HTML → WeasyPrint pipeline."""
        try:
            from ..core.doc_renderer import DocRenderer
            renderer = DocRenderer()
            markdown = FormatPipeline._export_markdown(content, template_name, "")
            result = renderer.render_document(
                Path(markdown).read_text(encoding="utf-8"),
                template="long_doc",
            )
            out_path = Path(output_path or f"/tmp/{template_name}.pdf")
            out_path.write_bytes(result.pdf_bytes if hasattr(result, 'pdf_bytes') else b"")
            return str(out_path)
        except Exception as e:
            logger.warning(f"FormatPipeline pdf: {e}")
            return FormatPipeline._export_markdown(content, template_name,
                        str(Path(output_path or "/tmp").with_suffix(".md")))


# ═══ 4. Multi-Language Support ═══

class MultiLangSupport:
    """Template-based localization for multi-language reports.

    Usage:
        mls = MultiLangSupport()
        mls.load_locale("zh-CN", "livingtree/locales/")
        title = mls.t("eia_report_title", lang="zh-CN")  # → "环境影响评价报告"
        title = mls.t("eia_report_title", lang="en")      # → "EIA Report"
    """

    _locales: dict[str, dict[str, str]] = {}
    _builtin: dict[str, dict[str, str]] = {
        "zh-CN": {
            "report_title": "环境影响评价报告",
            "table_of_contents": "目录",
            "chapter": "第{num}章",
            "section": "节",
            "table_caption": "表",
            "figure_caption": "图",
            "reference": "参考文献",
            "appendix": "附录",
            "approval": "审批",
            "prepared_by": "编制单位",
            "date": "日期",
            "page": "第{num}页",
        },
        "en": {
            "report_title": "Environmental Impact Assessment Report",
            "table_of_contents": "Table of Contents",
            "chapter": "Chapter {num}",
            "section": "Section",
            "table_caption": "Table",
            "figure_caption": "Figure",
            "reference": "References",
            "appendix": "Appendix",
            "approval": "Approval",
            "prepared_by": "Prepared by",
            "date": "Date",
            "page": "Page {num}",
        },
    }

    @classmethod
    def t(cls, key: str, lang: str = "zh-CN", **fmt) -> str:
        """Translate a key to the given language with optional formatting."""
        locale = cls._locales.get(lang, {}) or cls._builtin.get(lang, {})
        text = locale.get(key, key)
        if fmt:
            text = text.format(**fmt)
        return text

    @classmethod
    def load_locale(cls, lang: str, directory: str) -> int:
        """Load locale files from directory (e.g., locales/zh-CN.json)."""
        try:
            path = Path(directory) / f"{lang}.json"
            if path.exists():
                cls._locales[lang] = json.loads(path.read_text(encoding="utf-8"))
                return len(cls._locales[lang])
        except Exception:
            pass
        return 0

    @classmethod
    def available_languages(cls) -> list[str]:
        return sorted(set(list(cls._locales.keys()) + list(cls._builtin.keys())))


# ═══ 5. ReportEnhancer — unified entry point ═══

class ReportEnhancer:
    """Unified professional document generation with all enhancements.

    Bridges: EIA models → DocEngine → CitationTracker → FormatPipeline → .docx/PDF
    """

    def __init__(self):
        self.citations = CitationTracker()
        self._doc_engine = None

    def _get_engine(self):
        if self._doc_engine is None:
            from .doc_engine import DocEngine
            self._doc_engine = DocEngine()
        return self._doc_engine

    async def generate(self, template_type: str, data: dict,
                 format: str = "docx", output: str = "",
                 data_sources: list[dict] = None,
                 citations: bool = True, lang: str = "zh-CN") -> dict:
        """Generate a professional report with all enhancements.

        Args:
            template_type: 'eia_report', 'emergency_plan', 'feasibility', etc.
            data: Template variables and section content
            format: 'docx', 'pdf', 'markdown', 'html'
            output: Output file path
            data_sources: [{type:'csv', path:'data.csv'}, {type:'api', url:'...'}]
            citations: Enable auto-numbering of tables, figures, references
            lang: Report language ('zh-CN', 'en')

        Returns:
            {output_path, format, size, pages, citations_used}
        """
        # 1. Merge data sources
        merged_data = dict(data)
        if data_sources:
            merged_data["external_data"] = DataBinder.merge_sources(data_sources)

        # 2. Enrich with EIA physics models
        engine = self._get_engine()
        enriched = engine.enrich_with_eia_data(template_type, merged_data)

        # 3. Generate report content via DocEngine
        result = await engine.generate_report_with_models(template_type, enriched)

        # 4. Process citations
        if citations and result.get("sections"):
            for section in result["sections"]:
                if isinstance(section, dict) and "body" in section:
                    section["body"] = self.citations.process_document(
                        section.get("body", "")
                    )

        # 5. Inject multi-lang labels
        result["_lang"] = lang
        result["_labels"] = {
            "toc": MultiLangSupport.t("table_of_contents", lang),
            "refs": MultiLangSupport.t("reference", lang),
        }

        # 6. Output via FormatPipeline
        output_path = ""
        if format == "docx":
            output_path = FormatPipeline.export_docx(
                result, template_type, output, self.citations)
        elif format == "pdf":
            output_path = FormatPipeline.export_pdf(
                result, template_type, output)
        else:
            output_path = FormatPipeline._export_markdown(
                result, template_type, output)

        return {
            "output_path": output_path,
            "format": format,
            "size": Path(output_path).stat().st_size if Path(output_path).exists() else 0,
            "citations": {
                "tables": sum(self.citations._tables.values()),
                "figures": sum(self.citations._figures.values()),
                "references": len(self.citations._refs),
            },
            "models_used": list(enriched.keys()) if enriched else [],
            "sections": len(result.get("sections", [])),
        }


__all__ = [
    "CitationTracker", "DataBinder", "FormatPipeline",
    "MultiLangSupport", "ReportEnhancer",
]
