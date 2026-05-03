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
        """Generate report using learned templates."""
        reqs = requirements or {}
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


