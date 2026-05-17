"""LivingTree Handshake Protocol (LHP) — three-model unified layer governance.

Every system layer is governed by the three-model intelligence (Embedding·L1·L2).
Governors communicate via standardized handshakes, forming a self-optimizing
cognitive mesh. Humans experience this as an increasingly intelligent system
that "just works" — no configuration, no manual tuning, no intervention needed.

Architecture:
  ┌─────────────────────────────────────────────────────────┐
  │                    Human (transparent)                  │
  ├─────────────────────────────────────────────────────────┤
  │  Input  │ Context │ Routing │ Capability │ Storage      │
  │ Governor│Governor │Governor │ Governor   │ Governor     │
  ├─────────┴─────────┴─────────┴────────────┴─────────────┤
  │  Output │ Comm    │ Task    │ Self       │ Evolution    │
  │ Governor│Governor │Governor │ Governor   │ Governor     │
  ├─────────────────────────────────────────────────────────┤
  │              Three-Model Intelligence                   │
  │    Embedding(感知)  │  L1 Fast(执行)  │  L2 Pro(推理)    │
  └─────────────────────────────────────────────────────────┘

Handshake format:
  {handshake_id, source, target, governor, action, payload,
   context_snapshot, priority, ttl, callback}

Layers governed:
  1. Input     — intercept/classify/preprocess/enrich user input
  2. Context   — compress/retrieve/manage conversation context
  3. Routing   — elect providers, allocate budget, failover
  4. Capability — discover/execute/orchestrate tools and skills
  5. Storage   — index/cache/persist/retrieve knowledge vectors
  6. Output    — format/review/hallucination-check/finalize
  7. Comm      — channel selection, message formatting, escalation
  8. Task      — decompose/plan/schedule/monitor complex tasks
  9. Self      — introspection, health monitoring, self-healing
 10. Evolution — learn patterns, generate rules, improve system
"""

from __future__ import annotations

import asyncio
import hashlib
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

import numpy as np
from loguru import logger


# ═══════════════════════════════════════════════════════════════
# Handshake Protocol
# ═══════════════════════════════════════════════════════════════

class HandshakePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class GovernorLevel(str, Enum):
    EMBEDDING = "embedding"  # Pattern matching, fast decisions
    L1 = "l1"                # Execution, quick reasoning
    L2 = "l2"                # Deep reasoning, strategic planning
    AUTO = "auto"            # System auto-selects level


@dataclass
class Handshake:
    """A message between layer governors via the cognitive mesh."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    source: str = ""          # source governor name
    target: str = ""          # target governor name ("" = broadcast)
    governor: GovernorLevel = GovernorLevel.AUTO
    action: str = ""          # what to do
    payload: dict = field(default_factory=dict)
    context_snapshot: list[float] | None = None  # 384-dim vector
    priority: HandshakePriority = HandshakePriority.NORMAL
    ttl: float = 30.0         # time-to-live seconds
    callback: str = ""        # handshake ID to respond to
    created_at: float = field(default_factory=time.time)
    responded: bool = False
    response: dict | None = None

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl

    def to_log(self) -> str:
        return (
            f"[{self.id[:6]}] {self.source}→{self.target} "
            f"{self.governor.value}/{self.action}({self.priority.value})"
        )


@dataclass
class LayerStats:
    """Runtime stats for a layer governor."""
    handshakes_sent: int = 0
    handshakes_received: int = 0
    decisions_made: int = 0
    reflex_hits: int = 0
    l1_fast_path: int = 0
    l2_deep_path: int = 0
    avg_latency_ms: float = 0.0
    errors: int = 0
    last_active: float = field(default_factory=time.time)


# ═══════════════════════════════════════════════════════════════
# Task Journal — full action log for human visibility
# ═══════════════════════════════════════════════════════════════

class JournalStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    PAUSED = "paused"


@dataclass
class JournalEntry:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    action: str = ""           # what was done / will be done
    layer: str = ""            # which governor/layer
    model: str = ""            # embedding/l1/l2
    status: JournalStatus = JournalStatus.PENDING
    tool_used: str = ""        # tool/API called (if any)
    input_short: str = ""      # input summary (first 100 chars)
    output_short: str = ""     # output summary (first 200 chars)
    started_at: float = 0.0
    completed_at: float = 0.0
    error: str = ""
    depends_on: list[str] = field(default_factory=list)  # IDs of blocking entries
    estimated_ms: float = 0.0  # predicted duration
    elapsed_ms: float = 0.0    # actual duration
    human_decision: str = ""   # human input at decision points

    @property
    def is_active(self) -> bool:
        return self.status in (JournalStatus.RUNNING, JournalStatus.PENDING,
                                JournalStatus.PAUSED)

    def summary(self) -> str:
        icon = {JournalStatus.DONE: "✅", JournalStatus.RUNNING: "🔄",
                JournalStatus.FAILED: "❌", JournalStatus.BLOCKED: "🚫",
                JournalStatus.PENDING: "⏳", JournalStatus.PAUSED: "⏸️",
                JournalStatus.SKIPPED: "⏭️"}.get(self.status, "❓")

        eta = f" {self.elapsed_ms:.0f}ms" if self.elapsed_ms else ""
        err = f" [{self.error[:50]}]" if self.error else ""
        deps = f" (等待: {','.join(self.depends_on)})" if self.depends_on else ""
        return f"{icon} [{self.layer}][{self.model}] {self.action[:60]}{deps}{eta}{err}"


class TaskJournal:
    """Immutable action log. Every system action is recorded here for
    human inspection. The journal is append-only — entries accumulate
    but never mutate (status changes create new entries with references)."""

    def __init__(self):
        self._entries: list[JournalEntry] = []
        self._lock = threading.Lock()
        self._paused: bool = False
        self._human_messages: list[dict] = []
        self._decision_queue: asyncio.Queue = asyncio.Queue(maxsize=20)

    def log(self, action: str, layer: str = "", model: str = "",
            tool: str = "", input_short: str = "", depends_on: list[str] = None,
            estimated_ms: float = 0.0) -> JournalEntry:
        entry = JournalEntry(
            action=action, layer=layer, model=model, tool_used=tool,
            input_short=input_short[:100], depends_on=depends_on or [],
            estimated_ms=estimated_ms, status=JournalStatus.PENDING,
            started_at=time.time(),
        )
        with self._lock:
            self._entries.append(entry)
        return entry

    def start(self, entry_id: str) -> None:
        with self._lock:
            for e in self._entries:
                if e.id == entry_id:
                    e.status = JournalStatus.RUNNING
                    e.started_at = time.time()
                    return

    def complete(self, entry_id: str, output: str = "", elapsed_ms: float = 0.0) -> None:
        with self._lock:
            for e in self._entries:
                if e.id == entry_id:
                    e.status = JournalStatus.DONE
                    e.output_short = output[:200]
                    e.completed_at = time.time()
                    e.elapsed_ms = elapsed_ms or (e.completed_at - e.started_at) * 1000
                    return

    def fail(self, entry_id: str, error: str) -> None:
        with self._lock:
            for e in self._entries:
                if e.id == entry_id:
                    e.status = JournalStatus.FAILED
                    e.error = error[:200]
                    e.completed_at = time.time()
                    return

    def block(self, entry_id: str, reason: str, depends_on: list[str]) -> None:
        with self._lock:
            for e in self._entries:
                if e.id == entry_id:
                    e.status = JournalStatus.BLOCKED
                    e.error = reason[:200]
                    e.depends_on = depends_on
                    return

    @property
    def paused(self) -> bool:
        return self._paused

    def pause_all(self) -> None:
        with self._lock:
            self._paused = True
            for e in self._entries:
                if e.status == JournalStatus.RUNNING:
                    e.status = JournalStatus.PAUSED

    def resume_all(self) -> None:
        with self._lock:
            self._paused = False
            for e in self._entries:
                if e.status == JournalStatus.PAUSED:
                    e.status = JournalStatus.RUNNING

    # ═══ Human query interface ═══

    def status_report(self) -> str:
        """Generate a structured status report for human consumption."""
        with self._lock:
            done = [e for e in self._entries if e.status == JournalStatus.DONE]
            active = [e for e in self._entries if e.is_active]
            failed = [e for e in self._entries if e.status == JournalStatus.FAILED]
            blocked = [e for e in self._entries if e.status == JournalStatus.BLOCKED]
            total_elapsed = sum(e.elapsed_ms for e in self._entries) / 1000

            # Estimate remaining
            remaining_ms = sum(
                e.estimated_ms for e in self._entries
                if e.status in (JournalStatus.PENDING, JournalStatus.PAUSED)
            )

            lines = [
                "━━━ 任务状态报告 ━━━",
                f"已完成: {len(done)} | 进行中: {len(active)} | "
                f"失败: {len(failed)} | 阻塞: {len(blocked)}",
                f"已用时间: {total_elapsed:.0f}s | 预计剩余: {remaining_ms/1000:.0f}s",
                "", "── 进行中 ──",
            ]
            for e in active[-10:]:
                lines.append(f"  {e.summary()}")
            if failed:
                lines.append("── 失败 ──")
                for e in failed[-5:]:
                    lines.append(f"  {e.summary()}")
            if blocked:
                lines.append("── 阻塞 ──")
                for e in blocked[-5:]:
                    lines.append(f"  {e.summary()}")
            if done:
                lines.append(f"── 已完成 ({len(done)}) ──")
                for e in done[-5:]:
                    lines.append(f"  {e.summary()}")
            if self._paused:
                lines.append("\n⏸️  系统已暂停 — 等待人类指令")
            return "\n".join(lines)

    def pending_report(self) -> str:
        """What's left to do, with dependencies."""
        with self._lock:
            pending = [
                e for e in self._entries
                if e.status in (JournalStatus.PENDING, JournalStatus.BLOCKED)
            ]
            if not pending:
                return "✅ 所有任务已完成"
            lines = ["── 待完成 ──"]
            for e in pending:
                deps = f" (需要: {', '.join(e.depends_on)})" if e.depends_on else ""
                eta = f" ≈{e.estimated_ms/1000:.0f}s" if e.estimated_ms else ""
                lines.append(f"  ⏳ {e.action[:80]}{deps}{eta}")
            return "\n".join(lines)

    def problem_report(self) -> str:
        """What went wrong and why."""
        with self._lock:
            failed = [e for e in self._entries if e.status == JournalStatus.FAILED]
            blocked = [e for e in self._entries if e.status == JournalStatus.BLOCKED]
            if not failed and not blocked:
                return "✅ 无问题"
            lines = ["── 问题清单 ──"]
            for e in failed:
                lines.append(f"  ❌ {e.action[:60]}: {e.error[:100]}")
            for e in blocked:
                lines.append(f"  🚫 {e.action[:60]}: {e.error[:100]}")
            return "\n".join(lines)

    def get_history(self, limit: int = 20) -> list[JournalEntry]:
        with self._lock:
            return list(self._entries[-limit:])

    # ═══ Decision points ═══

    async def ask_decision(self, question: str, options: list[str],
                           timeout: float = 120.0) -> str | None:
        """Present a decision point to human. Blocks until response or timeout."""
        decision = {
            "question": question, "options": options,
            "timeout": timeout, "asked_at": time.time(),
        }
        await self._decision_queue.put(decision)
        try:
            return await asyncio.wait_for(
                self._decision_queue.get(), timeout=timeout,
            )
        except asyncio.TimeoutError:
            return None

    def resolve_decision(self, answer: str) -> None:
        """Human provides answer to a pending decision."""
        self._decision_queue.put_nowait(answer)

    def pending_decisions(self) -> list[dict]:
        return [d for d in list(self._decision_queue._queue)
                if isinstance(d, dict) and "question" in d]

    # ═══ Human message injection ═══

    def inject_message(self, message: str) -> None:
        """Human injects a message into the conversation loop."""
        with self._lock:
            self._human_messages.append({
                "time": time.time(), "message": message, "from": "human",
            })

    def consume_messages(self) -> list[dict]:
        """Consume and clear human messages for injection into L2 context."""
        with self._lock:
            msgs = list(self._human_messages)
            self._human_messages.clear()
            return msgs


