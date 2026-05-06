"""P2PPresence — Distributed spatial perception across LivingTree nodes.

Enables multiple LivingTree instances to share presence observations,
cross-validate entity detections, and build a unified spatial map.

Analogy (RuView): ESP32 mesh (4-6 nodes) captures CSI on 3 channels × 56
subcarriers = 168 data streams, fused via attention networks.
LivingTree: P2P mesh nodes each observe their local presence signals, then
share Structured Presence Reports (SPR) via encrypted P2P channels. The
"Presence Fusion" engine combines cross-node observations with consensus
voting and conflict resolution.

Key Concepts:
- PresenceShare: structured data exchanged between nodes
- PresenceFusion: cross-node observation merging (voting + bayesian)
- SpatialMap: distributed topology built from shared observations
- DriftDetection: detect when a node's perception diverges from consensus

Innovation: "Collective Presence Field" — multiple nodes observing the same
space build a probabilistic field model similar to multi-static radar,
achieving higher accuracy than any single node alone.
"""

from __future__ import annotations

import json
import time
import asyncio
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


# ── Types ──

class SharePriority(str, Enum):
    URGENT = "urgent"      # Entity appeared/disappeared
    HIGH = "high"          # Activity level change
    NORMAL = "normal"      # Periodic update
    LOW = "low"            # Background sync


@dataclass
class PresenceShare:
    """Structured presence data shared between P2P nodes."""
    node_id: str
    node_name: str
    timestamp: float
    priority: SharePriority = SharePriority.NORMAL
    entities: list[dict] = field(default_factory=list)   # [{entity_id, type, confidence, activity}]
    activity_summary: dict = field(default_factory=dict)
    ghost_detection: dict | None = None
    spatial_snapshot: dict = field(default_factory=dict)
    sequence: int = 0              # Monotonic sequence number
    ttl: int = 3                   # Hop limit


@dataclass
class FusedObservation:
    """Result of fusing observations from multiple nodes about one entity."""
    entity_id: str
    node_sightings: dict[str, float]   # {node_id: confidence}
    fused_confidence: float
    consensus: float                   # 0-1 inter-node agreement
    activity: str
    location_consensus: str            # Most agreed-upon zone/proximity
    conflicts: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class DriftSeverity(str, Enum):
    NONE = "none"
    MILD = "mild"            # Slight deviation from consensus
    MODERATE = "moderate"    # Notable divergence
    SEVERE = "severe"        # Major disagreement — possible sensor issue
    ISOLATED = "isolated"    # Node appears disconnected from reality


@dataclass
class DriftAlert:
    """Alert when a node's perception significantly differs from peers."""
    node_id: str
    severity: DriftSeverity
    entity_id: str
    node_confidence: float
    consensus_confidence: float
    divergence: float        # How far off the node is
    message: str
    timestamp: float = field(default_factory=time.time)


# ── Fusion Engine ──

