"""
推理协调器 - Reasoning Coordinator

功能：
1. 推理类型识别
2. 推理器选择
3. 多推理器协作
4. 结果融合
"""

import time
from typing import Dict, List, Any, Optional
from enum import Enum
from loguru import logger


class ReasoningType(Enum):
    """推理类型"""
    CAUSAL = "causal"           # 因果推理
    SYMBOLIC = "symbolic"       # 符号推理
    ANALOGICAL = "analogical"   # 类比推理
    COUNTERFACTUAL = "counterfactual"  # 反事实推理
    HYBRID = "hybrid"           # 混合推理


class ReasoningCoordinator:
    """
    推理协调器 - 协调多种推理器的工作
    
    核心能力：
    1. 根据查询意图选择合适的推理器
    2. 协调多个推理器协作
    3. 融合多个推理器的结果
    4. 提供统一的推理接口
    """
    
    def __init__(self):
        self._logger = logger.bind(component="ReasoningCoordinator")
        
        # 延迟加载推理器
        self._causal_reasoner = None
        self._symbolic_engine = None
        self._analogical_reasoner = None
        self._counterfactual_engine = None
    
    def _init_reasoners(self):
        """延迟初始化推理器"""
        if self._causal_reasoner is None:
            from .causal_reasoner import CausalReasoner
            from .symbolic_engine import SymbolicEngine
            from .analogical_reasoner import AnalogicalReasoner
            from .counterfactual_engine import CounterfactualEngine
            
            self._causal_reasoner = CausalReasoner()
            self._symbolic_engine = SymbolicEngine()
            self._analogical_reasoner = AnalogicalReasoner()
            self._counterfactual_engine = CounterfactualEngine()
            
            self._logger.info("推理器初始化完成")
    
    def _detect_reasoning_type(self, query: str) -> ReasoningType:
        """
        根据查询检测推理类型
        
        Args:
            query: 查询内容
        
        Returns:
            推理类型
        """
        query_lower = query.lower()
        
        # 检测反事实推理
        counterfactual_markers = ['如果', '假如', '假设', '要是', '倘若', 'what if', 'if']
        if any(marker in query_lower for marker in counterfactual_markers):
            return ReasoningType.COUNTERFACTUAL
        
        # 检测因果推理
        causal_markers = ['因为', '所以', '导致', '原因', '影响', '为什么', 'why', 'because']
        if any(marker in query_lower for marker in causal_markers):
            return ReasoningType.CAUSAL
        
        # 检测类比推理
        analogy_markers = ['类似', '好比', '如同', '比如', '例如', '类比', 'analogy', 'like']
        if any(marker in query_lower for marker in analogy_markers):
            return ReasoningType.ANALOGICAL
        
        # 默认使用混合推理
        return ReasoningType.HYBRID
    
    def reason(self, query: str, reasoning_type: str = None) -> Dict:
        """
        统一推理接口
        
        Args:
            query: 查询内容
            reasoning_type: 推理类型（可选，自动检测）
        
        Returns:
            推理结果
        """
        self._init_reasoners()
        
        # 确定推理类型
        if reasoning_type:
            try:
                reason_type = ReasoningType(reasoning_type.lower())
            except ValueError:
                self._logger.warning(f"无效的推理类型: {reasoning_type}，使用自动检测")
                reason_type = self._detect_reasoning_type(query)
        else:
            reason_type = self._detect_reasoning_type(query)
        
        self._logger.debug(f"推理类型: {reason_type.value}")
        
        # 根据类型选择推理器
        if reason_type == ReasoningType.CAUSAL:
            return self._causal_reason(query)
        elif reason_type == ReasoningType.SYMBOLIC:
            return self._symbolic_reason(query)
        elif reason_type == ReasoningType.ANALOGICAL:
            return self._analogical_reason(query)
        elif reason_type == ReasoningType.COUNTERFACTUAL:
            return self._counterfactual_reason(query)
        else:
            return self._hybrid_reason(query)
    
    def _causal_reason(self, query: str) -> Dict:
        """因果推理"""
        result = self._causal_reasoner.reason(query)
        
        return {
            'type': 'causal',
            'result': result.get('result', ''),
            'confidence': result.get('confidence', 0.0),
            'steps': result.get('steps', []),
            'related_nodes': result.get('related_nodes', [])
        }
    
    def _symbolic_reason(self, query: str) -> Dict:
        """符号推理"""
        result = self._symbolic_engine.reason(query)
        
        return {
            'type': 'symbolic',
            'result': result.conclusion,
            'confidence': result.confidence,
            'matched_rules': result.matched_rules,
            'steps': result.reasoning_steps
        }
    
    def _analogical_reason(self, query: str) -> Dict:
        """类比推理"""
        # 简单处理：尝试从查询中提取源域和目标域
        query_lower = query.lower()
        
        # 查找类比标记
        analogy_markers = ['类似', '好比', '如同']
        marker_pos = -1
        marker = ''
        
        for m in analogy_markers:
            pos = query_lower.find(m)
            if pos != -1:
                marker_pos = pos
                marker = m
                break
        
        if marker_pos != -1:
            source = query[:marker_pos].strip()
            target = query[marker_pos + len(marker):].strip()
        else:
            # 默认处理
            source = query
            target = query
        
        result = self._analogical_reasoner.reason(source, target, query)
        
        return {
            'type': 'analogical',
            'result': result.conclusion,
            'confidence': result.confidence,
            'mappings': [
                {'source': m.source_element, 'target': m.target_element, 'similarity': m.similarity}
                for m in result.mappings
            ],
            'steps': result.reasoning_steps
        }
    
    def _counterfactual_reason(self, query: str) -> Dict:
        """反事实推理"""
        result = self._counterfactual_engine.reason(query)
        
        return {
            'type': 'counterfactual',
            'result': result.conclusion,
            'confidence': result.confidence,
            'assumptions': result.assumptions,
            'alternative_outcomes': result.alternative_outcomes,
            'steps': result.reasoning_steps
        }
    
    def _hybrid_reason(self, query: str) -> Dict:
        """
        混合推理 - 综合使用多种推理器
        
        策略：
        1. 首先尝试符号推理（规则匹配）
        2. 如果置信度不足，尝试因果推理
        3. 最后尝试类比推理
        """
        results = []
        
        # 符号推理
        symbolic_result = self._symbolic_engine.reason(query)
        results.append({
            'type': 'symbolic',
            'result': symbolic_result.conclusion,
            'confidence': symbolic_result.confidence
        })
        
        # 如果符号推理置信度不足，尝试因果推理
        if symbolic_result.confidence < 0.7:
            causal_result = self._causal_reasoner.reason(query)
            results.append({
                'type': 'causal',
                'result': causal_result.get('result', ''),
                'confidence': causal_result.get('confidence', 0.0)
            })
        
        # 如果仍然不足，尝试类比推理
        if all(r['confidence'] < 0.6 for r in results):
            analogy_result = self._analogical_reasoner.reason(query, query)
            results.append({
                'type': 'analogical',
                'result': analogy_result.conclusion,
                'confidence': analogy_result.confidence
            })
        
        # 融合结果
        best_result = max(results, key=lambda x: x['confidence'])
        
        return {
            'type': 'hybrid',
            'result': best_result['result'],
            'confidence': best_result['confidence'],
            'primary_source': best_result['type'],
            'all_results': results
        }
    
    def do_intervention(self, node: str, value: Any) -> Dict:
        """
        执行干预操作
        
        Args:
            node: 节点
            value: 干预值
        
        Returns:
            干预结果
        """
        self._init_reasoners()
        
        result = self._causal_reasoner.do_intervention(node, value)
        
        return {
            'intervened_node': result.intervened_node,
            'intervention_value': result.intervention_value,
            'effects': result.effects,
            'confidence': result.confidence,
            'steps': result.reasoning_steps
        }
    
    def add_rule(self, rule: Dict):
        """添加推理规则"""
        self._init_reasoners()
        self._symbolic_engine.add_rule(rule)
    
    def add_causal_relation(self, cause: str, effect: str, weight: float = 0.5):
        """添加因果关系"""
        self._init_reasoners()
        self._causal_reasoner.add_causal_relation(cause, effect, weight)
    
    def get_causal_graph(self) -> Dict:
        """获取因果图"""
        self._init_reasoners()
        return self._causal_reasoner.get_causal_graph()
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            'reasoning_types': [rt.value for rt in ReasoningType],
            'description': {
                'causal': '因果推理 - 基于因果图的推理',
                'symbolic': '符号推理 - 基于规则的推理',
                'analogical': '类比推理 - 基于结构映射的推理',
                'counterfactual': '反事实推理 - 基于假设的推理',
                'hybrid': '混合推理 - 综合多种推理方式'
            }
        }


# 单例模式
_coordinator_instance = None

def get_reasoning_coordinator() -> ReasoningCoordinator:
    """获取推理协调器实例"""
    global _coordinator_instance
    if _coordinator_instance is None:
        _coordinator_instance = ReasoningCoordinator()
    return _coordinator_instance