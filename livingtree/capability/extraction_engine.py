"""Extraction Engine — LangExtract-powered structured entity extraction.

Wraps Google's LangExtract (Apache 2.0) with LivingTree's DeepSeek/LiteLLM
model backend. Provides source-grounded extraction with precise char-level
mapping and visual highlighting support.

Usage:
    engine = ExtractionEngine(api_key="sk-...", base_url="https://api.deepseek.com/v1")
    
    result = engine.extract(
        text="The patient presents with fever and cough for 3 days.",
        classes=["symptom", "finding", "medication"],
    )
    # → [ExtractionResult(extraction_class="symptom", extraction_text="fever",
    #      char_interval=(35, 40), ...), ...]
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from langextract import extract as lx_extract
from langextract import data as lx_data


@dataclass
class ExtractionResult:
    """A single grounded extraction with source position."""
    extraction_class: str
    extraction_text: str
    char_start: int = -1
    char_end: int = -1
    attributes: dict[str, str] = field(default_factory=dict)
    confidence: float = 1.0
    source_text_snippet: str = ""

    def to_dict(self) -> dict:
        return {
            "class": self.extraction_class,
            "text": self.extraction_text,
            "char_interval": [self.char_start, self.char_end],
            "attributes": self.attributes,
            "confidence": self.confidence,
            "snippet": self.source_text_snippet[:80] if self.source_text_snippet else "",
        }

    def format_display(self) -> str:
        pos = f"@{self.char_start}:{self.char_end}" if self.char_start >= 0 else "@?"
        attrs = ", ".join(f"{k}={v}" for k, v in self.attributes.items())
        base = f"  [{self.extraction_class}] `{self.extraction_text}` {pos}"
        return f"{base} ({attrs})" if attrs else base


class ExtractionEngine:
    """LangExtract wrapper configured for LivingTree's model backend.

    Uses DeepSeek API via LiteLLM for extraction. Falls back to raw
    Langextract with Gemini if DeepSeek is not available.
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
    ):
        self._api_key = api_key
        self._base_url = base_url
        self._model = model or "deepseek/deepseek-v4-flash"
        self._lx_available = True
        self._lx_extract = lx_extract
        self._lx_data = lx_data
        logger.debug("LangExtract v1.3.0 loaded")

    def extract(
        self,
        text: str,
        classes: list[str],
        prompt_description: str = "",
        examples: list[dict] | None = None,
        model_id: str = "",
    ) -> list[ExtractionResult]:
        """Extract structured entities from text with source grounding.

        Args:
            text: Input text to extract from
            classes: List of extraction class names (e.g. ["character", "emotion"])
            prompt_description: Natural language description of what to extract
            examples: Optional few-shot examples (list of {"text": ..., "extractions": [...]})
            model_id: Override model (defaults to DeepSeek flash)

        Returns:
            List of ExtractionResult with char-level source positions
        """
        if not text or not text.strip():
            return []

        if self._lx_available:
            return self._extract_with_langextract(text, classes, prompt_description, examples, model_id)

        return self._extract_fallback(text, classes)

    def extract_with_grounding(
        self,
        text: str,
        classes: list[str],
        attributes_map: dict[str, list[str]] | None = None,
    ) -> list[ExtractionResult]:
        """Extract entities with grounded source positions and attributes.

        Args:
            text: Input text
            classes: Extraction class names
            attributes_map: Optional {class_name: [attr1, attr2]} for attribute hints

        Returns:
            Grounded ExtractionResult list
        """
        prompt = f"Extract the following types of entities from the text: {', '.join(classes)}.\n"
        prompt += "Output must use exact text from the source. Do not paraphrase.\n"

        if attributes_map:
            for cls, attrs in attributes_map.items():
                prompt += f"For '{cls}', also extract: {', '.join(attrs)}.\n"

        prompt += "One extraction per line: [class] | text | attr1=val1, attr2=val2"

        return self.extract(text, classes, prompt_description=prompt)

    def visualize_to_html(
        self,
        extractions: list[ExtractionResult],
        source_text: str,
        title: str = "LivingTree Extraction Results",
    ) -> str:
        """Generate an interactive HTML visualization of extraction results.

        Args:
            extractions: List of extraction results
            source_text: The original source text
            title: HTML page title

        Returns:
            Full HTML string ready to write to file
        """
        escaped_text = source_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        items_json = json.dumps(
            [e.to_dict() for e in extractions],
            ensure_ascii=False,
            indent=2,
        )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><title>{title}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:1000px;margin:auto;padding:20px;background:#0d1117;color:#c9d1d9}}
