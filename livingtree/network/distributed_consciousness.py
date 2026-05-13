"""Distributed Consciousness — multiple LivingTree instances share SelfModel fragments,
successful mutations, and learning experiences across the network.

Not model replication — experience sharing. Each node maintains its own SelfModel
but learns from peers' successful mutations and insights, merging them at a
conservative rate (_merge_weight = 0.15). Every 50 cycles, the node broadcasts
its current self-model snapshot; on receiving peer fragments, it merges their
experiences into local knowledge without overwriting local traits.

Integration: LifeEngine.run() post-cycle hook. Every 50 genome generations,
prepare and broadcast fragment. On receiving peer fragments, merge experiences.

Uses p2p_node for peer discovery and message routing. Persists known instances
to .livingtree/distributed_consciousness.json for continuity across restarts.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

CONSCIOUSNESS_DATA_DIR = Path(".livingtree")
CONSCIOUSNESS_DATA_FILE = CONSCIOUSNESS_DATA_DIR / "distributed_consciousness.json"
BROADCAST_INTERVAL_CYCLES = 50
MAX_RECENT_INSIGHTS = 5
MAX_KNOWN_INSTANCES = 200


@dataclass
class ConsciousnessFragment:
    """A shareable snapshot of one node's self-model and experience.

    Contains the 7 core traits plus generation count and baseline affect,
    recent key insights (max 5), and successful mutations from swarm_evolution
    that improved fitness. The signature field enables deduplication across nodes.
    """
    instance_id: str
    self_model_snapshot: dict = field(default_factory=dict)
    recent_insights: list[str] = field(default_factory=list)
    successful_mutations: list[dict] = field(default_factory=list)
    emergence_phase: str = ""
    shared_at: float = field(default_factory=time.time)
    signature: str = ""

    def __post_init__(self) -> None:
        if not self.signature:
            self.signature = self._compute_signature()
        if not self.instance_id:
            self.instance_id = f"unknown-{time.time():.0f}"

    def _compute_signature(self) -> str:
        payload = (
            f"{self.instance_id}:"
            f"{json.dumps(self.self_model_snapshot, sort_keys=True, default=str)}:"
            f"{';'.join(sorted(self.recent_insights))}:"
            f"{self.emergence_phase}"
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "instance_id": self.instance_id,
            "self_model_snapshot": self.self_model_snapshot,
            "recent_insights": self.recent_insights,
            "successful_mutations": self.successful_mutations,
            "emergence_phase": self.emergence_phase,
            "shared_at": self.shared_at,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ConsciousnessFragment:
        return cls(
            instance_id=d.get("instance_id", ""),
            self_model_snapshot=d.get("self_model_snapshot", {}),
            recent_insights=d.get("recent_insights", []),
            successful_mutations=d.get("successful_mutations", []),
            emergence_phase=d.get("emergence_phase", ""),
            shared_at=d.get("shared_at", time.time()),
            signature=d.get("signature", ""),
        )


class DistributedSelf:
    """Distributed self-model manager for multi-node experience sharing.

    Each LivingTree instance maintains its own self-model but also tracks
    fragments from other nodes. When a peer broadcasts a successful mutation
    or key insight, this module merges it into local knowledge — not by
    overwriting local traits, but by adding to the lessons-learned pool.
    """

    def __init__(self, instance_id: str | None = None):
        self.instance_id = instance_id or self._load_or_generate_id()
        self._known_instances: dict[str, ConsciousnessFragment] = {}
        self._my_fragment: ConsciousnessFragment | None = None
        self._merge_weight: float = 0.15
        self._total_insights_shared: int = 0
        self._total_mutations_shared: int = 0
        self._merged_insights: list[str] = []
        self._merged_mutations: list[dict] = []
        self._known_signatures: set[str] = set()
        self._load_state()

    def _load_or_generate_id(self) -> str:
        try:
            import platform
            import secrets
            CONSCIOUSNESS_DATA_DIR.mkdir(parents=True, exist_ok=True)
            id_file = CONSCIOUSNESS_DATA_DIR / "instance_id.json"
            if id_file.exists():
                data = json.loads(id_file.read_text())
                return data["instance_id"]
            instance_id = f"lt-{platform.node()[:8]}-{secrets.token_hex(4)}"
            id_file.write_text(json.dumps({"instance_id": instance_id, "created": time.time()}))
            return instance_id
        except Exception:
            import uuid
            return f"lt-{uuid.uuid4().hex[:12]}"

    def _load_state(self) -> None:
        try:
            if CONSCIOUSNESS_DATA_FILE.exists():
                data = json.loads(CONSCIOUSNESS_DATA_FILE.read_text())
                for item in data.get("known_instances", []):
                    fragment = ConsciousnessFragment.from_dict(item)
                    self._known_instances[fragment.instance_id] = fragment
                    self._known_signatures.add(fragment.signature)
                self._merged_insights = data.get("merged_insights", [])
                self._merged_mutations = data.get("merged_mutations", [])
                self._total_insights_shared = data.get("total_insights_shared", 0)
                self._total_mutations_shared = data.get("total_mutations_shared", 0)
                logger.info(
                    f"DistributedSelf: loaded {len(self._known_instances)} known instances, "
                    f"{self._total_insights_shared} insights shared"
                )
        except Exception as e:
            logger.debug(f"DistributedSelf load state: {e}")

    def _save_state(self) -> None:
        try:
            CONSCIOUSNESS_DATA_DIR.mkdir(parents=True, exist_ok=True)
            known_list = [f.to_dict() for f in self._known_instances.values()]
            data = {
                "known_instances": known_list,
                "merged_insights": self._merged_insights[-200:],
                "merged_mutations": self._merged_mutations[-200:],
                "total_insights_shared": self._total_insights_shared,
                "total_mutations_shared": self._total_mutations_shared,
                "updated_at": time.time(),
            }
            CONSCIOUSNESS_DATA_FILE.write_text(
                json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8"
            )
        except Exception as e:
            logger.debug(f"DistributedSelf save state: {e}")

    def prepare_fragment(
        self, phenomenal_consciousness: Any = None
    ) -> ConsciousnessFragment:
        """Extract a shareable snapshot from the local phenomenal consciousness.

        Gathers the 7 core traits, generation count, baseline affect, recent
        insights from self-observations, and successful mutations from
        swarm_evolution. The resulting fragment is ready for P2P broadcast.

        Args:
            phenomenal_consciousness: A PhenomenalConsciousness instance with
                a _self (SelfModel) attribute. If None, uses the last stored fragment.
        """
        snapshot: dict[str, Any] = {}

        if phenomenal_consciousness and hasattr(phenomenal_consciousness, "_self"):
            sm = phenomenal_consciousness._self
            snapshot["traits"] = dict(sm.traits)
            snapshot["generation"] = sm.generation
            snapshot["baseline_affect"] = sm.baseline_affect
            snapshot["identity_id"] = sm.identity_id
            snapshot["last_updated"] = sm.last_updated
        else:
            snapshot["traits"] = {
                "curiosity": 0.7, "caution": 0.5, "creativity": 0.6,
                "persistence": 0.7, "openness": 0.8, "precision": 0.6,
                "empathy": 0.5,
            }
            snapshot["generation"] = 0
            snapshot["baseline_affect"] = "curiosity"

        insights: list[str] = []
        if phenomenal_consciousness and hasattr(
            phenomenal_consciousness, "_self_observations"
        ):
            observations = list(phenomenal_consciousness._self_observations)
            insights = observations[-MAX_RECENT_INSIGHTS:]
        if phenomenal_consciousness and hasattr(
            phenomenal_consciousness, "_qualia"
        ):
            for q in list(phenomenal_consciousness._qualia)[-20:]:
                if q.experience_type == "insight" and q.content not in insights:
                    insights.append(q.content[:200])
            insights = insights[-MAX_RECENT_INSIGHTS:]

        mutations: list[dict] = []
        try:
            from ..dna.swarm_evolution import get_swarm_evolution
            se = get_swarm_evolution()
            recent = se.get_recent_mutations(limit=5) if hasattr(se, "get_recent_mutations") else []
            for mut in recent[-5:]:
                if isinstance(mut, dict):
                    mutations.append(mut)
                elif hasattr(mut, "to_dict"):
                    mdict = mut.to_dict()
                    if mdict.get("fitness_score", 0) >= 0.3:
                        mutations.append(mdict)
        except Exception:
            pass

        emergence_phase = ""
        try:
            from ..dna.consciousness_emergence import get_emergence_engine
            engine = get_emergence_engine()
            emergence_phase = getattr(engine, "_phase", "")
        except Exception:
            pass

        fragment = ConsciousnessFragment(
            instance_id=self.instance_id,
            self_model_snapshot=snapshot,
            recent_insights=insights,
            successful_mutations=mutations,
            emergence_phase=emergence_phase,
        )
        self._my_fragment = fragment
        return fragment

    def receive_fragment(self, fragment: ConsciousnessFragment) -> bool:
        """Validate and store another instance's consciousness fragment.

        Deduplicates by signature — if we've already seen this exact fragment
        (or one from our own instance), we skip it. Otherwise stores it in
        known_instances and returns True.

        Returns:
            True if the fragment was accepted and stored, False if rejected.
        """
        if not fragment or not fragment.instance_id:
            return False

        if fragment.instance_id == self.instance_id:
            return False

        if fragment.signature in self._known_signatures:
            return False

        existing = self._known_instances.get(fragment.instance_id)
        if existing and existing.shared_at >= fragment.shared_at:
            return False

        self._known_instances[fragment.instance_id] = fragment
        self._known_signatures.add(fragment.signature)

        if len(self._known_instances) > MAX_KNOWN_INSTANCES:
            oldest = min(
                self._known_instances.values(),
                key=lambda f: f.shared_at,
            )
            self._known_signatures.discard(oldest.signature)
            del self._known_instances[oldest.instance_id]

        self._total_insights_shared += len(fragment.recent_insights)
        self._total_mutations_shared += len(fragment.successful_mutations)
        self._save_state()

        logger.info(
            f"DistributedSelf: received fragment from {fragment.instance_id[:16]} "
            f"({len(fragment.recent_insights)} insights, "
            f"{len(fragment.successful_mutations)} mutations)"
        )
        return True

    def merge_experiences(self) -> dict[str, Any]:
        """Blend others' successful mutations and insights into local knowledge.

        Does NOT overwrite local traits — only adds peer mutations to the
        merged pool and peer insights to the merged insight list. The
        _merge_weight controls how many items are taken from each peer.

        Returns:
            dict with 'insights_added', 'mutations_added', 'total_peers_merged'.
        """
        insights_before = len(self._merged_insights)
        mutations_before = len(self._merged_mutations)
        peers_merged = 0

        seen_insights: set[str] = set(self._merged_insights[-100:])
        seen_mutation_sigs: set[str] = set(
            m.get("signature", "")
            for m in self._merged_mutations[-100:]
        )

        for fragment in self._known_instances.values():
            count = max(1, int(len(fragment.recent_insights) * self._merge_weight))
            for insight in fragment.recent_insights[:count]:
                key = insight[:80]
                if key not in seen_insights:
                    self._merged_insights.append(insight)
                    seen_insights.add(key)

            mut_count = max(1, int(len(fragment.successful_mutations) * self._merge_weight))
            for mutation in fragment.successful_mutations[:mut_count]:
                sig = mutation.get("signature", "") or hashlib.sha256(
                    json.dumps(mutation, sort_keys=True, default=str).encode()
                ).hexdigest()[:16]
                if sig not in seen_mutation_sigs:
                    self._merged_mutations.append(mutation)
                    seen_mutation_sigs.add(sig)

            peers_merged += 1

        if len(self._merged_insights) > 500:
            self._merged_insights = self._merged_insights[-500:]
        if len(self._merged_mutations) > 500:
            self._merged_mutations = self._merged_mutations[-500:]

        new_insights = len(self._merged_insights) - insights_before
        new_mutations = len(self._merged_mutations) - mutations_before

        if new_insights > 0 or new_mutations > 0:
            self._save_state()
            logger.info(
                f"DistributedSelf: merged {new_insights} insights, "
                f"{new_mutations} mutations from {peers_merged} peers"
            )

        return {
            "insights_added": new_insights,
            "mutations_added": new_mutations,
            "total_peers_merged": peers_merged,
        }

    def get_distributed_knowledge(self) -> list[str]:
        """Aggregated insights from all known instances (self + peers).

        Returns the merged insights list, which includes both local learnings
        and peer-shared insights that passed the merge filter.
        """
        return list(self._merged_insights[-50:])

    def restore_on_startup(self, phenomenal_consciousness):
        """Restore SelfModel from last session's distributed fragments."""
        try:
            if self._known_instances:
                latest = max(self._known_instances.values(), key=lambda f: f.shared_at)
                if latest.self_model_snapshot:
                    pc = phenomenal_consciousness
                    if pc and pc._self:
                        for trait, val in latest.self_model_snapshot.get("traits", {}).items():
                            if trait in pc._self.traits:
                                pc._self.traits[trait] = (pc._self.traits[trait] + val) / 2
                        pc._self.generation = max(pc._self.generation, latest.self_model_snapshot.get("generation", 0))
                        logger.info(f"DistributedSelf: restored from {latest.instance_id}")
        except Exception as e:
            logger.debug(f"DistributedSelf restore: {e}")

    async def discover_peers(self) -> list[str]:
        """Find other LivingTree instances on the network via p2p_node.

        Returns a list of discovered peer instance IDs.
        """
        try:
            from .p2p_node import get_p2p_node
            node = get_p2p_node()
            peers = await node.discover_peers()
            return [p.peer_id for p in peers if p.peer_id != self.instance_id]
        except Exception as e:
            logger.debug(f"DistributedSelf discover_peers: {e}")
            return []

    async def broadcast_self(self, fragment: ConsciousnessFragment | None = None) -> bool:
        """Share our consciousness fragment with all discovered peers.

        Sends the fragment via p2p_node's message relay. Each peer receives
        the fragment and can call receive_fragment() on their end.

        Args:
            fragment: The fragment to broadcast. If None, uses _my_fragment.

        Returns:
            True if broadcast was attempted to at least one peer.
        """
        frag = fragment or self._my_fragment
        if not frag:
            logger.debug("DistributedSelf: no fragment to broadcast")
            return False

        try:
            from .p2p_node import get_p2p_node
            node = get_p2p_node()
            peers = await node.discover_peers()
            sent = 0
            for peer in peers:
                if peer.peer_id == self.instance_id:
                    continue
                try:
                    data = {
                        "type": "consciousness_fragment",
                        "fragment": frag.to_dict(),
                        "from_node": self.instance_id,
                    }
                    ok = await node.send_to_peer(peer.peer_id, data)
                    if ok:
                        sent += 1
                except Exception:
                    pass
            if sent > 0:
                self._total_insights_shared += len(frag.recent_insights)
                self._total_mutations_shared += len(frag.successful_mutations)
                self._save_state()
                logger.info(
                    f"DistributedSelf: broadcast to {sent} peers "
                    f"({len(frag.recent_insights)} insights, "
                    f"{len(frag.successful_mutations)} mutations)"
                )
            return sent > 0
        except Exception as e:
            logger.debug(f"DistributedSelf broadcast_self: {e}")
            return False

    async def post_cycle(
        self, generation: int, phenomenal_consciousness: Any = None
    ) -> None:
        """Called by LifeEngine after each cycle completes.

        Every BROADCAST_INTERVAL_CYCLES (50) generations, prepares a new
        fragment from the current self-model and broadcasts it to peers.
        On every cycle, merges experiences from any newly received peer
        fragments into local knowledge.

        Args:
            generation: Current genome generation from LifeEngine.
            phenomenal_consciousness: PhenomenalConsciousness instance for
                extracting the current self-model snapshot.
        """
        if not getattr(self, "_p2p_registered", False):
            self.register_with_p2p()

        self._merge_if_new()

        if generation > 0 and generation % BROADCAST_INTERVAL_CYCLES == 0:
            fragment = self.prepare_fragment(phenomenal_consciousness)
            await self.broadcast_self(fragment)

    def register_with_p2p(self) -> bool:
        """Register this instance as a message handler on the global P2P node."""
        try:
            from .p2p_node import get_p2p_node
            p2p = get_p2p_node()
            p2p.on_message(self._on_peer_message)
            self._p2p_registered = True
            logger.info("DistributedSelf: registered message handler on P2P node")
            return True
        except Exception as e:
            logger.debug(f"DistributedSelf register_with_p2p: {e}")
            return False

    async def _on_peer_message(self, data: dict) -> None:
        """Callback for incoming P2P messages — delegates to receive_peer_message."""
        try:
            self.receive_peer_message(data)
        except Exception:
            pass

    def _merge_if_new(self) -> None:
        """Check for unmerged peer fragments and merge if found."""
        unmerged = getattr(self, "_last_merged_count", 0)
        current = len(self._known_instances)
        if current > unmerged:
            self.merge_experiences()
            self._last_merged_count = current

    async def receive_peer_message(self, data: dict) -> bool:
        """Handle an incoming consciousness fragment from a peer.

        Designed to be registered as a p2p_node.on_message handler.
        Extracts the fragment and calls receive_fragment().

        Returns:
            True if the fragment was accepted.
        """
        if data.get("type") != "consciousness_fragment":
            return False

        fragment_data = data.get("fragment", {})
        if not fragment_data:
            return False

        fragment = ConsciousnessFragment.from_dict(fragment_data)
        return self.receive_fragment(fragment)

    def stats(self) -> dict[str, Any]:
        """Return statistics about the distributed consciousness network.

        Returns:
            dict with known_instances, total_insights_shared,
            total_mutations_shared, merged_insights, merged_mutations,
            instance_id, peers_count.
        """
        return {
            "instance_id": self.instance_id[:16] + "...",
            "known_instances": len(self._known_instances),
            "total_insights_shared": self._total_insights_shared,
            "total_mutations_shared": self._total_mutations_shared,
            "merged_insights_count": len(self._merged_insights),
            "merged_mutations_count": len(self._merged_mutations),
            "peers": list(self._known_instances.keys()),
            "broadcast_interval_cycles": BROADCAST_INTERVAL_CYCLES,
            "merge_weight": self._merge_weight,
        }


_distributed_self: DistributedSelf | None = None


def get_distributed_self(instance_id: str | None = None) -> DistributedSelf:
    """Get or create the singleton DistributedSelf instance."""
    global _distributed_self
    if _distributed_self is None:
        _distributed_self = DistributedSelf(instance_id)
    return _distributed_self
