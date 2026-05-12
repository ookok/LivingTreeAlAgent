"""
Task Tree — Hierarchical Task Decomposition with Live SSE Streaming
==================================================================

Backend for the Living Canvas task decomposition visualization. Builds a dynamic
task breakdown tree via LLM-guided recursive decomposition, streaming structural
updates as SSE events for real-time frontend rendering.

Key references:
    - ROMA (arXiv:2602.01848): "ROMA: Robust Multi-Agent Task Decomposition with
      Adaptive Recomposition" — inspires the pattern-based pre-decomposition and
      the dependency-aware ordering strategy used in TaskDecomposer.
    - Tree-of-Thoughts (Yao et al., arXiv:2305.10601): "Tree of Thoughts:
      Deliberate Problem Solving with Large Language Models" — the foundational
      concept of branching exploration trees over intermediate reasoning steps,
      directly informing the TaskNode hierarchy and depth-limited decomposition.
    - SSE (Server-Sent Events, WHATWG HTML Living Standard §9.2): the
      unidirectional streaming protocol used for live task-tree sync to the
      frontend canvas.

Architecture:
    TaskStatus(Enum) → TaskNode(@dataclass) → TaskTree(manager) → TaskDecomposer(LLM)
    Each layer emits structured SSE events consumed by the Living Canvas HTMX frontend.

Usage:
    from livingtree.execution.task_tree import create_task_tree, get_task_decomposer

    tree = create_task_tree("Build a user authentication system")
    decomposer = get_task_decomposer()
    async for event in decomposer.decompose("Build a user authentication system"):
        print(event)  # SSE-formatted string
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, ClassVar

from loguru import logger

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MAX_DEPTH = 4
DEFAULT_MAX_CHILDREN = 6
SSE_EOL = "\n\n"

PATTERN_LIBRARY: dict[str, list[dict[str, Any]]] = {
    "authentication": [
        {"label": "User Model & Storage", "priority": "P0", "reasoning": "Core identity persistence"},
        {"label": "Credential Validation", "priority": "P0", "reasoning": "Password hashing and comparison"},
        {"label": "Token / Session Management", "priority": "P1", "reasoning": "JWT or session cookie issuance"},
        {"label": "OAuth / Social Login", "priority": "P2", "reasoning": "Third-party identity provider integration"},
        {"label": "Rate Limiting & Lockout", "priority": "P1", "reasoning": "Brute-force protection"},
    ],
    "crud": [
        {"label": "Data Model & Schema", "priority": "P0", "reasoning": "DB schema or ORM definitions"},
        {"label": "Create Endpoint", "priority": "P0", "reasoning": "POST handler with validation"},
        {"label": "Read / List Endpoint", "priority": "P0", "reasoning": "GET with filtering and pagination"},
        {"label": "Update Endpoint", "priority": "P1", "reasoning": "PUT/PATCH handler"},
        {"label": "Delete Endpoint", "priority": "P1", "reasoning": "Soft or hard delete logic"},
    ],
    "pipeline": [
        {"label": "Data Ingestion", "priority": "P0", "reasoning": "Input source connectors"},
        {"label": "Validation & Cleaning", "priority": "P0", "reasoning": "Schema enforcement and sanitization"},
        {"label": "Transformation", "priority": "P1", "reasoning": "Business logic and mapping"},
        {"label": "Storage / Persistence", "priority": "P1", "reasoning": "Output sink"},
        {"label": "Monitoring & Alerts", "priority": "P2", "reasoning": "Observability hooks"},
    ],
}


# ---------------------------------------------------------------------------
# TaskStatus
# ---------------------------------------------------------------------------

class TaskStatus(str, Enum):
    """Execution lifecycle states for a single TaskNode.

    Transitions:
        PENDING → THINKING → RUNNING → DONE
                            ↘ FAILED
                  → SKIPPED (dependency failed)
    """

    PENDING = "pending"
    THINKING = "thinking"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# TaskNode
# ---------------------------------------------------------------------------

@dataclass
class TaskNode:
    """Single node in the hierarchical task decomposition tree.

    Each node represents a discrete sub-task. The tree is built top-down via
    LLM-guided recursive decomposition (Tree-of-Thoughts style) and rendered
    live on the Living Canvas via SSE.

    Attributes:
        id: UUID v4 string unique across the tree.
        label: Short human-readable name (e.g. "User Model & Storage").
        description: Detailed natural-language description of the sub-task.
        status: Current lifecycle state (TaskStatus enum).
        parent_id: UUID of the parent TaskNode, or None for the root.
        children: Ordered list of child TaskNodes.
        depth: Distance from the root (root=0).
        priority: P0 (critical) through P3 (nice-to-have).
        estimated_tokens: LLM-predicted token cost for this sub-task.
        actual_tokens: Measured token consumption after execution.
        reasoning: Why the decomposer chose this sub-task.
        dependencies: Ordered list of sibling node IDs that must finish first.
        result: Execution output text (set on DONE).
        created_at: POSIX timestamp of node creation.
        started_at: POSIX timestamp when status moved to RUNNING.
        completed_at: POSIX timestamp of DONE/FAILED/SKIPPED.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    label: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    parent_id: str | None = None
    children: list[TaskNode] = field(default_factory=list)
    depth: int = 0
    priority: str = "P2"
    estimated_tokens: int = 0
    actual_tokens: int = 0
    reasoning: str = ""
    dependencies: list[str] = field(default_factory=list)
    result: str | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Flat JSON-serializable representation (no recursive children)."""
        status_val = self.status.value if isinstance(self.status, TaskStatus) else str(self.status)
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "status": status_val,
            "parent_id": self.parent_id,
            "depth": self.depth,
            "priority": self.priority,
            "estimated_tokens": self.estimated_tokens,
            "actual_tokens": self.actual_tokens,
            "reasoning": self.reasoning,
            "dependencies": self.dependencies,
            "result": self.result,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    def to_tree_dict(self) -> dict[str, Any]:
        """Recursive JSON-serializable representation including children."""
        data = self.to_dict()
        data["children"] = [child.to_tree_dict() for child in self.children]
        return data

    # ------------------------------------------------------------------
    # Progress
    # ------------------------------------------------------------------

    def progress(self) -> float:
        """Compute completion ratio [0, 1] based on children statuses.

        Weights: DONE=1.0, RUNNING=0.5, THINKING=0.2, PENDING/FAILED/SKIPPED=0.0.
        If there are no children the node's own status determines the value.
        """
        if not self.children:
            if self.status == TaskStatus.DONE:
                return 1.0
            if self.status == TaskStatus.RUNNING:
                return 0.5
            if self.status == TaskStatus.THINKING:
                return 0.2
            return 0.0

        weight_map = {
            TaskStatus.DONE: 1.0,
            TaskStatus.RUNNING: 0.5,
            TaskStatus.THINKING: 0.2,
        }
        total = sum(
            weight_map.get(child.status, 0.0) for child in self.children
        )
        return total / len(self.children)


# ---------------------------------------------------------------------------
# TaskTree
# ---------------------------------------------------------------------------

class TaskTree:
    """In-memory task hierarchy manager with fast ID-based node lookup.

    Usage::

        tree = TaskTree()
        root = tree.create_root("Design a microservice architecture")
        child = tree.add_child(root.id, "API Gateway", "Route and throttle requests")
        tree.update_status(child.id, TaskStatus.RUNNING, reasoning="Entry point first")
        for event in tree.to_sse_events():
            ...
    """

    def __init__(self) -> None:
        self._root: TaskNode | None = None
        self._node_index: dict[str, TaskNode] = {}
        self._event_log: list[dict[str, Any]] = []  # ordered change log

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def create_root(self, description: str) -> TaskNode:
        """Instantiate the root TaskNode in THINKING status."""
        if self._root is not None:
            logger.warning("TaskTree already has a root; overwriting")
        root = TaskNode(
            label=description[:60],
            description=description,
            status=TaskStatus.THINKING,
            depth=0,
            priority="P0",
        )
        self._root = root
        self._node_index[root.id] = root
        self._log_event("node_update", root)
        logger.info(f"TaskTree root created | id={root.id} description={description[:60]}")
        return root

    def add_child(
        self,
        parent_id: str,
        label: str,
        description: str = "",
        priority: str = "P2",
        estimated_tokens: int = 0,
        reasoning: str = "",
        dependencies: list[str] | None = None,
    ) -> TaskNode:
        """Create a child TaskNode under *parent_id* and return it."""
        parent = self._node_index.get(parent_id)
        if parent is None:
            raise KeyError(f"Parent node {parent_id} not found in index")

        child = TaskNode(
            label=label,
            description=description,
            parent_id=parent_id,
            depth=parent.depth + 1,
            priority=priority,
            estimated_tokens=estimated_tokens,
            reasoning=reasoning,
            dependencies=dependencies or [],
        )
        parent.children.append(child)
        self._node_index[child.id] = child
        self._log_event("node_update", child)
        logger.debug(f"Child added | id={child.id} parent={parent_id} label={label}")
        return child

    def update_status(
        self, node_id: str, status: TaskStatus | str, reasoning: str = ""
    ) -> TaskNode:
        """Transition a node to a new status, recording timestamps."""
        if isinstance(status, str):
            try:
                status = TaskStatus(status)
            except ValueError:
                status = TaskStatus.PENDING
        node = self._node_index[node_id]
        old_status = node.status
        node.status = status
        if reasoning:
            node.reasoning = reasoning

        now = time.time()
        if status == TaskStatus.RUNNING and old_status != TaskStatus.RUNNING:
            node.started_at = now
        elif status in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.SKIPPED):
            node.completed_at = now

            # Cascade: skip children whose dependencies include a failed node
            if status == TaskStatus.FAILED:
                for child in list(self._node_index.values()):
                    if child.parent_id == node_id or node_id in child.dependencies:
                        if child.status == TaskStatus.PENDING:
                            self.update_status(
                                child.id, TaskStatus.SKIPPED,
                                reasoning=f"Parent/dependency {node_id} failed",
                            )

        self._log_event("node_update", node)
        logger.debug(f"Status transition | id={node_id} {old_status.value}→{status.value}")
        return node

    def set_result(self, node_id: str, result_text: str) -> TaskNode:
        """Store execution result and auto-transition to DONE if still RUNNING."""
        node = self._node_index[node_id]
        node.result = result_text
        if node.status in (TaskStatus.RUNNING, TaskStatus.PENDING, TaskStatus.THINKING):
            self.update_status(node_id, TaskStatus.DONE)
        else:
            self._log_event("node_update", node)
        return node

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_tree(self) -> TaskNode | None:
        """Return the root TaskNode (with recursive children)."""
        return self._root

    def get_node(self, node_id: str) -> TaskNode:
        """O(1) lookup by node id."""
        return self._node_index[node_id]

    def stats(self) -> dict[str, Any]:
        """Aggregate statistics: totals, by-status breakdown, max depth."""
        nodes = list(self._node_index.values())
        if not nodes:
            return {"total": 0, "by_status": {}, "max_depth": 0}

        by_status: dict[str, int] = {}
        for node in nodes:
            key = node.status.value
            by_status[key] = by_status.get(key, 0) + 1

        return {
            "total": len(nodes),
            "by_status": by_status,
            "max_depth": max(node.depth for node in nodes),
            "progress": self._root.progress() if self._root else 0.0,
        }

    # ------------------------------------------------------------------
    # SSE serialization
    # ------------------------------------------------------------------

    def to_sse_events(self) -> str:
        """Return the full SSE event stream string (init + all updates + done)."""
        parts: list[str] = []
        if self._root is None:
            logger.warning("to_sse_events called on empty tree")
            return ""

        # Init event
        parts.append(self._format_sse("task_init", {
            "tree": self._root.to_tree_dict(),
            "stats": self.stats(),
        }))

        # Replay node update events
        for entry in self._event_log:
            if entry["event"] == "node_update":
                parts.append(self._format_sse("node_update", entry["data"]))

        # Done event
        parts.append(self._format_sse("task_done", {
            "summary": self.stats(),
            "root_id": self._root.id,
        }))
        return "".join(parts)

    def yield_sse_events(self) -> str:
        """Yield the current tree state as SSE events (for replay in generators)."""
        if self._root is None:
            return ""
        yield self._format_sse("task_init", {
            "tree": self._root.to_tree_dict(),
            "stats": self.stats(),
        })
        for entry in self._event_log:
            if entry["event"] == "node_update":
                yield self._format_sse("node_update", entry["data"])
        yield self._format_sse("task_done", {
            "summary": self.stats(),
            "root_id": self._root.id,
        })

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _log_event(self, event_type: str, node: TaskNode) -> None:
        """Record a structured event for SSE replay."""
        self._event_log.append({
            "event": event_type,
            "data": node.to_dict(),
            "ts": time.time(),
        })

    @staticmethod
    def _format_sse(event: str, data: dict[str, Any]) -> str:
        """Format a single SSE message block."""
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}{SSE_EOL}"


# ---------------------------------------------------------------------------
# Pre-decomposition pattern matching
# ---------------------------------------------------------------------------

def _match_pattern(description: str) -> list[dict[str, Any]] | None:
    """Return a pre-canned decomposition pattern if the description matches
    any known task archetype (authentication, CRUD, pipeline, etc.)."""
    lower = description.lower()
    for keyword, pattern in PATTERN_LIBRARY.items():
        if keyword in lower:
            logger.info(f"Pattern match | keyword={keyword} description={description[:50]}")
            return pattern
    return None


# ---------------------------------------------------------------------------
# TaskDecomposer
# ---------------------------------------------------------------------------

class TaskDecomposer:
    """LLM-guided recursive task decomposition with live SSE emission.

    Uses a consciousness/hub reference for LLM calls to iteratively break down
    a root description into a hierarchical TaskTree. Emits SSE events as each
    node is created or updated, enabling real-time Living Canvas rendering.

    Typical usage::

        decomposer = get_task_decomposer()
        async for event in decomposer.decompose("Build a real-time chat backend"):
            yield event  # forward to SSE endpoint

    Parameters:
        consciousness: An object exposing an async ``generate(prompt) → str``
                       method (typically a StreamThinker or Hub reference).
        max_depth: Hard limit on recursion depth (default 4).
        max_children: Maximum children per parent node (default 6).
    """

    def __init__(
        self,
        consciousness: Any = None,
        max_depth: int = DEFAULT_MAX_DEPTH,
        max_children: int = DEFAULT_MAX_CHILDREN,
    ) -> None:
        self._consciousness = consciousness
        self._hub: Any = None
        self.max_depth = max_depth
        self.max_children = max_children

    def set_consciousness(self, consciousness: Any) -> None:
        """Wire in a consciousness for LLM calls."""
        self._consciousness = consciousness

    def set_hub(self, hub: Any) -> None:
        """Wire in the integration hub reference."""
        self._hub = hub

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def decompose(
        self,
        task_description: str,
        max_depth: int | None = None,
        max_children: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """Async generator that builds the TaskTree and yields SSE events live.

        Args:
            task_description: Natural-language description of the root task.
            max_depth: Override the instance-level depth limit.
            max_children: Override the instance-level children limit.
        """
        depth_limit = max_depth if max_depth is not None else self.max_depth
        child_limit = max_children if max_children is not None else self.max_children

        logger.info(
            f"TaskDecomposer.decompose start | desc={task_description[:60]} "
            f"max_depth={depth_limit} max_children={child_limit}"
        )

        tree = TaskTree()
        root = tree.create_root(task_description)

        # Emit init
        yield self._make_sse("task_init", {
            "tree": root.to_tree_dict(),
            "stats": tree.stats(),
        })

        # Attempt pattern-based pre-decomposition
        pattern = _match_pattern(task_description)
        if pattern:
            root_label = root.label
            for entry in pattern:
                child = tree.add_child(
                    parent_id=root.id,
                    label=entry["label"],
                    description=task_description,
                    priority=entry.get("priority", "P2"),
                    reasoning=entry.get("reasoning", ""),
                )
                yield self._node_sse(child)
        else:
            # LLM-guided decomposition at depth 0 → depth 1
            await self._decompose_level(tree, root, depth_limit, child_limit)

        # Recursive breadth-first decomposition for remaining levels
        queue: list[TaskNode] = list(root.children) if root.children else []
        while queue:
            node = queue.pop(0)
            if node.depth < depth_limit - 1:
                tree.update_status(node.id, TaskStatus.THINKING)
                yield self._node_sse(node)
                await self._decompose_level(tree, node, depth_limit, child_limit)
            queue.extend(node.children)

        # Final done event
        yield self._make_sse("task_done", {
            "summary": tree.stats(),
            "root_id": root.id,
        })

    async def decompose_stream(self, task_description: str) -> AsyncGenerator[str, None]:
        """Convenience wrapper that delegates to decompose()."""
        async for event in self.decompose(task_description):
            yield event

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _decompose_level(
        self,
        tree: TaskTree,
        parent: TaskNode,
        depth_limit: int,
        child_limit: int,
    ) -> None:
        """Ask the LLM to break *parent* into sub-tasks, then add them to the tree."""
        if parent.depth >= depth_limit:
            return

        prompt = self._build_decomposition_prompt(parent, child_limit)
        response = await self._llm_generate(prompt)
        subtasks = self._parse_subtasks(response)

        for sub in subtasks[:child_limit]:
            child = tree.add_child(
                parent_id=parent.id,
                label=sub.get("label", "Sub-task"),
                description=sub.get("description", parent.description),
                priority=sub.get("priority", "P2"),
                estimated_tokens=sub.get("estimated_tokens", 0),
                reasoning=sub.get("reasoning", ""),
                dependencies=sub.get("dependencies", []),
            )
            logger.debug(f"LLM-generated child | id={child.id} label={child.label}")

    def _build_decomposition_prompt(self, node: TaskNode, max_children: int) -> str:
        """Construct the LLM prompt for task decomposition."""
        return (
            f"Break down the following task into {max_children} or fewer sub-tasks. "
            f"Consider sequential dependencies when ordering. "
            f"Return a JSON array of objects, each with keys: "
            f"label (short name), description (one sentence), priority (P0/P1/P2/P3), "
            f"reasoning (why this sub-task), dependencies (list of 0-based sibling indices that must complete first), "
            f"estimated_tokens (integer). "
            f"\n\nTask (depth {node.depth}): {node.description}\n\nJSON:"
        )

    async def _llm_generate(self, prompt: str) -> str:
        """Invoke the consciousness/hub LLM, or return a synthetic fallback."""
        if self._consciousness is None:
            logger.warning("No consciousness reference; using fallback decomposition")
            return "[]"  # No subtasks — leaf node

        try:
            if hasattr(self._consciousness, "generate"):
                result = self._consciousness.generate(prompt)
                if asyncio.iscoroutine(result):
                    return await result
                return str(result)
            if hasattr(self._consciousness, "think"):
                result = self._consciousness.think(prompt)
                if asyncio.iscoroutine(result):
                    return await result
                return str(result)
            if callable(self._consciousness):
                result = self._consciousness(prompt)
                if asyncio.iscoroutine(result):
                    return await result
                return str(result)
        except Exception as exc:
            logger.error(f"LLM generation failed: {exc}")
        return "[]"

    @staticmethod
    def _parse_subtasks(raw: str) -> list[dict[str, Any]]:
        """Extract a JSON array from LLM output, handling markdown fences."""
        text = raw.strip()
        # Strip ```json fences
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        # Find first '[' ... last ']'
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1:
            logger.warning(f"Cannot find JSON array in LLM response: {text[:120]}")
            return []

        try:
            parsed = json.loads(text[start:end + 1])
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError as exc:
            logger.error(f"JSON parse error: {exc}  raw={text[:200]}")

        return []

    # ------------------------------------------------------------------
    # SSE formatting
    # ------------------------------------------------------------------

    @staticmethod
    def _make_sse(event: str, data: dict[str, Any]) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}{SSE_EOL}"

    @staticmethod
    def _node_sse(node: TaskNode) -> str:
        return (
            f"event: node_update\n"
            f"data: {json.dumps(node.to_dict(), ensure_ascii=False)}{SSE_EOL}"
        )


# ---------------------------------------------------------------------------
# Singleton factories
# ---------------------------------------------------------------------------

_DECOMPOSER_INSTANCE: TaskDecomposer | None = None


def get_task_decomposer(
    consciousness: Any = None,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_children: int = DEFAULT_MAX_CHILDREN,
) -> TaskDecomposer:
    """Return the singleton TaskDecomposer instance.

    Creates it on first call; subsequent calls ignore arguments.
    Pass the consciousness reference on the first call to wire up LLM access.
    """
    global _DECOMPOSER_INSTANCE
    if _DECOMPOSER_INSTANCE is None:
        _DECOMPOSER_INSTANCE = TaskDecomposer(
            consciousness=consciousness,
            max_depth=max_depth,
            max_children=max_children,
        )
        logger.info(
            f"TaskDecomposer singleton created | max_depth={max_depth} "
            f"max_children={max_children}"
        )
    return _DECOMPOSER_INSTANCE


def create_task_tree(description: str) -> TaskTree:
    """Factory: create and seed a TaskTree with a root node.

    Returns the TaskTree instance (not the root node) so callers can
    further populate it or pass it to TaskDecomposer.
    """
    tree = TaskTree()
    tree.create_root(description)
    logger.info(f"TaskTree factory created | description={description[:60]}")
    return tree
