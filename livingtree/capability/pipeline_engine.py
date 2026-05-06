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

sql-flow inspired Declarative DSL:
    pipeline = DeclarativePipeline.from_yaml("my_pipeline.yml")
    result = await DeclarativePipelineEngine.run(pipeline, input_data)
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import yaml
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from loguru import logger


# ══════════════════════════════════════════════════════════════════════
# sql-flow Pattern 1: Declarative Pipeline DSL
# ══════════════════════════════════════════════════════════════════════

class SinkType(str, Enum):
    """Output destinations mirroring sql-flow multi-sink architecture."""
    STDOUT = "stdout"
    MEMORY = "memory"
    KB = "knowledge_base"
    P2P = "p2p_broadcast"
    LOG = "log_file"
    KAFKA = "kafka"
    POSTGRES = "postgres"
    DISK = "disk"
    TUI = "tui"


class SourceType(str, Enum):
    """Input sources for declarative pipelines."""
    RAW = "raw_input"          # Direct user input
    KAFKA = "kafka"
    WEBSOCKET = "websocket"
    KB = "knowledge_base"      # Query existing knowledge
    MEMORY = "struct_memory"   # Query memory
    FILE = "file"
    P2P = "p2p_node"           # Incoming from peer node


class HandlerType(str, Enum):
    """Processing handler types for the transform stage."""
    LLM_TRANSFORM = "llm_transform"
    LLM_EXTRACT = "llm_extract"
    LLM_FILTER = "llm_filter"
    LLM_AGGREGATE = "llm_aggregate"
    RRF_FUSION = "rrf_fusion"
    CLEAN = "signal_clean"
    FORMAT = "format_rule"
    UDF = "udf"                # User-defined Python function
    ENRICH = "enrich"          # Join with external data source


@dataclass
class PipelineSource:
    """Declarative source: where data enters the pipeline."""
    type: SourceType = SourceType.RAW
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"type": self.type.value, "config": self.config}

    @classmethod
    def from_dict(cls, d: dict) -> "PipelineSource":
        return cls(type=SourceType(d.get("type", "raw_input")),
                   config=d.get("config", {}))


@dataclass
class PipelineHandler:
    """Declarative handler: a single transform step in the pipeline."""
    type: HandlerType
    prompt: str = ""
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    condition: str = ""        # SQL-like WHERE clause for filtering
    group_by: str = ""         # Aggregation key
    window: str = ""           # Tumbling window e.g. "5 minutes", "1 hour"
    config: dict[str, Any] = field(default_factory=dict)
    udf_name: str = ""         # Name of registered UDF to call
    enrich_source: str = ""    # External source for enrichment join

    def to_dict(self) -> dict:
        d = {"type": self.type.value}
        if self.prompt: d["prompt"] = self.prompt
        if self.model: d["model"] = self.model
        if self.temperature != 0.7: d["temperature"] = self.temperature
        if self.max_tokens != 4096: d["max_tokens"] = self.max_tokens
        if self.condition: d["condition"] = self.condition
        if self.group_by: d["group_by"] = self.group_by
        if self.window: d["window"] = self.window
        if self.config: d["config"] = self.config
        if self.udf_name: d["udf_name"] = self.udf_name
        if self.enrich_source: d["enrich_source"] = self.enrich_source
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "PipelineHandler":
        return cls(
            type=HandlerType(d.get("type", "llm_transform")),
            prompt=d.get("prompt", ""),
            model=d.get("model", ""),
            temperature=d.get("temperature", 0.7),
            max_tokens=d.get("max_tokens", 4096),
            condition=d.get("condition", ""),
            group_by=d.get("group_by", ""),
            window=d.get("window", ""),
            config=d.get("config", {}),
            udf_name=d.get("udf_name", ""),
            enrich_source=d.get("enrich_source", ""),
        )


