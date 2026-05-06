"""CommandRouter — natural language command dispatching with rich error guidance.

    Compresses 60+ slash commands into 8 unified commands.
    Users speak naturally; system figures out intent.

    8 commands:
      /ask     "搜一下transformer最新进展"
      /do      "执行这个SQL查询"
      /files   "帮我修改config.py把端口改成8888"
      /learn   "挖掘一下项目里的知识"
      /check   "检查系统状态"
      /docs    "批量生成10份报告"
      /team    "查看在线节点"
      /help    "怎么用这个系统"

    Each command auto-detects sub-action from natural language and provides
    step-by-step guidance when input is ambiguous or wrong.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# ═══ Command Definitions ═══

COMMANDS = {
    "ask": {
        "icon": "🔍",
        "title": "搜索与查资料",
        "description": "搜索互联网、论文、代码库、本地知识库",
        "examples": [
            ("搜一下transformer最新进展", "多引擎搜索+LLM重排"),
            ("打开这个网页 https://arxiv.org/abs/1706.03762", "抓取网页内容"),
            ("查一下最近有什么新项目", "GitHub Trending"),
            ("这篇论文讲了什么", "解析PDF+提取方法论"),
            ("有没有关于分布式系统的推荐？", "深度搜索技术方案"),
            ("记住：以后环评报告水环境章节用HJ 2.3-2018", "存入知识库"),
        ],
        "actions": ["search", "web", "brain", "fetch", "recall", "factcheck"],
        "fallback": "告诉我你想查什么，比如：'搜一下最新的大模型论文'、'打开这个网页链接'、'查一下数据库'",
    },
    "do": {
        "icon": "⚡",
        "title": "执行操作",
        "description": "运行命令、查询数据库、计算模型、修改代码",
        "examples": [
            ("查看代码差异", "git diff"),
            ("执行 SELECT * FROM users", "SQL查询"),
            ("帮我计算高斯烟羽 Q=5 u=3 x=1000", "物理模型计算"),
            ("帮我改代码，加一个缓存层", "SelfModifier"),
            ("写一个对比两个CSV文件的工具", "ToolSynthesis"),
            ("安装这个依赖包", "shell pip install"),
            ("定时每天9点备份数据库", "创建定时任务"),
        ],
        "actions": ["shell", "sql", "git", "compute", "modify", "synthesize", "cron", "evolvetool"],
        "fallback": "告诉我要做什么，比如：'执行SQL查询'、'查看代码变更'、'帮我计算高斯扩散'、'帮我写个工具'",
    },
    "files": {
        "icon": "📁",
        "title": "文件管理",
        "description": "查找、修改、保存、备份文件",
        "examples": [
            ("找一下认证相关的代码", "代码搜索"),
            ("把config.py的端口从8100改成8888", "精确替换"),
            ("扫描项目里的重复代码", "去重分析"),
            ("备份一下config.py", "语义备份"),
            ("生成一份港口环评报告模板", "模板渲染+实例化"),
            ("打补丁修复端口配置", "补丁管理"),
            ("监控文件变化自动索引", "文件监控"),
        ],
        "actions": ["find", "save", "replace", "locate", "dedup", "patch", "render", "backup", "watch", "history"],
        "fallback": "告诉我要对文件做什么，比如：'找认证代码'、'改config.yaml的端口'、'备份重要文件'",
    },
    "learn": {
        "icon": "🧠",
        "title": "学习与进化",
        "description": "自动从文档和互联网学习新知识",
        "examples": [
            ("挖掘这个项目的知识", "自动知识提取"),
            ("整理今天的对话内容", "知识巩固"),
            ("看看AI大脑学到了什么", "学习摘要"),
            ("我哪类报告写得最差", "弱点分析"),
            ("学习100份环评报告的写作风格", "文档风格学习"),
            ("帮我学一下安全评价报告的写法", "跨域迁移学习"),
            ("更新系统", "自我进化"),
        ],
        "actions": ["mine", "consolidate", "evolve", "market", "practice", "brain"],
        "fallback": "告诉我你想学什么，比如：'挖掘项目知识'、'整理今天的内容'、'学习报告写作风格'、'看看哪个写得差'",
    },
    "check": {
        "icon": "📊",
        "title": "检查与诊断",
        "description": "系统状态、数据质量、合规审查、安全审计",
        "examples": [
            ("系统状态怎么样", "CPU/内存/网络/磁盘"),
            ("检查一下这段代码的质量", "AgentEval输出评测"),
            ("这个模型的信任度如何", "信任评分"),
            ("这段话事实准确吗", "事实核查"),
            ("合规检查这份报告", "GB标准自检"),
            ("这个数据的来源是什么", "数据血缘追溯"),
            ("最近有什么错误", "活动日志+错误汇总"),
            ("费用统计", "token成本+代理费用"),
        ],
        "actions": ["status", "sysinfo", "eval", "trust", "factcheck", "compliance", "cost", "activity", "lineage", "semdiff", "gaps"],
        "fallback": "告诉我要检查什么，比如：'系统状态'、'检查代码质量'、'数据来源追溯'、'费用统计'",
    },
    "docs": {
        "icon": "📄",
        "title": "文档生成",
        "description": "批量生成报告、管理模板、生成系统文档",
        "examples": [
            ("批量生成10份环评报告，数据在data.csv", "CSV→并行LLM→DOCX"),
            ("创建一个新的环评报告项目", "项目初始化向导"),
            ("管理我的报告模板", "模板版本管理"),
            ("生成系统使用文档", "自文档系统"),
            ("根据模板生成报告", "模板实例化"),
            ("帮我收集报告需要的数据", "数据收集向导"),
        ],
        "actions": ["batch", "template", "compliance", "selfdocs", "plan"],
        "fallback": "告诉我要生成什么，比如：'批量生成报告'、'创建一个新项目'、'管理模板'、'生成系统文档'",
    },
    "team": {
        "icon": "🌐",
        "title": "协作与网络",
        "description": "P2P通信、用户管理、辩论决策、消息推送",
        "examples": [
            ("查看在线用户", "P2P节点列表"),
            ("邀请同事加入", "好友管理"),
            ("发起一个技术方案辩论", "多角色辩论"),
            ("我要用deepseek模型", "锁定模型"),
            ("切换到另一个方案继续讨论", "对话分支切换"),
            ("查看我的使用统计", "用户画像"),
            ("用微信发通知", "消息网关"),
        ],
        "actions": ["peers", "connect", "login", "debate", "branch", "profile", "prefer", "binding", "gateway", "snapshot"],
        "fallback": "告诉我要做什么，比如：'查看在线用户'、'发起辩论'、'切换到对话分支'、'锁定模型'",
    },
    "network": {
        "icon": "🌐",
        "title": "网络加速",
        "description": "科学上网代理服务 /scinet — 加速 GitHub/HuggingFace/Google/StackOverflow 等海外站点 (学习用途)",
        "examples": [
            ("/scinet start", "启动代理服务 (端口7890)"),
            ("/scinet stop", "停止代理服务"),
            ("/scinet status", "查看服务状态"),
            ("/scinet test", "测试海外站点连通性"),
            ("/scinet pac", "获取PAC自动配置URL"),
        ],
        "actions": ["start", "stop", "status", "test", "pac"],
        "fallback": "使用 /scinet start 启动代理服务, /scinet stop 停止, /scinet status 查看状态",
    },
    "seed": {
        "icon": "🌱",
        "title": "角色初始化",
        "description": "一键配置 — 选择你的职业角色，自动设置所有模块",
        "examples": [
            ("/seed eia_engineer", "环评工程师 — 自动注册政府公告站"),
            ("/seed env_engineer", "环保工程师 — 配置设备+监测提醒"),
            ("/seed equipment_supplier", "设备供应商 — 招标机会追踪"),
            ("/seed monitoring_company", "监测公司 — 验收+运维机会"),
            ("/seed consultant", "咨询顾问 — 政策合规追踪"),
        ],
        "actions": ["plant", "list", "guide"],
        "fallback": "使用 /seed <角色名> 一键配置，角色: eia_engineer, env_engineer, equipment_supplier, monitoring_company, consultant",
    },
}

COMMAND_LIST = list(COMMANDS.keys())

HELP_INTRO = """🌳 LivingTree 命令指南

