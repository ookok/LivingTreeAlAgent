"""Pipeline Engine — NL-driven operator pipeline with auto-generation.

Users describe what they want in natural language. The engine uses LLM
to auto-generate the optimal operator pipeline, then executes it.

Operators: map, filter, resolve, reduce, glean, sort, extract.

Usage:
    engine = PipelineEngine(consciousness, extraction_engine)
    
    result = await engine.run(
        "从100份环评报告中提取所有PM2.5指标，去重后按浓度从高到低排序"
    )
    # Auto-generates pipeline, executes it, returns structured results
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class PipelineStep:
    op: str
    prompt: str = ""
    condition: str = ""
    key: str = ""
    reverse: bool = False
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "op": self.op, "prompt": self.prompt, "condition": self.condition,
            "key": self.key, "reverse": self.reverse, "params": self.params,
        }


@dataclass
class PipelineConfig:
    name: str = ""
    description: str = ""
    input_type: str = "documents"
    steps: list[PipelineStep] = field(default_factory=list)

    def to_yaml_like(self) -> str:
        lines = [f"# {self.name}", f"# {self.description}", "pipeline:"]
        for i, s in enumerate(self.steps):
            lines.append(f"  - {s.op}:")
            if s.prompt:
                lines.append(f'      prompt: "{s.prompt[:80]}"')
            if s.condition:
                lines.append(f'      condition: "{s.condition[:60]}"')
            if s.key:
                lines.append(f'      key: {s.key}')
            if s.reverse:
                lines.append(f'      reverse: true')
        return "\n".join(lines)


PIPELINE_GEN_PROMPT = """You are a pipeline architect. Given a document processing task description in natural language, generate the optimal operator pipeline.

Available operators:
- extract: Structured entity extraction from text (classes: list of entity types)
- map: Apply LLM to each item (prompt: instruction)
- filter: Keep items matching condition (condition: boolean expression)
- resolve: Deduplicate/merge conflicting items (key: field to merge on)
- reduce: Aggregate/summarize (prompt: summary instruction)
- glean: Agentic refinement — retry with better prompt (prompt: enhanced instruction)
- sort: Sort by key (key: field name, reverse: true/false)

Rules:
1. Always start with extract or map
2. Always end with reduce or sort
3. Use resolve before reduce to clean duplicates
4. Extract/concrete tasks first, summarize last
5. Keep pipeline 3-7 steps

Input description: {description}

