"""
EventGraph - 事件图谱

实现"以史为鉴"能力的核心组件：
- 构建事件图谱（主体-事件-结果）
- 扫描图谱，归纳因果规则
- 验证规则的置信度

借鉴人类文明的因果推理能力：
事件A → 因果链 → 事件B → 归纳规则 → 决策
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import time
from datetime import datetime


class EventType(Enum):
    ACTION = "action"
    REACTION = "reaction"
    OCCURRENCE = "occurrence"
    DECISION = "decision"


class CausalConfidence(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class EventNode:
    event_id: str
    subject: str
    event: str
    result: str
    event_type: EventType = EventType.OCCURRENCE
    timestamp: float = field(default_factory=lambda: time.time())
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0

    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp)


@dataclass
class CausalLink:
    cause_event_id: str
    effect_event_id: str
    confidence: float
    evidence: List[str] = field(default_factory=list)
    explanation: str = ""


@dataclass
class CausalRule:
    rule_id: str
    cause_pattern: str
    effect_pattern: str
    confidence: float
    supporting_count: int = 0
    contradicting_count: int = 0
    examples: List[str] = field(default_factory=list)

    @property
    def confidence_level(self) -> CausalConfidence:
        if self.confidence > 0.8:
            return CausalConfidence.HIGH
        elif self.confidence >= 0.5:
            return CausalConfidence.MEDIUM
        else:
            return CausalConfidence.LOW


class EventGraph:

    def __init__(self):
        self._logger = logger.bind(component="EventGraph")
        self._events: Dict[str, EventNode] = {}
        self._causal_links: List[CausalLink] = []
        self._rules: List[CausalRule] = []

        self._init_historical_events()
        self._logger.info("✅ EventGraph 初始化完成")

    def _init_historical_events(self):
        self.add_event("罗马帝国", "过度扩张", "财政危机", EventType.ACTION)
        self.add_event("罗马帝国", "财政危机", "军队叛乱", EventType.REACTION)
        self.add_event("罗马帝国", "军队叛乱", "帝国崩溃", EventType.OCCURRENCE)

        self.add_causal_link("罗马帝国_过度扩张", "罗马帝国_财政危机", 0.85)
        self.add_causal_link("罗马帝国_财政危机", "罗马帝国_军队叛乱", 0.9)
        self.add_causal_link("罗马帝国_军队叛乱", "罗马帝国_帝国崩溃", 0.95)

        self.add_event("苏联", "经济僵化", "改革失败", EventType.OCCURRENCE)
        self.add_event("苏联", "改革失败", "解体", EventType.OCCURRENCE)
        self.add_causal_link("苏联_经济僵化", "苏联_改革失败", 0.8)
        self.add_causal_link("苏联_改革失败", "苏联_解体", 0.92)

    def _generate_event_id(self, subject: str, event: str) -> str:
        return f"{subject}_{event}".replace(" ", "_")

    def add_event(self, subject: str, event: str, result: str,
                  event_type: EventType = EventType.OCCURRENCE,
                  metadata: Dict[str, Any] = None) -> str:
        event_id = self._generate_event_id(subject, event)

        if event_id in self._events:
            self._logger.warning(f"事件已存在: {event_id}")
            return event_id

        event_node = EventNode(
            event_id=event_id,
            subject=subject,
            event=event,
            result=result,
            event_type=event_type,
            metadata=metadata or {}
        )

        self._events[event_id] = event_node
        self._logger.debug(f"➕ 添加事件: {event_id} -> {result}")

        return event_id

    def get_event(self, event_id: str) -> Optional[EventNode]:
        return self._events.get(event_id)

    def add_causal_link(self, cause_event_id: str, effect_event_id: str,
                        confidence: float = 0.7, evidence: str = ""):
        if cause_event_id not in self._events:
            self._logger.warning(f"原因事件不存在: {cause_event_id}")
            return

        if effect_event_id not in self._events:
            self._logger.warning(f"结果事件不存在: {effect_event_id}")
            return

        link = CausalLink(
            cause_event_id=cause_event_id,
            effect_event_id=effect_event_id,
            confidence=confidence,
            evidence=[evidence] if evidence else []
        )

        self._causal_links.append(link)
        self._logger.debug(f"🔗 添加因果链接: {cause_event_id} -> {effect_event_id} ({confidence})")

    def query_causal_chain(self, event_id: str, max_depth: int = 5) -> List[Dict[str, Any]]:
        chain = []
        current_event_id = event_id
        depth = 0

        while current_event_id and depth < max_depth:
            event = self._events.get(current_event_id)
            if not event:
                break

            chain.append({
                "event_id": current_event_id,
                "subject": event.subject,
                "event": event.event,
                "result": event.result,
                "depth": depth
            })

            found = False
            for link in self._causal_links:
                if link.effect_event_id == current_event_id:
                    current_event_id = link.cause_event_id
                    found = True
                    break

            if not found:
                break

            depth += 1

        return chain

    def query_effect_chain(self, event_id: str, max_depth: int = 5) -> List[Dict[str, Any]]:
        chain = []
        current_event_id = event_id
        depth = 0

        while current_event_id and depth < max_depth:
            event = self._events.get(current_event_id)
            if not event:
                break

            chain.append({
                "event_id": current_event_id,
                "subject": event.subject,
                "event": event.event,
                "result": event.result,
                "depth": depth
            })

            found = False
            for link in self._causal_links:
                if link.cause_event_id == current_event_id:
                    current_event_id = link.effect_event_id
                    found = True
                    break

            if not found:
                break

            depth += 1

        return chain

    def induce_rules(self, min_confidence: float = 0.6) -> List[CausalRule]:
        rules = []
        pattern_counts: Dict[str, Dict[str, int]] = {}

        for link in self._causal_links:
            cause_event = self._events.get(link.cause_event_id)
            effect_event = self._events.get(link.effect_event_id)

            if not cause_event or not effect_event:
                continue

            cause_pattern = cause_event.event
            effect_pattern = effect_event.result

            if cause_pattern not in pattern_counts:
                pattern_counts[cause_pattern] = {}

            if effect_pattern not in pattern_counts[cause_pattern]:
                pattern_counts[cause_pattern][effect_pattern] = 0

            pattern_counts[cause_pattern][effect_pattern] += 1

        for cause_pattern, effects in pattern_counts.items():
            total_count = sum(effects.values())

            for effect_pattern, count in effects.items():
                confidence = count / total_count

                if confidence >= min_confidence:
                    rule = CausalRule(
                        rule_id=f"{cause_pattern}->{effect_pattern}",
                        cause_pattern=cause_pattern,
                        effect_pattern=effect_pattern,
                        confidence=confidence,
                        supporting_count=count,
                        contradicting_count=total_count - count,
                        examples=[f"{cause_pattern} → {effect_pattern}"]
                    )
                    rules.append(rule)

        rules.sort(key=lambda x: x.confidence, reverse=True)
        self._rules = rules
        self._logger.info(f"🔍 归纳出 {len(rules)} 条因果规则")
        return rules

    def validate_rule(self, rule: CausalRule) -> float:
        supporting = 0
        contradicting = 0

        for link in self._causal_links:
            cause_event = self._events.get(link.cause_event_id)
            effect_event = self._events.get(link.effect_event_id)

            if not cause_event or not effect_event:
                continue

            if cause_event.event == rule.cause_pattern:
                if effect_event.result == rule.effect_pattern:
                    supporting += 1
                else:
                    contradicting += 1

        total = supporting + contradicting
        if total == 0:
            return 0.0

        new_confidence = supporting / total
        rule.confidence = new_confidence
        rule.supporting_count = supporting
        rule.contradicting_count = contradicting

        self._logger.debug(f"✅ 验证规则: {rule.rule_id} -> 置信度: {new_confidence:.2f}")

        return new_confidence

    def predict_outcome(self, event_description: str) -> List[Dict[str, Any]]:
        predictions = []

        for rule in self._rules:
            if rule.cause_pattern in event_description:
                predictions.append({
                    "predicted_outcome": rule.effect_pattern,
                    "confidence": rule.confidence,
                    "rule_id": rule.rule_id,
                    "supporting_examples": rule.supporting_count
                })

        predictions.sort(key=lambda x: x["confidence"], reverse=True)
        return predictions

    def get_events_by_subject(self, subject: str) -> List[EventNode]:
        return [event for event in self._events.values() if event.subject == subject]

    def get_all_events(self) -> List[EventNode]:
        return list(self._events.values())

    def get_event_count(self) -> int:
        return len(self._events)

    def get_rule_count(self) -> int:
        return len(self._rules)


event_graph = EventGraph()


def get_event_graph() -> EventGraph:
    return event_graph
