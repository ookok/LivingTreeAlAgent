"""
写作工具集
注册到 ToolRegistry
"""

import json
from pathlib import Path
from core.tools_registry import ToolRegistry, tool, SCHEMA
from core.config import get_projects_dir


def _get_project_dir(project_name: str) -> Path:
    """获取项目目录"""
    return get_projects_dir() / project_name


def _ensure_project(project_name: str) -> Path:
    """确保项目目录存在"""
    p = _get_project_dir(project_name)
    p.mkdir(parents=True, exist_ok=True)
    docs_dir = p / "docs"
    docs_dir.mkdir(exist_ok=True)
    return p


def _slugify(name: str) -> str:
    """转换为安全的文件名"""
    import re
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'\s+', '-', name)
    return name.strip('-').lower()


def register_writing_tools(agent):
    """注册写作工具"""

    @tool(
        name="create_document",
        description="创建 Markdown 文档",
        parameters=SCHEMA["create_document"],
        toolset="writing",
    )
    def create_document(ctx: dict, project_name: str, title: str, content: str) -> str:
        _ensure_project(project_name)
        filename = _slugify(title) + ".md"
        filepath = _get_project_dir(project_name) / "docs" / filename
        # 添加 YAML frontmatter
        frontmatter = f'---\ntitle: "{title}"\ncreated: "{_now()}"\n---\n\n'
        filepath.write_text(frontmatter + content, encoding="utf-8")
        return f"已创建: {filepath}"

    @tool(
        name="edit_document",
        description="编辑 Markdown 文档中的指定文本",
        parameters=SCHEMA["edit_document"],
        toolset="writing",
    )
    def edit_document(ctx: dict, path: str, old_str: str, new_str: str) -> str:
        p = Path(path)
        if not p.exists():
            return f"文件不存在: {path}"
        try:
            text = p.read_text(encoding="utf-8")
            if old_str not in text:
                return f"未找到: {old_str[:50]}..."
            new_text = text.replace(old_str, new_str, 1)
            p.write_text(new_text, encoding="utf-8")
            return f"已修改: {path}"
        except Exception as e:
            return f"编辑失败: {e}"

    @tool(
        name="list_documents",
        description="列出项目中的所有文档",
        parameters=SCHEMA["list_documents"],
        toolset="writing",
    )
    def list_documents(ctx: dict, project_name: str) -> str:
        docs_dir = _get_project_dir(project_name) / "docs"
        if not docs_dir.exists():
            return "项目目录为空"
        docs = sorted(docs_dir.glob("*.md"))
        if not docs:
            return "暂无文档"
        lines = []
        for d in docs:
            stat = d.stat()
            lines.append(f"- {d.name} ({_format_size(stat.st_size)})")
        return "\n".join(lines)

    @tool(
        name="read_document",
        description="读取 Markdown 文档",
        parameters=SCHEMA["read_document"],
        toolset="writing",
    )
    def read_document(ctx: dict, path: str) -> str:
        p = Path(path)
        if not p.exists():
            return f"文件不存在: {path}"
        try:
            return p.read_text(encoding="utf-8")
        except Exception as e:
            return f"读取失败: {e}"

    @tool(
        name="list_projects",
        description="列出所有写作项目",
        parameters=SCHEMA["list_projects"],
        toolset="project",
    )
    def list_projects(ctx: dict) -> str:
        projects_dir = get_projects_dir()
        if not projects_dir.exists():
            return "暂无项目"
        projects = [p for p in projects_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]
        if not projects:
            return "暂无项目"
        lines = [f"- {p.name}/" for p in sorted(projects, key=lambda x: x.name.lower())]
        return "\n".join(lines)

    @tool(
        name="create_project",
        description="创建新的写作项目",
        parameters=SCHEMA["create_project"],
        toolset="project",
    )
    def create_project(ctx: dict, name: str, description: str = "") -> str:
        p = _ensure_project(name)
        meta = {
            "name": name,
            "description": description,
            "created": _now(),
        }
        (p / ".project.meta").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return f"已创建项目: {name}/"

    @tool(
        name="switch_project",
        description="切换当前项目（仅信息，不实际切换）",
        parameters=SCHEMA["switch_project"],
        toolset="project",
    )
    def switch_project(ctx: dict, name: str) -> str:
        p = _get_project_dir(name)
        if not p.exists():
            return f"项目不存在: {name}"
        meta_file = p / ".project.meta"
        meta = {}
        if meta_file.exists():
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        return f"当前项目: {name}\n描述: {meta.get('description', '无')}"


def _now() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _format_size(size: int) -> str:
    for unit in ("B", "KB", "MB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}GB"
