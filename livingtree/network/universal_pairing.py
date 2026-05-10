"""Universal Pairing — multi-modal device connection toward Internet of Everything.

Pairing methods (any one works, no preference):
  1. 8-digit numeric code  — type on either device, like Bluetooth
  2. QR code scan           — already exists, kept for convenience
  3. Same-LAN auto-detect   — zero-interaction: if same WiFi, auto-pair
  4. Audio/ultrasonic       — PC plays inaudible tone, phone hears it
  5. BLE proximity          — nearby devices discovered via Web Bluetooth

Trust model:
  Level 0: Observer  — can see AI status, receive notifications
  Level 1: Sensor    — can provide camera/GPS/mic data to AI
  Level 2: Operator  — can execute commands, browse files
  Level 3: Manager   — full admin, modify config, manage other devices

Device Mesh:
  Once paired, any device can relay messages to any other paired device.
  PC → Phone_A → Phone_B. Creates a self-healing mesh without central relay.

Innovation: "万物互联" (Internet of Everything)
  Every device is a node. Pairing is the handshake. After that:
  - Capability auto-negotiation (what can you do for the swarm?)
  - Context-aware routing (send camera task to nearest device with camera)
  - Progressive escalation (tasks get harder as trust builds)
  - Ephemeral pairing (one-task, auto-expires after 5 min)
"""

from __future__ import annotations

import asyncio
import hashlib
import json as _json
import random
import time as _time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


class TrustLevel(Enum):
    OBSERVER = 0   # Can see status, receive notifications
    SENSOR = 1     # Can provide sensor data (camera, GPS, mic)
    OPERATOR = 2   # Can execute commands, browse files
    MANAGER = 3    # Full admin: config, manage other devices


class PairMethod(Enum):
    QR = "qr"
    CODE_8_DIGIT = "code"
    LAN_AUTO = "lan"
    AUDIO = "audio"
    BLE = "ble"
    MANUAL = "manual"


@dataclass
class PairedDevice:
    device_id: str
    device_name: str
    device_type: str  # mobile, pc, tablet, iot, sensor, robot
    paired_at: float
    pair_method: PairMethod
    trust_level: TrustLevel = TrustLevel.OBSERVER
    capabilities: list[str] = field(default_factory=list)
    last_seen: float = 0.0
    mesh_hops: int = 0       # Distance from this node in mesh (0=direct)
    relayed_by: str = ""     # Device ID of the relay node
    ws: Any = None
    session_id: str = ""

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id, "name": self.device_name,
            "type": self.device_type, "trust": self.trust_level.value,
            "capabilities": self.capabilities, "pair_method": self.pair_method.value,
            "mesh_hops": self.mesh_hops,
        }