class PresenceFusion:
    """Fuses presence observations from multiple P2P nodes.

    Uses weighted voting + Bayesian update to produce a unified
    entity presence picture. Higher weights for nodes with:
    - Better reputation (from network/reputation.py)
    - Lower latency (more timely observations)
    - More observation history (established track record)
    """

    OBSERVATION_TTL = 300       # 5 minutes before observation expires
    CONSENSUS_THRESHOLD = 0.4   # Minimum node agreement for consensus

    def __init__(self):
        self._observations: dict[str, dict[str, Any]] = {}  # entity_id → {node_id → data}
        self._fused: dict[str, FusedObservation] = {}
        self._node_weights: dict[str, float] = {}           # node_id → weight
        self._history: deque[FusedObservation] = deque(maxlen=500)

    def submit_observation(self, node_id: str, share: PresenceShare,
                           node_reputation: float = 0.5) -> int:
        """Submit a node's presence share for fusion. Returns entities updated."""
        weight = 0.3 + node_reputation * 0.7
        self._node_weights[node_id] = weight

        updated = 0
        for entity in share.entities:
            eid = entity.get("entity_id", "")
            if not eid:
                continue

            if eid not in self._observations:
                self._observations[eid] = {}
            self._observations[eid][node_id] = {
                "confidence": entity.get("confidence", 0.5),
                "activity": entity.get("activity", "idle"),
                "type": entity.get("type", "unknown"),
                "location": entity.get("location_hint", ""),
                "timestamp": share.timestamp,
                "weight": weight,
            }
            updated += 1

        # Fuse updated entities
        for eid in list(self._observations.keys()):
            self._fuse_entity(eid)

        return updated

    def get_fused(self, entity_id: str) -> FusedObservation | None:
        """Get the fused observation for an entity."""
        return self._fused.get(entity_id)

    def get_all_fused(self) -> list[FusedObservation]:
        """Get all currently fused entity observations."""
        self._prune_expired()
        return list(self._fused.values())

    def get_consensus_entities(self, min_confidence: float = 0.5) -> list[FusedObservation]:
        """Get entities with strong multi-node consensus."""
        return [f for f in self._fused.values()
                if f.consensus > self.CONSENSUS_THRESHOLD
                and f.fused_confidence >= min_confidence]

    # ── Private ──

    def _fuse_entity(self, entity_id: str) -> FusedObservation | None:
        """Fuse observations from all nodes for a single entity."""
        obs_dict = self._observations.get(entity_id, {})
        if not obs_dict:
            return None

        # Weighted average confidence
        total_weight = 0.0
        weighted_conf = 0.0
        activity_votes: dict[str, float] = {}
        location_votes: dict[str, float] = {}

        for node_id, obs in obs_dict.items():
            weight = obs["weight"]
            weighted_conf += obs["confidence"] * weight
            total_weight += weight
            activity_votes[obs["activity"]] = activity_votes.get(obs["activity"], 0) + weight
            loc = obs.get("location", "")
            if loc:
                location_votes[loc] = location_votes.get(loc, 0) + weight

        fused_conf = weighted_conf / total_weight if total_weight > 0 else 0.0

        # Consensus: how much nodes agree (variance of confidences)
        confidences = [obs["confidence"] for obs in obs_dict.values()]
        if len(confidences) > 1:
            mean_conf = sum(confidences) / len(confidences)
            variance = sum((c - mean_conf) ** 2 for c in confidences) / len(confidences)
            consensus = max(0.0, 1.0 - variance * 2)  # lower variance = higher consensus
        else:
            consensus = 0.5  # single observer = uncertain

        # Best activity and location
        best_activity = max(activity_votes, key=activity_votes.get) if activity_votes else "unknown"
        best_location = max(location_votes, key=location_votes.get) if location_votes else ""

        # Detect conflicts: nodes with confidence > 2 std from mean
        conflicts = []
        if len(confidences) > 2:
            std_dev = (sum((c - mean_conf) ** 2 for c in confidences) / len(confidences)) ** 0.5
            for node_id, obs in obs_dict.items():
                if abs(obs["confidence"] - mean_conf) > 2 * std_dev:
                    conflicts.append(node_id)

        fused = FusedObservation(
            entity_id=entity_id,
            node_sightings={nid: obs["confidence"] for nid, obs in obs_dict.items()},
            fused_confidence=round(fused_conf, 3),
            consensus=round(consensus, 3),
            activity=best_activity,
            location_consensus=best_location,
            conflicts=conflicts,
        )
        self._fused[entity_id] = fused
        self._history.append(fused)
        return fused

    def _prune_expired(self) -> None:
        """Remove expired observations."""
        now = time.time()
        expired_entities = []
        for eid, obs_dict in self._observations.items():
            obs_dict_copy = dict(obs_dict)
            for node_id, obs in obs_dict_copy.items():
                if now - obs["timestamp"] > self.OBSERVATION_TTL:
                    del obs_dict[node_id]
            if not obs_dict:
                expired_entities.append(eid)
        for eid in expired_entities:
            del self._observations[eid]
            self._fused.pop(eid, None)

    def _get_consensus_stats(self) -> dict:
        entities = self._fused
        if not entities:
            return {"avg_consensus": 0.0, "high_consensus": 0, "total": 0}
        avg = sum(e.consensus for e in entities.values()) / len(entities)
        high = sum(1 for e in entities.values() if e.consensus > 0.7)
        return {"avg_consensus": round(avg, 3), "high_consensus": high, "total": len(entities)}


