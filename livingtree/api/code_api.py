"""Code Mode API — project management + file system operations.

Project layout (user-scoped):
    output/{user_id}/code/{project_name}/   ← user's project source code
    output/{user_id}/docs/                   ← user's documents

Admin users: can see all users' projects.
Regular users: only see their own projects.
"""
from __future__ import annotations

import difflib
import fnmatch
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from livingtree.api.auth import get_current_user, is_admin

# ═══ Config ═══
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
PROJECTS_META_FILE = OUTPUT_DIR / "projects.json"

EXCLUDE_PATTERNS = [
    ".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".sisyphus",
    "node_modules", ".livingtree", "dist", "build", ".venv", "venv",
    "*.pyc", "*.egg-info", ".wt", "trae_snapshot", ".python-version",
    "livingtree_ai_agent.egg-info", "__MACOSX",
]

TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json",
    ".yaml", ".yml", ".toml", ".md", ".txt", ".cfg", ".ini", ".env",
    ".sh", ".bat", ".ps1", ".xml", ".sql", ".rs", ".go", ".java",
    ".cpp", ".c", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
    ".kt", ".scala", ".r", ".lua", ".dart", ".vue", ".svelte",
    ".gitignore", ".dockerignore", ".proto",
}

MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB


# ═══ Models ═══

class FileItem(BaseModel):
    name: str
    path: str
    type: str  # file | dir
    size: int = 0


class FileListResponse(BaseModel):
    path: str
    items: list[FileItem]


class FileContentRequest(BaseModel):
    path: str
    content: str


class DiffRequest(BaseModel):
    path: str
    old_content: str
    new_content: str
    project: str = ""


class DiffResponse(BaseModel):
    path: str
    diff: str
    has_changes: bool


class ProjectInfo(BaseModel):
    name: str
    path: str
    owner: str = ""
    created_at: float
    github_url: str = ""
    github_branch: str = "main"
    last_synced: float = 0.0
    file_count: int = 0
    doc_count: int = 0


class CreateProjectRequest(BaseModel):
    name: str
    github_url: str = ""


# ═══ User-Scoped Path Helpers ═══

def _get_user_dir(user_id: str) -> Path:
    """Get user's output directory: output/{user_id}/"""
    return OUTPUT_DIR / user_id


def _get_user_code_dir(user_id: str) -> Path:
    """Get user's code directory: output/{user_id}/code/"""
    return _get_user_dir(user_id) / "code"


def _get_user_docs_dir(user_id: str) -> Path:
    """Get user's docs directory: output/{user_id}/docs/"""
    return _get_user_dir(user_id) / "docs"


def _get_project_dir(user_id: str, name: str) -> Path:
    """Get project directory: output/{user_id}/code/{name}/"""
    return _get_user_code_dir(user_id) / name


def _project_exists(user_id: str, name: str) -> bool:
    return _get_project_dir(user_id, name).is_dir()


# ═══ Project Meta Store ═══

def _load_projects() -> list[dict]:
    if PROJECTS_META_FILE.exists():
        try:
            return json.loads(PROJECTS_META_FILE.read_text())
        except Exception:
            pass
    return []


