"""VirtualFS — Mirage-inspired Unified Virtual File System for AI Agents.

Everything is a file path. AI agents use familiar commands (ls, cat, grep, cp, find)
across ALL backends — local disk, HTTP, GitHub, knowledge base, RAM — as if they
were one filesystem.

Mounts:
    /ram/       ← in-memory scratch space
    /disk/      ← local filesystem
    /web/       ← HTTP resources
    /github/    ← GitHub repos
    /kb/        ← knowledge base

Usage:
    from livingtree.capability.virtual_fs import get_virtual_fs

    vfs = get_virtual_fs()
    result = await vfs.execute("ls /disk/project")
    result = await vfs.execute("cat /github/myrepo/readme.md")
    result = await vfs.execute("grep -i error /disk/logs/*.log")
    result = await vfs.execute("cp /web/arxiv/fetch /ram/tmp/arxiv.txt")
    result = await vfs.execute("find /kb -name '*memory*'")
"""
from __future__ import annotations

import asyncio
import base64
import fnmatch
import hashlib
import os
import shlex
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import aiohttp
from loguru import logger


# ══════════════════════════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════════════════════════

@dataclass
class VFSEntry:
    """A single entry in the virtual filesystem (file or directory)."""
    name: str
    path: str
    is_dir: bool = False
    size: int = 0
    modified: float = 0.0
    resource_type: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════════
# Resource Base Class
# ══════════════════════════════════════════════════════════════════════

