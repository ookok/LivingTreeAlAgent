"""
知识图谱编辑器 (Knowledge Graph Editor)

核心功能：
1. 自定义知识图谱结构
2. 内容难度分级
3. 个性化偏好权重设置
4. 学习路径动态生成

参考 Wondering 的自定义模式设计
"""

import json
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class KnowledgeNode:
    """知识节点"""
    id: str
    title: str
    content: str
    difficulty: int = 1  # 1-5 级难度
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    weight: float = 1.0  # 用户偏好权重
    mastered: bool = False
    last_accessed: float = 0.0
    access_count: int = 0


@dataclass
class KnowledgeEdge:
    """知识关系边"""
    source: str
    target: str
    relation: str  # prerequisite, related, reference, etc.
    weight: float = 1.0


@dataclass
class LearningPath:
    """学习路径"""
    id: str
    name: str
    nodes: List[str] = field(default_factory=list)
    estimated_time_minutes: int = 0
    difficulty_level: int = 1
    progress: float = 0.0


@dataclass
class UserPreference:
    """用户偏好设置"""
    user_id: str
    preferred_categories: List[str] = field(default_factory=list)
    difficulty_preference: int = 3  # 1-5
    learning_style: str = "balanced"  # visual, auditory, reading, balanced
    daily_goal_minutes: int = 30
    topic_weights: Dict[str, float] = field(default_factory=dict)


