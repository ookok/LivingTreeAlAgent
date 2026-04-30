"""
MentalModelBuilder - 心理表征模块

将文档解析结果转化为"概念图"数据结构，支持推理。

核心功能：
1. 文本解析与概念提取
2. 关系识别与构建
3. 命题生成与推理支持
4. 知识图谱集成

设计原理：
- 采用"概念-关系-命题"三元组作为统一中间表示
- 支持图数据库持久化
- 提供推理接口，支持逻辑推理和联想

使用示例：
    builder = MentalModelBuilder()
    
    # 从文本构建心理模型
    text = "人工智能是一门研究、开发用于模拟、延伸和扩展人的智能的理论、方法、技术及应用系统的新的技术科学。"
    graph = builder.build_from_text(text)
    
    # 查询概念
    nodes = graph.search("人工智能")
    
    # 获取相关概念
    related = graph.get_related("人工智能", relation_type="is_a")
"""

import uuid
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field


@dataclass
class ConceptNode:
    """概念节点"""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    label: str = ""
    concept_type: str = "concept"  # concept, entity, event, term, proposition
    definition: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    confidence: float = 1.0
    source: str = ""
    domain: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "label": self.label,
            "concept_type": self.concept_type,
            "definition": self.definition,
            "properties": self.properties,
            "confidence": self.confidence,
            "source": self.source,
            "domain": self.domain
        }


@dataclass
class Relation:
    """概念关系"""
    relation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""
    target_id: str = ""
    relation_type: str = "related_to"  # is_a, part_of, related_to, causes, depends_on, implies
    weight: float = 1.0
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "weight": self.weight,
            "description": self.description
        }


@dataclass
class Proposition:
    """命题 - 由概念和关系组成的语义单元"""
    proposition_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subject_id: str = ""
    predicate: str = ""
    object_id: str = ""
    truth_value: float = 1.0
    evidence: List[str] = field(default_factory=list)
    context: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposition_id": self.proposition_id,
            "subject_id": self.subject_id,
            "predicate": self.predicate,
            "object_id": self.object_id,
            "truth_value": self.truth_value,
            "evidence": self.evidence,
            "context": self.context
        }


class ConceptGraph:
    """概念图 - 知识的统一中间表示"""
    
    def __init__(self):
        self.nodes: Dict[str, ConceptNode] = {}
        self.relations: List[Relation] = []
        self.propositions: List[Proposition] = []
        
        # 索引
        self.label_index: Dict[str, Set[str]] = {}  # label -> node_ids
        self.type_index: Dict[str, Set[str]] = {}   # concept_type -> node_ids
        self.domain_index: Dict[str, Set[str]] = {} # domain -> node_ids
        self.source_index: Dict[str, Set[str]] = {} # source -> node_ids
        self.relation_index: Dict[str, List[str]] = {}  # source_id -> relation_ids
    
    def add_node(self, node: ConceptNode) -> str:
        """添加概念节点"""
        self.nodes[node.node_id] = node
        
        # 更新索引
        self._update_index(self.label_index, node.label, node.node_id)
        self._update_index(self.type_index, node.concept_type, node.node_id)
        self._update_index(self.domain_index, node.domain, node.node_id)
        self._update_index(self.source_index, node.source, node.node_id)
        
        return node.node_id
    
    def add_relation(self, relation: Relation):
        """添加关系"""
        self.relations.append(relation)
        
        if relation.source_id not in self.relation_index:
            self.relation_index[relation.source_id] = []
        self.relation_index[relation.source_id].append(relation.relation_id)
    
    def add_proposition(self, proposition: Proposition):
        """添加命题"""
        self.propositions.append(proposition)
    
    def get_node(self, node_id: str) -> Optional[ConceptNode]:
        return self.nodes.get(node_id)
    
    def get_nodes_by_label(self, label: str) -> List[ConceptNode]:
        """按标签查询节点"""
        node_ids = self.label_index.get(label, set())
        return [self.nodes[node_id] for node_id in node_ids if node_id in self.nodes]
    
    def get_nodes_by_type(self, concept_type: str) -> List[ConceptNode]:
        """按类型查询节点"""
        node_ids = self.type_index.get(concept_type, set())
        return [self.nodes[node_id] for node_id in node_ids if node_id in self.nodes]
    
    def get_nodes_by_domain(self, domain: str) -> List[ConceptNode]:
        """按领域查询节点"""
        node_ids = self.domain_index.get(domain, set())
        return [self.nodes[node_id] for node_id in node_ids if node_id in self.nodes]
    
    def get_related_nodes(self, node_id: str, relation_type: str = None) -> List[Tuple[ConceptNode, Relation]]:
        """获取关联节点"""
        results = []
        relation_ids = self.relation_index.get(node_id, [])
        
        for rid in relation_ids:
            for rel in self.relations:
                if rel.relation_id == rid:
                    if relation_type and rel.relation_type != relation_type:
                        continue
                    target_node = self.nodes.get(rel.target_id)
                    if target_node:
                        results.append((target_node, rel))
                    break
        
        return results
    
    def search(self, query: str, domain: str = None, limit: int = 10) -> List[ConceptNode]:
        """搜索概念"""
        results = []
        query_lower = query.lower()
        
        for node in self.nodes.values():
            if domain and node.domain != domain:
                continue
            
            score = 0
            if query_lower in node.label.lower():
                score += 10
            if query_lower in node.definition.lower():
                score += 5
            for prop in node.properties.values():
                if query_lower in str(prop).lower():
                    score += 2
            
            if score > 0:
                results.append((score, node))
        
        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:limit]]
    
    def infer(self, node_id: str, max_depth: int = 3) -> List[Tuple[ConceptNode, List[Relation]]]:
        """推理 - 获取节点的传递闭包"""
        visited = set()
        results = []
        
        def dfs(current_id: str, path: List[Relation], depth: int):
            if depth >= max_depth or current_id in visited:
                return
            
            visited.add(current_id)
            related = self.get_related_nodes(current_id)
            
            for target_node, relation in related:
                new_path = path + [relation]
                results.append((target_node, new_path))
                dfs(target_node.node_id, new_path, depth + 1)
        
        dfs(node_id, [], 0)
        return results
    
    def to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        return {
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
            "relations": [rel.to_dict() for rel in self.relations],
            "propositions": [prop.to_dict() for prop in self.propositions],
            "statistics": self.get_statistics()
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_nodes": len(self.nodes),
            "total_relations": len(self.relations),
            "total_propositions": len(self.propositions),
            "types": {t: len(ids) for t, ids in self.type_index.items()},
            "domains": {d: len(ids) for d, ids in self.domain_index.items()}
        }
    
    def _update_index(self, index: Dict[str, Set[str]], key: str, value: str):
        """更新索引"""
        if key:
            if key not in index:
                index[key] = set()
            index[key].add(value)


