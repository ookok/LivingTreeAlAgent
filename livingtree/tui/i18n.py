"""I18n — Multi-language TUI support. Default: zh (Chinese).

Usage:
    from .i18n import i18n, t
    t("chat.send")  # "发送" (zh) or "Send" (en)
    i18n.switch("en")  # switch to English
"""
from __future__ import annotations


class I18n:
    """Singleton i18n manager with lazy string interpolation."""

    _instance: I18n | None = None

    @classmethod
    def instance(cls) -> I18n:
        if cls._instance is None:
            cls._instance = I18n()
        return cls._instance

    def __init__(self):
        self._lang = "zh"
        self._loaded: dict[str, dict[str, str]] = {}

    @property
    def lang(self) -> str:
        return self._lang

    def switch(self, lang: str):
        self._lang = lang

    def get(self, key: str, default: str = "") -> str:
        table = self._loaded.get(self._lang, {})
        return table.get(key, _LANG_TABLE.get(self._lang, {}).get(key, _LANG_TABLE.get("zh", {}).get(key, key)))

    def __call__(self, key: str, **kwargs) -> str:
        text = self.get(key, key)
        if kwargs:
            return text.format(**kwargs)
        return text


i18n = I18n.instance()
t = i18n


# ═══ Language tables ═══

_LANG_TABLE: dict[str, dict[str, str]] = {
    "zh": {
        # ── App ──
        "app.title": "🌳 LivingTree",
        "app.subtitle": "数字生命体 v{version}",
        "app.search_placeholder": "搜索功能模块...",
        "app.ready": "系统就绪",
        "app.booting": "系统初始化中，请稍候...",
        "app.boot_failed": "启动失败",
        "app.launch": "启动",
        "app.cancel": "取消",

        # ── Cards ──
        "card.chat": "💬\nAI 对话\n多模态 · 流式 · 任务树",
        "card.code": "📝\n代码编辑器\n编辑 · 运行 · Diff",
        "card.docs": "📚\n知识库\n文档管理与检索",
        "card.tools": "🔧\n工具箱\nPDF · 图表 · 地图 · 预览",
        "card.settings": "⚙\n系统配置\nAPI · 基因组 · 设置",

        # ── Chat screen ──
        "chat.title": "AI 对话",
        "chat.welcome": "🌳 LivingTree AI Agent",
        "chat.thinking": "正在思考中...",
        "chat.cancelled": "⚠ 已取消",
        "chat.cancelled_partial": "⚠ 生成已取消",
        "chat.timeout": "请求超时",
        "chat.error": "调用失败",
        "chat.new_session": "新会话",
        "chat.clear": "对话已清空",
        "chat.system_ready": "系统就绪",
        "chat.model": "模型",
        "chat.session": "会话",
        "chat.reasoning": "推理",
        "chat.reasoning_depth": "推理深度",
        "chat.cycle_effort": "推理深度",
        "chat.help": "可用命令",
        "chat.unknown_cmd": "未知命令",
        "chat.searching": "搜索",
        "chat.fetching": "获取",
        "chat.parsing": "解析",
        "chat.stash": "暂存功能已触发",

        # ── Bindings ──
        "bind.chat": "对话",
        "bind.code": "代码",
        "bind.docs": "知识库",
        "bind.tools": "工具箱",
        "bind.settings": "设置",
        "bind.quit": "退出",
        "bind.help": "帮助",
        "bind.enter": "进入",
        "bind.send": "发送",
        "bind.sidebar": "侧栏",
        "bind.new_session": "新会话",
        "bind.focus_input": "输入",
        "bind.refresh": "刷新",
        "bind.refresh_models": "刷新模型",
        "bind.return": "返回",

        # ── StatusBar ──
        "status.keys": "Ctrl+T 对话  Ctrl+E 代码  Ctrl+D 文档  Ctrl+K 工具  F2 设置  Ctrl+Q 退出",
        "status.llm": "LLM",

        # ── Code screen ──
        "code.title": "代码编辑器",
        "code.back": "← 返回首页 (Esc)",
        "code.search": "Search files",
        "code.new": "New",
        "code.save": "Save",
        "code.diff": "Diff",
        "code.ai_gen": "AI Gen",
        "code.run": "Run",
        "code.goto": "Goto",
        "code.welcome": "# Code Editor",
        "code.draft_saved": "Draft saved",
        "code.no_code": "No code to run",
        "code.output": "Output",
        "code.ok": "OK (no output)",

        # ── Tools screen ──
        "tools.title": "工具箱",
        "tools.back": "← 返回首页 (Esc)",
        "tools.models_tab": "🔬 模型",
        "tools.models_title": "🔬 模型管理",
        "tools.models_refresh": "🔄 刷新所有平台模型",
        "tools.models_refreshing": "⏳ 刷新中...",
        "tools.models_fetching": "正在从各平台拉取模型列表...",
        "tools.models_done": "✓ 已刷新 {count} 个平台，共 {total} 个模型",
        "tools.models_refresh_hint": "点击刷新按钮拉取模型列表",
        "tools.pdf_tab": "📄 PDF/Doc",
        "tools.translate_tab": "🌐 翻译",
        "tools.chart_tab": "📊 图表",
        "tools.map_tab": "🗺 地图",

        # ── Settings screen ──
        "settings.title": "系统配置",
        "settings.back": "← 返回首页 (Esc)",

        # ── Docs screen ──
        "docs.title": "知识库",
        "docs.back": "← 返回首页 (Esc)",

        # ── Coding agents ──
        "agents.title": "🔧 Coding Agents",
        "agents.status": "{count} coding agents",
        "agents.ready": "✓ ready",
        "agents.not_found": "○ not found",
        "agents.launch": "▶ Launch",
        "agents.install": "⬇ Install",
        "agents.installing": "Installing",
        "agents.installed": "installed",
        "agents.install_failed": "Install failed",
        "agents.install_timeout": "Install timed out",
        "agents.launching": "Launching",
        "agents.capabilities": "Skills: 分析 · 生成 · 审查\nTools: PDF · 地图 · 图表\nAgents: 环评专家 · 安全审查",

        # ── Boot ──
        "boot.step_config": "配置系统",
        "boot.step_engine": "导入引擎",
        "boot.step_world": "构建世界",
        "boot.step_service": "启动服务",
        "boot.step_done": "初始化完成",

        # ── NeonConversation ──
        "neon.engine_not_ready": "Engine not ready",
        "neon.request_timeout": "Request timeout",
        "neon.error": "Error",

        # ── Slash commands ──
        "slash.search": "多源搜索",
        "slash.pipeline": "自动流水线",
        "slash.file": "预览文件",
        "slash.fetch": "获取URL",
        "slash.parse": "解析文档",
        "slash.stash": "暂存管理",
        "slash.clear": "清空对话",
        "slash.status": "系统状态",
        "slash.narrative": "生命叙事",
        "slash.help": "命令帮助",
        "slash.code": "代码生成",
        "slash.report": "报告生成",
        "slash.analyze": "深度分析",
        "slash.diff": "查看差异",
        "slash.share": "分享会话",
        "slash.init": "初始化项目",
        "slash.retry": "重试",
        "slash.memory": "记忆管理",
        "slash.extract": "实体抽取",
        "slash.errors": "错误日志",
        "slash.effort": "推理深度",
        "slash.predict": "影响预测",
        "slash.debate": "多智能体辩论",

        # ── Command outputs ──
        "cmd.not_ready": "系统未就绪",
        "cmd.status_title": "## 系统状态",
        "cmd.help_text": "**文件:** /find <关键词>  /save <文件>  /replace <文件> <旧> <新>  /locate <描述>\n**文件操作:** /render <模板> <键=值>  /dedup [模式]  /patch list|apply|revert  /backup save|list|restore  /history <文件>  /watch start|stop\n**命令:** /search <关键词>  /fetch <URL>  /clear  /status  /help  /evolve  /tools  /route <查询>  /optimize <提示词>  /role [名称]  /graph [节点],
        "cmd.search_usage": "用法: /search <关键词>",
        "cmd.fetch_usage": "用法: /fetch <URL>",
        "cmd.searching": "**正在搜索:** {q}",
        "cmd.no_results": "[dim]所有搜索引擎均无结果[/dim]",
        "cmd.search_error": "[red]搜索错误: {e}[/red]",
        "cmd.fetching": "**正在获取:** {url}",
        "cmd.http_error": "[red]HTTP {code}[/red]",
        "cmd.fetch_error": "[red]获取错误: {e}[/red]",
        "cmd.evolve_title": "## 🧬 自进化状态",
        "cmd.evolve_requests": "- **请求数**: {n}",
        "cmd.evolve_hits": "- **结构化命中**: {n} ({pct})",
        "cmd.evolve_failures": "- **解析失败**: {n}",
        "cmd.evolve_latency": "- **平均延迟**: {ms}ms",
        "cmd.evolve_widgets": "### 组件渲染",
        "cmd.evolve_parser": "### 解析器统计",
        "cmd.evolve_error": "[red]进化错误: {e}[/red]",
        "cmd.route_usage": "用法: /route <查询>",
        "cmd.route_title": "## 🧭 SkillRouter: *{q}*",
        "cmd.route_providers": "**Provider:**",
        "cmd.route_tools": "**工具:**",
        "cmd.route_roles": "**角色:**",
        "cmd.route_error": "[red]路由错误: {e}[/red]",
        "cmd.score": "得分",
        "cmd.optimize_usage": "用法: /optimize <提示词>",
        "cmd.optimizing": "**正在优化:** {p}",
        "cmd.optimize_title": "## 📝 提示词优化 ({rounds}轮, 评分={score})",
        "cmd.optimize_original": "### 原始",
        "cmd.optimize_result": "### 优化后",
        "cmd.optimize_improvements": "### 改进",
        "cmd.role_title": "## 🎭 可用角色",
        "cmd.role_unknown": "未知角色: {name}。使用 /role 查看列表。",
        "cmd.role_detail": "## 🎭 角色: {name}",
        "cmd.role_prompt": "提示词",
        "cmd.role_gates": "质量要求",
        "cmd.role_format": "输出格式",
        "cmd.role_examples": "示例",
        "cmd.input": "输入",
        "cmd.output": "输出",

        # ── Cron commands ──
        "cmd.cron_usage": "用法: /cron list|add <描述>|remove <id>|test <id>",
        "cmd.cron_title": "## ⏰ 定时任务",
        "cmd.cron_empty": "[dim]暂无定时任务。使用 /cron add <描述> 创建[/dim]",
        "cmd.cron_added": "已添加定时任务: {desc}",
        "cmd.cron_removed": "已移除: {id}",
        "cmd.cron_notfound": "未找到: {id}",
        "cmd.cron_tested": "已测试执行: {id}",

        # ── Recall commands ──
        "cmd.recall_usage": "用法: /recall <关键词>",
        "cmd.recall_title": "## 🔍 会话回忆: *{q}* ({n} 条已索引)",
        "cmd.recall_empty": "[dim]未找到相关记录[/dim]",

        # ── Gateway commands ──
        "cmd.gateway_usage": "用法: /gateway status|config telegram <token> [chat_id]",
        "cmd.gateway_title": "## 🌐 消息网关",
        "cmd.gateway_configured": "{platform} 已配置",
    },

    "en": {
        # ── App ──
        "app.title": "🌳 LivingTree",
        "app.subtitle": "Digital Life Form v{version}",
        "app.search_placeholder": "Search modules...",
        "app.ready": "System ready",
        "app.booting": "Initializing, please wait...",
        "app.boot_failed": "Boot failed",
        "app.launch": "Launch",
        "app.cancel": "Cancel",

        # ── Cards ──
        "card.chat": "💬\nAI Chat\nMulti-modal · Streaming · Task Tree",
        "card.code": "📝\nCode Editor\nEdit · Run · Diff",
        "card.docs": "📚\nKnowledge Base\nDocument Management",
        "card.tools": "🔧\nToolbox\nPDF · Charts · Maps · Preview",
        "card.settings": "⚙\nSettings\nAPI · Genome · Config",

        # ── Chat screen ──
        "chat.title": "AI Chat",
        "chat.welcome": "🌳 LivingTree AI Agent",
        "chat.thinking": "Thinking...",
        "chat.cancelled": "⚠ Cancelled",
        "chat.cancelled_partial": "⚠ Generation cancelled",
        "chat.timeout": "Request timeout",
        "chat.error": "Call failed",
        "chat.new_session": "New session",
        "chat.clear": "Chat cleared",
        "chat.system_ready": "System ready",
        "chat.model": "Model",
        "chat.session": "Session",
        "chat.reasoning": "Reasoning",
        "chat.reasoning_depth": "Reasoning depth",
        "chat.cycle_effort": "Reasoning depth",
        "chat.help": "Available commands",
        "chat.unknown_cmd": "Unknown command",
        "chat.searching": "Searching",
        "chat.fetching": "Fetching",
        "chat.parsing": "Parsing",
        "chat.stash": "Stash triggered",

        # ── Bindings ──
        "bind.chat": "Chat",
        "bind.code": "Code",
        "bind.docs": "Docs",
        "bind.tools": "Tools",
        "bind.settings": "Settings",
        "bind.quit": "Quit",
        "bind.help": "Help",
        "bind.enter": "Enter",
        "bind.send": "Send",
        "bind.sidebar": "Sidebar",
        "bind.new_session": "New Session",
        "bind.focus_input": "Focus Input",
        "bind.refresh": "Refresh",
        "bind.refresh_models": "Refresh Models",
        "bind.return": "Back",

        # ── StatusBar ──
        "status.keys": "Ctrl+T Chat  Ctrl+E Code  Ctrl+D Docs  Ctrl+K Tools  F2 Settings  Ctrl+Q Quit",
        "status.llm": "LLM",

        # ── Code screen ──
        "code.title": "Code Editor",
        "code.back": "← Back (Esc)",
        "code.search": "Search files",
        "code.new": "New",
        "code.save": "Save",
        "code.diff": "Diff",
        "code.ai_gen": "AI Gen",
        "code.run": "Run",
        "code.goto": "Goto",
        "code.welcome": "# Code Editor",
        "code.draft_saved": "Draft saved",
        "code.no_code": "No code to run",
        "code.output": "Output",
        "code.ok": "OK (no output)",

        # ── Tools screen ──
        "tools.title": "Toolbox",
        "tools.back": "← Back (Esc)",
        "tools.models_tab": "🔬 Models",
        "tools.models_title": "🔬 Model Manager",
        "tools.models_refresh": "🔄 Refresh All Platforms",
        "tools.models_refreshing": "⏳ Refreshing...",
        "tools.models_fetching": "Fetching model lists from all platforms...",
        "tools.models_done": "✓ Refreshed {count} platforms, {total} models total",
        "tools.models_refresh_hint": "Click refresh to fetch model lists",
        "tools.pdf_tab": "📄 PDF/Doc",
        "tools.translate_tab": "🌐 Translate",
        "tools.chart_tab": "📊 Charts",
        "tools.map_tab": "🗺 Maps",

        # ── Settings screen ──
        "settings.title": "Settings",
        "settings.back": "← Back (Esc)",

        # ── Docs screen ──
        "docs.title": "Knowledge Base",
        "docs.back": "← Back (Esc)",

        # ── Coding agents ──
        "agents.title": "🔧 Coding Agents",
        "agents.status": "{count} coding agents",
        "agents.ready": "✓ ready",
        "agents.not_found": "○ not found",
        "agents.launch": "▶ Launch",
        "agents.install": "⬇ Install",
        "agents.installing": "Installing",
        "agents.installed": "installed",
        "agents.install_failed": "Install failed",
        "agents.install_timeout": "Install timed out",
        "agents.launching": "Launching",
        "agents.capabilities": "Skills: Analysis · Gen · Review\nTools: PDF · Maps · Charts\nAgents: EIA Expert · Safety Audit",

        # ── Boot ──
        "boot.step_config": "Config System",
        "boot.step_engine": "Import Engine",
        "boot.step_world": "Build World",
        "boot.step_service": "Start Services",
        "boot.step_done": "Initialization Complete",

        # ── NeonConversation ──
        "neon.engine_not_ready": "Engine not ready",
        "neon.request_timeout": "Request timeout",
        "neon.error": "Error",

        # ── Slash commands ──
        "slash.search": "Multi-source search",
        "slash.pipeline": "Auto pipeline",
        "slash.file": "Preview file",
        "slash.fetch": "Fetch URL",
        "slash.parse": "Parse document",
        "slash.stash": "Stash manager",
        "slash.clear": "Clear chat",
        "slash.status": "System status",
        "slash.narrative": "Life narrative",
        "slash.help": "Command help",
        "slash.code": "Code generation",
        "slash.report": "Report generation",
        "slash.analyze": "Deep analysis",
        "slash.diff": "View diff",
        "slash.share": "Share session",
        "slash.init": "Init project",
        "slash.retry": "Retry",
        "slash.memory": "Memory manager",
        "slash.extract": "Entity extract",
        "slash.errors": "Error logs",
        "slash.effort": "Reasoning depth",
        "slash.predict": "Impact predict",
        "slash.debate": "Multi-agent debate",

        # ── Command outputs ──
        "cmd.not_ready": "System not ready",
        "cmd.status_title": "## System Status",
        "cmd.help_text": "**Files:** /find <q>  /save <file>  /replace <f> <old> <new>  /locate <desc>\n**FileOps:** /render <tpl> <k=v>  /dedup [pat]  /patch list|apply|revert  /backup save|list|restore  /history <f>  /watch start|stop\n**Commands:** /search <q>  /fetch <url>  /clear  /status  /help  /evolve  /tools  /route <q>  /optimize <p>  /role [name]  /graph [node]",
        "cmd.search_usage": "Usage: /search <query>",
        "cmd.fetch_usage": "Usage: /fetch <url>",
        "cmd.searching": "**Searching:** {q}",
        "cmd.no_results": "[dim]No results from any engine[/dim]",
        "cmd.search_error": "[red]Search error: {e}[/red]",
        "cmd.fetching": "**Fetching:** {url}",
        "cmd.http_error": "[red]HTTP {code}[/red]",
        "cmd.fetch_error": "[red]Fetch error: {e}[/red]",
        "cmd.evolve_title": "## 🧬 Evolution Status",
        "cmd.evolve_requests": "- **Requests**: {n}",
        "cmd.evolve_hits": "- **Structured hits**: {n} ({pct})",
        "cmd.evolve_failures": "- **Parse failures**: {n}",
        "cmd.evolve_latency": "- **Avg latency**: {ms}ms",
        "cmd.evolve_widgets": "### Widget Renders",
        "cmd.evolve_parser": "### Parser Stats",
        "cmd.evolve_error": "[red]Evolve error: {e}[/red]",
        "cmd.route_usage": "Usage: /route <query>",
        "cmd.route_title": "## 🧭 SkillRouter: *{q}*",
        "cmd.route_providers": "**Providers:**",
        "cmd.route_tools": "**Tools:**",
        "cmd.route_roles": "**Roles:**",
        "cmd.route_error": "[red]Route error: {e}[/red]",
        "cmd.score": "score",
        "cmd.optimize_usage": "Usage: /optimize <prompt>",
        "cmd.optimizing": "**Optimizing:** {p}",
        "cmd.optimize_title": "## 📝 Prompt Optimized ({rounds} rounds, score={score})",
        "cmd.optimize_original": "### Original",
        "cmd.optimize_result": "### Optimized",
        "cmd.optimize_improvements": "### Improvements",
        "cmd.role_title": "## 🎭 Available Roles",
        "cmd.role_unknown": "Unknown role: {name}. Use /role to list.",
        "cmd.role_detail": "## 🎭 Role: {name}",
        "cmd.role_prompt": "Prompt",
        "cmd.role_gates": "Quality Gates",
        "cmd.role_format": "Format",
        "cmd.role_examples": "Examples",
        "cmd.input": "Input",
        "cmd.output": "Output",

        # ── Cron commands ──
        "cmd.cron_usage": "Usage: /cron list|add <desc>|remove <id>|test <id>",
        "cmd.cron_title": "## ⏰ Cron Jobs",
        "cmd.cron_empty": "[dim]No cron jobs. Use /cron add <desc>[/dim]",
        "cmd.cron_added": "Cron added: {desc}",
        "cmd.cron_removed": "Removed: {id}",
        "cmd.cron_notfound": "Not found: {id}",
        "cmd.cron_tested": "Test executed: {id}",

        # ── Recall commands ──
        "cmd.recall_usage": "Usage: /recall <keyword>",
        "cmd.recall_title": "## 🔍 Session Recall: *{q}* ({n} indexed)",
        "cmd.recall_empty": "[dim]No matches found[/dim]",

        # ── Gateway commands ──
        "cmd.gateway_usage": "Usage: /gateway status|config telegram <token> [chat_id]",
        "cmd.gateway_title": "## 🌐 Message Gateway",
        "cmd.gateway_configured": "{platform} configured",
    },
}