class KnowledgeGraphEditor:
    """知识图谱编辑器"""
    
    DIFFICULTY_LEVELS = {
        1: {"name": "入门", "description": "基础概念", "time_multiplier": 0.5},
        2: {"name": "基础", "description": "核心原理", "time_multiplier": 0.8},
        3: {"name": "进阶", "description": "深入理解", "time_multiplier": 1.0},
        4: {"name": "高级", "description": "复杂应用", "time_multiplier": 1.5},
        5: {"name": "专家", "description": "精通掌握", "time_multiplier": 2.0}
    }
    
    RELATION_TYPES = ["prerequisite", "related", "reference", "part_of", "derived_from"]
    
    def __init__(self):
        self._logger = logger.bind(component="KnowledgeGraphEditor")
        self._nodes: Dict[str, KnowledgeNode] = {}
        self._edges: List[KnowledgeEdge] = []
        self._user_preferences: Dict[str, UserPreference] = {}
        self._learning_paths: Dict[str, LearningPath] = {}
        
        self._logger.info("知识图谱编辑器初始化完成")
    
    def add_node(self, title: str, content: str, difficulty: int = 3, 
                 category: str = "general", tags: List[str] = None) -> str:
        """
        添加知识节点
        
        Args:
            title: 节点标题
            content: 节点内容
            difficulty: 难度等级 (1-5)
            category: 分类
            tags: 标签列表
        
        Returns:
            节点ID
        """
        node_id = f"node_{int(time.time() * 1000)}"
        node = KnowledgeNode(
            id=node_id,
            title=title,
            content=content,
            difficulty=min(max(difficulty, 1), 5),
            category=category,
            tags=tags or []
        )
        self._nodes[node_id] = node
        self._logger.debug(f"添加知识节点: {node_id} - {title}")
        return node_id
    
    def update_node(self, node_id: str, **kwargs):
        """更新知识节点"""
        if node_id not in self._nodes:
            raise ValueError(f"节点不存在: {node_id}")
        
        node = self._nodes[node_id]
        if "title" in kwargs:
            node.title = kwargs["title"]
        if "content" in kwargs:
            node.content = kwargs["content"]
        if "difficulty" in kwargs:
            node.difficulty = min(max(kwargs["difficulty"], 1), 5)
        if "category" in kwargs:
            node.category = kwargs["category"]
        if "tags" in kwargs:
            node.tags = kwargs["tags"]
        if "weight" in kwargs:
            node.weight = kwargs["weight"]
        if "mastered" in kwargs:
            node.mastered = kwargs["mastered"]
        
        self._logger.debug(f"更新知识节点: {node_id}")
    
    def set_difficulty_level(self, node_id: str, level: int):
        """设置节点难度等级"""
        self.update_node(node_id, difficulty=level)
    
    def set_preference_weight(self, node_id: str, weight: float):
        """设置节点偏好权重"""
        self.update_node(node_id, weight=weight)
    
    def add_edge(self, source_id: str, target_id: str, relation: str = "related"):
        """
        添加知识关系边
        
        Args:
            source_id: 源节点ID
            target_id: 目标节点ID
            relation: 关系类型
        """
        if source_id not in self._nodes or target_id not in self._nodes:
            raise ValueError("节点不存在")
        
        if relation not in self.RELATION_TYPES:
            raise ValueError(f"无效的关系类型: {relation}")
        
        edge = KnowledgeEdge(
            source=source_id,
            target=target_id,
            relation=relation
        )
        self._edges.append(edge)
        self._logger.debug(f"添加关系边: {source_id} -{relation}-> {target_id}")
    
    def create_user_preference(self, user_id: str, **kwargs) -> UserPreference:
        """
        创建用户偏好设置
        
        Args:
            user_id: 用户ID
            kwargs: 偏好参数
        
        Returns:
            用户偏好对象
        """
        preference = UserPreference(user_id=user_id, **kwargs)
        self._user_preferences[user_id] = preference
        self._logger.debug(f"创建用户偏好: {user_id}")
        return preference
    
    def update_user_preference(self, user_id: str, **kwargs):
        """更新用户偏好设置"""
        if user_id not in self._user_preferences:
            self.create_user_preference(user_id)
        
        pref = self._user_preferences[user_id]
        if "preferred_categories" in kwargs:
            pref.preferred_categories = kwargs["preferred_categories"]
        if "difficulty_preference" in kwargs:
            pref.difficulty_preference = min(max(kwargs["difficulty_preference"], 1), 5)
        if "learning_style" in kwargs:
            pref.learning_style = kwargs["learning_style"]
        if "daily_goal_minutes" in kwargs:
            pref.daily_goal_minutes = kwargs["daily_goal_minutes"]
        if "topic_weights" in kwargs:
            pref.topic_weights = kwargs["topic_weights"]
    
    def generate_learning_path(self, user_id: str, topic: str = None, 
                               target_difficulty: int = None) -> LearningPath:
        """
        动态生成学习路径
        
        Args:
            user_id: 用户ID
            topic: 主题（可选）
            target_difficulty: 目标难度（可选）
        
        Returns:
            学习路径对象
        """
        # 获取用户偏好
        pref = self._user_preferences.get(user_id)
        if pref:
            difficulty = target_difficulty or pref.difficulty_preference
            preferred_categories = pref.preferred_categories
            topic_weights = pref.topic_weights
        else:
            difficulty = target_difficulty or 3
            preferred_categories = []
            topic_weights = {}
        
        # 筛选节点
        candidates = []
        for node_id, node in self._nodes.items():
            # 难度匹配
            if node.difficulty > difficulty:
                continue
            
            # 分类匹配
            if preferred_categories and node.category not in preferred_categories:
                continue
            
            # 主题匹配
            if topic and topic.lower() not in node.title.lower():
                continue
            
            # 计算优先级（考虑偏好权重）
            priority = node.weight
            if node.category in topic_weights:
                priority *= topic_weights[node.category]
            
            candidates.append((priority, node))
        
        # 按优先级排序
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        # 构建路径
        path_nodes = [node.id for _, node in candidates[:10]]
        estimated_time = sum(self.DIFFICULTY_LEVELS[node.difficulty]["time_multiplier"] * 15 
                           for _, node in candidates[:10])
        
        path = LearningPath(
            id=f"path_{int(time.time() * 1000)}",
            name=f"学习路径 - {topic or '综合'}",
            nodes=path_nodes,
            estimated_time_minutes=int(estimated_time),
            difficulty_level=difficulty
        )
        
        self._learning_paths[path.id] = path
        self._logger.info(f"生成学习路径: {path.id} - {len(path_nodes)} 个节点")
        
        return path
    
    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        """获取知识节点"""
        return self._nodes.get(node_id)
    
    def get_nodes_by_category(self, category: str) -> List[KnowledgeNode]:
        """按分类获取节点"""
        return [node for node in self._nodes.values() if node.category == category]
    
    def get_nodes_by_difficulty(self, difficulty: int) -> List[KnowledgeNode]:
        """按难度获取节点"""
        return [node for node in self._nodes.values() if node.difficulty == difficulty]
    
    def get_user_preference(self, user_id: str) -> Optional[UserPreference]:
        """获取用户偏好"""
        return self._user_preferences.get(user_id)
    
    def get_learning_path(self, path_id: str) -> Optional[LearningPath]:
        """获取学习路径"""
        return self._learning_paths.get(path_id)
    
    def get_all_categories(self) -> List[str]:
        """获取所有分类"""
        return list(set(node.category for node in self._nodes.values()))
    
    def export_graph(self) -> Dict:
        """导出知识图谱"""
        return {
            "nodes": [vars(node) for node in self._nodes.values()],
            "edges": [vars(edge) for edge in self._edges],
            "version": "1.0"
        }
    
    def import_graph(self, data: Dict):
        """导入知识图谱"""
        # 清空现有数据
        self._nodes.clear()
        self._edges.clear()
        
        # 导入节点
        for node_data in data.get("nodes", []):
            node = KnowledgeNode(**node_data)
            self._nodes[node.id] = node
        
        # 导入边
        for edge_data in data.get("edges", []):
            edge = KnowledgeEdge(**edge_data)
            self._edges.append(edge)
        
        self._logger.info(f"导入知识图谱: {len(self._nodes)} 个节点, {len(self._edges)} 条边")


