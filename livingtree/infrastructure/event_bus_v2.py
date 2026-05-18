from __future__ import annotations

import asyncio
import fnmatch
import time
import uuid
from collections import defaultdict, deque
from functools import wraps
from threading import Lock
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

from loguru import logger
from pydantic import BaseModel, Field, ValidationError, field_validator

from livingtree.infrastructure.event_bus import EventBus as _EventBusBase  # type: ignore[import-untyped]

# ============================================================================
# Organ Constants — 12-organ biological architecture
# ============================================================================

ORGAN_CEREBRUM: str = "cerebrum"
ORGAN_CORTEX: str = "cortex"
ORGAN_HEART: str = "heart"
ORGAN_LUNGS: str = "lungs"
ORGAN_LIVER: str = "liver"
ORGAN_KIDNEY: str = "kidney"
ORGAN_STOMACH: str = "stomach"
ORGAN_SPLEEN: str = "spleen"
ORGAN_SKIN: str = "skin"
ORGAN_EYE: str = "eye"
ORGAN_EAR: str = "ear"
ORGAN_PANCREAS: str = "pancreas"
ORGAN_SYSTEM: str = "system"
ORGAN_WILDCARD: str = "*"

ALL_ORGANS: Tuple[str, ...] = (
    ORGAN_CEREBRUM,
    ORGAN_CORTEX,
    ORGAN_HEART,
    ORGAN_LUNGS,
    ORGAN_LIVER,
    ORGAN_KIDNEY,
    ORGAN_STOMACH,
    ORGAN_SPLEEN,
    ORGAN_SKIN,
    ORGAN_EYE,
    ORGAN_EAR,
    ORGAN_PANCREAS,
    ORGAN_SYSTEM,
)

ORGAN_LABELS: Dict[str, str] = {
    ORGAN_CEREBRUM: "Cerebrum",
    ORGAN_CORTEX: "Cortex",
    ORGAN_HEART: "Heart",
    ORGAN_LUNGS: "Lungs",
    ORGAN_LIVER: "Liver",
    ORGAN_KIDNEY: "Kidney",
    ORGAN_STOMACH: "Stomach",
    ORGAN_SPLEEN: "Spleen",
    ORGAN_SKIN: "Skin",
    ORGAN_EYE: "Eye",
    ORGAN_EAR: "Ear",
    ORGAN_PANCREAS: "Pancreas",
    ORGAN_SYSTEM: "System",
}

# ============================================================================
# Event Type Constants — system events + organ-specific events
# ============================================================================

# System events
EVENT_SYSTEM_STARTUP: str = "system.startup"
EVENT_SYSTEM_SHUTDOWN: str = "system.shutdown"
EVENT_SYSTEM_HEARTBEAT: str = "system.heartbeat"
EVENT_SYSTEM_ERROR: str = "system.error"
EVENT_SYSTEM_WARNING: str = "system.warning"
EVENT_SYSTEM_METRIC: str = "system.metric"
EVENT_SYSTEM_CONFIG_CHANGE: str = "system.config_change"
EVENT_SYSTEM_LIFECYCLE: str = "system.lifecycle"
EVENT_SYSTEM_EMERGENCE: str = "system.emergence"

# Cerebrum — AI routing, decision making
EVENT_CEREBRUM_DECISION: str = "cerebrum.decision"
EVENT_CEREBRUM_ROUTE: str = "cerebrum.route"
EVENT_CEREBRUM_THOUGHT: str = "cerebrum.thought"
EVENT_CEREBRUM_CLASSIFY: str = "cerebrum.classify"
EVENT_CEREBRUM_CONTEXT_COMPRESS: str = "cerebrum.context_compress"
EVENT_CEREBRUM_MODEL_SELECT: str = "cerebrum.model_select"

# Cortex — perception, admin, visualization
EVENT_CORTEX_PERCEIVE: str = "cortex.perceive"
EVENT_CORTEX_VISUALIZE: str = "cortex.visualize"
EVENT_CORTEX_ADMIN: str = "cortex.admin"
EVENT_CORTEX_DASHBOARD: str = "cortex.dashboard"
EVENT_CORTEX_EMERGENCE_DETECT: str = "cortex.emergence_detect"

# Heart — core engine, lifecycle
EVENT_HEART_BEAT: str = "heart.beat"
EVENT_HEART_PULSE: str = "heart.pulse"
EVENT_HEART_HEALTH: str = "heart.health"
EVENT_HEART_START: str = "heart.start"
EVENT_HEART_STOP: str = "heart.stop"

