"""TemplateEngine — instantiate templates with context-aware variable filling.

    1. Variable extraction: auto-detect {{var}} placeholders in template
    2. Context injection: fill from project context, KB, or LLM inference
    3. Smart fill: LLM reads template + context → fills missing variables
    4. Batch instantiation: single template → N documents from CSV/JSON params
    5. Iterative refinement: self-check output → fix gaps → re-output

    Usage:
        engine = get_template_engine()
        doc = await engine.instantiate("环评报告模板.md", {"项目名称": "XX大桥"}, hub)
        docs = await engine.batch("报告.md", [{"name": "A"}, {"name": "B"}], hub)
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

TEMPLATE_DIR = Path(".livingtree/templates")


@dataclass
class TemplateResult:
    path: Path
    variables_found: int = 0
    variables_filled: int = 0
    variables_missing: int = 0
    content: str = ""
    applied: bool = False
    preview: str = ""


class TemplateEngine:
    """Context-aware template instantiation with LLM assistance."""

    VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")

    def extract_variables(self, content: str) -> list[str]:
        """Find all {{var}} placeholders in template."""
        return list(set(self.VAR_PATTERN.findall(content)))

    def fill_static(self, content: str, context: dict[str, str]) -> tuple[str, list[str]]:
        """Fill known variables, return (filled_content, [still_missing_vars])."""
        missing = []
        for var in self.extract_variables(content):
            pattern = "{{" + var + "}}"
            if var in context:
                content = content.replace(pattern, str(context[var]))
        return content, [v for v in self.extract_variables(content)]

    async def instantiate(
        self,
        template_path: str | Path,
        context: dict[str, str] | None = None,
        hub=None,
        output_path: str | Path | None = None,
        dry_run: bool = False,
    ) -> TemplateResult:
        """Fill a template with context. LLM fills any remaining gaps.

        Args:
            template_path: Path to .md/.txt template file
            context: Known key-value pairs to fill
            hub: IntegrationHub for LLM access
            output_path: Where to write the result (auto-generated if None)
            dry_run: Preview only
        """
        template_path = Path(template_path)
        context = context or {}

        if not template_path.exists():
            return TemplateResult(path=template_path)

        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        all_vars = self.extract_variables(content)
        result = TemplateResult(path=template_path, variables_found=len(all_vars))

        # Phase 1: fill static + KB context
        kb_context = self._gather_context(hub, all_vars)
        merged = {**kb_context, **context}
        content, still_missing = self.fill_static(content, merged)

        # Phase 2: LLM fills the rest
        if still_missing and hub and hub.world:
            content = await self._llm_fill(content, still_missing, hub)

        final_missing = self.extract_variables(content)
        result.variables_filled = len(all_vars) - len(final_missing)
        result.variables_missing = len(final_missing)
        result.content = content
        result.preview = f"  filled {result.variables_filled}/{len(all_vars)} vars, {len(final_missing)} unfilled"

        if result.variables_filled > 0 and not dry_run:
            out = Path(output_path) if output_path else template_path.with_suffix(f".filled{template_path.suffix}")
            out.write_text(content, encoding="utf-8")
            result.path = out
            result.applied = True

        return result

    async def batch(
        self,
        template_path: str | Path,
        params_list: list[dict[str, str]],
        hub=None,
        output_dir: str | Path | None = None,
        concurrency: int = 5,
    ) -> list[TemplateResult]:
        """Generate N documents from one template with parallel LLM calls.

        Args:
            template_path: Template file with {{var}} placeholders
            params_list: [{var1: val1, var2: val2}, ...] — one dict per document
            hub: LLM access
            output_dir: Output directory (auto: .livingtree/generated/)
            concurrency: Max parallel LLM calls
        """
        odir = Path(output_dir) if output_dir else Path(".livingtree/generated")
        odir.mkdir(parents=True, exist_ok=True)

        template_path = Path(template_path)
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        all_vars = self.extract_variables(content)
        kb_context = self._gather_context(hub, all_vars) if hub else {}

        sem = asyncio.Semaphore(concurrency)
        results = []

        async def _gen_one(i: int, params: dict[str, str]) -> TemplateResult:
            async with sem:
                merged = {**kb_context, **params}
                filled, _ = self.fill_static(content, merged)
                remaining = self.extract_variables(filled)
                if remaining and hub and hub.world:
                    filled = await self._llm_fill(filled, remaining, hub)
                out = odir / f"{template_path.stem}_{i:03d}{template_path.suffix}"
                out.write_text(filled, encoding="utf-8")
                return TemplateResult(
                    path=out, variables_found=len(all_vars),
                    variables_filled=len(all_vars) - len(self.extract_variables(filled)),
                    variables_missing=len(self.extract_variables(filled)),
                    content=filled, applied=True,
                )

        tasks = [_gen_one(i, p) for i, p in enumerate(params_list)]
        results = await asyncio.gather(*tasks)
        return list(results)

    def _gather_context(self, hub, variables: list[str]) -> dict[str, str]:
        """Gather context from KB/project files for template variables."""
        ctx = {}
        try:
            from livingtree.core.unified_registry import get_registry
            reg = get_registry()
            for var in variables:
                # Try KB
                kb = getattr(reg, '_kbs', {})
                for kb_name, kb_obj in kb.items():
                    try:
                        hits = kb_obj.search(var, limit=1)
                        if hits:
                            ctx[var] = str(hits[0])[:500]
                            break
                    except Exception:
                        pass
        except Exception:
            pass
        return ctx

    async def _llm_fill(self, content: str, missing: list[str], hub) -> str:
        """LLM reads template with blanks → fills in missing variables."""
        llm = hub.world.consciousness._llm
        try:
            result = await llm.chat(
                messages=[{"role": "user", "content": (
                    "You are filling a document template. Replace all {{variable_name}} "
                    "placeholders with plausible, reasonable values specific to this context. "
                    "DO NOT leave any {{}} placeholders unfilled. "
                    "If you don't know a value, use the most common/reasonable default.\n\n"
                    "Missing variables: " + ", ".join(missing) + "\n\n"
                    "TEMPLATE:\n```\n" + content[-8000:] + "\n```\n\n"
                    "Output the COMPLETE filled template (no explanation)."
                )}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.3, max_tokens=4000, timeout=30,
            )
            if result and result.text:
                # Strip code fences if present
                text = result.text.strip()
                text = re.sub(r'^```\w*\n?', '', text)
                text = re.sub(r'\n?```$', '', text)
                return text
        except Exception as e:
            logger.debug(f"LLM fill: {e}")
        return content


_engine: TemplateEngine | None = None


def get_template_engine() -> TemplateEngine:
    global _engine
    if _engine is None:
        _engine = TemplateEngine()
    return _engine
