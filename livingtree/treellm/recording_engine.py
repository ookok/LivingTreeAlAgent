"""RecordingEngine — Task recording and replay with frontend rendering.

Every action through the unified layers can be recorded into a replayable,
editable Recording. Supports XML (human-editable) and JSONL (machine-efficient)
formats. Replay in deterministic, streaming, or edit-and-rerun modes.

Recording format:
  <recording id="rec_xxx" created="..." duration_ms="..." layers="input|llm|tool|vfs|render">
    <event id="evt_N" ts="..." type="..." layer="..." render="..." depends="...">
      <params .../>
      <result error="..." duration_ms="...">...</result>
    </event>
  </recording>

Integration:
  rec = get_recording_engine()
  rec.start("分析代码库")              # Begin recording
  evt_id = rec.capture("tool", "vfs:list", {"path":"/disk"}, result, "table")
  evt_id = rec.capture("llm", "chat", params, result, "stream", depends=["evt_1"])
  recording = rec.stop()               # → Recording object
  await rec.replay(recording, mode="stream", speed=2)  # Replay
"""

from __future__ import annotations

import asyncio
import copy
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, AsyncIterator, Optional
from xml.etree import ElementTree as ET
from xml.dom import minidom

from loguru import logger

RECORDINGS_DIR = Path(".livingtree/recordings")


# ═══ Data Types ════════════════════════════════════════════════════


class RecordLayer(StrEnum):
    INPUT = "input"
    LLM = "llm"
    TOOL = "tool"
    VFS = "vfs"
    RENDER = "render"
    MEMORY = "memory"


class ReplayMode(StrEnum):
    DETERMINISTIC = "deterministic"  # Re-execute tools, compare results
    STREAMING = "streaming"          # Yield events with original timing
    SKELETON = "skeleton"            # Fast-forward, show structure only
    EDIT = "edit"                    # Modify params and re-execute


@dataclass
class RecordedEvent:
    """A single recorded event in a task trace."""
    id: str
    ts: int = 0                     # Milliseconds from recording start
    type: str = ""                  # "user_input" | "llm_chat" | "tool_call" | "vfs_op" | "render"
    layer: RecordLayer = RecordLayer.TOOL
    params: dict = field(default_factory=dict)
    capability: str = ""            # For tool calls: "vfs:read", "tool:web_search"
    result: Any = None
    result_error: bool = False
    result_duration_ms: float = 0.0
    render: str = "card"            # Frontend render hint
    depends_on: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "ts": self.ts, "type": self.type,
            "layer": self.layer.value, "params": self.params,
            "capability": self.capability,
            "result": self._serialize_result(),
            "result_error": self.result_error,
            "result_duration_ms": self.result_duration_ms,
            "render": self.render, "depends_on": self.depends_on,
            "metadata": self.metadata,
        }

    def _serialize_result(self):
        if isinstance(self.result, (str, int, float, bool, type(None))):
            return self.result
        if isinstance(self.result, (list, dict)):
            return json.dumps(self.result, ensure_ascii=False, default=str)[:10000]
        return str(self.result)[:10000]

    @classmethod
    def from_dict(cls, d: dict) -> "RecordedEvent":
        return cls(
            id=d["id"], ts=d.get("ts", 0), type=d.get("type", ""),
            layer=RecordLayer(d.get("layer", "tool")),
            params=d.get("params", {}), capability=d.get("capability", ""),
            result=d.get("result"), result_error=d.get("result_error", False),
            result_duration_ms=d.get("result_duration_ms", 0),
            render=d.get("render", "card"), depends_on=d.get("depends_on", []),
            metadata=d.get("metadata", {}),
        )


