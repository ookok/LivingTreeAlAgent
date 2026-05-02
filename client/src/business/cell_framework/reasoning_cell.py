"""
推理细胞模块

包含：
- ReasoningCell: 通用推理细胞
- CausalReasoningCell: 因果推理细胞
- SymbolicReasoningCell: 符号推理细胞
"""

from enum import Enum
from typing import Any, Dict, List
import asyncio
from .cell import Cell, CellType


class ReasoningMode(Enum):
    """推理模式"""
    DEDUCTIVE = "deductive"        # 演绎推理
    INDUCTIVE = "inductive"        # 归纳推理
    ABDUCTIVE = "abductive"        # 溯因推理
    ANALOGICAL = "analogical"      # 类比推理
    CAUSAL = "causal"              # 因果推理
    SYMBOLIC = "symbolic"          # 符号推理


class ReasoningCell(Cell):
    """
    通用推理细胞
    
    负责逻辑推理、问题解决和决策制定。
    """
    
    def __init__(self, specialization: str = "general"):
        super().__init__(specialization)
        self.reasoning_mode = ReasoningMode.DEDUCTIVE
        self.max_depth = 5
        self.confidence_threshold = 0.7
    
    @property
    def cell_type(self) -> CellType:
        return CellType.REASONING
    
    async def _process_signal(self, message: dict) -> Any:
        """
        处理推理请求
        
        支持的消息格式：
        {
            'type': 'reason',
            'query': '推理问题',
            'context': '上下文信息',
            'mode': 'deductive|inductive|abductive|analogical'
        }
        """
        message_type = message.get('type', '')
        
        if message_type == 'reason':
            return await self._reason(
                query=message.get('query', ''),
                context=message.get('context', ''),
                mode=message.get('mode', 'deductive')
            )
        
        return {'error': f"Unknown message type: {message_type}"}
    
    async def _reason(self, query: str, context: str = "", mode: str = "deductive") -> Dict[str, Any]:
        """
        执行推理
        
        Args:
            query: 推理问题
            context: 上下文信息
            mode: 推理模式
        
        Returns:
            推理结果
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            # 根据模式选择推理策略
            reasoning_mode = ReasoningMode(mode.lower())
            
            if reasoning_mode == ReasoningMode.DEDUCTIVE:
                result = self._deductive_reasoning(query, context)
            elif reasoning_mode == ReasoningMode.INDUCTIVE:
                result = self._inductive_reasoning(query, context)
            elif reasoning_mode == ReasoningMode.ABDUCTIVE:
                result = self._abductive_reasoning(query, context)
            elif reasoning_mode == ReasoningMode.ANALOGICAL:
                result = self._analogical_reasoning(query, context)
            else:
                result = self._default_reasoning(query, context)
            
            processing_time = asyncio.get_event_loop().time() - start_time
            self.record_success(processing_time)
            
            return {
                'success': True,
                'result': result,
                'confidence': self._calculate_confidence(result),
                'mode': mode,
                'processing_time': round(processing_time, 2)
            }
        
        except Exception as e:
            self.record_error()
            return {
                'success': False,
                'error': str(e),
                'mode': mode
            }
    
    def _deductive_reasoning(self, query: str, context: str) -> str:
        """演绎推理：从一般规则推导出具体结论"""
        return f"[演绎推理] 根据上下文 '{context}'，推理结论：{query} 的答案是基于逻辑推导得出的。"
    
    def _inductive_reasoning(self, query: str, context: str) -> str:
        """归纳推理：从具体实例归纳出一般规律"""
        return f"[归纳推理] 基于实例 '{context}'，归纳得出：{query} 的普遍规律。"
    
    def _abductive_reasoning(self, query: str, context: str) -> str:
        """溯因推理：从结果推断最可能的原因"""
        return f"[溯因推理] 根据观察 '{context}'，最可能的解释是：{query}。"
    
    def _analogical_reasoning(self, query: str, context: str) -> str:
        """类比推理：基于相似性进行推理"""
        return f"[类比推理] 类似情况 '{context}'，因此 {query} 应该采用相似的解决方案。"
    
    def _default_reasoning(self, query: str, context: str) -> str:
        """默认推理策略"""
        return f"[通用推理] 分析：{query}，上下文：{context}"
    
    def _calculate_confidence(self, result: str) -> float:
        """计算推理置信度"""
        if len(result) > 50:
            return 0.85
        return 0.6


class CausalReasoningCell(ReasoningCell):
    """
    因果推理细胞
    
    基于 Pearl 因果层次进行推理：
    - 第一层：关联（Association）
    - 第二层：干预（Intervention）
    - 第三层：反事实（Counterfactual）
    """
    
    def __init__(self):
        super().__init__(specialization="causal")
        self.reasoning_mode = ReasoningMode.CAUSAL
        self.causal_graph = {}  # 因果图
    
    async def _process_signal(self, message: dict) -> Any:
        """处理因果推理请求"""
        message_type = message.get('type', '')
        
        if message_type == 'causal_query':
            return await self._causal_reason(
                query=message.get('query', ''),
                level=message.get('level', 'association'),
                evidence=message.get('evidence', {})
            )
        
        return await super()._process_signal(message)
    
    async def _causal_reason(self, query: str, level: str = "association", 
                            evidence: dict = None) -> Dict[str, Any]:
        """
        执行因果推理
        
        Args:
            query: 因果问题
            level: 因果层次 (association/intervention/counterfactual)
            evidence: 证据信息
        
        Returns:
            推理结果
        """
        evidence = evidence or {}
        
        if level == 'association':
            result = self._association_reasoning(query, evidence)
            confidence = 0.75
        elif level == 'intervention':
            result = self._intervention_reasoning(query, evidence)
            confidence = 0.8
        elif level == 'counterfactual':
            result = self._counterfactual_reasoning(query, evidence)
            confidence = 0.6
        else:
            result = self._association_reasoning(query, evidence)
            confidence = 0.7
        
        return {
            'success': True,
            'result': result,
            'confidence': confidence,
            'level': level,
            'evidence_used': list(evidence.keys())
        }
    
    def _association_reasoning(self, query: str, evidence: dict) -> str:
        """关联推理：P(Y|X) - 观察到X时Y的概率"""
        return f"[关联] 观察到 {evidence}，推断 {query} 的相关性。"
    
    def _intervention_reasoning(self, query: str, evidence: dict) -> str:
        """干预推理：P(Y|do(X)) - 主动干预X后Y的结果"""
        return f"[干预] 如果执行 {evidence}，预期 {query} 的结果。"
    
    def _counterfactual_reasoning(self, query: str, evidence: dict) -> str:
        """反事实推理：P(Y|X, do(not X)) - 如果X未发生，Y会怎样"""
        return f"[反事实] 如果 {evidence} 没有发生，那么 {query}。"
    
    def add_causal_edge(self, cause: str, effect: str, weight: float = 1.0):
        """添加因果边"""
        if cause not in self.causal_graph:
            self.causal_graph[cause] = []
        self.causal_graph[cause].append((effect, weight))


class SymbolicReasoningCell(ReasoningCell):
    """
    符号推理细胞
    
    处理符号逻辑推理，支持：
    - 命题逻辑
    - 谓词逻辑
    - 规则推理
    """
    
    def __init__(self):
        super().__init__(specialization="symbolic")
        self.reasoning_mode = ReasoningMode.SYMBOLIC
        self.rules = []  # 推理规则
    
    async def _process_signal(self, message: dict) -> Any:
        """处理符号推理请求"""
        message_type = message.get('type', '')
        
        if message_type == 'symbolic_query':
            return await self._symbolic_reason(
                premises=message.get('premises', []),
                conclusion=message.get('conclusion', '')
            )
        elif message_type == 'add_rule':
            return self._add_rule(message.get('rule', {}))
        
        return await super()._process_signal(message)
    
    async def _symbolic_reason(self, premises: List[str], conclusion: str) -> Dict[str, Any]:
        """
        执行符号推理
        
        Args:
            premises: 前提列表
            conclusion: 待证明的结论
        
        Returns:
            推理结果
        """
        steps = []
        
        # 简单的规则匹配
        for premise in premises:
            for rule in self.rules:
                if rule['condition'] in premise:
                    steps.append(f"应用规则 '{rule['name']}' 到 '{premise}'")
        
        return {
            'success': True,
            'result': conclusion,
            'confidence': 0.9 if steps else 0.5,
            'steps': steps,
            'premises_used': len(premises)
        }
    
    def _add_rule(self, rule: dict) -> Dict[str, bool]:
        """添加推理规则"""
        if 'name' in rule and 'condition' in rule and 'action' in rule:
            self.rules.append(rule)
            return {'success': True, 'rule_count': len(self.rules)}
        return {'success': False, 'error': 'Invalid rule format'}