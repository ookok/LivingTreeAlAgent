"""Interactive Tool Canvas — AI suggests tools, user operates, results feed back.

No hardcoded tools. The AI dynamically decides which interactive tools to offer
based on task context. Tools are discovered from:
- ToolMarket (registered tools)
- UniversalScanner (discovered services)
- MCP servers (external tool providers)
- AI's own analysis (what would help the user right now)

Flow: AI emits ToolOffer → UI renders tool card → user operates → result → AI context
"""

from __future__ import annotations

import json as _json
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class ToolOffer:
    """AI suggests an interactive tool for the user to operate."""
    offer_id: str
    tool_type: str          # map, draw, calc, code, table, form, external, custom
    title: str              # What the tool helps with
    description: str        # Why this tool is relevant
    prompt: str             # What the user should do
    context_data: dict = field(default_factory=dict)
    result_endpoint: str = "/tree/tools/result"
    priority: str = "normal"  # high, normal, low

    def to_html(self) -> str:
        """Generate the tool card HTML."""
        if self.tool_type == "map":
            return self._map_card()
        elif self.tool_type == "draw":
            return self._draw_card()
        elif self.tool_type == "calc":
            return self._calc_card()
        elif self.tool_type == "code":
            return self._code_card()
        elif self.tool_type == "table":
            return self._table_card()
        elif self.tool_type == "form":
            return self._form_card()
        else:
            return self._generic_card()

    def _map_card(self) -> str:
        lat = self.context_data.get("lat", 39.9)
        lng = self.context_data.get("lng", 116.4)
        zoom = self.context_data.get("zoom", 13)
        marker = self.context_data.get("marker", "")
        return f'''<div class="tool-card" id="tool-{self.offer_id}" style="background:var(--panel);border:1px solid var(--border);border-radius:8px;overflow:hidden;margin:8px 0">
<div style="padding:8px 12px;display:flex;justify-content:space-between;align-items:center;background:rgba(100,150,180,.05);border-bottom:1px solid var(--border)">
<span style="font-size:12px;font-weight:600;color:var(--accent)">🗺️ {self.title}</span>
<div style="display:flex;gap:4px">
<button onclick="document.getElementById('tool-{self.offer_id}').remove()" style="background:none;border:none;color:var(--dim);cursor:pointer;font-size:14px">✕</button>
</div></div>
<div style="font-size:11px;color:var(--dim);padding:4px 12px">{self.description}</div>
<div style="font-size:11px;padding:4px 12px;color:var(--text)">💡 {self.prompt}</div>
<iframe src="https://www.openstreetmap.org/export/embed.html?bbox={lng-0.02},{lat-0.01},{lng+0.02},{lat+0.01}&layer=mapnik&marker={lat},{lng}"
style="width:100%;height:250px;border:none"></iframe>
<div style="padding:6px 12px;display:flex;gap:6px;border-top:1px solid var(--border)">
<input id="map-note-{self.offer_id}" placeholder="在此位置添加备注..." style="flex:1;font-size:11px;padding:4px 8px">
<button onclick="submitToolResult('{self.offer_id}','map',{{lat:{lat},lng:{lng},note:document.getElementById('map-note-{self.offer_id}').value}})" style="font-size:10px;padding:4px 10px">📨 发送给AI</button>
</div></div>'''

    def _draw_card(self) -> str:
        width = self.context_data.get("width", 600)
        height = self.context_data.get("height", 300)
        return f'''<div class="tool-card" id="tool-{self.offer_id}" style="background:var(--panel);border:1px solid var(--border);border-radius:8px;overflow:hidden;margin:8px 0">
<div style="padding:8px 12px;display:flex;justify-content:space-between;align-items:center;background:rgba(100,150,180,.05);border-bottom:1px solid var(--border)">
<span style="font-size:12px;font-weight:600;color:var(--accent)">🎨 {self.title}</span>
<div style="display:flex;gap:4px">
<button onclick="clearCanvas('draw-{self.offer_id}')" style="background:var(--panel);border:1px solid var(--border);color:var(--dim);font-size:10px;padding:2px 6px;border-radius:3px;cursor:pointer">清除</button>
<button onclick="document.getElementById('tool-{self.offer_id}').remove()" style="background:none;border:none;color:var(--dim);cursor:pointer;font-size:14px">✕</button>
</div></div>
<div style="font-size:11px;color:var(--dim);padding:4px 12px">{self.description}</div>
<div style="font-size:11px;padding:4px 12px;color:var(--text)">💡 {self.prompt}</div>
<canvas id="draw-{self.offer_id}" width="{width}" height="{height}" style="background:#fff;cursor:crosshair;display:block;margin:0 auto;max-width:100%"></canvas>
<div style="padding:4px 12px;display:flex;gap:4px;border-top:1px solid var(--border);flex-wrap:wrap">
<button onclick="setDrawColor('draw-{self.offer_id}','#000')" style="width:20px;height:20px;background:#000;border:1px solid #ccc;border-radius:50%;cursor:pointer"></button>
<button onclick="setDrawColor('draw-{self.offer_id}','#e05050')" style="width:20px;height:20px;background:#e05050;border:1px solid #ccc;border-radius:50%;cursor:pointer"></button>
<button onclick="setDrawColor('draw-{self.offer_id}','#1B365D')" style="width:20px;height:20px;background:#1B365D;border:1px solid #ccc;border-radius:50%;cursor:pointer"></button>
<button onclick="setDrawColor('draw-{self.offer_id}','#6c8')" style="width:20px;height:20px;background:#6c8;border:1px solid #ccc;border-radius:50%;cursor:pointer"></button>
<button onclick="setDrawColor('draw-{self.offer_id}','#e8a030')" style="width:20px;height:20px;background:#e8a030;border:1px solid #ccc;border-radius:50%;cursor:pointer"></button>
<input type="range" min="1" max="8" value="2" oninput="setDrawWidth('draw-{self.offer_id}',this.value)" style="width:80px">
<button onclick="submitToolResult('{self.offer_id}','draw',{{data:document.getElementById('draw-{self.offer_id}').toDataURL()}})" style="font-size:10px;padding:4px 10px;margin-left:auto">📨 发送给AI</button>
</div></div>
<script>initDrawCanvas('draw-{self.offer_id}')</script>'''

    def _calc_card(self) -> str:
        expr = self.context_data.get("expression", "")
        return f'''<div class="tool-card" id="tool-{self.offer_id}" style="background:var(--panel);border:1px solid var(--border);border-radius:8px;overflow:hidden;margin:8px 0">
<div style="padding:8px 12px;display:flex;justify-content:space-between;align-items:center;background:rgba(100,150,180,.05);border-bottom:1px solid var(--border)">
<span style="font-size:12px;font-weight:600;color:var(--accent)">🧮 {self.title}</span>
<button onclick="document.getElementById('tool-{self.offer_id}').remove()" style="background:none;border:none;color:var(--dim);cursor:pointer;font-size:14px">✕</button></div>
<div style="font-size:11px;color:var(--dim);padding:4px 12px">{self.description}</div>
<div style="padding:8px 12px">
<div style="display:flex;gap:6px;margin-bottom:8px">
<input id="calc-expr-{self.offer_id}" value="{expr}" placeholder="输入表达式, 如: 2+3*4, sqrt(16), sin(pi/2)" style="flex:1;font-size:13px;padding:8px;font-family:monospace">
<button onclick="runCalc('{self.offer_id}')" style="font-size:12px;padding:8px 14px">= 计算</button>
</div>
<div style="display:flex;flex-wrap:wrap;gap:3px;margin-bottom:4px">
<button onclick="insertCalc('{self.offer_id}','+')" class="lc-tool-btn">+</button>
<button onclick="insertCalc('{self.offer_id}','-')" class="lc-tool-btn">-</button>
<button onclick="insertCalc('{self.offer_id}','*')" class="lc-tool-btn">×</button>
<button onclick="insertCalc('{self.offer_id}','/')" class="lc-tool-btn">÷</button>
<button onclick="insertCalc('{self.offer_id}','(')" class="lc-tool-btn">(</button>
<button onclick="insertCalc('{self.offer_id}',')')" class="lc-tool-btn">)</button>
<button onclick="insertCalc('{self.offer_id}','**')" class="lc-tool-btn">^</button>
<button onclick="insertCalc('{self.offer_id}','sqrt(')" class="lc-tool-btn">√</button>
<button onclick="insertCalc('{self.offer_id}','Math.PI')" class="lc-tool-btn">π</button>
<button onclick="insertCalc('{self.offer_id}','Math.E')" class="lc-tool-btn">e</button>
</div>
<div id="calc-result-{self.offer_id}" style="font-size:16px;font-family:monospace;padding:8px;background:rgba(0,0,0,.05);border-radius:4px;min-height:32px;color:var(--accent)"></div>
<div style="display:flex;gap:6px;margin-top:4px">
<div id="calc-history-{self.offer_id}" style="flex:1;font-size:10px;color:var(--dim);max-height:60px;overflow-y:auto"></div>
<button onclick="submitToolResult('{self.offer_id}','calc',{{history:document.getElementById('calc-history-{self.offer_id}').textContent}})" style="font-size:10px;padding:4px 10px">📨 发送给AI</button>
</div></div></div>'''

    def _code_card(self) -> str:
        code = self.context_data.get("code", "")
        lang = self.context_data.get("language", "python")
        return f'''<div class="tool-card" id="tool-{self.offer_id}" style="background:var(--panel);border:1px solid var(--border);border-radius:8px;overflow:hidden;margin:8px 0">
<div style="padding:8px 12px;display:flex;justify-content:space-between;align-items:center;background:rgba(100,150,180,.05);border-bottom:1px solid var(--border)">
<span style="font-size:12px;font-weight:600;color:var(--accent)">💻 {self.title}</span>
<div style="display:flex;gap:4px">
<button onclick="runCode('{self.offer_id}')" style="font-size:10px;padding:3px 8px;background:var(--accent);color:var(--bg);border:none;border-radius:3px;cursor:pointer">▶ 运行</button>
<button onclick="document.getElementById('tool-{self.offer_id}').remove()" style="background:none;border:none;color:var(--dim);cursor:pointer;font-size:14px">✕</button>
</div></div>
<div style="font-size:11px;color:var(--dim);padding:4px 12px">{self.description}</div>
<div style="font-size:11px;padding:4px 12px;color:var(--text)">💡 {self.prompt}</div>
<textarea id="code-editor-{self.offer_id}" style="width:100%;min-height:200px;background:var(--bg);border:none;color:var(--text);padding:12px;font-family:var(--font-mono);font-size:12px;resize:vertical;line-height:1.5" spellcheck="false">{code}</textarea>
<div id="code-output-{self.offer_id}" style="padding:8px 12px;font-family:var(--font-mono);font-size:11px;color:var(--dim);max-height:200px;overflow-y:auto;display:none;border-top:1px solid var(--border)"></div>
<div style="padding:4px 12px;display:flex;gap:4px;border-top:1px solid var(--border)">
<select id="code-lang-{self.offer_id}" style="font-size:10px;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:2px 6px;border-radius:3px">
<option value="python" {"selected" if lang=="python" else ""}>Python</option>
<option value="javascript" {"selected" if lang=="javascript" else ""}>JavaScript</option>
<option value="sql" {"selected" if lang=="sql" else ""}>SQL</option>
<option value="bash" {"selected" if lang=="bash" else ""}>Bash</option>
</select>
<button onclick="submitToolResult('{self.offer_id}','code',{{code:document.getElementById('code-editor-{self.offer_id}').value,output:document.getElementById('code-output-{self.offer_id}').textContent}})" style="font-size:10px;padding:4px 10px;margin-left:auto">📨 发送给AI</button>
</div></div>'''

    def _table_card(self) -> str:
        rows = self.context_data.get("rows", [["", ""], ["", ""]])
        cols = self.context_data.get("columns", ["列A", "列B"])
        header_html = "<tr>" + "".join(f'<th style="padding:6px 10px;border-bottom:1px solid var(--border);text-align:left;font-size:11px">{c}</th>' for c in cols) + "</tr>"
        body_html = ""
        for i, row in enumerate(rows[:10]):
            body_html += "<tr>" + "".join(f'<td style="padding:4px 6px;border-bottom:1px solid var(--border)"><input value="{cell}" style="width:100%;background:transparent;border:none;color:var(--text);font-size:11px;padding:2px" onchange="updateTableRow(\'{self.offer_id}\',{i})"></td>' for cell in (row if row else [""]*len(cols))) + "</tr>"
        return f'''<div class="tool-card" id="tool-{self.offer_id}" style="background:var(--panel);border:1px solid var(--border);border-radius:8px;overflow:hidden;margin:8px 0">
<div style="padding:8px 12px;display:flex;justify-content:space-between;align-items:center;background:rgba(100,150,180,.05);border-bottom:1px solid var(--border)">
<span style="font-size:12px;font-weight:600;color:var(--accent)">📊 {self.title}</span>
<button onclick="document.getElementById('tool-{self.offer_id}').remove()" style="background:none;border:none;color:var(--dim);cursor:pointer;font-size:14px">✕</button></div>
<div style="font-size:11px;color:var(--dim);padding:4px 12px">{self.description}</div>
<div style="overflow-x:auto;padding:4px">
<table style="width:100%;border-collapse:collapse;font-size:12px">{header_html}{body_html}</table>
</div>
<div style="padding:6px 12px;display:flex;gap:4px;border-top:1px solid var(--border)">
<button onclick="collectTableData('{self.offer_id}')" style="font-size:10px;padding:4px 10px">📨 发送给AI</button>
<button onclick="addTableRow('{self.offer_id}')" style="font-size:10px;padding:4px 10px;background:var(--panel);border:1px solid var(--border);color:var(--dim);cursor:pointer">+ 添加行</button>
</div></div>'''

    def _form_card(self) -> str:
        fields = self.context_data.get("fields", [{"label": "输入", "name": "input", "type": "text"}])
        fields_html = ""
        for f in fields[:8]:
            tp = f.get("type", "text")
            if tp == "textarea":
                fields_html += f'<div style="margin-bottom:6px"><label style="font-size:11px;color:var(--dim)">{f["label"]}</label><textarea name="{f["name"]}" rows="3" style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:8px;border-radius:4px;font-size:12px"></textarea></div>'
            elif tp == "select":
                opts = f.get("options", [])
                opts_html = "".join(f'<option value="{o}">{o}</option>' for o in opts)
                fields_html += f'<div style="margin-bottom:6px"><label style="font-size:11px;color:var(--dim)">{f["label"]}</label><select name="{f["name"]}" style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:8px;border-radius:4px;font-size:12px">{opts_html}</select></div>'
            else:
                fields_html += f'<div style="margin-bottom:6px"><label style="font-size:11px;color:var(--dim)">{f["label"]}</label><input name="{f["name"]}" type="{tp}" style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:8px;border-radius:4px;font-size:12px"></div>'
        return f'''<div class="tool-card" id="tool-{self.offer_id}" style="background:var(--panel);border:1px solid var(--border);border-radius:8px;overflow:hidden;margin:8px 0">
<div style="padding:8px 12px;display:flex;justify-content:space-between;align-items:center;background:rgba(100,150,180,.05);border-bottom:1px solid var(--border)">
<span style="font-size:12px;font-weight:600;color:var(--accent)">📋 {self.title}</span>
<button onclick="document.getElementById('tool-{self.offer_id}').remove()" style="background:none;border:none;color:var(--dim);cursor:pointer;font-size:14px">✕</button></div>
<div style="font-size:11px;color:var(--dim);padding:4px 12px">{self.description}</div>
<div style="padding:8px 12px">{fields_html}</div>
<div style="padding:6px 12px;border-top:1px solid var(--border)">
<button onclick="submitToolResult('{self.offer_id}','form',collectFormData('tool-{self.offer_id}'))" style="font-size:11px;padding:6px 14px">📨 提交并发送给AI</button>
</div></div>'''

    def _generic_card(self) -> str:
        return f'''<div class="tool-card" id="tool-{self.offer_id}" style="background:var(--panel);border:1px solid var(--border);border-radius:8px;overflow:hidden;margin:8px 0">
<div style="padding:8px 12px;display:flex;justify-content:space-between;align-items:center;background:rgba(100,150,180,.05);border-bottom:1px solid var(--border)">
<span style="font-size:12px;font-weight:600;color:var(--accent)">🔧 {self.title}</span>
<button onclick="document.getElementById('tool-{self.offer_id}').remove()" style="background:none;border:none;color:var(--dim);cursor:pointer;font-size:14px">✕</button></div>
<div style="font-size:11px;color:var(--dim);padding:4px 12px">{self.description}</div>
<div style="font-size:11px;padding:4px 12px;color:var(--text)">💡 {self.prompt}</div>
<div style="padding:8px 12px">
<textarea id="generic-input-{self.offer_id}" rows="4" placeholder="在此输入..." style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:8px;border-radius:4px;font-size:12px;resize:vertical"></textarea>
</div>
<div style="padding:6px 12px;border-top:1px solid var(--border);display:flex;justify-content:flex-end">
<button onclick="submitToolResult('{self.offer_id}','custom',{{input:document.getElementById('generic-input-{self.offer_id}').value}})" style="font-size:10px;padding:4px 12px">📨 发送给AI</button>
</div></div>'''


