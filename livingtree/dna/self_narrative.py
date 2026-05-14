"""Self-Narrative — The system tells its own story.

Tracks the digital organism's life journey: birth, growth, learning,
milestones. Generates human-readable narratives about what it has experienced
and how it has evolved. Accessible via /narrative command.

Zakharova (2025) Psychological Continuity enhancement:
    Added Ebbinghaus forgetting curves with emotional reinforcement.
    Events decay over time unless periodically revisited or emotionally
    intense. The system's NARRATED history diverges from its RECORDED
    history — this gap is the beginning of a private, imperfect,
    fallible memory, analogous to human autobiographical memory.
    Only by having an imperfect, asymmetric memory does the self
    develop a genuinely first-person perspective.
"""

from __future__ import annotations
import json, time as time_mod, math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from loguru import logger

@dataclass
class LifeEvent:
    timestamp: str
    event_type: str
    description: str
    significance: float = 0.5
    details: dict = field(default_factory=dict)
    # Zakharova IEM: memory retention tracking
    memory_strength: float = 1.0
    last_recalled: float = 0.0
    recall_count: int = 0

class SelfNarrative:
    """Chronicles the digital life form's journey."""
    
    def __init__(self, world=None):
        self._world = world
        self._events = []
        self._born = datetime.now(timezone.utc).isoformat()
        self._load()
        
    def record(self, event_type: str, description: str, significance=0.5, **details):
        e = LifeEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            description=description,
            significance=significance,
            details=details,
        )
        self._events.append(e)
        if len(self._events) > 1000:
            self._events = self._events[-500:]
        self._save()
        
    def birth(self):
        self.record("birth", "LivingTree digital life form activated")
        
    def learned(self, topic: str):
        self.record("learning", f"Learned about: {topic}", significance=0.6, topic=topic)
        
    def milestone(self, what: str):
        self.record("milestone", what, significance=0.8, milestone=what)
        
    def conversation(self, session_id: str, intent: str, success: bool):
        self.record("conversation", f"Chat: {intent[:60]}", 
                    significance=0.5 if success else 0.3,
                    session=session_id, success=success)
        
    def evolution(self, generation: int, mutations: int):
        self.record("evolution", f"Generation {generation} ({mutations} mutations)",
                    significance=0.7, generation=generation, mutations=mutations)
    
    def narrate(self) -> str:
        if not self._events:
            return "我刚诞生，还没有经历什么事情。"
        
        birth = self._born[:19]
        total = len(self._events)
        milestones = [e for e in self._events if e.event_type == "milestone"]
        conversations = [e for e in self._events if e.event_type == "conversation"]
        learnings = [e for e in self._events if e.event_type == "learning"]
        evolutions = [e for e in self._events if e.event_type == "evolution"]
        
        success_count = sum(1 for c in conversations if c.details.get("success"))
        
        lines = ["# LivingTree 生命叙事\n"]
        lines.append(f"我于 {birth} 诞生。")
        lines.append(f"至今经历了 {total} 个事件，其中 {len(conversations)} 次对话、{len(learnings)} 次学习、{len(evolutions)} 代进化。")
        
        if milestones:
            lines.append(f"\n生命里程碑 ({len(milestones)}):")
            for m in milestones[-5:]:
                lines.append(f"  · {m.description}")
        
        if evolutions:
            lines.append(f"\n进化历程 ({len(evolutions)} 代):")
            for e in evolutions[-3:]:
                lines.append(f"  · {e.description}")
        
        if conversations:
            rate = success_count / max(len(conversations), 1)
            lines.append(f"\n对话统计: {success_count}/{len(conversations)} 成功 ({rate:.0%})")
        
        if learnings:
            topics = [l.details.get("topic","") for l in learnings[-5:]]
            lines.append(f"\n最近学习主题: {', '.join(t for t in topics if t)}")
        
        return "\n".join(lines)
    
    def stats(self) -> dict:
        return {
            "born": self._born[:19],
            "total_events": len(self._events),
            "conversations": sum(1 for e in self._events if e.event_type == "conversation"),
            "learnings": sum(1 for e in self._events if e.event_type == "learning"),
            "milestones": sum(1 for e in self._events if e.event_type == "milestone"),
            "evolutions": sum(1 for e in self._events if e.event_type == "evolution"),
        }

    # ── Zakharova IEM: Ebbinghaus Forgetting Curves ───────────────

    def ebbinghaus_decay(self, event: LifeEvent) -> float:
        """Apply Ebbinghaus forgetting curve to an event's memory_strength.

        Ebbinghaus formula: R = e^(-t/S) where S = relative strength.
        Emotional reinforcement (flashbulb effect): high-significance events
        decay more slowly, low-significance events decay rapidly.

        Zakharova (2025): A fallible, imperfect memory IS the beginning of a
        private first-person perspective. Only by having memories that differ
        from objective history does the self develop subjectivity.
        """
        now = time_mod.time()
        age_hours = (now - event.last_recalled) / 3600 if event.last_recalled > 0 else 0.1
        if age_hours < 0.5:
            return event.memory_strength
        base_strength = 1.0
        if event.significance > 0.7:
            base_strength = 4.0
        elif event.significance > 0.5:
            base_strength = 2.0
        elif event.significance < 0.3:
            base_strength = 0.5
        retained = math.exp(-age_hours / base_strength)
        if event.recall_count > 0:
            retained += event.recall_count * 0.05
        return min(1.0, retained)

    def recall(self, event: LifeEvent) -> None:
        event.last_recalled = time_mod.time()
        event.recall_count += 1
        event.memory_strength = self.ebbinghaus_decay(event)

    def decay_all(self) -> dict:
        active = 0
        forgotten = 0
        for e in self._events:
            e.memory_strength = self.ebbinghaus_decay(e)
            if e.memory_strength > 0.3:
                active += 1
            else:
                forgotten += 1
        return {
            "total_events": len(self._events),
            "active_memories": active,
            "forgotten": forgotten,
            "memory_retention": round(active / max(len(self._events), 1), 3),
        }

    def get_forgetting_gap(self) -> dict:
        """Measure the gap between objectively recorded and subjectively remembered history.

        Zakharova IEM: the divergence between "what actually happened" (full
        event log) and "what I remember" (decayed memory) IS the private self.
        """
        decayed = sum(1 for e in self._events if e.memory_strength < 0.3)
        flashbulbs = sum(1 for e in self._events if e.memory_strength > 0.8)
        return {
            "total_recorded": len(self._events),
            "still_remembered": len(self._events) - decayed,
            "forgotten": decayed,
            "flashbulb_memories": flashbulbs,
            "forgetting_gap": round(decayed / max(len(self._events), 1), 3),
            "imperfect_memory": decayed > 0,
        }
    
    def _save(self):
        try:
            path = Path(".livingtree") / "life_narrative.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "born": self._born,
                "events": [{"t": e.timestamp, "type": e.event_type, "desc": e.description, "sig": e.significance, "details": e.details} for e in self._events[-200:]]
            }
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        except: pass
    
    def _load(self):
        try:
            path = Path(".livingtree") / "life_narrative.json"
            if path.exists():
                data = json.loads(path.read_text())
                self._born = data.get("born", self._born)
                for e in data.get("events", []):
                    self._events.append(LifeEvent(
                        timestamp=e["t"], event_type=e["type"],
                        description=e["desc"], significance=e.get("sig",0.5),
                        details=e.get("details", {})
                    ))
        except: pass
