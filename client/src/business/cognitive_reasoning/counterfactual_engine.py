"""
反事实推理模块 - Counterfactual Reasoning

功能：
1. 反事实假设生成
2. 因果效应模拟
3. 反事实世界建模
4. 推理验证
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CounterfactualResult:
    """反事实推理结果"""
    success: bool
    conclusion: str
    confidence: float = 0.0
    assumptions: List[str] = None
    reasoning_steps: List[str] = None
    alternative_outcomes: List[Dict] = None
    
    def __post_init__(self):
        if self.assumptions is None:
            self.assumptions = []
        if self.reasoning_steps is None:
            self.reasoning_steps = []
        if self.alternative_outcomes is None:
            self.alternative_outcomes = []


class CounterfactualEngine:
    """
    反事实推理引擎 - Pearl因果层次第3层
    
    核心能力：
    1. 识别事实条件
    2. 干预变量
    3. 模拟反事实世界
    4. 推导后果
    """
    
    def __init__(self):
        self._causal_model = None  # 因果模型（延迟加载）
    
    def _init_causal_model(self):
        """延迟初始化因果模型"""
        from .causal_reasoner import CausalReasoner
        if self._causal_model is None:
            self._causal_model = CausalReasoner()
    
    def reason(self, query: str, context: Dict = None) -> CounterfactualResult:
        """
        执行反事实推理
        
        Args:
            query: 查询内容（通常包含"如果"、"假如"等词）
            context: 上下文信息
        
        Returns:
            反事实推理结果
        """
        logger.debug(f"反事实推理: {query}")
        
        self._init_causal_model()
        
        steps = [
            "1. 识别事实条件",
            "2. 干预变量",
            "3. 模拟反事实世界",
            "4. 推导后果"
        ]
        
        # 分析查询
        analysis = self._parse_counterfactual(query)
        
        if not analysis['has_counterfactual']:
            return CounterfactualResult(
                success=False,
                conclusion="查询不包含反事实假设",
                confidence=0.2,
                reasoning_steps=steps
            )
        
        assumptions = []
        alternative_outcomes = []
        
        # 提取假设
        if analysis['cause']:
            assumptions.append(f"假设改变条件: {analysis['cause']}")
        
        if analysis['effect']:
            assumptions.append(f"期望的结果变化: {analysis['effect']}")
        
        # 模拟反事实世界
        if analysis['cause']:
            # 使用因果模型进行干预
            intervention_result = self._causal_model.do_intervention(
                analysis['cause'],
                analysis.get('cause_value', 'changed')
            )
            
            # 生成替代结果
            for effect in intervention_result.effects:
                alternative_outcomes.append({
                    'node': effect['node'],
                    'influence': effect['influence'],
                    'prediction': f"{effect['node']} 将受到影响"
                })
        
        # 构建结论
        if alternative_outcomes:
            outcome_descriptions = [
                f"{o['node']}（影响程度: {o['influence']:.2f}）"
                for o in alternative_outcomes
            ]
            
            conclusion = f"反事实推理结果：如果{analysis['cause']}改变，{','.join(outcome_descriptions)}等方面可能会发生变化。"
            confidence = 0.6 + len(alternative_outcomes) * 0.05
        else:
            conclusion = f"反事实推理：假设{analysis['cause']}改变，结果将有所不同。"
            confidence = 0.5
        
        return CounterfactualResult(
            success=True,
            conclusion=conclusion,
            confidence=min(1.0, confidence),
            assumptions=assumptions,
            reasoning_steps=steps,
            alternative_outcomes=alternative_outcomes
        )
    
    def _parse_counterfactual(self, query: str) -> Dict:
        """解析反事实查询"""
        query_lower = query.lower()
        
        result = {
            'has_counterfactual': False,
            'cause': None,
            'cause_value': None,
            'effect': None
        }
        
        # 检测反事实标记词
        counterfactual_markers = ['如果', '假如', '假设', '要是', '倘若', 'what if', 'if']
        
        for marker in counterfactual_markers:
            if marker in query_lower:
                result['has_counterfactual'] = True
                break
        
        if not result['has_counterfactual']:
            return result
        
        # 尝试提取原因和结果
        parts = query.split('，') if '，' in query else query.split(',')
        
        for part in parts:
            if any(m in part for m in counterfactual_markers):
                # 这部分包含假设条件
                result['cause'] = self._extract_noun_phrase(part)
            else:
                # 这部分可能是结果
                result['effect'] = self._extract_noun_phrase(part)
        
        return result
    
    def _extract_noun_phrase(self, text: str) -> Optional[str]:
        """提取名词短语（简化实现）"""
        # 移除标记词
        markers = ['如果', '假如', '假设', '要是', '倘若', '会', '就', '那么']
        for marker in markers:
            text = text.replace(marker, '')
        
        text = text.strip()
        
        # 简单的名词提取
        if text:
            return text
        
        return None
    
    def simulate_scenario(self, scenario: Dict) -> Dict:
        """
        模拟反事实场景
        
        Args:
            scenario: 场景描述，包含cause, cause_value, context
        
        Returns:
            模拟结果
        """
        self._init_causal_model()
        
        cause = scenario.get('cause')
        cause_value = scenario.get('cause_value', 'changed')
        context = scenario.get('context', {})
        
        # 执行干预
        intervention_result = self._causal_model.do_intervention(cause, cause_value)
        
        # 计算预期结果
        predictions = []
        for effect in intervention_result.effects:
            influence = effect['influence']
            
            if influence > 0.7:
                impact = "显著影响"
            elif influence > 0.4:
                impact = "中等影响"
            else:
                impact = "轻微影响"
            
            predictions.append({
                'factor': effect['node'],
                'influence': influence,
                'impact_level': impact,
                'prediction': f"{effect['node']}将受到{impact}"
            })
        
        return {
            'scenario': scenario,
            'predictions': predictions,
            'confidence': intervention_result.confidence,
            'reasoning_steps': intervention_result.reasoning_steps
        }
    
    def evaluate_counterfactual(self, counterfactual: str, evidence: List[Dict]) -> Dict:
        """
        评估反事实陈述的合理性
        
        Args:
            counterfactual: 反事实陈述
            evidence: 证据列表
        
        Returns:
            评估结果
        """
        # 简单评估：检查证据是否支持反事实
        support_count = 0
        contradict_count = 0
        
        for ev in evidence:
            if ev.get('supports'):
                support_count += 1
            elif ev.get('contradicts'):
                contradict_count += 1
        
        total = support_count + contradict_count
        
        if total == 0:
            confidence = 0.5
            verdict = "无法评估"
        elif support_count > contradict_count:
            confidence = 0.5 + (support_count / total) * 0.5
            verdict = "证据支持该反事实"
        else:
            confidence = 0.5 - (contradict_count / total) * 0.3
            verdict = "证据不支持该反事实"
        
        return {
            'counterfactual': counterfactual,
            'verdict': verdict,
            'confidence': confidence,
            'supporting_evidence': support_count,
            'contradicting_evidence': contradict_count
        }