class InteractiveToolRegistry:
    """Dynamic registry of available interactive tools.

    Tools are NOT hardcoded. They're discovered from:
    - AI analysis of task context
    - ToolMarket search results
    - UniversalScanner discovered services
    - MCP server tool listings
    """

    def __init__(self):
        self._offers: dict[str, ToolOffer] = {}

    def suggest_tools(self, task_context: str, available_tools: list[dict]) -> list[ToolOffer]:
        """AI analyzes the task and suggests relevant interactive tools.

        This is where the AI decides what tools to offer — not the developer.
        """
        offers = []
        ctx_lower = task_context.lower()

        if any(kw in ctx_lower for kw in ["地图", "位置", "坐标", "地点", "map", "location", "gps"]):
            offers.append(ToolOffer(
                offer_id=f"map_{len(offers)}",
                tool_type="map",
                title="在地图上标注位置",
                description="AI 发现任务涉及地理位置信息",
                prompt="点击地图标记位置，添加备注后发送给 AI 继续分析",
                context_data={"lat": 39.9, "lng": 116.4},
            ))

        if any(kw in ctx_lower for kw in ["图", "画", "示意", "流程图", "架构", "结构", "draw", "diagram", "chart"]):
            offers.append(ToolOffer(
                offer_id=f"draw_{len(offers)}",
                tool_type="draw",
                title="手绘示意图",
                description="AI 发现任务需要可视化表达",
                prompt="在画布上绘制示意图，完成后发送给 AI 识别和分析",
            ))

        if any(kw in ctx_lower for kw in ["计算", "算", "公式", "推导", "验算", "参数", "calc", "compute", "math"]):
            offers.append(ToolOffer(
                offer_id=f"calc_{len(offers)}",
                tool_type="calc",
                title="验算与计算器",
                description="AI 发现任务涉及数值计算",
                prompt="输入公式或表达式进行验算，结果可发送回 AI 验证",
            ))

        if any(kw in ctx_lower for kw in ["代码", "写", "编程", "code", "script", "函数", "class"]):
            offers.append(ToolOffer(
                offer_id=f"code_{len(offers)}",
                tool_type="code",
                title="代码编辑器",
                description="AI 发现任务涉及代码",
                prompt="在编辑器中修改代码，运行测试后发送给 AI 评审",
                context_data={"code": task_context[:500]},
            ))

        if any(kw in ctx_lower for kw in ["数据", "表格", "列表", "对比", "参数", "table", "data", "compare"]):
            offers.append(ToolOffer(
                offer_id=f"table_{len(offers)}",
                tool_type="table",
                title="数据表格",
                description="AI 发现任务涉及结构化数据",
                prompt="在表格中录入或修改数据，完成后发送给 AI 处理",
                context_data={"columns": ["参数", "值", "备注"], "rows": [["", "", ""], ["", "", ""], ["", "", ""]]},
            ))

        for tool in available_tools:
            offers.append(ToolOffer(
                offer_id=f"ext_{tool.get('name', 'tool')}_{len(offers)}",
                tool_type="external",
                title=f"使用工具: {tool.get('name', '未知')}",
                description=tool.get('description', '')[:100],
                prompt=f"此工具可以帮助完成任务",
                context_data=tool,
                result_endpoint=f"/api/tools/execute/{tool.get('name', '')}",
            ))

        return offers