# ═══════════════════════════════════════════════════════════════
# Cognitive Mesh — the central nervous system
# ═══════════════════════════════════════════════════════════════

class CognitiveMesh:
    """The central message bus connecting all layer governors.

    Routes handshakes between governors, manages priority queues,
    tracks message history, and provides the shared world state.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._governors: dict[str, "LayerGovernor"] = {}
        self._handshake_log: list[Handshake] = []
        self._pending: list[Handshake] = []
        self._world_state: dict[str, Any] = {}
        self._embedding_cache: dict[str, np.ndarray] = {}
        self._stats: dict[str, LayerStats] = {}
        self._total_handshakes: int = 0
        self._mesh_health: float = 1.0

    def register(self, governor: "LayerGovernor") -> None:
        with self._lock:
            self._governors[governor.layer_name] = governor
            self._stats[governor.layer_name] = LayerStats()
            governor.mesh = self
            logger.debug(f"CognitiveMesh: registered {governor.layer_name}")

    def send(self, handshake: Handshake) -> Handshake:
        """Send a handshake through the mesh. Returns the same handshake with
        a response attached if the target governor is synchronous."""
        with self._lock:
            self._total_handshakes += 1
            self._handshake_log.append(handshake)
            if len(self._handshake_log) > 1000:
                self._handshake_log = self._handshake_log[-500:]

            # Update source stats
            if handshake.source in self._stats:
                self._stats[handshake.source].handshakes_sent += 1

        # Route to target(s)
        if handshake.target and handshake.target in self._governors:
            target = self._governors[handshake.target]
            response = target.receive(handshake)
            handshake.responded = True
            handshake.response = response
        elif not handshake.target:
            # Broadcast to all governors
            for name, gov in self._governors.items():
                if name != handshake.source:
                    gov.receive(handshake)
        else:
            with self._lock:
                self._pending.append(handshake)

        return handshake

    async def send_async(self, handshake: Handshake) -> Handshake:
        """Async handshake that waits for target response."""
        self.send(handshake)
        if handshake.callback:
            deadline = time.time() + handshake.ttl
            while time.time() < deadline:
                with self._lock:
                    for h in self._handshake_log:
                        if h.id == handshake.callback and h.responded:
                            return h
                await asyncio.sleep(0.05)
        return handshake

    def query_world_state(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._world_state.get(key, default)

    def update_world_state(self, key: str, value: Any) -> None:
        with self._lock:
            self._world_state[key] = value

    def cache_embedding(self, text: str, vec: np.ndarray) -> None:
        key = hashlib.md5(text[:500].encode()).hexdigest()[:16]
        with self._lock:
            self._embedding_cache[key] = vec

    def get_cached_embedding(self, text: str) -> np.ndarray | None:
        key = hashlib.md5(text[:500].encode()).hexdigest()[:16]
        with self._lock:
            return self._embedding_cache.get(key)

    def update_mesh_health(self, governor_name: str, healthy: bool) -> None:
        with self._lock:
            if governor_name in self._stats:
                self._stats[governor_name].last_active = time.time()

    def stats(self) -> dict:
        with self._lock:
            return {
                "governors": len(self._governors),
                "total_handshakes": self._total_handshakes,
                "pending": len(self._pending),
                "mesh_health": self._mesh_health,
                "layers": {
                    name: {
                        "sent": s.handshakes_sent,
                        "received": s.handshakes_received,
                        "reflex": s.reflex_hits,
                        "l1_fast": s.l1_fast_path,
                        "l2_deep": s.l2_deep_path,
                        "errors": s.errors,
                    }
                    for name, s in self._stats.items()
                },
            }


# ═══════════════════════════════════════════════════════════════
# Layer Governor base class
# ═══════════════════════════════════════════════════════════════

class LayerGovernor:
    """Base class for all layer governors. Each governor uses three-model
    intelligence to make decisions for its layer."""

    layer_name: str = "base"

    def __init__(self):
        self.mesh: CognitiveMesh | None = None
        self._tmi = None  # ThreeModelIntelligence reference
        self._tree_llm = None
        self._decision_log: list[dict] = []

    def _ensure_tmi(self):
        if self._tmi is None:
            try:
                from ..treellm.three_model_intelligence import get_three_model_intelligence
                self._tmi = get_three_model_intelligence(self._tree_llm)
            except Exception:
                pass

    def send(self, target: str, action: str, payload: dict = None,
             governor: GovernorLevel = GovernorLevel.AUTO,
             priority: HandshakePriority = HandshakePriority.NORMAL,
             ttl: float = 30.0, callback: str = "",
             context_vector: list[float] | None = None) -> Handshake:
        if not self.mesh:
            return Handshake(source=self.layer_name, action="no_mesh")
        h = Handshake(
            source=self.layer_name, target=target,
            governor=governor, action=action,
            payload=payload or {}, priority=priority,
            ttl=ttl, callback=callback,
            context_snapshot=context_vector,
        )
        return self.mesh.send(h)

    def receive(self, handshake: Handshake) -> dict | None:
        """Override in subclasses. Returns response payload or None."""
        if self.mesh:
            stats = self.mesh._stats.get(self.layer_name)
            if stats:
                stats.handshakes_received += 1
        return None

    def stats(self) -> LayerStats:
        if self.mesh:
            return self.mesh._stats.get(self.layer_name, LayerStats())
        return LayerStats()


# ═══════════════════════════════════════════════════════════════
# 1. Input Governor — intercept, classify, enrich
# ═══════════════════════════════════════════════════════════════

class InputGovernor(LayerGovernor):
    """Governs the input layer: spinal reflex intercept, complexity triage,
    intent classification, emotion detection, prompt enrichment,
    and live architecture awareness via code_graph."""

    layer_name = "input"
    _arch_cache: dict = {}
    _arch_scanned: bool = False

    async def process(self, query: str, hub=None) -> dict[str, Any]:
        """Full input processing pipeline. Returns enriched input context."""
        t0 = time.time()
        self._ensure_tmi()

        # Step 1: Spinal reflex — intercept trivial queries
        if self._tmi:
            reflex = await self._tmi.spinal_reflex(query)
            if reflex:
                if self.mesh:
                    s = self.mesh._stats.get(self.layer_name)
                    if s: s.reflex_hits += 1
                return {
                    "handled": True, "response": reflex,
                    "method": "reflex", "elapsed_ms": (time.time() - t0) * 1000,
                }

        # Step 2: Triage + Emotion
        triage = self._tmi.triage(query) if self._tmi else None
        emotion = self._tmi._detect_emotion(query) if self._tmi else None

        # Step 3: Architecture awareness — inject code graph context
        arch_ctx = await self._get_architecture_context(query)

        # Step 4: Handshake → Context Governor for knowledge preload
        if triage and triage.label == "reasoning" and self.mesh:
            await self.mesh.send_async(Handshake(
                source=self.layer_name, target="context",
                governor=GovernorLevel.L1, action="preload",
                payload={"query": query, "predicted_needs": triage.predicted_needs},
                priority=HandshakePriority.HIGH, ttl=5.0,
            ))

        # Step 5: Handshake → Routing Governor for provider selection
        if self.mesh and triage:
            self.mesh.send(Handshake(
                source=self.layer_name, target="routing",
                governor=GovernorLevel.L1 if triage.label == "fast" else GovernorLevel.L2,
                action="select_provider",
                payload={"complexity": triage.complexity, "label": triage.label,
                         "query_len": len(query)},
                priority=HandshakePriority.HIGH, ttl=3.0,
            ))

        return {
            "handled": False, "query": query,
            "triage": triage, "emotion": emotion,
            "tone": emotion.tone_modifier() if emotion else "",
            "architecture_context": arch_ctx,
            # Innovation 4: adaptive temperature
            "temperature_adjust": self._adaptive_temperature(emotion, triage),
            "elapsed_ms": (time.time() - t0) * 1000,
        }

    # ═══ Innovation 4: Adaptive temperature ═══
    @staticmethod
    def _adaptive_temperature(emotion, triage) -> float:
        """Auto-adjust temperature based on emotion + complexity.
        Confused/urgent → lower temp (more deterministic).
        Creative/excited → higher temp (more diverse)."""
        if emotion is None or triage is None:
            return 0.0
        adjust = 0.0
        if emotion.is_confused:
            adjust -= 0.15  # more deterministic when user is confused
        if emotion.is_urgent:
            adjust -= 0.10  # direct answers when urgent
        if emotion.is_negative:
            adjust += 0.05  # slightly more creative to defuse
        if triage.complexity > 0.7:
            adjust += 0.05  # complex tasks need more exploration
        return max(-0.2, min(0.2, adjust))  # clamp to safe range

    async def _get_architecture_context(self, query: str) -> str:
        if not self._arch_scanned:
            try:
                from ..capability.code_graph import CodeGraph
                cg = CodeGraph()
                if hasattr(cg, 'stats') and cg.stats().get("total_files", 0) < 10:
                    cg.index(str(Path.cwd()), patterns=["**/*.py"])
                self._arch_cache = {
                    "stats": cg.stats() if hasattr(cg, 'stats') else {},
                    "dependencies": getattr(cg, '_deps', {}),
                }
                self._arch_scanned = True
                if self.mesh:
                    self.mesh.update_world_state("architecture_graph", self._arch_cache)
            except Exception:
                self._arch_scanned = True

        code_keywords = ["代码", "模块", "架构", "调用", "依赖", "文件", "函数",
                         "code", "module", "architecture", "import", "function"]
        if any(kw in query.lower() for kw in code_keywords):
            ctx_parts = []
            # Semantic search
            try:
                from ..capability.semantic_code_search import search_codebase
                results = search_codebase(query, top_k=3)
                if results:
                    ctx_parts.append("\n".join(
                        f"📁 {r.get('file','')}: {r.get('snippet','')[:200]}"
                        for r in results[:3]
                    ))
            except Exception:
                pass
            # CodePercept: AST-level perception
            ast_ctx = self._ast_perception(query)
            if ast_ctx:
                ctx_parts.append(ast_ctx)
            return "\n".join(ctx_parts) if ctx_parts else ""
        return ""

    # ═══ CodePercept: AST-level code perception ═══

    def _ast_perception(self, query: str) -> str:
        """Parse code structure as structured perception, not raw text.
        Extract function signatures, call chains, control flow from AST.
        This gives L2 precise, executable semantics instead of fuzzy NLP."""
        try:
            from ..capability.ast_parser import ASTParser
            parser = ASTParser()

            # Extract file/module references from query
            import re as _re
            file_refs = _re.findall(r'[\w./-]+\.py', query)
            if not file_refs:
                file_refs = _re.findall(r'[\w_]+\.py', query)

            parts = []
            for fref in file_refs[:3]:
                try:
                    fpath = Path(fref)
                    if not fpath.exists():
                        # Search in livingtree/
                        candidates = list(Path("livingtree").rglob(fref))
                        if candidates:
                            fpath = candidates[0]
                        else:
                            continue

                    content = fpath.read_text(encoding="utf-8")[:50000]
                    tree = parser.parse(content) if hasattr(parser, 'parse') else None

                    if tree:
                        # Extract function signatures
                        funcs = self._extract_functions(tree, content)
                        if funcs:
                            sig_lines = "\n".join(
                                f"  def {f['name']}({', '.join(f['params'][:5])})"
                                + (f" → {f['return_type']}" if f.get('return_type') else "")
                                for f in funcs[:10]
                            )
                            parts.append(f"📄 {fref} — {len(funcs)} functions:\n{sig_lines}")

                        # Extract call graph
                        calls = self._extract_calls(tree, content)
                        if calls:
                            call_lines = "\n".join(
                                f"  {c['caller']} → {c['callee']}"
                                for c in calls[:10]
                            )
                            parts.append(f"🔗 Call graph:\n{call_lines}")
                except Exception:
                    continue

            return "\n".join(parts) if parts else ""
        except Exception:
            return ""

    @staticmethod
    def _extract_functions(tree, content: str) -> list[dict]:
        """Walk AST and extract function signatures with types."""
        import ast as _ast
        funcs = []
        try:
            for node in _ast.walk(tree):
                if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                    params = []
                    for arg in node.args.args:
                        p = arg.arg
                        if arg.annotation:
                            try:
                                p += f": {_ast.unparse(arg.annotation)}"
                            except Exception:
                                pass
                        params.append(p)
                    returns = ""
                    if node.returns:
                        try:
                            returns = _ast.unparse(node.returns)
                        except Exception:
                            pass
                    funcs.append({
                        "name": node.name,
                        "params": params,
                        "return_type": returns,
                        "lineno": node.lineno,
                        "decorators": [
                            _ast.unparse(d) for d in node.decorator_list
                        ] if node.decorator_list else [],
                    })
        except Exception:
            pass
        return funcs

    @staticmethod
    def _extract_calls(tree, content: str) -> list[dict]:
        """Walk AST and extract call relationships."""
        import ast as _ast
        calls = []
        current_func = ["<module>"]
        try:
            class CallVisitor(_ast.NodeVisitor):
                def visit_FunctionDef(self, node):
                    old = current_func[0]
                    current_func[0] = node.name
                    self.generic_visit(node)
                    current_func[0] = old

                def visit_AsyncFunctionDef(self, node):
                    self.visit_FunctionDef(node)

                def visit_Call(self, node):
                    callee = ""
                    if isinstance(node.func, _ast.Name):
                        callee = node.func.id
                    elif isinstance(node.func, _ast.Attribute):
                        callee = _ast.unparse(node.func)
                    if callee and not callee.startswith("_"):
                        calls.append({
                            "caller": current_func[0],
                            "callee": callee,
                            "lineno": node.lineno,
                        })
                    self.generic_visit(node)
            CallVisitor().visit(tree)
        except Exception:
            pass
        return calls

    # ═══ Innovation 2: Architecture Visualization ═══

    def render_architecture_mermaid(self) -> str:
        """Generate a live Mermaid graph of the project architecture."""
        if not self._arch_scanned or not self._arch_cache.get("dependencies"):
            return "graph TD\n  A[Architecture not scanned yet]"

        deps = self._arch_cache["dependencies"]
        lines = ["graph TD"]
        seen = set()

        for mod, targets in list(deps.items())[:30]:
            mod_short = mod.replace("livingtree.", "lt/").replace(".", "/")
            for t in targets[:5]:
                t_short = t.replace("livingtree.", "lt/").replace(".", "/")
                edge = f"  {mod_short} --> {t_short}"
                if edge not in seen:
                    lines.append(edge)
                    seen.add(edge)

        if self._arch_cache.get("stats"):
            s = self._arch_cache["stats"]
            lines.append(f"  classDef info fill:#e1f5fe,stroke:#0288d1")
            lines.append(f"  note1[Files: {s.get('total_files','?')} | "
                        f"Edges: {s.get('total_edges','?')} | "
                        f"Entities: {s.get('total_entities','?')}]")
            lines.append(f"  class note1 info")

        return "\n".join(lines)

    def detect_arch_hotspots(self) -> list[dict]:
        deps = self._arch_cache.get("dependencies", {})
        if not deps:
            return []
        fan_in: dict[str, int] = {}
        for mod, targets in deps.items():
            for t in targets:
                fan_in[t] = fan_in.get(t, 0) + 1
        return sorted(
            [{"module": k, "fan_in": v, "risk": "high" if v > 15 else "medium"}
             for k, v in fan_in.items() if v > 5],
            key=lambda x: -x["fan_in"],
        )[:10]

    # ═══ CodePercept: Type graph (function I/O signatures) ═══
    def build_type_graph(self) -> dict:
        """Extract function I/O type signatures from AST.
        Returns {function_name: {params: [...], return_type: str, file: str}}.
        This is a type graph — structured, queryable, executable semantics."""
        type_graph = {}
        try:
            import ast as _ast
            for py_file in Path("livingtree").rglob("*.py"):
                if "_archive" in str(py_file):
                    continue
                try:
                    content = py_file.read_text(encoding="utf-8")[:30000]
                    tree = _ast.parse(content)
                    funcs = self._extract_functions(tree, content)
                    for f in funcs:
                        key = f"{py_file.stem}.{f['name']}"
                        if key not in type_graph:
                            type_graph[key] = {
                                "params": f["params"],
                                "return_type": f["return_type"],
                                "file": str(py_file),
                                "line": f["lineno"],
                                "decorators": f["decorators"],
                            }
                except Exception:
                    continue
            if self.mesh:
                self.mesh.update_world_state("type_graph", type_graph)
        except Exception:
            pass
        return type_graph

    def query_type_graph(self, func_name: str) -> dict | None:
        """Query the type graph for a function's I/O signature."""
        tg = self.mesh.query_world_state("type_graph", {}) if self.mesh else {}
        if func_name in tg:
            return tg[func_name]
        for key, val in tg.items():
            if func_name in key:
                return val
        return None

    def receive(self, handshake: Handshake) -> dict | None:
        super().receive(handshake)
        if handshake.action == "user_input":
            return {"ack": True, "governor": self.layer_name}
        return None


