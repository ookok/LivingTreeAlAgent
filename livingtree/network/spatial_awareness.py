"""SpatialAwareness — Abstract spatial mapping and topology for LivingTree.

Models the "space" around a LivingTree node as an abstract topology graph,
not requiring GPS or physical sensors. The space is defined by connectivity
relationships: what peers are nearby, what rooms/zones exist, how signals
propagate through the network topology.

Analogy (RuView): Room model from CSI signal patterns + Fresnel zones.
LivingTree: "Rooms" are logical zones inferred from P2P topology, signal
propagation delays, and entity co-occurrence patterns.

Key Concepts:
- SpatialNode: a location in the abstract space (device, room, building)
- SpatialEdge: proximity/connectivity relationship between nodes
- RoomModel: logical zone grouping entities with similar spatial properties
- PropagationModel: how signals/information flows through the space
- TopologyMap: complete graph of the perceived spatial environment

Innovation: "Signal Triangulation" — cross-reference entity sightings from
multiple P2P nodes to locate entities in the abstract space grid.
"""

from __future__ import annotations

import time
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


# ── Types ──

class ZoneType(str, Enum):
    DEVICE = "device"         # A single computer/terminal
    ROOM = "room"             # A logical room (same LAN segment)
    FLOOR = "floor"           # A building floor (same router/gateway)
    BUILDING = "building"     # An entire building
    REGION = "region"         # Geographic region
    CLOUD = "cloud"           # Remote/cloud nodes
    UNKNOWN = "unknown"


class Proximity(str, Enum):
    SAME_DEVICE = "same_device"      # Co-located on one machine
    SAME_LAN = "same_lan"            # Same local network
    SAME_GATEWAY = "same_gateway"    # Behind same router
    REMOTE_LOW_LATENCY = "remote_low"  # < 50ms
    REMOTE = "remote"                # > 50ms
    UNKNOWN = "unknown"


@dataclass
class SpatialNode:
    """A node in the spatial topology graph."""
    node_id: str
    name: str
    zone_type: ZoneType = ZoneType.UNKNOWN
    zone_id: str = ""                  # Grouping zone
    proximity: Proximity = Proximity.UNKNOWN
    entities_present: list[str] = field(default_factory=list)  # entity_ids
    signal_strength: float = 1.0       # Connectivity quality 0-1
    latency_ms: float = 0.0
    last_updated: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SpatialEdge:
    """Connection between two spatial nodes."""
    source_id: str
    target_id: str
    proximity: Proximity
    latency_ms: float
    bandwidth_hint: str = ""   # "lan", "wan", "relay"
    encrypted: bool = True
    last_active: float = field(default_factory=time.time)


@dataclass
class RoomModel:
    """A logical room/zone in the abstract space."""
    zone_id: str
    zone_type: ZoneType
    name: str
    nodes: list[str] = field(default_factory=list)      # node_ids in this zone
    entities: list[str] = field(default_factory=list)   # entity_ids detected
    gateway_node: str = ""       # Node acting as gateway to this zone
    parent_zone: str = ""        # Containing zone (e.g., room→floor→building)
    density: float = 0.0         # Entity density (entities / nodes)
    last_updated: float = field(default_factory=time.time)


@dataclass
class TriangulationResult:
    """Cross-node entity triangulation result."""
    entity_id: str
    entity_name: str
    observing_nodes: list[str]      # Which nodes detect this entity
    confidence: float
    estimated_zone: ZoneType
    consensus_score: float          # How much nodes agree (0-1)
    conflicting_nodes: list[str]    # Nodes that disagree


# ── Main Engine ──

