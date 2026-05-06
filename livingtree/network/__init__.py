"""Network Layer — P2P node discovery, NAT traversal, reputation, encrypted channels,
spatial perception, presence detection, biometric signatures."""

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
]
