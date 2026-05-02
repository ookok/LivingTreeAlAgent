"""
智能创作与专业审核增强系统 - 知识图谱
"""

import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field


@dataclass
class KnowledgeNode:
    """知识节点"""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    content: str = ""
    node_type: str = "concept"  # concept, entity, event, term
    domain: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    verified: bool = False
    quality_score: float = 0.0
    usage_count: int = 0


@dataclass
class KnowledgeRelation:
    """知识关系"""
    relation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""
    target_id: str = ""
    relation_type: str = ""  # is_a, part_of, related_to, causes, depends_on
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


class KnowledgeGraph:
    """知识图谱"""
    
    def __init__(self):
        self.nodes: Dict[str, KnowledgeNode] = {}
        self.relations: List[KnowledgeRelation] = []
        self.index_by_domain: Dict[str, Set[str]] = {}
        self.index_by_type: Dict[str, Set[str]] = {}
        self.relation_index: Dict[str, List[str]] = {}  # node_id -> [relation_ids]
    
    def add_node(self, node: KnowledgeNode) -> str:
        """添加节点"""
        self.nodes[node.node_id] = node
        
        # 更新索引
        if node.domain:
            if node.domain not in self.index_by_domain:
                self.index_by_domain[node.domain] = set()
            self.index_by_domain[node.domain].add(node.node_id)
        
        if node.node_type:
            if node.node_type not in self.index_by_type:
                self.index_by_type[node.node_type] = set()
            self.index_by_type[node.node_type].add(node.node_id)
        
        return node.node_id
    
    def add_relation(self, relation: KnowledgeRelation):
        """添加关系"""
        self.relations.append(relation)
        
        if relation.source_id not in self.relation_index:
            self.relation_index[relation.source_id] = []
        self.relation_index[relation.source_id].append(relation.relation_id)
    
    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        return self.nodes.get(node_id)
    
    def get_related_nodes(self, node_id: str, relation_type: str = None) -> List[KnowledgeNode]:
        """获取关联节点"""
        relation_ids = self.relation_index.get(node_id, [])
        related = []
        
        for rid in relation_ids:
            for rel in self.relations:
                if rel.relation_id == rid:
                    if relation_type and rel.relation_type != relation_type:
                        continue
                    target = self.nodes.get(rel.target_id)
                    if target:
                        related.append(target)
                    break
        
        return related
    
    def search(self, query: str, domain: str = None, limit: int = 10) -> List[KnowledgeNode]:
        """搜索"""
        results = []
        query_lower = query.lower()
        
        for node in self.nodes.values():
            if domain and node.domain != domain:
                continue
            
            score = 0
            if query_lower in node.title.lower():
                score += 10
            if query_lower in node.content.lower():
                score += 5
            
            if score > 0:
                results.append((score, node))
        
        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:limit]]
    
    def extract_from_text(self, text: str, domain: str = "") -> List[KnowledgeNode]:
        """从文本提取知识"""
        nodes = []
        
        # 提取术语
        terms = re.findall(r'[\u4e00-\u9fa5]{2,}(?:技术|方法|系统|理论|模型)', text)
        for term in set(terms):
            node = KnowledgeNode(
                title=term,
                content=f"从文本提取: {term}",
                node_type="term",
                domain=domain,
                quality_score=0.7
            )
            nodes.append(node)
            self.add_node(node)
        
        # 提取组织
        orgs = re.findall(r'([A-Z\u4e00-\u9fa5]{5,})(?:公司|机构|组织|单位)', text)
        for org in set(orgs):
            node = KnowledgeNode(
                title=org,
                content=f"组织: {org}",
                node_type="entity",
                domain=domain,
                quality_score=0.8
            )
            nodes.append(node)
            self.add_node(node)
        
        return nodes
    
    def get_statistics(self) -> Dict[str, Any]:
        """统计"""
        return {
            "total_nodes": len(self.nodes),
            "total_relations": len(self.relations),
            "by_domain": {d: len(ids) for d, ids in self.index_by_domain.items()},
            "by_type": {t: len(ids) for t, ids in self.index_by_type.items()},
        }


class KnowledgeBase:
    """知识库"""
    
    def __init__(self):
        self.graph = KnowledgeGraph()
        self.entries: Dict[str, Dict] = {}  # 知识条目
        self.categories: Dict[str, Set[str]] = {}  # 分类 -> 条目ID
        self.tag_index: Dict[str, Set[str]] = {}  # 标签 -> 条目ID
    
    def add_entry(self, entry: Dict) -> str:
        """添加知识条目"""
        entry_id = entry.get("id", str(uuid.uuid4()))
        entry["id"] = entry_id
        entry["created_at"] = datetime.now().isoformat()
        
        self.entries[entry_id] = entry
        
        # 更新索引
        category = entry.get("category")
        if category:
            if category not in self.categories:
                self.categories[category] = set()
            self.categories[category].add(entry_id)
        
        for tag in entry.get("tags", []):
            if tag not in self.tag_index:
                self.tag_index[tag] = set()
            self.tag_index[tag].add(entry_id)
        
        # 提取到图谱
        self.graph.extract_from_text(entry.get("content", ""), entry.get("domain", ""))
        
        return entry_id
    
    def search(self, query: str, category: str = None, tags: List[str] = None, limit: int = 20) -> List[Dict]:
        """搜索"""
        results = []
        query_lower = query.lower()
        
        for entry in self.entries.values():
            if category and entry.get("category") != category:
                continue
            
            if tags:
                entry_tags = set(entry.get("tags", []))
                if not any(t in entry_tags for t in tags):
                    continue
            
            score = 0
            if query_lower in entry.get("title", "").lower():
                score += 10
            if query_lower in entry.get("content", "").lower():
                score += 5
            
            if score > 0:
                results.append((score, entry))
        
        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:limit]]
    
    def recommend(self, entry_id: str, limit: int = 5) -> List[Dict]:
        """推荐相关"""
        entry = self.entries.get(entry_id)
        if not entry:
            return []
        
        tags = set(entry.get("tags", []))
        if not tags:
            return []
        
        candidates = set()
        for tag in tags:
            if tag in self.tag_index:
                candidates.update(self.tag_index[tag])
        
        candidates.discard(entry_id)
        
        scored = []
        for cid in candidates:
            other = self.entries.get(cid)
            if other:
                common_tags = len(tags & set(other.get("tags", [])))
                scored.append((common_tags, other))
        
        scored.sort(reverse=True)
        return [s[1] for s in scored[:limit]]
    
    def get_by_category(self, category: str) -> List[Dict]:
        """按分类获取"""
        entry_ids = self.categories.get(category, set())
        return [self.entries[eid] for eid in entry_ids if eid in self.entries]
    
    def get_statistics(self) -> Dict[str, Any]:
        """统计"""
        return {
            "total_entries": len(self.entries),
            "categories": {c: len(ids) for c, ids in self.categories.items()},
            "top_tags": sorted(
                [(t, len(ids)) for t, ids in self.tag_index.items()],
                key=lambda x: x[1], reverse=True
            )[:10],
            "graph_stats": self.graph.get_statistics()
        }


def create_knowledge_graph() -> KnowledgeGraph:
    return KnowledgeGraph()


def create_knowledge_base() -> KnowledgeBase:
    return KnowledgeBase()