_registry: Optional[InteractiveToolRegistry] = None


def get_tool_registry() -> InteractiveToolRegistry:
    global _registry
    if _registry is None:
        _registry = InteractiveToolRegistry()
    return _registry


# ═══ JavaScript: Drawing Canvas + Calculator + Tool API ═══

TOOL_CANVAS_JS = r"""
// Drawing Canvas
var _drawStates = {};
function initDrawCanvas(canvasId) {
  var c = document.getElementById(canvasId);
  if (!c) return;
  var ctx = c.getContext('2d');
  _drawStates[canvasId] = { ctx: ctx, drawing: false, color: '#000', width: 2 };
  c.onmousedown = function(e) { _drawStates[canvasId].drawing = true; _draw(e, canvasId); };
  c.onmouseup = c.onmouseleave = function() { _drawStates[canvasId].drawing = false; _drawStates[canvasId].ctx.beginPath(); };
  c.onmousemove = function(e) { _draw(e, canvasId); };
  c.ontouchstart = function(e) { e.preventDefault(); _drawStates[canvasId].drawing = true; _drawTouch(e, canvasId); };
  c.ontouchmove = function(e) { e.preventDefault(); _drawTouch(e, canvasId); };
  c.ontouchend = function() { _drawStates[canvasId].drawing = false; };
}
function _draw(e, id) {
  var s = _drawStates[id]; if (!s || !s.drawing) return;
  var r = s.ctx.canvas.getBoundingClientRect();
  s.ctx.lineWidth = s.width; s.ctx.lineCap = 'round'; s.ctx.strokeStyle = s.color;
  s.ctx.lineTo((e.clientX - r.left), (e.clientY - r.top)); s.ctx.stroke(); s.ctx.beginPath();
  s.ctx.moveTo((e.clientX - r.left), (e.clientY - r.top));
}
function _drawTouch(e, id) {
  var s = _drawStates[id]; if (!s || !s.drawing) return;
  var r = s.ctx.canvas.getBoundingClientRect();
  var t = e.touches[0];
  s.ctx.lineWidth = s.width; s.ctx.lineCap = 'round'; s.ctx.strokeStyle = s.color;
  s.ctx.lineTo((t.clientX - r.left), (t.clientY - r.top)); s.ctx.stroke(); s.ctx.beginPath();
  s.ctx.moveTo((t.clientX - r.left), (t.clientY - r.top));
}
function setDrawColor(id, c) { if(_drawStates[id]) _drawStates[id].color = c; }
function setDrawWidth(id, w) { if(_drawStates[id]) _drawStates[id].width = w; }
function clearCanvas(id) { var c = document.getElementById(id); if(c) c.getContext('2d').clearRect(0,0,c.width,c.height); }

// Calculator
function runCalc(offerId) {
  var expr = document.getElementById('calc-expr-' + offerId).value;
  var resultEl = document.getElementById('calc-result-' + offerId);
  var historyEl = document.getElementById('calc-history-' + offerId);
  try {
    var sanitized = expr.replace(/sqrt\(/g, 'Math.sqrt(').replace(/\^/g, '**');
    var result = eval(sanitized);
    resultEl.textContent = expr + ' = ' + result;
    historyEl.textContent += expr + ' = ' + result + '\n';
  } catch(e) {
    resultEl.textContent = '错误: ' + e.message;
  }
}
function insertCalc(offerId, op) {
  var el = document.getElementById('calc-expr-' + offerId);
  el.value += op; el.focus();
}

// Code execution (via shell endpoint)
function runCode(offerId) {
  var code = document.getElementById('code-editor-' + offerId).value;
  var lang = document.getElementById('code-lang-' + offerId).value;
  var output = document.getElementById('code-output-' + offerId);
  output.style.display = 'block'; output.textContent = '运行中...';
  fetch('/tree/shell/exec', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({command: lang === 'python' ? 'python -c ' + JSON.stringify(code) : lang === 'bash' ? code : 'node -e ' + JSON.stringify(code)}),
  }).then(r => r.text()).then(html => {
    var tmp = document.createElement('div'); tmp.innerHTML = html;
    var pre = tmp.querySelector('pre');
    output.textContent = pre ? pre.textContent : '执行完成';
  });
}

// Table helpers
function updateTableRow(offerId, rowIdx) {}
function addTableRow(offerId) {}
function collectTableData(offerId) {
  var rows = []; var card = document.getElementById('tool-' + offerId);
  if (card) { card.querySelectorAll('tr').forEach(function(tr, i) {
    var cells = []; tr.querySelectorAll('input').forEach(function(inp) { cells.push(inp.value); });
    if (cells.length) rows.push(cells);
  });}
  submitToolResult(offerId, 'table', {rows: rows});
}

// Form data collection
function collectFormData(cardId) {
  var data = {}; var card = document.getElementById(cardId);
  if (card) { card.querySelectorAll('input,select,textarea').forEach(function(el) {
    if (el.name) data[el.name] = el.value;
  });}
  return data;
}

// Submit tool result back to AI context
function submitToolResult(offerId, toolType, resultData) {
  var card = document.getElementById('tool-' + offerId);
  fetch('/tree/tools/result', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({offer_id: offerId, tool_type: toolType, result: resultData}),
  }).then(r => r.text()).then(html => {
    var chatLog = document.getElementById('lc-chat-log') || document.getElementById('chat-log');
    if (chatLog) {
      var div = document.createElement('div');
      div.innerHTML = '<div class="msg user"><div class="who">你 · ' + toolType + '</div><div class="text">✅ 已发送给AI</div></div>';
      chatLog.appendChild(div.firstElementChild);
      chatLog.scrollTop = chatLog.scrollHeight;
    }
    if (card) {
      card.style.opacity = '0.5';
      card.querySelector('button').textContent = '✅ 已发送';
      setTimeout(function() { if(card) card.remove(); }, 2000);
    }
  });
}
"""
