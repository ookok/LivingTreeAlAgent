"""
Ollama 模型工具集
注册到 ToolRegistry
"""

from business.tools_registry import ToolRegistry, tool, SCHEMA


def register_model_tools(agent):
    """注册 Ollama 模型工具"""

    @tool(
        name="list_models",
        description="列出 Ollama 中已注册和已加载的模型",
        parameters=SCHEMA["list_models"],
        toolset="ollama",
    )
    def list_models(ctx: dict) -> str:
        client = agent.ollama
        models = client.list_models()
        if not models:
            return "Ollama 中暂无已注册的模型。\n请先从模型市场下载模型。"
        lines = ["已注册模型："]
        for m in models:
            lines.append(f"- {m.name} ({_format_size(m.size)})")
        return "\n".join(lines)

    @tool(
        name="load_model",
        description="将模型加载到内存中",
        parameters=SCHEMA["load_model"],
        toolset="ollama",
    )
    def load_model(ctx: dict, name: str) -> str:
        client = agent.ollama
        if client.is_loaded(name):
            return f"模型已加载: {name}"
        ok = client.load_model(name)
        if ok:
            return f"模型已加载: {name}"
        else:
            return f"加载失败: {name}"

    @tool(
        name="unload_model",
        description="从内存中卸载模型",
        parameters=SCHEMA["unload_model"],
        toolset="ollama",
    )
    def unload_model(ctx: dict, name: str) -> str:
        client = agent.ollama
        ok = client.unload_model(name)
        if ok:
            return f"模型已卸载: {name}"
        else:
            return f"卸载失败: {name}"


def _format_size(size: int) -> str:
    if size == 0:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"