Output ONLY valid JSON:
{{"name":"short_name","description":"what this does","steps":[{{"op":"extract","classes":["class1"]}},{{"op":"map","prompt":"instruction"}},{{"op":"resolve","key":"field"}},{{"op":"sort","key":"field","reverse":false}}]}}"""


class PipelineEngine:
    """Auto-generates and executes operator pipelines from natural language."""

    def __init__(self, consciousness: Any = None, extraction_engine: Any = None):
        self._consciousness = consciousness
        self._extraction = extraction_engine

    async def generate(self, description: str) -> PipelineConfig:
        """Generate a pipeline from natural language description.

        Uses LLM (LongCat — free) to auto-generate optimal operator sequence.
        """
        if not description.strip():
            return PipelineConfig(name="empty", description="no description")

        steps = []
        name = "auto_pipeline"
        desc = description

        if self._consciousness:
            try:
                result = await self._consciousness.chain_of_thought(
                    PIPELINE_GEN_PROMPT.format(description=description[:2000]),
                    steps=1,
                    temperature=0.3,
                    max_tokens=1024,
                )
                json_text = result.strip()
                start, end = json_text.find("{"), json_text.rfind("}")
                if start >= 0 and end > start:
                    data = json.loads(json_text[start:end + 1])
                    name = data.get("name", name)
                    desc = data.get("description", desc)
                    for s in data.get("steps", []):
                        op = s.get("op", "map")
                        classes = s.get("classes", [])
                        prompt = s.get("prompt", "")

                        if classes and op == "extract":
                            steps.append(PipelineStep(
                                op="extract",
                                params={"classes": classes},
                            ))
                        elif op == "filter":
                            steps.append(PipelineStep(
                                op="filter",
                                condition=s.get("condition", ""),
                            ))
                        elif op == "resolve":
                            steps.append(PipelineStep(
                                op="resolve",
                                key=s.get("key", "text"),
                            ))
                        elif op == "reduce":
                            steps.append(PipelineStep(
                                op="reduce",
                                prompt=prompt or "Summarize the results",
                            ))
                        elif op == "sort":
                            steps.append(PipelineStep(
                                op="sort",
                                key=s.get("key", "text"),
                                reverse=s.get("reverse", False),
                            ))
                        elif op == "glean":
                            steps.append(PipelineStep(
                                op="glean",
                                prompt=prompt or "Refine and improve the results",
                            ))
                        else:
                            steps.append(PipelineStep(
                                op="map",
                                prompt=prompt or description,
                            ))
            except Exception as e:
                logger.debug(f"Pipeline auto-gen: {e}")

        if not steps:
            steps = self._fallback_pipeline(description)

        return PipelineConfig(name=name, description=desc, steps=steps)

    async def execute(
        self,
        config: PipelineConfig,
        documents: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute a pipeline config on input documents.

        Args:
            config: PipelineConfig with operator steps
            documents: List of document texts to process

        Returns:
            Dict with results, stats, and pipeline trace
        """
        docs = documents or []
        trace = []
        current = [{"text": d, "source": f"doc_{i}"} for i, d in enumerate(docs)]

        for step in config.steps:
            op = step.op
            entry = {"op": op, "input_count": len(current)}

            if op == "extract" and self._extraction:
                classes = step.params.get("classes", ["entity"])
                extracted = []
                for item in current:
                    text = item.get("text", "")
                    results = self._extraction.extract(text=text, classes=classes)
                    for r in results:
                        extracted.append({
                            "class": r.extraction_class,
                            "text": r.extraction_text,
                            "position": f"{r.char_start}:{r.char_end}",
                            "source": item.get("source", ""),
                            **r.attributes,
                        })
                current = extracted
                entry["output_count"] = len(current)

            elif op == "filter" and step.condition:
                cond = step.condition
                filtered = []
                for item in current:
                    try:
                        text_val = str(item.get("text", "")).lower()
                        cond_lower = cond.lower()
                        if ">" in cond_lower or "<" in cond_lower:
                            filtered.append(item)
                        elif "empty" in cond_lower and not text_val:
                            continue
                        elif "short" in cond_lower and len(text_val) < 10:
                            continue
                        else:
                            filtered.append(item)
                    except Exception:
                        filtered.append(item)
                current = filtered
                entry["output_count"] = len(current)

            elif op == "resolve":
                key = step.key or "text"
                seen = {}
                merged = []
                for item in current:
                    k = str(item.get(key, "")).strip().lower()
                    if k and k in seen:
                        merged[-1]["_merged_from"] = merged[-1].get("_merged_from", []) + [item.get("source", "")]
                    elif k:
                        seen[k] = True
                        merged.append(item)
                    else:
                        merged.append(item)
                current = merged
                entry["output_count"] = len(current)

            elif op == "sort":
                key = step.key or "text"
                try:
                    current.sort(
                        key=lambda x: str(x.get(key, "")).lower(),
                        reverse=step.reverse,
                    )
                except Exception:
                    pass
                entry["output_count"] = len(current)

            elif op == "reduce" and self._consciousness:
                text_items = [str(item.get("text", ""))[:500] for item in current[:20]]
                combined = "\n".join(text_items)
                summary = await self._consciousness.chain_of_thought(
                    f"{step.prompt or 'Summarize'}:\n\n{combined}",
                    steps=1,
                    temperature=0.5,
                    max_tokens=1024,
                )
                current = [{"text": summary, "source": "reduce", "input_items": len(current)}]
                entry["output_count"] = 1

            elif op == "glean" and self._consciousness:
                refined = []
                for item in current[:10]:
                    text = str(item.get("text", ""))[:1000]
                    improved = await self._consciousness.chain_of_thought(
                        f"{step.prompt or 'Refine and improve'}: {text}",
                        steps=1, temperature=0.5, max_tokens=512,
                    )
                    refined.append({**item, "text": improved or text, "_gleaned": True})
                current = refined
                entry["output_count"] = len(current)

            trace.append(entry)

        return {
            "pipeline": config.name,
            "description": config.description,
            "steps_executed": len(trace),
            "output_count": len(current),
            "results": current[:50],
            "trace": trace,
            "config_yaml": config.to_yaml_like(),
        }

    async def run_nl(
        self,
        description: str,
        documents: list[str] | None = None,
    ) -> dict[str, Any]:
        """Full pipeline: NL description → auto-generate → execute.

        Args:
            description: Natural language task description
            documents: Optional input documents

        Returns:
            Execution result dict with pipeline config
        """
        config = await self.generate(description)
        result = await self.execute(config, documents)
        result["generated_pipeline"] = {
            "name": config.name,
            "description": config.description,
            "steps": [s.to_dict() for s in config.steps],
        }
        return result

    def _fallback_pipeline(self, description: str) -> list[PipelineStep]:
        desc_lower = description.lower()

        if any(kw in desc_lower for kw in ["提取", "extract", "抽取"]):
            return [
                PipelineStep(op="extract", params={"classes": ["entity", "metric", "value"]}),
                PipelineStep(op="resolve", key="text"),
                PipelineStep(op="sort", key="text"),
            ]

        if any(kw in desc_lower for kw in ["去重", "合并", "merge", "dedup"]):
            return [
                PipelineStep(op="map", prompt=description),
                PipelineStep(op="resolve", key="text"),
                PipelineStep(op="reduce", prompt="Summarize deduplicated results"),
            ]

        return [
            PipelineStep(op="map", prompt=description),
            PipelineStep(op="reduce", prompt="Summarize the key findings"),
        ]
