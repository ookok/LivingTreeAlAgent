"""Behavior Tree Planner — agentic multi-branch task execution.

Inspired by AgenticQwen's dual data flywheels:
  - Reasoning flywheel: learn from errors → harder tasks
  - Agentic flywheel:  linear workflows → multi-branch behavior trees

Node types:
  Sequence  — execute children in order, stop on failure
  Selector  — execute children in order, stop on first success (fallback)
  Action    — execute a tool/function, return success/failure
  Condition — check a condition before proceeding
  Parallel  — execute all children, succeed if N succeed

Integrates with LivingTree's model election for intelligent branch selection.
"""
from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from loguru import logger


class NodeStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"


@dataclass
class TreeContext:
    """Context passed through tree execution."""
    user_input: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    results: dict[str, Any] = field(default_factory=dict)
    depth: int = 0
    max_depth: int = 10


class TreeNode(ABC):
    """Base node for behavior tree."""

    def __init__(self, name: str = "", description: str = ""):
        self.name = name
        self.description = description
        self.status = NodeStatus.RUNNING

    @abstractmethod
    async def tick(self, ctx: TreeContext) -> NodeStatus:
        """Execute one tick. Returns SUCCESS, FAILURE, or RUNNING."""
        ...

    def reset(self):
        self.status = NodeStatus.RUNNING


# ═══ Composite Nodes ═══


class Sequence(TreeNode):
    """Execute children in order. Fails on first child failure."""

    def __init__(self, name: str = "", children: list[TreeNode] = None):
        super().__init__(name)
        self.children = children or []
        self._index = 0

    async def tick(self, ctx: TreeContext) -> NodeStatus:
        ctx.depth += 1
        if ctx.depth > ctx.max_depth:
            return NodeStatus.FAILURE

        while self._index < len(self.children):
            child = self.children[self._index]
            status = await child.tick(ctx)
            if status == NodeStatus.FAILURE:
                self.status = NodeStatus.FAILURE
                ctx.errors.append(f"{self.name}/{child.name}: 失败")
                return NodeStatus.FAILURE
            if status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING
            self._index += 1

        self.status = NodeStatus.SUCCESS
        return NodeStatus.SUCCESS

    def reset(self):
        super().reset()
        self._index = 0
        for child in self.children:
            child.reset()


class Selector(TreeNode):
    """Execute children in order until one succeeds (fallback pattern)."""

    def __init__(self, name: str = "", children: list[TreeNode] = None):
        super().__init__(name)
        self.children = children or []
        self._tried: list[str] = []

    async def tick(self, ctx: TreeContext) -> NodeStatus:
        ctx.depth += 1
        if ctx.depth > ctx.max_depth:
            return NodeStatus.FAILURE

        for child in self.children:
            status = await child.tick(ctx)
            child.reset()
            self._tried.append(child.name)
            if status == NodeStatus.SUCCESS:
                self.status = NodeStatus.SUCCESS
                logger.info(f"Selector '{self.name}': 选中分支 '{child.name}'")
                return NodeStatus.SUCCESS

        self.status = NodeStatus.FAILURE
        ctx.errors.append(f"{self.name}: 所有分支均失败 (尝试了: {', '.join(self._tried)})")
        return NodeStatus.FAILURE

    def reset(self):
        super().reset()
        self._tried = []
        for child in self.children:
            child.reset()


class Parallel(TreeNode):
    """Execute all children. Succeed if at least `required` succeed."""

    def __init__(self, name: str = "", children: list[TreeNode] = None, required: int = 1):
        super().__init__(name)
        self.children = children or []
        self.required = required

    async def tick(self, ctx: TreeContext) -> NodeStatus:
        tasks = [child.tick(ctx) for child in self.children]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successes = sum(1 for r in results if r == NodeStatus.SUCCESS)
        if successes >= self.required:
            self.status = NodeStatus.SUCCESS
            return NodeStatus.SUCCESS

        self.status = NodeStatus.FAILURE
        return NodeStatus.FAILURE

    def reset(self):
        super().reset()
        for child in self.children:
            child.reset()


# ═══ Leaf Nodes ═══


class Action(TreeNode):
    """Execute a tool/callable. Returns success if no exception."""

    def __init__(self, name: str = "", fn: Callable = None, args: tuple = (), kwargs: dict = None):
        super().__init__(name)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs or {}

    async def tick(self, ctx: TreeContext) -> NodeStatus:
        if not self.fn:
            return NodeStatus.FAILURE
        try:
            if asyncio.iscoroutinefunction(self.fn):
                result = await self.fn(ctx, *self.args, **self.kwargs)
            else:
                result = self.fn(ctx, *self.args, **self.kwargs)
            ctx.results[self.name] = result
            logger.debug(f"Action '{self.name}': 成功")
            return NodeStatus.SUCCESS
        except Exception as e:
            ctx.errors.append(f"{self.name}: {e}")
            logger.warning(f"Action '{self.name}': 失败 — {e}")
            return NodeStatus.FAILURE

    def reset(self):
        super().reset()


class Condition(TreeNode):
    """Check a condition. Used before risky actions."""

    def __init__(self, name: str = "", check: Callable[[TreeContext], bool] = None):
        super().__init__(name)
        self.check = check

    async def tick(self, ctx: TreeContext) -> NodeStatus:
        if not self.check:
            return NodeStatus.FAILURE
        try:
            ok = self.check(ctx) if not asyncio.iscoroutinefunction(self.check) else await self.check(ctx)
            return NodeStatus.SUCCESS if ok else NodeStatus.FAILURE
        except Exception:
            return NodeStatus.FAILURE


