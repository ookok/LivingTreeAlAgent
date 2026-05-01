"""
符号推理模块 - Symbolic Reasoning

功能：
1. 规则引擎
2. 逻辑推理
3. 知识表示
4. 推理链构建
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Rule:
    """推理规则"""
    rule_id: str
    name: str
    conditions: Dict[str, Any]
    conclusions: Dict[str, Any]
    confidence: float = 0.8
    priority: int = 1


@dataclass
class SymbolicResult:
    """符号推理结果"""
    success: bool
    conclusion: Any
    confidence: float = 0.0
    matched_rules: List[str] = None
    reasoning_steps: List[str] = None
    
    def __post_init__(self):
        if self.matched_rules is None:
            self.matched_rules = []
        if self.reasoning_steps is None:
            self.reasoning_steps = []


class SymbolicEngine:
    """
    符号推理引擎 - 基于规则的推理
    
    核心能力：
    1. 规则匹配
    2. 前向链推理
    3. 逻辑演绎
    4. 知识查询
    """
    
    def __init__(self):
        self._rules: List[Rule] = []
        self._knowledge_base: Dict[str, Any] = {}
        
        # 初始化默认规则
        self._init_default_rules()
    
    def _init_default_rules(self):
        """初始化默认规则"""
        self._rules = [
            Rule(
                rule_id="rule_weather_mood",
                name="天气影响心情",
                conditions={"weather": ["sunny", "晴天"]},
                conclusions={"mood": "happy", "suggestion": "适合户外活动"},
                confidence=0.85,
                priority=1
            ),
            Rule(
                rule_id="rule_weather_activity",
                name="天气影响活动",
                conditions={"weather": ["rainy", "下雨", "雨天"]},
                conclusions={"activity": "stay_home", "suggestion": "适合室内活动"},
                confidence=0.9,
                priority=1
            ),
            Rule(
                rule_id="rule_mood_productivity",
                name="心情影响生产力",
                conditions={"mood": ["happy", "开心"]},
                conclusions={"productivity": "high", "expectation": "工作效率较高"},
                confidence=0.75,
                priority=2
            ),
            Rule(
                rule_id="rule_sleep_mood",
                name="睡眠影响心情",
                conditions={"sleep": ["good", "充足"]},
                conclusions={"mood": "positive", "outcome": "心情较好"},
                confidence=0.8,
                priority=1
            ),
            Rule(
                rule_id="rule_temperature_activity",
                name="温度影响活动",
                conditions={"temperature": ["hot", "炎热"]},
                conclusions={"activity": "indoor", "advice": "避免户外活动"},
                confidence=0.85,
                priority=1
            )
        ]
        
        # 初始化知识库
        self._knowledge_base = {
            'weather_conditions': ['sunny', 'rainy', 'cloudy', 'snowy', 'windy'],
            'mood_states': ['happy', 'sad', 'angry', 'calm', 'excited'],
            'activities': ['go_out', 'stay_home', 'work', 'play', 'exercise'],
            'sleep_quality': ['good', 'poor', 'average']
        }
    
    def add_rule(self, rule: Rule):
        """添加规则"""
        self._rules.append(rule)
        # 按优先级排序
        self._rules.sort(key=lambda r: r.priority, reverse=True)
        logger.info(f"添加规则: {rule.name}")
    
    def add_knowledge(self, key: str, value: Any):
        """添加知识"""
        self._knowledge_base[key] = value
    
    def reason(self, query: str, context: Dict = None) -> SymbolicResult:
        """
        执行符号推理
        
        Args:
            query: 查询内容
            context: 上下文信息
        
        Returns:
            推理结果
        """
        logger.debug(f"符号推理: {query}")
        
        query_lower = query.lower()
        context = context or {}
        
        steps = []
        matched_rules = []
        conclusions = []
        
        steps.append("1. 解析查询")
        
        # 匹配规则
        for rule in self._rules:
            if self._match_rule(rule, query_lower, context):
                matched_rules.append(rule.rule_id)
                conclusions.append(rule.conclusions)
        
        if matched_rules:
            steps.append(f"2. 匹配到 {len(matched_rules)} 条规则")
            steps.append("3. 应用推理规则")
            
            # 合并结论
            merged_conclusions = {}
            for conclusion in conclusions:
                merged_conclusions.update(conclusion)
            
            confidence = self._calculate_confidence(matched_rules)
            
            return SymbolicResult(
                success=True,
                conclusion=merged_conclusions,
                confidence=confidence,
                matched_rules=matched_rules,
                reasoning_steps=steps
            )
        else:
            steps.append("2. 未匹配到明确规则")
            
            # 尝试知识库查询
            knowledge_result = self._query_knowledge(query_lower)
            if knowledge_result:
                steps.append("3. 知识库查询成功")
                return SymbolicResult(
                    success=True,
                    conclusion=knowledge_result,
                    confidence=0.6,
                    matched_rules=[],
                    reasoning_steps=steps
                )
            
            return SymbolicResult(
                success=False,
                conclusion="没有匹配到明确规则，需要更多信息",
                confidence=0.3,
                matched_rules=[],
                reasoning_steps=steps
            )
    
    def _match_rule(self, rule: Rule, query: str, context: Dict) -> bool:
        """检查规则是否匹配"""
        for key, values in rule.conditions.items():
            # 检查查询中是否包含条件
            if any(v.lower() in query for v in values):
                return True
            
            # 检查上下文
            if key in context and context[key] in values:
                return True
        
        return False
    
    def _calculate_confidence(self, matched_rules: List[str]) -> float:
        """计算置信度"""
        if not matched_rules:
            return 0.0
        
        total_confidence = 0.0
        for rule_id in matched_rules:
            rule = next((r for r in self._rules if r.rule_id == rule_id), None)
            if rule:
                total_confidence += rule.confidence
        
        return min(1.0, total_confidence / len(matched_rules))
    
    def _query_knowledge(self, query: str) -> Optional[Dict]:
        """查询知识库"""
        for key, value in self._knowledge_base.items():
            if key.lower() in query:
                return {key: value}
        
        return None
    
    def get_rules(self) -> List[Rule]:
        """获取所有规则"""
        return self._rules
    
    def get_knowledge(self) -> Dict:
        """获取知识库"""
        return self._knowledge_base
    
    def forward_chain(self, facts: Dict[str, Any]) -> Dict:
        """
        前向链推理
        
        Args:
            facts: 初始事实
        
        Returns:
            推理得出的结论
        """
        conclusions = facts.copy()
        changed = True
        iterations = 0
        
        while changed and iterations < 10:
            changed = False
            iterations += 1
            
            for rule in self._rules:
                # 检查规则条件是否满足
                conditions_met = all(
                    key in conclusions and conclusions[key] in values
                    for key, values in rule.conditions.items()
                )
                
                if conditions_met:
                    # 应用结论
                    for key, value in rule.conclusions.items():
                        if key not in conclusions:
                            conclusions[key] = value
                            changed = True
        
        return conclusions
    
    def backward_chain(self, goal: str, facts: Dict[str, Any]) -> bool:
        """
        后向链推理
        
        Args:
            goal: 目标
            facts: 当前事实
        
        Returns:
            是否可以达到目标
        """
        # 检查目标是否已在事实中
        if goal in facts:
            return True
        
        # 查找可以推导出目标的规则
        for rule in self._rules:
            if goal in rule.conclusions:
                # 检查规则条件是否可以满足
                conditions_met = True
                for cond_key, cond_values in rule.conditions.items():
                    if cond_key not in facts:
                        # 递归检查条件
                        if not self.backward_chain(cond_key, facts):
                            conditions_met = False
                    elif facts[cond_key] not in cond_values:
                        conditions_met = False
                
                if conditions_met:
                    facts[goal] = rule.conclusions[goal]
                    return True
        
        return False