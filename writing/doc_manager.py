"""
文档管理器
负责项目文档的创建、编辑、保存、列表
"""

import json
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from client.src.business.config import get_projects_dir


@dataclass
class DocInfo:
    path: str
    title: str
    size: int
    modified: float
    project: str


class DocManager:
    """
    文档管理器
    - 创建/编辑/删除 Markdown 文档
    - 从 frontmatter 提取标题
    - 自动保存
    - 项目隔离
    """

    def __init__(self):
        self._projects_dir = get_projects_dir()
        self._projects_dir.mkdir(parents=True, exist_ok=True)

    # ── 项目 ───────────────────────────────────────────────────

    def list_projects(self) -> list[str]:
        return sorted([
            p.name for p in self._projects_dir.iterdir()
            if p.is_dir() and not p.name.startswith(".")
        ])

    def create_project(self, name: str, description: str = "") -> str:
        p = self._projects_dir / name
        p.mkdir(parents=True, exist_ok=True)
        (p / "docs").mkdir(exist_ok=True)
        (p / "assets").mkdir(exist_ok=True)

        meta = {
            "name": name,
            "description": description,
            "created": self._now(),
        }
        (p / ".project.meta").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return str(p)

    def get_project_meta(self, name: str) -> dict:
        p = self._projects_dir / name
        meta_file = p / ".project.meta"
        if meta_file.exists():
            try:
                return json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"name": name, "description": ""}

    def delete_project(self, name: str) -> bool:
        import shutil
        p = self._projects_dir / name
        if p.exists():
            shutil.rmtree(str(p))
            return True
        return False

    # ── 文档 ───────────────────────────────────────────────────

    def list_documents(self, project_name: str) -> list[DocInfo]:
        docs_dir = self._projects_dir / project_name / "docs"
        if not docs_dir.exists():
            return []
        results = []
        for f in sorted(docs_dir.glob("*.md")):
            try:
                stat = f.stat()
                title = self._extract_title(f) or f.stem
                results.append(DocInfo(
                    path=str(f),
                    title=title,
                    size=stat.st_size,
                    modified=stat.st_mtime,
                    project=project_name,
                ))
            except Exception:
                pass
        return results

    def create_document(
        self,
        project_name: str,
        title: str,
        content: str = "",
        author: str = "Hermes",
    ) -> str:
        """创建文档，返回文件路径"""
        docs_dir = self._projects_dir / project_name / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)

        filename = self._slugify(title) + ".md"
        filepath = docs_dir / filename

        # 避免覆盖已有文件
        counter = 1
        while filepath.exists():
            filename = f"{self._slugify(title)}_{counter}.md"
            filepath = docs_dir / filename
            counter += 1

        # YAML frontmatter
        frontmatter = f"""---
title: "{title}"
created: "{self._now()}"
author: "{author}"
---

"""
        filepath.write_text(frontmatter + content, encoding="utf-8")
        return str(filepath)

    def save_document(self, path: str, content: str) -> bool:
        """保存文档"""
        p = Path(path)
        if not p.exists():
            return False
        try:
            # 保留原有 frontmatter
            existing = p.read_text(encoding="utf-8")
            frontmatter = ""
            if existing.startswith("---"):
                parts = existing.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = "---\n" + parts[1] + "\n---\n"
                    # 更新修改时间
                    import re
                    fm_text = parts[1]
                    fm_text = re.sub(
                        r'^modified:.*$', f'modified: "{self._now()}"', fm_text,
                        flags=re.MULTILINE
                    )
                    frontmatter = "---\n" + fm_text + "\n---\n"

            p.write_text(frontmatter + content, encoding="utf-8")
            return True
        except Exception:
            return False

    def read_document(self, path: str) -> str:
        """读取文档（去掉 frontmatter）"""
        p = Path(path)
        if not p.exists():
            return ""
        text = p.read_text(encoding="utf-8")
        # 去掉 frontmatter
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                return parts[2].lstrip("\n")
        return text

    def delete_document(self, path: str) -> bool:
        p = Path(path)
        if p.exists() and p.suffix == ".md":
            p.unlink()
            return True
        return False

    def get_document_meta(self, path: str) -> dict:
        """从 frontmatter 提取元数据"""
        p = Path(path)
        if not p.exists():
            return {}
        text = p.read_text(encoding="utf-8")
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                meta = {}
                for line in parts[1].split("\n"):
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip().strip('"')
                return meta
        return {}

    def update_title(self, path: str, new_title: str) -> bool:
        """更新文档标题"""
        p = Path(path)
        if not p.exists():
            return False
        text = p.read_text(encoding="utf-8")
        import re
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                fm_lines = parts[1].split("\n")
                new_fm_lines = []
                found = False
                for line in fm_lines:
                    if line.startswith("title:"):
                        new_fm_lines.append(f'title: "{new_title}"')
                        found = True
                    else:
                        new_fm_lines.append(line)
                if not found:
                    new_fm_lines.insert(0, f'title: "{new_title}"')
                text = "---\n" + "\n".join(new_fm_lines) + "\n---\n" + parts[2]
                p.write_text(text, encoding="utf-8")
                return True
        return False

    # ── 辅助 ───────────────────────────────────────────────────

    def _extract_title(self, path: Path) -> str | None:
        """从 frontmatter 提取标题"""
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    for line in parts[1].split("\n"):
                        if line.startswith("title:"):
                            return line.split(":", 1)[1].strip().strip('"')
        except Exception:
            pass
        return None

    @staticmethod
    def _slugify(text: str) -> str:
        import re
        text = re.sub(r'[<>:"/\\|?*]', '_', text)
        text = re.sub(r'\s+', '-', text)
        text = re.sub(r'-+', '-', text)
        return text.strip('-').lower()[:80]

    @staticmethod
    def _now() -> str:
        return time.strftime("%Y-%m-%d %H:%M")
