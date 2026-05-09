"""LivingTree Memory — Cognee-integrated memory for AI agents.

Provides remember / recall / forget operations scoped by user and workspace.
Layers: session memory (fast cache) → persistent knowledge graph (Cognee).

Usage:
    from livingtree.core.session_memory import agent_memory

    await agent_memory.remember("Fixed JWT bug in auth.py", user_id="dev_1", project="myapp")
    results = await agent_memory.recall("JWT bug", user_id="dev_1")
    await agent_memory.forget(user_id="dev_1", project="myapp")

Cognee is optional — falls back to in-memory JSON store if not installed.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MEMORY_DIR = PROJECT_ROOT / "data" / "memory"

_cognee_available = False
try:
    import cognee  # noqa: F401
    _cognee_available = True
except ImportError:
    pass


class AgentMemory:
    """LivingTree agent memory — wraps Cognee with user/workspace scoping."""

    def __init__(self):
        self._initialized = False
        self._fallback_file = MEMORY_DIR / "fallback_memory.json"

    async def _ensure_init(self):
        if self._initialized:
            return
        if _cognee_available:
            try:
                import cognee
                await cognee.prune.prune_data()
                await cognee.prune.prune_system(metadata=True)
                logger.info("Cognee memory engine initialized")
            except Exception as e:
                logger.warning(f"Cognee init failed, using fallback: {e}")
        self._initialized = True

    # ── Fallback store ──

    def _load_fallback(self) -> list[dict]:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        if self._fallback_file.exists():
            try:
                return json.loads(self._fallback_file.read_text())
            except Exception:
                pass
        return []

    def _save_fallback(self, entries: list[dict]):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self._fallback_file.write_text(json.dumps(entries, ensure_ascii=False, indent=2))

    # ── Public API ──

    async def remember(
        self,
        content: str,
        *,
        user_id: str = "",
        project: str = "",
        workspace_id: str = "",
        dataset: str = "livingtree_main",
        metadata: Optional[dict] = None,
    ) -> bool:
        """Store a memory entry scoped by user/project/workspace."""
        await self._ensure_init()

        scope = f"user={user_id}" if user_id else "global"
        if project:
            scope += f":project={project}"
        if workspace_id:
            scope += f":workspace={workspace_id}"

        if _cognee_available:
            try:
                import cognee
                full_text = f"[{scope}] {content}"
                await cognee.add(full_text, dataset_name=dataset)
                await cognee.cognify(dataset_name=dataset)
                logger.debug(f"Memory: remembered [{scope}] {content[:80]}")
                return True
            except Exception as e:
                logger.warning(f"Memory remember failed: {e}")

        # Fallback
        entries = self._load_fallback()
        entries.append({
            "content": content,
            "scope": scope,
            "user_id": user_id,
            "project": project,
            "workspace_id": workspace_id,
            "dataset": dataset,
            "metadata": metadata or {},
            "timestamp": time.time(),
        })
        # Trim to last 500 entries
        if len(entries) > 500:
            entries = entries[-500:]
        self._save_fallback(entries)
        return True

    async def recall(
        self,
        query: str,
        *,
        user_id: str = "",
        project: str = "",
        workspace_id: str = "",
        dataset: str = "livingtree_main",
        limit: int = 5,
    ) -> list[str]:
        """Recall relevant memories, scoped by user/project/workspace."""
        await self._ensure_init()

        if _cognee_available:
            try:
                import cognee
                results = await cognee.search(
                    query_text=query,
                    dataset_name=dataset,
                    top_k=limit,
                )
                # Filter by scope
                scoped = []
                for r in results:
                    text = str(r) if not isinstance(r, dict) else r.get("text", str(r))
                    if user_id and user_id not in text:
                        continue
                    if project and project not in text:
                        continue
                    if len(text) > 300:
                        text = text[:297] + "..."
                    scoped.append(text)
                if scoped:
                    logger.debug(f"Memory: recalled {len(scoped)} items for '{query[:50]}'")
                return scoped[:limit]
            except Exception as e:
                logger.warning(f"Memory recall failed: {e}")

        # Fallback: simple keyword matching
        entries = self._load_fallback()
        query_lower = query.lower()
        matched = []
        for entry in reversed(entries):
            if user_id and entry.get("user_id") != user_id:
                continue
            if project and entry.get("project") != project:
                continue
            if workspace_id and entry.get("workspace_id") != workspace_id:
                continue
            content = entry.get("content", "")
            if query_lower in content.lower():
                matched.append(content)
            elif any(word in content.lower() for word in query_lower.split() if len(word) > 1):
                matched.append(content)
        return matched[:limit]

    async def forget(
        self,
        *,
        user_id: str = "",
        project: str = "",
        dataset: str = "livingtree_main",
    ) -> bool:
        """Forget memories for a scope or entire dataset."""
        await self._ensure_init()

        if _cognee_available:
            try:
                import cognee
                await cognee.forget(dataset=dataset)
                logger.info(f"Memory: forgot dataset '{dataset}'")
                return True
            except Exception as e:
                logger.warning(f"Memory forget failed: {e}")

        # Fallback
        if not user_id and not project:
            entries = []
        else:
            entries = self._load_fallback()
            entries = [
                e for e in entries
                if not (
                    (user_id and e.get("user_id") == user_id)
                    and (project and e.get("project") == project)
                )
            ]
        self._save_fallback(entries)
        return True

    async def get_context_injection(
        self,
        user_message: str,
        *,
        user_id: str = "",
        project: str = "",
        workspace_id: str = "",
        max_tokens: int = 500,
    ) -> str:
        """Get relevant memories formatted as context injection for LLM prompt."""
        memories = await self.recall(
            user_message,
            user_id=user_id,
            project=project,
            workspace_id=workspace_id,
            limit=5,
        )
        if not memories:
            return ""

        lines = ["## 相关历史记忆"]
        for i, m in enumerate(memories, 1):
            lines.append(f"{i}. {m}")
        return "\n".join(lines)


# ── Document Ingestion (MarkItDown → Cognee) ──

_MD_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".csv", ".json", ".xml",
                  ".html", ".htm", ".png", ".jpg", ".jpeg", ".mp3", ".wav", ".epub"}


async def ingest_document(
    file_path: str,
    *,
    user_id: str = "",
    project: str = "",
    workspace_id: str = "",
) -> dict:
    """Parse a document with MarkItDown and feed it into agent memory.

    Uses system's existing MarkItDown integration. Falls back to plain
    text reading for .txt/.md files.
    """
    from pathlib import Path
    fpath = Path(file_path)
    if not fpath.exists():
        return {"ok": False, "error": f"文件不存在: {file_path}"}

    suffix = fpath.suffix.lower()
    markdown = ""

    # MarkItDown for Office/PDF/image documents
    if suffix in _MD_EXTENSIONS:
        try:
            from markitdown import MarkItDown
            md = MarkItDown()
            result = md.convert(str(fpath))
            markdown = result.text_content.strip()
        except ImportError:
            pass
        except Exception as e:
            return {"ok": False, "error": f"MarkItDown 解析失败: {e}"}

    # Plain text for .txt/.md/.py etc.
    if not markdown:
        try:
            markdown = fpath.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                markdown = fpath.read_text(encoding="gbk")
            except Exception as e:
                return {"ok": False, "error": f"文件编码读取失败: {e}"}

    if not markdown.strip():
        return {"ok": False, "error": "未能提取文本内容"}

    # Feed into agent memory
    summary = markdown[:2000] + ("..." if len(markdown) > 2000 else "")
    await agent_memory.remember(
        f"文档 '{fpath.name}' 内容:\n{summary}",
        user_id=user_id, project=project, workspace_id=workspace_id,
    )

    return {
        "ok": True,
        "file_name": fpath.name,
        "char_count": len(markdown),
        "markdown": markdown,
        "summary": summary,
    }


# ── Singleton ──

agent_memory = AgentMemory()