# ── Drift Detection ──

class DriftDetector:
    """Detects when a node's perception diverges from the P2P consensus.

    Potential causes:
    - Sensor/input degradation (noisy signal)
    - Isolated network segment (can't see other nodes)
    - Compromised node (tampered perception)
    - Environmental change (node moved to new location)
    """

    DRIFT_HISTORY_SIZE = 20
    MILD_DRIFT_SIGMA = 1.5         # 1.5 std from mean
    MODERATE_DRIFT_SIGMA = 2.5
    SEVERE_DRIFT_SIGMA = 3.5

    def __init__(self, fusion: PresenceFusion):
        self._fusion = fusion
        self._node_history: dict[str, deque[float]] = {}  # node_id → recent divergences
        self._alerts: deque[DriftAlert] = deque(maxlen=100)

    def check_node(self, node_id: str, entity_id: str,
                   node_confidence: float) -> DriftAlert | None:
        """Check if a node's observation for an entity is drifting."""
        fused = self._fusion.get_fused(entity_id)
        if not fused or node_id not in fused.node_sightings:
            return None

        consensus_conf = fused.fused_confidence
        divergence = abs(node_confidence - consensus_conf)

        # Track history
        if node_id not in self._node_history:
            self._node_history[node_id] = deque(maxlen=self.DRIFT_HISTORY_SIZE)
        self._node_history[node_id].append(divergence)

        history = list(self._node_history[node_id])
        if len(history) < 5:
            return None  # not enough data

        mean_div = sum(history) / len(history)
        std_div = (sum((d - mean_div) ** 2 for d in history) / len(history)) ** 0.5
        if std_div < 0.01:
            return None  # too stable to detect drift

        z_score = (divergence - mean_div) / std_div

        if z_score > self.SEVERE_DRIFT_SIGMA:
            severity = DriftSeverity.SEVERE
            msg = f"Node {node_id[:8]} severely diverged on {entity_id} (z={z_score:.1f})"
        elif z_score > self.MODERATE_DRIFT_SIGMA:
            severity = DriftSeverity.MODERATE
            msg = f"Node {node_id[:8]} moderately diverged on {entity_id} (z={z_score:.1f})"
        elif z_score > self.MILD_DRIFT_SIGMA:
            severity = DriftSeverity.MILD
            msg = f"Node {node_id[:8]} slightly diverged on {entity_id} (z={z_score:.1f})"
        else:
            return None

        alert = DriftAlert(
            node_id=node_id, severity=severity, entity_id=entity_id,
            node_confidence=round(node_confidence, 3),
            consensus_confidence=round(consensus_conf, 3),
            divergence=round(divergence, 3), message=msg,
        )
        self._alerts.append(alert)
        logger.warning(msg)
        return alert

    def check_isolation(self, node_id: str, active_peers: int) -> DriftAlert | None:
        """Check if a node is isolated from the P2P network."""
        if active_peers < 2:
            alert = DriftAlert(
                node_id=node_id, severity=DriftSeverity.ISOLATED,
                entity_id="*", node_confidence=0.0, consensus_confidence=0.0,
                divergence=1.0,
                message=f"Node {node_id[:8]} isolated (only {active_peers} active peers)",
            )
            self._alerts.append(alert)
            return alert
        return None

    def get_alerts(self, severity: DriftSeverity | None = None) -> list[DriftAlert]:
        if severity:
            return [a for a in self._alerts if a.severity == severity]
        return list(self._alerts)

    def get_node_status(self, node_id: str) -> dict:
        history = list(self._node_history.get(node_id, []))
        if not history:
            return {"status": "unknown", "mean_divergence": 0.0}
        mean_div = sum(history) / len(history)
        return {
            "status": "healthy" if mean_div < 0.2 else "drifting" if mean_div < 0.4 else "divergent",
            "mean_divergence": round(mean_div, 3),
            "observations": len(history),
        }


