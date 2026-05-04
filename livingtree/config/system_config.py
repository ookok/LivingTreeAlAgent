"""Central configuration for language detection, prompts, and system constants.

Replaces 30+ hardcoded patterns across the codebase with a single source of truth.
Uses intent-driven routing instead of static keyword matching where appropriate.
"""

from dataclasses import dataclass, field
from typing import Any

# ── Language detection (consolidated from 3 copies) ──

EXT_TO_LANG: dict[str, str] = {
    ".py": "python", ".pyi": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".jsx": "javascript",
    ".html": "html", ".css": "css",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".md": "markdown", ".sql": "sql", ".sh": "bash",
    ".rs": "rust", ".go": "go", ".java": "java",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".c": "c", ".h": "c",
    ".rb": "ruby", ".php": "php", ".swift": "swift", ".kt": "kotlin",
    ".lua": "lua", ".zig": "zig", ".dart": "dart",
    ".tf": "terraform", ".toml": "toml", ".cfg": "ini", ".ini": "ini",
    ".xml": "xml", ".csv": "csv", ".env": "text",
}

LANG_DISPLAY_NAMES: list[tuple[str, str]] = [
    ("python", "Python"), ("javascript", "JavaScript"), ("typescript", "TypeScript"),
    ("html", "HTML"), ("css", "CSS"), ("json", "JSON"), ("yaml", "YAML"),
    ("markdown", "Markdown"), ("sql", "SQL"), ("bash", "Bash"),
    ("rust", "Rust"), ("go", "Go"), ("java", "Java"), ("cpp", "C++"),
    ("c", "C"), ("ruby", "Ruby"), ("php", "PHP"), ("swift", "Swift"),
    ("kotlin", "Kotlin"), ("lua", "Lua"), ("dart", "Dart"),
]

# ── Intent-based routing (replaces keyword lists) ──

PIPELINE_INTENT_TRIGGERS = [
    "提取", "汇总", "去重", "排序", "过滤", "筛选", "合并",
    "extract", "summarize", "dedup", "sort", "filter", "merge",
]

PRO_REASONING_INTENT_TRIGGERS = [
    "分析", "推理", "预测", "评估", "优化", "报告", "方案", "风险",
    "analyze", "reason", "predict", "evaluate", "optimize", "report",
]

# ── System prompts (centralized from 10+ files) ──

SYSTEM_PROMPTS = {
    "chat_default": (
        "You are a professional AI assistant. Reply in Markdown format.\n"
        "Rules:\n"
        "1. Use ### for headings\n"
        "2. Code blocks with language: ```python\n"
        "3. Lists with - or 1.\n"
        "4. Important content in **bold**\n"
        "5. Tables with | alignment\n"
        "6. Be concise and structured"
    ),
    "stream_of_thought": "快速分析用户意图。流式输出思考过程。",
    "chain_of_thought": "深度{steps}步推理。Output reasoning steps then final answer.",
    "hypothesis_gen": "Generate {count} distinct hypotheses. One per line.",
    "knowledge_gaps": "Identify knowledge gaps. Output 3-5 questions.",
    "intent_recognition": (
        "Return JSON: {{\"intent\":str,\"domain\":str,\"confidence\":float,\"summary\":str}}. "
        "Domain: detect from user message content (do not use fixed list)."
    ),
}

# ── Reasoning effort levels ──

REASONING_EFFORTS = ["off", "high", "max"]

# ── Feature keywords for classifier (not intent-dependent) ──

CLASSIFIER_FEATURES = [
    "analyze", "分析", "code", "代码", "生成", "report", "报告",
    "search", "搜索", "knowledge", "知识", "train", "训练",
    "translate", "翻译", "summarize", "总结", "refactor", "重构",
    "fix", "修复", "debug", "emergency", "应急", "eia",
]

# ── Slash commands (centralized from chat.py) ──

SLASH_COMMANDS: dict[str, str] = {
    "/file": "预览文件内容 — /file 路径",
    "/code": "AI 生成代码 — /code 描述",
    "/report": "AI 生成报告 — /report 主题",
    "/search": "多源融合搜索 — /search 关键词",
    "/analyze": "深度分析 — /analyze 问题",
    "/clear": "清空聊天 — /clear",
    "/help": "显示命令帮助 — /help",
    "/stash": "暂存草稿 — /stash | /stash list|pop|clear",
    "/effort": "推理深度 — /effort off|high|max",
    "/memory": "用户记忆 — /memory | /memory show|clear|path",
    "/diff": "渲染差异 — /diff <old> <new>",
    "/share": "导出对话 — /share",
    "/init": "生成 AGENTS.md — /init",
    "/retry": "重试最后一条 — /retry",
    "/status": "系统状态 — /status",
    "/extract": "实体提取 — /extract <class1,class2> <text>",
    "/pipeline": "自动管道 — /pipeline <自然语言描述>",
    "/parse": "解析文档 — /parse <PDF路径>",
    "/fetch": "抓取网页 — /fetch <URL>",
    "/errors": "系统错误 — /errors | /errors clear",
}
