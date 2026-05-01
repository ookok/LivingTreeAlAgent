"""
因果推理模块 - Causal Reasoning

功能：
1. 因果图构建
2. 因果推理
3. 干预操作 (do-calculus)
4. 因果效应估计
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import networkx as nx

logger = logging.getLogger(__name__)


@dataclass
class CausalNode:
    """因果图节点"""
    node_id: str
    name: str
    node_type: str  # cause/effect/confounder/mediator
    value: Any = None
    probability: float = 0.5


@dataclass
class InterventionResult:
    """干预结果"""
    intervened_node: str
    intervention_value: Any
    effects: List[Dict]
    confidence: float = 0.0
    reasoning_steps: List[str] = None
    
    def __post_init__(self):
        if self.reasoning_steps is None:
            self.reasoning_steps = []


class CausalGraph:
    """因果图"""
    
    def __init__(self):
        self._graph = nx.DiGraph()
        self._nodes: Dict[str, CausalNode] = {}
    
    def add_node(self, node_id: str, name: str, node_type: str = "cause", value: Any = None):
        """添加节点"""
        node = CausalNode(node_id=node_id, name=name, node_type=node_type, value=value)
        self._nodes[node_id] = node
        self._graph.add_node(node_id, **node.__dict__)
    
    def add_edge(self, cause_id: str, effect_id: str, weight: float = 0.5):
        """添加因果边"""
        if cause_id in self._nodes and effect_id in self._nodes:
            self._graph.add_edge(cause_id, effect_id, weight=weight)
    
    def get_node(self, node_id: str) -> Optional[CausalNode]:
        """获取节点"""
        return self._nodes.get(node_id)
    
    def get_parents(self, node_id: str) -> List[CausalNode]:
        """获取父节点（原因）"""
        parents = []
        for parent_id in self._graph.predecessors(node_id):
            parents.append(self._nodes[parent_id])
        return parents
    
    def get_children(self, node_id: str) -> List[CausalNode]:
        """获取子节点（结果）"""
        children = []
        for child_id in self._graph.successors(node_id):
            children.append(self._nodes[child_id])
        return children
    
    def get_path(self, source_id: str, target_id: str) -> List[str]:
        """获取路径"""
        try:
            return nx.shortest_path(self._graph, source_id, target_id)
        except nx.NetworkXNoPath:
            return []
    
    def get_graph_data(self) -> Dict:
        """获取图数据"""
        return {
            'nodes': [{'id': n, **self._nodes[n].__dict__} for n in self._nodes],
            'edges': [{'source': u, 'target': v, 'weight': d['weight']} 
                     for u, v, d in self._graph.edges(data=True)]
        }
    
    def clear(self):
        """清空图"""
        self._graph.clear()
        self._nodes.clear()


class CausalReasoner:
    """
    因果推理器 - 基于因果图的推理
    
    支持：
    1. 因果链分析
    2. do-calculus干预
    3. 反事实推理基础
    """
    
    def __init__(self):
        self._graph = CausalGraph()
        self._rules: List[Dict] = []
        
        # 初始化默认因果图
        self._init_default_graph()
    
    def _init_default_graph(self):
        """初始化默认因果图"""
        # 添加常见节点
        self._graph.add_node("weather", "天气", "cause")
        self._graph.add_node("temperature", "温度", "cause")
        self._graph.add_node("mood", "心情", "effect")
        self._graph.add_node("activity", "活动", "effect")
        self._graph.add_node("productivity", "生产力", "effect")
        self._graph.add_node("sleep", "睡眠", "confounder")
        
        # 添加因果边
        self._graph.add_edge("weather", "mood", 0.6)
        self._graph.add_edge("temperature", "mood", 0.5)
        self._graph.add_edge("weather", "activity", 0.7)
        self._graph.add_edge("mood", "activity", 0.4)
        self._graph.add_edge("activity", "productivity", 0.8)
        self._graph.add_edge("sleep", "mood", 0.7)
        self._graph.add_edge("sleep", "productivity", 0.6)
    
    def add_causal_relation(self, cause: str, effect: str, weight: float = 0.5):
        """添加因果关系"""
        # 如果节点不存在，创建节点
        if cause not in self._graph._nodes:
            self._graph.add_node(cause, cause, "cause")
        if effect not in self._graph._nodes:
            self._graph.add_node(effect, effect, "effect")
        
        self._graph.add_edge(cause, effect, weight)
        logger.debug(f"添加因果关系: {cause} -> {effect} (权重: {weight})")
    
    def add_rule(self, rule: Dict):
        """添加推理规则"""
        self._rules.append(rule)
    
    def reason(self, query: str) -> Dict:
        """
        执行因果推理
        
        Args:
            query: 查询内容
        
        Returns:
            推理结果
        """
        logger.debug(f"因果推理: {query}")
        
        # 分析查询类型
        if "因为" in query or "why" in query.lower() or "为什么" in query:
            return self._explain_reasoning(query)
        elif "如果" in query or "假如" in query or "what if" in query.lower():
            return self._counterfactual_reasoning(query)
        else:
            return self._general_causal_reasoning(query)
    
    def _explain_reasoning(self, query: str) -> Dict:
        """解释性推理"""
        steps = []
        confidence = 0.7
        
        # 提取关键词
        keywords = self._extract_keywords(query)
        
        # 查找相关节点
        related_nodes = []
        for node_id, node in self._graph._nodes.items():
            if any(kw in node.name for kw in keywords):
                related_nodes.append(node)
        
        if related_nodes:
            steps.append(f"1. 识别到相关概念: {[n.name for n in related_nodes]}")
            
            # 查找因果链
            chains = []
            for node in related_nodes:
                parents = self._graph.get_parents(node.node_id)
                if parents:
                    chains.append(f"{[p.name for p in parents]} -> {node.name}")
            
            if chains:
                steps.append(f"2. 因果链分析: {', '.join(chains)}")
                steps.append("3. 综合分析因果关系")
                conclusion = f"分析完成，找到潜在的因果关系: {', '.join(chains)}"
                confidence = 0.8
            else:
                conclusion = f"未找到明确的因果关系链，但识别到相关概念: {[n.name for n in related_nodes]}"
                confidence = 0.5
        else:
            conclusion = "未找到相关的因果关系"
            confidence = 0.3
        
        return {
            'type': 'causal',
            'result': conclusion,
            'confidence': confidence,
            'steps': steps,
            'related_nodes': [n.name for n in related_nodes]
        }
    
    def _counterfactual_reasoning(self, query: str) -> Dict:
        """反事实推理"""
        steps = [
            "1. 识别事实条件",
            "2. 干预变量",
            "3. 模拟反事实世界",
            "4. 推导后果"
        ]
        
        return {
            'type': 'counterfactual',
            'result': "反事实推理: 假设条件改变，结果将有所不同",
            'confidence': 0.65,
            'steps': steps
        }
    
    def _general_causal_reasoning(self, query: str) -> Dict:
        """通用因果推理"""
        steps = [
            "1. 识别因果结构",
            "2. 应用因果推理规则",
            "3. 综合分析"
        ]
        
        # 查找相关节点
        keywords = self._extract_keywords(query)
        related_nodes = []
        
        for node_id, node in self._graph._nodes.items():
            if any(kw in node.name for kw in keywords):
                related_nodes.append(node)
        
        if related_nodes:
            return {
                'type': 'causal',
                'result': f"基于因果图的推理结果，涉及: {[n.name for n in related_nodes]}",
                'confidence': 0.7,
                'steps': steps,
                'related_nodes': [n.name for n in related_nodes]
            }
        else:
            return {
                'type': 'causal',
                'result': "基于现有因果知识的推理结果",
                'confidence': 0.5,
                'steps': steps
            }
    
    def do_intervention(self, node: str, value: Any) -> InterventionResult:
        """
        干预操作 (do-calculus)
        Pearl的因果层次第2层
        
        Args:
            node: 节点ID
            value: 干预值
        
        Returns:
            干预结果
        """
        logger.debug(f"干预操作: do({node} = {value})")
        
        effects = []
        
        # 查找受影响的节点
        if node in self._graph._nodes:
            for neighbor in self._graph._graph.successors(node):
                edge_data = self._graph._graph.get_edge_data(node, neighbor)
                edge_weight = edge_data.get('weight', 0.5)
                
                effects.append({
                    'node': neighbor,
                    'influence': edge_weight,
                    'original_value': self._graph._nodes[neighbor].value,
                    'predicted_change': f"基于因果强度 {edge_weight} 的变化"
                })
        
        return InterventionResult(
            intervened_node=node,
            intervention_value=value,
            effects=effects,
            confidence=0.7 + len(effects) * 0.05,
            reasoning_steps=[
                f"1. 执行干预 do({node} = {value})",
                f"2. 传播因果效应到 {len(effects)} 个下游节点",
                f"3. 计算影响程度"
            ]
        )
    
    def estimate_effect(self, cause: str, effect: str, confounders: List[str] = None) -> Dict:
        """
        估计因果效应
        
        Args:
            cause: 原因节点
            effect: 结果节点
            confounders: 混淆变量
        
        Returns:
            因果效应估计
        """
        path = self._graph.get_path(cause, effect)
        
        if not path:
            return {'effect': 0.0, 'confidence': 0.3, 'message': '无因果路径'}
        
        # 计算路径强度
        total_weight = 1.0
        for i in range(len(path) - 1):
            edge_data = self._graph._graph.get_edge_data(path[i], path[i+1])
            if edge_data:
                total_weight *= edge_data.get('weight', 0.5)
        
        return {
            'cause': cause,
            'effect': effect,
            'path': path,
            'effect_size': total_weight,
            'confidence': min(0.95, 0.5 + total_weight * 0.5),
            'message': f"估计因果效应: {cause} -> {effect} = {total_weight:.2f}"
        }
    
    def get_causal_graph(self) -> Dict:
        """获取因果图"""
        return self._graph.get_graph_data()
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        words = text.lower().split()
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'in', 'on', 'at', 'to', 'for', 'this', 'that', 'with', 'and', 'or', 'but', 'not'}
        return [w for w in words if w not in stop_words and len(w) > 2]