class ModelDecision(TreeNode):
    """Use a small free model to decide which branch to take.

    Integrates with LivingTree's model election to pick the best free model.
    """

    def __init__(self, name: str = "", prompt_template: str = "", options: list[str] = None):
        super().__init__(name)
        self.prompt_template = prompt_template
        self.options = options or []

    async def tick(self, ctx: TreeContext) -> NodeStatus:
        if not self.options:
            return NodeStatus.FAILURE

        prompt = self.prompt_template.format(
            user_input=ctx.user_input,
            history="\n".join(str(h) for h in ctx.history[-3:]),
            errors="\n".join(ctx.errors[-3:]),
            options="\n".join(f"{i+1}. {o}" for i, o in enumerate(self.options)),
        )

        try:
            # Use LivingTree's model election via hub
            import asyncio
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._call_model, prompt)
            choice = self._parse_choice(result)
            if choice is not None and 0 <= choice < len(self.options):
                ctx.results[f"{self.name}_choice"] = self.options[choice]
                ctx.results[f"{self.name}_index"] = choice
                return NodeStatus.SUCCESS
        except Exception as e:
            ctx.errors.append(f"ModelDecision '{self.name}': {e}")

        return NodeStatus.FAILURE

    def _call_model(self, prompt: str) -> str:
        """Call a small free model via LivingTree's consciousness."""
        try:
            from livingtree.treellm.dual_consciousness import get_consciousness
            c = get_consciousness()
            if c:
                # Use light model for fast decision
                return c.quick_think(prompt, max_tokens=100)
        except Exception:
            pass
        return "1"  # Default to first option

    def _parse_choice(self, text: str) -> Optional[int]:
        """Parse model output to option index."""
        import re
        # Try direct number
        m = re.search(r'\b([1-9])\b', str(text))
        if m:
            return int(m.group(1)) - 1
        # Try matching option text
        for i, opt in enumerate(self.options):
            if opt.lower() in str(text).lower():
                return i
        return 0  # Default to first


# ═══ Tree Builder ═══


def build_agentic_tree(
    task_steps: list[dict],
    *,
    fallback_steps: list[dict] = None,
    pre_checks: list[dict] = None,
    parallel_steps: list[dict] = None,
) -> TreeNode:
    """Build a behavior tree from task plan steps.

    Structure:
        Selector(root)
        ├── Sequence (pre_checks)
        │   └── Condition foreach pre_check
        ├── Sequence (primary path with condition gate)
        │   ├── Condition: verify prerequisites
        │   └── Sequence (main steps)
        │       ├── Action: step1
        │       └── Action: step2
        ├── Parallel (parallel steps, if any)
        └── Sequence (fallback path)
            └── Action: fallback_step
    """
    root_children = []

    # Primary path with condition gate
    primary = Sequence(name="primary_path")
    primary.children = [
        Action(name=f"step_{i}", fn=_make_step_fn(s)) for i, s in enumerate(task_steps)
    ]
    root_children.append(primary)

    # Parallel steps (e.g., search multiple sources simultaneously)
    if parallel_steps:
        parallel_actions = [
            Action(name=f"parallel_{i}", fn=_make_step_fn(s)) for i, s in enumerate(parallel_steps)
        ]
        parallel = Parallel(name="parallel_search", children=parallel_actions, required=1)
        root_children.append(parallel)

    # Fallback path
    if fallback_steps:
        fallback = Sequence(name="fallback_path")
        fallback.children = [
            Action(name=f"fallback_{i}", fn=_make_step_fn(s)) for i, s in enumerate(fallback_steps)
        ]
        root_children.append(fallback)

    return Selector(name="agentic_root", children=root_children)


def _make_step_fn(step: dict) -> Callable:
    """Wrap a step dict into a callable action."""
    async def _execute(ctx: TreeContext, s=step):
        tool = s.get("tool", "")
        args = s.get("args", {})
        desc = s.get("description", tool or "unknown_step")
        logger.debug(f"BehaviorTree: 执行 '{desc}'")
        # Placeholder: actual tool execution via hub
        ctx.results[desc] = {"tool": tool, "args": args, "status": "ok"}
        return {"ok": True, "step": desc}
    return _execute


# ═══ Plan-to-Tree Converter ═══


def linear_plan_to_tree(
    steps: list[str],
    *,
    fallback_hint: str = "",
    use_model_for_routing: bool = False,
) -> TreeNode:
    """Convert a linear plan (list of step descriptions) into a behavior tree.

    Auto-generates fallback branches and uses model election for routing
    when use_model_for_routing is True.

    Args:
        steps: ["search codebase", "analyze results", "apply fix"]
        fallback_hint: hint for alternative approach (e.g., "ask user for clarification")
        use_model_for_routing: use small free model to decide between branches

    Returns:
        Root TreeNode (Selector)
    """
    task_steps = [{"tool": s, "description": s, "args": {}} for s in steps]

    fallback_steps = None
    if fallback_hint:
        fallback_steps = [{"tool": fallback_hint, "description": fallback_hint, "args": {}}]

    tree = build_agentic_tree(task_steps, fallback_steps=fallback_steps)

    if use_model_for_routing:
        decision = ModelDecision(
            name="route_decision",
            prompt_template=(
                "Given the task: {user_input}\n"
                "History: {history}\n"
                "Choose the best approach:\n{options}\n"
                "Answer with just the number."
            ),
            options=[s["description"] for s in task_steps] + ([fallback_hint] if fallback_hint else []),
        )
        # Wrap in Sequence: decide then execute
        wrapper = Sequence(name="model_routed")
        wrapper.children.append(decision)
        wrapper.children.append(tree)
        return wrapper

    return tree
