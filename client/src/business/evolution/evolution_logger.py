from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import json
import os
from collections import defaultdict

class EvolutionEventType(Enum):
    POLICY_UPDATE = "policy_update"
    SKILL_LEARNED = "skill_learned"
    SKILL_IMPROVED = "skill_improved"
    INSIGHT_DISCOVERED = "insight_discovered"
    FEEDBACK_RECEIVED = "feedback_received"
    EXPERIENCE_RECORDED = "experience_recorded"
    STRATEGY_CHANGE = "strategy_change"
    MEMORY_UPDATED = "memory_updated"
    SELF_REFLECTION = "self_reflection"

class EvolutionImpact(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class EvolutionEvent:
    event_id: str
    event_type: EvolutionEventType
    timestamp: datetime
    description: str
    details: Dict[str, Any]
    impact: EvolutionImpact
    confidence: float = 0.8
    related_entities: List[str] = field(default_factory=list)

@dataclass
class EvolutionPhase:
    phase_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    events: List[EvolutionEvent] = field(default_factory=list)
    summary: Optional[str] = None

class EvolutionLogger:
    def __init__(self, storage_path: str = "./data/evolution"):
        self.storage_path = storage_path
        self.events: List[EvolutionEvent] = []
        self.phases: Dict[str, EvolutionPhase] = {}
        self.current_phase: Optional[EvolutionPhase] = None
        os.makedirs(storage_path, exist_ok=True)
        self._load_events()
        self._load_phases()
    
    def _load_events(self):
        events_file = os.path.join(self.storage_path, "events.json")
        if os.path.exists(events_file):
            try:
                with open(events_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.events = [self._event_from_dict(d) for d in data]
            except Exception as e:
                print(f"Error loading events: {e}")
    
    def _load_phases(self):
        phases_file = os.path.join(self.storage_path, "phases.json")
        if os.path.exists(phases_file):
            try:
                with open(phases_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for phase_data in data:
                        phase = self._phase_from_dict(phase_data)
                        self.phases[phase.phase_id] = phase
            except Exception as e:
                print(f"Error loading phases: {e}")
    
    def _save_events(self):
        events_file = os.path.join(self.storage_path, "events.json")
        with open(events_file, 'w', encoding='utf-8') as f:
            json.dump([self._event_to_dict(e) for e in self.events], f, indent=2, default=str)
    
    def _save_phases(self):
        phases_file = os.path.join(self.storage_path, "phases.json")
        with open(phases_file, 'w', encoding='utf-8') as f:
            json.dump([self._phase_to_dict(p) for p in self.phases.values()], f, indent=2, default=str)
    
    def _event_to_dict(self, event: EvolutionEvent) -> Dict[str, Any]:
        return {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "timestamp": event.timestamp.isoformat(),
            "description": event.description,
            "details": event.details,
            "impact": event.impact.value,
            "confidence": event.confidence,
            "related_entities": event.related_entities
        }
    
    def _event_from_dict(self, data: Dict[str, Any]) -> EvolutionEvent:
        return EvolutionEvent(
            event_id=data["event_id"],
            event_type=EvolutionEventType(data["event_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            description=data["description"],
            details=data["details"],
            impact=EvolutionImpact(data["impact"]),
            confidence=data.get("confidence", 0.8),
            related_entities=data.get("related_entities", [])
        )
    
    def _phase_to_dict(self, phase: EvolutionPhase) -> Dict[str, Any]:
        return {
            "phase_id": phase.phase_id,
            "start_time": phase.start_time.isoformat(),
            "end_time": phase.end_time.isoformat() if phase.end_time else None,
            "events": [self._event_to_dict(e) for e in phase.events],
            "summary": phase.summary
        }
    
    def _phase_from_dict(self, data: Dict[str, Any]) -> EvolutionPhase:
        return EvolutionPhase(
            phase_id=data["phase_id"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]) if data["end_time"] else None,
            events=[self._event_from_dict(e) for e in data.get("events", [])],
            summary=data.get("summary")
        )
    
    def start_phase(self, phase_id: str):
        self.current_phase = EvolutionPhase(
            phase_id=phase_id,
            start_time=datetime.now()
        )
        self.phases[phase_id] = self.current_phase
    
    def end_phase(self, summary: Optional[str] = None):
        if self.current_phase:
            self.current_phase.end_time = datetime.now()
            self.current_phase.summary = summary
            self._save_phases()
    
    def log_event(
        self,
        event_type: EvolutionEventType,
        description: str,
        details: Dict[str, Any] = None,
        impact: EvolutionImpact = EvolutionImpact.MEDIUM,
        confidence: float = 0.8,
        related_entities: List[str] = None
    ):
        event_id = f"event_{int(datetime.now().timestamp())}_{len(self.events)}"
        event = EvolutionEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp=datetime.now(),
            description=description,
            details=details or {},
            impact=impact,
            confidence=confidence,
            related_entities=related_entities or []
        )
        
        self.events.append(event)
        
        if self.current_phase:
            self.current_phase.events.append(event)
        
        self._save_events()
        self._save_phases()
        
        return event_id
    
    def log_policy_update(self, policy_name: str, changes: Dict[str, Any]):
        return self.log_event(
            event_type=EvolutionEventType.POLICY_UPDATE,
            description=f"策略更新: {policy_name}",
            details={"policy_name": policy_name, "changes": changes},
            impact=EvolutionImpact.HIGH,
            related_entities=[policy_name]
        )
    
    def log_skill_learned(self, skill_name: str, skill_info: Dict[str, Any]):
        return self.log_event(
            event_type=EvolutionEventType.SKILL_LEARNED,
            description=f"学习新技能: {skill_name}",
            details={"skill_name": skill_name, "skill_info": skill_info},
            impact=EvolutionImpact.HIGH,
            related_entities=[skill_name]
        )
    
    def log_skill_improved(self, skill_name: str, improvement: str):
        return self.log_event(
            event_type=EvolutionEventType.SKILL_IMPROVED,
            description=f"技能改进: {skill_name}",
            details={"skill_name": skill_name, "improvement": improvement},
            impact=EvolutionImpact.MEDIUM,
            related_entities=[skill_name]
        )
    
    def log_insight(self, insight_id: str, insight_data: Dict[str, Any]):
        return self.log_event(
            event_type=EvolutionEventType.INSIGHT_DISCOVERED,
            description=f"发现新洞察: {insight_data.get('description', insight_id)}",
            details={"insight_id": insight_id, "insight_data": insight_data},
            impact=EvolutionImpact.MEDIUM,
            confidence=insight_data.get("confidence", 0.8),
            related_entities=[insight_data.get("policy_name", "")]
        )
    
    def log_feedback(self, feedback_type: str, rating: Optional[int] = None):
        impact = EvolutionImpact.HIGH if rating and rating < 3 else EvolutionImpact.MEDIUM
        return self.log_event(
            event_type=EvolutionEventType.FEEDBACK_RECEIVED,
            description=f"收到{'负面' if rating and rating < 3 else ''}反馈",
            details={"feedback_type": feedback_type, "rating": rating},
            impact=impact
        )
    
    def log_experience(self, experience_id: str, task_type: str, success: bool):
        impact = EvolutionImpact.LOW
        if not success:
            impact = EvolutionImpact.MEDIUM
        
        return self.log_event(
            event_type=EvolutionEventType.EXPERIENCE_RECORDED,
            description=f"记录经验: {'成功' if success else '失败'} - {task_type}",
            details={"experience_id": experience_id, "task_type": task_type, "success": success},
            impact=impact,
            related_entities=[experience_id]
        )
    
    def log_strategy_change(self, strategy_name: str, old_value: Any, new_value: Any):
        return self.log_event(
            event_type=EvolutionEventType.STRATEGY_CHANGE,
            description=f"策略变更: {strategy_name}",
            details={"strategy_name": strategy_name, "old_value": old_value, "new_value": new_value},
            impact=EvolutionImpact.HIGH
        )
    
    def log_memory_update(self, memory_type: str, update_info: Dict[str, Any]):
        return self.log_event(
            event_type=EvolutionEventType.MEMORY_UPDATED,
            description=f"记忆更新: {memory_type}",
            details={"memory_type": memory_type, "update_info": update_info},
            impact=EvolutionImpact.LOW
        )
    
    def log_reflection(self, reflection_summary: str):
        return self.log_event(
            event_type=EvolutionEventType.SELF_REFLECTION,
            description="自我反思",
            details={"summary": reflection_summary},
            impact=EvolutionImpact.MEDIUM
        )
    
    def get_recent_events(self, limit: int = 20) -> List[EvolutionEvent]:
        return sorted(self.events, key=lambda x: x.timestamp, reverse=True)[:limit]
    
    def get_events_by_type(self, event_type: EvolutionEventType) -> List[EvolutionEvent]:
        return [e for e in self.events if e.event_type == event_type]
    
    def get_events_by_impact(self, impact: EvolutionImpact) -> List[EvolutionEvent]:
        return [e for e in self.events if e.impact == impact]
    
    def get_evolution_summary(self, days: int = 7) -> Dict[str, Any]:
        cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)
        
        recent_events = [
            e for e in self.events 
            if e.timestamp.timestamp() >= cutoff_time
        ]
        
        event_counts = defaultdict(int)
        impact_counts = defaultdict(int)
        
        for event in recent_events:
            event_counts[event.event_type.value] += 1
            impact_counts[event.impact.value] += 1
        
        return {
            "total_events": len(recent_events),
            "events_by_type": dict(event_counts),
            "events_by_impact": dict(impact_counts),
            "period_days": days,
            "top_entities": self._get_top_entities(recent_events)
        }
    
    def _get_top_entities(self, events: List[EvolutionEvent]) -> List[str]:
        entity_counts = defaultdict(int)
        for event in events:
            for entity in event.related_entities:
                if entity:
                    entity_counts[entity] += 1
        
        return [entity for entity, _ in sorted(entity_counts.items(), key=lambda x: -x[1])[:5]]
    
    def get_phase_events(self, phase_id: str) -> List[EvolutionEvent]:
        phase = self.phases.get(phase_id)
        return phase.events if phase else []
    
    def get_all_phases(self) -> List[EvolutionPhase]:
        return sorted(self.phases.values(), key=lambda x: x.start_time, reverse=True)
    
    def export_logs(self, filepath: Optional[str] = None) -> str:
        export_data = {
            "events": [self._event_to_dict(e) for e in self.events],
            "phases": [self._phase_to_dict(p) for p in self.phases.values()],
            "export_time": datetime.now().isoformat()
        }
        
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, default=str)
            return filepath
        
        return json.dumps(export_data, indent=2, default=str)