@dataclass
class Recording:
    """A complete task recording."""
    id: str
    title: str = ""
    created_at: float = field(default_factory=time.time)
    duration_ms: int = 0
    events: list[RecordedEvent] = field(default_factory=list)
    task_type: str = "general"
    provider: str = ""
    session_id: str = "perpetual"
    total_tool_calls: int = 0
    total_tokens: int = 0

    def to_jsonl(self) -> str:
        return "\n".join(json.dumps(e.to_dict(), ensure_ascii=False) for e in self.events)

    def to_xml(self) -> str:
        root = ET.Element("recording", {
            "id": self.id, "created": str(int(self.created_at)),
            "duration_ms": str(self.duration_ms),
            "layers": "input|llm|tool|vfs|render",
        })
        meta = ET.SubElement(root, "meta")
        ET.SubElement(meta, "task_type").text = self.task_type
        ET.SubElement(meta, "provider").text = self.provider
        ET.SubElement(meta, "session_id").text = self.session_id
        ET.SubElement(meta, "tool_calls").text = str(self.total_tool_calls)
        ET.SubElement(meta, "total_tokens").text = str(self.total_tokens)

        timeline = ET.SubElement(root, "timeline")
        for e in self.events:
            el = ET.SubElement(timeline, "event", {
                "id": e.id, "ts": str(e.ts), "type": e.type,
                "layer": e.layer.value, "render": e.render,
            })
            if e.depends_on:
                el.set("depends", ",".join(e.depends_on))
            if e.capability:
                el.set("capability", e.capability)

            params_el = ET.SubElement(el, "params")
            for k, v in e.params.items():
                params_el.set(k, str(v)[:200])

            result_el = ET.SubElement(el, "result", {
                "error": str(e.result_error).lower(),
                "duration_ms": str(int(e.result_duration_ms)),
            })
            result_text = str(e.result)[:5000] if e.result else ""
            result_el.text = result_text

        rough = ET.tostring(root, encoding="unicode")
        return minidom.parseString(rough).toprettyxml(indent="  ")

    def to_dict(self) -> dict:
        return {
            "id": self.id, "title": self.title, "created_at": self.created_at,
            "duration_ms": self.duration_ms, "task_type": self.task_type,
            "provider": self.provider, "total_tool_calls": self.total_tool_calls,
            "total_tokens": self.total_tokens,
            "events": [e.to_dict() for e in self.events],
        }

    @classmethod
    def from_jsonl(cls, jsonl_text: str) -> "Recording":
        events = []
        for line in jsonl_text.strip().split("\n"):
            if line.strip():
                events.append(RecordedEvent.from_dict(json.loads(line)))
        rec = Recording(id="imported", events=events)
        if events:
            rec.duration_ms = events[-1].ts
        return rec

    def render_config(self) -> dict:
        """Generate frontend rendering configuration."""
        views = []
        has_table = any(e.render == "table" for e in self.events)
        has_stream = any(e.render == "stream" for e in self.events)
        has_code = any(e.render == "code" for e in self.events)

        views.append({"type": "timeline", "title": "执行时间线", "default": True})
        views.append({"type": "card", "title": "摘要视图"})
        if has_table:
            views.append({"type": "table", "title": "数据表格"})
        if has_stream:
            views.append({"type": "stream", "title": "逐字回放"})
        if has_code:
            views.append({"type": "code", "title": "代码视图"})

        # File changes for diff view
        changed_files = [e for e in self.events
                         if e.layer == RecordLayer.VFS and e.params.get("path")]
        if changed_files:
            views.append({"type": "diff", "title": "文件变更"})

        return {"default_view": "timeline", "views": views}


# ═══ RecordingEngine ═══════════════════════════════════════════════