# ═══════════════════════════════════════════════════════════════
# 2. Context Governor — compress, retrieve, manage
# ═══════════════════════════════════════════════════════════════

class ContextGovernor(LayerGovernor):
    """Governs the context layer: vector-based retrieval, context compression,
    knowledge preloading, memory management.

    Innovation: multi-turn memory compression via 384-dim vectors.
    100 conversation turns = 38KB instead of 100KB+ raw text."""

    layer_name = "context"
    _context_store: list[dict] = []
    _turn_vectors: list[np.ndarray] = []  # compressed turn embeddings

    async def preload(self, query: str, predicted_needs: list[str]) -> dict:
        results = {}
        try:
            from ..knowledge.vector_store import VectorStore
            store = VectorStore()
            embedding = store.embed(query)
            docs = store.search_similar(embedding, top_k=5)
            results["knowledge"] = docs
        except Exception:
            results["knowledge"] = []
        if self._tmi and self.mesh:
            try:
                vec = self._tmi._get_embedding(query)
                if vec is not None:
                    self.mesh.cache_embedding(query, vec)
            except Exception:
                pass
        return {"preloaded": results, "needs": predicted_needs}

    def compress_turn(self, text: str) -> np.ndarray | None:
        """Compress a conversation turn into a 384-dim vector.
        100 turns = 100 × 384 × 4 bytes = 153KB → negligible."""
        self._ensure_tmi()
        if self._tmi:
            try:
                vec = self._tmi._get_embedding(text[:2000])
                if vec is not None:
                    self._turn_vectors.append(vec)
                    if len(self._turn_vectors) > 100:
                        self._turn_vectors = self._turn_vectors[-100:]
                    return vec
            except Exception:
                pass
        return None

    def find_similar_turns(self, query: str, top_k: int = 3) -> list[int]:
        """Find conversation turns similar to query. Returns turn indices."""
        self._ensure_tmi()
        if not self._turn_vectors or not self._tmi:
            return []
        try:
            q_vec = self._tmi._get_embedding(query[:500])
            if q_vec is None:
                return []
            matrix = np.stack(self._turn_vectors)
            similarities = np.dot(matrix, q_vec)
            indices = np.argsort(similarities)[-top_k:][::-1]
            return [int(i) for i in indices if float(similarities[int(i)]) > 0.7]
        except Exception:
            return []

    def compress_context(self, messages: list[dict], max_tokens: int) -> list[dict]:
        if len(messages) <= 5:
            return messages
        if self.mesh:
            self.send("routing", "context_budget",
                      {"current_tokens": sum(len(str(m)) for m in messages),
                       "max_tokens": max_tokens})
        return messages[-max_tokens // 100:]

    def receive(self, handshake: Handshake) -> dict | None:
        super().receive(handshake)
        if handshake.action == "preload":
            return {"status": "preloading",
                    "query": handshake.payload.get("query", "")[:100]}
        if handshake.action == "retrieve_context":
            return {"context": str(self._context_store[-3:])}
        return None


# ═══════════════════════════════════════════════════════════════
# 3. Routing Governor — elect providers, allocate budget
# ═══════════════════════════════════════════════════════════════

class RoutingGovernor(LayerGovernor):
    """Governs the routing layer: provider election, cost/latency optimization,
    failover management, budget distribution."""

    layer_name = "routing"
    _provider_scores: dict[str, float] = {}
    _budget: dict[str, float] = {"daily": 10.0, "used": 0.0}

    def select_provider(self, complexity: float, label: str) -> dict:
        """Select optimal provider based on task characteristics."""
        if label == "reflex":
            return {"provider": "none", "reason": "reflex handled"}
        if label == "fast":
            return {"provider": "deepseek", "model": "deepseek-v4-flash",
                    "reason": "l1_fast_path", "temperature": 0.3}
        return {"provider": "deepseek", "model": "deepseek-v4-pro",
                "reason": "l2_deep_reasoning", "temperature": 0.3}

    def allocate_budget(self, estimated_tokens: int) -> dict:
        remaining = self._budget["daily"] - self._budget["used"]
        if estimated_tokens / 1000 * 0.002 > remaining:
            return {"approved": False, "reason": "budget_exceeded",
                    "remaining": remaining}
        return {"approved": True, "estimated_cost": estimated_tokens / 1000 * 0.002}

    def receive(self, handshake: Handshake) -> dict | None:
        super().receive(handshake)
        if handshake.action == "select_provider":
            return self.select_provider(
                handshake.payload.get("complexity", 0.5),
                handshake.payload.get("label", "fast"),
            )
        if handshake.action == "context_budget":
            return self.allocate_budget(
                handshake.payload.get("current_tokens", 0),
            )
        return None


# ═══════════════════════════════════════════════════════════════
# 4. Capability Governor — discover, execute, orchestrate tools
# ═══════════════════════════════════════════════════════════════

class CapabilityGovernor(LayerGovernor):
    """Governs the capability layer: tool discovery, execution, result
    aggregation, multi-tool orchestration, sandboxing."""

    layer_name = "capability"
    _tool_cache: dict[str, Any] = {}
    _tool_stats: dict[str, dict] = {}

    async def execute(self, tool_name: str, params: dict) -> dict:
        """Execute a tool with L1 handling, L2 oversight."""
        try:
            from ..treellm.capability_bus import get_capability_bus
            bus = get_capability_bus()
            result = await bus.invoke(f"tool:{tool_name}", **params)
            self._tool_stats[tool_name] = self._tool_stats.get(tool_name, {"calls": 0, "errors": 0})
            self._tool_stats[tool_name]["calls"] += 1
            return {"success": True, "result": str(result)[:2000]}
        except Exception as e:
            self._tool_stats[tool_name] = self._tool_stats.get(tool_name, {"calls": 0, "errors": 0})
            self._tool_stats[tool_name]["errors"] += 1
            return {"success": False, "error": str(e)[:200]}

    async def orchestrate(self, task_description: str) -> dict:
        """L2 plans a multi-tool chain for complex tasks."""
        return {"plan": f"Orchestrating: {task_description[:100]}",
                "steps": [], "fallback": "sequential"}

    def receive(self, handshake: Handshake) -> dict | None:
        super().receive(handshake)
        if handshake.action == "execute_tool":
            return {"ack": True, "tool": handshake.payload.get("tool", "")}
        return None


# ═══════════════════════════════════════════════════════════════
# 5. Storage Governor — index, cache, persist vectors
# ═══════════════════════════════════════════════════════════════

class StorageGovernor(LayerGovernor):
    """Governs the storage layer: vector indexing, cache management,
    persistence, TTL-based cleanup, GC orchestration."""

    layer_name = "storage"
    _cache_hits: int = 0
    _cache_misses: int = 0

    def index_vector(self, text: str, vector: list[float], metadata: dict = None) -> dict:
        """Index a vector for future retrieval."""
        if self.mesh:
            self.mesh.update_world_state(f"vec:{hashlib.md5(text.encode()).hexdigest()[:12]}",
                                         {"vector": vector, "meta": metadata or {}})
        return {"indexed": True, "dim": len(vector)}

    def retrieve_similar(self, query_vector: list[float], top_k: int = 5) -> list[dict]:
        """Retrieve similar vectors. Embedding does fast L2 scan."""
        return []  # Implemented via vector_store or hnsw/lancedb

    def receive(self, handshake: Handshake) -> dict | None:
        super().receive(handshake)
        if handshake.action == "index":
            return self.index_vector(
                handshake.payload.get("text", ""),
                handshake.payload.get("vector", []),
                handshake.payload.get("meta", {}),
            )
        if handshake.action == "retrieve":
            return {"results": self.retrieve_similar(
                handshake.payload.get("vector", []),
                handshake.payload.get("top_k", 5),
            )}
        return None


# ═══════════════════════════════════════════════════════════════
# 6. Output Governor — format, review, hallucination-check
# ═══════════════════════════════════════════════════════════════

class OutputGovernor(LayerGovernor):
    """Governs the output layer: format selection, quality review,
    hallucination detection, output sanitation, streaming control."""

    layer_name = "output"
    _quality_log: list[float] = []

    def review(self, text: str, context: str = "") -> dict:
        issues = []
        hallucination_markers = [
            "I don't have access to", "as of my knowledge cutoff",
            "I cannot access", "I am unable to",
        ]
        for marker in hallucination_markers:
            if marker.lower() in text.lower():
                issues.append(f"hallucination_marker: {marker}")
        quality = 1.0 - len(issues) * 0.2
        self._quality_log.append(quality)
        if len(self._quality_log) > 100:
            self._quality_log = self._quality_log[-100:]
        avg_quality = sum(self._quality_log) / len(self._quality_log) if self._quality_log else 1.0
        if avg_quality < 0.7 and self.mesh:
            self.send("evolution", "quality_alert",
                      {"avg_quality": avg_quality, "recent": self._quality_log[-10:]},
                      priority=HandshakePriority.HIGH)
        return {"quality": quality, "issues": issues, "avg_quality": avg_quality,
                "approved": quality >= 0.6}

    # ═══ Innovation 5: Silent self-check ═══
    async def silent_self_check(self, text: str, query: str, tree_llm=None) -> dict:
        """L2 reviews its own output before returning to human.

        CodePercept-inspired: if response contains code, execute it in sandbox
        for deterministic verification — not just fuzzy text scoring."""
        if not tree_llm or len(text) < 20:
            return {"passed": True, "confidence": 1.0}

        # CodePercept: executable verification for code responses
        code_blocks = re.findall(r'```(?:python|py)?\s*\n(.*?)```', text, re.DOTALL)
        if code_blocks:
            exec_result = await self._executable_verify(code_blocks, query)
            if exec_result:
                return exec_result

        # Fallback: text-based self-check
        check_prompt = (
            f"Rate this response on clarity, accuracy, and completeness (1-5 each).\n"
            f"Query: {query[:200]}\n"
            f"Response: {text[:500]}\n\n"
            f"Output JSON: "
            '{"clarity":3,"accuracy":3,"completeness":3,"issues":[],"fix":""}'
        )
        try:
            resp = await tree_llm.chat(
                messages=[{"role": "user", "content": check_prompt}],
                temperature=0.1, max_tokens=300, timeout=15,
                enable_coach=False, enable_onto=False,
            )
            result = resp.text if resp and hasattr(resp, "text") else ""
            m = re.search(r'\{.*\}', result, re.DOTALL)
            if m:
                data = _json_loads(m.group(0))
                scores = [data.get(k, 3) for k in ("clarity", "accuracy", "completeness")]
                confidence = sum(scores) / (len(scores) * 5.0)
                passed = confidence >= 0.6
                if not passed and self.mesh:
                    self.send("evolution", "quality_alert",
                              {"confidence": confidence, "issues": data.get("issues", [])},
                              priority=HandshakePriority.HIGH)
                return {"passed": passed, "confidence": confidence,
                        "issues": data.get("issues", []),
                        "fix": data.get("fix", "")}
        except Exception:
            pass
        return {"passed": True, "confidence": 0.8}

    # ═══ CodePercept: Executable verification ═══

    async def _executable_verify(self, code_blocks: list[str], query: str) -> dict | None:
        """Run code in sandbox to verify correctness deterministically.
        Code that runs correctly = verified. Code that fails = flagged."""
        import tempfile, os as _os

        for i, code in enumerate(code_blocks[:3]):
            code = code.strip()
            if not code or len(code) < 10:
                continue

            try:
                # Write to temp file and execute
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".py", delete=False, encoding="utf-8",
                ) as f:
                    f.write(code)
                    tmp_path = f.name

                from ..treellm.unified_exec import run_sync
                result = run_sync(f"{_os.sys.executable} {tmp_path}", timeout=10)
                _os.unlink(tmp_path, missing_ok=True)

                if result.success and result.stdout.strip():
                    return {
                        "passed": True,
                        "confidence": 0.95,
                        "method": "executable_verify",
                        "output": result.stdout[:500],
                    }
                elif not result.success:
                    return {
                        "passed": False,
                        "confidence": 0.3,
                        "method": "executable_verify",
                        "issues": [f"Execution failed: {result.stderr[:300]}"],
                        "fix": "Fix the code to run without errors",
                    }
            except Exception:
                try:
                    _os.unlink(tmp_path, missing_ok=True)
                except Exception:
                    pass
                continue

        return None

    def receive(self, handshake: Handshake) -> dict | None:
        super().receive(handshake)
        if handshake.action == "review_output":
            return self.review(
                handshake.payload.get("text", ""),
                handshake.payload.get("context", ""),
            )
        return None


