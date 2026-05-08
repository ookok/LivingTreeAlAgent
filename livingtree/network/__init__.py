"""Network Layer — P2P node discovery, NAT traversal, reputation, encrypted channels,
spatial perception, presence detection, biometric signatures, site acceleration,
Scinet v2.0 intelligent proxy (RL Bandit + GNN Topology + Federated + QUIC + Cache)."""

from .site_accelerator import SiteAccelerator, get_accelerator
from .domain_ip_pool import DomainIPPool, DomainIP, DomainEntry
from .scinet_service import ScinetService, ScinetStatus, get_scinet

# Scinet v2.0 Modules
from .scinet_engine import ScinetEngine, ScinetEngineStatus, get_scinet_engine
from .scinet_quic import QuicTunnel, ProtocolObfuscator, get_quic_tunnel
from .scinet_bandit import BanditRouter, RequestContext, ArmState, get_bandit_router
from .scinet_federated import FederatedLearner, FederatedModel, FederatedAggregator, get_federated_learner
from .scinet_topology import TopologyOptimizer, TopoNode, TopoEdge, get_topology
from .scinet_cache import SemanticCache, CacheEntry, DeltaCompressor, get_semantic_cache
from .scinet_webtransport import WebTransportServer, WTSession, get_webtransport_server
from .scinet_vllm import VLLMTrafficEngine, TrafficPatternGenerator, SemanticContentSplitter, get_vllm_engine
from .scinet_swarm import SwarmNetwork, SplitModel, SwarmConsensus, RegionalHub, get_swarm_network, get_regional_hub

# Relay registry & config sync
from .relay_registry import RelayRegistry, RelayServer, RelayList, get_relay_registry
from .config_sync import ConfigSyncer, ConfigPackage, get_config_syncer
from .p2p_node import get_p2p_node

# Original network
from .node import Node, NodeInfo
from .discovery import Discovery, PeerInfo
from .nat_traverse import NATTraverser
from .reputation import Reputation
from .encrypted_channel import EncryptedChannel, EncryptedMessage
from .offline_mode import DualMode, SyncQueueItem

# Spatial perception (RuView-inspired)
from .presence_sensor import (
    PresenceSensor, PresenceEntity, SignalEvent, SignalSource,
    EntityType, ActivityLevel, GhostDetection, PresenceReport,
    get_presence_sensor, PRESENCE_SENSOR,
)
from .spatial_awareness import (
    SpatialAwareness, SpatialNode, SpatialEdge, RoomModel,
    ZoneType, Proximity, TriangulationResult,
    get_spatial_awareness, SPATIAL_AWARENESS,
)
from .biometric_signature import (
    BiometricRegistry, BiometricProfile, KeystrokeProfile,
    CommandVocabulary, TemporalRhythm, ErrorSignature,
    LanguageFingerprint, IdentityConfidence,
    get_biometric_registry, BIOMETRIC_REGISTRY,
)
from .p2p_presence import (
    P2PPresence, PresenceShare, PresenceFusion, FusedObservation,
    DriftDetector, DriftAlert, DriftSeverity, SharePriority,
    get_p2p_presence, P2P_PRESENCE,
)

__all__ = [
    # Relay & config sync (v2.3)
    "RelayRegistry", "RelayServer", "RelayList", "get_relay_registry",
    "ConfigSyncer", "ConfigPackage", "get_config_syncer",
    "get_p2p_node",
    # Original
    "Node", "NodeInfo", "Discovery", "PeerInfo", "NATTraverser",
    "Reputation", "EncryptedChannel", "EncryptedMessage", "DualMode", "SyncQueueItem",
    # Presence Sensor
    "PresenceSensor", "PresenceEntity", "SignalEvent", "SignalSource",
    "EntityType", "ActivityLevel", "GhostDetection", "PresenceReport",
    "get_presence_sensor", "PRESENCE_SENSOR",
    # Spatial Awareness
    "SpatialAwareness", "SpatialNode", "SpatialEdge", "RoomModel",
    "ZoneType", "Proximity", "TriangulationResult",
    "get_spatial_awareness", "SPATIAL_AWARENESS",
    # Biometric Signature
    "BiometricRegistry", "BiometricProfile", "KeystrokeProfile",
    "CommandVocabulary", "TemporalRhythm", "ErrorSignature",
    "LanguageFingerprint", "IdentityConfidence",
    "get_biometric_registry", "BIOMETRIC_REGISTRY",
    # P2P Presence
    "P2PPresence", "PresenceShare", "PresenceFusion", "FusedObservation",
    "DriftDetector", "DriftAlert", "DriftSeverity", "SharePriority",
    "get_p2p_presence", "P2P_PRESENCE",
    # Scinet v2.0
    "ScinetEngine", "ScinetEngineStatus", "get_scinet_engine",
    "QuicTunnel", "ProtocolObfuscator", "get_quic_tunnel",
    "BanditRouter", "RequestContext", "ArmState", "get_bandit_router",
    "FederatedLearner", "FederatedModel", "FederatedAggregator", "get_federated_learner",
    "TopologyOptimizer", "TopoNode", "TopoEdge", "get_topology",
    "SemanticCache", "CacheEntry", "DeltaCompressor", "get_semantic_cache",
    "WebTransportServer", "WTSession", "get_webtransport_server",
    "VLLMTrafficEngine", "TrafficPatternGenerator", "SemanticContentSplitter", "get_vllm_engine",
    "SwarmNetwork", "SplitModel", "SwarmConsensus", "RegionalHub", "get_swarm_network", "get_regional_hub",
]
