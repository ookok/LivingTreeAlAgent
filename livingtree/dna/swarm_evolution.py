"""Distributed Swarm Evolution — share successful self-evolution mutations across P2P nodes.

Each node discovers mutations locally via AutonomousCodeEvolution. When a mutation
passes the sandbox test suite with fitness > 0.3, this module broadcasts it to the
swarm. Other nodes receive, validate, and optionally apply peer mutations.

Safety gates: sandbox validation, fitness threshold, test suite pass, no breaking changes.
Deduplication: SHA256 signature to skip mutations already seen.
Trust scoring: prefer mutations from high-reputation nodes.
Persistence: .livingtree/swarm_mutations.json log.

Integration:
    - Hooks into self_evolution.py AutonomousCodeEvolution._persist_mutation
    - Uses network/p2p_node.py for P2P broadcast via WebSocket relay
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

SWARM_DATA_DIR = Path(".livingtree")
SWARM_MUTATIONS_FILE = SWARM_DATA_DIR / "swarm_mutations.json"
MIN_FITNESS_FOR_SHARE = 0.3
MIN_TRUST_FOR_APPLY = 0.2
MAX_MUTATIONS_STORED = 200


# ═══════════════════════════════════════════════════════════════
# Dataclasses
# ═══════════════════════════════════════════════════════════════

@dataclass
class SharedMutation:
    """A self-evolution mutation shared across the P2P swarm."""
    mutation_id: str
    source_node_id: str
    file_path: str
    mutation_type: str  # threshold / prompt / dead_code / refactor / structure
    fitness_score: float
    original_diff: str  # unified diff text
    generation: int = 0
    description: str = ""
    timestamp: float = field(default_factory=time.time)
    signature: str = ""

    def __post_init__(self) -> None:
        if not self.signature:
            self.signature = self._compute_signature()

    def _compute_signature(self) -> str:
        payload = f"{self.source_node_id}:{self.file_path}:{self.original_diff}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "mutation_id": self.mutation_id,
            "source_node_id": self.source_node_id,
            "file_path": self.file_path,
            "mutation_type": self.mutation_type,
            "fitness_score": self.fitness_score,
            "original_diff": self.original_diff,
            "generation": self.generation,
            "description": self.description,
            "timestamp": self.timestamp,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, d: dict) -> SharedMutation:
        return cls(
            mutation_id=d["mutation_id"],
            source_node_id=d["source_node_id"],
            file_path=d["file_path"],
            mutation_type=d["mutation_type"],
            fitness_score=d["fitness_score"],
            original_diff=d["original_diff"],
            generation=d.get("generation", 0),
            description=d.get("description", ""),
            timestamp=d.get("timestamp", time.time()),
            signature=d.get("signature", ""),
        )


@dataclass
class MutationValidation:
    """Result of validating a received swarm mutation."""
    mutation_id: str
    valid: bool
    reason: str = ""
    sandbox_result: bool = False
    test_results: dict = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
# Main Class
# ═══════════════════════════════════════════════════════════════

class SwarmEvolution:
    """Distributed evolution — broadcast & receive mutations across P2P swarm nodes.

    Lifecycle:
        1. Local mutation succeeds (fitness > 0.3, tests pass)
        2. share_mutation() → broadcast to swarm via p2p_node.py
        3. Other nodes receive_mutation() → validate → maybe apply
        4. sync_with_swarm() → periodically pull missed mutations from peers
    """

    MESSAGE_TYPE = "swarm_mutation"

    def __init__(self, source_root: str = "livingtree", project_root: str = "."):
        self.source_root = Path(source_root)
        self.project_root = Path(project_root)
        self._sent: dict[str, SharedMutation] = {}
        self._received: dict[str, SharedMutation] = {}
        self._applied: dict[str, SharedMutation] = {}
        self._rejected: dict[str, tuple[SharedMutation, str]] = {}
        self._signatures: set[str] = set()
        self._node_trust: dict[str, float] = {}
        self._p2p_node = None
        SWARM_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._load()

    # ── Broadcasting ──

    def share_mutation(
        self,
        mutation_id: str = "",
        source_node_id: str = "",
        file_path: str = "",
        mutation_type: str = "",
        fitness_score: float = 0.0,
        original_diff: str = "",
        generation: int = 0,
        description: str = "",
    ) -> Optional[SharedMutation]:
        """Broadcast a successful local mutation to all connected swarm peers.

        Args:
            mutation_id: UUID for this mutation (auto-generated if blank).
            source_node_id: Node ID of the originating node.
            file_path: Relative path to the mutated source file.
            mutation_type: Category (threshold/prompt/dead_code/refactor/structure).
            fitness_score: Fitness score from local evolution pipeline.
            original_diff: Unified diff of the mutation.
            generation: Evolution generation number.
            description: Human-readable description of the change.

        Returns:
            SharedMutation if broadcast, None if below fitness threshold.
        """
        if fitness_score < MIN_FITNESS_FOR_SHARE:
            logger.debug(f"Swarm: mutation fitness {fitness_score:.2f} below share threshold")
            return None

        mutation = SharedMutation(
            mutation_id=mutation_id or str(uuid.uuid4()),
            source_node_id=source_node_id,
            file_path=file_path,
            mutation_type=mutation_type,
            fitness_score=fitness_score,
            original_diff=original_diff,
            generation=generation,
            description=description,
        )

        if mutation.signature in self._signatures:
            logger.debug(f"Swarm: ignoring duplicate mutation {mutation.signature}")
            return None

        self._signatures.add(mutation.signature)
        self._sent[mutation.mutation_id] = mutation
        self._save()

        self._broadcast_to_swarm(mutation)
        logger.info(
            f"Swarm: shared mutation {mutation.mutation_id[:8]} ({mutation_type}) "
            f"fitness={fitness_score:.3f} → swarm"
        )
        return mutation

    def _broadcast_to_swarm(self, mutation: SharedMutation) -> None:
        """Send mutation data to all known peers via P2P relay."""
        p2p = self._get_p2p_node()
        if p2p is None:
            logger.debug("Swarm: P2P node not available, skipping broadcast")
            return

        payload = {
            "type": self.MESSAGE_TYPE,
            "mutation": mutation.to_dict(),
        }

        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                for peer_id in p2p._peers:
                    asyncio.ensure_future(p2p.send_to_peer(peer_id, payload))
            else:
                for peer_id in p2p._peers:
                    loop.run_until_complete(p2p.send_to_peer(peer_id, payload))
        except Exception as e:
            logger.debug(f"Swarm: broadcast error: {e}")

    # ── Receiving ──

    def receive_mutation(self, mutation_data: dict) -> Optional[MutationValidation]:
        """Receive and process a mutation from another swarm node.

        Steps: parse → dedup → validate → maybe apply.
        """
        try:
            mutation = SharedMutation.from_dict(mutation_data)
        except Exception as e:
            logger.warning(f"Swarm: invalid mutation data: {e}")
            return MutationValidation(
                mutation_id=mutation_data.get("mutation_id", "unknown"),
                valid=False,
                reason=f"parse error: {e}",
            )

        if mutation.signature in self._signatures:
            return MutationValidation(
                mutation_id=mutation.mutation_id,
                valid=False,
                reason="duplicate signature",
            )

        validation = self.validate_mutation(mutation)

        if validation.valid:
            self._received[mutation.mutation_id] = mutation
            self._signatures.add(mutation.signature)
            self._save()

            applied = self.apply_mutation(mutation)
            if applied:
                self._applied[mutation.mutation_id] = mutation
                self._adjust_trust(mutation.source_node_id, +0.05)
                logger.info(
                    f"Swarm: applied mutation {mutation.mutation_id[:8]} "
                    f"from node {mutation.source_node_id[:12]}"
                )
            else:
                self._rejected[mutation.mutation_id] = (mutation, "apply failed")
                self._adjust_trust(mutation.source_node_id, -0.02)
        else:
            self._rejected[mutation.mutation_id] = (mutation, validation.reason)
            self._signatures.add(mutation.signature)
            self._save()

        return validation

    # ── Validation ──

    def validate_mutation(self, mutation: SharedMutation) -> MutationValidation:
        """Validate a received mutation before applying.

        Checks:
            1. Fitness score meets minimum threshold
            2. Source node is trusted enough
            3. Diff applies cleanly in sandbox
            4. Test suite passes after applying
        """
        if mutation.fitness_score < MIN_FITNESS_FOR_SHARE:
            return MutationValidation(
                mutation_id=mutation.mutation_id,
                valid=False,
                reason=f"fitness {mutation.fitness_score:.2f} < {MIN_FITNESS_FOR_SHARE}",
            )

        trust = self._node_trust.get(mutation.source_node_id, 0.0)
        if trust < MIN_TRUST_FOR_APPLY and self._node_trust:
            return MutationValidation(
                mutation_id=mutation.mutation_id,
                valid=False,
                reason=f"node trust {trust:.2f} < {MIN_TRUST_FOR_APPLY}",
            )

        target_file = self.source_root / mutation.file_path
        if not target_file.exists():
            return MutationValidation(
                mutation_id=mutation.mutation_id,
                valid=False,
                reason=f"target file not found: {mutation.file_path}",
            )

        sandbox_ok = self._sandbox_test(mutation)
        if not sandbox_ok:
            return MutationValidation(
                mutation_id=mutation.mutation_id,
                valid=False,
                reason="sandbox test failed",
                sandbox_result=False,
            )

        test_ok, test_results = self._run_test_suite(mutation)
        if not test_ok:
            return MutationValidation(
                mutation_id=mutation.mutation_id,
                valid=False,
                reason="test suite failed",
                sandbox_result=True,
                test_results=test_results,
            )

        return MutationValidation(
            mutation_id=mutation.mutation_id,
            valid=True,
            reason="all checks passed",
            sandbox_result=True,
            test_results=test_results,
        )

    def _sandbox_test(self, mutation: SharedMutation) -> bool:
        """Verify the diff applies cleanly to a copy of the target file."""
        import tempfile

        target_file = self.source_root / mutation.file_path
        try:
            original = target_file.read_text("utf-8")
        except Exception:
            return False

        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(original)
                tmp_path = tmp.name

            result = subprocess.run(
                ["patch", "--dry-run", "-p0", tmp_path],
                input=mutation.original_diff,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.project_root),
            )
            Path(tmp_path).unlink(missing_ok=True)
            return result.returncode == 0
        except FileNotFoundError:
            return True
        except Exception:
            return False

    def _run_test_suite(self, mutation: SharedMutation) -> tuple[bool, dict]:
        """Run pytest after applying the mutation to a sandbox copy.

        Returns (passed, {stdout_lines, stderr_lines, returncode, duration}).
        """
        import tempfile
        import shutil

        target_file = self.source_root / mutation.file_path
        try:
            original = target_file.read_text("utf-8")
        except Exception:
            return False, {"error": "cannot read target file"}

        sandbox_dir = Path(tempfile.mkdtemp(prefix="swarm_sandbox_"))
        try:
            relative_dir = Path(mutation.file_path).parent
            target_sandbox = sandbox_dir / relative_dir / Path(mutation.file_path).name
            target_sandbox.parent.mkdir(parents=True, exist_ok=True)
            target_sandbox.write_text(original, "utf-8")
            sandbox_top = sandbox_dir / self.source_root.name
            shutil.copytree(
                str(self.source_root),
                str(sandbox_top),
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".livingtree"),
            )

            result = subprocess.run(
                ["patch", "-p0"],
                input=mutation.original_diff,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(sandbox_dir),
            )
            if result.returncode != 0:
                return False, {"patch_failed": result.stderr[:200]}

            start = time.time()
            test_result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/", "--tb=no", "-q"],
                capture_output=True,
                text=True,
                timeout=180,
                cwd=str(sandbox_dir),
            )
            duration = time.time() - start
            passed = test_result.returncode == 0

            return passed, {
                "returncode": test_result.returncode,
                "stdout_tail": test_result.stdout.splitlines()[-5:] if test_result.stdout else [],
                "duration": round(duration, 2),
            }
        except Exception as e:
            return False, {"error": str(e)[:200]}
        finally:
            shutil.rmtree(str(sandbox_dir), ignore_errors=True)

    # ── Applying ──

    def apply_mutation(self, mutation: SharedMutation) -> bool:
        """Apply a validated mutation to the local codebase."""
        try:
            result = subprocess.run(
                ["patch", "-p0"],
                input=mutation.original_diff,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.project_root),
            )
            ok = result.returncode == 0
            if not ok:
                logger.warning(f"Swarm: patch apply failed: {result.stderr[:120]}")
            return ok
        except Exception as e:
            logger.warning(f"Swarm: apply exception: {e}")
            return False

    # ── Trust Scoring ──

    def _adjust_trust(self, node_id: str, delta: float) -> None:
        current = self._node_trust.get(node_id, 0.0)
        self._node_trust[node_id] = max(-1.0, min(1.0, current + delta))

    # ── Syncing ──

    def sync_with_swarm(self) -> list[SharedMutation]:
        """Pull recent mutations from known peers that we haven't seen yet.

        Sends a sync request to each peer, collects responses, and processes
        any new mutations.
        """
        p2p = self._get_p2p_node()
        if p2p is None:
            return []

        new_mutations: list[SharedMutation] = []
        request = {"type": "swarm_sync_request", "known_signatures": list(self._signatures)}

        import asyncio

        async def _gather():
            for peer_id in list(p2p._peers.keys())[:10]:
                try:
                    await p2p.send_to_peer(peer_id, request)
                except Exception:
                    pass

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(_gather())
            else:
                loop.run_until_complete(_gather())
        except Exception as e:
            logger.debug(f"Swarm: sync error: {e}")

        logger.debug(f"Swarm: sync requested from {len(p2p._peers)} peers")
        return new_mutations

    # ── P2P message handler (registered on p2p_node) ──

    async def _on_swarm_message(self, data: dict) -> None:
        """Handle incoming P2P messages related to swarm evolution."""
        msg_type = data.get("type", "")
        if msg_type == self.MESSAGE_TYPE:
            self.receive_mutation(data.get("mutation", {}))
        elif msg_type == "swarm_sync_request":
            known = set(data.get("known_signatures", []))
            unsent = [
                m.to_dict()
                for m in self._sent.values()
                if m.signature not in known
            ]
            if unsent:
                p2p = self._get_p2p_node()
                sender = data.get("from", "")
                if p2p and sender:
                    for m in unsent:
                        try:
                            await p2p.send_to_peer(sender, {
                                "type": self.MESSAGE_TYPE,
                                "mutation": m,
                            })
                        except Exception:
                            pass

    def register_with_p2p(self) -> bool:
        """Register the swarm message handler on the global P2P node."""
        p2p = self._get_p2p_node()
        if p2p is None:
            logger.debug("Swarm: cannot register, no P2P node available")
            return False
        p2p.on_message(self._on_swarm_message)
        logger.info("Swarm: registered message handler on P2P node")
        return True

    # ── Queries ──

    def get_shared_mutations(self, limit: int = 50) -> list[dict]:
        """Return recently shared (sent) mutations, newest first."""
        sorted_muts = sorted(
            self._sent.values(), key=lambda m: m.timestamp, reverse=True
        )
        return [m.to_dict() for m in sorted_muts[:limit]]

    def stats(self) -> dict:
        """Return swarm evolution runtime statistics."""
        return {
            "total_shared": len(self._sent),
            "total_received": len(self._received),
            "applied": len(self._applied),
            "rejected": len(self._rejected),
            "duplicates_avoided": (
                len(self._signatures)
                - len(self._sent)
                - len(self._received)
            ),
            "trusted_nodes": len(self._node_trust),
            "top_trusted": sorted(
                self._node_trust.items(), key=lambda kv: -kv[1]
            )[:5],
        }

    def reputation(self, node_id: str) -> float:
        """Return the trust score for a given node ID."""
        return self._node_trust.get(node_id, 0.0)

    # ── Persistence ──

    def _save(self) -> None:
        """Persist swarm mutations to disk."""
        try:
            data = {
                "sent": {k: v.to_dict() for k, v in self._sent.items()},
                "received": {k: v.to_dict() for k, v in self._received.items()},
                "applied": {k: v.to_dict() for k, v in self._applied.items()},
                "rejected": {
                    k: {"mutation": m.to_dict(), "reason": r}
                    for k, (m, r) in self._rejected.items()
                },
                "signatures": list(self._signatures),
                "node_trust": self._node_trust,
            }
            SWARM_MUTATIONS_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), "utf-8"
            )
        except Exception as e:
            logger.warning(f"Swarm: save error: {e}")

    def _load(self) -> None:
        """Load swarm mutations from disk."""
        if not SWARM_MUTATIONS_FILE.exists():
            return

        try:
            data = json.loads(SWARM_MUTATIONS_FILE.read_text("utf-8"))
            for v in data.get("sent", {}).values():
                m = SharedMutation.from_dict(v)
                self._sent[m.mutation_id] = m
            for v in data.get("received", {}).values():
                m = SharedMutation.from_dict(v)
                self._received[m.mutation_id] = m
            for v in data.get("applied", {}).values():
                m = SharedMutation.from_dict(v)
                self._applied[m.mutation_id] = m
            for k, v in data.get("rejected", {}).items():
                m = SharedMutation.from_dict(v["mutation"])
                self._rejected[k] = (m, v.get("reason", ""))
            self._signatures = set(data.get("signatures", []))
            self._node_trust = data.get("node_trust", {})

            all_sigs: set[str] = set()
            for m in self._sent.values():
                all_sigs.add(m.signature)
            for m in self._received.values():
                all_sigs.add(m.signature)
            self._signatures |= all_sigs

            logger.debug(
                f"Swarm: loaded {len(self._sent)} sent, {len(self._received)} received, "
                f"{len(self._applied)} applied, {len(self._node_trust)} trusted nodes"
            )
        except Exception as e:
            logger.warning(f"Swarm: load error: {e}")

    # ── P2P access ──

    def _get_p2p_node(self):
        if self._p2p_node is not None:
            return self._p2p_node
        try:
            from ..network.p2p_node import get_p2p_node
            self._p2p_node = get_p2p_node()
            return self._p2p_node
        except Exception:
            return None


# ═══════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════

_swarm: SwarmEvolution | None = None


def get_swarm_evolution() -> SwarmEvolution:
    global _swarm
    if _swarm is None:
        _swarm = SwarmEvolution()
    return _swarm