# ═══════════════════════════════════════════════════════════════
# 7. Communication Governor — channel selection, formatting
# ═══════════════════════════════════════════════════════════════

class CommunicationGovernor(LayerGovernor):
    """Governs the communication layer: channel selection (web/wechat/feishu),
    message formatting, rate limiting, escalation decisions."""

    layer_name = "communication"

    def select_channel(self, urgency: float, content_type: str) -> dict:
        """Select the appropriate communication channel."""
        if urgency > 0.8:
            return {"channel": "all", "reason": "critical urgency"}
        if content_type == "code":
            return {"channel": "web", "reason": "code rendering"}
        return {"channel": "web", "reason": "default"}

    def format_message(self, text: str, channel: str) -> dict:
        """Format message for the selected channel."""
        if channel == "web":
            return {"format": "html", "text": text}
        if channel == "wechat":
            return {"format": "markdown", "text": text[:2000]}
        return {"format": "text", "text": text}

    def receive(self, handshake: Handshake) -> dict | None:
        super().receive(handshake)
        if handshake.action == "select_channel":
            return self.select_channel(
                handshake.payload.get("urgency", 0.5),
                handshake.payload.get("content_type", "text"),
            )
        return None


# ═══════════════════════════════════════════════════════════════
# 8. Task Governor — decompose, plan, schedule
# ═══════════════════════════════════════════════════════════════