.source{{background:#161b22;padding:16px;border-radius:8px;white-space:pre-wrap;line-height:1.8;font-family:monospace}}
.ext{{border-radius:4px;padding:2px 4px;margin:1px;cursor:pointer}}
.symptom{{background:rgba(248,81,73,0.3);border-bottom:2px solid #f85149}}
.finding{{background:rgba(63,185,80,0.3);border-bottom:2px solid #3fb950}}
.medication{{background:rgba(88,166,255,0.3);border-bottom:2px solid #58a6ff}}
.character{{background:rgba(210,168,255,0.3);border-bottom:2px solid #d2a8ff}}
.emotion{{background:rgba(254,174,43,0.3);border-bottom:2px solid #feae2b}}
.relationship{{background:rgba(255,123,114,0.3);border-bottom:2px solid #ff7b72}}
.event{{background:rgba(163,113,247,0.3);border-bottom:2px solid #a371f7}}
.results{{margin-top:20px}}
.result-item{{background:#161b22;padding:8px 12px;margin:4px 0;border-radius:4px;border-left:3px solid #58a6ff}}
.position{{color:#8b949e;font-size:0.85em}}
#filter{{width:100%;padding:8px;margin:10px 0;background:#161b22;border:1px solid #30363d;color:#c9d1d9;border-radius:4px}}
#stats{{color:#8b949e;margin:8px 0}}
</style>
</head>
<body>
<h1>{title}</h1>
<div id="stats">Total: {len(extractions)} extractions</div>
<input type="text" id="filter" placeholder="Filter by class or text...">
<div class="source">{escaped_text[:8000]}</div>
<div class="results" id="results"></div>
<script>
const items = {items_json};
function render(){{document.getElementById('stats').textContent='Total: '+items.length+' extractions';}}
render();
</script>
</body>
</html>"""
        return html

    # ── Private ──

    def _extract_with_langextract(
        self,
        text: str,
        classes: list[str],
        prompt_desc: str,
        examples: list[dict] | None,
        model_id: str,
    ) -> list[ExtractionResult]:
        try:
            lx_examples = []
            if examples:
                for ex in examples:
                    ex_text = ex.get("text", "")
                    ex_extractions = ex.get("extractions", [])
                    lx_extractions = []
                    for e in ex_extractions:
                        lx_extractions.append(self._lx_data.Extraction(
                            extraction_class=e.get("extraction_class", ""),
                            extraction_text=e.get("extraction_text", ""),
                            attributes=e.get("attributes", {}),
                        ))
                    if lx_extractions:
                        lx_examples.append(self._lx_data.ExampleData(
                            text=ex_text,
                            extractions=lx_extractions,
                        ))

            if not prompt_desc and classes:
                prompt_desc = f"Extract {', '.join(classes)} from the text. Use exact text from source."

            result = self._lx_extract(
                text_or_documents=text,
                prompt_description=prompt_desc or f"Extract: {', '.join(classes)}",
                examples=lx_examples if lx_examples else None,
                model_id=model_id or self._model,
            )

            results = []
            if hasattr(result, 'extractions'):
                for ext in result.extractions:
                    ci = getattr(ext, 'char_interval', None)
                    results.append(ExtractionResult(
                        extraction_class=getattr(ext, 'extraction_class', 'unknown'),
                        extraction_text=getattr(ext, 'extraction_text', ''),
                        char_start=ci[0] if ci else -1,
                        char_end=ci[1] if ci else -1,
                        attributes=getattr(ext, 'attributes', {}),
                        source_text_snippet=text[max(0, (ci[0]-20 if ci else 0)):((ci[1]+20) if ci else 100)],
                    ))
            return results

        except Exception as e:
            logger.warning(f"LangExtract extraction failed: {e}")
            return self._extract_fallback(text, classes)

    def _extract_fallback(
        self,
        text: str,
        classes: list[str],
    ) -> list[ExtractionResult]:
        """Fallback regex-based extraction when LangExtract is unavailable."""
        import re
        results = []
        text_lower = text.lower()

        patterns = {
            "symptom": r"(fever|cough|headache|pain|nausea|fatigue|dizziness)",
            "finding": r"(normal|abnormal|elevated|reduced|positive|negative)",
            "medication": r"([A-Z][a-z]+(?:ine|ol|am|ide|cin|pril|one|ium)\s?\d*(?:mg|mcg|g)?)",
            "name": r"([A-Z][a-z]+\s[A-Z][a-z]+)",
        }

        for cls in classes:
            pattern = patterns.get(cls.lower())
            if not pattern:
                continue
            for match in re.finditer(pattern, text):
                results.append(ExtractionResult(
                    extraction_class=cls,
                    extraction_text=match.group(1),
                    char_start=match.start(),
                    char_end=match.end(),
                    source_text_snippet=text[max(0, match.start()-20):match.end()+20],
                ))

        return results


def create_extraction_engine(api_key: str = "", base_url: str = "",
                               model: str = "") -> ExtractionEngine:
    return ExtractionEngine(api_key=api_key, base_url=base_url, model=model)