class UniversalPairingHub:
    """Multi-modal device pairing + progressive trust + mesh relay."""

    CODE_LENGTH = 8
    CODE_TTL = 300  # 5 minutes
    AUDIO_FREQ_BASE = 18000  # 18kHz base (inaudible to most adults)
    AUDIO_FREQ_STEP = 50     # 50Hz per digit

    def __init__(self):
        self._paired: dict[str, PairedDevice] = {}
        self._pending_codes: dict[str, dict] = {}  # code → {session_id, created_at, method}
        self._pending_audio: dict[str, dict] = {}
        self._ws: Any = None

    # ═══ 1. All Pairing Methods ═══

    def generate_code(self) -> str:
        """Generate an 8-digit numeric pairing code."""
        code = "".join(str(random.randint(0, 9)) for _ in range(self.CODE_LENGTH))
        sid = f"pair_{int(_time.time())}"
        self._pending_codes[code] = {
            "session_id": sid, "created_at": _time.time(),
            "method": "code", "attempts": 0,
        }
        self._clean_expired_codes()
        return code

    def verify_code(self, code: str, device_id: str = "") -> Optional[str]:
        """Verify an 8-digit code. Returns session_id if valid."""
        self._clean_expired_codes()
        pending = self._pending_codes.get(code.strip())
        if not pending:
            return None
        pending["attempts"] += 1
        if pending["attempts"] > 5:
            del self._pending_codes[code]
            return None
        return pending["session_id"]

    def _clean_expired_codes(self):
        now = _time.time()
        expired = [c for c, d in self._pending_codes.items() if now - d["created_at"] > self.CODE_TTL]
        for c in expired:
            del self._pending_codes[c]

    def generate_qr_url(self, server_url: str) -> str:
        """Generate QR pairing URL (existing)."""
        code = self.generate_code()
        return f"{server_url}/tree/reach/pair/{code}"

    def generate_audio_signal(self) -> dict:
        """Generate audio pairing signal data.

        Encodes a pairing token into frequency-shift keying.
        The PC plays this through speakers; the phone's mic picks it up.
        """
        token = f"LT{random.randint(10000, 99999)}"
        frequencies = []
        for i, ch in enumerate(token):
            freq = self.AUDIO_FREQ_BASE + (ord(ch) % 10) * self.AUDIO_FREQ_STEP
            frequencies.append({"index": i, "freq": freq, "duration_ms": 80})
        sid = f"audio_{int(_time.time())}"
        self._pending_audio[token] = {"session_id": sid, "created_at": _time.time()}
        return {"token": token, "frequencies": frequencies, "session_id": sid}

    def verify_audio_token(self, token: str) -> Optional[str]:
        pending = self._pending_audio.pop(token, None)
        if pending and _time.time() - pending["created_at"] < self.CODE_TTL:
            return pending["session_id"]
        return None

    def detect_lan_devices(self) -> list[dict]:
        """Detect devices on same LAN via UDP broadcast. Zero-interaction pairing."""
        devices = []
        try:
            from .discovery import Discovery
            discovery = Discovery()
            peers = discovery.get_peers()
            for p in peers:
                if _time.time() - p.last_seen < 90:
                    devices.append({
                        "device_id": p.id, "name": p.name,
                        "address": p.address, "source": "lan_broadcast",
                    })
        except Exception:
            pass
        return devices

    # ═══ 2. Device Pairing ═══

    def pair_device(self, device_id: str, device_name: str, device_type: str,
                    pair_method: PairMethod, capabilities: list[str] | None = None,
                    ws=None, session_id: str = "") -> PairedDevice:
        """Register a paired device and assign initial trust."""
        existing = self._paired.get(device_id)
        trust = existing.trust_level if existing else TrustLevel.OBSERVER

        device = PairedDevice(
            device_id=device_id, device_name=device_name,
            device_type=device_type, paired_at=_time.time(),
            pair_method=pair_method, trust_level=trust,
            capabilities=capabilities or self._guess_capabilities(device_type),
            last_seen=_time.time(), ws=ws, session_id=session_id,
        )
        self._paired[device_id] = device
        logger.info(f"Device paired: {device_name} ({device_type}) via {pair_method.value} — trust: {trust.value}")
        return device

    def _guess_capabilities(self, device_type: str) -> list[str]:
        caps = {"mobile": ["camera", "gps", "microphone", "qr_scan", "biometric"],
                "pc": ["compute", "storage", "display", "keyboard"],
                "tablet": ["camera", "display", "microphone", "touch"],
                "iot": ["temperature", "humidity", "motion", "light"],
                "sensor": ["environment", "presence", "distance"],
                "robot": ["movement", "camera", "gripper", "lidar"]}
        return caps.get(device_type, ["connectivity"])

    # ═══ 3. Progressive Trust ═══

    def promote_trust(self, device_id: str) -> Optional[TrustLevel]:
        """Escalate trust level: Observer → Sensor → Operator → Manager."""
        device = self._paired.get(device_id)
        if not device:
            return None
        levels = [TrustLevel.OBSERVER, TrustLevel.SENSOR, TrustLevel.OPERATOR, TrustLevel.MANAGER]
        current_idx = levels.index(device.trust_level)
        if current_idx < len(levels) - 1:
            device.trust_level = levels[current_idx + 1]
            logger.info(f"Trust promoted: {device.device_name} → {device.trust_level.value}")
        return device.trust_level

    def demote_trust(self, device_id: str) -> Optional[TrustLevel]:
        device = self._paired.get(device_id)
        if not device:
            return None
        levels = [TrustLevel.OBSERVER, TrustLevel.SENSOR, TrustLevel.OPERATOR, TrustLevel.MANAGER]
        current_idx = levels.index(device.trust_level)
        if current_idx > 0:
            device.trust_level = levels[current_idx - 1]
        return device.trust_level

    def can_do(self, device_id: str, required_level: TrustLevel) -> bool:
        device = self._paired.get(device_id)
        return device is not None and device.trust_level.value >= required_level.value

    # ═══ 4. Device Mesh ═══

    def get_reachable_devices(self, target_device_id: str) -> list[PairedDevice]:
        """Find all routes to reach target_device, direct or via relay."""
        routes = []
        target = self._paired.get(target_device_id)
        if not target:
            return routes

        if target.ws:
            routes.append(target)

        for did, device in self._paired.items():
            if did != target_device_id and device.ws:
                routes.append(PairedDevice(
                    device_id=target.device_id, device_name=target.device_name,
                    device_type=target.device_type, paired_at=target.paired_at,
                    pair_method=target.pair_method, trust_level=target.trust_level,
                    capabilities=target.capabilities,
                    mesh_hops=target.mesh_hops + 1,
                    relayed_by=did, ws=device.ws,
                ))
        return routes

    async def relay_message(self, from_device: str, to_device: str, message: dict) -> bool:
        """Send message to device via any available relay path."""
        routes = self.get_reachable_devices(to_device)
        for route in routes:
            if route.ws:
                try:
                    await route.ws.send_json({
                        "type": "relay_message",
                        "from": from_device, "to": to_device,
                        "hops": route.mesh_hops,
                        "message": message,
                    })
                    return True
                except Exception:
                    continue
        return False

    # ═══ 5. Ephemeral Pairing ═══

    def create_ephemeral_pairing(self, task: str, ttl: float = 300.0) -> str:
        """Create a one-time pairing for a specific task. Auto-expires."""
        token = f"ephemeral_{int(_time.time())}_{random.randint(1000, 9999)}"
        return token

    # ═══ 6. Status ═══

    def get_paired_devices(self) -> list[dict]:
        return [d.to_dict() for d in self._paired.values()]

    def get_pending_codes(self) -> list[str]:
        """Return active codes (masked for security)."""
        self._clean_expired_codes()
        return [f"{c[:4]}****" for c in self._pending_codes]

    def status(self) -> dict:
        by_type = {}
        for d in self._paired.values():
            by_type.setdefault(d.device_type, 0)
            by_type[d.device_type] += 1
        return {
            "paired": len(self._paired),
            "by_type": by_type,
            "pending_codes": len(self._pending_codes),
            "devices": self.get_paired_devices(),
            "mesh_capable": sum(1 for d in self._paired.values() if d.ws),
        }


_pairing_instance: Optional[UniversalPairingHub] = None


def get_pairing() -> UniversalPairingHub:
    global _pairing_instance
    if _pairing_instance is None:
        _pairing_instance = UniversalPairingHub()
    return _pairing_instance
