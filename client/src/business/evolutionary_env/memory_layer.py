"""
记忆层（Memory Layer）：动态知识图谱

核心功能：
1. 超越RAG：可写的动态知识图谱
2. 自我更新机制：从用户交互中学习关联规则
3. 反向回流：用户修改反馈回灌到知识图谱
"""

import json
import time
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class KnowledgeNode:
    node_id: str
    label: str
    node_type: str  # concept, entity, action, pattern
    properties: Dict[str, Any]
    embedding: List[float] = None
    confidence: float = 1.0

@dataclass
class KnowledgeEdge:
    edge_id: str
    source: str
    target: str
    relation: str
    weight: float = 1.0
    frequency: int = 1

@dataclass
class LearnedPattern:
    pattern_id: str
    conditions: List[Dict[str, Any]]
    action: str
    confidence: float
    usage_count: int

class MemoryLayer:
    def __init__(self):
        self.nodes: Dict[str, KnowledgeNode] = {}
        self.edges: Dict[str, KnowledgeEdge] = {}
        self.patterns: Dict[str, LearnedPattern] = {}
        self.node_counter = 0
        self.edge_counter = 0
        self.pattern_counter = 0
        
        # 初始化核心概念节点
        self._initialize_core_concepts()
    
    def _initialize_core_concepts(self):
        """初始化环评领域的核心概念"""
        core_concepts = [
            ('环评报告', 'concept', {'description': '环境影响评价报告'}),
            ('化工项目', 'concept', {'description': '化工行业建设项目'}),
            ('水源地', 'entity', {'description': '饮用水水源保护区'}),
            ('噪声预测', 'action', {'description': '噪声影响预测分析'}),
            ('水环境', 'concept', {'description': '水环境影响评价'}),
            ('大气环境', 'concept', {'description': '大气环境影响评价'}),
            ('敏感目标', 'entity', {'description': '环境敏感保护目标'}),
            ('监测数据', 'concept', {'description': '环境监测数据'}),
            ('三线一单', 'concept', {'description': '生态保护红线、环境质量底线、资源利用上线和生态环境准入清单'}),
            ('CAD图纸', 'entity', {'description': '项目设计图纸'}),
            ('Excel', 'entity', {'description': '表格数据文件'}),
        ]
        
        for label, node_type, properties in core_concepts:
            self.add_node(label, node_type, properties)
    
    def add_node(self, label: str, node_type: str, properties: Dict[str, Any] = None) -> str:
        """添加知识节点"""
        node_id = f"node_{self.node_counter}_{int(time.time())}"
        node = KnowledgeNode(
            node_id=node_id,
            label=label,
            node_type=node_type,
            properties=properties or {}
        )
        self.nodes[node_id] = node
        self.node_counter += 1
        return node_id
    
    def add_edge(self, source_id: str, target_id: str, relation: str, weight: float = 1.0):
        """添加知识边（关联）"""
        if source_id not in self.nodes or target_id not in self.nodes:
            return
        
        edge_key = f"{source_id}_{target_id}_{relation}"
        
        if edge_key in self.edges:
            # 更新已有边的权重和频率
            edge = self.edges[edge_key]
            edge.weight = min(1.0, edge.weight + 0.1)
            edge.frequency += 1
        else:
            edge_id = f"edge_{self.edge_counter}_{int(time.time())}"
            edge = KnowledgeEdge(
                edge_id=edge_id,
                source=source_id,
                target=target_id,
                relation=relation,
                weight=weight,
                frequency=1
            )
            self.edges[edge_key] = edge
            self.edge_counter += 1
    
    def find_node_by_label(self, label: str) -> str:
        """根据标签查找节点ID"""
        for node_id, node in self.nodes.items():
            if node.label == label:
                return node_id
        return None
    
    def learn_association(self, concept1: str, concept2: str, relation: str = 'related_to'):
        """
        从用户交互中学习关联规则
        
        例如：当用户反复在"噪声预测"前询问"声环境功能区划"时，
        系统会自动建立强关联
        """
        node1_id = self.find_node_by_label(concept1)
        node2_id = self.find_node_by_label(concept2)
        
        if not node1_id:
            node1_id = self.add_node(concept1, 'concept')
        
        if not node2_id:
            node2_id = self.add_node(concept2, 'concept')
        
        self.add_edge(node1_id, node2_id, relation)
        print(f"[记忆层] 学习到关联: {concept1} -[{relation}]-> {concept2}")
    
    def learn_pattern(self, conditions: List[Dict[str, Any]], action: str):
        """
        学习交互模式
        
        Args:
            conditions: 触发条件列表
            action: 推荐的动作
        """
        pattern_id = f"pattern_{self.pattern_counter}"
        pattern = LearnedPattern(
            pattern_id=pattern_id,
            conditions=conditions,
            action=action,
            confidence=0.7,
            usage_count=0
        )
        self.patterns[pattern_id] = pattern
        self.pattern_counter += 1
        print(f"[记忆层] 学习到模式: {pattern_id} -> {action}")
    
    def update_pattern_confidence(self, pattern_id: str, positive: bool):
        """
        根据用户反馈更新模式置信度
        
        Args:
            pattern_id: 模式ID
            positive: 是否正向反馈
        """
        if pattern_id in self.patterns:
            pattern = self.patterns[pattern_id]
            if positive:
                pattern.confidence = min(1.0, pattern.confidence + 0.1)
                pattern.usage_count += 1
            else:
                pattern.confidence = max(0.1, pattern.confidence - 0.1)
    
    def find_matching_patterns(self, context: Dict[str, Any]) -> List[Tuple[str, float]]:
        """
        根据当前上下文查找匹配的模式
        
        Returns:
            模式ID和匹配度的列表（按匹配度排序）
        """
        matches = []
        
        for pattern_id, pattern in self.patterns.items():
            match_score = self._match_pattern(pattern, context)
            if match_score > 0.5:
                matches.append((pattern_id, match_score))
        
        return sorted(matches, key=lambda x: x[1], reverse=True)
    
    def _match_pattern(self, pattern: LearnedPattern, context: Dict[str, Any]) -> float:
        """计算模式与上下文的匹配度"""
        score = 0.0
        total_conditions = len(pattern.conditions)
        
        for condition in pattern.conditions:
            key = condition.get('key')
            value = condition.get('value')
            
            if key in context:
                if context[key] == value:
                    score += 1.0
                elif isinstance(context.get(key), str) and isinstance(value, str):
                    if value.lower() in context[key].lower():
                        score += 0.5
        
        return score / max(total_conditions, 1)
    
    def backflow_correction(self, original_content: str, corrected_content: str, context: Dict[str, Any]):
        """
        用户修改后的内容反向回流到知识图谱
        
        Args:
            original_content: AI生成的原始内容
            corrected_content: 用户修改后的内容
            context: 当时的上下文
        """
        if corrected_content != original_content:
            # 提取关键概念并建立关联
            self._extract_and_link_concepts(corrected_content, context)
            print(f"[记忆层] 内容修正已回流: {len(corrected_content)} 字符")
    
    def _extract_and_link_concepts(self, text: str, context: Dict[str, Any]):
        """从文本中提取概念并建立关联"""
        keywords = ['水源地', '噪声', '大气', '水环境', '敏感', '监测', '评价', '预测']
        
        found_concepts = []
        for keyword in keywords:
            if keyword in text:
                found_concepts.append(keyword)
        
        # 建立概念之间的关联
        for i, concept1 in enumerate(found_concepts):
            for concept2 in found_concepts[i+1:]:
                self.learn_association(concept1, concept2, 'co_occur')
    
    def get_recommendations(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        根据当前上下文获取推荐
        
        Returns:
            推荐的动作和置信度列表
        """
        recommendations = []
        
        # 基于知识图谱推荐
        for edge_key, edge in self.edges.items():
            if edge.weight > 0.8:
                source_node = self.nodes.get(edge.source)
                target_node = self.nodes.get(edge.target)
                if source_node and target_node:
                    recommendations.append({
                        'type': 'knowledge_association',
                        'source': source_node.label,
                        'target': target_node.label,
                        'relation': edge.relation,
                        'confidence': edge.weight
                    })
        
        # 基于模式推荐
        matching_patterns = self.find_matching_patterns(context)
        for pattern_id, score in matching_patterns[:3]:
            pattern = self.patterns[pattern_id]
            recommendations.append({
                'type': 'pattern_match',
                'action': pattern.action,
                'confidence': score * pattern.confidence
            })
        
        return sorted(recommendations, key=lambda x: x['confidence'], reverse=True)
    
    def export_knowledge_graph(self) -> Dict[str, Any]:
        """导出知识图谱用于可视化或训练"""
        return {
            'nodes': [{
                'id': node.node_id,
                'label': node.label,
                'type': node.node_type,
                'properties': node.properties
            } for node in self.nodes.values()],
            'edges': [{
                'id': edge.edge_id,
                'source': edge.source,
                'target': edge.target,
                'relation': edge.relation,
                'weight': edge.weight,
                'frequency': edge.frequency
            } for edge in self.edges.values()],
            'patterns': [{
                'id': pattern.pattern_id,
                'conditions': pattern.conditions,
                'action': pattern.action,
                'confidence': pattern.confidence,
                'usage_count': pattern.usage_count
            } for pattern in self.patterns.values()]
        }