@dataclass
class PipelineSink:
    """Declarative sink: where processed data goes."""
    type: SinkType = SinkType.MEMORY
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"type": self.type.value, "config": self.config}

    @classmethod
    def from_dict(cls, d: dict) -> "PipelineSink":
        return cls(type=SinkType(d.get("type", "memory")),
                   config=d.get("config", {}))


@dataclass
class DeclarativePipeline:
    """sql-flow-style declarative pipeline: source → handlers → sinks."""
    name: str = "unnamed"
    description: str = ""
    source: PipelineSource = field(default_factory=PipelineSource)
    setup: list[str] = field(default_factory=list)  # SQL/commands before pipeline
    handlers: list[PipelineHandler] = field(default_factory=list)
    sinks: list[PipelineSink] = field(default_factory=list)
    max_in_flight: int = 1000
    batch_size: int = 100

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "source": self.source.to_dict(),
            "setup": self.setup,
            "handlers": [h.to_dict() for h in self.handlers],
            "sinks": [s.to_dict() for s in self.sinks],
            "max_in_flight": self.max_in_flight,
            "batch_size": self.batch_size,
        }

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.to_dict(), allow_unicode=True, default_flow_style=False)

    @classmethod
    def from_dict(cls, d: dict) -> "DeclarativePipeline":
        return cls(
            name=d.get("name", "unnamed"),
            description=d.get("description", ""),
            source=PipelineSource.from_dict(d.get("source", {})),
            setup=d.get("setup", []),
            handlers=[PipelineHandler.from_dict(h) for h in d.get("handlers", [])],
            sinks=[PipelineSink.from_dict(s) for s in d.get("sinks", [])],
            max_in_flight=d.get("max_in_flight", 1000),
            batch_size=d.get("batch_size", 100),
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "DeclarativePipeline":
        """Load a declarative pipeline from a YAML config file."""
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if "pipeline" in data:
            return cls.from_dict(data["pipeline"])
        return cls.from_dict(data)

    @classmethod
    def quick(cls, name: str, description: str, source_type: str = "raw_input",
              handlers: list[dict] | None = None, sinks: list[str] | None = None) -> "DeclarativePipeline":
        """Quick one-liner to create a pipeline."""
        return cls(
            name=name,
            description=description,
            source=PipelineSource(type=SourceType(source_type)),
            handlers=[PipelineHandler.from_dict(h) for h in (handlers or [])],
            sinks=[PipelineSink(type=SinkType(s)) for s in (sinks or ["memory"])],
        )


# ══════════════════════════════════════════════════════════════════════
# sql-flow Pattern 4: UDF (User Defined Function) Pipeline Injection
# ══════════════════════════════════════════════════════════════════════

@dataclass
class PipelineUDF:
    """A user-defined function that can be injected into pipeline handlers."""
    name: str
    func: Callable
    description: str = ""
    input_type: str = "any"      # Expected input type hint
    output_type: str = "any"     # Output type hint
    registered_at: float = field(default_factory=time.time)
    call_count: int = 0
    total_latency_ms: float = 0.0

    def __call__(self, *args, **kwargs):
        start = time.time()
        result = self.func(*args, **kwargs)
        self.call_count += 1
        self.total_latency_ms += (time.time() - start) * 1000
        return result


class UDFRegistry:
    """Registry for user-defined functions callable from pipelines.
    sql-flow: CREATE OR REPLACE FUNCTION my_udf ... →
    LivingTree: udf_registry.register("my_udf", my_func)
    """

    def __init__(self):
        self._udfs: dict[str, PipelineUDF] = {}

    def register(self, name: str, func: Callable, description: str = "",
                 input_type: str = "any", output_type: str = "any") -> PipelineUDF:
        """Register a UDF that can be invoked by name in pipeline handlers."""
        udf = PipelineUDF(name=name, func=func, description=description,
                         input_type=input_type, output_type=output_type)
        self._udfs[name] = udf
        logger.debug(f"UDFRegistry: registered '{name}'")
        return udf

    def unregister(self, name: str) -> bool:
        return self._udfs.pop(name, None) is not None

    def get(self, name: str) -> PipelineUDF | None:
        return self._udfs.get(name)

    def invoke(self, name: str, *args, **kwargs) -> Any:
        """Invoke a registered UDF by name."""
        udf = self._udfs.get(name)
        if not udf:
            raise KeyError(f"UDF '{name}' not registered")
        return udf(*args, **kwargs)

    def list_udfs(self) -> list[dict]:
        return [
            {"name": u.name, "description": u.description,
             "input_type": u.input_type, "output_type": u.output_type,
             "call_count": u.call_count, "avg_latency_ms": round(u.total_latency_ms / max(u.call_count, 1), 2)}
            for u in self._udfs.values()
        ]

    def stats(self) -> dict:
        return {"total_udfs": len(self._udfs),
                "total_calls": sum(u.call_count for u in self._udfs.values())}


# Global UDF registry singleton
UDF_REGISTRY = UDFRegistry()


# ══════════════════════════════════════════════════════════════════════
# Declarative Pipeline Engine
# ══════════════════════════════════════════════════════════════════════

class DeclarativePipelineEngine:
    """Executes sql-flow-style declarative pipelines with Source→Handlers→Sinks."""

    @staticmethod
    async def run(pipeline: DeclarativePipeline, input_data: Any = None,
                  context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a declarative pipeline end-to-end.

        Args:
            pipeline: The declarative pipeline definition
            input_data: Input data (if source is raw_input, this is the data)
            context: Runtime context (knowledge_base, consciousness, etc.)

        Returns:
            dict with keys: 'results', 'sinks', 'runtime_stats'
        """
        ctx = context or {}
        stats = {"started_at": time.time(), "handlers_executed": 0, "sinks_written": 0}

        # Execute setup commands (e.g., attach databases, create views)
        for cmd in pipeline.setup:
            logger.debug(f"Pipeline setup: {cmd}")

        # Acquire data from source
        data = await DeclarativePipelineEngine._fetch_source(pipeline.source, input_data, ctx)

        # Execute handlers sequentially (like sql-flow's SQL chain)
        for handler in pipeline.handlers:
            data = await DeclarativePipelineEngine._execute_handler(handler, data, ctx)
            stats["handlers_executed"] += 1

        # Fan out to sinks
        sink_results = {}
        for sink in pipeline.sinks:
            try:
                result = await DeclarativePipelineEngine._write_sink(sink, data, ctx)
                sink_results[sink.type.value] = result
                stats["sinks_written"] += 1
            except Exception as e:
                sink_results[sink.type.value] = {"error": str(e)}
                logger.warning(f"Pipeline sink '{sink.type.value}' failed: {e}")

        stats["elapsed_ms"] = (time.time() - stats["started_at"]) * 1000
        return {"results": data, "sinks": sink_results, "runtime_stats": stats}

    @staticmethod
    async def _fetch_source(source: PipelineSource, input_data: Any, ctx: dict) -> Any:
        if source.type == SourceType.RAW:
            return input_data
        if source.type == SourceType.KB:
            kb = ctx.get("knowledge_base")
            query = source.config.get("query", "")
            if kb and query:
                return kb.search(query, top_k=source.config.get("top_k", 10))
        if source.type == SourceType.MEMORY:
            mem = ctx.get("struct_memory")
            query = source.config.get("query", "")
            if mem and query:
                entries, synths = await mem.retrieve_for_query(query)
                return {"entries": entries, "synthesis": synths}
        if source.type == SourceType.FILE:
            path = source.config.get("path", "")
            if path:
                return Path(path).read_text(encoding="utf-8")
        return input_data

    @staticmethod
    async def _execute_handler(handler: PipelineHandler, data: Any, ctx: dict) -> Any:
        if handler.type == HandlerType.UDF:
            udf = UDF_REGISTRY.get(handler.udf_name)
            if udf:
                return udf(data, ctx)
            raise KeyError(f"UDF '{handler.udf_name}' not found")

        if handler.type in (HandlerType.LLM_TRANSFORM, HandlerType.LLM_EXTRACT,
                            HandlerType.LLM_FILTER, HandlerType.LLM_AGGREGATE):
            consciousness = ctx.get("consciousness")
            if consciousness and handler.prompt:
                full_prompt = handler.prompt
                if handler.condition:
                    full_prompt = f"Filter condition: {handler.condition}\n\n{full_prompt}"
                if handler.group_by:
                    full_prompt = f"Group by: {handler.group_by}\n{full_prompt}"
                result = await consciousness.chain_of_thought(
                    f"{full_prompt}\n\nData: {str(data)[:8000]}")
                return result

        if handler.type == HandlerType.CLEAN:
            from ..knowledge.struct_mem import SignalCleaner
            cleaner = SignalCleaner()
            if isinstance(data, str):
                results = cleaner.clean({"content": data, "role": "system"})
                return data if cleaner.is_clean(results) else "[cleaned]"
            return data

        if handler.type == HandlerType.FORMAT:
            rules = ctx.get("format_rules", [])
            if rules and isinstance(data, str):
                for rule in rules:
                    data = re.sub(rule["pattern"], rule["replacement"], data)
            return data

        return data

    @staticmethod
    async def _write_sink(sink: PipelineSink, data: Any, ctx: dict) -> dict:
        if sink.type == SinkType.MEMORY:
            ctx["_pipeline_results"] = data
            return {"stored": True, "type": "memory"}

        if sink.type == SinkType.KB:
            kb = ctx.get("knowledge_base")
            if kb and hasattr(kb, 'add_document'):
                title = sink.config.get("title", "pipeline_output")
                kb.add_document(title=title, content=str(data)[:10000])
                return {"stored": True, "type": "knowledge_base"}

        if sink.type == SinkType.LOG:
            logger.info(f"Pipeline output: {str(data)[:500]}")
            return {"logged": True}

        if sink.type == SinkType.STDOUT:
            return {"output": str(data)[:2000]}

        if sink.type == SinkType.P2P:
            p2p = ctx.get("p2p_presence")
            if p2p and hasattr(p2p, 'build_share'):
                share = p2p.build_share("pipeline_output", {"data": str(data)[:2000]})
                return {"shared": True, "share": share}
            return {"shared": False, "error": "no p2p layer"}

        if sink.type == SinkType.DISK:
            path = sink.config.get("path", ".livingtree/pipelines/output.json")
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(json.dumps({"data": str(data), "timestamp": time.time()},
                                              ensure_ascii=False, default=str), encoding="utf-8")
            return {"written": True, "path": path}

        return {"stored": False, "type": sink.type.value}


def pipeline_from_yaml(path: str | Path) -> DeclarativePipeline:
    """Load a declarative pipeline from a YAML file."""
    return DeclarativePipeline.from_yaml(path)


@dataclass
class PipelineStep:
    op: str
    prompt: str = ""
    condition: str = ""
    key: str = ""
    reverse: bool = False
    params: dict[str, Any] = field(default_factory=dict)
    format_before: bool = False
    format_after: bool = False

    def to_dict(self) -> dict:
        return {
            "op": self.op, "prompt": self.prompt, "condition": self.condition,
            "key": self.key, "reverse": self.reverse, "params": self.params,
            "format_before": self.format_before, "format_after": self.format_after,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PipelineStep":
        fields = {
            k: v for k, v in d.items() if k in cls.__dataclass_fields__
        }
        return cls(**fields)


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

@dataclass
class FormatRule:
    """A single text transformation rule using regex substitution."""
    name: str
    pattern: str
    replacement: Any
    description: str = ""
    enabled: bool = True
    flags: int = 0

    def apply(self, text: str) -> str:
        if not self.enabled or not self.pattern:
            return text
        repl = self.replacement
        import re as _re
        if callable(repl):
            return _re.sub(self.pattern, repl, text, flags=self.flags)
        return _re.sub(self.pattern, str(repl), text, flags=self.flags)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "pattern": self.pattern,
            "replacement": self.replacement,
            "description": self.description,
            "enabled": self.enabled,
            "flags": self.flags,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FormatRule":
        fields = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**fields)


@dataclass
class RuleChain:
    """An ordered chain of FormatRules applied sequentially (like Clibor formatting)."""
    name: str
    rules: list[FormatRule] = field(default_factory=list)
    description: str = ""

    def apply(self, text: str) -> tuple[str, int]:
        """Apply all enabled rules in sequence. Returns (transformed_text, changes_made)."""
        changes = 0
        result = text
        for rule in self.rules:
            before = result
            result = rule.apply(result)
            if result != before:
                changes += 1
        return result, changes

    def add_rule(self, rule: FormatRule) -> None:
        self.rules.append(rule)

    def remove_rule(self, name: str) -> bool:
        for i, r in enumerate(self.rules):
            if r.name == name:
                self.rules.pop(i)
                return True
        return False

    def reorder(self, name: str, new_index: int) -> bool:
        for i, r in enumerate(self.rules):
            if r.name == name:
                rule = self.rules.pop(i)
                self.rules.insert(new_index, rule)
                return True
        return False

    def toggle(self, name: str) -> bool:
        for r in self.rules:
            if r.name == name:
                r.enabled = not r.enabled
                return True
        return False

    def enable_all(self) -> None:
        for r in self.rules:
            r.enabled = True

    def disable_all(self) -> None:
        for r in self.rules:
            r.enabled = False

    def enabled_rules(self) -> list[FormatRule]:
        return [r for r in self.rules if r.enabled]

    def to_dict(self) -> dict:
        return {"name": self.name, "rules": [r.to_dict() for r in self.rules],
                "description": self.description}


TEXT_FORMATTER = RuleChain(
    name="default_formatter",
    description="Common text formatting rules (Clibor-inspired)",
    rules=[
        FormatRule("strip_trailing_spaces", r"[ \t]+$", "", "Remove trailing whitespace", flags=re.MULTILINE),
        FormatRule("compress_blank_lines", r"\n{3,}", "\n\n", "Collapse 3+ blank lines to 2"),
        FormatRule("normalize_quotes", r"[\u201c\u201d\u2018\u2019]", '"', "Convert smart quotes to straight quotes"),
        FormatRule("remove_html_tags", r"<[^>]+>", "", "Strip HTML tags"),
        FormatRule("fix_fullwidth_numbers", r"[\uff10-\uff19]", lambda m: str(ord(m.group(0)) - 0xff10), "Convert fullwidth to ASCII digits"),
        FormatRule("trim_lines", r"^[ \t]+|[ \t]+$", "", "Trim leading/trailing spaces per line", flags=re.MULTILINE),
    ],
)


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
            # Optional: apply formatting before this step
            if getattr(step, "format_before", False):
                for item in current:
                    if "text" in item:
                        text, _ = TEXT_FORMATTER.apply(item.get("text", ""))
                        item["text"] = text

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

            # Optional: apply formatting after this step
            if getattr(step, "format_after", False):
                for item in current:
                    if "text" in item:
                        text, _ = TEXT_FORMATTER.apply(item.get("text", ""))
                        item["text"] = text
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

    def register_format_rule(self, name: str, pattern: str, replacement: Any, description: str = "") -> FormatRule:
        """Register a new TEXT_FORMATTER rule at runtime."""
        rule = FormatRule(name=name, pattern=pattern, replacement=replacement, description=description)
        TEXT_FORMATTER.add_rule(rule)
        return rule

    def remove_format_rule(self, name: str) -> bool:
        """Remove a formatting rule from TEXT_FORMATTER by name."""
        return TEXT_FORMATTER.remove_rule(name)

    def list_format_rules(self) -> list[dict]:
        """List all registered formatting rules with their metadata."""
        return [r.to_dict() for r in TEXT_FORMATTER.rules]

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