class MentalModelBuilder:
    """心理模型构建器"""
    
    def __init__(self, knowledge_graph=None):
        self.knowledge_graph = knowledge_graph
        self._relation_patterns = {
            "is_a": [r"([\u4e00-\u9fa5a-zA-Z]+)是([\u4e00-\u9fa5a-zA-Z]+)", r"([\u4e00-\u9fa5a-zA-Z]+)属于([\u4e00-\u9fa5a-zA-Z]+)"],
            "part_of": [r"([\u4e00-\u9fa5a-zA-Z]+)包含([\u4e00-\u9fa5a-zA-Z]+)", r"([\u4e00-\u9fa5a-zA-Z]+)由([\u4e00-\u9fa5a-zA-Z]+)组成"],
            "causes": [r"([\u4e00-\u9fa5a-zA-Z]+)导致([\u4e00-\u9fa5a-zA-Z]+)", r"([\u4e00-\u9fa5a-zA-Z]+)引起([\u4e00-\u9fa5a-zA-Z]+)"],
            "related_to": [r"([\u4e00-\u9fa5a-zA-Z]+)与([\u4e00-\u9fa5a-zA-Z]+)相关", r"([\u4e00-\u9fa5a-zA-Z]+)涉及([\u4e00-\u9fa5a-zA-Z]+)"]
        }
    
    def build_from_text(self, text: str, domain: str = "", source: str = "text") -> ConceptGraph:
        """从文本构建概念图"""
        graph = ConceptGraph()
        
        # 提取概念
        concepts = self._extract_concepts(text)
        
        # 添加节点
        node_mapping = {}
        for concept in concepts:
            node = ConceptNode(
                label=concept["label"],
                concept_type=concept["type"],
                definition=concept.get("definition", ""),
                confidence=concept.get("confidence", 0.8),
                source=source,
                domain=domain
            )
            node_id = graph.add_node(node)
            node_mapping[concept["label"]] = node_id
        
        # 提取关系
        relations = self._extract_relations(text, node_mapping)
        for rel in relations:
            if rel["source"] in node_mapping and rel["target"] in node_mapping:
                relation = Relation(
                    source_id=node_mapping[rel["source"]],
                    target_id=node_mapping[rel["target"]],
                    relation_type=rel["type"],
                    weight=rel.get("weight", 1.0),
                    description=rel.get("description", "")
                )
                graph.add_relation(relation)
        
        return graph
    
    def build_from_document(self, document: Dict) -> ConceptGraph:
        """从文档构建概念图"""
        text = document.get("content", "")
        domain = document.get("domain", "")
        source = document.get("source", "document")
        
        graph = self.build_from_text(text, domain, source)
        
        # 添加文档元信息作为属性
        metadata_node = ConceptNode(
            label=f"文档_{document.get('title', 'unknown')}",
            concept_type="document",
            definition=document.get("summary", ""),
            properties={
                "title": document.get("title"),
                "author": document.get("author"),
                "date": document.get("date"),
                "url": document.get("url")
            },
            source=source,
            domain=domain
        )
        graph.add_node(metadata_node)
        
        return graph
    
    def merge_graphs(self, graphs: List[ConceptGraph]) -> ConceptGraph:
        """合并多个概念图"""
        merged = ConceptGraph()
        
        for graph in graphs:
            # 合并节点
            for node_id, node in graph.nodes.items():
                existing = merged.get_nodes_by_label(node.label)
                if existing:
                    existing_node = existing[0]
                    existing_node.confidence = max(existing_node.confidence, node.confidence)
                else:
                    merged.add_node(node)
            
            # 合并关系
            for relation in graph.relations:
                merged.add_relation(relation)
            
            # 合并命题
            for prop in graph.propositions:
                merged.add_proposition(prop)
        
        return merged
    
    def _extract_concepts(self, text: str) -> List[Dict]:
        """从文本中提取概念"""
        concepts = []
        
        # 提取中文术语（2个及以上字符的词）
        chinese_terms = re.findall(r'[\u4e00-\u9fa5]{2,}(?:技术|方法|系统|理论|模型|概念|算法|数据|智能|学习)', text)
        for term in set(chinese_terms):
            concepts.append({
                "label": term,
                "type": "term",
                "confidence": 0.85
            })
        
        # 提取英文术语
        english_terms = re.findall(r'[A-Za-z][a-z]+(?:[A-Z][a-z]+)*', text)
        for term in set(english_terms):
            if len(term) > 2:
                concepts.append({
                    "label": term,
                    "type": "term",
                    "confidence": 0.7
                })
        
        # 提取实体（组织、人物）
        organizations = re.findall(r'([A-Z\u4e00-\u9fa5]{3,})(?:公司|机构|组织|研究院|大学)', text)
        for org in set(organizations):
            concepts.append({
                "label": org,
                "type": "entity",
                "confidence": 0.9
            })
        
        # 提取事件
        events = re.findall(r'(发生|出现|进行|完成|启动)([\u4e00-\u9fa5]{2,})', text)
        for _, event in events:
            concepts.append({
                "label": event,
                "type": "event",
                "confidence": 0.75
            })
        
        return concepts
    
    def _extract_relations(self, text: str, node_mapping: Dict[str, str]) -> List[Dict]:
        """从文本中提取关系"""
        relations = []
        
        text_lower = text.lower()
        
        for relation_type, patterns in self._relation_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for source, target in matches:
                    if source in node_mapping and target in node_mapping:
                        relations.append({
                            "source": source,
                            "target": target,
                            "type": relation_type,
                            "weight": 0.8
                        })
        
        return relations
    
    def validate_graph(self, graph: ConceptGraph) -> Dict[str, Any]:
        """验证概念图的完整性"""
        issues = []
        
        # 检查孤立节点
        connected_nodes = set()
        for rel in graph.relations:
            connected_nodes.add(rel.source_id)
            connected_nodes.add(rel.target_id)
        
        for node_id in graph.nodes:
            if node_id not in connected_nodes and len(graph.nodes) > 1:
                issues.append(f"孤立节点: {graph.nodes[node_id].label}")
        
        # 检查低置信度节点
        for node in graph.nodes.values():
            if node.confidence < 0.5:
                issues.append(f"低置信度节点: {node.label} ({node.confidence})")
        
        # 检查重复标签
        label_counts = {}
        for node in graph.nodes.values():
            label_counts[node.label] = label_counts.get(node.label, 0) + 1
        
        for label, count in label_counts.items():
            if count > 1:
                issues.append(f"重复标签: {label} ({count}次)")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "statistics": graph.get_statistics()
        }


def create_concept_graph() -> ConceptGraph:
    """创建概念图实例"""
    return ConceptGraph()


def create_mental_model_builder(knowledge_graph=None) -> MentalModelBuilder:
    """创建心理模型构建器"""
    return MentalModelBuilder(knowledge_graph)
