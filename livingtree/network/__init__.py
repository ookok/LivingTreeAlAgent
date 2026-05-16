"""Network Layer — P2P node discovery, NAT traversal, reputation, encrypted channels,
spatial perception, presence detection, biometric signatures, site acceleration."""

from .site_accelerator import SiteAccelerator, get_accelerator
from .domain_ip_pool import DomainIPPool, DomainIP, DomainEntry

from .relay_registry import RelayRegistry, RelayServer, RelayList, get_relay_registry
from .config_sync import ConfigSyncer, ConfigPackage, get_config_syncer
from .p2p_node import get_p2p_node
from .distributed_consciousness import ConsciousnessFragment, DistributedSelf, get_distributed_self

from .node import Node, NodeInfo
from .discovery import Discovery, PeerInfo
from .nat_traverse import NATTraverser
from .reputation import Reputation
from .encrypted_channel import EncryptedChannel, EncryptedMessage
from .offline_mode import DualMode, SyncQueueItem

from .presence_sensor import (PresenceSensor, PresenceEntity, SignalEvent, SignalSource,
    EntityType, ActivityLevel, GhostDetection, PresenceReport,
    get_presence_sensor, PRESENCE_SENSOR)
from .spatial_awareness import (SpatialAwareness, SpatialNode, SpatialEdge, RoomModel,
    ZoneType, Proximity, TriangulationResult,
    get_spatial_awareness, SPATIAL_AWARENESS)
from .biometric_signature import (BiometricRegistry, BiometricProfile, KeystrokeProfile,
    CommandVocabulary, TemporalRhythm, ErrorSignature,
    LanguageFingerprint, IdentityConfidence,
    get_biometric_registry, BIOMETRIC_REGISTRY)
from .p2p_presence import (P2PPresence, PresenceShare, PresenceFusion, FusedObservation,
    DriftDetector, DriftAlert, DriftSeverity, SharePriority,
    get_p2p_presence, P2P_PRESENCE)

__all__ = [
    "SiteAccelerator", "get_accelerator",
    "DomainIPPool", "DomainIP", "DomainEntry",
    "RelayRegistry", "RelayServer", "RelayList", "get_relay_registry",
    "ConfigSyncer", "ConfigPackage", "get_config_syncer",
    "get_p2p_node",
    "ConsciousnessFragment", "DistributedSelf", "get_distributed_self",
    "Node", "NodeInfo", "Discovery", "PeerInfo", "NATTraverser",
    "Reputation", "EncryptedChannel", "EncryptedMessage", "DualMode", "SyncQueueItem",
    "PresenceSensor", "PresenceEntity", "SignalEvent", "SignalSource",
    "EntityType", "ActivityLevel", "GhostDetection", "PresenceReport",
    "get_presence_sensor", "PRESENCE_SENSOR",
    "SpatialAwareness", "SpatialNode", "SpatialEdge", "RoomModel",
    "ZoneType", "Proximity", "TriangulationResult",
    "get_spatial_awareness", "SPATIAL_AWARENESS",
    "BiometricRegistry", "BiometricProfile", "KeystrokeProfile",
    "CommandVocabulary", "TemporalRhythm", "ErrorSignature",
    "LanguageFingerprint", "IdentityConfidence",
    "get_biometric_registry", "BIOMETRIC_REGISTRY",
    "P2PPresence", "PresenceShare", "PresenceFusion", "FusedObservation",
    "DriftDetector", "DriftAlert", "DriftSeverity", "SharePriority",
    "get_p2p_presence", "P2P_PRESENCE",
]
