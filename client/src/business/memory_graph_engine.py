"""
多模态记忆图引擎 (Multimodal Memory Graph Engine)

基于 VimRAG 论文思想实现：
1. Multimodal Memory Graph: 将推理过程建模为动态有向无环图
2. Graph-Modulated Visual Memory Encoding: 基于拓扑位置评估节点重要性
3. Graph-Guided Policy Optimization: 细粒度信用分配

与现有系统集成：
- 基于三重链验证引擎扩展
- 支持文本、图片、视频等多模态证据
- 与 FusionRAG 和 LLM Wiki 无缝集成
"""

import json
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4

# 导入共享基础设施
from business.shared import (
    EventBus,
    CacheLayer,
    get_event_bus,
    get_cache,
    EVENTS
)


class NodeType(Enum):
    """记忆节点类型"""
    EVIDENCE = "evidence"      # 证据节点
    REASONING = "reasoning"    # 推理节点
    CONCLUSION = "conclusion"  # 结论节点
    QUERY = "query"            # 查询节点
    SOURCE = "source"          # 来源节点


class RelationType(Enum):
    """边的关系类型"""
    SUPPORTS = "supports"      # 支持
    CONTRADICTS = "contradicts" # 矛盾
    IMPLIES = "implies"        # 蕴含
    CITES = "cites"           # 引用
    DERIVES_FROM = "derives_from" # 来源于


@dataclass
class MemoryNode:
    """记忆节点"""
    node_id: str
    content: str
    node_type: NodeType
    importance: float = 0.0
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    modalities: List[str] = field(default_factory=list)  # ["text", "image", "video"]


