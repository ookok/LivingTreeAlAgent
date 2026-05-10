"""Reach Gateway — Cross-device AI sensory extension network.

The AI is the brain. Mobile devices are its eyes, ears, and hands.
When the AI needs something it can't do (scan, photo, GPS, NFC, voice),
it reaches through to connected devices and asks the human operator.

Design philosophy:
- AI is the primary agent — it decides what sensory input it needs
- Human is the AI's "hand" — follows simple, clear instructions
- Mobile is the AI's "sensory organ" — camera, GPS, mic, scanner
- Zero friction — no app install, no login, no setup

Architecture:
    LivingTree Server (AI Brain)
           │
    ┌──────┴──────┐
    │ ReachGateway │ ← WebSocket hub for all devices
    └──────┬──────┘
           │
    ┌──────┼──────────┐
    ▼      ▼           ▼
  [PC]  [Mobile]   [Tablet]
  Browser  PWA       Web
"""

from __future__ import annotations

import asyncio
import hashlib
import json as _json
import secrets
import time as _time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from loguru import logger


class DeviceType(Enum):
    PC = "pc"
    MOBILE = "mobile"
    TABLET = "tablet"
    UNKNOWN = "unknown"


class SensorType(Enum):
    CAMERA_PHOTO = "camera_photo"
    CAMERA_SCAN = "camera_scan"
    QR_CODE = "qr_code"
    GPS_LOCATION = "gps_location"
    MICROPHONE = "microphone"
    NFC_TAG = "nfc_tag"
    ACCELEROMETER = "accelerometer"
    COMPASS = "compass"
    BIOMETRIC = "biometric"
    SCREENSHOT = "screenshot"
    CLIPBOARD = "clipboard"
    TOUCH_SIGNATURE = "touch_signature"


class TaskPriority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


@dataclass
class DeviceInfo:
    device_id: str
    device_type: DeviceType
    device_name: str = ""
    user_agent: str = ""
    capabilities: list[str] = field(default_factory=list)
    connected_at: float = 0.0
    last_seen: float = 0.0
    session_id: str = ""
    ws: Any = None

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "device_type": self.device_type.value,
            "device_name": self.device_name,
            "capabilities": self.capabilities,
            "connected_at": self.connected_at,
            "session_id": self.session_id,
        }


@dataclass
class SensorRequest:
    """AI asks a device to perform a sensory action."""
    request_id: str
    sensor_type: SensorType
    title: str
    instruction: str
    priority: TaskPriority = TaskPriority.NORMAL
    target_device_id: str = ""
    target_device_type: str = "mobile"
    timeout_seconds: float = 120.0
    required: bool = True
    context: str = ""
    hints: list[str] = field(default_factory=list)
    created_at: float = 0.0
    expires_at: float = 0.0
    status: str = "pending"
    result: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "type": "sensor_request",
            "sensor_type": self.sensor_type.value,
            "title": self.title,
            "instruction": self.instruction,
            "priority": self.priority.value,
            "timeout_seconds": self.timeout_seconds,
            "required": self.required,
            "context": self.context,
            "hints": self.hints,
            "created_at": self.created_at,
            "status": self.status,
        }


@dataclass
class TaskCard:
    """A minimal interactive task pushed to a mobile device."""
    card_id: str
    title: str
    description: str
    action_type: str  # "photo", "scan", "location", "confirm", "input", "choice"
    action_prompt: str = ""
    choices: list[str] = field(default_factory=list)
    callback_event: str = ""
    expires_in_seconds: float = 300.0
    status: str = "pending"
    result: Any = None
    created_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "card_id": self.card_id,
            "type": "task_card",
            "title": self.title,
            "description": self.description,
            "action_type": self.action_type,
            "action_prompt": self.action_prompt,
            "choices": self.choices,
            "callback_event": self.callback_event,
            "expires_in_seconds": self.expires_in_seconds,
            "created_at": self.created_at,
        }