# Lungs — channels, network, I/O
EVENT_LUNGS_INHALE: str = "lungs.inhale"
EVENT_LUNGS_EXHALE: str = "lungs.exhale"
EVENT_LUNGS_MESSAGE: str = "lungs.message"
EVENT_LUNGS_BRIDGE: str = "lungs.bridge"
EVENT_LUNGS_CONNECT: str = "lungs.connect"
EVENT_LUNGS_DISCONNECT: str = "lungs.disconnect"

# Liver — quality guard, filtering
EVENT_LIVER_FILTER: str = "liver.filter"
EVENT_LIVER_QUALITY: str = "liver.quality"
EVENT_LIVER_GUARD: str = "liver.guard"
EVENT_LIVER_VALIDATE: str = "liver.validate"

# Kidney — processing, execution framework
EVENT_KIDNEY_PROCESS: str = "kidney.process"
EVENT_KIDNEY_EXECUTE: str = "kidney.execute"
EVENT_KIDNEY_TOOLBOX: str = "kidney.toolbox"
EVENT_KIDNEY_PIPELINE: str = "kidney.pipeline"

# Stomach — knowledge, digestion
EVENT_STOMACH_DIGEST: str = "stomach.digest"
EVENT_STOMACH_KNOWLEDGE: str = "stomach.knowledge"
EVENT_STOMACH_INGEST: str = "stomach.ingest"
EVENT_STOMACH_LINEAGE: str = "stomach.lineage"
EVENT_STOMACH_PARSE: str = "stomach.parse"

# Spleen — economy, resources
EVENT_SPLEEN_ALLOCATE: str = "spleen.allocate"
EVENT_SPLEEN_ECONOMY: str = "spleen.economy"
EVENT_SPLEEN_BUDGET: str = "spleen.budget"
EVENT_SPLEEN_TOKEN: str = "spleen.token"

# Skin — security, boundary
EVENT_SKIN_DEFEND: str = "skin.defend"
EVENT_SKIN_AUTH: str = "skin.auth"
EVENT_SKIN_ENCRYPT: str = "skin.encrypt"
EVENT_SKIN_SECRET: str = "skin.secret"
EVENT_SKIN_SANITIZE: str = "skin.sanitize"

# Eye — vision, video search
EVENT_EYE_SEE: str = "eye.see"
EVENT_EYE_SEARCH: str = "eye.search"
EVENT_EYE_CAPTURE: str = "eye.capture"
EVENT_EYE_SCREENSHOT: str = "eye.screenshot"

# Ear — audio, voice, speech
EVENT_EAR_HEAR: str = "ear.hear"
EVENT_EAR_SPEAK: str = "ear.speak"
EVENT_EAR_LISTEN: str = "ear.listen"
EVENT_EAR_CALL: str = "ear.call"
EVENT_EAR_SYNTHESIZE: str = "ear.synthesize"

# Pancreas — cell management, swarm
EVENT_PANCREAS_CELL: str = "pancreas.cell"
EVENT_PANCREAS_SWARM: str = "pancreas.swarm"
EVENT_PANCREAS_SYNC: str = "pancreas.sync"
EVENT_PANCREAS_FRAGMENT: str = "pancreas.fragment"

# Wildcard
EVENT_WILDCARD: str = "*"

# ============================================================================
# LivingEvent — typed Pydantic BaseModel (not dataclass)
# ============================================================================

