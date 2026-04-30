"""
ExperienceManager - 经验档案管理

基于向量数据库的"案例库" + 决策树记录，实现经验积累与复用。

核心功能：
1. 案例存储 - 存储成功/失败案例
2. 案例检索 - 根据问题检索相似案例
3. 决策树记录 - 记录决策过程和结果
4. 经验提取 - 从案例中提取经验规则
5. 相似性匹配 - 向量相似度检索

设计原理：
- 使用向量数据库存储案例
- 决策树记录决策路径
- 支持案例分类和标签
- 经验规则提取和复用

使用示例：
    manager = ExperienceManager()
    
    # 存储案例
    case_id = manager.store_case({
        "problem": "用户问如何修复代码错误",
        "solution": "建议用户检查日志",
        "outcome": "success",
        "confidence": 0.85
    })
    
    # 检索相似案例
    similar = manager.retrieve_similar("如何调试程序", limit=3)
    
    # 添加决策记录
    manager.add_decision("task_id", "选择方案A", {"reason": "效率更高"})
"""

import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import numpy as np


class CaseOutcome(Enum):
    """案例结果"""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    UNKNOWN = "unknown"


class DecisionNodeType(Enum):
    """决策节点类型"""
    ROOT = "root"
    DECISION = "decision"
    ACTION = "action"
    OUTCOME = "outcome"
    LEAF = "leaf"


@dataclass
class CaseRecord:
    """案例记录"""
    case_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    problem: str = ""
    problem_type: str = ""
    domain: str = ""
    solution: str = ""
    outcome: CaseOutcome = CaseOutcome.UNKNOWN
    confidence: float = 0.0
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "problem": self.problem,
            "problem_type": self.problem_type,
            "domain": self.domain,
            "solution": self.solution,
            "outcome": self.outcome.value,
            "confidence": self.confidence,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class DecisionNode:
    """决策节点"""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: Optional[str] = None
    node_type: DecisionNodeType = DecisionNodeType.DECISION
    label: str = ""
    decision: Optional[str] = None
    reason: Optional[str] = None
    confidence: float = 0.0
    children: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "parent_id": self.parent_id,
            "node_type": self.node_type.value,
            "label": self.label,
            "decision": self.decision,
            "reason": self.reason,
            "confidence": self.confidence,
            "children": self.children,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


class DecisionTree:
    """决策树"""
    
    def __init__(self):
        self.nodes: Dict[str, DecisionNode] = {}
        self.root_id: Optional[str] = None
    
    def add_node(self, node: DecisionNode) -> str:
        """添加节点"""
        self.nodes[node.node_id] = node
        
        if node.node_type == DecisionNodeType.ROOT and not self.root_id:
            self.root_id = node.node_id
        
        # 更新父节点的子节点列表
        if node.parent_id and node.parent_id in self.nodes:
            parent = self.nodes[node.parent_id]
            if node.node_id not in parent.children:
                parent.children.append(node.node_id)
        
        return node.node_id
    
    def get_node(self, node_id: str) -> Optional[DecisionNode]:
        return self.nodes.get(node_id)
    
    def get_path(self, node_id: str) -> List[DecisionNode]:
        """获取从根节点到指定节点的路径"""
        path = []
        current_id = node_id
        
        while current_id:
            node = self.nodes.get(current_id)
            if not node:
                break
            path.append(node)
            current_id = node.parent_id
        
        return list(reversed(path))
    
    def get_subtree(self, node_id: str) -> List[DecisionNode]:
        """获取子树"""
        subtree = []
        
        def dfs(current_id):
            node = self.nodes.get(current_id)
            if node:
                subtree.append(node)
                for child_id in node.children:
                    dfs(child_id)
        
        dfs(node_id)
        return subtree
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "root_id": self.root_id,
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
            "node_count": len(self.nodes)
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        type_counts = {}
        for node in self.nodes.values():
            type_counts[node.node_type.value] = type_counts.get(node.node_type.value, 0) + 1
        
        return {
            "total_nodes": len(self.nodes),
            "by_type": type_counts
        }


