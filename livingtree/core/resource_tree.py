"""Resource Tree — unified virtual filesystem for LivingTree capabilities.

Inspired by strukto-ai/mirage (1.6k stars):
  "One filesystem, every backend. AI agents reach every backend with
  the same handful of Unix-like tools."

All LivingTree modules mounted as a single directory tree:
  /knowledge/   → KnowledgeBase + LazyIndex    (search, read docs)
  /weather/     → OpenMeteoClient              (forecast, history, AQ)
  /models/      → FreeModelPool                (available models, stats)
  /graph/       → HypergraphStore              (entities, edges, paths)
  /session/     → LifeContext                  (plan, results, metadata)
  /config/      → LTAIConfig                   (runtime settings)
  /events/      → EventBus                     (recent events)

Operations (Unix-like):
  read(path)     → cat — get resource content
  list(path)     → ls — list directory contents  
  search(path, q)→ grep — search within mount
  pipe(commands) → bash pipeline — chain operations
  snapshot()     → tar — save workspace state
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from loguru import logger


# ═══ Data Types ═══


@dataclass
class MountPoint:
    """A single mounted resource in the virtual filesystem.

    Mirage analog: new S3Resource({ bucket: 'logs' }) mounted at /s3
    """
    path: str                      # Mount path, e.g. "/knowledge"
    name: str                      # Human-readable name
    read_fn: Callable | None = None      # async fn(path) → str
    list_fn: Callable | None = None      # async fn(path) → list[str]
    search_fn: Callable | None = None    # async fn(path, query, top_k) → list
    write_fn: Callable | None = None     # async fn(path, content) → bool
    metadata: dict = field(default_factory=dict)


@dataclass
class PipeStep:
    """A single step in a pipeline command chain.

    Mirage analog: cat file | grep pattern | wc -l
    """
    command: str                   # "read", "search", "list", "write"
    target: str                    # Path argument
    args: dict = field(default_factory=dict)


@dataclass
class ResourceResult:
    """Result of a resource operation."""
    path: str
    operation: str                 # "read", "list", "search", "write", "pipe"
    content: str = ""              # Text content (for read)
    items: list[str] = field(default_factory=list)  # List items (for list/search)
    error: str = ""
    latency_ms: float = 0.0
    metadata: dict = field(default_factory=dict)

    def as_context(self) -> str:
        """Format for LLM context injection."""
        if self.content:
            return self.content[:2000]
        if self.items:
            return "\n".join(self.items[:50])
        return self.error or "(empty)"


# ═══ Resource Tree ═══


class ResourceTree:
    """Unified virtual filesystem for all LivingTree capabilities.

    Every module is a mount point. The agent accesses everything
    through unified path-based operations instead of learning
    N different module APIs.

    Usage:
        tree = ResourceTree()
        tree.mount("/knowledge", kb_reader, kb_lister, kb_searcher)
        
        # Read like a filesystem
        doc = await tree.read("/knowledge/环评/GB3095-2012")
        
        # Search like grep
        results = await tree.search("/knowledge", "SO2 排放标准")
        
        # List like ls
        entries = await tree.list("/knowledge/环评")
        
        # Pipeline like bash
        result = await tree.pipe("read /knowledge/standard | search SO2 | list")
    """

    def __init__(self):
        self._mounts: dict[str, MountPoint] = {}
        self._history: list[ResourceResult] = []
        self._snapshots: dict[str, dict] = {}

    # ── Mount Management ──

    def mount(
        self, path: str, name: str = "",
        read_fn: Callable | None = None,
        list_fn: Callable | None = None,
        search_fn: Callable | None = None,
        write_fn: Callable | None = None,
        **metadata,
    ) -> MountPoint:
        """Mount a resource at a path. Idempotent — overwrites if exists."""
        mp = MountPoint(
            path=path, name=name or path.strip("/"),
            read_fn=read_fn, list_fn=list_fn,
            search_fn=search_fn, write_fn=write_fn,
            metadata=metadata,
        )
        self._mounts[path] = mp
        logger.debug(f"ResourceTree mounted: {path} ({mp.name})")
        return mp

    def unmount(self, path: str) -> None:
        self._mounts.pop(path, None)

    def mounts(self) -> list[str]:
        return sorted(self._mounts.keys())

    def _resolve(self, path: str) -> tuple[MountPoint, str]:
        """Resolve a path to its mount point and relative path.

        e.g. "/knowledge/环评/GB3095" → (knowledge_mount, "环评/GB3095")
        """
        # Find the longest matching mount prefix
        best = None
        best_prefix = ""
        for mp_path in self._mounts:
            if path.startswith(mp_path) and len(mp_path) > len(best_prefix):
                best = self._mounts[mp_path]
                best_prefix = mp_path

        if not best:
            raise ValueError(f"No mount found for path: {path}")

        relative = path[len(best_prefix):].lstrip("/")
        return best, relative

    # ── File Operations (cat, ls, grep) ──

    async def read(self, path: str) -> ResourceResult:
        """Read a resource — like 'cat'.

        Returns:
            ResourceResult with .content populated
        """
        t0 = time.time()
        try:
            mp, rel = self._resolve(path)
            if not mp.read_fn:
                return ResourceResult(path=path, operation="read",
                                      error=f"Mount '{mp.path}' does not support read",
                                      latency_ms=(time.time() - t0) * 1000)

            content = mp.read_fn(rel)
            if hasattr(content, '__await__'):
                content = await content

            result = ResourceResult(
                path=path, operation="read",
                content=str(content)[:10000],
                latency_ms=(time.time() - t0) * 1000,
                metadata=mp.metadata,
            )
        except Exception as e:
            result = ResourceResult(path=path, operation="read",
                                    error=str(e),
                                    latency_ms=(time.time() - t0) * 1000)

        self._history.append(result)
        return result

    async def list(self, path: str = "/") -> ResourceResult:
        """List directory contents — like 'ls'.

        If path is "/", list all mount points.
        If path is a mount, list its contents.
        """
        t0 = time.time()
        try:
            if path == "/" or path == "":
                items = [f"{p}/" for p in self.mounts()]
                result = ResourceResult(path=path, operation="list", items=items,
                                        latency_ms=(time.time() - t0) * 1000)
            else:
                mp, rel = self._resolve(path)
                if not mp.list_fn:
                    return ResourceResult(path=path, operation="list",
                                          error=f"Mount '{mp.path}' does not support list",
                                          latency_ms=(time.time() - t0) * 1000)

                items = mp.list_fn(rel)
                if hasattr(items, '__await__'):
                    items = await items

                result = ResourceResult(path=path, operation="list",
                                        items=list(items)[:100],
                                        latency_ms=(time.time() - t0) * 1000)
        except Exception as e:
            result = ResourceResult(path=path, operation="list",
                                    error=str(e),
                                    latency_ms=(time.time() - t0) * 1000)

        self._history.append(result)
        return result

    async def search(
        self, path: str, query: str, top_k: int = 10,
    ) -> ResourceResult:
        """Search within a resource — like 'grep'.

        Args:
            path: Mount path to search within
            query: Search query string
            top_k: Max results
        """
        t0 = time.time()
        try:
            mp, rel = self._resolve(path)
            if not mp.search_fn:
                return ResourceResult(path=path, operation="search",
                                      error=f"Mount '{mp.path}' does not support search",
                                      latency_ms=(time.time() - t0) * 1000)

            results = mp.search_fn(rel, query, top_k)
            if hasattr(results, '__await__'):
                results = await results

            items = [str(r)[:200] for r in results[:top_k]]
            result = ResourceResult(path=path, operation="search",
                                    items=items,
                                    latency_ms=(time.time() - t0) * 1000,
                                    metadata={"query": query, "top_k": top_k})
        except Exception as e:
            result = ResourceResult(path=path, operation="search",
                                    error=str(e),
                                    latency_ms=(time.time() - t0) * 1000)

        self._history.append(result)
        return result

    async def write(self, path: str, content: str) -> ResourceResult:
        """Write to a resource — like 'echo > file'."""
        t0 = time.time()
        try:
            mp, rel = self._resolve(path)
            if not mp.write_fn:
                return ResourceResult(path=path, operation="write",
                                      error=f"Mount '{mp.path}' does not support write",
                                      latency_ms=(time.time() - t0) * 1000)

            ok = mp.write_fn(rel, content)
            if hasattr(ok, '__await__'):
                ok = await ok

            result = ResourceResult(
                path=path, operation="write",
                content=f"Wrote {len(content)} chars to {path}" if ok else f"Write failed",
                latency_ms=(time.time() - t0) * 1000)
        except Exception as e:
            result = ResourceResult(path=path, operation="write",
                                    error=str(e),
                                    latency_ms=(time.time() - t0) * 1000)

        self._history.append(result)
        return result

    # ── Pipeline Execution ──

    async def pipe(self, pipeline: str) -> ResourceResult:
        """Execute a simple pipeline — like bash pipe.

        Syntax: "command path | command path [args]"
        Each step feeds its output to the next.

        Examples:
          "read /knowledge/standard | search SO2"
          "list /knowledge | search GB3095"
        """
        t0 = time.time()
        steps_raw = [s.strip() for s in pipeline.split("|")]

        steps: list[PipeStep] = []
        for s in steps_raw:
            parts = s.split(maxsplit=1)
            cmd = parts[0] if parts else ""
            target = parts[1] if len(parts) > 1 else ""
            # Extract args from remaining parts
            args = {}
            if len(parts) > 2:
                for p in parts[2:]:
                    if "=" in p:
                        k, v = p.split("=", 1)
                        args[k] = v
            steps.append(PipeStep(command=cmd, target=target, args=args))

        if not steps:
            return ResourceResult(path="", operation="pipe",
                                  error="Empty pipeline", latency_ms=0)

        # Execute pipeline
        current_data: str = ""
        current_items: list[str] = []

        for step in steps:
            if step.command == "read":
                r = await self.read(step.target)
                current_data = r.content
                current_items = []
            elif step.command == "list":
                r = await self.list(step.target or "/")
                current_items = r.items
                current_data = "\n".join(current_items)
            elif step.command == "search":
                query = step.args.get("q", step.target)
                top_k = int(step.args.get("top_k", 10))
                # Search within current data if no path given
                if step.target and step.target != query:
                    r = await self.search(step.target, query, top_k)
                elif current_data:
                    # Inline grep: search within previous output
                    lines = current_data.split("\n")
                    matched = [l for l in lines if query.lower() in l.lower()]
                    r = ResourceResult(path="pipe", operation="search",
                                       items=matched[:top_k])
                else:
                    r = ResourceResult(path="pipe", operation="search",
                                       error="No data to search")
                current_items = r.items
                current_data = "\n".join(current_items)
            elif step.command == "write":
                r = await self.write(step.target, current_data)
                current_data = r.content
                current_items = []
            else:
                r = ResourceResult(path="pipe", operation=step.command,
                                   error=f"Unknown command: {step.command}")
                break

        result = ResourceResult(
            path="pipe", operation="pipe",
            content=current_data,
            items=current_items,
            latency_ms=(time.time() - t0) * 1000,
            metadata={"pipeline": pipeline, "steps": len(steps)},
        )
        self._history.append(result)
        return result

    # ── Snapshot & Restore ──

    def snapshot(self, label: str = "") -> dict:
        """Snapshot current workspace state.

        Mirage analog: workspace.snapshot("demo.tar")
        """
        data = {
            "label": label or time.strftime("%Y%m%d_%H%M%S"),
            "timestamp": time.time(),
            "mounts": {p: {"name": m.name, "metadata": m.metadata}
                       for p, m in self._mounts.items()},
            "history_length": len(self._history),
        }
        self._snapshots[data["label"]] = data
        return data

    def restore(self, label: str) -> bool:
        """List available snapshots (actual restore depends on module state)."""
        return label in self._snapshots

    def list_snapshots(self) -> list[str]:
        return list(self._snapshots.keys())

    # ── Stats ──

    def stats(self) -> dict[str, Any]:
        return {
            "mounts": self.mounts(),
            "total_operations": len(self._history),
            "snapshots": len(self._snapshots),
            "operations_by_type": self._op_stats(),
        }

    def _op_stats(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for r in self._history:
            counts[r.operation] += 1
        return dict(counts)


# ═══ Preset: LivingTree Default Mounts ═══


def create_living_tree_fs(
    kb=None, om_weather=None, pool=None, hg=None,
    consciousness=None, event_bus=None,
) -> ResourceTree:
    """Create a ResourceTree pre-mounted with all LivingTree modules.

    Mirrors Mirage's: new Workspace({ '/s3': ..., '/slack': ... })
    """
    tree = ResourceTree()

    # ── /knowledge ──
    if kb:
        def kb_read(rel_path: str) -> str:
            docs = kb.search(rel_path.replace("/", " "), top_k=3)
            if docs:
                return "\n\n---\n\n".join(
                    f"# {d.title}\n{d.content[:2000]}" for d in docs)
            return "(no results)"

        def kb_list(rel_path: str) -> list[str]:
            docs = kb.search(rel_path.replace("/", " ") if rel_path else "", top_k=20)
            return [f"{d.title} ({len(d.content)} chars)" for d in docs]

        def kb_search(rel_path: str, query: str, top_k: int = 10) -> list[str]:
            docs = kb.search(query, top_k=top_k)
            return [f"[{d.title}] {d.content[:150]}" for d in docs]

        tree.mount("/knowledge", "KnowledgeBase",
                   read_fn=kb_read, list_fn=kb_list, search_fn=kb_search)

    # ── /weather ──
    if om_weather:
        async def weather_read(rel_path: str) -> str:
            # Parse city from path: /weather/北京 or /weather/39.9,116.4
            import re
            coords = re.findall(r'[\d.]+', rel_path)
            if len(coords) >= 2:
                ctx = await om_weather.get_environmental_context(
                    float(coords[0]), float(coords[1]))
            elif rel_path:
                ctx = await om_weather.get_environmental_context(
                    0, 0, city=rel_path)
            else:
                ctx = "Usage: /weather/{city} or /weather/{lat},{lon}"
            return ctx

        async def weather_list(rel_path: str) -> list[str]:
            try:
                report = await om_weather.get_for_city(
                    rel_path or "北京", days=3)
                items = [f"Current: {report.current.to_context()}" if report.current else ""]
                for d in report.daily[:3]:
                    items.append(f"{d.date}: {d.temp_min}~{d.temp_max}°C, {d.description}")
                return [i for i in items if i]
            except Exception:
                return ["Weather data unavailable — try /weather/北京"]

        tree.mount("/weather", "OpenMeteo",
                   read_fn=weather_read, list_fn=weather_list)

    # ── /models ──
    if pool:
        def models_read(rel_path: str) -> str:
            stats = pool.pool_stats()
            lines = [f"Total: {stats['total_models']}, Healthy: {stats['healthy']}, "
                     f"Available: {stats['available']}"]
            lines.append(f"Success rate: {stats.get('avg_success_rate', 'N/A')}")
            for role, model in stats.get("role_assignments", {}).items():
                lines.append(f"  {role}: {model}")
            return "\n".join(lines)

        def models_list(rel_path: str) -> list[str]:
            available = pool.available_models()
            items = []
            for name in available[:20]:
                m = pool._get_model(name)
                items.append(
                    f"{name}: coding={m.coding:.1f} reasoning={m.reasoning:.1f} "
                    f"status={m.status.value} ctx={m.context_window}")
            return items

        tree.mount("/models", "FreeModelPool",
                   read_fn=models_read, list_fn=models_list)

    # ── /graph ──
    if hg:
        def graph_read(rel_path: str) -> str:
            stats = hg.stats()
            lines = [f"Entities: {stats['entity_count']}, "
                     f"HyperEdges: {stats['hyperedge_count']}, "
                     f"Avg entities/edge: {stats['avg_entity_per_edge']:.1f}"]
            return "\n".join(lines)

        def graph_list(rel_path: str) -> list[str]:
            entities = list(hg._entities.values())[:30]
            return [f"{e.id}: {e.label} ({e.entity_type})" for e in entities]

        def graph_search(rel_path: str, query: str, top_k: int = 10) -> list[str]:
            from .graph_introspector import get_introspector
            insp = get_introspector()
            results = insp.search_by_meaning(query, hg, top_k=top_k)
            return [f"{eid}: score={score:.2f}" for eid, score in results]

        tree.mount("/graph", "HypergraphStore",
                   read_fn=graph_read, list_fn=graph_list,
                   search_fn=graph_search)

    # ── /session ──
    if consciousness:
        def session_read(rel_path: str) -> str:
            if hasattr(consciousness, 'prove_instantiation'):
                proof = consciousness.prove_instantiation()
                return json.dumps(proof, ensure_ascii=False, indent=2)
            return str(consciousness)

        def session_list(rel_path: str) -> list[str]:
            if hasattr(consciousness, 'my_recent_experiences'):
                return consciousness.my_recent_experiences(limit=10)
            return [str(consciousness)[:100]]

        tree.mount("/session", "Consciousness",
                   read_fn=session_read, list_fn=session_list)

    # ── /events ──
    if event_bus:
        def events_read(rel_path: str) -> str:
            history = event_bus.get_history(limit=20)
            lines = []
            for evt in history:
                lines.append(
                    f"[{evt.event_type}] {str(evt.data)[:100]}")
            return "\n".join(lines) if lines else "(no recent events)"

        def events_list(rel_path: str) -> list[str]:
            stats = event_bus.stats()
            return [f"Event types: {stats['event_types']}, "
                    f"Subscribers: {stats['total_subscribers']}"]

        tree.mount("/events", "EventBus",
                   read_fn=events_read, list_fn=events_list)

    logger.info(
        f"LivingTree FS created: {len(tree.mounts())} mounts — "
        f"{', '.join(tree.mounts())}",
    )
    return tree


# ═══ Singleton ═══

_resource_tree: ResourceTree | None = None


def get_resource_tree() -> ResourceTree:
    global _resource_tree
    if _resource_tree is None:
        _resource_tree = ResourceTree()
    return _resource_tree


__all__ = [
    "ResourceTree", "MountPoint", "ResourceResult", "PipeStep",
    "create_living_tree_fs", "get_resource_tree",
]
