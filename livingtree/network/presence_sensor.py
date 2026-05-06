"""PresenceSensor — Multi-signal entity detection for LivingTree.

Detects living beings (users, peers, external agents) through indirect
"signal disturbance" patterns — no cameras or special hardware needed.

Analogy (RuView): WiFi CSI subcarrier disturbances → human pose.
LivingTree: interaction pressure, resource rhythm, network pulse, temporal
signatures → detected entities.

Signal Sources:
1. INTERACTION — keystroke rate, command complexity, response latency
2. RESOURCE — CPU/memory usage patterns, process activity
3. NETWORK — P2P heartbeat, external API call frequency, LAN activity
4. TEMPORAL — time-of-day cycles, idle/burst periods, session duration
5. BEHAVIORAL — unique vocabulary, error patterns, workflow preferences

Innovation: "Ghost Detection" — detecting passive presence (someone in the
room but not interacting) through ambient signal baseline shifts.

Usage:
    from livingtree.network.presence_sensor import PresenceSensor
    ps = PresenceSensor()
    ps.feed_signal("keystroke", value=1.0, source="user_terminal")
    entities = ps.detect()
    for e in entities:
        print(f"{e.name} ({e.entity_type}): confidence={e.confidence:.2f}")
"""

from __future__ import annotations

import time
import math
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


# ── Types ──

class SignalSource(str, Enum):
    INTERACTION = "interaction"    # Keystrokes, commands, mouse
    RESOURCE = "resource"          # CPU, memory, disk, processes
    NETWORK = "network"            # P2P, API calls, LAN
    TEMPORAL = "temporal"          # Time patterns, sessions
    BEHAVIORAL = "behavioral"     # Vocabulary, errors, workflows


class EntityType(str, Enum):
    HUMAN_USER = "human_user"           # Living human at keyboard
    PASSIVE_PRESENCE = "passive"        # Present but not interacting
    PEER_NODE = "peer_node"             # Another LivingTree instance
    EXTERNAL_AGENT = "external_agent"   # Bot, API consumer, automated system
    AMBIENT = "ambient"                 # Environmental pattern (background noise)
    UNKNOWN = "unknown"


class ActivityLevel(str, Enum):
    IDLE = "idle"           # No activity detected
    LOW = "low"             # Passive browsing/reading
    ACTIVE = "active"       # Normal interaction
    INTENSE = "intense"     # Heavy coding/typing/commanding
    BURST = "burst"         # Sudden spike (alert/emergency)


@dataclass
class SignalEvent:
    """A single signal observation."""
    source: SignalSource
    signal_type: str           # e.g. "keystroke", "cpu_spike", "peer_heartbeat"
    value: float               # Normalized 0.0-1.0
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PresenceEntity:
    """A detected living being or active presence."""
    entity_id: str
    name: str
    entity_type: EntityType
    confidence: float              # 0.0-1.0 detection confidence
    activity_level: ActivityLevel = ActivityLevel.IDLE
    signal_signature: dict[str, float] = field(default_factory=dict)
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    observation_count: int = 0
    location_hint: str = ""         # "same_room", "same_lan", "remote"
    peer_node_id: str = ""          # If entity_type=PEER_NODE

    @property
    def staleness(self) -> float:
        """Seconds since last seen."""
        return time.time() - self.last_seen

    @property
    def is_active(self) -> bool:
        return self.staleness < 300 and self.activity_level in (
            ActivityLevel.ACTIVE, ActivityLevel.INTENSE, ActivityLevel.BURST)


@dataclass
class GhostDetection:
    """Passive presence detection — someone is nearby but not interacting."""
    detected: bool
    confidence: float
    evidence: list[str]       # What signals suggest ghost presence
    estimated_distance: str   # "same_device", "same_room", "same_building"


