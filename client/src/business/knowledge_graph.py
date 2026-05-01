"""
Knowledge Graph - 知识图谱模块

核心功能：
1. 领域知识网络构建
2. 语义搜索和推理
3. 实体关系管理
4. 知识图谱可视化

设计理念：
- 支持多种知识表示形式
- 支持语义查询和推理
- 支持知识更新和演进
"""

import json
import networkx as nx
from typing import Dict, Any, Optional, List, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

# 可选导入 matplotlib
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    plt = None

logger = logging.getLogger(__name__)


class EntityType(Enum):
    """实体类型"""
    PERSON = "person"
    ORGANIZATION = "organization"
    PROJECT = "project"
    MODULE = "module"
    FUNCTION = "function"
    CLASS = "class"
    CONCEPT = "concept"
    DOCUMENT = "document"
    TAG = "tag"


class RelationType(Enum):
    """关系类型"""
    PART_OF = "part_of"
    DEPENDS_ON = "depends_on"
    IMPLEMENTS = "implements"
    USES = "uses"
    CONTAINS = "contains"
    RELATED_TO = "related_to"
    DEFINES = "defines"
    REFERENCES = "references"


@dataclass
class Entity:
    """知识图谱实体"""
    id: str
    name: str
    type: EntityType
    description: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Relation:
    """知识图谱关系"""
    source_id: str
    target_id: str
    type: RelationType
    weight: float = 1.0
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)


