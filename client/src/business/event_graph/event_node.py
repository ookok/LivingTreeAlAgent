"""
EventGraph - 事件图谱

实现"以史为鉴"能力的核心组件：
- 构建事件图谱（主体-事件-结果）
- 扫描图谱，归纳因果规则
- 验证规则的置信度

借鉴人类文明的因果推理能力：
事件A → 因果链 → 事件B → 归纳规则 → 决策

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import time
from datetime import datetime


class EventType(Enum):
    """事件类型"""
    ACTION = "action"           # 主动行动
    REACTION = "reaction"       # 被动反应
    OCCURRENCE = "occurrence"   # 自然发生
    DECISION = "decision"       # 决策


class CausalConfidence(Enum):
    """因果置信度等级"""
    LOW = "low"           # 低 (<0.5)
    MEDIUM = "medium"     # 中 (0.5-0.8)
    HIGH = "high"         # 高 (>0.8)


@dataclass
class EventNode:
    """
    事件节点
    
    代表一个事件，包含主体、事件描述、结果和时间戳。
    """
    event_id: str              # 事件唯一ID
    subject: str               # 主体（如"罗马帝国"）
    event: str                 # 事件（如"过度扩张"）
    result: str                # 结果（如"崩溃"）
    event_type: EventType = EventType.OCCURRENCE
    timestamp: float = field(default_factory=lambda: time.time())
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0    # 事件真实性置信度
    
    @property
    def datetime(self) -> datetime:
        """获取事件时间"""
        return datetime.fromtimestamp(self.timestamp)


@dataclass
class CausalLink:
    """
    因果链接
    
    表示两个事件之间的因果关系。
    """
    cause_event_id: str    # 原因事件ID
    effect_event_id: str   # 结果事件ID
    confidence: float      # 因果置信度 (0-1)
    evidence: List[str] = field(default_factory=list)  # 证据支持
    explanation: str = ""  # 因果解释


@dataclass
class CausalRule:
    """
    因果规则
    
    从事件图谱中归纳出的可复用模式。
    """
    rule_id: str
    cause_pattern: str     # 原因模式（如"过度扩张"）
    effect_pattern: str    # 结果模式（如"帝国崩溃"）
    confidence: float      # 规则置信度 (0-1)
    supporting_count: int = 0    # 支持案例数
    contradicting_count: int = 0 # 矛盾案例数
    examples: List[str] = field(default_factory=list)
    
    @property
    def confidence_level(self) -> CausalConfidence:
        """获取置信度等级"""
        if self.confidence > 0.8:
            return CausalConfidence.HIGH
        elif self.confidence >= 0.5:
            return CausalConfidence.MEDIUM
        else:
            return CausalConfidence.LOW


class EventGraph:
    """
    事件图谱
    
    存储和管理事件及其因果关系，支持：
    1. 事件的添加和查询
    2. 因果链查询
    3. 规则归纳
    """
    
    def __init__(self):
        self._logger = logger.bind(component="EventGraph")
        self._events: Dict[str, EventNode] = {}
        self._causal_links: List[CausalLink] = []
        self._rules: List[CausalRule] = []
        
        # 预定义一些历史事件
        self._init_historical_events()
        
        self._logger.info("✅ EventGraph 初始化完成")
    
    def _init_historical_events(self):
        """初始化历史事件示例"""
        # 添加历史事件
        self.add_event("罗马帝国", "过度扩张", "财政危机", EventType.ACTION)
        self.add_event("罗马帝国", "财政危机", "军队叛乱", EventType.REACTION)
        self.add_event("罗马帝国", "军队叛乱", "帝国崩溃", EventType.OCCURRENCE)
        
        # 添加因果链接
        self.add_causal_link("罗马帝国_过度扩张", "罗马帝国_财政危机", 0.85)
        self.add_causal_link("罗马帝国_财政危机", "罗马帝国_军队叛乱", 0.9)
        self.add_causal_link("罗马帝国_军队叛乱", "罗马帝国_帝国崩溃", 0.95)
        
        # 添加另一个案例
        self.add_event("苏联", "经济僵化", "改革失败", EventType.OCCURRENCE)
        self.add_event("苏联", "改革失败", "解体", EventType.OCCURRENCE)
        self.add_causal_link("苏联_经济僵化", "苏联_改革失败", 0.8)
        self.add_causal_link("苏联_改革失败", "苏联_解体", 0.92)
    
    def _generate_event_id(self, subject: str, event: str) -> str:
        """生成事件ID"""
        return f"{subject}_{event}".replace(" ", "_")
    
    def add_event(self, subject: str, event: str, result: str, 
                  event_type: EventType = EventType.OCCURRENCE,
                  metadata: Dict[str, Any] = None) -> str:
        """
        添加事件到图谱
        
        Args:
            subject: 主体
            event: 事件描述
            result: 结果
            event_type: 事件类型
            metadata: 元数据
            
        Returns:
            事件ID
        """
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
        """获取事件"""
        return self._events.get(event_id)
    
    def add_causal_link(self, cause_event_id: str, effect_event_id: str, 
                        confidence: float = 0.7, evidence: str = ""):
        """
        添加因果链接
        
        Args:
            cause_event_id: 原因事件ID
            effect_event_id: 结果事件ID
            confidence: 置信度
            evidence: 支持证据
        """
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
        """
        查询事件的因果链（向上追溯原因）
        
        Args:
            event_id: 事件ID
            max_depth: 最大追溯深度
            
        Returns:
            因果链路径列表
        """
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
            
            # 找到导致当前事件的原因
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
        """
        查询事件的影响链（向下追溯结果）
        
        Args:
            event_id: 事件ID
            max_depth: 最大追溯深度
            
        Returns:
            影响链路径列表
        """
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
            
            # 找到当前事件导致的结果
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
        """
        从图谱中归纳因果规则
        
        Args:
            min_confidence: 最小置信度阈值
            
        Returns:
            归纳出的因果规则列表
        """
        rules = []
        
        # 统计模式频率
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
        
        # 生成规则
        for cause_pattern, effects in pattern_counts.items():
            total_count = sum(effects.values())
            
            for effect_pattern, count in effects.items():
                # 计算置信度（简单实现：支持率）
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
        
        # 按置信度排序
        rules.sort(key=lambda x: x.confidence, reverse=True)
        
        # 更新规则库
        self._rules = rules
        
        self._logger.info(f"🔍 归纳出 {len(rules)} 条因果规则")
        return rules
    
    def validate_rule(self, rule: CausalRule) -> float:
        """
        验证规则的置信度
        
        Args:
            rule: 待验证的规则
            
        Returns:
            更新后的置信度
        """
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
        """
        根据历史模式预测结果
        
        Args:
            event_description: 事件描述
            
        Returns:
            预测结果列表
        """
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
        """获取指定主体的所有事件"""
        return [event for event in self._events.values() if event.subject == subject]
    
    def get_all_events(self) -> List[EventNode]:
        """获取所有事件"""
        return list(self._events.values())
    
    def get_event_count(self) -> int:
        """获取事件数量"""
        return len(self._events)
    
    def get_rule_count(self) -> int:
        """获取规则数量"""
        return len(self._rules)


# 创建全局实例
event_graph = EventGraph()


def get_event_graph() -> EventGraph:
    """获取事件图谱实例"""
    return event_graph


# 测试函数
async def test_event_graph():
    """测试事件图谱"""
    import sys
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 EventGraph")
    print("=" * 60)
    
    graph = EventGraph()
    
    # 1. 测试因果链查询
    print("\n[1] 测试因果链查询...")
    chain = graph.query_causal_chain("罗马帝国_帝国崩溃")
    print(f"    ✓ 罗马帝国崩溃的因果链 ({len(chain)} 步):")
    for step in chain:
        print(f"      {'  ' * step['depth']}{step['event']} → {step['result']}")
    
    # 2. 测试影响链查询
    print("\n[2] 测试影响链查询...")
    chain = graph.query_effect_chain("罗马帝国_过度扩张")
    print(f"    ✓ 过度扩张的影响链 ({len(chain)} 步):")
    for step in chain:
        print(f"      {'  ' * step['depth']}{step['event']} → {step['result']}")
    
    # 3. 测试规则归纳
    print("\n[3] 测试规则归纳...")
    rules = graph.induce_rules(min_confidence=0.7)
    print(f"    ✓ 归纳出 {len(rules)} 条规则:")
    for rule in rules:
        print(f"      - {rule.cause_pattern} → {rule.effect_pattern} (置信度: {rule.confidence:.2f})")
    
    # 4. 测试结果预测
    print("\n[4] 测试结果预测...")
    predictions = graph.predict_outcome("某公司过度扩张")
    print(f"    ✓ 预测结果 ({len(predictions)} 条):")
    for pred in predictions:
        print(f"      - {pred['predicted_outcome']} (置信度: {pred['confidence']:.2f})")
    
    # 5. 测试规则验证
    print("\n[5] 测试规则验证...")
    if rules:
        new_confidence = graph.validate_rule(rules[0])
        print(f"    ✓ 规则验证后置信度: {new_confidence:.2f}")
    
    print("\n" + "=" * 60)
    print("🎉 所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_event_graph())