class Resource(ABC):
    """Abstract base for all filesystem backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable resource name (e.g. 'ram', 'disk', 'web')."""
        ...

    @abstractmethod
    async def list_dir(self, path: str) -> list[VFSEntry]:
        """List entries in a virtual directory path."""
        ...

    @abstractmethod
    async def read_file(self, path: str) -> str:
        """Read content from a virtual file path."""
        ...

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if a virtual path exists."""
        ...

    async def write_file(self, path: str, content: str) -> None:
        """Write content to a virtual file path (optional)."""
        raise NotImplementedError(f"{self.name}: write not supported")


# ══════════════════════════════════════════════════════════════════════
# RAMResource — in-memory scratch space
# ══════════════════════════════════════════════════════════════════════

class RAMResource(Resource):
    """In-memory dict-based virtual filesystem.

    Used for scratch space, temp results, agent working memory.
    Full read/write support.
    """

    @property
    def name(self) -> str:
        return "ram"

    def __init__(self):
        self._store: dict[str, str] = {}
        self._dirs: set[str] = {"/"}

    def _normalize(self, path: str) -> str:
        p = path.replace("\\", "/").rstrip("/") or "/"
        return p if p.startswith("/") else "/" + p

    async def list_dir(self, path: str) -> list[VFSEntry]:
        norm = self._normalize(path)
        prefix = norm if norm == "/" else norm + "/"
        entries: dict[str, VFSEntry] = {}
        now = time.time()

        for p in self._dirs:
            if p == norm or not p.startswith(prefix) or p == prefix.rstrip("/"):
                continue
            rest = p[len(prefix):]
            if "/" in rest:
                continue
            entries[rest] = VFSEntry(
                name=rest, path=p, is_dir=True, size=0,
                modified=now, resource_type="ram",
            )

        for p, content in self._store.items():
            if not p.startswith(prefix):
                continue
            rest = p[len(prefix):]
            if "/" in rest:
                continue
            entries[rest] = VFSEntry(
                name=rest, path=p, is_dir=False,
                size=len(content.encode("utf-8")),
                modified=now, resource_type="ram",
            )

        return sorted(entries.values(), key=lambda e: (not e.is_dir, e.name))

    async def read_file(self, path: str) -> str:
        norm = self._normalize(path)
        if norm not in self._store:
            raise FileNotFoundError(f"RAM: {path} not found")
        return self._store[norm]

    async def write_file(self, path: str, content: str) -> None:
        norm = self._normalize(path)
        self._store[norm] = content
        parts = norm.strip("/").split("/")
        for i in range(len(parts) + 1):
            d = "/" + "/".join(parts[:i])
            self._dirs.add(d if d else "/")

    async def exists(self, path: str) -> bool:
        norm = self._normalize(path)
        return norm in self._store or norm in self._dirs

    def snapshot(self) -> dict:
        return {"store": dict(self._store), "dirs": sorted(self._dirs)}

    def restore(self, data: dict) -> None:
        self._store = data.get("store", {})
        self._dirs = set(data.get("dirs", ["/"]))


# ══════════════════════════════════════════════════════════════════════
# DiskResource — local filesystem
# ══════════════════════════════════════════════════════════════════════

class DiskResource(Resource):
    r"""Local filesystem backend. Translates /disk/sub/path -> root_path\sub\path."""

    @property
    def name(self) -> str:
        return "disk"

    def __init__(self, root_path: str | Path = "."):
        self._root = Path(root_path).resolve()

    async def list_dir(self, path: str) -> list[VFSEntry]:
        real = self._to_real(path)
        if not real.is_dir():
            raise NotADirectoryError(f"Disk: {path} is not a directory")
        try:
            from ..infrastructure.fast_fs import get_fast_fs
            ffs = get_fast_fs()
            fast_entries = ffs.list_dir(str(real))
            if fast_entries:
                return [VFSEntry(
                    name=e.name, path=self._normalize_vpath(Path(e.full_path)),
                    is_dir=e.is_dir, size=e.size, modified=e.mtime,
                    resource_type="disk",
                ) for e in fast_entries]
        except Exception:
            pass
        entries = []
        try:
            with os.scandir(str(real)) as it:
                for entry in it:
                    stat = entry.stat()
                    entries.append(VFSEntry(
                        name=entry.name,
                        path=self._normalize_vpath(real / entry.name),
                        is_dir=entry.is_dir(),
                        size=stat.st_size if not entry.is_dir() else 0,
                        modified=stat.st_mtime,
                        resource_type="disk",
                    ))
        except PermissionError:
            pass
        return sorted(entries, key=lambda e: (not e.is_dir, e.name))

    async def read_file(self, path: str) -> str:
        real = self._to_real(path)
        if not real.is_file():
            raise FileNotFoundError(f"Disk: {path} not found")
        try:
            from ..infrastructure.fast_fs import get_fast_fs
            ffs = get_fast_fs()
            text = ffs.read_text(str(real))
            if text:
                return text
        except Exception:
            pass
        return real.read_text(encoding="utf-8", errors="replace")

    async def write_file(self, path: str, content: str) -> None:
        real = self._to_real(path)
        real.parent.mkdir(parents=True, exist_ok=True)
        real.write_text(content, encoding="utf-8")

    async def exists(self, path: str) -> bool:
        return self._to_real(path).exists()

    def _to_real(self, vpath: str) -> Path:
        rel = vpath.replace("\\", "/").lstrip("/")
        if rel.startswith("disk/") or rel == "disk":
            parts = rel.split("/", 1)
            rel = parts[1] if len(parts) > 1 else ""
        return self._root / rel

    def _normalize_vpath(self, real: Path) -> str:
        try:
            rel = real.resolve().relative_to(self._root)
        except ValueError:
            rel = real
        return "/disk/" + str(rel).replace("\\", "/")

    def walk_files(self, vpath: str, pattern: str = "*") -> list[VFSEntry]:
        real = self._to_real(vpath)
        if not real.is_dir():
            return []
        try:
            from ..infrastructure.fast_fs import get_fast_fs
            ffs = get_fast_fs()
            fast_entries = ffs.scan_tree(str(real), max_depth=5)
            if fast_entries:
                results = []
                for e in fast_entries:
                    if not e.is_dir and fnmatch.fnmatch(e.name, pattern):
                        results.append(VFSEntry(
                            name=e.name, path=self._normalize_vpath(Path(e.full_path)),
                            is_dir=False, size=e.size, modified=e.mtime,
                            resource_type="disk",
                        ))
                return results
        except Exception:
            pass
        results = []
        for root, dirs, files in os.walk(str(real)):
            depth = Path(root).relative_to(real).parts if real != Path(root) else []
            if len(depth) >= 5:
                dirs.clear()
            for name in files:
                if fnmatch.fnmatch(name, pattern):
                    fp = Path(root) / name
                    stat = fp.stat()
                    results.append(VFSEntry(
                        name=name, path=self._normalize_vpath(fp),
                        is_dir=False, size=stat.st_size,
                        modified=stat.st_mtime, resource_type="disk",
                    ))
        return results


# ══════════════════════════════════════════════════════════════════════
# HTTPResource — web resources via HTTP GET
# ══════════════════════════════════════════════════════════════════════

class HTTPResource(Resource):
    """HTTP backend. read_file() does HTTP GET to base_url + path. Read-only."""

    @property
    def name(self) -> str:
        return "web"

    def __init__(self, base_url: str = "https://httpbin.org/get"):
        self._base = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def list_dir(self, path: str) -> list[VFSEntry]:
        return []

    async def read_file(self, path: str) -> str:
        rel = self._to_rel(path)
        url = f"{self._base}/{rel}" if rel else self._base
        session = await self._get_session()
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status >= 400:
                    raise FileNotFoundError(f"HTTP {resp.status}: {url}")
                text = await resp.text()
                content_type = resp.headers.get("Content-Type", "")
                if "text/" not in content_type and "application/json" not in content_type:
                    raise ValueError(
                        f"HTTP: binary/non-text content at {url} "
                        f"(Content-Type: {content_type})"
                    )
                return text

    async def exists(self, path: str) -> bool:
        try:
            await self.read_file(path)
            return True
        except (FileNotFoundError, Exception):
            return False

    def _to_rel(self, vpath: str) -> str:
        rel = vpath.replace("\\", "/").lstrip("/")
        if rel.startswith("web/") or rel == "web":
            parts = rel.split("/", 1)
            rel = parts[1] if len(parts) > 1 else ""
        return rel


# ══════════════════════════════════════════════════════════════════════
# GitHubResource — GitHub API filesystem
# ══════════════════════════════════════════════════════════════════════

class GitHubResource(Resource):
    """GitHub API backend. Maps /github/{owner}/{repo}/... to API calls. Read-only.

    If token not provided, attempts to load from livingtree.config.secrets
    (github_token key). Falls back to unauthenticated access.
    """

    API_BASE = "https://api.github.com"

    @property
    def name(self) -> str:
        return "github"

    def __init__(self, token: str = "", owner: str = "", repo: str = ""):
        self._token = token
        if not self._token:
            try:
                from ..config.secrets import get_secret_vault
                self._token = get_secret_vault().get("github_token", "")
            except Exception:
                pass
        self._owner = owner
        self._repo = repo
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def list_dir(self, path: str) -> list[VFSEntry]:
        owner, repo, subpath = self._parse_path(path)
        url = f"{self.API_BASE}/repos/{owner}/{repo}/contents/{subpath}" if subpath else \
              f"{self.API_BASE}/repos/{owner}/{repo}/contents"
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        session = await self._get_session()
        async with session.get(url, headers=headers,
                               timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 404:
                return []
            if resp.status >= 400:
                logger.warning(f"GitHub API {resp.status}: {url}")
                return []
            data = await resp.json()

        entries = []
        if isinstance(data, list):
            for item in data:
                entries.append(VFSEntry(
                    name=item.get("name", ""),
                    path=f"/github/{owner}/{repo}/{item.get('path', '')}",
                    is_dir=item.get("type") == "dir",
                    size=item.get("size", 0),
                    modified=time.time(),
                    resource_type="github",
                    metadata={
                        "sha": item.get("sha", ""),
                        "url": item.get("html_url", ""),
                    },
                ))
        return sorted(entries, key=lambda e: (not e.is_dir, e.name))

    async def read_file(self, path: str) -> str:
        owner, repo, subpath = self._parse_path(path)
        url = f"{self.API_BASE}/repos/{owner}/{repo}/contents/{subpath}"
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        session = await self._get_session()
        async with session.get(url, headers=headers,
                               timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status >= 400:
                raise FileNotFoundError(
                    f"GitHub {resp.status}: {owner}/{repo}/{subpath}"
                )
            data = await resp.json()

        if isinstance(data, dict) and data.get("content"):
            try:
                return base64.b64decode(data["content"]).decode("utf-8")
            except Exception as e:
                raise ValueError(f"GitHub: decode error for {subpath}: {e}")

        raise FileNotFoundError(f"GitHub: not a file: {owner}/{repo}/{subpath}")

    async def exists(self, path: str) -> bool:
        try:
            owner, repo, _ = self._parse_path(path)
            return bool(owner and repo)
        except Exception:
            return False

    def _parse_path(self, vpath: str) -> tuple[str, str, str]:
        parts = vpath.replace("\\", "/").strip("/").split("/")
        owner = parts[0] if len(parts) > 0 else self._owner
        repo = parts[1] if len(parts) > 1 else self._repo
        subpath = "/".join(parts[2:]) if len(parts) > 2 else ""
        return owner, repo, subpath


# ══════════════════════════════════════════════════════════════════════
# KBResource — LivingTree Knowledge Base
# ══════════════════════════════════════════════════════════════════════

class KBResource(Resource):
    """LivingTree Knowledge Base backend. Read-only.

    Subdirectories:
        /kb/documents/     -> KnowledgeBase documents
        /kb/memories/      -> StructMem entries
        /kb/synthesis/     -> StructMem synthesis blocks
    """

    @property
    def name(self) -> str:
        return "kb"

    def __init__(self):
        self._kb = None
        self._mem = None

    def _ensure_kb(self):
        if self._kb is not None:
            return
        try:
            from ..knowledge.knowledge_base import KnowledgeBase
            self._kb = KnowledgeBase()
        except Exception as e:
            logger.warning(f"KBResource: KnowledgeBase init failed: {e}")
            self._kb = False

    def _ensure_mem(self):
        if self._mem is not None:
            return
        try:
            from ..knowledge.struct_mem import get_struct_mem
            self._mem = get_struct_mem()
        except Exception as e:
            logger.warning(f"KBResource: StructMem init failed: {e}")
            self._mem = False

    async def list_dir(self, path: str) -> list[VFSEntry]:
        norm = path.replace("\\", "/").strip("/")

        if norm in ("kb", "kb/", ""):
            return [
                VFSEntry(name="documents", path="/kb/documents",
                         is_dir=True, resource_type="kb"),
                VFSEntry(name="memories", path="/kb/memories",
                         is_dir=True, resource_type="kb"),
                VFSEntry(name="synthesis", path="/kb/synthesis",
                         is_dir=True, resource_type="kb"),
            ]

        if norm.startswith("kb/documents"):
            self._ensure_kb()
            if self._kb is False:
                return []
            try:
                docs = self._kb.storage.list_documents()
                return [
                    VFSEntry(
                        name=doc.id, path=f"/kb/documents/{doc.id}",
                        is_dir=False, size=len(doc.content.encode("utf-8")),
                        modified=doc.updated_at.timestamp()
                        if hasattr(doc.updated_at, 'timestamp') else time.time(),
                        resource_type="kb",
                        metadata={"title": doc.title, "domain": doc.domain or ""},
                    )
                    for doc in docs
                ]
            except Exception as e:
                logger.warning(f"KBResource list documents: {e}")
                return []

        if norm.startswith("kb/memories"):
            self._ensure_mem()
            if self._mem is False:
                return []
            try:
                entries = []
                for eid, entry in self._mem._entries.items():
                    entries.append(VFSEntry(
                        name=eid, path=f"/kb/memories/{eid}",
                        is_dir=False,
                        size=len((entry.content or "").encode("utf-8")),
                        modified=time.time(),
                        resource_type="kb",
                        metadata={
                            "timestamp": entry.timestamp,
                            "role": entry.role,
                            "session_id": entry.session_id,
                        },
                    ))
                return entries
            except Exception as e:
                logger.warning(f"KBResource list memories: {e}")
                return []

        if norm.startswith("kb/synthesis"):
            self._ensure_mem()
            if self._mem is False:
                return []
            try:
                blocks = []
                for s in self._mem._synthesis:
                    blocks.append(VFSEntry(
                        name=s.id, path=f"/kb/synthesis/{s.id}",
                        is_dir=False,
                        size=len((s.content or "").encode("utf-8")),
                        modified=time.time(),
                        resource_type="kb",
                        metadata={
                            "timestamp": s.timestamp,
                            "source_entries": len(s.source_entries),
                        },
                    ))
                return blocks
            except Exception as e:
                logger.warning(f"KBResource list synthesis: {e}")
                return []

        return []

    async def read_file(self, path: str) -> str:
        norm = path.replace("\\", "/").strip("/")

        if norm.startswith("kb/documents/"):
            doc_id = norm[len("kb/documents/"):]
            self._ensure_kb()
            if self._kb is False:
                raise FileNotFoundError(f"KB: KnowledgeBase unavailable")
            doc = self._kb.storage.get_document(doc_id)
            if doc is None:
                raise FileNotFoundError(f"KB: document {doc_id} not found")
            return doc.content

        if norm.startswith("kb/memories/"):
            mem_id = norm[len("kb/memories/"):]
            self._ensure_mem()
            if self._mem is False:
                raise FileNotFoundError(f"KB: StructMem unavailable")
            entry = self._mem._entries.get(mem_id)
            if entry is None:
                raise FileNotFoundError(f"KB: memory {mem_id} not found")
            return entry.content

        if norm.startswith("kb/synthesis/"):
            syn_id = norm[len("kb/synthesis/"):]
            self._ensure_mem()
            if self._mem is False:
                raise FileNotFoundError(f"KB: StructMem unavailable")
            for s in self._mem._synthesis:
                if s.id == syn_id:
                    return s.content
            raise FileNotFoundError(f"KB: synthesis {syn_id} not found")

        raise FileNotFoundError(f"KB: unknown path {path}")

    async def exists(self, path: str) -> bool:
        norm = path.replace("\\", "/").strip("/")

        if norm in ("kb", "kb/documents", "kb/memories", "kb/synthesis"):
            return True

        try:
            if norm.startswith("kb/documents/"):
                doc_id = norm[len("kb/documents/"):]
                self._ensure_kb()
                return self._kb is not False and self._kb.storage.get_document(doc_id) is not None
            if norm.startswith("kb/memories/"):
                mem_id = norm[len("kb/memories/"):]
                self._ensure_mem()
                return self._mem is not False and mem_id in self._mem._entries
            if norm.startswith("kb/synthesis/"):
                syn_id = norm[len("kb/synthesis/"):]
                self._ensure_mem()
                return self._mem is not False and any(s.id == syn_id for s in self._mem._synthesis)
        except Exception:
            pass
        return False

    async def search(self, query: str) -> list[VFSEntry]:
        """Semantic search across KB documents and memories."""
        results = []
        self._ensure_kb()
        if self._kb and self._kb is not False:
            try:
                docs = self._kb.storage.search(query, top_k=10)
                for doc in docs:
                    results.append(VFSEntry(
                        name=doc.id, path=f"/kb/documents/{doc.id}",
                        size=len(doc.content.encode("utf-8")),
                        resource_type="kb",
                        metadata={"title": doc.title, "score": getattr(doc, 'score', 0)},
                    ))
            except Exception:
                pass
        self._ensure_mem()
        if self._mem and self._mem is not False:
            try:
                entries = self._mem.search(query, top_k=10)
                for e in entries:
                    results.append(VFSEntry(
                        name=e.id, path=f"/kb/memories/{e.id}",
                        resource_type="kb",
                        metadata={"content": e.content[:200]},
                    ))
            except Exception:
                pass
        return results[:20]


# ══════════════════════════════════════════════════════════════════════
# VirtualFS — the workspace orchestrator
# ══════════════════════════════════════════════════════════════════════

class VirtualFS:
    """Unified virtual filesystem orchestrator.

    Parses bash-like commands and executes them across mounted resources.
    Supports: ls, cat, grep, cp, find, wc with pipe chaining.
    """

    def __init__(self, mounts: dict[str, Resource] | None = None):
        self._mounts: dict[str, Resource] = mounts or {
            "/ram": RAMResource(),
            "/disk": DiskResource("."),
        }

    def mount(self, path: str, resource: Resource) -> None:
        path = path.rstrip("/") or "/"
        self._mounts[path] = resource
        logger.info(f"VirtualFS: mounted {resource.name} at {path}")

    def unmount(self, path: str) -> bool:
        path = path.rstrip("/") or "/"
        if path in self._mounts:
            del self._mounts[path]
            logger.info(f"VirtualFS: unmounted {path}")
            return True
        return False

    def list_mounts(self) -> dict[str, str]:
        return {p: r.name for p, r in self._mounts.items()}

    def _resolve(self, path: str) -> tuple[Resource, str]:
        norm = path.replace("\\", "/") or "/"
        best = ""
        best_res: Resource | None = None
        for mp, res in self._mounts.items():
            mp_norm = mp.rstrip("/")
            if norm == mp_norm or norm.startswith(mp_norm + "/") or mp_norm == "/":
                if len(mp_norm) > len(best):
                    best = mp_norm
                    best_res = res
        if best_res is None:
            raise ValueError(f"VirtualFS: no mount for path '{path}'")
        rel = norm[len(best):].lstrip("/")
        return best_res, rel

    # ── Public API ──

    @staticmethod
    def _split_pipes(command: str) -> list[str]:
        """Split command on | only outside of quotes and double quotes."""
        parts: list[str] = []
        current: list[str] = []
        in_single = False
        in_double = False
        for ch in command:
            if ch == "'" and not in_double:
                in_single = not in_single
                current.append(ch)
            elif ch == '"' and not in_single:
                in_double = not in_double
                current.append(ch)
            elif ch == '|' and not in_single and not in_double:
                parts.append(''.join(current).strip())
                current = []
            else:
                current.append(ch)
        parts.append(''.join(current).strip())
        return parts

    async def execute(self, command: str) -> str:
        """Parse and execute a bash-like command across mounted resources.

        Supports pipes: `grep error /disk/log.txt | wc -l`
        """
        pipelines = VirtualFS._split_pipes(command)
        stdin = ""
        for i, cmd_str in enumerate(pipelines):
            args = shlex.split(cmd_str) if cmd_str else []
            if not args:
                continue
            op = args[0].lower()
            op_args = args[1:]

            if op == "ls":
                stdin = await self._cmd_ls(op_args)
            elif op == "cat":
                stdin = await self._cmd_cat(op_args)
            elif op == "grep":
                stdin = await self._cmd_grep(op_args, stdin)
            elif op == "cp":
                stdin = await self._cmd_cp(op_args)
            elif op == "find":
                stdin = await self._cmd_find(op_args)
            elif op == "wc":
                stdin = await self._cmd_wc(op_args, stdin)
            elif op == "echo":
                stdin = " ".join(op_args)
            elif op == "head":
                stdin = self._cmd_head(op_args, stdin)
            elif op == "tail":
                stdin = self._cmd_tail(op_args, stdin)
            else:
                stdin = f"VirtualFS: unknown command '{op}'"

        return stdin

    async def read_file(self, vpath: str) -> str:
        """Direct read of a virtual file path."""
        res, rel = self._resolve(vpath)
        return await res.read_file(rel)

    async def write_file(self, vpath: str, content: str) -> None:
        """Direct write to a virtual file path with content-based dedup check."""
        res, rel = self._resolve(vpath)
        # Dedup: check if content already exists with same hash
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        try:
            existing = await res.read_file(rel)
            if hashlib.sha256(existing.encode()).hexdigest() == content_hash:
                return  # Skip write — identical content
        except Exception:
            pass  # File doesn't exist or can't read — proceed with write
        await res.write_file(rel, content)

    async def dedup_dir(self, vpath: str, delete: bool = False) -> dict:
        """Find and optionally remove duplicate files in a VFS directory.

        Uses SHA256 content hash. Like office_tools.file_deduplicate but VFS-aware.
        """
        res, rel = self._resolve(vpath)
        if not hasattr(res, 'walk_files'):
            return {"error": "Resource does not support directory scanning"}

        entries = res.walk_files(vpath) if hasattr(res, 'walk_files') else []
        if not entries and hasattr(res, 'list_dir'):
            entries = await res.list_dir(rel)

        seen: dict[str, list[str]] = {}
        for entry in entries:
            fpath = entry.path if hasattr(entry, 'path') else str(entry)
            try:
                content = await res.read_file(fpath)
                h = hashlib.sha256(content.encode()).hexdigest()
                seen.setdefault(h, []).append(fpath)
            except Exception:
                continue

        duplicates = {h: paths for h, paths in seen.items() if len(paths) > 1}
        deleted = saved_bytes = 0
        if delete:
            for paths in duplicates.values():
                for dup in paths[1:]:
                    try:
                        saved_bytes += len(await res.read_file(dup))
                        await self._resolve(dup)[0].write_file(
                            self._resolve(dup)[1], "")  # Clear content
                    except Exception:
                        pass
                    deleted += 1

        return {
            "scanned": len(entries),
            "duplicate_groups": len(duplicates),
            "duplicate_files": sum(len(v) - 1 for v in duplicates.values()),
            "deleted": deleted,
            "saved_kb": round(saved_bytes / 1024, 1),
            "samples": [{"hash": h[:12], "count": len(v), "files": v[:3]}
                       for h, v in list(duplicates.items())[:10]],
        }

    async def list_dir(self, vpath: str) -> list[VFSEntry]:
        """Direct list of a virtual directory path."""
        res, rel = self._resolve(vpath)
        return await res.list_dir(rel)

    def snapshot(self) -> dict:
        data: dict[str, Any] = {"mounts": {}}
        for mp, res in self._mounts.items():
            if isinstance(res, RAMResource):
                data["mounts"][mp] = {
                    "type": "ram",
                    "state": res.snapshot(),
                }
            elif isinstance(res, DiskResource):
                data["mounts"][mp] = {
                    "type": "disk",
                    "root": str(res._root),
                }
            elif isinstance(res, HTTPResource):
                data["mounts"][mp] = {
                    "type": "web",
                    "base_url": res._base,
                }
            elif isinstance(res, GitHubResource):
                data["mounts"][mp] = {
                    "type": "github",
                    "owner": res._owner,
                    "repo": res._repo,
                }
            elif isinstance(res, KBResource):
                data["mounts"][mp] = {"type": "kb"}
        return data

    def restore(self, data: dict) -> None:
        self._mounts = {}
        for mp, cfg in data.get("mounts", {}).items():
            t = cfg.get("type", "")
            if t == "ram":
                r = RAMResource()
                r.restore(cfg.get("state", {}))
                self._mounts[mp] = r
            elif t == "disk":
                self._mounts[mp] = DiskResource(cfg.get("root", "."))
            elif t == "web":
                self._mounts[mp] = HTTPResource(cfg.get("base_url", ""))
            elif t == "github":
                self._mounts[mp] = GitHubResource(
                    owner=cfg.get("owner", ""), repo=cfg.get("repo", "")
                )
            elif t == "kb":
                self._mounts[mp] = KBResource()

    # ── Command implementations ──

    async def _cmd_ls(self, args: list[str]) -> str:
        long_fmt = "-l" in args
        targets = [a for a in args if not a.startswith("-")]
        if not targets:
            targets = ["/"]
        lines = []
        for target in targets:
            try:
                res, rel = self._resolve(target)
                entries = await (res.list_dir(rel) if rel else res.list_dir(""))
            except Exception as e:
                lines.append(f"ls: {target}: {e}")
                continue
            if not entries:
                continue
            if long_fmt:
                for e in entries:
                    type_char = "d" if e.is_dir else "-"
                    size_str = f"{e.size:>8}"
                    mod_str = time.strftime(
                        "%Y-%m-%d %H:%M",
                        time.localtime(e.modified) if e.modified else time.localtime(),
                    )
                    lines.append(
                        f"{type_char} {size_str} {mod_str} {e.name}"
                    )
            else:
                lines.extend(e.name for e in entries)
        return "\n".join(lines)

    async def _cmd_cat(self, args: list[str]) -> str:
        if not args:
            return "cat: missing file operand"
        results = []
        for target in args:
            try:
                res, rel = self._resolve(target)
                content = await res.read_file(rel)
                results.append(content)
            except FileNotFoundError as e:
                results.append(f"cat: {e}")
            except NotImplementedError:
                results.append(f"cat: {res.name} does not support read")
            except Exception as e:
                results.append(f"cat: {target}: {e}")
        return "\n".join(results)

    async def _cmd_grep(self, args: list[str], stdin: str = "") -> str:
        ignore_case = False
        show_numbers = False
        count_only = False
        positional = []

        i = 0
        while i < len(args):
            a = args[i]
            if a == "-i":
                ignore_case = True
            elif a == "-n":
                show_numbers = True
            elif a == "-c":
                count_only = True
            elif a.startswith("-") and len(a) > 1:
                for c in a[1:]:
                    if c == "i":
                        ignore_case = True
                    elif c == "n":
                        show_numbers = True
                    elif c == "c":
                        count_only = True
            else:
                positional.append(a)
            i += 1

        if not positional:
            if stdin:
                pattern = ""
            else:
                return "grep: missing pattern"
        else:
            pattern = positional[0]
            positional = positional[1:]

        if not pattern and stdin:
            return stdin

        # KB path → semantic search, not literal grep
        search_path = positional[0] if positional else ""
        if search_path.startswith("/kb") and pattern and not stdin:
            kb = self._resources.get("kb")
            if kb and hasattr(kb, 'search'):
                results = await kb.search(pattern)
                if results:
                    return "\n".join(
                        f"{r.path} | {r.metadata.get('title', '')} | "
                        f"{r.metadata.get('content', '')[:200]}"
                        for r in results[:15]
                    )
                return f"No KB results for: {pattern}"
            return "KB resource not available"

        try:
            from ..infrastructure.fast_fs import get_fast_fs
            ffs = get_fast_fs()
            if ffs.rg_available and not stdin:
                search_dir = positional[0] if positional else "."
                from pathlib import Path as _P
                search_dir = str(self._to_real(search_dir))
                matches = ffs.grep(
                    search_dir, pattern, file_glob="*",
                    max_results=200, ignore_case=ignore_case,
                )
                if matches:
                    lines = []
                    for m in matches:
                        if count_only:
                            lines.append(f"{m.file_path}:1")
                        elif show_numbers:
                            lines.append(f"{m.file_path}:{m.line_number}:{m.line_text}")
                        else:
                            lines.append(f"{m.file_path}:{m.line_text}")
                    return "\n".join(lines)
        except Exception:
            pass

        lines_out = []

        if positional:
            expanded: list[str] = []
            for p in positional:
                res, rel = self._resolve(p)
                if "*" in p or "?" in p:
                    expanded.extend(self._expand_glob(p, res, rel))
                else:
                    expanded.append(p)

            if not expanded:
                expanded = positional

            for fpath in expanded:
                try:
                    res, rel = self._resolve(fpath)
                    content = await res.read_file(rel)
                except (FileNotFoundError, NotImplementedError):
                    continue
                except Exception:
                    continue

                file_lines = content.split("\n")
                matches = []
                for ln_num, line in enumerate(file_lines, 1):
                    if self._grep_match(line, pattern, ignore_case):
                        matches.append((ln_num, line))

                prefix = f"{fpath}:" if len(expanded) > 1 else ""

                if count_only:
                    lines_out.append(f"{prefix}{len(matches)}")
                else:
                    for ln_num, line in matches:
                        if show_numbers:
                            lines_out.append(f"{prefix}{ln_num}:{line}")
                        else:
                            lines_out.append(f"{prefix}{line}")
        elif stdin:
            for ln_num, line in enumerate(stdin.split("\n"), 1):
                if self._grep_match(line, pattern, ignore_case):
                    if count_only:
                        continue
                    if show_numbers:
                        lines_out.append(f"{ln_num}:{line}")
                    else:
                        lines_out.append(line)
            if count_only and pattern:
                count = sum(
                    1 for line in stdin.split("\n")
                    if self._grep_match(line, pattern, ignore_case)
                )
                lines_out.append(str(count))

        return "\n".join(lines_out)

    @staticmethod
    def _grep_match(line: str, pattern: str, ignore_case: bool) -> bool:
        if ignore_case:
            return pattern.lower() in line.lower()
        return pattern in line

    async def _cmd_cp(self, args: list[str]) -> str:
        if len(args) < 2:
            return "cp: missing file operand"
        src = args[0]
        dst = args[1]
        try:
            src_res, src_rel = self._resolve(src)
            content = await src_res.read_file(src_rel)
        except FileNotFoundError as e:
            return f"cp: {e}"
        except NotImplementedError:
            return f"cp: source {src_res.name} is read-only"
        except Exception as e:
            return f"cp: {src}: {e}"

        try:
            dst_res, dst_rel = self._resolve(dst)
            await dst_res.write_file(dst_rel, content)
            return ""
        except NotImplementedError:
            return f"cp: destination {dst_res.name} is read-only"
        except Exception as e:
            return f"cp: {dst}: {e}"

    async def _cmd_find(self, args: list[str]) -> str:
        name_pattern = "*"
        target = "/"

        i = 0
        while i < len(args):
            a = args[i]
            if a == "-name" and i + 1 < len(args):
                name_pattern = args[i + 1].strip("'\"")
                i += 2
                continue
            elif not a.startswith("-"):
                target = a
            i += 1

        if "*" not in name_pattern:
            name_pattern = f"*{name_pattern}*"

        try:
            res, rel = self._resolve(target)
        except ValueError as e:
            return f"find: {e}"

        results = self._expand_glob(target, res, rel, pattern=name_pattern)
        return "\n".join(sorted(results))

    def _expand_glob(
        self, vpath: str, res: Resource, rel: str,
        pattern: str = "*",
    ) -> list[str]:
        """Expand a glob pattern within a resource. Returns matching virtual paths."""
        results: list[str] = []

        if isinstance(res, RAMResource):
            for p in res._store:
                if fnmatch.fnmatch(p, f"/{rel}/{pattern}") or \
                   fnmatch.fnmatch(p, f"/{rel}"):
                    results.append(p)
                dir_part = os.path.dirname(p) if "/" in p else "/"
                check = f"{dir_part}/{pattern}"
                if fnmatch.fnmatch(p, check):
                    results.append(p)

        elif isinstance(res, DiskResource):
            mp = ""
            for mp_key in self._mounts:
                if self._mounts[mp_key] is res:
                    mp = mp_key
                    break
            dir_vpath = mp + "/" + rel if rel else mp
            for entry in res.walk_files(dir_vpath, pattern):
                results.append(entry.path)

        elif isinstance(res, KBResource):
            norm = vpath.replace("\\", "/").strip("/")
            if norm.startswith("kb/documents"):
                try:
                    res._ensure_kb()
                    if res._kb is not False:
                        for doc in res._kb.storage.list_documents():
                            if fnmatch.fnmatch(doc.id, pattern) or \
                               fnmatch.fnmatch(doc.title, pattern):
                                results.append(f"/kb/documents/{doc.id}")
                except Exception:
                    pass
            elif norm.startswith("kb/memories"):
                try:
                    res._ensure_mem()
                    if res._mem is not False:
                        for eid, entry in res._mem._entries.items():
                            if fnmatch.fnmatch(eid, pattern) or \
                               fnmatch.fnmatch(entry.content[:60], pattern):
                                results.append(f"/kb/memories/{eid}")
                except Exception:
                    pass
            elif norm.startswith("kb/synthesis"):
                try:
                    res._ensure_mem()
                    if res._mem is not False:
                        for s in res._mem._synthesis:
                            if fnmatch.fnmatch(s.id, pattern) or \
                               fnmatch.fnmatch(s.content[:60], pattern):
                                results.append(f"/kb/synthesis/{s.id}")
                except Exception:
                    pass

        return results

    async def _cmd_wc(self, args: list[str], stdin: str = "") -> str:
        lines_only = "-l" in args
        words_only = "-w" in args
        chars_only = "-c" in args
        targets = [a for a in args if not a.startswith("-")]
        output = []

        if targets:
            for target in targets:
                try:
                    res, rel = self._resolve(target)
                    content = await res.read_file(rel)
                except Exception as e:
                    output.append(f"wc: {target}: {e}")
                    continue
                lc = content.count("\n")
                wc = len(content.split())
                cc = len(content)
                if lines_only:
                    output.append(f"{lc:>6} {target}")
                elif words_only:
                    output.append(f"{wc:>6} {target}")
                elif chars_only:
                    output.append(f"{cc:>6} {target}")
                else:
                    output.append(f"{lc:>6} {wc:>6} {cc:>6} {target}")
        elif stdin:
            lc = stdin.count("\n")
            wc_val = len(stdin.split())
            cc = len(stdin)
            if lines_only:
                output.append(str(lc))
            elif words_only:
                output.append(str(wc_val))
            elif chars_only:
                output.append(str(cc))
            else:
                output.append(f"{lc:>6} {wc_val:>6} {cc:>6}")

        return "\n".join(output)

    @staticmethod
    def _cmd_head(args: list[str], stdin: str) -> str:
        n = 10
        positional = []
        for a in args:
            if a.startswith("-n") and len(a) > 2:
                try:
                    n = int(a[2:])
                except ValueError:
                    pass
            elif a == "-n":
                pass
            elif not a.startswith("-"):
                positional.append(a)
        lines = stdin.split("\n")
        return "\n".join(lines[:n])

    @staticmethod
    def _cmd_tail(args: list[str], stdin: str) -> str:
        n = 10
        for a in args:
            if a.startswith("-n") and len(a) > 2:
                try:
                    n = int(a[2:])
                except ValueError:
                    pass
        lines = stdin.split("\n")
        return "\n".join(lines[-n:])


# ══════════════════════════════════════════════════════════════════════
# Singleton
# ══════════════════════════════════════════════════════════════════════

_vfs: VirtualFS | None = None
_vfs_lock = __import__('threading').Lock()


def get_virtual_fs() -> VirtualFS:
    """Get or create the global VirtualFS singleton."""
    global _vfs
    if _vfs is None:
        with _vfs_lock:
            if _vfs is None:
                _vfs = VirtualFS()
                try:
                    from .public_apis_resource import get_public_apis
                    _vfs.mount("/public-apis", get_public_apis())
                except Exception:
                    pass
                logger.info("VirtualFS singleton created")
    return _vfs


def reset_virtual_fs() -> None:
    """Reset the global VirtualFS singleton."""
    global _vfs
    _vfs = None


__all__ = [
    "VFSEntry",
    "Resource",
    "RAMResource",
    "DiskResource",
    "HTTPResource",
    "GitHubResource",
    "KBResource",
    "VirtualFS",
    "get_virtual_fs",
    "reset_virtual_fs",
]