class KnowledgeGraph:
    """
    知识图谱
    
    核心特性：
    1. 实体管理 - 添加、更新、删除实体
    2. 关系管理 - 建立实体间关系
    3. 语义搜索 - 基于图的搜索
    4. 知识推理 - 基于关系的推理
    5. 可视化 - 图的可视化展示
    """
    
    def __init__(self):
        self._entities: Dict[str, Entity] = {}
        self._relations: List[Relation] = []
        self._graph = nx.DiGraph()
        logger.info("✅ KnowledgeGraph 初始化完成")
    
    def add_entity(self, id: str, name: str, type: EntityType, 
                  description: str = "", **attributes) -> Entity:
        """添加实体"""
        entity = Entity(
            id=id,
            name=name,
            type=type,
            description=description,
            attributes=attributes
        )
        self._entities[id] = entity
        self._graph.add_node(id, label=name, type=type.value)
        return entity
    
    def get_entity(self, id: str) -> Optional[Entity]:
        """获取实体"""
        return self._entities.get(id)
    
    def update_entity(self, id: str, **kwargs):
        """更新实体"""
        if id not in self._entities:
            raise ValueError(f"实体不存在: {id}")
        
        entity = self._entities[id]
        if "name" in kwargs:
            entity.name = kwargs["name"]
        if "description" in kwargs:
            entity.description = kwargs["description"]
        if "attributes" in kwargs:
            entity.attributes.update(kwargs["attributes"])
        entity.updated_at = datetime.now()
        
        # 更新图节点
        self._graph.nodes[id]["label"] = entity.name
    
    def delete_entity(self, id: str):
        """删除实体"""
        if id not in self._entities:
            return
        
        # 删除相关关系
        self._relations = [r for r in self._relations if r.source_id != id and r.target_id != id]
        
        # 删除实体
        del self._entities[id]
        self._graph.remove_node(id)
    
    def add_relation(self, source_id: str, target_id: str, 
                    type: RelationType, weight: float = 1.0, description: str = "") -> Relation:
        """添加关系"""
        if source_id not in self._entities:
            raise ValueError(f"源实体不存在: {source_id}")
        if target_id not in self._entities:
            raise ValueError(f"目标实体不存在: {target_id}")
        
        relation = Relation(
            source_id=source_id,
            target_id=target_id,
            type=type,
            weight=weight,
            description=description
        )
        
        self._relations.append(relation)
        self._graph.add_edge(source_id, target_id, type=type.value, weight=weight)
        
        return relation
    
    def get_relations(self, entity_id: str) -> List[Relation]:
        """获取实体的所有关系"""
        return [
            r for r in self._relations 
            if r.source_id == entity_id or r.target_id == entity_id
        ]
    
    def search(self, query: str) -> List[Tuple[Entity, float]]:
        """
        语义搜索
        
        Args:
            query: 搜索查询
        
        Returns:
            实体列表及其匹配度
        """
        results = []
        
        for entity in self._entities.values():
            score = 0
            
            # 名称匹配
            if query.lower() in entity.name.lower():
                score += 0.5
            
            # 描述匹配
            if query.lower() in entity.description.lower():
                score += 0.3
            
            # 属性匹配
            for value in entity.attributes.values():
                if query.lower() in str(value).lower():
                    score += 0.1
            
            if score > 0:
                results.append((entity, score))
        
        # 按匹配度排序
        results.sort(key=lambda x: -x[1])
        return results
    
    def find_path(self, source_id: str, target_id: str) -> Optional[List[str]]:
        """
        查找实体间的路径
        
        Args:
            source_id: 源实体ID
            target_id: 目标实体ID
        
        Returns:
            路径上的实体ID列表
        """
        try:
            path = nx.shortest_path(self._graph, source_id, target_id)
            return path
        except nx.NetworkXNoPath:
            return None
    
    def get_neighbors(self, entity_id: str, depth: int = 1) -> List[Entity]:
        """
        获取实体的邻居节点
        
        Args:
            entity_id: 实体ID
            depth: 搜索深度
        
        Returns:
            邻居实体列表
        """
        neighbors = set()
        
        for relation in self._relations:
            if relation.source_id == entity_id:
                neighbors.add(relation.target_id)
            elif relation.target_id == entity_id:
                neighbors.add(relation.source_id)
        
        return [self._entities.get(n) for n in neighbors if self._entities.get(n)]
    
    def infer_relations(self) -> List[Relation]:
        """
        推理新关系
        
        Returns:
            推理出的新关系列表
        """
        inferred = []
        
        # 传递性推理：如果 A -> B 且 B -> C，则 A -> C
        for r1 in self._relations:
            for r2 in self._relations:
                if r1.target_id == r2.source_id:
                    # 检查是否已存在
                    exists = any(
                        r.source_id == r1.source_id and r.target_id == r2.target_id
                        for r in self._relations
                    )
                    
                    if not exists:
                        inferred.append(Relation(
                            source_id=r1.source_id,
                            target_id=r2.target_id,
                            type=RelationType.RELATED_TO,
                            weight=min(r1.weight, r2.weight) * 0.5,
                            description="推理得出"
                        ))
        
        return inferred
    
    def visualize(self, output_path: Optional[str] = None):
        """可视化知识图谱"""
        if not MATPLOTLIB_AVAILABLE:
            print("⚠️ matplotlib 不可用，跳过可视化")
            return
        
        plt.figure(figsize=(12, 8))
        
        # 布局
        pos = nx.spring_layout(self._graph, k=0.15, iterations=20)
        
        # 绘制节点
        node_colors = []
        for node in self._graph.nodes:
            entity = self._entities.get(node)
            if entity:
                if entity.type == EntityType.MODULE:
                    node_colors.append('#4a90d9')
                elif entity.type == EntityType.FUNCTION:
                    node_colors.append('#67c23a')
                elif entity.type == EntityType.CLASS:
                    node_colors.append('#e6a23c')
                else:
                    node_colors.append('#909399')
            else:
                node_colors.append('#909399')
        
        nx.draw(self._graph, pos, node_color=node_colors, node_size=1500, 
                with_labels=True, font_size=8, font_color='white',
                edge_color='#d9d9d9', linewidths=2)
        
        # 添加图例
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#4a90d9', label='Module'),
            Patch(facecolor='#67c23a', label='Function'),
            Patch(facecolor='#e6a23c', label='Class'),
            Patch(facecolor='#909399', label='Other')
        ]
        plt.legend(handles=legend_elements, loc='upper right')
        
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"✅ 知识图谱已保存到: {output_path}")
        else:
            plt.show()
    
    def export_to_json(self, file_path: str):
        """导出为 JSON"""
        data = {
            "entities": [
                {
                    "id": e.id,
                    "name": e.name,
                    "type": e.type.value,
                    "description": e.description,
                    "attributes": e.attributes
                } for e in self._entities.values()
            ],
            "relations": [
                {
                    "source_id": r.source_id,
                    "target_id": r.target_id,
                    "type": r.type.value,
                    "weight": r.weight,
                    "description": r.description
                } for r in self._relations
            ]
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 知识图谱已导出到: {file_path}")
    
    def import_from_json(self, file_path: str):
        """从 JSON 导入"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 导入实体
        for entity_data in data.get("entities", []):
            self.add_entity(
                id=entity_data["id"],
                name=entity_data["name"],
                type=EntityType(entity_data["type"]),
                description=entity_data.get("description", ""),
                **entity_data.get("attributes", {})
            )
        
        # 导入关系
        for relation_data in data.get("relations", []):
            self.add_relation(
                source_id=relation_data["source_id"],
                target_id=relation_data["target_id"],
                type=RelationType(relation_data["type"]),
                weight=relation_data.get("weight", 1.0),
                description=relation_data.get("description", "")
            )
        
        print(f"✅ 知识图谱已从 {file_path} 导入")


# 全局单例
_global_knowledge_graph: Optional[KnowledgeGraph] = None


def get_knowledge_graph() -> KnowledgeGraph:
    """获取全局知识图谱单例"""
    global _global_knowledge_graph
    if _global_knowledge_graph is None:
        _global_knowledge_graph = KnowledgeGraph()
    return _global_knowledge_graph


# 测试函数
def test_knowledge_graph():
    """测试知识图谱"""
    print("🧪 测试知识图谱")
    print("="*60)
    
    kg = get_knowledge_graph()
    
    # 添加实体
    print("\n📥 添加实体:")
    kg.add_entity("auth_module", "认证模块", EntityType.MODULE, description="用户认证相关功能")
    kg.add_entity("user_service", "UserService", EntityType.CLASS, description="用户服务类")
    kg.add_entity("login_func", "login()", EntityType.FUNCTION, description="用户登录函数")
    kg.add_entity("jwt_concept", "JWT", EntityType.CONCEPT, description="JSON Web Token")
    
    print("✅ 实体添加成功")
    
    # 添加关系
    print("\n🔗 添加关系:")
    kg.add_relation("auth_module", "user_service", RelationType.CONTAINS, description="认证模块包含用户服务")
    kg.add_relation("user_service", "login_func", RelationType.CONTAINS, description="用户服务包含登录函数")
    kg.add_relation("login_func", "jwt_concept", RelationType.USES, description="登录函数使用JWT")
    
    print("✅ 关系添加成功")
    
    # 搜索测试
    print("\n🔍 搜索测试:")
    results = kg.search("登录")
    for entity, score in results:
        print(f"   [{score:.2f}] {entity.name} - {entity.description}")
    
    # 路径查找测试
    print("\n📍 路径查找:")
    path = kg.find_path("auth_module", "jwt_concept")
    if path:
        print(f"   路径: {' -> '.join(path)}")
    
    # 推理测试
    print("\n🧠 关系推理:")
    inferred = kg.infer_relations()
    print(f"   推理出 {len(inferred)} 个新关系")
    
    # 导出测试
    print("\n📤 导出测试:")
    kg.export_to_json("test_knowledge_graph.json")
    
    print("\n🎉 知识图谱测试完成！")
    return True


if __name__ == "__main__":
    test_knowledge_graph()