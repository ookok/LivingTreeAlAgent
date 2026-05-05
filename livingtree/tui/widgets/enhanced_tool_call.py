"""EnhancedToolCall — Toad ToolCall widget + system tools/skills/MCP/roles + election badge.

Display per-message L0-L3 election badge. Integrates 22 MCP tools,
4 physical models, 8 expert roles, and skill discovery into Toad's
native ToolCall rendering pipeline.
"""
from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Static
from textual.binding import Binding
from textual import on
from textual.message import Message


class ToolInvokeRequest(Message):
    """Request to invoke a system tool."""
    def __init__(self, tool_name: str, params: dict):
        super().__init__()
        self.tool_name = tool_name
        self.params = params


class ElectionBadge(Static):
    """A compact badge showing L0-L3 per-message election status.

    Single line when merged:  ⚡siliconflow-flash
    Per-layer when different: L0:longcat · L1:deepseek · L3:opencode-serve
    """

    def set_election(self, badge_text: str):
        if badge_text:
            self.update(badge_text)
            self.display = True
        else:
            self.display = False


# ═══ System tool registry ═══

SYSTEM_TOOLS: dict[str, dict] = {
    # ── File operations ──
    "file_read": {
        "name": "读取文件",
        "category": "file",
        "description": "读取文件内容（支持超大文件流式读取）",
        "params": {"path": "文件路径", "max_chars": "最大字符数(默认10000)"},
        "icon": "📖",
    },
    "file_write": {
        "name": "写入文件",
        "category": "file",
        "description": "写入/保存文件（自动选择目录: .py→src/ .docx→output/ .md→docs/）",
        "params": {"filename": "文件名", "content": "文件内容"},
        "icon": "💾",
    },
    "file_replace": {
        "name": "替换文件内容",
        "category": "file",
        "description": "精准替换文件内容（正则/章节/行范围/JSON路径），原子写入",
        "params": {"path": "文件路径", "mode": "pattern|section|lines|json", "target": "替换目标", "replacement": "新内容"},
        "icon": "✏️",
    },
    "file_find": {
        "name": "搜索文件",
        "category": "file",
        "description": "全域文件搜索（文件系统+代码+文档+历史+知识库 6路并行）",
        "params": {"query": "搜索关键词"},
        "icon": "🔍",
    },

    # ── Physical models (EIA) ──
    "gaussian_plume": {
        "name": "高斯烟羽模型",
        "category": "physics",
        "description": "大气污染物扩散高斯烟羽模型 (GB/T3840-1991)",
        "formula": "C(x,y,z) = Q/(2π·u·σy·σz) · exp(-y²/2σy²) · [exp(-(z-He)²/2σz²) + exp(-(z+He)²/2σz²)]",
        "params": {"Q": "排放速率 g/s", "u": "风速 m/s", "x": "下风向距离 m",
                   "y": "横向距离 m", "z": "受体高度 m", "stability": "稳定度 A-F",
                   "He": "有效源高 m"},
        "output": "落地浓度 C (g/m³)",
        "standard": "对比GB3095-2012环境空气质量标准",
        "icon": "🌫",
    },
    "noise_attenuation": {
        "name": "噪声衰减模型",
        "category": "physics",
        "description": "点声源几何发散衰减计算 (GB/T 17247)",
        "formula": "Lp(r) = Lw - 20·log₁₀(r) - 11  (自由场半球面)",
        "params": {"Lw": "声功率级 dB", "r": "距离 m", "ground_type": "地面类型 hard/soft"},
        "output": "声压级 Lp (dB)",
        "standard": "对比GB3096-2008声环境质量标准",
        "icon": "🔊",
    },
    "dispersion_coeff": {
        "name": "扩散系数",
        "category": "physics",
        "description": "Pasquill-Gifford 扩散系数 (σy, σz) 计算",
        "formula": "σy = a₁·x^b₁  (a₁=f(stability, x)); σz = a₂·x^b₂  (a₂=f(stability))",
        "params": {"x": "距离 m", "stability": "稳定度 A-F"},
        "output": "σy, σz (m)",
        "standard": "GB/T3840-1991 附录B 扩散参数",
        "icon": "📐",
    },

    # ── Code analysis ──
    "build_code_graph": {
        "name": "代码图谱",
        "category": "code",
        "description": "构建/重建代码知识图谱",
        "params": {"path": "项目路径"},
        "icon": "🕸",
    },
    "blast_radius": {
        "name": "影响范围",
        "category": "code",
        "description": "分析代码变更的波及范围",
        "params": {"files": "变更文件列表"},
        "icon": "💥",
    },
    "search_code": {
        "name": "代码搜索",
        "category": "code",
        "description": "按名称/路径搜索代码实体",
        "params": {"query": "搜索关键词"},
        "icon": "🔍",
    },

    # ── Knowledge ──
    "search_knowledge": {
        "name": "知识搜索",
        "category": "knowledge",
        "description": "搜索知识库",
        "params": {"query": "搜索内容"},
        "icon": "📚",
    },
    "detect_knowledge_gaps": {
        "name": "知识缺口检测",
        "category": "knowledge",
        "description": "自动检测知识空白领域",
        "params": {},
        "icon": "🔬",
    },

    # ── Cell training ──
    "train_cell": {
        "name": "训练细胞",
        "category": "cell",
        "description": "在领域数据上训练 AI 细胞",
        "params": {"cell_name": "细胞名称", "data": "训练数据"},
        "icon": "🧬",
    },
    "drill_train": {
        "name": "深度训练",
        "category": "cell",
        "description": "MS-SWIFT 自动化训练 (LoRA/QLoRA/全参数)",
        "params": {"cell_name": "细胞名称", "model_name": "模型名", "training_type": "lora/full/distill"},
        "icon": "🔧",
    },
    "absorb_codebase": {
        "name": "吸收代码库",
        "category": "cell",
        "description": "吸收代码模式到 AI 细胞",
        "params": {"path": "代码路径"},
        "icon": "🧠",
    },

    # ── Generation ──
    "generate_code": {
        "name": "代码生成",
        "category": "gen",
        "description": "AI 生成带注释的代码",
        "params": {"name": "名称", "description": "描述", "language": "编程语言", "domain": "领域"},
        "icon": "💻",
    },
    "generate_report": {
        "name": "报告生成",
        "category": "gen",
        "description": "生成工业级报告 (环评/应急预案/验收/可行性)",
        "params": {"template_type": "报告类型", "data": "报告数据"},
        "icon": "📄",
    },
    "generate_diagram": {
        "name": "图表生成",
        "category": "gen",
        "description": "AI 生成流程图/架构图/时序图 (ASCII)",
        "params": {"description": "图表描述"},
        "icon": "📊",
    },

    # ── Search ──
    "unified_search": {
        "name": "聚合搜索",
        "category": "search",
        "description": "多引擎搜索 (SparkSearch → DDGSearch)",
        "params": {"query": "搜索关键词", "limit": "结果数量"},
        "icon": "🔎",
    },

    # ── System ──
    "get_status": {
        "name": "系统状态",
        "category": "system",
        "description": "获取系统运行状态",
        "params": {},
        "icon": "📡",
    },
    "chat": {
        "name": "AI 对话",
        "category": "chat",
        "description": "发送消息到 LivingTree AI",
        "params": {"message": "消息内容"},
        "icon": "💬",
    },
    "analyze": {
        "name": "深度分析",
        "category": "chat",
        "description": "链式推理深度分析",
        "params": {"topic": "分析主题"},
        "icon": "🧪",
    },

    # ── Expert roles ──
    "full_stack_engineer": {
        "name": "全栈工程师",
        "category": "role",
        "description": "Python/JS/React/SQL 全栈开发",
        "params": {"task": "任务描述"},
        "icon": "👨‍💻",
    },
    "data_analyst": {
        "name": "数据分析师",
        "category": "role",
        "description": "数据分析、Python、SQL",
        "params": {"task": "任务描述"},
        "icon": "📈",
    },
    "ai_researcher": {
        "name": "AI研究员",
        "category": "role",
        "description": "ML、Python、算法研究",
        "params": {"task": "任务描述"},
        "icon": "🤖",
    },
}

