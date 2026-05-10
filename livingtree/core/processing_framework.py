"""Processing Framework — QGIS Processing Toolbox for LivingTree tools.

Standardizes all tools into a unified ToolSpec (metadata, I/O types,
parameters) enabling visual chain orchestration where tools can be
connected like a dataflow pipeline.

ToolSpec:  {name, description, inputs, outputs, parameters, category}
Chain:     [Step1] → [Step2] → [Step3] — validated type compatibility
"""

from __future__ import annotations

import json as _json
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class ToolSpec:
    """Standardized tool metadata — QGIS Processing Toolbox style."""
    name: str
    description: str = ""
    category: str = "general"
    inputs: list[dict] = field(default_factory=list)       # [{name, type, required, default}]
    outputs: list[dict] = field(default_factory=list)       # [{name, type, description}]
    parameters: dict[str, Any] = field(default_factory=dict)
    provider: str = "livingtree"
    icon: str = "🔧"
    tags: list[str] = field(default_factory=list)
    # QGIS-style: can it run in a chain?
    chainable: bool = True
    input_source: str = ""    # which output.name from previous step feeds this


@dataclass
class ChainStep:
    tool: ToolSpec
    input_map: dict[str, str] = field(default_factory=dict)  # param_name → source_output_name
    enabled: bool = True
    order: int = 0


@dataclass
class ToolChain:
    name: str
    steps: list[ChainStep] = field(default_factory=list)
    description: str = ""
    total_tools: int = 0

    def validate(self) -> dict:
        """Validate type compatibility across chain steps."""
        issues = []
        for i, step in enumerate(self.steps):
            if i == 0:
                continue
            prev = self.steps[i - 1]
            prev_outputs = {o["name"]: o["type"] for o in prev.tool.outputs}
            for inp in step.tool.inputs:
                src = step.input_map.get(inp["name"], "")
                if src and src in prev_outputs:
                    if prev_outputs[src] != inp["type"] and inp["type"] != "any":
                        issues.append({
                            "step": i, "param": inp["name"],
                            "expected": inp["type"], "actual": prev_outputs[src],
                        })
        return {"valid": len(issues) == 0, "issues": issues}