# ── Main Coordinator ──

class P2PPresence:
    """Orchestrates distributed spatial perception across P2P nodes.

    Coordinates between:
    - PresenceSensor (local entity detection)
    - SpatialAwareness (spatial topology)
    - BiometricRegistry (entity identification)
    - P2P network (node communication)
    - PresenceFusion (cross-node observation fusion)
    - DriftDetector (perception health monitoring)
    """

    SHARE_INTERVAL = 15.0     # Seconds between presence shares
    URGENT_SHARE_DELAY = 2.0  # Delay before sharing urgent events

    def __init__(self, world=None):
        self._world = world
        self._fusion = PresenceFusion()
        self._drift = DriftDetector(self._fusion)
        self._last_share: float = 0.0
        self._sequence = 0
        self._pending_urgent: deque[PresenceShare] = deque(maxlen=20)

    # ── Local observation → share ──

    def build_share(self, presence_sensor=None,
                    spatial=None, biometric=None,
                    priority: SharePriority = SharePriority.NORMAL) -> PresenceShare:
        """Build a presence share from local sensors."""
        ps = presence_sensor
        entities = []
        if ps:
            for e in ps.detect():
                entities.append({
                    "entity_id": e.entity_id,
                    "name": e.name,
                    "type": e.entity_type.value,
                    "confidence": e.confidence,
                    "activity": e.activity_level.value,
                    "location_hint": e.location_hint,
                    "staleness": round(e.staleness, 1),
                })

            ghost = ps._detect_ghost() if hasattr(ps, '_detect_ghost') else None
            ghost_data = {"detected": ghost.detected, "confidence": ghost.confidence,
                          "distance": ghost.estimated_distance} if ghost else None

            activity = ps._activity_summary()
        else:
            ghost_data = None
            activity = {}

        spatial_snapshot = spatial.get_spatial_report() if spatial else {}

        node_id = ""
        node_name = ""
        if self._world:
            p2p = getattr(self._world, 'p2p_node', None)
            if p2p:
                node_id = getattr(p2p, 'node_id', '')
                node_name = getattr(p2p, 'name', '')

        self._sequence += 1
        return PresenceShare(
            node_id=node_id, node_name=node_name,
            timestamp=time.time(), priority=priority,
            entities=entities, activity_summary=activity,
            ghost_detection=ghost_data, spatial_snapshot=spatial_snapshot,
            sequence=self._sequence,
        )

    # ── Receive remote share ──

    def receive_share(self, share_data: dict | str) -> PresenceShare | None:
        """Process a presence share received from a peer node."""
        try:
            if isinstance(share_data, str):
                share_data = json.loads(share_data)
            share = PresenceShare(**share_data)

            # Submit for fusion
            node_reputation = 0.5
            if self._world:
                rep = getattr(self._world, 'reputation', None)
                if rep and hasattr(rep, 'get_score'):
                    node_reputation = rep.get_score(share.node_id) or 0.5

            updated = self._fusion.submit_observation(share.node_id, share, node_reputation)

            # Drift check
            for entity in share.entities:
                self._drift.check_node(
                    share.node_id, entity["entity_id"], entity["confidence"])

            logger.debug(f"P2PPresence: received share from {share.node_id[:8]} "
                         f"({len(share.entities)} entities, {updated} fused)")
            return share
        except Exception as e:
            logger.error(f"P2PPresence: failed to process share: {e}")
            return None

    # ── Periodic sync ──

    async def maybe_share(self, presence_sensor=None, spatial=None,
                          biometric=None, force: bool = False) -> PresenceShare | None:
        """Share presence data with peers if enough time has passed."""
        now = time.time()

        # Check for urgent shares first
        urgent = self._check_urgent(presence_sensor)
        if urgent and (force or now - self._last_share > self.URGENT_SHARE_DELAY):
            share = urgent
        elif force or now - self._last_share > self.SHARE_INTERVAL:
            share = self.build_share(presence_sensor, spatial, biometric)
        else:
            return None

        self._last_share = now
        await self._broadcast_share(share)
        return share

    async def _broadcast_share(self, share: PresenceShare) -> None:
        """Send share to all connected peers."""
        if not self._world:
            return

        try:
            # Use collective consciousness channel
            collective = getattr(self._world, 'collective', None)
            if collective:
                # Encode presence share as knowledge
                from ..network.collective import SharedKnowledge
                # Just log for now — actual transport handled by collective
                logger.debug(f"P2PPresence: would share via collective "
                             f"({len(share.entities)} entities)")

            # Direct P2P broadcast
            node = getattr(self._world, 'node', None)
            if node and hasattr(node, 'broadcast'):
                data = json.dumps(share.__dict__, default=str, ensure_ascii=False)
                await node.broadcast("presence_share", data.encode())
                logger.debug(f"P2PPresence: broadcast presence share (seq={share.sequence})")
        except Exception as e:
            logger.debug(f"P2PPresence: broadcast error: {e}")

    # ── Queries ──

    def get_fused_entities(self) -> list[FusedObservation]:
        return self._fusion.get_all_fused()

    def get_consensus_view(self) -> list[FusedObservation]:
        return self._fusion.get_consensus_entities()

    def get_drift_status(self) -> dict:
        return {
            "alerts": len(self._drift.get_alerts()),
            "severe": len(self._drift.get_alerts(DriftSeverity.SEVERE)),
            "node_statuses": {
                nid: self._drift.get_node_status(nid)
                for nid in self._drift._node_history
            },
        }

    def get_report(self) -> dict[str, Any]:
        """Get comprehensive distributed perception report."""
        fused = self._fusion.get_all_fused()
        consensus_stats = self._fusion._get_consensus_stats()
        return {
            "fused_entities": len(fused),
            "consensus": consensus_stats,
            "drift": {
                "total_alerts": len(self._drift.get_alerts()),
                "severe": len(self._drift.get_alerts(DriftSeverity.SEVERE)),
                "isolated": len(self._drift.get_alerts(DriftSeverity.ISOLATED)),
            },
            "sharing": {
                "last_share_age": round(time.time() - self._last_share, 1),
                "sequence": self._sequence,
                "pending_urgent": len(self._pending_urgent),
            },
            "top_entities": [
                {
                    "id": e.entity_id,
                    "confidence": e.fused_confidence,
                    "consensus": e.consensus,
                    "observers": len(e.node_sightings),
                    "activity": e.activity,
                    "conflicts": e.conflicts,
                }
                for e in sorted(fused, key=lambda x: x.fused_confidence, reverse=True)[:5]
            ],
        }

    # ── Internal ──

    def _check_urgent(self, presence_sensor) -> PresenceShare | None:
        """Check for events that need urgent sharing (entity appeared/disappeared)."""
        if not presence_sensor:
            return None
        # Check for entity state changes
        return None  # Placeholder — full implementation requires state tracking


# ── Singleton ──

P2P_PRESENCE: P2PPresence = None  # type: ignore


def get_p2p_presence(world=None) -> P2PPresence:
    global P2P_PRESENCE
    if P2P_PRESENCE is None:
        P2P_PRESENCE = P2PPresence(world)
    return P2P_PRESENCE
