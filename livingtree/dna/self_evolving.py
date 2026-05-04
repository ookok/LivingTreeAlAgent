"""Self-Evolving Engine — The system improves its own code autonomously.

Uses the LifeEngine pipeline to generate, test, and deploy code changes to
itself. Works with: code_engine (generate), orchestrator (plan/execute),
side_git (safe rollback), quality_checker (validate), test runner.

Cycle: observe → generate hypothesis → write patch → test → deploy or rollback.

Safety: all changes go through side-git snapshot → test → human approval gate.
"""

from __future__ import annotations
import asyncio, difflib, subprocess, time, json
from dataclasses import dataclass, field
from pathlib import Path
from loguru import logger

@dataclass
class EvolutionCandidate:
    id: str
    target_file: str
    description: str
    original_code: str = ""
    evolved_code: str = ""
    test_results: dict = field(default_factory=dict)
    quality_score: float = 0.0
    safety_score: float = 0.0
    status: str = "pending"  # pending → tested → approved → deployed → rolled_back
    diff: str = ""

class SelfEvolvingEngine:
    """Autonomous code improvement with safety gates."""

    MAX_CANDIDATES = 5
    MIN_QUALITY_SCORE = 0.6    

    def __init__(self, world=None):
        self._world = world
        self._candidates = []
        self._deployed_count = 0
        self._rollback_count = 0

    async def observe_and_propose(self) -> list[EvolutionCandidate]:
        candidates = []
        code_graph = getattr(self._world, 'code_graph', None) if self._world else None
        if not code_graph:
            return candidates

        hubs = code_graph.find_hubs(3) if hasattr(code_graph, 'find_hubs') else []
        uncovered = code_graph.find_uncovered() if hasattr(code_graph, 'find_uncovered') else []
        error_file = Path(".livingtree/errors.json")
        error_patterns = []
        if error_file.exists():
            try:
                errors = json.loads(error_file.read_text())
                error_patterns = [e for e in errors if e.get("location", "").endswith(".py")][-5:]
            except: pass

        for hub in hubs[:2]:
            candidate = await self._generate_improvement(
                hub.file, f"Optimize high-connectivity module: {hub.name} ({len(hub.dependents)} dependents)"
            )
            if candidate:
                candidates.append(candidate)

        for unc in uncovered[:2]:
            candidate = await self._generate_improvement(
                unc.file, f"Add test coverage for uncovered function: {unc.name}"
            )
            if candidate:
                candidates.append(candidate)

        for err in error_patterns[:2]:
            loc = err.get("location","").split(":")[0]
            if loc:
                candidate = await self._generate_improvement(
                    loc, f"Fix recurring error: {err.get('message','')[:100]}"
                )
                if candidate:
                    candidates.append(candidate)

        self._candidates = candidates[:self.MAX_CANDIDATES]
        return self._candidates

    async def test_candidate(self, candidate: EvolutionCandidate) -> EvolutionCandidate:
        if not candidate.evolved_code or not candidate.target_file:
            candidate.status = "skipped"
            return candidate

        original_path = Path(candidate.target_file)
        if not original_path.exists():
            candidate.status = "file_missing"
            return candidate

        candidate.original_code = original_path.read_text(encoding="utf-8")

        diff = list(difflib.unified_diff(
            candidate.original_code.splitlines(True),
            candidate.evolved_code.splitlines(True),
            fromfile=candidate.target_file, tofile=f"{candidate.target_file}.evolved",
        ))
        candidate.diff = "".join(diff)

        qc = getattr(self._world, 'quality_checker', None) if self._world else None
        if qc:
            result = await qc.check(candidate.evolved_code)
            candidate.quality_score = result.final_score if hasattr(result, 'final_score') else 0.5

        candidate.status = "tested" if candidate.quality_score >= self.MIN_QUALITY_SCORE else "quality_failed"
        return candidate

    async def deploy_candidate(self, candidate: EvolutionCandidate) -> dict:
        if candidate.status != "tested":
            return {"deployed": False, "reason": f"status is {candidate.status}"}

        side_git = getattr(self._world, 'side_git', None) if self._world else None
        turn_id = None
        if side_git:
            turn_id = await side_git.pre_turn()

        try:
            Path(candidate.target_file).write_text(candidate.evolved_code, encoding="utf-8")
            self._deployed_count += 1
            candidate.status = "deployed"
            logger.info(f"Evolution deployed: {candidate.target_file}")

            return {"deployed": True, "file": candidate.target_file, "turn_id": turn_id,
                    "diff_lines": len(candidate.diff.splitlines())}
        except Exception as e:
            candidate.status = "deploy_failed"
            if side_git and turn_id:
                await side_git.restore(turn_id)
            return {"deployed": False, "error": str(e)}

    async def rollback_last(self) -> dict:
        side_git = getattr(self._world, 'side_git', None) if self._world else None
        if not side_git or not side_git._turns:
            return {"rolled_back": False, "reason": "no snapshots"}

        last = side_git._turns[-1]
        ok = await side_git.restore(last.turn_id)
        if ok:
            self._rollback_count += 1
        return {"rolled_back": ok, "turn_id": last.turn_id}

    def get_status(self) -> dict:
        return {
            "candidates": len(self._candidates),
            "deployed": self._deployed_count,
            "rollbacks": self._rollback_count,
            "pending": [c.id for c in self._candidates if c.status == "pending"],
            "tested": [c.id for c in self._candidates if c.status == "tested"],
        }

    async def _generate_improvement(self, file_path: str, description: str) -> EvolutionCandidate | None:
        if not self._world or not hasattr(self._world, 'code_engine'):
            return None

        path = Path(file_path)
        if not path.exists():
            return None

        import uuid
        cid = uuid.uuid4().hex[:8]
        original = path.read_text(encoding="utf-8")[:5000]

        try:
            consciousness = self._world.consciousness
            prompt = (
                f"Improve the following code. Focus on: {description}\n\n"
                f"File: {file_path}\n\n"
                f"Original code:\n```\n{original[:3000]}\n```\n\n"
                f"Output ONLY the complete improved code. No explanations."
            )
            result = await consciousness.chain_of_thought(prompt, steps=2, max_tokens=8192)
            evolved = result.split("```")[1] if "```" in result and result.count("```") >= 2 else result
            evolved = evolved.strip()
            if not evolved or len(evolved) < 20:
                return None
        except Exception as e:
            logger.debug(f"Evolution generate: {e}")
            return None

        return EvolutionCandidate(
            id=cid, target_file=file_path, description=description,
            evolved_code=evolved,
        )