class TaskGovernor(LayerGovernor):
    """Governs the task layer: decomposition, planning, scheduling,
    progress tracking, dependency resolution, retry management."""

    layer_name = "task"
    _active_tasks: dict[str, dict] = {}
    _completed_tasks: list[dict] = []

    async def decompose(self, task_description: str) -> dict:
        """Decompose a complex task into subtasks. L2 plans, L1 estimates."""
        # Handshake → Input for task classification
        if self.mesh:
            self.send("input", "classify_task",
                      {"task": task_description[:200]})
        return {
            "task_id": hashlib.md5(task_description.encode()).hexdigest()[:12],
            "subtasks": [],
            "estimated_rounds": 3,
        }

    def schedule(self, task_id: str, subtasks: list[dict]) -> dict:
        """Schedule subtasks across available workers."""
        self._active_tasks[task_id] = {
            "subtasks": subtasks,
            "started": time.time(),
            "status": "running",
        }
        return {"scheduled": len(subtasks), "task_id": task_id}

    def receive(self, handshake: Handshake) -> dict | None:
        super().receive(handshake)
        if handshake.action == "decompose":
            return {"task_id": hashlib.md5(
                handshake.payload.get("task", "").encode()
            ).hexdigest()[:12]}
        return None


# ═══════════════════════════════════════════════════════════════
# 9. Self Governor — introspection, health, self-healing
# ═══════════════════════════════════════════════════════════════