@dataclass
class PresenceReport:
    """Complete presence snapshot at a point in time."""
    timestamp: float
    active_entities: list[PresenceEntity]
    ghost_detection: Optional[GhostDetection]
    activity_summary: dict[str, Any]
    node_count: int           # Total LivingTree nodes in network


# ── Signal Processors ──

@dataclass
class SignalWindow:
    """Sliding window of recent signals for pattern detection."""
    signals: deque[SignalEvent] = field(default_factory=lambda: deque(maxlen=200))
    window_seconds: float = 300.0  # 5 minute default

    def add(self, event: SignalEvent) -> None:
        self.signals.append(event)

    def get_recent(self, seconds: float | None = None) -> list[SignalEvent]:
        cutoff = time.time() - (seconds or self.window_seconds)
        return [s for s in self.signals if s.timestamp > cutoff]

    def density(self, source: SignalSource | None = None,
                window: float = 60.0) -> float:
        """Signals per minute for given source."""
        recent = [s for s in self.get_recent(window)
                  if source is None or s.source == source]
        return len(recent) / max(window / 60.0, 1.0)

    def mean_value(self, source: SignalSource, window: float = 60.0) -> float:
        recent = [s for s in self.get_recent(window) if s.source == source]
        if not recent:
            return 0.0
        return sum(s.value for s in recent) / len(recent)

    def burst_score(self, window: float = 10.0) -> float:
        """Detect sudden activity bursts vs baseline."""
        recent = self.get_recent(window)
        baseline = self.get_recent(600.0)
        if not baseline:
            return 0.0
        baseline_rate = len(baseline) / max(600.0, 1.0)
        recent_rate = len(recent) / max(window, 1.0)
        ratio = recent_rate / max(baseline_rate, 0.001)
        return min(1.0, ratio / 5.0)  # 5x baseline = max burst


# ── Main Sensor ──

