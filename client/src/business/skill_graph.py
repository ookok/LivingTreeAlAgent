"""
技能图谱 (Skill Graph)
======================

参考: github.com/vercel/find-skills

实现技能关系图谱功能：
1. 技能图谱构建 - 构建技能之间的关系图谱
2. 技能路径查找 - 查找技能之间的路径
3. 技能聚类 - 将相关技能分组
4. 技能影响力分析 - 分析技能的影响力

核心特性：
- 图谱构建器 - 构建技能关系图谱
- 路径查找器 - 查找技能路径
- 聚类分析器 - 技能聚类
- 影响力分析器 - 分析技能影响力

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

logger = __import__('logging').getLogger(__name__)


class RelationType(Enum):
    """关系类型"""
    DEPENDS_ON = "depends_on"           # 依赖
    RELATED_TO = "related_to"           # 相关
    USED_TOGETHER = "used_together"     # 一起使用
    ALTERNATIVE = "alternative"         # 替代
    PRE_REQUISITE = "pre_requisite"     # 前置条件


@dataclass
class SkillNode:
    """技能节点"""
    name: str
    category: str
    level: str
    score: float = 0.0
    connections: List[str] = field(default_factory=list)


@dataclass
class SkillEdge:
    """技能关系边"""
    source: str
    target: str
    relation_type: RelationType
    weight: float = 1.0


@dataclass
class PathResult:
    """路径结果"""
    path: List[str]
    distance: float
    relations: List[SkillEdge]


@dataclass
class SkillCluster:
    """技能聚类"""
    name: str
    skills: List[str]
    centroid: str
    cohesion: float = 0.0


class SkillGraph:
    """
    技能图谱
    
    功能：
    1. 构建技能关系图谱
    2. 查找技能路径
    3. 技能聚类
    4. 影响力分析
    """
    
    def __init__(self):
        # 节点集合
        self._nodes: Dict[str, SkillNode] = {}
        
        # 边集合
        self._edges: List[SkillEdge] = []
        
        # 邻接表
        self._adjacency: Dict[str, List[Tuple[str, RelationType, float]]] = {}
        
        # 预定义的技能关系
        self._predefined_relations = [
            # LLM 相关
            ("llm", "rag", RelationType.USED_TOGETHER, 0.9),
            ("llm", "prompt", RelationType.USED_TOGETHER, 0.8),
            ("llm", "api", RelationType.USED_TOGETHER, 0.7),
            
            # RAG 相关
            ("rag", "embedding", RelationType.DEPENDS_ON, 0.95),
            ("rag", "vector_database", RelationType.DEPENDS_ON, 0.9),
            ("rag", "search", RelationType.USED_TOGETHER, 0.8),
            
            # Python 相关
            ("python", "asyncio", RelationType.USED_TOGETHER, 0.8),
            ("python", "pyqt", RelationType.USED_TOGETHER, 0.7),
            ("python", "fastapi", RelationType.USED_TOGETHER, 0.8),
            
            # Web 相关
            ("api", "database", RelationType.DEPENDS_ON, 0.85),
            ("api", "authentication", RelationType.USED_TOGETHER, 0.75),
            
            # DevOps 相关
            ("docker", "kubernetes", RelationType.USED_TOGETHER, 0.9),
            ("docker", "deployment", RelationType.USED_TOGETHER, 0.8),
            
            # 测试相关
            ("testing", "python", RelationType.USED_TOGETHER, 0.8),
            ("testing", "api", RelationType.USED_TOGETHER, 0.7),
        ]
    
    def add_node(self, skill_name: str, category: str = "other", level: str = "intermediate", score: float = 0.0):
        """
        添加技能节点
        
        Args:
            skill_name: 技能名称
            category: 分类
            level: 级别
            score: 分数
        """
        if skill_name not in self._nodes:
            self._nodes[skill_name] = SkillNode(
                name=skill_name,
                category=category,
                level=level,
                score=score,
                connections=[],
            )
            self._adjacency[skill_name] = []
    
    def add_edge(self, source: str, target: str, relation_type: RelationType = RelationType.RELATED_TO, weight: float = 1.0):
        """
        添加技能关系边
        
        Args:
            source: 源技能
            target: 目标技能
            relation_type: 关系类型
            weight: 权重
        """
        # 确保节点存在
        if source not in self._nodes:
            self.add_node(source)
        if target not in self._nodes:
            self.add_node(target)
        
        # 添加边
        edge = SkillEdge(
            source=source,
            target=target,
            relation_type=relation_type,
            weight=weight,
        )
        self._edges.append(edge)
        
        # 更新邻接表
        self._adjacency[source].append((target, relation_type, weight))
        self._adjacency[target].append((source, relation_type, weight))
        
        # 更新节点连接
        self._nodes[source].connections.append(target)
        self._nodes[target].connections.append(source)
    
    def build_from_skills(self, skills: List[dict]):
        """
        从技能列表构建图谱
        
        Args:
            skills: 技能列表
        """
        # 添加节点
        for skill in skills:
            self.add_node(
                skill_name=skill.get("name", ""),
                category=skill.get("category", "other"),
                level=skill.get("level", "intermediate"),
                score=skill.get("score", 0.0),
            )
        
        # 添加预定义关系
        for source, target, relation, weight in self._predefined_relations:
            if source in self._nodes and target in self._nodes:
                self.add_edge(source, target, relation, weight)
        
        # 添加基于分类的关系
        self._add_category_relations()
    
    def _add_category_relations(self):
        """添加基于分类的关系"""
        # 按分类分组
        categories = {}
        for skill_name, node in self._nodes.items():
            if node.category not in categories:
                categories[node.category] = []
            categories[node.category].append(skill_name)
        
        # 同一分类的技能相互关联
        for category, skills in categories.items():
            for i, skill1 in enumerate(skills):
                for skill2 in skills[i+1:]:
                    if skill1 != skill2:
                        self.add_edge(skill1, skill2, RelationType.RELATED_TO, 0.5)
    
    def find_path(self, source: str, target: str) -> Optional[PathResult]:
        """
        查找技能路径
        
        Args:
            source: 源技能
            target: 目标技能
            
        Returns:
            路径结果
        """
        if source not in self._nodes or target not in self._nodes:
            return None
        
        # BFS 查找路径
        visited = {source}
        queue = [(source, [source], [])]
        
        while queue:
            current, path, relations = queue.pop(0)
            
            if current == target:
                return PathResult(
                    path=path,
                    distance=len(path) - 1,
                    relations=relations,
                )
            
            for neighbor, relation_type, weight in self._adjacency.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    new_relations = relations + [SkillEdge(
                        source=current,
                        target=neighbor,
                        relation_type=relation_type,
                        weight=weight,
                    )]
                    queue.append((neighbor, path + [neighbor], new_relations))
        
        return None
    
    def find_shortest_path(self, source: str, target: str) -> Optional[PathResult]:
        """
        查找最短路径
        
        Args:
            source: 源技能
            target: 目标技能
            
        Returns:
            最短路径结果
        """
        if source not in self._nodes or target not in self._nodes:
            return None
        
        # Dijkstra 算法
        distances = {node: float('inf') for node in self._nodes}
        distances[source] = 0
        previous = {}
        visited = set()
        
        while len(visited) < len(self._nodes):
            # 找到未访问的最小距离节点
            min_dist = float('inf')
            current = None
            for node in self._nodes:
                if node not in visited and distances[node] < min_dist:
                    min_dist = distances[node]
                    current = node
            
            if current is None:
                break
            
            visited.add(current)
            
            # 更新邻居距离
            for neighbor, relation_type, weight in self._adjacency.get(current, []):
                if neighbor not in visited:
                    new_dist = distances[current] + (1 - weight)  # 权重越高，距离越短
                    if new_dist < distances[neighbor]:
                        distances[neighbor] = new_dist
                        previous[neighbor] = current
        
        # 重建路径
        if target not in previous:
            return None
        
        path = []
        current = target
        while current != source:
            path.insert(0, current)
            current = previous.get(current)
            if current is None:
                return None
        
        path.insert(0, source)
        
        return PathResult(
            path=path,
            distance=distances[target],
            relations=[],
        )
    
    def cluster(self, min_size: int = 2) -> List[SkillCluster]:
        """
        技能聚类
        
        Args:
            min_size: 最小聚类大小
            
        Returns:
            聚类结果
        """
        clusters = []
        visited = set()
        
        for skill_name in self._nodes:
            if skill_name not in visited:
                # BFS 找到连通分量
                cluster_skills = []
                queue = [skill_name]
                local_visited = set()
                
                while queue:
                    current = queue.pop(0)
                    if current not in local_visited:
                        local_visited.add(current)
                        cluster_skills.append(current)
                        for neighbor, _, _ in self._adjacency.get(current, []):
                            if neighbor not in local_visited:
                                queue.append(neighbor)
                
                # 标记为已访问
                visited.update(local_visited)
                
                # 过滤小聚类
                if len(cluster_skills) >= min_size:
                    # 找到中心节点（连接最多的节点）
                    centroid = max(cluster_skills, key=lambda s: len(self._nodes[s].connections))
                    
                    # 计算内聚度
                    cohesion = self._calculate_cohesion(cluster_skills)
                    
                    clusters.append(SkillCluster(
                        name=f"cluster_{centroid}",
                        skills=cluster_skills,
                        centroid=centroid,
                        cohesion=cohesion,
                    ))
        
        return clusters
    
    def _calculate_cohesion(self, skills: List[str]) -> float:
        """计算聚类内聚度"""
        if len(skills) < 2:
            return 0.0
        
        total_connections = 0
        possible_connections = len(skills) * (len(skills) - 1) / 2
        
        for i, skill1 in enumerate(skills):
            for skill2 in skills[i+1:]:
                # 检查是否有连接
                for neighbor, _, _ in self._adjacency.get(skill1, []):
                    if neighbor == skill2:
                        total_connections += 1
                        break
        
        return total_connections / possible_connections if possible_connections > 0 else 0.0
    
    def analyze_influence(self) -> Dict[str, float]:
        """
        分析技能影响力
        
        Returns:
            技能影响力字典
        """
        influence = {}
        
        for skill_name, node in self._nodes.items():
            # 基础影响力 = 连接数 + 技能分数
            base_score = len(node.connections) + node.score
            
            # 考虑连接权重
            weighted_score = 0
            for neighbor, relation_type, weight in self._adjacency.get(skill_name, []):
                neighbor_node = self._nodes.get(neighbor)
                if neighbor_node:
                    weighted_score += weight * (1 + neighbor_node.score)
            
            # 综合影响力
            influence[skill_name] = base_score + weighted_score * 0.5
        
        # 归一化
        max_influence = max(influence.values()) if influence else 1.0
        for skill_name in influence:
            influence[skill_name] /= max_influence
        
        return influence
    
    def get_neighbors(self, skill_name: str, depth: int = 1) -> List[str]:
        """
        获取技能的邻居
        
        Args:
            skill_name: 技能名称
            depth: 深度
            
        Returns:
            邻居技能列表
        """
        if skill_name not in self._nodes:
            return []
        
        visited = {skill_name}
        result = []
        queue = [(skill_name, 0)]
        
        while queue:
            current, current_depth = queue.pop(0)
            
            if current_depth > 0:
                result.append(current)
            
            if current_depth < depth:
                for neighbor, _, _ in self._adjacency.get(current, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, current_depth + 1))
        
        return result
    
    def get_nodes(self) -> List[SkillNode]:
        """获取所有节点"""
        return list(self._nodes.values())
    
    def get_edges(self) -> List[SkillEdge]:
        """获取所有边"""
        return self._edges.copy()
    
    def get_stats(self) -> Dict[str, int]:
        """获取图谱统计"""
        return {
            "nodes": len(self._nodes),
            "edges": len(self._edges),
            "avg_connections": sum(len(n.connections) for n in self._nodes.values()) / max(len(self._nodes), 1),
        }


# 便捷函数
def create_skill_graph() -> SkillGraph:
    """创建技能图谱"""
    return SkillGraph()


__all__ = [
    "RelationType",
    "SkillNode",
    "SkillEdge",
    "PathResult",
    "SkillCluster",
    "SkillGraph",
    "create_skill_graph",
]