class ReachGateway:
    """Cross-device WebSocket hub. AI reaches through to any connected device.

    Singleton — one gateway per server instance.
    """

    _instance: Optional[ReachGateway] = None

    def __init__(self):
        self._devices: dict[str, DeviceInfo] = {}
        self._sessions: dict[str, set[str]] = {}
        self._pending_requests: dict[str, SensorRequest] = {}
        self._pending_cards: dict[str, TaskCard] = {}
        self._response_futures: dict[str, asyncio.Future] = {}
        self._on_device_connected: list[Callable] = []
        self._on_sensor_response: list[Callable] = []
        self._hub: Any = None

    @classmethod
    def get(cls) -> ReachGateway:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_hub(self, hub):
        self._hub = hub

    @property
    def hub(self):
        return self._hub

    # ── Device Lifecycle ──

    def generate_pairing_code(self) -> str:
        """Generate a short human-readable pairing code."""
        return secrets.token_hex(3)[:6].upper()

    def generate_pairing_qr(self, server_url: str) -> str:
        """Generate a QR code data URL for device pairing."""
        code = self.generate_pairing_code()
        pairing_url = f"{server_url}/tree/reach/pair/{code}"
        self._sessions[code] = set()
        return pairing_url

    async def register_device(self, ws, device_type_str: str, device_name: str = "",
                               session_id: str = "", user_agent: str = "") -> DeviceInfo:
        device_id = hashlib.sha256(f"{_time.time()}{secrets.token_hex(8)}".encode()).hexdigest()[:16]
        try:
            dt = DeviceType(device_type_str)
        except ValueError:
            dt = DeviceType.UNKNOWN

        caps = self._detect_capabilities(dt, user_agent)
        device = DeviceInfo(
            device_id=device_id,
            device_type=dt,
            device_name=device_name or f"{dt.value}-{device_id[:4]}",
            user_agent=user_agent,
            capabilities=caps,
            connected_at=_time.time(),
            last_seen=_time.time(),
            session_id=session_id,
            ws=ws,
        )

        self._devices[device_id] = device
        if session_id:
            self._sessions.setdefault(session_id, set()).add(device_id)

        logger.info(
            f"Reach: device '{device.device_name}' ({dt.value}) connected — "
            f"caps: {', '.join(caps)}"
        )

        for cb in self._on_device_connected:
            try:
                cb(device)
            except Exception:
                pass

        return device

    def unregister_device(self, device_id: str):
        device = self._devices.pop(device_id, None)
        if device and device.session_id:
            s = self._sessions.get(device.session_id)
            if s:
                s.discard(device_id)
        logger.info(f"Reach: device '{getattr(device, 'device_name', device_id)}' disconnected")

    def _detect_capabilities(self, device_type: DeviceType, ua: str) -> list[str]:
        caps = []
        ua_lower = ua.lower()
        if device_type == DeviceType.MOBILE:
            if "iphone" in ua_lower or "android" in ua_lower:
                caps.extend(["camera_photo", "camera_scan", "qr_code", "gps_location", "microphone", "touch_signature"])
        elif device_type == DeviceType.PC:
            caps.extend(["clipboard", "screenshot"])
        return caps

    # ── Device Queries ──

    def get_devices(self, device_type: Optional[DeviceType] = None) -> list[DeviceInfo]:
        if device_type:
            return [d for d in self._devices.values() if d.device_type == device_type]
        return list(self._devices.values())

    def get_mobile_devices(self) -> list[DeviceInfo]:
        return self.get_devices(DeviceType.MOBILE)

    def has_mobile(self) -> bool:
        return any(d.device_type == DeviceType.MOBILE for d in self._devices.values())

    def get_session_devices(self, session_id: str) -> list[DeviceInfo]:
        ids = self._sessions.get(session_id, set())
        return [self._devices[did] for did in ids if did in self._devices]

    def get_device(self, device_id: str) -> Optional[DeviceInfo]:
        return self._devices.get(device_id)

    # ── AI → Device: Push sensor requests ──

    async def request_sensor(
        self,
        sensor_type: SensorType,
        title: str,
        instruction: str,
        target_device_type: str = "mobile",
        target_device_id: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: float = 120.0,
        context: str = "",
        required: bool = True,
        hints: list[str] | None = None,
    ) -> Optional[dict]:
        """AI requests a sensory action from a device. Blocks until response or timeout.

        Returns the device's response data, or None if timed out/no device available.
        """
        request_id = f"req_{int(_time.time() * 1000)}_{secrets.token_hex(3)}"
        req = SensorRequest(
            request_id=request_id,
            sensor_type=sensor_type,
            title=title,
            instruction=instruction,
            priority=priority,
            target_device_id=target_device_id,
            target_device_type=target_device_type,
            timeout_seconds=timeout,
            required=required,
            context=context,
            hints=hints or [],
            created_at=_time.time(),
            expires_at=_time.time() + timeout,
        )

        target = None
        if target_device_id:
            target = self._devices.get(target_device_id)
        else:
            dt = DeviceType(target_device_type) if target_device_type in ("mobile", "pc", "tablet") else DeviceType.MOBILE
            candidates = self.get_devices(dt)
            target = candidates[0] if candidates else None

        if not target or not target.ws:
            logger.warning(f"Reach: no device available for {sensor_type.value}")
            if not required:
                return {"status": "skipped", "reason": "no_device"}
            return None

        self._pending_requests[request_id] = req

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._response_futures[request_id] = future

        try:
            await target.ws.send_json(req.to_dict())
            logger.info(f"Reach: sent {sensor_type.value} request to '{target.device_name}' — {title}")
            result = await asyncio.wait_for(future, timeout=timeout)
            req.status = "completed"
            req.result = result
            return result
        except asyncio.TimeoutError:
            req.status = "timeout"
            logger.warning(f"Reach: {sensor_type.value} request timed out ({timeout}s)")
            return None
        except Exception as e:
            req.status = "failed"
            logger.warning(f"Reach: {sensor_type.value} request failed: {e}")
            return None
        finally:
            self._response_futures.pop(request_id, None)

    async def push_task_card(self, card: TaskCard) -> bool:
        """Push an interactive task card to all connected mobile devices."""
        self._pending_cards[card.card_id] = card
        delivered = False
        for device in self.get_mobile_devices():
            if device.ws:
                try:
                    await device.ws.send_json(card.to_dict())
                    delivered = True
                except Exception as e:
                    logger.debug(f"Reach: card delivery to {device.device_name} failed: {e}")
        return delivered

    # ── Device → AI: Receive sensor responses ──

    async def receive_response(self, device_id: str, data: dict):
        """Handle sensor response from a device."""
        request_id = data.get("request_id", "")
        device = self._devices.get(device_id)
        if device:
            device.last_seen = _time.time()

        future = self._response_futures.get(request_id)
        if future and not future.done():
            future.set_result(data)
            return

        req = self._pending_requests.get(request_id)
        for cb in self._on_sensor_response:
            try:
                cb(req, data, device_id)
            except Exception:
                pass

    def on_device_connected(self, callback: Callable):
        self._on_device_connected.append(callback)

    def on_sensor_response(self, callback: Callable):
        self._on_sensor_response.append(callback)

    # ── Status ──

    def status(self) -> dict:
        return {
            "total_devices": len(self._devices),
            "mobile_devices": len(self.get_mobile_devices()),
            "pc_devices": len(self.get_devices(DeviceType.PC)),
            "pending_requests": len(self._pending_requests),
            "devices": [d.to_dict() for d in self._devices.values()],
        }


def get_reach_gateway() -> ReachGateway:
    return ReachGateway.get()