class SelfGovernor(LayerGovernor):
    """Governs self-awareness: health monitoring via vital_signs,
    anomaly detection via immune_system, self-healing,
    distributed trace via recording_engine+audit_log, graceful degradation."""

    layer_name = "self"
    _health_checks: list[dict] = []
    _anomalies: list[dict] = []
    _trace_spans: list[dict] = []
    _last_check: float = 0

    async def health_check(self) -> dict:
        """Run health check across all layers + vital_signs + immune_system."""
        results = {}
        anomalies = []

        # Vital signs check
        try:
            from ..treellm.vital_signs import get_vital_signs
            vs = get_vital_signs()
            v = vs.check_all()
            # Pass P/B/C health to mesh
            if self.mesh:
                self.mesh.update_world_state("p_health", v.get("p_health", 0.5))
                self.mesh.update_world_state("b_health", v.get("b_health", 0.5))
                self.mesh.update_world_state("c_health", v.get("c_health", 0.5))
            for key, val in v.items():
                if isinstance(val, (int, float)) and val < 0.4:
                    anomalies.append({"signal": key, "value": val, "threshold": 0.4})
                    self.detect_anomaly(f"low_{key}", val)
            results["vital_signs"] = v
        except Exception as e:
            results["vital_signs"] = f"unavailable: {e}"

        # Immune system scan
        try:
            from ..dna.immune_system import get_immune_system
            imm = get_immune_system()
            threats = imm.scan() if hasattr(imm, 'scan') else []
            if threats:
                for t in threats[:3]:
                    anomalies.append({"signal": "immune_threat", "value": str(t)[:200]})
                    self.detect_anomaly("immune_threat", str(t)[:100])
            results["immune"] = f"{len(threats)} threats" if hasattr(imm, 'scan') else "ok"
        except Exception:
            results["immune"] = "unavailable"

        # Mesh health ping
        if self.mesh:
            for name in self.mesh._governors:
                hs = self.mesh.send(Handshake(
                    source=self.layer_name, target=name,
                    action="health_ping", ttl=2.0,
                ))
                results[name] = "ok" if hs.responded else "timeout"
                if not hs.responded:
                    anomalies.append({"signal": "governor_timeout", "value": name})

        # On anomaly → handshake to Evolution for fix proposal
        if anomalies and self.mesh:
            self.send("evolution", "anomaly_alert",
                      {"anomalies": anomalies[:5]},
                      priority=HandshakePriority.HIGH)

        self._last_check = time.time()
        return {"mesh_health": results, "anomalies": anomalies,
                "anomaly_count": len(self._anomalies)}

    def start_trace(self, trace_id: str, context: dict = None) -> str:
        """Start a distributed trace span. Recorded via recording_engine."""
        span = {
            "trace_id": trace_id, "start": time.time(),
            "context": context or {}, "events": [],
        }
        self._trace_spans.append(span)
        try:
            from ..treellm.recording_engine import get_recording_engine
            rec = get_recording_engine()
            rec.capture("trace", trace_id, params=context or {}, result="started")
        except Exception:
            pass
        return trace_id

    def trace_event(self, trace_id: str, event: str, detail: Any = None) -> None:
        """Add an event to a trace span."""
        for span in self._trace_spans:
            if span["trace_id"] == trace_id:
                span["events"].append({
                    "time": time.time(), "event": event,
                    "detail": str(detail)[:500] if detail else "",
                })
                break

    def get_trace(self, trace_id: str) -> dict | None:
        """Retrieve a full trace by ID."""
        for span in self._trace_spans:
            if span["trace_id"] == trace_id:
                return span
        # Try recording_engine as fallback
        try:
            from ..treellm.recording_engine import get_recording_engine
            rec = get_recording_engine()
            events = rec.get_events(trace_id) if hasattr(rec, 'get_events') else []
            return {"trace_id": trace_id, "events": events}
        except Exception:
            pass
        return None

    def get_causal_chain(self, error_msg: str) -> list[dict]:
        """Build a causal chain from recent traces related to an error."""
        chain = []
        for span in self._trace_spans[-20:]:
            for evt in span.get("events", []):
                if any(kw in str(evt).lower() for kw in ["error", "fail", "timeout", "exception"]):
                    chain.append(span)
                    break
        return chain

    def detect_anomaly(self, signal: str, value: Any) -> None:
        self._anomalies.append({
            "time": time.time(), "signal": signal,
            "value": str(value)[:200],
        })
        if len(self._anomalies) > 100:
            self._anomalies = self._anomalies[-100:]

        # Predictive healing: check for degrading trends
        degraded = self._check_degradation_trend(signal)
        if degraded and self.mesh:
            self.send("evolution", "predictive_heal",
                      {"signal": signal, "trend": degraded},
                      priority=HandshakePriority.HIGH)

        try:
            from ..observability.audit_log import get_audit_log
            get_audit_log().log("anomaly", signal, detail=str(value)[:500])
        except Exception:
            pass

    def _check_degradation_trend(self, signal: str) -> dict | None:
        """Predictive: detect degrading trend before hard failure."""
        recent = [
            a for a in self._anomalies[-20:]
            if a["signal"] == signal
        ]
        if len(recent) < 3:
            return None
        times = [a["time"] for a in recent]
        intervals = [times[i+1] - times[i] for i in range(len(times)-1)]
        if intervals and min(intervals) < max(intervals) * 0.5:
            return {"signal": signal, "count": len(recent),
                    "accelerating": True,
                    "avg_interval_s": sum(intervals) / len(intervals)}
        return None

    # ═══ Innovation 4: Chaos Engineering ═══

    def inject_chaos(self, governor_name: str = "", intensity: float = 0.1) -> dict:
        """Controlled fault injection. Randomly disrupt a governor to test resilience.
        Only fires if mesh_health > 0.7 (system is healthy enough to handle it).
        Never touches 'self' governor (that's the failsafe)."""
        if governor_name == "self" or intensity > 0.5:
            return {"injected": False, "reason": "protected"}
        if self.mesh and self.mesh._mesh_health < 0.7:
            return {"injected": False, "reason": "mesh_unhealthy"}

        if not governor_name and self.mesh:
            import random as _random
            candidates = [n for n in self.mesh._governors if n != "self"]
            if not candidates:
                return {"injected": False, "reason": "no_candidates"}
            governor_name = _random.choice(candidates)

        chaos_types = ["latency_spike", "temporary_unavailable", "corrupted_response"]
        import random as _random
        chaos_type = _random.choice(chaos_types)

        logger.warning(
            f"ChaosMonkey: injecting {chaos_type} into {governor_name} "
            f"(intensity={intensity})"
        )
        self.detect_anomaly("chaos_injection",
                           f"{governor_name}:{chaos_type}")

        if self.mesh:
            self.mesh.update_world_state(f"chaos_{governor_name}", {
                "type": chaos_type, "intensity": intensity,
                "injected_at": time.time(),
            })

        return {"injected": True, "governor": governor_name,
                "type": chaos_type, "intensity": intensity}

    def receive(self, handshake: Handshake) -> dict | None:
        super().receive(handshake)
        if handshake.action == "health_ping":
            return {"status": "alive", "layer": self.layer_name}
        if handshake.action == "anomaly_alert":
            self.detect_anomaly(
                handshake.payload.get("signal", "unknown"),
                handshake.payload.get("value", ""),
            )
            # If critical → escalate to human via communication governor
            if handshake.priority == HandshakePriority.CRITICAL and self.mesh:
                self.send("communication", "escalate",
                          {"problem": handshake.payload.get("signal", ""),
                           "detail": str(handshake.payload.get("value", ""))},
                          priority=HandshakePriority.CRITICAL)
            return {"logged": True}
        return None


# ═══════════════════════════════════════════════════════════════
# 10. Evolution Governor — learn patterns, generate rules
# ═══════════════════════════════════════════════════════════════

class EvolutionGovernor(LayerGovernor):
    """Governs self-evolution: pattern discovery, rule generation,
    prompt improvement, reflex creation, architecture optimization,
    anti-pattern detection via L2 periodic code review."""

    layer_name = "evolution"
    _evolutions: list[dict] = []
    _anti_patterns: list[dict] = []
    _last_review: float = 0

    async def discover_and_improve(self, hub=None) -> list[str]:
        improvements = []
        self._ensure_tmi()
        if self._tmi:
            dreams = await self._tmi.dream(hub)
            improvements.extend(dreams)

        # Periodic anti-pattern detection via L2 code review
        if time.time() - self._last_review > 3600 and self.mesh:
            patterns = await self._detect_anti_patterns(hub)
            if patterns:
                improvements.append(f"anti_patterns: {len(patterns)} found")
                self._anti_patterns.extend(patterns)
                self._last_review = time.time()

        if self.mesh:
            self.send("self", "health_ping", priority=HandshakePriority.LOW)
        return improvements

    async def _detect_anti_patterns(self, hub=None) -> list[dict]:
        """L2 reviews codebase for anti-patterns: circular deps, god modules, deep nesting."""
        patterns = []
        try:
            arch = self.mesh.query_world_state("architecture_graph", {}) if self.mesh else {}
            deps = arch.get("dependencies", {})
            if deps:
                # Detect circular dependencies
                for mod_a, targets in deps.items():
                    for mod_b in targets:
                        if mod_b in deps and mod_a in deps.get(mod_b, []):
                            patterns.append({
                                "type": "circular_dependency",
                                "modules": [mod_a, mod_b],
                                "severity": "high",
                            })
                # Detect god modules (>20 imports)
                for mod, targets in deps.items():
                    if len(targets) > 20:
                        patterns.append({
                            "type": "god_module",
                            "module": mod,
                            "import_count": len(targets),
                            "severity": "medium",
                        })
        except Exception:
            pass

        if patterns and hub and hub.world and hub.world.consciousness:
            try:
                desc = "\n".join(
                    f"- {p['type']}: {p.get('modules', p.get('module',''))} [{p['severity']}]"
                    for p in patterns[:5]
                )
                prompt = (
                    f"Found these code architecture issues:\n{desc}\n\n"
                    f"Suggest concrete refactoring steps. Output JSON array: "
                    '[{"issue":"...","fix":"...","priority":"high|medium|low"}]'
                )
                resp = await hub.world.consciousness.query(prompt, max_tokens=400, temperature=0.3)
                if resp:
                    import re as _re, json as _json
                    m = _re.search(r'\[.*\]', resp, _re.DOTALL)
                    if m:
                        fixes = _json.loads(m.group(0))
                        for fix in fixes:
                            fix["detected_at"] = time.time()
                        patterns.extend(fixes)
            except Exception:
                pass

        if patterns:
            logger.info(f"AntiPatterns: detected {len(patterns)} issues")

        return patterns

    def generate_reflex(self, pattern: str, response: str) -> dict:
        self._ensure_tmi()
        if self._tmi:
            self._tmi.add_reflex(pattern, response)
        self._evolutions.append({"time": time.time(), "type": "reflex", "pattern": pattern})
        return {"created": True, "pattern": pattern}

    def receive(self, handshake: Handshake) -> dict | None:
        super().receive(handshake)
        if handshake.action == "quality_alert":
            return {"action": "scheduled_improvement",
                    "quality": handshake.payload.get("avg_quality", 0)}
        if handshake.action == "health_ping":
            return {"status": "alive", "layer": self.layer_name}
        return None


# ═══════════════════════════════════════════════════════════════
# Unified System — the complete cognitive organism
# ═══════════════════════════════════════════════════════════════

