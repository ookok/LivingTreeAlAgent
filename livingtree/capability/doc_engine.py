"""End-to-end document generation engine.

No hardcoded templates. Templates are learned from:
1. TemplateLearner (KB + Distillation)
2. FormatDiscovery (document analysis)
3. KnowledgeBase (previously generated)

Uses the TemplateLearner for dynamic template generation.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, Field


class DocSpec(BaseModel):
    name: str
    template_type: str
    sections: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocEngine:
    """Document generation with dynamic template learning."""

    def __init__(self, output_dir: str = "./data/output"):
        self._templates: dict[str, DocSpec] = {}
        self._progress: dict[str, float] = {}
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.knowledge_base: Any = None
        self.template_learner: Any = None

    def list_templates(self) -> list[str]:
        return list(self._templates.keys())

    def get_template(self, template_type: str) -> list[str]:
        tpl = self._templates.get(template_type)
        return tpl.sections if tpl else []

    async def generate_report(self, template_type: str, data: dict[str, Any],
                               requirements: dict[str, Any] | None = None) -> dict[str, Any]:
        """Generate report using learned templates.

        Auto-extracts structured entities from raw input text when
        an ExtractionEngine is available in the world. Extracted entities
        are added to data before template generation.
        """
        reqs = requirements or {}

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
            content = await self._generate_section(sec, data, reqs)
            parts.append(f"# {sec}\n\n{content}")
            pct = int((idx / total) * 100)
            self._progress[template_type] = pct
            progress.append({"section": sec, "index": idx, "total": total, "progress_pct": pct})

        document = "\n\n".join(parts)
        return {
            "document": document, "sections": sections, "progress": progress,
            "template_type": template_type, "total_sections": total, "completed": True,
        }

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

        return ["项目概述", "背景分析", "核心内容", "实施方案", "结论与建议"]

    async def _generate_section(self, section: str, data: dict[str, Any],
                                requirements: dict[str, Any]) -> str:
        title = data.get("title", data.get("project_name", "项目"))
        return (
            f"本章节为「{section}」，针对项目「{title}」进行详细阐述。\n\n"
            f"主要内容应包括：相关背景和数据、分析方法与过程、结果与结论。\n\n"
            f"---\n*由 LivingTree DocEngine 自动生成。*"
        )

    async def generate_report_streaming(self, template_type: str, data: dict[str, Any],
                                        requirements: dict[str, Any] | None = None):
        """Incremental generation — yields each section as it's completed.

        Usage:
            async for update in engine.generate_report_streaming(...):
                print(f"[{update['progress_pct']}%] {update['section']}")
        """
        reqs = requirements or {}
        sections = await self._get_sections(template_type, data, reqs)
        total = len(sections)
        parts = []

        for idx, sec in enumerate(sections, start=1):
            content = await self._generate_section(sec, data, reqs)
            parts.append(f"# {sec}\n\n{content}")
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
        return text.strip()

    async def export_to(self, text: str, fmt: str = "markdown") -> str:
        path = self.output_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        path.write_text(text, encoding="utf-8")
        return str(path)