# 单例模式
_knowledge_graph_editor_instance = None

def get_knowledge_graph_editor() -> KnowledgeGraphEditor:
    """获取知识图谱编辑器实例"""
    global _knowledge_graph_editor_instance
    if _knowledge_graph_editor_instance is None:
        _knowledge_graph_editor_instance = KnowledgeGraphEditor()
    return _knowledge_graph_editor_instance


if __name__ == "__main__":
    print("=" * 60)
    print("知识图谱编辑器测试")
    print("=" * 60)
    
    editor = get_knowledge_graph_editor()
    
    # 1. 添加知识节点
    print("\n[1] 添加知识节点")
    node1 = editor.add_node("Python基础", "Python是一种高级编程语言", difficulty=1, category="编程")
    node2 = editor.add_node("机器学习", "机器学习是人工智能的分支", difficulty=3, category="AI")
    node3 = editor.add_node("深度学习", "深度学习是机器学习的子集", difficulty=4, category="AI")
    node4 = editor.add_node("神经网络", "神经网络是深度学习的核心", difficulty=4, category="AI")
    node5 = editor.add_node("PyTorch", "PyTorch是深度学习框架", difficulty=3, category="编程")
    
    print(f"已添加节点: {node1}, {node2}, {node3}, {node4}, {node5}")
    
    # 2. 添加关系边
    print("\n[2] 添加关系边")
    editor.add_edge(node2, node3, "derived_from")  # 机器学习 -> 深度学习
    editor.add_edge(node3, node4, "part_of")       # 深度学习 -> 神经网络
    editor.add_edge(node5, node4, "related")       # PyTorch -> 神经网络
    editor.add_edge(node1, node5, "prerequisite")  # Python基础 -> PyTorch
    print("关系边添加完成")
    
    # 3. 创建用户偏好
    print("\n[3] 创建用户偏好")
    pref = editor.create_user_preference(
        "user_001",
        preferred_categories=["AI", "编程"],
        difficulty_preference=3,
        learning_style="balanced",
        daily_goal_minutes=45,
        topic_weights={"AI": 1.5, "编程": 1.2}
    )
    print(f"用户偏好: {pref.user_id}")
    
    # 4. 设置节点偏好权重
    print("\n[4] 设置节点偏好权重")
    editor.set_preference_weight(node3, 2.0)  # 深度学习权重加倍
    editor.set_preference_weight(node4, 1.8)  # 神经网络权重提高
    print("权重设置完成")
    
    # 5. 生成学习路径
    print("\n[5] 生成学习路径")
    path = editor.generate_learning_path("user_001", topic="AI")
    print(f"路径ID: {path.id}")
    print(f"路径名称: {path.name}")
    print(f"节点数量: {len(path.nodes)}")
    print(f"预计时间: {path.estimated_time_minutes} 分钟")
    print(f"难度等级: {path.difficulty_level} ({editor.DIFFICULTY_LEVELS[path.difficulty_level]['name']})")
    
    # 6. 获取路径详情
    print("\n[6] 路径节点详情")
    for node_id in path.nodes[:5]:
        node = editor.get_node(node_id)
        if node:
            print(f"  - {node.title} (难度: {node.difficulty}, 权重: {node.weight})")
    
    # 7. 获取分类统计
    print("\n[7] 分类统计")
    categories = editor.get_all_categories()
    for category in categories:
        nodes = editor.get_nodes_by_category(category)
        print(f"  {category}: {len(nodes)} 个节点")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)