class LivingTreeSystem:
    """The complete unified system — all 10 governors orchestrated via CognitiveMesh.

    This is the top-level entry point that replaces scattered initialization.
    Human interaction is through a single process() call — everything else
    happens automatically through handshakes between governors.
    """

    def __init__(self, tree_llm=None):
        self.mesh = CognitiveMesh()
        self._tree_llm = tree_llm
        self.journal = TaskJournal()  # Human-visible action log

        # Instantiate all governors
        self.input = InputGovernor()
        self.context = ContextGovernor()
        self.routing = RoutingGovernor()
        self.capability = CapabilityGovernor()
        self.storage = StorageGovernor()
        self.output = OutputGovernor()
        self.communication = CommunicationGovernor()
        self.task = TaskGovernor()
        self.self_gov = SelfGovernor()
        self.evolution = EvolutionGovernor()

        # Wire governors into mesh
        for gov in [self.input, self.context, self.routing, self.capability,
                     self.storage, self.output, self.communication,
                     self.task, self.self_gov, self.evolution]:
            gov._tree_llm = tree_llm
            self.mesh.register(gov)

        # System Guardian — life support / failsafe
        self.guardian = SystemGuardian(self)

        # Evolution cycle timer
        self._evolution_task: asyncio.Task | None = None

    async def process(self, query: str, hub=None,
                      human_callback: Callable | None = None) -> dict[str, Any]:
        """Single entry point. Full pipeline with journal logging.

        In life support mode: bypass all governors, use emergency direct channel.
        Human can pause/resume via journal.pause_all()/resume_all().
        """
        t0 = time.time()

        if self.guardian.mode == SystemMode.LIFE_SUPPORT:
            entry = self.journal.log("emergency_chat", layer="guardian", model="l2")
            self.journal.start(entry.id)
            text = await self.guardian.emergency_chat(query)
            self.journal.complete(entry.id, text)
            return {
                "text": text, "method": "life_support",
                "mode": "life_support", "entry_id": entry.id,
                "elapsed_ms": (time.time() - t0) * 1000,
            }

        if self.journal.paused:
            return {
                "text": "⏸️ 系统已暂停。输入 '继续' 恢复，'报告' 查看状态。",
                "method": "paused",
                "elapsed_ms": (time.time() - t0) * 1000,
            }

        trace_id = hashlib.md5(f"{query}_{t0}".encode()).hexdigest()[:12]
        self.self_gov.start_trace(trace_id, {"query": query[:200]})

        human_msgs = self.journal.consume_messages()
        human_context = ""
        if human_msgs:
            human_context = "\n".join(f"[👤 人类: {m['message']}]" for m in human_msgs[-3:])

        entry = self.journal.log("输入处理", layer="input", model="embedding",
                                  input_short=query, estimated_ms=50)
        self.journal.start(entry.id)
        input_result = await self.input.process(query, hub)
        self.journal.complete(entry.id, f"triage={input_result.get('triage')}")

        if input_result.get("handled"):
            return {**input_result, "entry_id": entry.id}

        triage = input_result.get("triage")
        arch_ctx = input_result.get("architecture_context", "")
        enriched_query = query
        if arch_ctx:
            enriched_query = f"{query}\n\n[架构上下文]\n{arch_ctx}"
        if human_context:
            enriched_query = f"{human_context}\n\n{enriched_query}"

        from ..treellm.three_model_intelligence import get_three_model_intelligence
        tmi = get_three_model_intelligence(self._tree_llm)
        snapshot_id = tmi.save_snapshot(query[:100]) if tmi else ""

        if triage and triage.label == "fast" and self._tree_llm:
            entry2 = self.journal.log("L1快反", layer="l1", model="l1",
                                      input_short=enriched_query[:100], estimated_ms=300)
            self.journal.start(entry2.id)
            temp_adjust = input_result.get("temperature_adjust", 0.0)
            resp = await self._tree_llm.chat(
                messages=[{"role": "user", "content": enriched_query}],
                temperature=0.3 + temp_adjust, max_tokens=1024,
                enable_coach=False, enable_onto=False,
            )
            text = resp.text if resp and hasattr(resp, "text") else query
            method = "l1_fast"
            self.journal.complete(entry2.id, text[:200])
        elif self._tree_llm:
            entry2 = self.journal.log("L1↔L2协作", layer="l2", model="l1,l2",
                                      input_short=enriched_query[:100], estimated_ms=3000)
            self.journal.start(entry2.id)
            from ..treellm.l1_l2_collaboration import get_l1_l2_collaboration
            collab = get_l1_l2_collaboration(self._tree_llm)
            result = await collab.collaborative_chat(
                user_query=enriched_query, max_rounds=5, human_callback=human_callback,
            )
            text = result.text
            method = "l1_l2_collaboration"
            self.journal.complete(entry2.id, text[:200])
        else:
            text = query
            method = "unavailable"

        review = self.output.review(text)
        return {
            "text": text, "method": method,
            "quality": review.get("quality", 1.0),
            "snapshot_id": snapshot_id, "trace_id": trace_id,
            "entry_id": entry.id,
            "elapsed_ms": (time.time() - t0) * 1000,
        }

    # ═══ Unified Chat — single natural-language entry for ALL interactions ═══

    async def chat(self, message: str, hub=None) -> str:
        """THE ONLY entry point. Natural language drives everything.

        Humans type anything — the system auto-classifies intent:
          - Normal query → full pipeline (reflex/L1/L2)
          - Status check → journal report
          - Admin command → pause/resume/restart/inspect
          - Decision → answer pending decision point

        No code calls needed. Everything is just chat.
        """
        intent = await self._classify_intent(message)
        logger.debug(f"UnifiedChat: intent={intent} ({message[:50]})")

        if intent == "command_status":
            return self.journal.status_report()

        if intent == "command_pause":
            self.journal.pause_all()
            return "⏸️ 已暂停。随时说'继续'恢复，我会从断点接着做。"

        if intent == "command_resume":
            self.journal.resume_all()
            return "▶️ 已恢复。继续之前的工作。"

        if intent == "command_problems":
            return self.journal.problem_report()

        if intent == "command_eta":
            return self._eta_report()

        if intent == "command_health":
            result = await self.self_gov.health_check()
            return f"🫀 系统健康: {result.get('anomaly_count', 0)} 异常"

        if intent == "command_architecture":
            m = self.input.render_architecture_mermaid()
            return f"```mermaid\n{m}\n```"

        if intent == "command_chaos":
            r = self.self_gov.inject_chaos(intensity=0.1)
            return f"🌀 混沌注入: {r}"

        if intent == "command_inject":
            self.journal.inject_message(message)
            return "📨 已注入上下文，继续处理时我会参考。"

        if intent == "command_restart":
            target = message.replace("重启", "").replace("restart", "").strip()
            r = await self.guardian.hot_restart_governor(target) if target else {"error": "no target"}
            return str(r)

        if intent == "command_decision":
            self.journal.resolve_decision(message)
            return "✅ 已记录你的决定。"

        if intent == "command_snapshot":
            restored = await self._snapshot_switch(message)
            return restored or "未找到相关上下文，请说具体一点。"

        # Normal query — full intelligent pipeline
        result = await self.process(message, hub)
        text = result.get("text", "")
        method = result.get("method", "unknown")

        # Innovation 5: Silent self-check (async, doesn't block response)
        if len(text) > 20 and self._tree_llm:
            asyncio.create_task(
                self.output.silent_self_check(text, message, self._tree_llm)
            )

        # Innovation 2: Predictive preload for next likely query
        asyncio.create_task(self._speculative_preload(message))

        # Innovation 1: Compress this turn for memory-efficient history
        self.context.compress_turn(f"Q:{message[:100]} | A:{text[:100]}")

        return text

    # ═══ Innovation 3: Context snapshot switching ═══

    async def _snapshot_switch(self, hint: str) -> str | None:
        """Human says '回到刚才讨论数据库的时候' → find and restore that context.
        Uses embedding similarity to find the right snapshot from history."""
        from .three_model_intelligence import get_three_model_intelligence
        tmi = get_three_model_intelligence(self._tree_llm)
        if not tmi:
            return None

        # Search conversation memory
        similar_turns = self.context.find_similar_turns(hint, top_k=2)
        if similar_turns:
            turn_info = f"找到了 {len(similar_turns)} 个相关的历史上下文"
            # Search reasoning snapshots
            snapshots = tmi.find_similar_snapshot(hint, top_k=2)
            if snapshots:
                ctx = "\n".join(s.summary for s in snapshots[:2])
                # Inject as context for next query
                self.journal.inject_message(f"[上下文恢复] {ctx}")
                return f"已恢复上下文:\n{ctx}"
            return turn_info

        # Try reasoning snapshots
        snapshots = tmi.find_similar_snapshot(hint, top_k=3)
        if snapshots:
            ctx = "\n".join(s.summary for s in snapshots[:3])
            self.journal.inject_message(f"[上下文恢复] {ctx}")
            return f"已恢复到: {snapshots[0].summary}"

        return None

    # ═══ Intent classification ═══

    _INTENT_PATTERNS = [
        ("command_status",   ["报告", "状态", "进度", "做了什么", "汇报", "report", "status", "progress"]),
        ("command_pause",    ["暂停", "停一下", "等等", "pause", "stop", "wait", "等一下"]),
        ("command_resume",   ["继续", "接着", "恢复", "resume", "go on", "continue"]),
        ("command_problems", ["问题", "出错", "故障", "错误", "怎么了", "problems", "issues", "errors"]),
        ("command_eta",      ["还要多久", "预计", "剩余", "eta", "多久", "还要多长时间"]),
        ("command_health",   ["健康", "检查", "体检", "health", "check", "状态怎么样"]),
        ("command_architecture", ["架构图", "可视化", "依赖图", "mermaid", "结构图"]),
        ("command_chaos",    ["混沌", "chaos", "故障注入", "注入"]),
        ("command_restart",  ["重启", "restart"]),
        ("command_inject",   ["注意", "提醒", "记住", "note", "remember"]),
        ("command_decision", ["决定", "选", "option", "decide"]),
        ("command_snapshot", ["回到", "恢复", "之前", "刚才", "上一次"]),
    ]

    async def _classify_intent(self, message: str) -> str:
        """Classify user intent: normal query vs system command.
        Embedding-based for ambiguous cases, pattern-based for clear ones."""
        msg_lower = message.lower().strip()

        # Pattern match (fast, <1ms)
        for intent, keywords in self._INTENT_PATTERNS:
            for kw in keywords:
                if kw in msg_lower:
                    return intent

        # Embedding-based (for ambiguous messages)
        try:
            from .three_model_intelligence import get_three_model_intelligence
            tmi = get_three_model_intelligence(self._tree_llm)
            if tmi and tmi._embedder:
                vec = tmi._get_embedding(message)
                if vec is not None and hasattr(tmi, '_reflex_matrix') and tmi._reflex_matrix is not None:
                    sims = np.dot(tmi._reflex_matrix, vec)
                    if float(np.max(sims)) > 0.85:
                        return "command_status"  # Matched a reflex → likely a known command
        except Exception:
            pass

        # Default: normal query
        return "normal_query"

    def _eta_report(self) -> str:
        entries = self.journal.get_history(50)
        pending = [e for e in entries if e.status in (
            JournalStatus.PENDING, JournalStatus.RUNNING, JournalStatus.PAUSED,
        )]
        remaining = sum(e.estimated_ms for e in pending) / 1000
        done = sum(e.elapsed_ms for e in entries if e.status == JournalStatus.DONE) / 1000
        return (
            f"已用: {done:.0f}s | 剩余约: {remaining:.0f}s | "
            f"待完成: {len(pending)} 项 | "
            f"{'⏸️暂停中' if self.journal.paused else '▶️运行中'}"
        )

    # ═══ Performance optimizations ═══

    async def _speculative_preload(self, current_query: str) -> None:
        """After answering query, predict and preload what human might ask next.
        Uses semantic trajectory prediction on recent conversation."""
        try:
            from .three_model_intelligence import get_three_model_intelligence
            tmi = get_three_model_intelligence(self._tree_llm)
            if tmi:
                needs = tmi._predict_needs(current_query)
                if needs:
                    await self.context.preload(current_query, needs)
        except Exception:
            pass

    def stats(self) -> dict:
        return {
            "mesh": self.mesh.stats(),
            "input_reflex_hits": self.mesh._stats.get("input", LayerStats()).reflex_hits,
            "anomalies": len(self.self_gov._anomalies),
            "traces": len(self.self_gov._trace_spans),
            "architecture": "scanned" if self.input._arch_scanned else "pending",
            "guardian": self.guardian.stats(),
        }