class ProcessingFramework:
    """QGIS Processing Toolbox for LivingTree tools.

    Registers tool specifications, validates chain compatibility,
    and generates visual chain diagrams.
    """

    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}
        self._chains: list[ToolChain] = []
        self._register_builtins()

    def _register_builtins(self):
        builtins = [
            ToolSpec("text_extract", "提取文本", "text",
                     inputs=[{"name": "content", "type": "string", "required": True}],
                     outputs=[{"name": "text", "type": "string", "description": "提取的纯文本"}]),
            ToolSpec("stt_transcribe", "语音转文字", "audio",
                     inputs=[{"name": "audio", "type": "bytes", "required": True}],
                     outputs=[{"name": "text", "type": "string", "description": "转写结果"}]),
            ToolSpec("llm_chat", "LLM对话", "llm",
                     inputs=[{"name": "prompt", "type": "string", "required": True}],
                     outputs=[{"name": "response", "type": "string", "description": "LLM回复"}],
                     parameters={"temperature": 0.7}),
            ToolSpec("knowledge_search", "知识库检索", "knowledge",
                     inputs=[{"name": "query", "type": "string", "required": True}],
                     outputs=[{"name": "results", "type": "list", "description": "检索结果列表"}]),
            ToolSpec("web_fetch", "网页抓取", "web",
                     inputs=[{"name": "url", "type": "string", "required": True}],
                     outputs=[{"name": "content", "type": "string", "description": "网页内容"}]),
            ToolSpec("report_generate", "报告生成", "output",
                     inputs=[{"name": "data", "type": "any", "required": True}],
                     outputs=[{"name": "report", "type": "string", "description": "生成的报告"}]),
            ToolSpec("ocr_scan", "图片OCR", "vision",
                     inputs=[{"name": "image", "type": "bytes", "required": True}],
                     outputs=[{"name": "text", "type": "string", "description": "识别文字"}]),
            ToolSpec("video_search", "视频搜索", "video",
                     inputs=[{"name": "keyword", "type": "string", "required": True}],
                     outputs=[{"name": "results", "type": "list", "description": "视频列表"}]),
        ]
        for t in builtins:
            self._tools[t.name] = t

    # ═══ Registration ═══

    def register(self, tool: ToolSpec):
        self._tools[tool.name] = tool

    def unregister(self, name: str):
        self._tools.pop(name, None)

    def list_tools(self, category: str = "") -> list[ToolSpec]:
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return sorted(tools, key=lambda t: t.name)

    def get_tool(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    # ═══ Chain Building ═══

    def build_chain(self, name: str, tool_names: list[str],
                    connections: list[dict] = None) -> ToolChain:
        """Build a processing chain from tool names.

        connections: [{from_step, from_output, to_step, to_input}, ...]
        """
        steps = []
        for i, tn in enumerate(tool_names):
            tool = self._tools.get(tn)
            if not tool:
                continue
            input_map = {}
            if connections:
                for conn in connections:
                    if conn.get("to_step") == i:
                        input_map[conn["to_input"]] = conn["from_output"]
            steps.append(ChainStep(tool=tool, input_map=input_map, order=i))

        chain = ToolChain(name=name, steps=steps, total_tools=len(steps))
        self._chains.append(chain)
        return chain

    def get_chain(self, name: str) -> Optional[ToolChain]:
        for c in self._chains:
            if c.name == name:
                return c
        return None

    # ═══ Visual Chain Diagram ═══

    def render_chain_html(self, chain: ToolChain) -> str:
        """Generate a visual processing chain as HTML."""
        validation = chain.validate()

        steps_html = []
        for i, step in enumerate(chain.steps):
            t = step.tool
            inputs_str = ", ".join(f"{inp['name']}:{inp['type']}" for inp in t.inputs[:3])
            outputs_str = ", ".join(f"{o['name']}:{o['type']}" for o in t.outputs[:3])

            connector = ""
            if i > 0:
                connector = '<div style="display:flex;align-items:center;justify-content:center;width: 40px;color:var(--accent);font-size:18px">→</div>'

            steps_html.append(f'''
            {connector}
            <div style="background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:8px 12px;text-align:center;min-width:120px">
              <div style="font-size:16px">{t.icon}</div>
              <div style="font-size:10px;font-weight:600;color:var(--accent)">{t.name}</div>
              <div style="font-size:8px;color:var(--dim)">{t.category}</div>
              <div style="font-size:8px;color:var(--dim);margin-top:2px">in: {inputs_str}</div>
              <div style="font-size:8px;color:var(--dim)">out: {outputs_str}</div>
            </div>''')

        valid_badge = '✅ 类型兼容' if validation["valid"] else f'⚠ {len(validation["issues"])}个类型不匹配'
        issues_html = ""
        if validation["issues"]:
            issues_html = '<div style="margin-top:4px;font-size:9px;color:var(--warn)">' + "; ".join(
                f"Step{i['step']}.{i['param']}: expected {i['expected']} got {i['actual']}"
                for i in validation["issues"]
            ) + '</div>'

        return f'''<div class="card">
<h2>🔗 处理链: {chain.name}</h2>
<p style="font-size:10px;color:var(--dim)">{chain.total_tools}个工具 · {valid_badge}</p>
<div style="display:flex;align-items:center;overflow-x:auto;padding:12px 8px;gap:0">
  {"".join(steps_html)}
</div>
{issues_html}
</div>'''

    def render_toolbox_html(self, category: str = "") -> str:
        tools = self.list_tools(category)
        categories = list(set(t.category for t in tools))

        tool_rows = []
        for t in tools:
            inputs_str = ", ".join(f"{inp['name']}" for inp in t.inputs[:4])
            outputs_str = ", ".join(f"{o['name']}" for o in t.outputs[:4])
            tool_rows.append(f'''
            <tr style="border-bottom:1px solid var(--border)">
              <td style="padding:6px 8px;font-size:11px">
                {t.icon} <b>{t.name}</b>
                <div style="font-size:9px;color:var(--dim)">{t.description}</div>
              </td>
              <td style="padding:6px 4px;text-align:center;font-size:10px">{t.category}</td>
              <td style="padding:6px 4px;font-size:9px;color:var(--dim)">{inputs_str}</td>
              <td style="padding:6px 4px;font-size:9px;color:var(--dim)">{outputs_str}</td>
            </tr>''')

        return f'''<div class="card">
<h2>🔧 处理工具箱 <span style="font-size:10px;color:var(--dim);font-weight:400">— QGIS Processing Toolbox</span></h2>
<div style="font-size:9px;color:var(--dim);margin:4px 0;display:flex;gap:12px">
  <span>工具 <b>{len(tools)}</b></span>
  <span>分类 <b>{len(categories)}</b></span>
  {" ".join(f'<span style="background:var(--panel);padding:1px 6px;border-radius:3px">{c}</span>' for c in sorted(categories))}
</div>
<div style="overflow-x:auto">
<table style="width:100%;border-collapse:collapse;font-size:11px">
<thead><tr style="text-align:left;border-bottom:2px solid var(--border);font-size:10px;color:var(--dim)">
  <th style="padding:6px 8px">工具</th>
  <th style="padding:6px 4px;text-align:center">分类</th>
  <th style="padding:6px 4px">输入</th>
  <th style="padding:6px 4px">输出</th>
</tr></thead>
<tbody>{"".join(tool_rows)}</tbody></table></div></div>'''


_instance: Optional[ProcessingFramework] = None


def get_processing() -> ProcessingFramework:
    global _instance
    if _instance is None:
        _instance = ProcessingFramework()
    return _instance