class RecordingEngine:
    """Task recording and replay engine."""

    _instance: Optional["RecordingEngine"] = None

    @classmethod
    def instance(cls) -> "RecordingEngine":
        if cls._instance is None:
            cls._instance = RecordingEngine()
        return cls._instance

    def __init__(self):
        self._active: Optional[Recording] = None
        self._start_ts: float = 0.0
        self._recordings: dict[str, Recording] = {}
        self._load_all()

    # ── Recording ──────────────────────────────────────────────────

    def start(self, title: str = "", task_type: str = "general",
              session_id: str = "perpetual") -> str:
        """Start recording. Returns recording_id."""
        rec_id = f"rec_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        self._active = Recording(
            id=rec_id, title=title, task_type=task_type,
            session_id=session_id,
        )
        self._start_ts = time.time()
        logger.info(f"RecordingEngine: started '{title or rec_id}'")
        return rec_id

    def capture(self, layer: RecordLayer, event_type: str,
                params: dict = None, result: Any = None,
                render: str = "card", capability: str = "",
                depends_on: list[str] = None,
                duration_ms: float = 0.0, error: bool = False,
                **meta) -> str:
        """Capture an event into the active recording. Returns event_id."""
        if not self._active:
            return ""
        evt = RecordedEvent(
            id=f"evt_{len(self._active.events)}",
            ts=int((time.time() - self._start_ts) * 1000),
            type=event_type, layer=layer,
            params=params or {}, capability=capability,
            result=result,
            result_error=error,
            result_duration_ms=duration_ms,
            render=render,
            depends_on=depends_on or [],
            metadata=meta,
        )
        self._active.events.append(evt)
        if layer == RecordLayer.TOOL:
            self._active.total_tool_calls += 1
        return evt.id

    def stop(self) -> Optional[Recording]:
        """Stop recording and return the completed Recording."""
        if not self._active:
            return None
        rec = self._active
        rec.duration_ms = int((time.time() - self._start_ts) * 1000)
        self._active = None
        self._recordings[rec.id] = rec
        self._save(rec)
        logger.info(f"RecordingEngine: stopped '{rec.id}' ({len(rec.events)} events, {rec.duration_ms}ms)")
        return rec

    @property
    def is_recording(self) -> bool:
        return self._active is not None

    # ── Replay ─────────────────────────────────────────────────────

    async def replay(self, recording_id: str,
                     mode: ReplayMode = ReplayMode.STREAMING,
                     speed: float = 1.0,
                     edits: dict[str, dict] = None,
                     bus: Any = None) -> AsyncIterator[RecordedEvent]:
        """Replay a recording in the specified mode."""
        rec = self._recordings.get(recording_id)
        if not rec:
            rec = self._load(recording_id)
        if not rec:
            yield RecordedEvent(id="error", type="error",
                               result={"error": f"Recording not found: {recording_id}"})
            return

        if mode == ReplayMode.SKELETON:
            for e in rec.events:
                e_skeleton = copy.deepcopy(e)
                e_skeleton.result = f"[{e.result_duration_ms}ms] {e.type}"
                yield e_skeleton
            return

        if mode == ReplayMode.EDIT and edits:
            for e in rec.events:
                if e.id in edits:
                    e.params.update(edits[e.id])
                if bus and e.capability:
                    try:
                        new_result = await bus.invoke(e.capability, **e.params)
                        e.result = new_result
                    except Exception as ex:
                        e.result = {"error": str(ex)}
                        e.result_error = True
                yield e
            return

        if mode == ReplayMode.DETERMINISTIC:
            for e in rec.events:
                if bus and e.capability:
                    try:
                        new_result = await bus.invoke(e.capability, **e.params)
                        if new_result != e.result:
                            e.metadata["diff"] = self._diff(e.result, new_result)
                            e.result = new_result
                    except Exception as ex:
                        e.result = {"error": str(ex)}
                        e.result_error = True
                yield e
            return

        # STREAMING mode: yield with original timing
        last_ts = 0
        for e in rec.events:
            delay = (e.ts - last_ts) / (speed * 1000.0)
            if delay > 0:
                await asyncio.sleep(min(delay, 2.0))  # Cap at 2s
            yield e
            last_ts = e.ts

    def render(self, recording_id: str, view: str = "timeline") -> dict:
        """Render a recording for frontend display."""
        rec = self._recordings.get(recording_id)
        if not rec:
            return {"error": f"Recording not found: {recording_id}"}

        config = rec.render_config()
        events = rec.to_dict()["events"]

        if view == "timeline":
            return {
                "view": "timeline",
                "config": config,
                "events": [{
                    "id": e["id"], "ts": e["ts"], "type": e["type"],
                    "render": e["render"], "summary": str(e["result"])[:200],
                    "depends_on": e["depends_on"],
                } for e in events],
            }
        if view == "card":
            return {
                "view": "card",
                "title": rec.title or rec.id,
                "duration_ms": rec.duration_ms,
                "events": len(events),
                "tool_calls": rec.total_tool_calls,
                "events": [{
                    "id": e["id"], "type": e["type"],
                    "render": e["render"],
                    "summary": str(e["result"])[:300],
                } for e in events],
            }
        if view == "table":
            rows = [e for e in events if e["render"] == "table"]
            return {
                "view": "table",
                "columns": ["id", "ts", "type", "capability", "result"],
                "rows": [{
                    "id": e["id"], "ts": e["ts"], "type": e["type"],
                    "capability": e.get("capability", ""),
                    "result": str(e["result"])[:200],
                } for e in rows],
            }
        if view == "diff":
            changed = [e for e in events
                       if e.get("layer") == "vfs" and e.get("params", {}).get("path")]
            return {
                "view": "diff",
                "files": [{
                    "path": e["params"].get("path", ""),
                    "before": "",
                    "after": str(e["result"])[:2000],
                } for e in changed],
            }
        return {"view": view, "events": events, "config": config}

    # ── Persistence ────────────────────────────────────────────────

    def _save(self, rec: Recording):
        try:
            RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
            path = RECORDINGS_DIR / f"{rec.id}.jsonl"
            path.write_text(rec.to_jsonl(), encoding="utf-8")
        except Exception as e:
            logger.debug(f"RecordingEngine save: {e}")

    def _load(self, rec_id: str) -> Optional[Recording]:
        try:
            path = RECORDINGS_DIR / f"{rec_id}.jsonl"
            if path.exists():
                return Recording.from_jsonl(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.debug(f"RecordingEngine load {rec_id}: {e}")
        return None

    def _load_all(self):
        try:
            if RECORDINGS_DIR.exists():
                for f in RECORDINGS_DIR.glob("*.jsonl"):
                    rec = Recording.from_jsonl(f.read_text(encoding="utf-8"))
                    if rec:
                        self._recordings[rec.id] = rec
                logger.info(f"RecordingEngine: loaded {len(self._recordings)} recordings")
        except Exception:
            pass

    def list_recordings(self) -> list[dict]:
        return [{
            "id": r.id, "title": r.title, "created_at": r.created_at,
            "duration_ms": r.duration_ms, "events": len(r.events),
            "tool_calls": r.total_tool_calls,
        } for r in self._recordings.values()]

    def delete(self, rec_id: str) -> bool:
        if rec_id in self._recordings:
            del self._recordings[rec_id]
        path = RECORDINGS_DIR / f"{rec_id}.jsonl"
        if path.exists():
            path.unlink()
            return True
        return False

    def export(self, rec_id: str, format: str = "jsonl") -> Optional[str]:
        rec = self._recordings.get(rec_id)
        if not rec:
            return None
        if format == "xml":
            return rec.to_xml()
        if format == "json":
            return json.dumps(rec.to_dict(), ensure_ascii=False, default=str)
        return rec.to_jsonl()

    @staticmethod
    def _diff(a: Any, b: Any) -> str:
        if a == b:
            return "no change"
        return f"changed: {str(a)[:100]} → {str(b)[:100]}"

    def stats(self) -> dict:
        return {
            "total_recordings": len(self._recordings),
            "is_recording": self._active is not None,
            "active_id": self._active.id if self._active else "",
        }


# ═══ Singleton ════════════════════════════════════════════════════

_engine: Optional[RecordingEngine] = None


def get_recording_engine() -> RecordingEngine:
    global _engine
    if _engine is None:
        _engine = RecordingEngine()
    return _engine


__all__ = [
    "RecordingEngine", "Recording", "RecordedEvent",
    "RecordLayer", "ReplayMode",
    "get_recording_engine",
]
