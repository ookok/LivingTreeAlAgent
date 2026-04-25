# decision_tracker.py - 决策追踪器

"""
Decision Tracker - 追踪每条决策的因果链

核心功能：
1. 记录决策上下文 - 记录做出决策时的完整上下文
2. 追踪决策链 - 追踪从信号到提案到执行的完整链路
3. 回溯分析 - 支持决策的回溯和解释
4. 决策审计 - 记录谁/何时/为何做出决策
"""

import json
import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import uuid

logger = logging.getLogger('evolution.decision')


class DecisionType(Enum):
    """决策类型"""
    APPROVE = "approve"  # 批准提案
    REJECT = "reject"  # 拒绝提案
    ROLLBACK = "rollback"  # 回滚执行
    ADJUST = "adjust"  # 调整提案参数
    DEFER = "defer"  # 推迟决策
    PRIORITIZE = "prioritize"  # 调整优先级


class DecisionOutcome(Enum):
    """决策结果"""
    SUCCESS = "success"  # 决策正确
    FAILURE = "failure"  # 决策错误
    PARTIAL = "partial"  # 部分正确
    UNKNOWN = "unknown"  # 未知


@dataclass
class DecisionContext:
    """决策上下文"""
    signals: List[Dict] = field(default_factory=list)  # 触发的信号
    proposals: List[Dict] = field(default_factory=list)  # 相关提案
    proposals_considered: int = 0  # 考虑的提案数量
    time_available_ms: float = 0.0  # 可用决策时间
    risk_tolerance: str = "medium"  # 风险承受能力
    
    def to_dict(self) -> Dict:
        return {
            'signals': self.signals,
            'proposals': self.proposals,
            'proposals_considered': self.proposals_considered,
            'time_available_ms': self.time_available_ms,
            'risk_tolerance': self.risk_tolerance
        }


@dataclass
class DecisionFactor:
    """决策因素"""
    factor_type: str  # severity, complexity, risk, success_rate, etc.
    value: float  # 因素值
    weight: float  # 因素权重
    description: str = ""
    
    @property
    def weighted_value(self) -> float:
        return self.value * self.weight
    
    def to_dict(self) -> Dict:
        return {
            'factor_type': self.factor_type,
            'value': self.value,
            'weight': self.weight,
            'weighted_value': self.weighted_value,
            'description': self.description
        }


@dataclass
class DecisionNode:
    """决策节点"""
    node_id: str
    decision_type: DecisionType
    timestamp: str
    context: DecisionContext
    factors: List[DecisionFactor]
    alternatives: List[str] = field(default_factory=list)  # 被否决的替代方案
    reasoning: str = ""  # 推理过程
    decision_maker: str = "system"  # system, user, auto
    
    def to_dict(self) -> Dict:
        return {
            'node_id': self.node_id,
            'decision_type': self.decision_type.value,
            'timestamp': self.timestamp,
            'context': self.context.to_dict(),
            'factors': [f.to_dict() for f in self.factors],
            'alternatives': self.alternatives,
            'reasoning': self.reasoning,
            'decision_maker': self.decision_maker
        }


@dataclass
class ExecutionChain:
    """执行链（从信号到执行的完整链路）"""
    chain_id: str
    proposal_id: str
    nodes: List[DecisionNode] = field(default_factory=list)  # 决策节点列表
    execution_id: Optional[str] = None
    final_outcome: Optional[str] = None
    outcome_reason: str = ""
    
    def add_node(self, node: DecisionNode):
        self.nodes.append(node)
    
    def to_dict(self) -> Dict:
        return {
            'chain_id': self.chain_id,
            'proposal_id': self.proposal_id,
            'nodes': [n.to_dict() for n in self.nodes],
            'execution_id': self.execution_id,
            'final_outcome': self.final_outcome,
            'outcome_reason': self.outcome_reason
        }


