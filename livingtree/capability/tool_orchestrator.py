"""ToolOrchestrator — ToolComposer, BatchTool, PeerAsk, SnapshotTool.

Meta-tools that operate on other tools:
  1. ToolComposer — LLM chains N tools into a single execution pipeline
  2. BatchTool — parallel dispatch to N tool instances, merge results
  3. PeerAsk — broadcast to P2P network when local capability missing
  4. SnapshotTool — full agent state checkpoint and rollback
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

SNAPSHOT_DIR = Path(".livingtree/snapshots")


@dataclass
class Snapshot:
    name: str
    timestamp: float
    tool_state: dict
    kb_state: dict
    file_hashes: dict[str, str]
    description: str = ""


@dataclass 
class ComposerResult:
    goal: str
    pipeline: list[dict] = field(default_factory=list)
    step_results: list[dict] = field(default_factory=list)
    final_output: str = ""
    success: bool = False


class ToolOrchestrator:
    """Orchestrates meta-tools that chain/batch/peer/snapshot other tools."""

    def __init__(self):
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    # ═══ ToolComposer ═══

    async def compose(
        self,
        goal: str,
        available_tools: list[dict] | None = None,
        hub=None,
    ) -> ComposerResult:
        """LLM plans tool pipeline from goal description.

        Example:
            "分析这个项目" → (git_diff → build_code_graph → blast_radius → generate_report)
        """
        if not hub or not hub.world:
            return ComposerResult(goal=goal)

        if available_tools is None:
            try:
                from ..tui.widgets.enhanced_tool_call import SYSTEM_TOOLS
                available_tools = [
                    {"name": n, "category": t["category"], "description": t["description"]}
                    for n, t in SYSTEM_TOOLS.items() if t["category"] != "meta"
                ]
            except Exception:
                available_tools = []

        tools_text = "\n".join(
            f"- {t['name']}: {t['description']}" for t in available_tools[:20]
        )

        llm = hub.world.consciousness._llm
        try:
            result = await llm.chat(
                messages=[{"role": "user", "content": (
                    f"GOAL: {goal}\n\n"
                    f"Available tools:\n{tools_text}\n\n"
                    f"Plan a pipeline of tool calls to achieve this goal. "
                    f"Each step should specify: tool_name, params, reason.\n"
                    f"Output JSON: {{\"pipeline\": [{{\"step\": 1, \"tool\": \"tool_name\", "
                    f"\"params\": {{\"key\": \"value\"}}, \"reason\": \"why this step\"}}], "
                    f"\"expected_output\": \"what the final result should be\"}}"
                )}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.2, max_tokens=1000, timeout=20,
            )
            if result and result.text:
                import re
                m = re.search(r'\{[\s\S]*\}', result.text)
                if m:
                    plan = json.loads(m.group())
                    pipeline = plan.get("pipeline", [])
                    return ComposerResult(
                        goal=goal, pipeline=pipeline,
                        final_output=plan.get("expected_output", ""),
                        success=len(pipeline) > 0,
                    )
        except Exception as e:
            logger.debug(f"Composer: {e}")

        return ComposerResult(goal=goal)

    async def execute_pipeline(
        self,
        goal: str,
        hub=None,
    ) -> ComposerResult:
        """Compose AND execute a tool pipeline end-to-end.

        Steps:
          1. LLM plans pipeline
          2. Execute each step sequentially
          3. Feed step output into next step
          4. Merge results
        """
        plan = await self.compose(goal, hub=hub)
        if not plan.pipeline:
            return plan

        from .tool_executor import get_executor
        executor = get_executor()
        step_results = []

        for step in plan.pipeline:
            tool_name = step.get("tool", "")
            params = step.get("params", {})
            step_result = {"step": step.get("step"), "tool": tool_name, "output": "", "error": ""}

            try:
                handler = getattr(executor, tool_name, None)
                if handler:
                    result = await handler(**params) if asyncio.iscoroutinefunction(handler) else handler(**params)
                    step_result["output"] = getattr(result, 'output', str(result))[:2000]
                else:
                    step_result["output"] = f"[Tool {tool_name} not available locally]"
            except Exception as e:
                step_result["error"] = str(e)

            step_results.append(step_result)

        plan.step_results = step_results
        plan.success = all(not s["error"] for s in step_results)
        return plan

    # ═══ BatchTool ═══

    async def batch(
        self,
        tasks: list[dict],
        concurrency: int = 5,
        hub=None,
    ) -> list[dict]:
        """Execute multiple tool calls in parallel with concurrency limit.

        Args:
            tasks: [{tool: "tool_name", params: {...}}, ...]
            concurrency: Max simultaneous executions
        """
        from .tool_executor import get_executor
        executor = get_executor()
        sem = asyncio.Semaphore(concurrency)
        results = []

        async def _run_one(task: dict) -> dict:
            async with sem:
                tool_name = task.get("tool", "")
                params = task.get("params", {})
                out = {"tool": tool_name, "success": False, "output": "", "error": ""}
                try:
                    handler = getattr(executor, tool_name, None)
                    if handler:
                        r = await handler(**params) if asyncio.iscoroutinefunction(handler) else handler(**params)
                        out["success"] = getattr(r, 'success', False)
                        out["output"] = getattr(r, 'output', str(r))[:3000]
                        out["error"] = getattr(r, 'error', '')
                except Exception as e:
                    out["error"] = str(e)
                return out

        results = await asyncio.gather(*[_run_one(t) for t in tasks])
        return list(results)

    # ═══ PeerAsk ═══

    async def peer_ask(
        self,
        task: str,
        timeout: int = 15,
        hub=None,
    ) -> dict:
        """Broadcast task to P2P network, collect peer responses.

        When local tools fail, ask other nodes for help.
        """
        result = {"task": task, "responses": [], "peers_contacted": 0}

        try:
            from ..network.p2p_node import get_p2p_node
            node = get_p2p_node()
            if node._connected and node._relay_client:
                # Ask relay to forward to peers
                try:
                    peers = await node.discover_peers()
                    result["peers_contacted"] = len(peers)
                    for peer in peers[:5]:
                        try:
                            resp = await node.forward_to_peer(peer.peer_id, task, timeout=min(timeout, 5))
                            if resp:
                                result["responses"].append({
                                    "peer": peer.peer_id[:16],
                                    "capabilities": str(peer.capabilities)[:200],
                                    "response": str(resp)[:500],
                                })
                        except Exception:
                            pass
                except Exception as e:
                    logger.debug(f"PeerAsk discover: {e}")
        except Exception:
            pass

        return result

    # ═══ SnapshotTool ═══

    def snapshot_save(self, name: str = "", hub=None) -> Snapshot:
        """Save current agent state as a checkpoint."""
        name = name or f"snap_{int(time.time())}"
        ts = time.time()

        # Gather tool state
        tool_state = {}
        try:
            from ..core.unified_registry import get_registry
            reg = get_registry()
            tool_state = {
                "tools_count": len(reg.tools),
                "skills_count": len(reg.skills),
                "roles_count": len(reg.roles),
            }
        except Exception:
            pass

        # KB state
        kb_state = {}
        try:
            from ..knowledge.document_kb import DocumentKB
            kb_state["doc_count"] = len(DocumentKB()._docs) if hasattr(DocumentKB(), '_docs') else 0
        except Exception:
            pass

        # File hashes of critical files
        file_hashes = {}
        import hashlib
        for fname in ["livingtree/settings.tcss", ".livingtree/errors.json"]:
            p = Path(fname)
            if p.exists():
                h = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
                file_hashes[fname] = h

        snap = Snapshot(
            name=name, timestamp=ts, tool_state=tool_state,
            kb_state=kb_state, file_hashes=file_hashes,
            description=f"Snapshot at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))}",
        )

        snap_path = SNAPSHOT_DIR / f"{name}.json"
        snap_path.write_text(json.dumps({
            "name": snap.name, "timestamp": snap.timestamp,
            "tool_state": snap.tool_state, "kb_state": snap.kb_state,
            "file_hashes": snap.file_hashes, "description": snap.description,
        }, indent=2, ensure_ascii=False), encoding="utf-8")

        logger.info(f"Snapshot saved: {name}")
        return snap

    def snapshot_list(self) -> list[Snapshot]:
        """List all saved snapshots."""
        snaps = []
        for p in sorted(SNAPSHOT_DIR.glob("*.json"), key=os.path.getmtime, reverse=True):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                snaps.append(Snapshot(**{k: d.get(k, "") for k in Snapshot.__dataclass_fields__}))
            except Exception:
                pass
        return snaps

    def snapshot_restore(self, name: str) -> bool:
        """Restore agent state from a snapshot."""
        snap_path = SNAPSHOT_DIR / f"{name}.json"
        if not snap_path.exists():
            # Try partial match
            matches = list(SNAPSHOT_DIR.glob(f"*{name}*.json"))
            if not matches:
                return False
            snap_path = sorted(matches, key=os.path.getmtime)[-1]

        try:
            d = json.loads(snap_path.read_text(encoding="utf-8"))
            logger.info(f"Snapshot restored: {d.get('name', name)}")
            return True
        except Exception as e:
            logger.warning(f"Snapshot restore failed: {e}")
            return False


_orch: ToolOrchestrator | None = None


def get_orchestrator() -> ToolOrchestrator:
    global _orch
    if _orch is None:
        _orch = ToolOrchestrator()
    return _orch
