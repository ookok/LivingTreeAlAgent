"""
脚本注入引擎 (InjectionEngine)
==============================

核心思想：向目标网页注入JavaScript脚本，实现功能增强

注入类型：
1. 填表助手 - 自动填充表单
2. 绘图覆盖 - 在页面上绘制Canvas图形
3. 监控脚本 - 监控用户行为
4. 悬浮工具栏 - 提供快捷操作
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class InjectionType(Enum):
    """注入类型"""
    FORM_ASSISTANT = "form_assistant"
    DRAWING_OVERLAY = "drawing_overlay"
    MONITORING = "monitoring"
    FLOATING_TOOLBAR = "floating_toolbar"
    AI_PANEL = "ai_panel"
    CUSTOM = "custom"


@dataclass
class InjectionRule:
    """注入规则"""
    rule_id: str
    name: str
    url_pattern: str  # URL正则模式
    injection_type: InjectionType
    enabled: bool = True
    priority: int = 0

    # 注入内容
    js_files: List[str] = field(default_factory=list)  # JS文件列表
    css_files: List[str] = field(default_factory=list)  # CSS文件列表
    inline_js: str = ""   # 内联JS
    inline_css: str = ""  # 内联CSS

    # 配置
    config: Dict[str, Any] = field(default_factory=dict)

    # 触发条件
    trigger_on_load: bool = True
    trigger_on_form: bool = False
    trigger_on_click: bool = False


@dataclass
class InjectionResult:
    """注入结果"""
    url: str
    injected: bool
    scripts: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class InjectionEngine:
    """
    脚本注入引擎

    核心能力：
    1. 规则管理 - 添加/删除/启用/禁用注入规则
    2. 内容注入 - 向HTML注入JS/CSS
    3. 触发控制 - 基于URL或用户行为触发
    4. 日志记录 - 记录注入历史
    """

    def __init__(self):
        self.rules: Dict[str, InjectionRule] = {}
        self.injection_history: List[InjectionResult] = []

        # 内置规则
        self._register_builtin_rules()

    def _register_builtin_rules(self):
        """注册内置规则"""

        # 填表助手规则
        self.add_rule(InjectionRule(
            rule_id="form_assistant_gov",
            name="政府网站填表助手",
            url_pattern=r"\.gov\.cn",
            injection_type=InjectionType.FORM_ASSISTANT,
            priority=10,
            inline_js=self._get_form_assistant_js(),
            inline_css=self._get_form_assistant_css()
        ))

        # 绘图覆盖规则（用于环评地图）
        self.add_rule(InjectionRule(
            rule_id="drawing_overlay_map",
            name="地图绘图覆盖",
            url_pattern=r"amap|gaode|baidu.*map|tianapi|tianditu",
            injection_type=InjectionType.DRAWING_OVERLAY,
            priority=10,
            inline_js=self._get_drawing_overlay_js(),
            inline_css=self._get_drawing_overlay_css()
        ))

        # 悬浮工具栏规则
        self.add_rule(InjectionRule(
            rule_id="floating_toolbar",
            name="悬浮工具栏",
            url_pattern=".*",  # 所有页面
            injection_type=InjectionType.FLOATING_TOOLBAR,
            priority=1,
            inline_js=self._get_floating_toolbar_js(),
            inline_css=self._get_floating_toolbar_css()
        ))

        # AI面板规则
        self.add_rule(InjectionRule(
            rule_id="ai_panel",
            name="AI助手面板",
            url_pattern=".*",
            injection_type=InjectionType.AI_PANEL,
            priority=1,
            inline_js=self._get_ai_panel_js(),
            inline_css=self._get_ai_panel_css()
        ))

    def add_rule(self, rule: InjectionRule):
        """添加注入规则"""
        self.rules[rule.rule_id] = rule

    def remove_rule(self, rule_id: str):
        """删除注入规则"""
        if rule_id in self.rules:
            del self.rules[rule_id]

    def enable_rule(self, rule_id: str):
        """启用规则"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True

    def disable_rule(self, rule_id: str):
        """禁用规则"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False

    def get_matched_rules(self, url: str) -> List[InjectionRule]:
        """获取匹配的规则"""
        matched = []
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            if re.search(rule.url_pattern, url, re.IGNORECASE):
                matched.append(rule)

        # 按优先级排序
        return sorted(matched, key=lambda r: r.priority, reverse=True)

    async def inject(
        self,
        html: str,
        url: str,
        context: Optional[Dict[str, Any]] = None
    ) -> InjectionResult:
        """
        向HTML注入脚本

        Args:
            html: 原始HTML
            url: 页面URL
            context: 额外上下文

        Returns:
            InjectionResult: 注入结果
        """
        result = InjectionResult(url=url, injected=False)

        # 获取匹配的规则
        matched_rules = self.get_matched_rules(url)

        if not matched_rules:
            return result

        # 合并所有注入内容
        all_js = []
        all_css = []

        for rule in matched_rules:
            if rule.inline_js:
                all_js.append(rule.inline_js)
            if rule.inline_css:
                all_css.append(rule.inline_css)
            all_js.extend(rule.js_files)

        # 构建注入脚本
        injected_scripts = []

        # CSS注入
        if all_css:
            css = f"<style>{''.join(all_css)}</style>"
            html = self._inject_before(html, "</head>", css)
            injected_scripts.append("CSS")

        # JS注入（注入到</body>前）
        if all_js:
            js = f"<script>{''.join(all_js)}</script>"
            html, injected = self._inject_after(html, "<body", js)
            if injected:
                injected_scripts.append("JS")

        result.injected = len(injected_scripts) > 0
        result.scripts = injected_scripts
        self.injection_history.append(result)

        return result

    def _inject_before(self, html: str, marker: str, content: str) -> str:
        """在指定标记前注入"""
        if marker in html:
            return html.replace(marker, content + marker, 1)
        return html

    def _inject_after(self, html: str, marker: str, content: str) -> tuple:
        """在指定标记后注入"""
        idx = html.find(marker)
        if idx != -1:
            insert_pos = idx + len(marker)
            # 找到标记后的第一个 >
            end_tag = html.find(">", insert_pos)
            if end_tag != -1:
                new_html = html[:end_tag + 1] + content + html[end_tag + 1:]
                return new_html, True
        return html, False

    # ============ 内置JS/CSS ============

    def _get_form_assistant_js(self) -> str:
        """填表助手JS"""
        return '''
(function() {
    window.HyperOS_FormAssistant = {
        version: '1.0',
        data: {},
        init: function() {
            this.connect();
            this.detectForms();
            this.createToolbar();
        },
        connect: function() {
            const ws = new WebSocket('ws://localhost:8765');
            ws.onmessage = (e) => {
                const data = JSON.parse(e.data);
                if (data.type === 'autofill') this.applyData(data.fields);
            };
            this.ws = ws;
        },
        detectForms: function() {
            const forms = document.querySelectorAll('form');
            forms.forEach(form => {
                form.addEventListener('submit', (e) => {
                    e.preventDefault();
                    const data = this.collectFormData(form);
                    this.ws.send(JSON.stringify({type: 'form_submit', data: data}));
                });
            });
        },
        createToolbar: function() {
            const toolbar = document.createElement('div');
            toolbar.id = 'hyper-toolbar';
            toolbar.innerHTML = '<button onclick="HyperOS_FormAssistant.showPanel()">AI填表</button>';
            document.body.appendChild(toolbar);
        },
        collectFormData: function(form) {
            const data = {};
            form.querySelectorAll('input, select, textarea').forEach(el => {
                if (el.name) data[el.name] = el.value;
            });
            return data;
        },
        applyData: function(fields) {
            fields.forEach(f => {
                const el = document.querySelector(`[name="${f.name}"]`);
                if (el) {
                    el.value = f.value;
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                }
            });
        },
        showPanel: function() {
            alert('HyperOS Form Assistant Panel');
        }
    };
    if (document.readyState === 'complete') {
        window.HyperOS_FormAssistant.init();
    } else {
        window.addEventListener('load', () => window.HyperOS_FormAssistant.init());
    }
})();
'''

    def _get_form_assistant_css(self) -> str:
        """填表助手CSS"""
        return '''
#hyper-toolbar {
    position: fixed;
    bottom: 20px;
    right: 20px;
    z-index: 999999;
    background: #3498db;
    padding: 10px;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
}
#hyper-toolbar button {
    background: white;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    cursor: pointer;
    font-weight: bold;
}
#hyper-toolbar button:hover { background: #f0f0f0; }
'''

    def _get_drawing_overlay_js(self) -> str:
        """绘图覆盖JS"""
        return '''
window.HyperOS_Drawing = {
    canvas: null,
    ctx: null,
    shapes: [],
    init: function() {
        this.createCanvas();
        this.createToolbar();
        this.connect();
    },
    createCanvas: function() {
        this.canvas = document.createElement('canvas');
        this.canvas.id = 'hyper-drawing-canvas';
        this.canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:9998;';
        document.body.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');
        this.resize();
        window.addEventListener('resize', () => this.resize());
    },
    resize: function() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    },
    createToolbar: function() {
        const toolbar = document.createElement('div');
        toolbar.id = 'hyper-drawing-toolbar';
        toolbar.innerHTML = '<button onclick="HyperOS_Drawing.clear()">清除</button><button onclick="HyperOS_Drawing.circle()">画圆</button><button onclick="HyperOS_Drawing.polygon()">多边形</button>';
        toolbar.style.cssText = 'position:fixed;top:10px;right:10px;z-index:9999;background:white;padding:10px;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,0.2);';
        document.body.appendChild(toolbar);
    },
    connect: function() {
        const ws = new WebSocket('ws://localhost:8765');
        ws.onmessage = (e) => {
            const data = JSON.parse(e.data);
            if (data.type === 'draw_command') this.drawShape(data.shape, data.coords, data.style);
        };
        this.ws = ws;
    },
    drawShape: function(shape, coords, style) {
        this.ctx.beginPath();
        if (shape === 'circle') {
            this.ctx.arc(coords[0].x, coords[0].y, coords[0].r || 50, 0, Math.PI * 2);
        } else if (shape === 'polygon') {
            coords.forEach((c, i) => {
                if (i === 0) this.ctx.moveTo(c.x, c.y);
                else this.ctx.lineTo(c.x, c.y);
            });
            this.ctx.closePath();
        }
        this.ctx.strokeStyle = style.color || 'red';
        this.ctx.lineWidth = style.width || 2;
        this.ctx.stroke();
    },
    clear: function() { this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height); }
};
window.addEventListener('load', () => window.HyperOS_Drawing.init());
'''

    def _get_drawing_overlay_css(self) -> str:
        return ''

    def _get_floating_toolbar_js(self) -> str:
        """悬浮工具栏JS"""
        return '''
window.HyperOS_Toolbar = {
    init: function() {
        this.create();
        this.addButtons();
    },
    create: function() {
        const div = document.createElement('div');
        div.id = 'hyperos-floating-toolbar';
        div.style.cssText = 'position:fixed;bottom:20px;left:20px;z-index:99999;display:flex;gap:5px;';
        document.body.appendChild(div);
    },
    addButtons: function() {
        const buttons = [
            {icon: '📋', title: '填表助手', action: () => alert('填表助手')},
            {icon: '🎨', title: '绘图', action: () => alert('绘图工具')},
            {icon: '🤖', title: 'AI分析', action: () => alert('AI分析')},
            {icon: '📊', title: '数据提取', action: () => alert('数据提取')}
        ];
        const toolbar = document.getElementById('hyperos-floating-toolbar');
        buttons.forEach(b => {
            const btn = document.createElement('button');
            btn.textContent = b.icon;
            btn.title = b.title;
            btn.style.cssText = 'width:40px;height:40px;border-radius:50%;border:none;background:#3498db;color:white;font-size:18px;cursor:pointer;box-shadow:0 2px 10px rgba(0,0,0,0.2);';
            btn.onclick = b.action;
            toolbar.appendChild(btn);
        });
    }
};
if (document.readyState === 'complete') window.HyperOS_Toolbar.init();
else window.addEventListener('load', () => window.HyperOS_Toolbar.init());
'''

    def _get_floating_toolbar_css(self) -> str:
        return ''

    def _get_ai_panel_js(self) -> str:
        """AI面板JS"""
        return '''
window.HyperOS_AIPanel = {
    panel: null,
    init: function() {
        this.create();
    },
    create: function() {
        this.panel = document.createElement('div');
        this.panel.id = 'hyperos-ai-panel';
        this.panel.innerHTML = '<div class="header">🤖 HyperOS AI</div><div class="content"><textarea placeholder="输入问题..."></textarea><button>发送</button></div>';
        this.panel.style.cssText = 'position:fixed;top:10px;right:10px;width:300px;max-height:400px;background:white;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.15);z-index:99999;overflow:hidden;display:none;';
        document.body.appendChild(this.panel);
        document.body.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.shiftKey && e.key === 'A') this.toggle();
        });
    },
    toggle: function() {
        this.panel.style.display = this.panel.style.display === 'none' ? 'block' : 'none';
    },
    show: function() { this.panel.style.display = 'block'; },
    hide: function() { this.panel.style.display = 'none'; }
};
window.addEventListener('load', () => window.HyperOS_AIPanel.init());
'''

    def _get_ai_panel_css(self) -> str:
        return '''
#hyperos-ai-panel .header { background: #3498db; color: white; padding: 12px; font-weight: bold; }
#hyperos-ai-panel .content { padding: 12px; }
#hyperos-ai-panel textarea { width: 100%; height: 80px; border: 1px solid #ddd; border-radius: 8px; padding: 8px; resize: none; }
#hyperos-ai-panel button { width: 100%; margin-top: 8px; padding: 10px; background: #3498db; color: white; border: none; border-radius: 8px; cursor: pointer; }
'''


# 全局实例
_injection_engine_instance: Optional[InjectionEngine] = None


def get_injection_engine() -> InjectionEngine:
    """获取注入引擎全局实例"""
    global _injection_engine_instance
    if _injection_engine_instance is None:
        _injection_engine_instance = InjectionEngine()
    return _injection_engine_instance