EXPERT_ROLES = {
    "full_stack_engineer": "全栈工程师 — Python/JS/React/SQL 全栈开发",
    "ui_designer": "UI 设计师 — 界面设计、原型、样式指南",
    "product_manager": "产品经理 — PRD、用户故事、路线图",
    "data_analyst": "数据分析师 — 分析报告、可视化、洞察",
    "marketing_specialist": "营销专家 — 营销计划、内容策略",
    "ai_researcher": "AI 研究员 — 算法模型、技术报告、论文",
    "devops_engineer": "DevOps 工程师 — 部署脚本、监控配置",
    "qa_engineer": "QA 工程师 — 测试计划、测试报告、Bug列表",
}

MCP_METHODS = {
    "build_code_graph": "构建代码图谱",
    "blast_radius": "影响分析",
    "get_callers": "查找调用者",
    "get_callees": "查找被调用者",
    "search_code": "搜索代码",
    "search_knowledge": "搜索知识库",
    "generate_code": "生成代码",
    "generate_report": "生成报告",
    "train_cell": "训练细胞",
    "absorb_codebase": "吸收代码库",
    "get_status": "系统状态",
}


def get_tool(tool_name: str) -> dict | None:
    return SYSTEM_TOOLS.get(tool_name)


def get_all_tools(category: str = "") -> list[dict]:
    tools = list(SYSTEM_TOOLS.values())
    if category:
        return [t for t in tools if t["category"] == category]
    return tools


def format_tool_list() -> str:
    """Format all available tools for display."""
    categories: dict[str, list[dict]] = {}
    for t in SYSTEM_TOOLS.values():
        cat = t["category"]
        categories.setdefault(cat, []).append(t)

    lines = ["## 🛠 System Tools & Roles", ""]
    for cat, tools in sorted(categories.items()):
        lines.append(f"### {cat}")
        for t in tools:
            lines.append(f"- {t['icon']} **{t['name']}** — {t['description']}")
        lines.append("")
    return "\n".join(lines)