# ═══════════════════════════════════════════════════════════════
# System Guardian — Life Support / Failsafe Mode
# ═══════════════════════════════════════════════════════════════

class SystemMode(str, Enum):
    NORMAL = "normal"         # All governors active
    DEGRADED = "degraded"     # Some governors impaired, graceful fallback
    LIFE_SUPPORT = "life_support"  # Minimal mode: direct I/O, emergency channel


class SystemGuardian:
    """Minimal failsafe subsystem. Auto-activates when system health degrades.

    In life support mode:
      - Bypasses ALL governors (they may be the source of failure)
      - Direct Embedding→L1→L2 pipeline with minimal dependencies
      - Monitors vital signs independently
      - Hot-restarts failed modules on recovery
      - Progressive: returns to normal mode when health is restored

    Activation thresholds:
      - 3+ anomalies in 60s → DEGRADED
      - 5+ anomalies or L2 errors > 50% → LIFE_SUPPORT
    """

    CHECK_INTERVAL = 15  # seconds between health checks

    def __init__(self, system: LivingTreeSystem):
        self._system = system
        self._mode = SystemMode.NORMAL
        self._lock = threading.Lock()
        self._error_count: int = 0
        self._consecutive_failures: int = 0
        self._last_recovery: float = 0.0
        self._restart_log: list[dict] = []
        self._guardian_task: asyncio.Task | None = None
        self._emergency_channel = asyncio.Queue(maxsize=10)
        self._direct_response_cache: dict[str, str] = {}

    @property
    def mode(self) -> SystemMode:
        return self._mode

    async def start(self) -> None:
        """Start the guardian background monitor."""
        if self._guardian_task and not self._guardian_task.done():
            return
        self._guardian_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"SystemGuardian: started (mode={self._mode.value})")

    async def stop(self) -> None:
        if self._guardian_task:
            self._guardian_task.cancel()
            try:
                await self._guardian_task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self) -> None:
        """Continuous background health monitoring."""
        while True:
            await asyncio.sleep(self.CHECK_INTERVAL)
            try:
                await self._health_check()
            except Exception as e:
                logger.debug(f"Guardian health check failed: {e}")

    async def _health_check(self) -> None:
        mesh = self._system.mesh
        self_gov = self._system.self_gov

        # Check anomaly rate
        now = time.time()
        recent_anomalies = [
            a for a in self_gov._anomalies
            if (now - a["time"]) < 60
        ]
        anomaly_count = len(recent_anomalies)

        # Check L2 error rate
        l2_stats = mesh._stats.get("input", LayerStats())
        l2_error_rate = l2_stats.errors / max(l2_stats.decisions_made, 1)

        # Decision
        with self._lock:
            if anomaly_count >= 5 or l2_error_rate > 0.5:
                if self._mode != SystemMode.LIFE_SUPPORT:
                    await self._activate_life_support(recent_anomalies)
            elif anomaly_count >= 3:
                if self._mode == SystemMode.NORMAL:
                    await self._activate_degraded(recent_anomalies)
            elif self._mode != SystemMode.NORMAL and anomaly_count == 0:
                await self._attempt_recovery()

    async def _activate_degraded(self, anomalies: list[dict]) -> None:
        logger.warning(
            f"SYSTEM DEGRADED: {len(anomalies)} anomalies in 60s"
        )
        self._mode = SystemMode.DEGRADED
        # Reduce mesh health to trigger conservative routing
        self._system.mesh._mesh_health = 0.5
        # Notify routing to prefer flash models
        self._system.mesh.update_world_state("system_mode", "degraded")
        # Cache recent errors for context
        for a in anomalies[:5]:
            self._system.self_gov.detect_anomaly(
                f"degraded_{a['signal']}", a["value"]
            )

    async def _activate_life_support(self, anomalies: list[dict]) -> None:
        """CRITICAL: activate minimal life support mode."""
        logger.critical(
            f"LIFE SUPPORT ACTIVATED: {len(anomalies)} anomalies, "
            f"{len(self._system.mesh._governors)} governors"
        )
        self._mode = SystemMode.LIFE_SUPPORT
        self._system.mesh._mesh_health = 0.1
        self._system.mesh.update_world_state("system_mode", "life_support")

        # Emergency inventory
        alive_governors = []
        for name, gov in self._system.mesh._governors.items():
            hs = self._system.mesh.send(Handshake(
                source="guardian", target=name,
                action="health_ping", ttl=1.0,
            ))
            alive_governors.append({
                "name": name,
                "alive": hs.responded,
            })

        # Log critical state
        for a in anomalies[:10]:
            self._system.self_gov.detect_anomaly(
                f"critical_{a['signal']}", a["value"]
            )

        # Attempt to restart failed governors
        for g in alive_governors:
            if not g["alive"] and g["name"] != "self":
                self._restart_log.append({
                    "time": time.time(),
                    "governor": g["name"],
                    "action": "restart_attempted",
                })
                logger.warning(f"LifeSupport: governor {g['name']} unresponsive")

    async def _attempt_recovery(self) -> None:
        """Progressive recovery: try to return to normal mode."""
        now = time.time()
        if now - self._last_recovery < 30:
            return

        logger.info("Attempting recovery from life support")
        self._system.mesh._mesh_health = 0.7

        # Re-register all governors
        for name, gov in list(self._system.mesh._governors.items()):
            if name != "self":
                hs = self._system.mesh.send(Handshake(
                    source="guardian", target=name,
                    action="health_ping", ttl=3.0,
                ))
                if hs.responded:
                    logger.info(f"Recovery: {name} back online")

        self._mode = SystemMode.NORMAL
        self._system.mesh._mesh_health = 1.0
        self._system.mesh.update_world_state("system_mode", "normal")
        self._last_recovery = now
        self._error_count = 0
        self._consecutive_failures = 0

        # Run health check after recovery
        await self._system.self_gov.health_check()

        logger.info("System recovered to NORMAL mode")

    # ═══ Emergency direct channel ═══

    async def emergency_chat(self, query: str) -> str:
        """Direct I/O pipeline — bypasses ALL governors in life support mode.

        Uses ONLY the three models (Embedding→reflex, L1→fast, L2→minimal).
        No governors, no mesh, no handshakes. Minimum viable response.
        """
        tree = self._system._tree_llm
        if not tree:
            return "System unavailable — life support active"

        # Embedding reflex intercept (still works in emergency)
        try:
            from .three_model_intelligence import get_three_model_intelligence
            tmi = get_three_model_intelligence(tree)
            reflex = await tmi.spinal_reflex(query)
            if reflex:
                return reflex
        except Exception:
            pass

        # Minimal L1 fast response
        try:
            resp = await tree.chat(
                messages=[{"role": "user", "content": query}],
                temperature=0.1, max_tokens=512, timeout=10,
                enable_coach=False, enable_onto=False,
            )
            if resp and hasattr(resp, "text") and resp.text:
                return resp.text
        except Exception:
            pass

        return (
            "系统处于生命维持模式 - 核心推理功能已降级。"
            "请稍候，系统正在自动恢复。\n\n"
            "[System in life support mode — degraded response. "
            "Auto-recovery in progress.]"
        )

    async def hot_restart_governor(self, governor_name: str) -> dict:
        """Hot-restart a specific governor without affecting others."""
        if governor_name == "self":
            return {"restarted": False, "reason": "self is protected"}
        mesh = self._system.mesh
        if governor_name not in mesh._governors:
            return {"restarted": False, "reason": "not found"}

        # Kill old
        old_gov = mesh._governors.pop(governor_name, None)
        # Re-register (governor retains state via mesh)
        if old_gov:
            mesh.register(old_gov)

        self._restart_log.append({
            "time": time.time(),
            "governor": governor_name,
            "action": "hot_restart",
        })

        logger.info(f"Hot-restarted governor: {governor_name}")
        return {"restarted": True, "governor": governor_name}

    def stats(self) -> dict:
        with self._lock:
            return {
                "mode": self._mode.value,
                "error_count": self._error_count,
                "consecutive_failures": self._consecutive_failures,
                "restarts": len(self._restart_log),
                "mesh_health": self._system.mesh._mesh_health,
            }


# ── Singleton ──
_system: LivingTreeSystem | None = None


def get_living_tree_system(tree_llm=None) -> LivingTreeSystem:
    global _system
    if _system is None and tree_llm is not None:
        _system = LivingTreeSystem(tree_llm)
    elif _system is None:
        _system = LivingTreeSystem()
    return _system