class SpatialAwareness:
    """Spatial topology and entity location mapping engine.

    Builds and maintains an abstract spatial model of the LivingTree node
    network, tracking where entities (users, peers) are located in the
    logical space based on P2P topology and signal propagation patterns.
    """

    def __init__(self):
        self._nodes: dict[str, SpatialNode] = {}
        self._edges: list[SpatialEdge] = []
        self._rooms: dict[str, RoomModel] = {}
        self._entity_locations: dict[str, str] = {}  # entity_id → node_id
        self._triangulation_history: deque[TriangulationResult] = deque(maxlen=200)
        self._propagation_cache: dict[str, list[str]] = {}  # node_id → reachable nodes

    # ── Node registration ──

    def register_node(self, node_id: str, name: str = "",
                      zone_type: ZoneType = ZoneType.UNKNOWN,
                      proximity: Proximity = Proximity.UNKNOWN,
                      latency_ms: float = 0.0, **meta) -> SpatialNode:
        """Register or update a spatial node."""
        now = time.time()
        if node_id in self._nodes:
            node = self._nodes[node_id]
            node.name = name or node.name
            node.zone_type = zone_type
            node.proximity = proximity
            node.latency_ms = latency_ms
            node.last_updated = now
            node.metadata.update(meta)
        else:
            node = SpatialNode(node_id=node_id, name=name or node_id[:12],
                               zone_type=zone_type, proximity=proximity,
                               latency_ms=latency_ms, metadata=dict(meta))
            self._nodes[node_id] = node
            logger.info(f"SpatialAwareness: registered node '{node.name}' "
                        f"({zone_type.value}, {proximity.value})")
        self._invalidate_propagation_cache()
        return node

    def register_self(self, p2p_node=None) -> SpatialNode:
        """Register the local LivingTree node."""
        import platform
        node_id = getattr(p2p_node, 'node_id', 'local') if p2p_node else 'local'
        name = getattr(p2p_node, 'name', platform.node()) if p2p_node else platform.node()
        latency = 0.0
        return self.register_node(node_id, name, ZoneType.DEVICE,
                                  Proximity.SAME_DEVICE, latency,
                                  hostname=platform.node(),
                                  platform=platform.system())

    def register_peer(self, peer_id: str, peer_name: str = "",
                      latency_ms: float = 10.0, same_lan: bool = True) -> SpatialNode:
        """Register a peer P2P node."""
        proximity = Proximity.SAME_LAN if same_lan else Proximity.REMOTE
        zone = ZoneType.ROOM if same_lan else ZoneType.CLOUD
        node = self.register_node(peer_id, peer_name, zone, proximity, latency_ms)

        # Create bidirectional edge
        local_id = self._get_local_id()
        self._add_edge(local_id, peer_id, proximity, latency_ms)
        return node

    # ── Edge management ──

    def _add_edge(self, src: str, tgt: str, proximity: Proximity,
                  latency_ms: float, bandwidth: str = "") -> SpatialEdge:
        # Check for existing edge
        for edge in self._edges:
            if (edge.source_id == src and edge.target_id == tgt) or \
               (edge.source_id == tgt and edge.target_id == src):
                edge.proximity = proximity
                edge.latency_ms = latency_ms
                edge.last_active = time.time()
                return edge

        edge = SpatialEdge(source_id=src, target_id=tgt,
                           proximity=proximity, latency_ms=latency_ms,
                           bandwidth_hint=bandwidth or self._bandwidth_hint(proximity))
        self._edges.append(edge)
        self._invalidate_propagation_cache()
        return edge

    # ── Entity location ──

    def locate_entity(self, entity_id: str, node_id: str,
                      confidence: float = 0.8) -> None:
        """Record that an entity was detected at a specific spatial node."""
        old_location = self._entity_locations.get(entity_id)
        self._entity_locations[entity_id] = node_id

        # Update the node's entity list
        if node_id in self._nodes:
            node = self._nodes[node_id]
            if entity_id not in node.entities_present:
                node.entities_present.append(entity_id)

        # If entity moved, log the movement
        if old_location and old_location != node_id:
            logger.debug(f"SpatialAwareness: entity '{entity_id}' moved "
                         f"from {old_location} to {node_id}")

        # Update room entity lists
        for room in self._rooms.values():
            if node_id in room.nodes:
                if entity_id not in room.entities:
                    room.entities.append(entity_id)
                room.density = len(room.entities) / max(len(room.nodes), 1)
                room.last_updated = time.time()

    def get_entity_location(self, entity_id: str) -> tuple[str | None, SpatialNode | None]:
        """Get where an entity is currently located."""
        node_id = self._entity_locations.get(entity_id)
        if node_id:
            return node_id, self._nodes.get(node_id)
        return None, None

    def get_entities_at(self, node_id: str) -> list[str]:
        """Get all entities currently at a node."""
        return self._nodes[node_id].entities_present if node_id in self._nodes else []

    # ── Room/Zone management ──

    def define_room(self, zone_id: str, name: str, zone_type: ZoneType,
                    nodes: list[str] | None = None,
                    parent_zone: str = "") -> RoomModel:
        """Define a logical room/zone."""
        if zone_id in self._rooms:
            room = self._rooms[zone_id]
            room.name = name
            room.zone_type = zone_type
        else:
            room = RoomModel(zone_id=zone_id, zone_type=zone_type, name=name)
            self._rooms[zone_id] = room

        if nodes:
            room.nodes = nodes
            room.density = len(room.entities) / max(len(nodes), 1)
        if parent_zone:
            room.parent_zone = parent_zone

        # Auto-assign nodes to zone if they match criteria
        for node_id, node in self._nodes.items():
            if node.zone_type == zone_type and node_id not in room.nodes:
                room.nodes.append(node_id)

        logger.info(f"SpatialAwareness: defined room '{name}' "
                    f"({zone_type.value}, {len(room.nodes)} nodes)")
        return room

    def auto_discover_rooms(self) -> list[RoomModel]:
        """Automatically discover logical zones from P2P topology.
        
        Groups nodes by: same LAN → ROOM, same gateway → FLOOR,
        remote → CLOUD.
        """
        new_rooms = []

        # Group by proximity
        by_proximity: dict[Proximity, list[str]] = defaultdict(list)
        for node_id, node in self._nodes.items():
            by_proximity[node.proximity].append(node_id)

        for proximity, node_ids in by_proximity.items():
            if len(node_ids) < 1:
                continue
            zone_type = {
                Proximity.SAME_DEVICE: ZoneType.DEVICE,
                Proximity.SAME_LAN: ZoneType.ROOM,
                Proximity.SAME_GATEWAY: ZoneType.FLOOR,
                Proximity.REMOTE: ZoneType.CLOUD,
                Proximity.REMOTE_LOW_LATENCY: ZoneType.BUILDING,
            }.get(proximity, ZoneType.UNKNOWN)

            room = self.define_room(
                f"auto_{zone_type.value}", f"Auto-{zone_type.value.title()}",
                zone_type, nodes=node_ids,
            )
            new_rooms.append(room)

        return new_rooms

    # ── Triangulation (P2P cross-node entity location) ──

    def triangulate(self, entity_id: str, entity_name: str = "",
                    sightings: dict[str, float] | None = None) -> TriangulationResult:
        """Cross-reference entity sightings from multiple nodes to determine
        the most likely location.

        sightings: {node_id: confidence} from each observing node.

        Innovation: multi-node consensus with conflict detection.
        """
        if not sightings:
            # Use current entity locations from registered nodes
            sightings = {}
            for node_id, node in self._nodes.items():
                if entity_id in node.entities_present:
                    sightings[node_id] = 0.8  # default confidence

        if not sightings:
            return TriangulationResult(
                entity_id=entity_id, entity_name=entity_name,
                observing_nodes=[], confidence=0.0,
                estimated_zone=ZoneType.UNKNOWN, consensus_score=0.0,
                conflicting_nodes=[],
            )

        observing = list(sightings.keys())
        confidences = list(sightings.values())

        # Compute consensus
        avg_conf = sum(confidences) / len(confidences)
        # Higher consensus when more nodes agree on same proximity
        proximity_votes: dict[Proximity, float] = defaultdict(float)
        for node_id, conf in sightings.items():
            if node_id in self._nodes:
                prox = self._nodes[node_id].proximity
                proximity_votes[prox] += conf

        total_votes = sum(proximity_votes.values())
        if total_votes > 0:
            best_proximity = max(proximity_votes, key=proximity_votes.get)
            consensus = proximity_votes[best_proximity] / total_votes
        else:
            consensus = 0.0
            best_proximity = Proximity.UNKNOWN

        # Detect conflicting nodes (nodes with different proximity)
        conflicting = [nid for nid in observing
                       if nid in self._nodes
                       and self._nodes[nid].proximity != best_proximity]

        # Map proximity to zone
        zone_map = {
            Proximity.SAME_DEVICE: ZoneType.DEVICE,
            Proximity.SAME_LAN: ZoneType.ROOM,
            Proximity.SAME_GATEWAY: ZoneType.FLOOR,
            Proximity.REMOTE_LOW_LATENCY: ZoneType.BUILDING,
            Proximity.REMOTE: ZoneType.CLOUD,
        }

        result = TriangulationResult(
            entity_id=entity_id,
            entity_name=entity_name,
            observing_nodes=observing,
            confidence=round(avg_conf * consensus, 3),
            estimated_zone=zone_map.get(best_proximity, ZoneType.UNKNOWN),
            consensus_score=round(consensus, 3),
            conflicting_nodes=conflicting,
        )
        self._triangulation_history.append(result)

        # Update entity location to best-guess node
        if observing:
            best_node = max(sightings, key=lambda k: sightings[k])
            self.locate_entity(entity_id, best_node, confidence=result.confidence)

        return result

    # ── Spatial queries ──

    def nearest_nodes(self, node_id: str, max_distance: int = 3) -> list[SpatialNode]:
        """Find nodes within N hops of the given node."""
        reachable = self._get_reachable_nodes(node_id, max_distance)
        return [self._nodes[n] for n in reachable if n in self._nodes]

    def entities_in_zone(self, zone_id: str) -> list[str]:
        """Get all entities in a given zone."""
        room = self._rooms.get(zone_id)
        return room.entities if room else []

    def nodes_in_zone(self, zone_id: str) -> list[str]:
        """Get all nodes in a given zone."""
        room = self._rooms.get(zone_id)
        return room.nodes if room else []

    def get_spatial_report(self) -> dict[str, Any]:
        """Get comprehensive spatial state report."""
        return {
            "nodes": len(self._nodes),
            "edges": len(self._edges),
            "rooms": len(self._rooms),
            "entities_located": len(self._entity_locations),
            "room_details": {
                rid: {
                    "name": r.name,
                    "type": r.zone_type.value,
                    "nodes": len(r.nodes),
                    "entities": len(r.entities),
                    "density": round(r.density, 3),
                }
                for rid, r in self._rooms.items()
            },
            "recent_triangulations": [
                {
                    "entity": t.entity_name,
                    "nodes": len(t.observing_nodes),
                    "consensus": t.consensus_score,
                    "zone": t.estimated_zone.value,
                }
                for t in list(self._triangulation_history)[-5:]
            ],
        }

    # ── Private helpers ──

    def _get_local_id(self) -> str:
        """Get the local node's ID."""
        for node_id, node in self._nodes.items():
            if node.proximity == Proximity.SAME_DEVICE:
                return node_id
        return "local"

    def _get_reachable_nodes(self, node_id: str, max_hops: int) -> list[str]:
        """BFS to find reachable nodes within max_hops."""
        if node_id not in self._nodes:
            return []

        cache_key = f"{node_id}:{max_hops}"
        if cache_key in self._propagation_cache:
            return self._propagation_cache[cache_key]

        # Build adjacency list
        adj: dict[str, list[str]] = defaultdict(list)
        for edge in self._edges:
            adj[edge.source_id].append(edge.target_id)
            adj[edge.target_id].append(edge.source_id)

        visited: set[str] = {node_id}
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])
        while queue:
            current, hops = queue.popleft()
            if hops >= max_hops:
                continue
            for neighbor in adj.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, hops + 1))

        reachable = list(visited - {node_id})
        self._propagation_cache[cache_key] = reachable
        return reachable

    def _invalidate_propagation_cache(self) -> None:
        self._propagation_cache.clear()

    @staticmethod
    def _bandwidth_hint(proximity: Proximity) -> str:
        return {
            Proximity.SAME_DEVICE: "local",
            Proximity.SAME_LAN: "lan",
            Proximity.SAME_GATEWAY: "wan",
            Proximity.REMOTE_LOW_LATENCY: "wan_fast",
            Proximity.REMOTE: "wan",
        }.get(proximity, "unknown")


# ── Singleton ──

SPATIAL_AWARENESS: SpatialAwareness = None  # type: ignore


def get_spatial_awareness() -> SpatialAwareness:
    global SPATIAL_AWARENESS
    if SPATIAL_AWARENESS is None:
        SPATIAL_AWARENESS = SpatialAwareness()
    return SPATIAL_AWARENESS