def _save_projects(projects: list[dict]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_META_FILE.write_text(json.dumps(projects, ensure_ascii=False, indent=2))


def _load_user_projects(user_id: str, is_admin_user: bool = False) -> list[dict]:
    """Load projects visible to a user. Admin sees all, user sees own."""
    all_projects = _load_projects()
    if is_admin_user:
        return all_projects
    return [p for p in all_projects if p.get("owner") == user_id]


def _count_files(dir_path: Path) -> int:
    if not dir_path.exists():
        return 0
    count = 0
    for item in dir_path.rglob("*"):
        if item.is_file():
            skip = False
            for pat in EXCLUDE_PATTERNS:
                if fnmatch.fnmatch(item.name, pat):
                    skip = True
                    break
            if not skip:
                count += 1
    return count


# ═══ Helpers ═══

def _resolve_path(rel_path: str) -> Path:
    """Resolve and validate a relative path stays inside PROJECT_ROOT."""
    full = (PROJECT_ROOT / rel_path).resolve()
    try:
        full.relative_to(PROJECT_ROOT)
    except ValueError:
        raise HTTPException(status_code=403, detail="禁止访问项目外路径")
    return full


def _should_exclude(name: str) -> bool:
    for pattern in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False


def _is_text_file(path: Path) -> bool:
    if path.suffix in TEXT_EXTENSIONS:
        return True
    if path.name in TEXT_EXTENSIONS:
        return True
    if not path.suffix:
        return True
    return False


def _require_admin(user: dict):
    if not is_admin(user["user_id"]):
        raise HTTPException(status_code=403, detail="需要管理员权限：Code 模式仅限企业微信管理员使用")


def _resolve_project_path(user_id: str, project: str, rel_path: str) -> Path:
    """Resolve path inside user's project dir. Sandboxed."""
    if project:
        base = _get_project_dir(user_id, project)
    else:
        base = _get_user_code_dir(user_id)
    full = (base / rel_path).resolve()
    try:
        full.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=403, detail="禁止访问项目外路径")
    return full


def _resolve_user_path(user_id: str, rel_path: str) -> Path:
    """Resolve path inside user's output dir (for shared docs access)."""
    base = _get_user_dir(user_id)
    full = (base / rel_path).resolve()
    try:
        full.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=403, detail="禁止访问用户目录外路径")
    return full


LANG_MAP = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".jsx": "jsx", ".tsx": "tsx", ".html": "html", ".css": "css",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
    ".md": "markdown", ".txt": "plaintext", ".sh": "bash", ".bat": "batch",
    ".ps1": "powershell", ".sql": "sql", ".rs": "rust", ".go": "go",
    ".java": "java", ".cpp": "cpp", ".c": "c", ".h": "c",
    ".xml": "xml", ".proto": "protobuf",
}


def _lang_from_path(path: str) -> str:
    p = Path(path)
    if p.suffix in LANG_MAP:
        return LANG_MAP[p.suffix]
    if p.name == "Dockerfile":
        return "dockerfile"
    if p.name == "Makefile":
        return "makefile"
    return "plaintext"


# ═══ Route Registration ═══