@dataclass
class GraphEdge:
    """图边"""
    from_node: str
    to_node: str
    relation_type: RelationType
    weight: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MemoryGraph:
    """多模态记忆图"""
    nodes: Dict[str, MemoryNode] = field(default_factory=dict)
    edges: List[GraphEdge] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    
    def add_node(self, content: str, node_type: NodeType, 
                 confidence: float = 0.0, modalities: List[str] = None) -> str:
        """添加节点"""
        node_id = str(uuid4())[:8]
        self.nodes[node_id] = MemoryNode(
            node_id=node_id,
            content=content,
            node_type=node_type,
            confidence=confidence,
            modalities=modalities or ["text"]
        )
        self.last_updated = datetime.now()
        return node_id
    
    def add_edge(self, from_node: str, to_node: str, 
                 relation_type: RelationType, weight: float = 0.0):
        """添加边"""
        if from_node not in self.nodes or to_node not in self.nodes:
            raise ValueError("节点不存在")
        
        self.edges.append(GraphEdge(
            from_node=from_node,
            to_node=to_node,
            relation_type=relation_type,
            weight=weight
        ))
        self.last_updated = datetime.now()
    
    def get_node(self, node_id: str) -> Optional[MemoryNode]:
        """获取节点"""
        return self.nodes.get(node_id)
    
    def get_neighbors(self, node_id: str) -> List[str]:
        """获取邻居节点"""
        neighbors = set()
        for edge in self.edges:
            if edge.from_node == node_id:
                neighbors.add(edge.to_node)
            if edge.to_node == node_id:
                neighbors.add(edge.from_node)
        return list(neighbors)
    
    def calculate_importance(self):
        """
        基于拓扑位置计算节点重要性（PageRank-like 算法）
        
        核心思想：
        1. 结论节点权重更高
        2. 被更多节点引用的节点更重要
        3. 重要节点引用的节点也更重要
        """
        # 初始化重要性
        for node in self.nodes.values():
            # 结论节点初始重要性更高
            if node.node_type == NodeType.CONCLUSION:
                node.importance = 0.5
            elif node.node_type == NodeType.REASONING:
                node.importance = 0.3
            else:
                node.importance = 0.2
        
        # 迭代计算（PageRank 算法）
        damping_factor = 0.85
        iterations = 10
        
        for _ in range(iterations):
            new_importance = {}
            
            for node_id, node in self.nodes.items():
                # 计算入边贡献
                in_edges = [e for e in self.edges if e.to_node == node_id]
                incoming_sum = sum(
                    self.nodes[e.from_node].importance * e.weight
                    for e in in_edges
                )
                
                new_importance[node_id] = (1 - damping_factor) + damping_factor * incoming_sum
            
            # 更新重要性
            for node_id, importance in new_importance.items():
                self.nodes[node_id].importance = importance
        
        # 归一化
        total = sum(n.importance for n in self.nodes.values())
        if total > 0:
            for node in self.nodes.values():
                node.importance /= total
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示"""
        return {
            "nodes": {k: {
                "content": v.content,
                "type": v.node_type.value,
                "importance": v.importance,
                "confidence": v.confidence,
                "modalities": v.modalities
            } for k, v in self.nodes.items()},
            "edges": [{
                "from": e.from_node,
                "to": e.to_node,
                "relation": e.relation_type.value,
                "weight": e.weight
            } for e in self.edges],
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat()
        }


class MemoryGraphEngine:
    """
    多模态记忆图引擎
    
    核心功能：
    1. 构建和管理多模态记忆图
    2. 基于图结构进行推理
    3. 动态分配计算资源（根据节点重要性）
    4. 支持细粒度信用分配
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        # 获取共享基础设施
        self.event_bus = get_event_bus()
        self.cache = get_cache()
        
        # 当前活动的记忆图
        self.active_graphs: Dict[str, MemoryGraph] = {}
        
        # 导入三重链引擎
        try:
            from business.fusion_rag import create_triple_chain_engine
            self.triple_chain_engine = create_triple_chain_engine()
        except:
            self.triple_chain_engine = None
        
        self._initialized = True
        print("[MemoryGraphEngine] 初始化完成")
    
    def create_graph(self, query: str = "") -> str:
        """创建新的记忆图"""
        graph_id = str(uuid4())[:8]
        self.active_graphs[graph_id] = MemoryGraph()
        
        # 如果有查询，添加查询节点
        if query:
            self.active_graphs[graph_id].add_node(query, NodeType.QUERY)
        
        print(f"[MemoryGraphEngine] 创建记忆图: {graph_id}")
        return graph_id
    
    def get_graph(self, graph_id: str) -> Optional[MemoryGraph]:
        """获取记忆图"""
        return self.active_graphs.get(graph_id)
    
    def add_evidence(self, graph_id: str, content: str, 
                     confidence: float = 0.0, modalities: List[str] = None) -> str:
        """添加证据节点"""
        graph = self.active_graphs.get(graph_id)
        if not graph:
            raise ValueError("记忆图不存在")
        
        node_id = graph.add_node(content, NodeType.EVIDENCE, confidence, modalities)
        return node_id
    
    def add_reasoning(self, graph_id: str, content: str, 
                      confidence: float = 0.0) -> str:
        """添加推理节点"""
        graph = self.active_graphs.get(graph_id)
        if not graph:
            raise ValueError("记忆图不存在")
        
        node_id = graph.add_node(content, NodeType.REASONING, confidence)
        return node_id
    
    def add_conclusion(self, graph_id: str, content: str, 
                       confidence: float = 0.0) -> str:
        """添加结论节点"""
        graph = self.active_graphs.get(graph_id)
        if not graph:
            raise ValueError("记忆图不存在")
        
        node_id = graph.add_node(content, NodeType.CONCLUSION, confidence)
        return node_id
    
    def connect_nodes(self, graph_id: str, from_node: str, to_node: str,
                      relation_type: RelationType, weight: float = 0.0):
        """连接节点"""
        graph = self.active_graphs.get(graph_id)
        if not graph:
            raise ValueError("记忆图不存在")
        
        graph.add_edge(from_node, to_node, relation_type, weight)
    
    def build_reasoning_graph(self, query: str, evidences: List[Dict], 
                              reasoning_steps: List[str], conclusion: str) -> str:
        """
        构建完整的推理图
        
        Args:
            query: 用户查询
            evidences: 证据列表
            reasoning_steps: 推理步骤
            conclusion: 结论
            
        Returns:
            图ID
        """
        graph_id = self.create_graph(query)
        graph = self.active_graphs[graph_id]
        
        # 添加查询节点
        query_node = graph.add_node(query, NodeType.QUERY)
        
        # 添加证据节点并连接到查询
        evidence_nodes = []
        for i, evidence in enumerate(evidences):
            content = evidence.get("content", "")
            confidence = evidence.get("confidence", 0.0)
            modalities = evidence.get("modalities", ["text"])
            
            node_id = graph.add_node(content, NodeType.EVIDENCE, confidence, modalities)
            evidence_nodes.append(node_id)
            graph.add_edge(query_node, node_id, RelationType.DERIVES_FROM, weight=confidence)
        
        # 添加推理节点并建立连接
        prev_node = None
        for step in reasoning_steps:
            node_id = graph.add_node(step, NodeType.REASONING, confidence=0.8)
            
            if prev_node:
                graph.add_edge(prev_node, node_id, RelationType.IMPLIES, weight=0.9)
            
            # 连接到相关证据
            for ev_node in evidence_nodes:
                graph.add_edge(ev_node, node_id, RelationType.SUPPORTS, weight=0.7)
            
            prev_node = node_id
        
        # 添加结论节点
        conclusion_node = graph.add_node(conclusion, NodeType.CONCLUSION, confidence=0.9)
        
        if prev_node:
            graph.add_edge(prev_node, conclusion_node, RelationType.IMPLIES, weight=0.95)
        
        # 连接证据到结论
        for ev_node in evidence_nodes:
            graph.add_edge(ev_node, conclusion_node, RelationType.SUPPORTS, weight=0.6)
        
        # 计算节点重要性
        graph.calculate_importance()
        
        # 发布事件
        self.event_bus.publish(EVENTS["KNOWLEDGE_DISCOVERED"], {
            "graph_id": graph_id,
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges)
        })
        
        return graph_id
    
    def allocate_tokens(self, graph_id: str, max_tokens: int = 8192) -> Dict[str, int]:
        """
        动态分配 token（Graph-Modulated Visual Memory Encoding）
        
        根据节点重要性分配计算资源
        """
        graph = self.active_graphs.get(graph_id)
        if not graph:
            raise ValueError("记忆图不存在")
        
        # 确保重要性已计算
        if not any(n.importance > 0 for n in graph.nodes.values()):
            graph.calculate_importance()
        
        # 根据重要性分配 token
        allocation = {}
        for node_id, node in graph.nodes.items():
            allocation[node_id] = int(node.importance * max_tokens)
        
        return allocation
    
    def extract_relevant_context(self, graph_id: str, max_tokens: int = 2048) -> str:
        """
        提取相关上下文（用于生成回答）
        
        根据节点重要性选择最相关的内容
        """
        graph = self.active_graphs.get(graph_id)
        if not graph:
            raise ValueError("记忆图不存在")
        
        # 按重要性排序节点
        sorted_nodes = sorted(
            graph.nodes.values(),
            key=lambda x: x.importance,
            reverse=True
        )
        
        # 构建上下文
        context = ""
        used_tokens = 0
        
        for node in sorted_nodes:
            # 估计 token 数量（简单估算）
            token_estimate = len(node.content) // 4
            
            if used_tokens + token_estimate <= max_tokens:
                context += f"【{node.node_type.value}】{node.content}\n\n"
                used_tokens += token_estimate
            else:
                break
        
        return context.strip()
    
    def evaluate_trajectory(self, graph_id: str, final_reward: float):
        """
        细粒度信用分配（Graph-Guided Policy Optimization）
        
        根据轨迹中的每个步骤分配奖励
        """
        graph = self.active_graphs.get(graph_id)
        if not graph:
            raise ValueError("记忆图不存在")
        
        # 获取推理步骤
        reasoning_nodes = [
            (k, v) for k, v in graph.nodes.items()
            if v.node_type == NodeType.REASONING
        ]
        
        # 按拓扑顺序排序（基于边的连接）
        reasoning_nodes.sort(key=lambda x: self._get_depth(graph, x[0]))
        
        # 分配奖励
        rewards = {}
        total_steps = len(reasoning_nodes)
        
        for i, (node_id, node) in enumerate(reasoning_nodes):
            # 早期步骤权重更高（因为影响后续步骤）
            position_bonus = 1 - (i / total_steps)
            
            # 结合节点重要性
            reward = final_reward * node.importance * position_bonus
            rewards[node_id] = reward
        
        return rewards
    
    def _get_depth(self, graph: MemoryGraph, node_id: str) -> int:
        """计算节点深度（从查询节点开始）"""
        visited = set()
        queue = [(node_id, 0)]
        
        while queue:
            current, depth = queue.pop(0)
            if current in visited:
                continue
            
            visited.add(current)
            
            # 找到查询节点
            if graph.nodes[current].node_type == NodeType.QUERY:
                return depth
            
            # 继续向上搜索
            parents = [e.from_node for e in graph.edges if e.to_node == current]
            for parent in parents:
                if parent not in visited:
                    queue.append((parent, depth + 1))
        
        return 999  # 未找到查询节点
    
    def visualize_graph(self, graph_id: str) -> str:
        """生成图的可视化表示"""
        graph = self.active_graphs.get(graph_id)
        if not graph:
            return "记忆图不存在"
        
        result = "```mermaid\ngraph TD\n"
        
        # 添加节点
        for node_id, node in graph.nodes.items():
            label = node.content[:30] + "..." if len(node.content) > 30 else node.content
            color_map = {
                NodeType.QUERY: "#4CAF50",
                NodeType.EVIDENCE: "#2196F3",
                NodeType.REASONING: "#FF9800",
                NodeType.CONCLUSION: "#9C27B0"
            }
            result += f'    {node_id}["{label}"]:::{node.node_type.value}\n'
        
        # 添加边
        for edge in graph.edges:
            relation_label = {
                RelationType.SUPPORTS: "支持",
                RelationType.CONTRADICTS: "矛盾",
                RelationType.IMPLIES: "蕴含",
                RelationType.DERIVES_FROM: "来源"
            }.get(edge.relation_type, edge.relation_type.value)
            
            result += f'    {edge.from_node} -->|{relation_label}| {edge.to_node}\n'
        
        # 添加样式
        result += """
    class query fill:#4CAF50,color:#fff;
    class evidence fill:#2196F3,color:#fff;
    class reasoning fill:#FF9800,color:#fff;
    class conclusion fill:#9C27B0,color:#fff;
```"""
        
        return result


# 创建全局实例
_memory_graph_engine = None


def get_memory_graph_engine() -> MemoryGraphEngine:
    """获取记忆图引擎实例"""
    global _memory_graph_engine
    if _memory_graph_engine is None:
        _memory_graph_engine = MemoryGraphEngine()
    return _memory_graph_engine


__all__ = [
    "NodeType",
    "RelationType",
    "MemoryNode",
    "GraphEdge",
    "MemoryGraph",
    "MemoryGraphEngine",
    "get_memory_graph_engine"
]