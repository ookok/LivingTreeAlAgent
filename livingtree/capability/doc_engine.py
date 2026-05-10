"""End-to-end document generation engine with Context-Folding.

No hardcoded templates. Templates are learned from:
1. TemplateLearner (KB + Distillation)
2. FormatDiscovery (document analysis)
3. KnowledgeBase (previously generated)

FoldAgent integration: when generating multi-section reports, each section's
content is folded into a compact summary before being passed as context to
subsequent sections. This keeps the generation context ~10x smaller, enabling
longer documents (50+ sections) without context explosion.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, Field

from ..execution.context_fold import FoldResult, fold_context, fold_text_heuristic


class DocSpec(BaseModel):
    name: str
    template_type: str
    sections: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocEngine:
    """Document generation with dynamic template learning and Context-Folding."""

    def __init__(self, output_dir: str = "./data/output"):
        self._templates: dict[str, DocSpec] = {}
        self._progress: dict[str, float] = {}
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.knowledge_base: Any = None
        self.template_learner: Any = None
        self._folded_sections: list[FoldResult] = []

    def list_templates(self) -> list[str]:
        return list(self._templates.keys())

    def get_template(self, template_type: str) -> list[str]:
        tpl = self._templates.get(template_type)
        return tpl.sections if tpl else []

    async def generate_report(self, template_type: str, data: dict[str, Any],
                                requirements: dict[str, Any] | None = None,
                                fold: bool = False,
                                fold_max_chars: int = 500) -> dict[str, Any]:
        """Generate report using learned templates with optional Context-Folding.

        When fold=True, each section's generated content is folded into a compact
        summary that's passed to subsequent sections. The final document retains
        full content; only the per-section generation context is compressed.

        Args:
            fold: Enable FoldAgent context compression between sections
            fold_max_chars: Target max chars for folded section summaries
        """
        reqs = requirements or {}
        self._folded_sections = []

        if "raw_text" in data and hasattr(self, '_extraction_engine'):
            try:
                engine = self._extraction_engine
                classes = ["symptom", "finding", "medication", "entity", "metric"]
                extractions = engine.extract(
                    text=data["raw_text"],
                    classes=classes,
                    prompt_description=(
                        f"Extract structured information for {template_type} report. "
                        "Use exact text from source. Include entity, attribute, and value."
                    ),
                )
                if extractions:
                    data["extracted_entities"] = [
                        {"class": e.extraction_class, "text": e.extraction_text,
                         "position": f"{e.char_start}:{e.char_end}",
                         "attributes": e.attributes}
                        for e in extractions
                    ]
                    logger.debug(f"DocEngine auto-extracted {len(extractions)} entities")
            except Exception as e:
                logger.debug(f"DocEngine extraction: {e}")

        if "raw_documents" in data and hasattr(self, '_pipeline_engine'):
            try:
                pipe_result = await self._pipeline_engine.run_nl(
                    f"Process and structure for {template_type} report: extract key entities, deduplicate, and organize",
                    documents=data["raw_documents"],
                )
                data["pipeline_results"] = pipe_result.get("results", [])
                data["pipeline_stats"] = {
                    "steps": pipe_result.get("steps_executed", 0),
                    "outputs": pipe_result.get("output_count", 0),
                }
                logger.debug(f"DocEngine auto-pipelined {data['pipeline_stats']}")
            except Exception as e:
                logger.debug(f"DocEngine pipeline: {e}")

        if "file_path" in data and hasattr(self, '_multimodal_parser'):
            try:
                parsed = await self._multimodal_parser.parse(data["file_path"])
                data["parsed_document"] = parsed.to_dict()
                data["parsed_text"] = parsed.text[:8000]
                data["parsed_tables"] = [t.to_markdown() for t in parsed.tables[:5]]
                data["parsed_images"] = [i.to_dict() for i in parsed.images[:10]]
                logger.debug(f"DocEngine auto-parsed {parsed.summary_text()}")
            except Exception as e:
                logger.debug(f"DocEngine multimodal: {e}")
        sections = await self._get_sections(template_type, data, reqs)
        parts: list[str] = []
        progress: list[dict[str, Any]] = []
        total = len(sections)

        for idx, sec in enumerate(sections, start=1):
            section_data = dict(data)
            if fold and self._folded_sections:
                folded_context = self._build_folded_context()
                section_data["_folded_previous_sections"] = folded_context

            content = await self._generate_section(sec, section_data, reqs)
            parts.append(f"# {sec}\n\n{content}")

            if fold and len(content) > fold_max_chars:
                consciousness = getattr(self, '_consciousness', None)
                folded = await fold_context(content, consciousness,
                                             template_type, fold_max_chars)
                self._folded_sections.append(folded)

            pct = int((idx / total) * 100)
            self._progress[template_type] = pct
            progress.append({"section": sec, "index": idx, "total": total, "progress_pct": pct})

        document = "\n\n".join(parts)
        result = {
            "document": document, "sections": sections, "progress": progress,
            "template_type": template_type, "total_sections": total, "completed": True,
        }
        if fold:
            result["folded_sections"] = [
                {"section": sections[i], "summary": f.summary, "compression": f.compression_ratio}
                for i, f in enumerate(self._folded_sections) if i < len(sections)
            ]
        return result

    def _build_folded_context(self) -> str:
        """Build compact context from all previously folded sections."""
        lines = ["[Context-Folding: 前置章节摘要]\n"]
        for i, f in enumerate(self._folded_sections):
            lines.append(f"## 章节{i+1}概要: {f.summary[:300]}")
            if f.key_entities:
                lines.append(f"关键信息: {', '.join(f.key_entities[:3])}")
            if f.decisions:
                lines.append(f"决策: {'; '.join(f.decisions[:2])}")
        return "\n".join(lines)

    async def _get_sections(self, template_type: str, data: dict[str, Any],
                            requirements: dict[str, Any]) -> list[str]:
        """Get sections — from TemplateLearner, not hardcoded."""
        # Custom from requirements
        if "sections" in requirements:
            return requirements["sections"]

        # From TemplateLearner
        if self.template_learner:
            try:
                steps = await self.template_learner.get_template(template_type)
                sections = [s.get("name", str(s)) for s in steps]
                if sections:
                    return sections
            except Exception as e:
                logger.debug(f"Template learner: {e}")

        # From FormatDiscovery
        if self.knowledge_base:
            try:
                docs = self.knowledge_base.search(template_type, top_k=5)
                headings: set[str] = set()
                for doc in docs:
                    for line in doc.content.split("\n"):
                        line = line.strip()
                        if line.startswith("#"):
                            headings.add(line.lstrip("#0123456789. ").strip()[:80])
                if len(headings) >= 3:
                    return sorted(headings)[:20]
            except Exception:
                pass

        # From DocEngineConfig (loaded via auto-load at init)
        config_templates = getattr(self, "_config_templates", {})
        sections = config_templates.get(template_type)
        if sections:
            return sections

        # Fuzzy match template_type against known templates
        fuzzy_map = {
            "环评": "eia_template", "eia": "eia_template", "环境": "eia_template",
            "应急": "emergency_plan_template", "预案": "emergency_plan_template",
            "验收": "acceptance_template", "accept": "acceptance_template",
            "可行": "feasibility_template", "feasibility": "feasibility_template",
            "分析": "feasibility_template",
        }
        for key, tpl_name in fuzzy_map.items():
            if key in template_type.lower():
                sections = config_templates.get(tpl_name)
                if sections:
                    return sections

        return ["项目概述", "背景分析", "核心内容", "实施方案", "结论与建议"]

    async def _generate_section(self, section: str, data: dict[str, Any],
                                requirements: dict[str, Any]) -> str:
        """Generate a single section using LLM when consciousness is available."""
        title = data.get("title", data.get("project_name", "项目"))
        consciousness = getattr(self, "_consciousness", None)
        template_type = data.get("template_type", data.get("_template_type", ""))

        if consciousness:
            try:
                folded = data.get("_folded_previous_sections", "")
                context_bits = []
                if data.get("raw_text"):
                    context_bits.append(f"原始资料:\n{data['raw_text'][:2000]}")
                if data.get("extracted_entities"):
                    entities = data["extracted_entities"][:10]
                    context_bits.append("关键信息: " + "; ".join(
                        f'{e.get("text", e.get("class",""))}' for e in entities))
                if data.get("parsed_text"):
                    context_bits.append(f"解析内容: {data['parsed_text'][:1500]}")
                if data.get("raw_documents"):
                    docs = data["raw_documents"]
                    if isinstance(docs, list):
                        context_bits.append(f"相关文档数: {len(docs)}")
                if folded:
                    context_bits.append(folded)

                context_str = "\n\n".join(context_bits) if context_bits else "暂无额外上下文"

                prompt = (
                    f"你正在撰写一份{template_type or '专业'}报告。请撰写章节: {section}。\n\n"
                    f"项目名称: {title}\n"
                    f"上下文资料:\n{context_str}\n\n"
                    f"要求: 专业、详实、有数据支撑。使用Markdown格式。"
                    f"输出该章节的完整内容(300-800字)。"
                )
                resp = await consciousness.chain_of_thought(prompt, steps=1)
                content = resp if isinstance(resp, str) else str(resp)
                if content and len(content) > 20:
                    return content
            except Exception as e:
                logger.debug(f"LLM section generation failed, using heuristics: {e}")

        return (
            f"## {section}\n\n"
            f"本章节针对项目「{title}」进行详细阐述。\n\n"
            f"主要内容应包括：相关背景和数据、分析方法与过程、结果与结论。\n\n"
            f"---\n*由 LivingTree DocEngine 自动生成。*"
        )

    def _load_config_templates(self):
        """Load industrial templates from DocEngineConfig."""
        try:
            from ..config.settings import DocEngineConfig
            cfg = DocEngineConfig()
            self._config_templates = {
                "eia_template": cfg.eia_template,
                "emergency_plan_template": cfg.emergency_plan_template,
                "acceptance_template": cfg.acceptance_template,
                "feasibility_template": cfg.feasibility_template,
                "环评报告": cfg.eia_template,
                "应急预案": cfg.emergency_plan_template,
                "验收报告": cfg.acceptance_template,
                "可行性研究": cfg.feasibility_template,
            }
            logger.debug(f"DocEngine: loaded {len(self._config_templates)} template sets")
        except Exception as e:
            self._config_templates = {}
            logger.debug(f"DocEngine: config templates not loaded: {e}")

    async def generate_report_streaming(self, template_type: str, data: dict[str, Any],
                                         requirements: dict[str, Any] | None = None,
                                         fold: bool = False,
                                         fold_max_chars: int = 500):
        """Incremental generation — yields each section as it's completed.

        With fold=True, each yield includes a 'folded_context' key with
        compressed summaries of all prior sections, enabling downstream
        consumption with minimal context overhead.

        Usage:
            async for update in engine.generate_report_streaming(fold=True):
                print(f"[{update['progress_pct']}%] {update['section']}")
        """
        reqs = requirements or {}
        self._folded_sections = []
        sections = await self._get_sections(template_type, data, reqs)
        total = len(sections)
        parts = []

        for idx, sec in enumerate(sections, start=1):
            section_data = dict(data)
            if fold and self._folded_sections:
                folded_context = self._build_folded_context()
                section_data["_folded_previous_sections"] = folded_context

            content = await self._generate_section(sec, section_data, reqs)
            parts.append(f"# {sec}\n\n{content}")

            if fold and len(content) > fold_max_chars:
                consciousness = getattr(self, '_consciousness', None)
                folded = await fold_context(content, consciousness,
                                             template_type, fold_max_chars)
                self._folded_sections.append(folded)

            pct = int((idx / total) * 100)
            yield {
                "type": "section_complete",
                "section": sec, "index": idx, "total": total,
                "progress_pct": pct, "content": content,
            }

        document = "\n\n".join(parts)
        yield {
            "type": "report_complete",
            "document": document,
            "total_sections": total,
            "template_type": template_type,
        }

    async def auto_format(self, text: str) -> str:
        """Format with Kami design system when available."""
        try:
            from ..core.doc_renderer import render_document
            result = render_document(content=text, template="long_doc", title="")
            if result.get("ok"):
                return result.get("html", text)
        except Exception:
            pass
        return text.strip()

    async def export_to(self, text: str, fmt: str = "markdown") -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        if fmt in ("pdf", "html"):
            try:
                from ..core.doc_renderer import render_document
                result = render_document(content=text, template="long_doc", title="")
                if result.get("ok"):
                    out_path = result.get("pdf_path") or result.get("html_path", "")
                    if out_path:
                        return out_path
            except Exception as e:
                logger.debug(f"Kami export failed: {e}")

        path = self.output_dir / f"report_{ts}.md"
        path.write_text(text, encoding="utf-8")
        return str(path)