class DecisionTracker:
    """
    决策追踪器
    
    追踪每条决策的完整因果链，支持回溯和解释
    """
    
    def __init__(self, evolution_log=None):
        self._log = evolution_log
        
        # 决策链存储
        self._chains: Dict[str, ExecutionChain] = {}
        
        # 提案到链的映射
        self._proposal_chains: Dict[str, str] = {}  # proposal_id -> chain_id
        
        # 信号到链的映射
        self._signal_chains: Dict[str, List[str]] = defaultdict(list)  # signal_id -> chain_ids
        
        # 决策历史
        self._decisions: List[DecisionNode] = []
        
        # 根因分析缓存
        self._root_cause_cache: Dict[str, Dict] = {}
    
    def create_chain(self, proposal_id: str) -> str:
        """创建新的执行链"""
        chain_id = f"chain_{uuid.uuid4().hex[:12]}"
        
        chain = ExecutionChain(
            chain_id=chain_id,
            proposal_id=proposal_id
        )
        
        self._chains[chain_id] = chain
        self._proposal_chains[proposal_id] = chain_id
        
        return chain_id
    
    def record_decision(
        self,
        chain_id: str,
        decision_type: DecisionType,
        context: DecisionContext,
        factors: List[DecisionFactor],
        reasoning: str = "",
        alternatives: List[str] = None,
        decision_maker: str = "system"
    ) -> str:
        """
        记录一个决策
        
        Returns:
            node_id
        """
        if chain_id not in self._chains:
            logger.warning(f"[DecisionTracker] Chain {chain_id} 不存在")
            return None
        
        node_id = f"node_{uuid.uuid4().hex[:12]}"
        
        node = DecisionNode(
            node_id=node_id,
            decision_type=decision_type,
            timestamp=datetime.now().isoformat(),
            context=context,
            factors=factors,
            alternatives=alternatives or [],
            reasoning=reasoning,
            decision_maker=decision_maker
        )
        
        # 添加到链
        self._chains[chain_id].add_node(node)
        
        # 添加到历史
        self._decisions.append(node)
        
        # 限制历史大小
        if len(self._decisions) > 1000:
            self._decisions = self._decisions[-500:]
        
        logger.debug(f"[DecisionTracker] 记录决策: {decision_type.value} in chain {chain_id}")
        
        return node_id
    
    def link_signal(self, chain_id: str, signal_id: str):
        """关联信号到链"""
        if chain_id not in self._chains:
            return
        
        if signal_id not in self._signal_chains:
            self._signal_chains[signal_id] = []
        
        if chain_id not in self._signal_chains[signal_id]:
            self._signal_chains[signal_id].append(chain_id)
    
    def link_execution(self, chain_id: str, execution_id: str):
        """关联执行结果到链"""
        if chain_id not in self._chains:
            return
        
        self._chains[chain_id].execution_id = execution_id
    
    def resolve_outcome(
        self,
        chain_id: str,
        outcome: DecisionOutcome,
        reason: str = ""
    ):
        """记录链的结果"""
        if chain_id not in self._chains:
            return
        
        chain = self._chains[chain_id]
        chain.final_outcome = outcome.value
        chain.outcome_reason = reason
        
        # 更新决策历史中的反馈
        for node in chain.nodes:
            # 这里可以添加反馈分析
            pass
        
        logger.info(f"[DecisionTracker] 链 {chain_id} 结果: {outcome.value}")
    
    def get_chain(self, chain_id: str) -> Optional[ExecutionChain]:
        """获取执行链"""
        return self._chains.get(chain_id)
    
    def get_chain_by_proposal(self, proposal_id: str) -> Optional[ExecutionChain]:
        """根据提案ID获取链"""
        chain_id = self._proposal_chains.get(proposal_id)
        return self._chains.get(chain_id) if chain_id else None
    
    def get_chains_by_signal(self, signal_id: str) -> List[ExecutionChain]:
        """根据信号ID获取关联的链"""
        chain_ids = self._signal_chains.get(signal_id, [])
        return [self._chains[cid] for cid in chain_ids if cid in self._chains]
    
    def analyze_root_cause(self, chain_id: str) -> Dict[str, Any]:
        """
        分析链的根因
        
        回溯从最终结果到最初信号的因果关系
        """
        if chain_id in self._root_cause_cache:
            return self._root_cause_cache[chain_id]
        
        chain = self._chains.get(chain_id)
        if not chain:
            return {}
        
        analysis = {
            'chain_id': chain_id,
            'proposal_id': chain.proposal_id,
            'final_outcome': chain.final_outcome,
            'nodes_count': len(chain.nodes),
            'timeline': [],
            'contributing_factors': [],
            'root_signals': [],
            'recommendations': []
        }
        
        # 构建时间线
        for node in chain.nodes:
            analysis['timeline'].append({
                'timestamp': node.timestamp,
                'type': node.decision_type.value,
                'reasoning': node.reasoning[:100] if node.reasoning else ''
            })
        
        # 提取贡献因素
        all_factors: Dict[str, float] = defaultdict(float)
        for node in chain.nodes:
            for factor in node.factors:
                all_factors[factor.factor_type] += factor.weighted_value
        
        # 按权重排序
        sorted_factors = sorted(
            all_factors.items(),
            key=lambda x: x[1],
            reverse=True
        )
        analysis['contributing_factors'] = [
            {'type': k, 'cumulative_weight': v}
            for k, v in sorted_factors[:10]
        ]
        
        # 提取根信号（最早的信号）
        if chain.nodes:
            first_context = chain.nodes[0].context
            for signal in first_context.signals:
                analysis['root_signals'].append({
                    'signal_type': signal.get('type', 'unknown'),
                    'severity': signal.get('severity', 'unknown'),
                    'description': signal.get('description', '')[:100]
                })
        
        # 生成建议
        if chain.final_outcome == 'failure':
            analysis['recommendations'] = [
                f"考虑增加对 {analysis['contributing_factors'][0]['type']} 的检测",
                "检查早期决策是否过于激进",
                "建议增加执行前的验证步骤"
            ]
        elif chain.final_outcome == 'partial':
            analysis['recommendations'] = [
                "部分成功，考虑分步骤执行",
                "分析中途失败的节点，优化处理"
            ]
        
        # 缓存结果
        self._root_cause_cache[chain_id] = analysis
        
        return analysis
    
    def get_decision_patterns(self) -> Dict[str, Any]:
        """获取决策模式统计"""
        patterns = {
            'total_decisions': len(self._decisions),
            'by_type': defaultdict(int),
            'by_maker': defaultdict(int),
            'avg_factors_per_decision': 0,
            'top_factors': defaultdict(float),
            'chain_success_rate': 0.0
        }
        
        if not self._decisions:
            return patterns
        
        # 统计决策类型
        for decision in self._decisions:
            patterns['by_type'][decision.decision_type.value] += 1
            patterns['by_maker'][decision.decision_maker] += 1
            
            # 统计因素
            for factor in decision.factors:
                patterns['top_factors'][factor.factor_type] += factor.weighted_value
        
        # 平均因素数
        patterns['avg_factors_per_decision'] = sum(
            len(d.factors) for d in self._decisions
        ) / len(self._decisions)
        
        # 转换defaultdict
        patterns['by_type'] = dict(patterns['by_type'])
        patterns['by_maker'] = dict(patterns['by_maker'])
        patterns['top_factors'] = dict(patterns['top_factors'])
        
        # 计算链成功率
        successful_chains = sum(
            1 for c in self._chains.values()
            if c.final_outcome == 'success'
        )
        patterns['chain_success_rate'] = (
            successful_chains / len(self._chains)
            if self._chains else 0.0
        )
        
        return patterns
    
    def explain_decision(self, node_id: str) -> Dict[str, Any]:
        """
        解释一个决策
        
        生成人类可读的解释
        """
        # 找到决策节点
        node = None
        for chain in self._chains.values():
            for n in chain.nodes:
                if n.node_id == node_id:
                    node = n
                    break
            if node:
                break
        
        if not node:
            return {'error': 'Decision not found'}
        
        explanation = {
            'node_id': node_id,
            'decision': node.decision_type.value,
            'timestamp': node.timestamp,
            'summary': '',
            'reasoning': node.reasoning,
            'factors': [],
            'alternatives': [],
            'context': {
                'signals_count': len(node.context.signals),
                'proposals_count': len(node.context.proposals),
                'time_available': node.context.time_available_ms,
                'risk_tolerance': node.context.risk_tolerance
            }
        }
        
        # 生成摘要
        type_descriptions = {
            DecisionType.APPROVE: "批准",
            DecisionType.REJECT: "拒绝",
            DecisionType.ROLLBACK: "回滚",
            DecisionType.ADJUST: "调整",
            DecisionType.DEFER: "推迟",
            DecisionType.PRIORITIZE: "调整优先级"
        }
        explanation['summary'] = f"系统{type_descriptions.get(node.decision_type, '做出')}"
        
        # 列出关键因素
        sorted_factors = sorted(
            node.factors,
            key=lambda f: f.weighted_value,
            reverse=True
        )
        for factor in sorted_factors[:5]:
            explanation['factors'].append({
                'name': factor.factor_type,
                'value': factor.value,
                'weight': factor.weight,
                'impact': factor.weighted_value,
                'description': factor.description
            })
        
        # 列出替代方案
        for alt in node.alternatives:
            explanation['alternatives'].append({
                'description': alt,
                'why_not_chosen': '选择了更优方案'
            })
        
        return explanation
    
    def get_audit_trail(self, chain_id: str) -> List[Dict]:
        """获取审计追踪"""
        chain = self._chains.get(chain_id)
        if not chain:
            return []
        
        trail = []
        
        # 信号事件
        for signal in chain.nodes[0].context.signals if chain.nodes else []:
            trail.append({
                'event': 'signal_detected',
                'timestamp': datetime.now().isoformat(),
                'data': signal
            })
        
        # 决策事件
        for node in chain.nodes:
            trail.append({
                'event': f'decision_{node.decision_type.value}',
                'timestamp': node.timestamp,
                'data': {
                    'node_id': node.node_id,
                    'factors_count': len(node.factors),
                    'alternatives_count': len(node.alternatives)
                }
            })
        
        # 执行事件
        if chain.execution_id:
            trail.append({
                'event': 'execution_completed',
                'timestamp': datetime.now().isoformat(),
                'data': {'execution_id': chain.execution_id}
            })
        
        # 结果事件
        if chain.final_outcome:
            trail.append({
                'event': f'outcome_{chain.final_outcome}',
                'timestamp': datetime.now().isoformat(),
                'data': {'reason': chain.outcome_reason}
            })
        
        return trail
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取追踪统计"""
        return {
            'total_chains': len(self._chains),
            'total_decisions': len(self._decisions),
            'chains_by_outcome': {
                outcome: sum(1 for c in self._chains.values() if c.final_outcome == outcome)
                for outcome in ['success', 'failure', 'partial', None]
            },
            'avg_nodes_per_chain': (
                sum(len(c.nodes) for c in self._chains.values()) / len(self._chains)
                if self._chains else 0
            )
        }


# 全局单例
_decision_tracker: Optional[DecisionTracker] = None


def get_decision_tracker(evolution_log=None) -> DecisionTracker:
    """获取 DecisionTracker 单例"""
    global _decision_tracker
    if _decision_tracker is None:
        _decision_tracker = DecisionTracker(evolution_log)
    return _decision_tracker