class ExperienceManager:
    """经验档案管理器"""
    
    def __init__(self, embedding_dim: int = 384):
        self._logger = logger.bind(component="ExperienceManager")
        
        # 案例存储
        self._cases: Dict[str, CaseRecord] = {}
        
        # 索引
        self._case_by_type: Dict[str, List[str]] = {}
        self._case_by_domain: Dict[str, List[str]] = {}
        self._case_by_tag: Dict[str, List[str]] = {}
        
        # 决策树存储
        self._decision_trees: Dict[str, DecisionTree] = {}
        
        # 向量存储（简化版）
        self._embedding_dim = embedding_dim
        self._embeddings: Dict[str, List[float]] = {}
        
        # 相似性阈值
        self._similarity_threshold = 0.7
        
        self._logger.info("经验档案管理器初始化完成")
    
    def store_case(self, case_data: Dict) -> str:
        """
        存储案例
        
        Args:
            case_data: 案例数据，包含以下字段：
                - problem: 问题描述
                - problem_type: 问题类型
                - domain: 领域
                - solution: 解决方案
                - outcome: 结果（success/partial/failed/unknown）
                - confidence: 置信度
                - tags: 标签列表
                - metadata: 元数据
        
        Returns:
            案例ID
        """
        outcome = CaseOutcome(case_data.get("outcome", "unknown"))
        
        case = CaseRecord(
            problem=case_data.get("problem", ""),
            problem_type=case_data.get("problem_type", ""),
            domain=case_data.get("domain", ""),
            solution=case_data.get("solution", ""),
            outcome=outcome,
            confidence=case_data.get("confidence", 0.0),
            tags=case_data.get("tags", []),
            metadata=case_data.get("metadata", {})
        )
        
        self._cases[case.case_id] = case
        
        # 更新索引
        self._update_index(self._case_by_type, case.problem_type, case.case_id)
        self._update_index(self._case_by_domain, case.domain, case.case_id)
        for tag in case.tags:
            self._update_index(self._case_by_tag, tag, case.case_id)
        
        # 生成嵌入（简化版）
        if case.problem:
            case.embedding = self._generate_embedding(case.problem)
            self._embeddings[case.case_id] = case.embedding
        
        self._logger.info(f"案例已存储: {case.case_id}")
        return case.case_id
    
    def retrieve_similar(self, query: str, limit: int = 5, domain: str = None) -> List[CaseRecord]:
        """
        根据问题检索相似案例
        
        Args:
            query: 查询问题
            limit: 返回数量限制
            domain: 领域过滤
        
        Returns:
            相似案例列表（按相似度排序）
        """
        if not self._cases:
            return []
        
        # 生成查询嵌入
        query_embedding = self._generate_embedding(query)
        
        # 计算相似度
        similarities = []
        
        for case_id, case in self._cases.items():
            # 领域过滤
            if domain and case.domain != domain:
                continue
            
            if case.embedding:
                similarity = self._cosine_similarity(query_embedding, case.embedding)
                if similarity >= self._similarity_threshold:
                    similarities.append((similarity, case))
        
        # 按相似度排序
        similarities.sort(key=lambda x: x[0], reverse=True)
        
        return [case for _, case in similarities[:limit]]
    
    def retrieve_by_type(self, problem_type: str) -> List[CaseRecord]:
        """按问题类型检索案例"""
        case_ids = self._case_by_type.get(problem_type, [])
        return [self._cases[cid] for cid in case_ids if cid in self._cases]
    
    def retrieve_by_domain(self, domain: str) -> List[CaseRecord]:
        """按领域检索案例"""
        case_ids = self._case_by_domain.get(domain, [])
        return [self._cases[cid] for cid in case_ids if cid in self._cases]
    
    def retrieve_by_tag(self, tag: str) -> List[CaseRecord]:
        """按标签检索案例"""
        case_ids = self._case_by_tag.get(tag, [])
        return [self._cases[cid] for cid in case_ids if cid in self._cases]
    
    def get_case(self, case_id: str) -> Optional[CaseRecord]:
        """获取案例"""
        return self._cases.get(case_id)
    
    def update_case(self, case_id: str, updates: Dict) -> bool:
        """更新案例"""
        case = self._cases.get(case_id)
        if not case:
            return False
        
        # 更新字段
        if "problem" in updates:
            case.problem = updates["problem"]
        if "solution" in updates:
            case.solution = updates["solution"]
        if "outcome" in updates:
            case.outcome = CaseOutcome(updates["outcome"])
        if "confidence" in updates:
            case.confidence = updates["confidence"]
        if "tags" in updates:
            case.tags = updates["tags"]
        
        case.updated_at = datetime.now()
        
        self._logger.info(f"案例已更新: {case_id}")
        return True
    
    def delete_case(self, case_id: str) -> bool:
        """删除案例"""
        case = self._cases.get(case_id)
        if not case:
            return False
        
        # 从索引中移除
        self._remove_from_index(self._case_by_type, case.problem_type, case_id)
        self._remove_from_index(self._case_by_domain, case.domain, case_id)
        for tag in case.tags:
            self._remove_from_index(self._case_by_tag, tag, case_id)
        
        # 从嵌入存储中移除
        if case_id in self._embeddings:
            del self._embeddings[case_id]
        
        # 删除案例
        del self._cases[case_id]
        
        self._logger.info(f"案例已删除: {case_id}")
        return True
    
    def create_decision_tree(self, task_id: str) -> DecisionTree:
        """创建决策树"""
        tree = DecisionTree()
        
        # 创建根节点
        root = DecisionNode(
            node_type=DecisionNodeType.ROOT,
            label=f"任务: {task_id}"
        )
        tree.add_node(root)
        
        self._decision_trees[task_id] = tree
        return tree
    
    def get_decision_tree(self, task_id: str) -> Optional[DecisionTree]:
        """获取决策树"""
        return self._decision_trees.get(task_id)
    
    def add_decision(self, task_id: str, decision: str, reason: str = "", confidence: float = 0.0) -> str:
        """
        添加决策记录
        
        Args:
            task_id: 任务ID
            decision: 决策内容
            reason: 决策理由
            confidence: 置信度
        
        Returns:
            节点ID
        """
        tree = self._decision_trees.get(task_id)
        if not tree:
            tree = self.create_decision_tree(task_id)
        
        # 获取最后一个非叶子节点作为父节点
        parent_id = tree.root_id
        
        # 创建决策节点
        node = DecisionNode(
            parent_id=parent_id,
            node_type=DecisionNodeType.DECISION,
            label=decision,
            decision=decision,
            reason=reason,
            confidence=confidence
        )
        
        node_id = tree.add_node(node)
        self._logger.info(f"决策已记录: {task_id} -> {decision}")
        return node_id
    
    def add_action(self, task_id: str, action: str, parent_id: Optional[str] = None) -> str:
        """添加动作节点"""
        tree = self._decision_trees.get(task_id)
        if not tree:
            tree = self.create_decision_tree(task_id)
        
        if not parent_id:
            parent_id = tree.root_id
        
        node = DecisionNode(
            parent_id=parent_id,
            node_type=DecisionNodeType.ACTION,
            label=action
        )
        
        return tree.add_node(node)
    
    def add_outcome(self, task_id: str, outcome: str, parent_id: Optional[str] = None) -> str:
        """添加结果节点"""
        tree = self._decision_trees.get(task_id)
        if not tree:
            tree = self.create_decision_tree(task_id)
        
        if not parent_id:
            parent_id = tree.root_id
        
        node = DecisionNode(
            parent_id=parent_id,
            node_type=DecisionNodeType.OUTCOME,
            label=outcome,
            metadata={"outcome": outcome}
        )
        
        return tree.add_node(node)
    
    def extract_rules(self, domain: str = None, limit: int = 10) -> List[Dict]:
        """
        从案例中提取经验规则
        
        Args:
            domain: 领域过滤
            limit: 返回数量限制
        
        Returns:
            规则列表
        """
        rules = []
        
        # 获取案例
        if domain:
            cases = self.retrieve_by_domain(domain)
        else:
            cases = list(self._cases.values())
        
        # 按结果分组
        success_cases = [c for c in cases if c.outcome == CaseOutcome.SUCCESS]
        failed_cases = [c for c in cases if c.outcome == CaseOutcome.FAILED]
        
        # 提取成功模式
        for case in success_cases[:limit]:
            rules.append({
                "type": "success_pattern",
                "condition": case.problem,
                "action": case.solution,
                "confidence": case.confidence,
                "domain": case.domain
            })
        
        # 提取失败模式
        for case in failed_cases[:limit]:
            rules.append({
                "type": "failure_pattern",
                "condition": case.problem,
                "avoid_action": case.solution,
                "confidence": case.confidence,
                "domain": case.domain
            })
        
        return rules
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        outcome_counts = {}
        for case in self._cases.values():
            outcome_counts[case.outcome.value] = outcome_counts.get(case.outcome.value, 0) + 1
        
        return {
            "total_cases": len(self._cases),
            "total_decision_trees": len(self._decision_trees),
            "by_outcome": outcome_counts,
            "by_domain": {d: len(ids) for d, ids in self._case_by_domain.items()},
            "by_type": {t: len(ids) for t, ids in self._case_by_type.items()}
        }
    
    def _generate_embedding(self, text: str) -> List[float]:
        """生成文本嵌入（简化版）"""
        # 实际应用中应使用真正的嵌入模型
        hash_value = hash(text) % (2**32)  # 限制在 numpy 种子范围内
        np.random.seed(hash_value)
        return np.random.rand(self._embedding_dim).tolist()
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def _update_index(self, index: Dict[str, List[str]], key: str, value: str):
        """更新索引"""
        if key:
            if key not in index:
                index[key] = []
            if value not in index[key]:
                index[key].append(value)
    
    def _remove_from_index(self, index: Dict[str, List[str]], key: str, value: str):
        """从索引中移除"""
        if key in index and value in index[key]:
            index[key].remove(value)


def create_experience_manager(embedding_dim: int = 384) -> ExperienceManager:
    """创建经验档案管理器实例"""
    return ExperienceManager(embedding_dim)