class PresenceSensor:
    """Multi-signal entity presence detection engine.

    Collects signals from multiple sources, fuses them into entity
    detections, and maintains a temporal presence model.
    """

    # Detection thresholds
    INTERACTION_DENSITY_ACTIVE = 2.0    # signals/min for "active"
    INTERACTION_DENSITY_INTENSE = 10.0  # signals/min for "intense"
    ENTITY_CONFIDENCE_CREATE = 0.4      # Minimum confidence to create entity
    ENTITY_STALE_TIMEOUT = 900          # 15 min without signal → mark as gone
    GHOST_BASELINE_SHIFT = 0.15         # Baseline shift threshold for ghost
    PEER_HEARTBEAT_TIMEOUT = 120        # 2 min without heartbeat → peer gone

    def __init__(self):
        self._window = SignalWindow()
        self._entities: dict[str, PresenceEntity] = {}
        self._entity_counter = 0
        self._baseline: dict[str, float] = {}  # source → baseline mean
        self._baseline_samples: int = 0
        self._ghost_history: deque[GhostDetection] = deque(maxlen=50)
        self._report_history: deque[PresenceReport] = deque(maxlen=100)

    # ── Signal ingestion ──

    def feed_signal(self, signal_type: str, value: float = 1.0,
                    source: str = "default", **metadata) -> SignalEvent:
        """Feed a raw signal into the sensor. Returns the created event."""
        # Classify source
        source_enum = self._classify_source(signal_type)
        event = SignalEvent(
            source=source_enum,
            signal_type=signal_type,
            value=max(0.0, min(1.0, value)),
            metadata={"source_name": source, **metadata},
        )
        self._window.add(event)
        self._update_baseline(event)
        return event

    def feed_batch(self, events: list[dict]) -> list[SignalEvent]:
        """Feed multiple signals at once."""
        results = []
        for evt in events:
            e = self.feed_signal(
                evt.get("type", "unknown"),
                value=evt.get("value", 1.0),
                source=evt.get("source", "batch"),
                **{k: v for k, v in evt.items() if k not in ("type", "value", "source")},
            )
            results.append(e)
        return results

    def feed_keystroke(self, delay_ms: float = 0.0) -> SignalEvent:
        """Record a keystroke with inter-key delay."""
        value = 0.5 if delay_ms < 200 else (0.8 if delay_ms < 500 else 0.3)
        return self.feed_signal("keystroke", value=value, source="keyboard",
                                inter_key_delay_ms=delay_ms)

    def feed_command(self, command: str, complexity: float = 0.5) -> SignalEvent:
        """Record a command execution."""
        return self.feed_signal("command", value=complexity, source="shell",
                                command=command[:100])

    def feed_peer_heartbeat(self, peer_id: str, capabilities: dict | None = None) -> SignalEvent:
        """Record a P2P node heartbeat."""
        caps_str = ",".join(capabilities.get("providers", [])[:3]) if capabilities else ""
        return self.feed_signal("peer_heartbeat", value=0.8, source="p2p",
                                peer_id=peer_id, capabilities=caps_str)

    def feed_cpu_spike(self, cpu_percent: float) -> SignalEvent:
        return self.feed_signal("cpu", value=min(cpu_percent / 100.0, 1.0), source="system")

    def feed_api_call(self, endpoint: str = "", latency_ms: float = 0.0) -> SignalEvent:
        value = min(latency_ms / 5000.0, 1.0) if latency_ms > 0 else 0.5
        return self.feed_signal("api_call", value=value, source="network",
                                endpoint=endpoint[:100])

    # ── Detection ──

    def detect(self) -> list[PresenceEntity]:
        """Run full entity detection pass. Returns all currently active entities."""
        self._prune_stale_entities()
        self._detect_human_user()
        self._detect_peers()
        self._detect_passive_presence()
        return [e for e in self._entities.values() if e.is_active]

    def get_report(self) -> PresenceReport:
        """Get a complete presence snapshot."""
        entities = self.detect()
        ghost = self._detect_ghost()
        return PresenceReport(
            timestamp=time.time(),
            active_entities=entities,
            ghost_detection=ghost,
            activity_summary=self._activity_summary(),
            node_count=sum(1 for e in entities if e.entity_type == EntityType.PEER_NODE),
        )

    def get_entity(self, entity_id: str) -> PresenceEntity | None:
        return self._entities.get(entity_id)

    def list_entities(self, entity_type: EntityType | None = None) -> list[PresenceEntity]:
        if entity_type:
            return [e for e in self._entities.values() if e.entity_type == entity_type]
        return list(self._entities.values())

    # ── Private: Detection logic ──

    def _detect_human_user(self) -> PresenceEntity | None:
        """Detect the primary human user from interaction + resource signals."""
        interaction_density = self._window.density(SignalSource.INTERACTION, 120)
        behavioral_density = self._window.density(SignalSource.BEHAVIORAL, 120)
        cpu_mean = self._window.mean_value(SignalSource.RESOURCE, 60)

        if interaction_density < 0.1 and behavioral_density < 0.05:
            # Update existing user entity to idle if present
            for e in self._entities.values():
                if e.entity_type == EntityType.HUMAN_USER:
                    e.activity_level = ActivityLevel.IDLE
                    e.last_seen = time.time()
            return None

        # Compute activity level and confidence
        total_density = interaction_density + behavioral_density * 0.5
        confidence = min(0.95, total_density / 5.0 + cpu_mean * 0.3)

        if total_density > self.INTERACTION_DENSITY_INTENSE:
            level = ActivityLevel.INTENSE
        elif self._window.burst_score(10) > 0.5:
            level = ActivityLevel.BURST
        elif total_density > self.INTERACTION_DENSITY_ACTIVE:
            level = ActivityLevel.ACTIVE
        else:
            level = ActivityLevel.LOW

        # Find or create entity
        entity = self._find_or_create_entity(
            "human_user_primary", "Primary User",
            EntityType.HUMAN_USER, confidence, level,
        )
        if entity is None:
            return None
        entity.signal_signature = {
            "interaction_rate": round(interaction_density, 2),
            "cpu_utilization": round(cpu_mean, 2),
            "burst_score": round(self._window.burst_score(), 2),
        }
        return entity

    def _detect_peers(self) -> list[PresenceEntity]:
        """Detect peer LivingTree nodes from heartbeat signals."""
        heartbeat_signals = [s for s in self._window.get_recent(600)
                            if s.signal_type == "peer_heartbeat"]
        if not heartbeat_signals:
            return []

        # Group by peer_id
        by_peer: dict[str, list[SignalEvent]] = {}
        for s in heartbeat_signals:
            pid = s.metadata.get("peer_id", "unknown")
            by_peer.setdefault(pid, []).append(s)

        entities = []
        for peer_id, signals in by_peer.items():
            latest = max(signals, key=lambda s: s.timestamp)
            age = time.time() - latest.timestamp
            if age > self.PEER_HEARTBEAT_TIMEOUT:
                continue

            confidence = min(0.9, len(signals) / 5.0 * 0.5 + 0.4)
            entity = self._find_or_create_entity(
                f"peer_{peer_id}", f"Node-{peer_id[:8]}",
                EntityType.PEER_NODE, confidence, ActivityLevel.ACTIVE,
            )
            entity.peer_node_id = peer_id
            entity.location_hint = "same_lan"
            entity.signal_signature = {
                "heartbeat_count": len(signals),
                "last_heartbeat_age_s": round(age, 1),
            }
            entities.append(entity)
        return entities

    def _detect_passive_presence(self) -> None:
        """Detect passive presence (someone nearby, not actively interacting)."""
        ghost = self._detect_ghost()
        if ghost and ghost.detected and ghost.confidence > 0.5:
            self._find_or_create_entity(
                "passive_presence", "Nearby Presence",
                EntityType.PASSIVE_PRESENCE, ghost.confidence,
                ActivityLevel.IDLE,
                location_hint=ghost.estimated_distance,
            )

    def _detect_ghost(self) -> GhostDetection:
        """Detect 'ghost' presence — ambient baseline shifts suggestive of
        someone in the room who isn't directly interacting.

        Innovation: uses the same principle as through-wall WiFi sensing —
        a human body disturbs the EM field even when not transmitting.
        Here, a nearby human disturbs the ambient resource/utilization baseline.
        """
        evidence: list[str] = []
        score = 0.0

        # Check baseline shift in resource signals
        cpu_baseline = self._baseline.get("cpu", 0.0)
        cpu_current = self._window.mean_value(SignalSource.RESOURCE, 300)
        if cpu_baseline > 0 and abs(cpu_current - cpu_baseline) > self.GHOST_BASELINE_SHIFT:
            evidence.append(f"CPU baseline shift: {cpu_baseline:.3f}→{cpu_current:.3f}")
            score += 0.3

        # Check temporal pattern: active during unusual hours = possible ghost
        interaction_recent = self._window.density(SignalSource.INTERACTION, 60)
        interaction_hour = self._window.density(SignalSource.INTERACTION, 3600)
        if interaction_hour > 0.05 and interaction_recent < 0.02:
            evidence.append("Historical activity without current interaction")
            score += 0.25

        # Check network: LAN activity without local interaction
        network_density = self._window.density(SignalSource.NETWORK, 120)
        if network_density > 0.5 and interaction_recent < 0.1:
            evidence.append(f"Network activity ({network_density:.1f}/min) without interaction")
            score += 0.2

        # Check peer nodes: if peers see a human but we don't
        peer_count = sum(1 for e in self._entities.values()
                        if e.entity_type == EntityType.PEER_NODE and e.is_active)
        if peer_count > 0 and interaction_recent < 0.05:
            evidence.append(f"Active peers ({peer_count}) but no local interaction")
            score += 0.15

        detected = score > 0.3
        distance = "same_device" if score > 0.6 else "same_room" if score > 0.4 else "same_building"
        return GhostDetection(detected=detected, confidence=score,
                              evidence=evidence, estimated_distance=distance)

    # ── Private: Helpers ──

    def _find_or_create_entity(self, entity_id: str, name: str,
                                entity_type: EntityType, confidence: float,
                                level: ActivityLevel,
                                location_hint: str = "") -> PresenceEntity:
        """Find existing entity or create new one."""
        now = time.time()
        if entity_id in self._entities:
            entity = self._entities[entity_id]
            entity.confidence = (entity.confidence * 0.7 + confidence * 0.3)
            entity.activity_level = level
            entity.last_seen = now
            entity.observation_count += 1
            if location_hint:
                entity.location_hint = location_hint
            return entity

        if confidence < self.ENTITY_CONFIDENCE_CREATE:
            return None  # not confident enough yet

        entity = PresenceEntity(
            entity_id=entity_id,
            name=name,
            entity_type=entity_type,
            confidence=confidence,
            activity_level=level,
            location_hint=location_hint,
        )
        self._entities[entity_id] = entity
        self._entity_counter += 1
        logger.debug(f"PresenceSensor: detected {entity_type.value} '{name}' "
                     f"(confidence={confidence:.2f})")
        return entity

    def _prune_stale_entities(self) -> None:
        """Remove entities that haven't been seen recently."""
        now = time.time()
        stale_ids = [eid for eid, e in self._entities.items()
                     if now - e.last_seen > self.ENTITY_STALE_TIMEOUT]
        for eid in stale_ids:
            logger.debug(f"PresenceSensor: entity '{self._entities[eid].name}' "
                         f"stale ({now - self._entities[eid].last_seen:.0f}s)")
            del self._entities[eid]

    def _update_baseline(self, event: SignalEvent) -> None:
        """Update running baseline for each signal source."""
        key = event.signal_type
        old = self._baseline.get(key, 0.0)
        n = self._baseline_samples
        self._baseline[key] = (old * n + event.value) / (n + 1)
        if event.signal_type not in ("keystroke", "command", "peer_heartbeat",
                                      "cpu", "api_call"):
            self._baseline_samples = min(n + 1, 10000)

    def _activity_summary(self) -> dict[str, Any]:
        return {
            "interaction_density": round(
                self._window.density(SignalSource.INTERACTION, 120), 2),
            "burst_score": round(self._window.burst_score(), 2),
            "entities_tracked": len(self._entities),
            "signals_last_minute": len(self._window.get_recent(60)),
            "baseline_cpu": round(self._baseline.get("cpu", 0.0), 3),
        }

    @staticmethod
    def _classify_source(signal_type: str) -> SignalSource:
        keystroke_types = {"keystroke", "keypress", "keyboard", "mouse", "click", "scroll"}
        command_types = {"command", "shell", "exec", "cli"}
        resource_types = {"cpu", "memory", "disk", "process", "io"}
        network_types = {"peer_heartbeat", "api_call", "http", "ws", "lan", "p2p"}
        temporal_types = {"session_start", "session_end", "idle", "wake", "sleep"}
        behavioral_types = {"error", "vocabulary", "pattern", "preference", "workflow"}

        st = signal_type.lower()
        if st in keystroke_types:
            return SignalSource.INTERACTION
        if st in command_types:
            return SignalSource.BEHAVIORAL
        if st in resource_types:
            return SignalSource.RESOURCE
        if st in network_types:
            return SignalSource.NETWORK
        if st in temporal_types:
            return SignalSource.TEMPORAL
        return SignalSource.INTERACTION  # default


# ── Singleton ──

PRESENCE_SENSOR: PresenceSensor = None  # type: ignore


def get_presence_sensor() -> PresenceSensor:
    global PRESENCE_SENSOR
    if PRESENCE_SENSOR is None:
        PRESENCE_SENSOR = PresenceSensor()
    return PRESENCE_SENSOR
