"""Response Schemas — structured output formats for TUI rendering.

Defines JSON schemas that the LLM should use when responding,
so the TUI can auto-render: tool calls, charts, maps, documents, code, diffs.

Self-learning: schemas track usage stats and auto-evolve prompt wording.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OutputType(str, Enum):
    CHAT = "chat"
    TOOL_CALL = "tool_call"
    CODE = "code"
    DIFF = "diff"
    CHART = "chart"
    MAP = "map"
    DOCUMENT = "document"
    TABLE = "table"
    SEARCH = "search"
    PLAN = "plan"
    ERROR = "error"


@dataclass
class SchemaField:
    name: str
    type: str
    description: str = ""
    required: bool = True
    example: Any = None


@dataclass
class OutputSchema:
    output_type: OutputType
    description: str
    fields: list[SchemaField] = field(default_factory=list)
    prompt_hint: str = ""
    usage_count: int = 0
    success_count: int = 0
    avg_tokens: float = 0.0


# ═══ Schema Registry ═══

SCHEMAS: dict[OutputType, OutputSchema] = {
    OutputType.CHAT: OutputSchema(
        output_type=OutputType.CHAT,
        description="Plain text chat response",
        prompt_hint="Respond conversationally. Use markdown for formatting.",
        fields=[
            SchemaField("type", "string", "Always 'chat'"),
            SchemaField("content", "string", "Chat message in markdown"),
        ],
    ),
    OutputType.TOOL_CALL: OutputSchema(
        output_type=OutputType.TOOL_CALL,
        description="Execute a tool with structured parameters",
        prompt_hint=(
            "When you need to use a tool, output JSON:\n"
            '{"type":"tool_call","tool":"tool_name","params":{...},"reasoning":"why"}\n'
            "Available tools: search, fetch, parse, chart, map, code, diff"
        ),
        fields=[
            SchemaField("type", "string", "Always 'tool_call'"),
            SchemaField("tool", "string", "Tool name", example="search"),
            SchemaField("params", "object", "Tool parameters"),
            SchemaField("reasoning", "string", "Why this tool is needed", required=False),
        ],
    ),
    OutputType.CODE: OutputSchema(
        output_type=OutputType.CODE,
        description="Code block with language detection",
        prompt_hint=(
            "Output code as JSON with language detection:\n"
            '{"type":"code","language":"python","code":"...","explanation":"..."}'
        ),
        fields=[
            SchemaField("type", "string", "Always 'code'"),
            SchemaField("language", "string", "Programming language"),
            SchemaField("code", "string", "Source code"),
            SchemaField("explanation", "string", "What the code does", required=False),
            SchemaField("filename", "string", "Suggested filename", required=False),
        ],
    ),
    OutputType.DIFF: OutputSchema(
        output_type=OutputType.DIFF,
        description="Code diff/patch for review",
        prompt_hint=(
            "Output diffs as JSON:\n"
            '{"type":"diff","filename":"app.py","before":"old","after":"new","description":"change"}'
        ),
        fields=[
            SchemaField("type", "string", "Always 'diff'"),
            SchemaField("filename", "string", "File being changed"),
            SchemaField("before", "string", "Original code"),
            SchemaField("after", "string", "New code"),
            SchemaField("description", "string", "Change description"),
        ],
    ),
    OutputType.CHART: OutputSchema(
        output_type=OutputType.CHART,
        description="Chart/plot data for terminal rendering",
        prompt_hint=(
            "Output chart data as JSON:\n"
            '{"type":"chart","chart_type":"bar"|"line"|"scatter","title":"...",'
            '"data":{"labels":["A","B"],"values":[10,20]},"width":50,"height":15}'
        ),
        fields=[
            SchemaField("type", "string", "Always 'chart'"),
            SchemaField("chart_type", "string", "bar, line, scatter, or pie"),
            SchemaField("title", "string", "Chart title"),
            SchemaField("data", "object", "Chart data (labels + values or points)"),
            SchemaField("width", "integer", "Render width", required=False, example=50),
            SchemaField("height", "integer", "Render height", required=False, example=15),
        ],
    ),
    OutputType.MAP: OutputSchema(
        output_type=OutputType.MAP,
        description="Map coordinates for terminal preview",
        prompt_hint=(
            "Output map data as JSON:\n"
            '{"type":"map","lat":39.9042,"lon":116.4074,"zoom":12,"label":"Beijing"}'
        ),
        fields=[
            SchemaField("type", "string", "Always 'map'"),
            SchemaField("lat", "number", "Latitude"),
            SchemaField("lon", "number", "Longitude"),
            SchemaField("zoom", "integer", "Zoom level (0-18)", required=False, example=12),
            SchemaField("label", "string", "Location label", required=False),
        ],
    ),
    OutputType.DOCUMENT: OutputSchema(
        output_type=OutputType.DOCUMENT,
        description="Structured document content",
        prompt_hint=(
            "Output document content as JSON:\n"
            '{"type":"document","format":"markdown","title":"...","content":"..."}'
        ),
        fields=[
            SchemaField("type", "string", "Always 'document'"),
            SchemaField("format", "string", "markdown, text, or json"),
            SchemaField("title", "string", "Document title"),
            SchemaField("content", "string", "Document content"),
            SchemaField("sections", "array", "Section headers", required=False),
        ],
    ),
    OutputType.TABLE: OutputSchema(
        output_type=OutputType.TABLE,
        description="Tabular data",
        prompt_hint=(
            "Output table data as JSON:\n"
            '{"type":"table","headers":["Name","Value"],"rows":[["A",1],["B",2]],"title":"..."}'
        ),
        fields=[
            SchemaField("type", "string", "Always 'table'"),
            SchemaField("headers", "array", "Column headers"),
            SchemaField("rows", "array", "Data rows (array of arrays)"),
            SchemaField("title", "string", "Table title", required=False),
        ],
    ),
    OutputType.SEARCH: OutputSchema(
        output_type=OutputType.SEARCH,
        description="Aggregated search results",
        prompt_hint=(
            "When returning search results, format as JSON:\n"
            '{"type":"search","query":"...","results":[{title,url,summary},...]}'
        ),
        fields=[
            SchemaField("type", "string", "Always 'search'"),
            SchemaField("query", "string", "Original search query"),
            SchemaField("results", "array", "Search result objects with title/url/summary"),
        ],
    ),
    OutputType.PLAN: OutputSchema(
        output_type=OutputType.PLAN,
        description="Task plan with steps and status",
        prompt_hint=(
            "Output task plan as JSON:\n"
            '{"type":"plan","title":"...","steps":[{name,status,priority},...]}'
        ),
        fields=[
            SchemaField("type", "string", "Always 'plan'"),
            SchemaField("title", "string", "Plan title"),
            SchemaField("steps", "array", "Step objects with name/status/pending|done|active"),
        ],
    ),
}


def get_schema(output_type: OutputType) -> OutputSchema:
    return SCHEMAS.get(output_type, SCHEMAS[OutputType.CHAT])


def get_system_prompt() -> str:
    """Generate the system prompt that tells the LLM about available output formats."""
    schemas_block = []
    for stype, schema in SCHEMAS.items():
        if stype == OutputType.CHAT:
            continue
        hint = schema.prompt_hint.strip()
        if hint:
            schemas_block.append(hint)

    return (
        "You are an AI assistant integrated with a terminal-based TUI (Text User Interface). "
        "You must respond in Chinese (中文) by default. "
        "You can output structured JSON to trigger specific TUI rendering widgets. "
        "For plain conversation, respond normally in Chinese. "
        "For structured outputs, wrap the JSON in ```json code blocks.\n\n"
        "## Available output formats:\n" + "\n\n".join(schemas_block) + "\n\n"
        "Choose the appropriate format based on what the user is asking. "
        "Use plain Chinese chat for conversation unless a structured format is clearly better."
    )