class LivingEvent(BaseModel):
    """Typed event schema for the 12-organ architecture.

    All events flowing through the bus MUST be instances of this model.
    Schema validation is enforced on construction and on publish_typed().
    """

    model_config = {"extra": "forbid", "validate_assignment": True}

    event_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique event identifier (UUID4 string)",
    )
    event_type: str = Field(
        ...,
        description="Event type using dot-notation (e.g. 'cerebrum.decision', 'system.error')",
    )
    source_organ: str = Field(
        ...,
        description="Source organ — one of the 12 organs or 'system'",
    )
    timestamp: float = Field(
        default_factory=time.time,
        description="Unix timestamp when the event was created",
    )
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary event payload",
    )
    priority: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Priority 0 (low) to 3 (critical)",
    )
    correlation_id: Optional[str] = Field(
        default=None,
        description="Optional correlation ID for tracing across organs in a request chain",
    )

    @field_validator("source_organ")
    @classmethod
    def _validate_source_organ(cls, v: str) -> str:
        if v not in ALL_ORGANS:
            raise ValueError(
                f"source_organ must be one of {sorted(ALL_ORGANS)}, got '{v}'"
            )
        return v

    @field_validator("priority")
    @classmethod
    def _validate_priority(cls, v: int) -> int:
        if not 0 <= v <= 3:
            raise ValueError(f"priority must be 0-3, got {v}")
        return v

    @classmethod
    def create(
        cls,
        event_type: str,
        source_organ: str,
        data: Optional[Dict[str, Any]] = None,
        priority: int = 0,
        correlation_id: Optional[str] = None,
        event_id: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> LivingEvent:
        """Factory method for convenient event creation."""
        kwargs: Dict[str, Any] = {
            "event_type": event_type,
            "source_organ": source_organ,
            "data": data or {},
            "priority": priority,
            "correlation_id": correlation_id,
        }
        if event_id is not None:
            kwargs["event_id"] = event_id
        if timestamp is not None:
            kwargs["timestamp"] = timestamp
        return cls(**kwargs)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize event to a plain dictionary (for legacy consumers)."""
        return self.model_dump()


# ============================================================================
# EventFilter — glob pattern matching on event_type, organ, priority
# ============================================================================

class EventFilter:
    """Filter for matching LivingEvent instances with glob + field constraints.

    Usage::

        f = EventFilter(event_pattern="cerebrum.*", priority_min=1)
        bus.subscribe_filtered(f, my_handler)

    All filter fields are AND-ed together.  ``None`` / default values mean
    "match anything".
    """

    __slots__ = (
        "_event_pattern",
        "_source_organ",
        "_priority_min",
        "_priority_max",
        "_correlation_id",
        "_data_fields",
    )

    def __init__(
        self,
        event_pattern: str = EVENT_WILDCARD,
        source_organ: Optional[str] = None,
        priority_min: int = 0,
        priority_max: int = 3,
        correlation_id: Optional[str] = None,
        data_fields: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._event_pattern: str = event_pattern
        self._source_organ: Optional[str] = source_organ
        self._priority_min: int = priority_min
        self._priority_max: int = priority_max
        self._correlation_id: Optional[str] = correlation_id
        self._data_fields: Dict[str, Any] = data_fields or {}

    @property
    def event_pattern(self) -> str:
        return self._event_pattern

    @property
    def source_organ(self) -> Optional[str]:
        return self._source_organ

    @property
    def priority_min(self) -> int:
        return self._priority_min

    @property
    def priority_max(self) -> int:
        return self._priority_max

    @property
    def correlation_id(self) -> Optional[str]:
        return self._correlation_id

    def matches(self, event: LivingEvent) -> bool:
        """Return True if *event* satisfies every constraint in this filter."""
        if self._event_pattern != EVENT_WILDCARD:
            if not fnmatch.fnmatch(event.event_type, self._event_pattern):
                return False

        if self._source_organ is not None and self._source_organ != ORGAN_WILDCARD:
            if event.source_organ != self._source_organ:
                return False

        if event.priority < self._priority_min:
            return False
        if event.priority > self._priority_max:
            return False

        if self._correlation_id is not None and event.correlation_id != self._correlation_id:
            return False

        for key, value in self._data_fields.items():
            if event.data.get(key) != value:
                return False

        return True

    def __repr__(self) -> str:
        parts: List[str] = [f"pattern={self._event_pattern!r}"]
        if self._source_organ:
            parts.append(f"organ={self._source_organ!r}")
        if self._priority_min > 0:
            parts.append(f"pri>={self._priority_min}")
        if self._priority_max < 3:
            parts.append(f"pri<={self._priority_max}")
        if self._correlation_id:
            parts.append(f"corr={self._correlation_id!r}")
        return f"EventFilter({', '.join(parts)})"


# ============================================================================
# EventBusV2 — enhanced event bus with typed events, filters, organ tracing
# ============================================================================

Handler = Callable[[LivingEvent], Any]
AsyncHandler = Callable[[LivingEvent], Coroutine[Any, Any, Any]]


class EventBusV2(_EventBusBase):
    """Enhanced event bus extending the existing one (v1) with:

    * Typed ``LivingEvent`` schema validation via ``publish_typed()``
    * Filtered subscriptions via ``subscribe_filtered()`` / ``EventFilter``
    * Organ-scoped shorthand: ``organ_subscribe()``, ``get_organ_events()``
    * Cross-organ request tracing via ``correlation_trace()``
    * Ring buffer of 10,000 events (global) + per-organ ring buffers
    * Thread-safe singleton: ``get_event_bus_v2()``

    Backward-compatible with v1 via ``get_event_bus()`` (aliased to v2).
    """

    _instance: Optional[EventBusV2] = None
    _singleton_lock: Lock = Lock()

    DEFAULT_RING_SIZE: int = 10000
    ORGAN_RING_SIZE: int = 5000

    def __new__(cls, *args: Any, **kwargs: Any) -> EventBusV2:  # type: ignore[misc]
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self, ring_buffer_size: int = DEFAULT_RING_SIZE) -> None:
        if getattr(self, "_initialized", False):
            return

        super().__init__()

        self._initialized: bool = True
        self._ring_size: int = ring_buffer_size

        self._lock: Lock = Lock()
        self._subscribers: Dict[str, List[Tuple[Optional[EventFilter], Handler]]] = (
            defaultdict(list)
        )
        self._event_history: deque[LivingEvent] = deque(maxlen=ring_buffer_size)
        self._organ_history: Dict[str, deque[LivingEvent]] = defaultdict(
            lambda: deque(maxlen=self.ORGAN_RING_SIZE)
        )

        self._published_count: int = 0

        logger.info(
            "EventBusV2 initialized | ring_buffer={} | organs={}",
            ring_buffer_size,
            len(ALL_ORGANS),
        )

    # ------------------------------------------------------------------
    # Core publish / subscribe
    # ------------------------------------------------------------------

    def publish_typed(self, event: LivingEvent) -> str:
        """Publish a ``LivingEvent`` with schema validation.

        Dict inputs are coerced through the Pydantic model so validation
        errors are raised before the event reaches any subscriber.

        Returns the event's ``event_id`` (useful for correlation tracking).
        """
        if isinstance(event, dict):
            event = LivingEvent(**event)
        elif not isinstance(event, LivingEvent):
            raise TypeError(
                f"publish_typed expects LivingEvent or dict, got {type(event).__name__}"
            )

        with self._lock:
            self._event_history.append(event)
            self._organ_history[event.source_organ].append(event)
            self._published_count += 1

        matched: int = 0
        candidates = self._subscribers.get(event.event_type, []) + self._subscribers.get(
            EVENT_WILDCARD, []
        )

        loop: Optional[asyncio.AbstractEventLoop] = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        for filt, handler in candidates:
            if filt is not None and not filt.matches(event):
                continue
            matched += 1
            try:
                if loop is not None and asyncio.iscoroutinefunction(handler):
                    loop.create_task(handler(event))
                else:
                    handler(event)
            except Exception:
                logger.opt(exception=True).warning(
                    "EventBusV2 handler failed | event={} | filter={}",
                    event.event_type,
                    filt,
                )

        logger.bind(event_type=event.event_type, matched=matched).trace(
            "Published typed event {event_id}", event_id=event.event_id
        )

        return event.event_id

    def publish(
        self,
        event_type: str,
        source_organ: str = ORGAN_SYSTEM,
        data: Optional[Dict[str, Any]] = None,
        priority: int = 0,
        correlation_id: Optional[str] = None,
    ) -> str:
        """Backward-compatible shorthand: publish a typed event from primitives."""
        return self.publish_typed(
            LivingEvent.create(
                event_type=event_type,
                source_organ=source_organ,
                data=data or {},
                priority=priority,
                correlation_id=correlation_id,
            )
        )

    def subscribe(self, event_type: str, handler: Handler, filt: Optional[EventFilter] = None) -> None:
        """Subscribe *handler* to *event_type*, optionally with a filter."""
        with self._lock:
            self._subscribers[event_type].append((filt, handler))
        logger.debug("Subscribed | event_type={} | filter={}", event_type, filt)

    def unsubscribe(self, event_type: str, handler: Handler) -> bool:
        """Remove *handler* from *event_type* subscribers.  Returns True if found."""
        with self._lock:
            entries = self._subscribers.get(event_type, [])
            initial = len(entries)
            self._subscribers[event_type] = [
                (f, h) for f, h in entries if h is not handler
            ]
            removed = initial - len(self._subscribers[event_type])
            if not self._subscribers[event_type]:
                del self._subscribers[event_type]
            return removed > 0

    def subscribe_filtered(self, filt: EventFilter, handler: Handler) -> None:
        """Subscribe *handler* to any event matching *filt*."""
        self.subscribe(EVENT_WILDCARD, handler, filt)

    # ------------------------------------------------------------------
    # Organ helpers
    # ------------------------------------------------------------------

    def organ_subscribe(
        self, organ_name: str, event_pattern: str, handler: Handler
    ) -> None:
        """Shorthand: subscribe to events from *organ_name* matching *event_pattern*.

        Equivalent to ``subscribe_filtered(EventFilter(event_pattern, org), handler)``.
        """
        filt = EventFilter(event_pattern=event_pattern, source_organ=organ_name)
        self.subscribe_filtered(filt, handler)
        logger.debug("Organ subscribe | organ={} | pattern={}", organ_name, event_pattern)

    def get_organ_events(self, organ_name: str, limit: int = 100) -> List[LivingEvent]:
        """Return the most recent *limit* events from *organ_name*."""
        dq = self._organ_history.get(organ_name)
        if not dq:
            return []
        return list(dq)[-limit:]

    # ------------------------------------------------------------------
    # Correlation tracing
    # ------------------------------------------------------------------

    def correlation_trace(self, correlation_id: str) -> List[LivingEvent]:
        """Trace all events sharing the same *correlation_id* across all organs.

        Events are returned in chronological order (by timestamp, then insertion).
        """
        trace: List[LivingEvent] = []
        with self._lock:
            for event in self._event_history:
                if event.correlation_id == correlation_id:
                    trace.append(event)
        trace.sort(key=lambda e: e.timestamp)
        return trace

    def start_correlation(self, correlation_id: Optional[str] = None) -> str:
        """Generate (or use) a correlation_id for request-chain tracing."""
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())
        self.publish_typed(
            LivingEvent.create(
                EVENT_SYSTEM_LIFECYCLE,
                source_organ=ORGAN_SYSTEM,
                data={"phase": "correlation_start"},
                correlation_id=correlation_id,
            )
        )
        return correlation_id

    def end_correlation(self, correlation_id: str) -> None:
        """Mark the end of a correlation chain."""
        self.publish_typed(
            LivingEvent.create(
                EVENT_SYSTEM_LIFECYCLE,
                source_organ=ORGAN_SYSTEM,
                data={"phase": "correlation_end"},
                correlation_id=correlation_id,
            )
        )

    # ------------------------------------------------------------------
    # History / introspection
    # ------------------------------------------------------------------

    def get_event_history(self, limit: int = 100) -> List[LivingEvent]:
        """Return the most recent *limit* events from the global ring buffer."""
        return list(self._event_history)[-limit:]

    def get_event_count(self) -> int:
        """Total number of events published since bus initialization."""
        return self._published_count

    def get_ring_size(self) -> int:
        return self._ring_size

    def get_subscriber_count(self) -> int:
        """Total number of unique subscriber entries across all event types."""
        with self._lock:
            return sum(len(v) for v in self._subscribers.values())

    def clear_history(self) -> None:
        """Purge all in-memory event history (ring buffers are reset)."""
        with self._lock:
            self._event_history.clear()
            self._organ_history.clear()
        logger.info("EventBusV2 history cleared")

    # ------------------------------------------------------------------
    # Backward-compatible aliases (v1 surface)
    # ------------------------------------------------------------------

    def emit(self, event_type: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> str:
        """Alias for ``publish()`` — matches common v1 ``emit()`` signature."""
        return self.publish(event_type=event_type, data=data, **kwargs)

    def on(self, event_type: str, handler: Handler) -> None:
        """Alias for ``subscribe()`` — matches common v1 ``on()`` signature."""
        self.subscribe(event_type, handler)

    def off(self, event_type: str, handler: Handler) -> bool:
        """Alias for ``unsubscribe()`` — matches common v1 ``off()`` signature."""
        return self.unsubscribe(event_type, handler)

    def clear(self) -> None:
        """Alias for ``clear_history()``."""
        self.clear_history()

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"EventBusV2(events={self._published_count}, "
            f"ring={len(self._event_history)}/{self._ring_size}, "
            f"subs={self.get_subscriber_count()})"
        )

    def __len__(self) -> int:
        return len(self._event_history)

    def __contains__(self, event_id: str) -> bool:
        with self._lock:
            return any(e.event_id == event_id for e in self._event_history)


# ============================================================================
# Singleton accessors
# ============================================================================

def get_event_bus_v2() -> EventBusV2:
    """Return the global EventBusV2 singleton instance."""
    return EventBusV2()


def get_event_bus() -> EventBusV2:
    """Backward-compatible accessor — returns the EventBusV2 singleton.

    All v1 call-sites that call ``get_event_bus()`` will transparently
    receive the V2 bus, which provides the full v1 API surface via aliases.
    """
    return get_event_bus_v2()