这是你的AI助手，支持8个主命令。你可以用自然语言描述需求：

{commands}

💡 提示：
  - 所有命令都支持自然语言输入，不用记语法
  - 遇到问题直接描述，系统会引导你
  - 使用 /help <命令> 查看某个命令的详细示例
  - 直接对话也可以，不一定要用命令"""


def format_command_help(cmd_name: str) -> str:
    """Generate detailed help for a single command."""
    cmd = COMMANDS.get(cmd_name)
    if not cmd:
        return f"未知命令: {cmd_name}\n\n可用命令: {', '.join(COMMAND_LIST)}\n试试 /help 查看所有命令。"

    lines = [f"## {cmd['icon']} /{cmd_name} — {cmd['title']}", "", cmd['description'], "", "**使用示例:**", ""]

    for example, explanation in cmd['examples']:
        lines.append(f"  > {example}")
        lines.append(f"    （{explanation}）")
        lines.append("")

    lines.append(f"💡 如果你输入不完整，我会引导你：'{{cmd['fallback']}}'")
    return "\n".join(lines)


def format_all_help() -> str:
    """Generate the full help page."""
    lines = ["## 🌳 LivingTree 命令指南", "",
             "8个主命令，支持自然语言。直接描述需求，不用记语法。", ""]

    for name, cmd in COMMANDS.items():
        lines.append(f"{cmd['icon']} **/{name}** — {cmd['title']}")
        lines.append(f"  {cmd['description']}")
        example = cmd['examples'][0][0]
        lines.append(f"  例: \"{example}\"")
        lines.append("")

    lines.append("💡 详细帮助: /help <命令名>  如: /help ask")
    lines.append("💡 所有命令都支持自然语言，比如直接说'帮我找个东西'而不是'/ask search xxx'")
    return "\n".join(lines)


def detect_intent(text: str) -> dict[str, Any]:
    """Detect which command and action from natural language input.

    Uses keyword matching + priority scoring. Falls back to 'ask' (most common).

    Returns {command, action, params, confidence}
    """
    text_lower = text.lower().strip()
    scores = {}

    for cmd_name, cmd in COMMANDS.items():
        score = 0.0

        # Exact command name match
        if text_lower == cmd_name:
            score += 10.0

        # Check command-specific keywords
        keywords = {
            "ask": ["搜", "查", "找", "搜索", "打开", "论文", "网页", "链接", "资料", "信息", "记住", "记下"],
            "do": ["执行", "运行", "计算", "改代码", "写工具", "写一个", "算一下", "安装", "定时", "sql", "git", "修改代码", "修复"],
            "files": ["文件", "修改", "改", "保存", "备份", "找", "定位", "扫描", "重复", "补丁", "模板", "替换", "端口", "config"],
            "learn": ["学", "挖掘", "整理", "进化", "知识", "弱点", "风格", "练习", "更新", "升级"],
            "check": ["检查", "状态", "诊断", "质量", "审计", "安全", "来源", "来源追溯", "合规", "费用", "统计", "错误"],
            "docs": ["报告", "生成", "文档", "批量", "项目", "模板", "收集数据", "数据收集"],
            "team": ["节点", "在线", "同事", "辩论", "用户", "偏好", "模型", "锁定", "分支", "邀请", "消息", "通知"],
            "network": ["scinet", "科学上网", "代理", "加速", "proxy", "vpn", "翻墙", "pac", "网络加速"],
            "seed": ["seed", "角色", "初始化", "配置", "设置", "setup", "wizard", "向导", "环评", "工程师"],
        }

        for kw in keywords.get(cmd_name, []):
            if kw in text_lower:
                score += 1.0

        scores[cmd_name] = score

    # Get the highest scoring command
    best = max(scores, key=scores.get)

    result = {"command": best, "action": "", "params": text, "confidence": min(scores[best] / 3.0, 1.0)}

    if scores[best] < 0.5:
        result["command"] = "ask"  # default fallback
        result["confidence"] = 0.1

    return result