def setup_code_routes(app: FastAPI) -> None:
    """Register code mode API routes on the FastAPI app."""

    # ── Project Management ──

    @app.get("/api/code/projects", response_model=list[ProjectInfo])
    async def list_projects(
        user: dict = Depends(get_current_user),
    ):
        """List projects visible to current user. Admin sees all; users see own."""
        _require_admin(user)
        my_projects = _load_user_projects(user["user_id"], is_admin(user["user_id"]))
        result = []
        for p in my_projects:
            owner = p.get("owner", "")
            proj_dir = _get_project_dir(owner, p["name"])
            result.append(ProjectInfo(
                name=p["name"],
                owner=owner,
                path=str(proj_dir.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                created_at=p.get("created_at", 0),
                github_url=p.get("github_url", ""),
                github_branch=p.get("github_branch", "main"),
                last_synced=p.get("last_synced", 0),
                file_count=_count_files(proj_dir),
                doc_count=p.get("doc_count", 0),
            ))
        return result

    @app.post("/api/code/projects", response_model=ProjectInfo)
    async def create_project(
        req: CreateProjectRequest,
        user: dict = Depends(get_current_user),
    ):
        """Create a new code project under current user's space."""
        _require_admin(user)

        name = req.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="项目名不能为空")
        if not re.match(r'^[\w\u4e00-\u9fff\-]+$', name):
            raise HTTPException(status_code=400, detail="项目名只能包含字母、数字、下划线、连字符和中文")

        user_id = user["user_id"]
        if _project_exists(user_id, name):
            raise HTTPException(status_code=400, detail=f"项目 '{name}' 已存在")

        proj_dir = _get_project_dir(user_id, name)
        proj_dir.mkdir(parents=True, exist_ok=True)

        project_meta = {
            "name": name,
            "owner": user_id,
            "created_at": time.time(),
            "github_url": req.github_url.strip(),
            "github_branch": "main",
            "last_synced": 0.0,
            "doc_count": 0,
        }
        projects = _load_projects()
        projects.append(project_meta)
        _save_projects(projects)

        logger.info(f"Code mode: user {user_id} created project '{name}'")

        return ProjectInfo(
            name=name,
            owner=user_id,
            path=str(proj_dir.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            created_at=project_meta["created_at"],
            github_url=project_meta["github_url"],
            github_branch=project_meta["github_branch"],
            file_count=0,
            doc_count=0,
        )

    @app.delete("/api/code/projects/{name}")
    async def delete_project(
        name: str,
        user: dict = Depends(get_current_user),
    ):
        """Delete a project and all its files."""
        _require_admin(user)

        user_id = user["user_id"]
        projects = _load_projects()
        proj = next((p for p in projects if p["name"] == name and p["owner"] == user_id), None)
        if not proj:
            raise HTTPException(status_code=404, detail="项目不存在")

        proj_dir = _get_project_dir(user_id, name)
        shutil.rmtree(proj_dir, ignore_errors=True)

        projects = [p for p in projects if not (p["name"] == name and p["owner"] == user_id)]
        _save_projects(projects)

        logger.info(f"Code mode: user {user_id} deleted project '{name}'")
        return {"ok": True, "name": name}

    @app.post("/api/code/projects/{name}/sync")
    async def sync_project(
        name: str,
        user: dict = Depends(get_current_user),
    ):
        """Sync project from linked GitHub repo (git pull)."""
        _require_admin(user)

        user_id = user["user_id"]
        projects = _load_projects()
        proj = next((p for p in projects if p["name"] == name and p["owner"] == user_id), None)
        if not proj:
            raise HTTPException(status_code=404, detail="项目不存在")
        if not proj.get("github_url"):
            raise HTTPException(status_code=400, detail="项目未关联 GitHub 仓库")

        proj_dir = _get_project_dir(user_id, name)
        if (proj_dir / ".git").exists():
            # Git pull
            try:
                result = subprocess.run(
                    ["git", "pull", "origin", proj.get("github_branch", "main")],
                    cwd=str(proj_dir), capture_output=True, text=True, timeout=60,
                )
                logger.info(f"Git pull {name}: {result.stdout[:200]}")
                proj["last_synced"] = time.time()
                _save_projects(projects)
                return {"ok": True, "output": result.stdout}
            except subprocess.TimeoutExpired:
                raise HTTPException(status_code=504, detail="Git 同步超时")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Git 同步失败: {e}")
        else:
            raise HTTPException(status_code=400, detail="项目未初始化 Git，请先通过 GitHub 克隆创建")

    @app.get("/api/code/files", response_model=FileListResponse)
    async def list_files(
        project: str = Query(default=""),
        path: str = Query(default=""),
        user: dict = Depends(get_current_user),
    ):
        """List files in user's project."""
        _require_admin(user)

        user_id = user["user_id"]
        if project and not _project_exists(user_id, project):
            raise HTTPException(status_code=404, detail="项目不存在")

        base_dir = _get_project_dir(user_id, project) if project else _get_user_code_dir(user_id)
        dir_path = base_dir / path if path else base_dir

        if not dir_path.exists() or not dir_path.is_dir():
            raise HTTPException(status_code=404, detail="目录不存在")

        items: list[FileItem] = []
        try:
            entries = sorted(
                dir_path.iterdir(),
                key=lambda e: (not e.is_dir(), e.name.lower())
            )
            for entry in entries:
                if _should_exclude(entry.name):
                    continue
                if entry.name.startswith(".") and entry.name not in (".gitignore", ".env.example"):
                    continue
                rel = str(entry.relative_to(PROJECT_ROOT)).replace("\\", "/")
                items.append(FileItem(
                    name=entry.name,
                    path=rel,
                    type="dir" if entry.is_dir() else "file",
                    size=entry.stat().st_size if entry.is_file() else 0,
                ))
        except PermissionError:
            raise HTTPException(status_code=403, detail="无权限访问此目录")

        return FileListResponse(path=path or ".", items=items)

    @app.get("/api/code/file")
    async def read_file(
        project: str = Query(default=""),
        path: str = Query(...),
        user: dict = Depends(get_current_user),
    ):
        """Read a file from user's project."""
        _require_admin(user)

        file_path = _resolve_project_path(user["user_id"], project, path)
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="文件不存在")

        if file_path.stat().st_size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="文件过大 (max 2MB)")

        if not _is_text_file(file_path):
            raise HTTPException(status_code=400, detail="不支持此文件类型")

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = file_path.read_text(encoding="gbk")
            except Exception:
                raise HTTPException(status_code=400, detail="无法读取文件编码")

        return {
            "path": path,
            "content": content,
            "size": file_path.stat().st_size,
            "lang": _lang_from_path(path),
        }

    @app.put("/api/code/file")
    async def write_file(
        req: FileContentRequest,
        project: str = Query(default=""),
        user: dict = Depends(get_current_user),
    ):
        """Write content to a file."""
        _require_admin(user)
        file_path = _resolve_project_path(user["user_id"], project, req.path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_path.write_text(req.content, encoding="utf-8")
        logger.info(
            f"Code mode: {user['user_id']} wrote {req.path} "
            f"({len(req.content)} chars)"
        )

        return {"ok": True, "path": req.path, "size": len(req.content)}

    @app.delete("/api/code/file")
    async def delete_file(
        project: str = Query(default=""),
        path: str = Query(...),
        user: dict = Depends(get_current_user),
    ):
        """Delete a file."""
        _require_admin(user)
        file_path = _resolve_project_path(user["user_id"], project, path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        if file_path.is_dir():
            raise HTTPException(status_code=400, detail="不能删除目录，请使用命令行")

        file_path.unlink()
        logger.info(f"Code mode: {user['user_id']} deleted {path}")

        return {"ok": True, "path": path}

    @app.post("/api/code/diff", response_model=DiffResponse)
    async def compute_diff(
        req: DiffRequest,
        user: dict = Depends(get_current_user),
    ):
        """Compute unified diff between old and new content."""
        _require_admin(user)
        file_path = _resolve_project_path(user["user_id"], req.project, req.path)
        _ = file_path  # used only for validation

        old_lines = req.old_content.splitlines(keepends=True)
        new_lines = req.new_content.splitlines(keepends=True)

        diff_lines = list(difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"a/{req.path}",
            tofile=f"b/{req.path}",
            lineterm="",
        ))

        diff_text = "\n".join(diff_lines)
        return DiffResponse(
            path=req.path,
            diff=diff_text,
            has_changes=len(diff_lines) > 0,
        )

    @app.post("/api/code/apply-diff")
    async def apply_diff(
        req: DiffRequest,
        user: dict = Depends(get_current_user),
    ):
        """Apply new content directly to a file (from chat diff cards)."""
        _require_admin(user)
        file_path = _resolve_project_path(user["user_id"], req.project, req.path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        backup = ""
        if file_path.exists():
            try:
                backup = file_path.read_text(encoding="utf-8")
            except Exception:
                pass

        file_path.write_text(req.new_content, encoding="utf-8")
        logger.info(f"Code mode: {user['user_id']} applied diff to {req.path}")

        return {
            "ok": True,
            "path": req.path,
            "backup": backup[:500] if len(backup) > 500 else backup,
        }

    @app.get("/api/code/search")
    async def search_files(
        q: str = Query(...),
        project: str = Query(default=""),
        path: str = Query(default=""),
        user: dict = Depends(get_current_user),
    ):
        """Search for files by name."""
        _require_admin(user)

        user_id = user["user_id"]
        base = _get_project_dir(user_id, project) if project else _get_user_code_dir(user_id)
        if path:
            base = base / path
        results: list[dict] = []

        term = q.lower()
        for item in base.rglob("*"):
            if _should_exclude(item.name):
                continue
            if item.name.startswith(".") and item.name not in (".gitignore",):
                continue
            if term in item.name.lower():
                rel = str(item.relative_to(PROJECT_ROOT)).replace("\\", "/")
                results.append({
                    "name": item.name,
                    "path": rel,
                    "type": "dir" if item.is_dir() else "file",
                })
            if len(results) >= 30:
                break

        return {"query": q, "results": results}

    logger.info("Code mode API routes registered")
