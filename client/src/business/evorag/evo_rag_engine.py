"""
EvoRAGEngine - 自进化 KG-RAG 框架

实现 EvoRAG 的核心创新：
1. 反馈驱动的反向传播机制
2. 将响应级反馈转化为三元组级更新
3. 路径评估维度（Supportiveness、Fidelity、Conflict）
4. 关系中心的KG演化（Relation Fusion、Relation Suppression）
5. 混合优先级检索

核心理念：建立"反馈→LLM→图数据"的闭环机制，实现KG-RAG的持续自进化

Author: LivingTreeAI Agent
Date: 2026-04-29
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import math
import time


class FeedbackType(Enum):
    """反馈类型"""
    LLM = "llm"          # LLM评估反馈
    HUMAN = "human"      # 人类反馈
    GROUND_TRUTH = "ground_truth"  # 真实标签反馈


@dataclass
class Triple:
    """
    知识图谱三元组
    
    包含头实体、关系、尾实体。
    """
    head: str
    relation: str
    tail: str
    
    def __hash__(self):
        return hash((self.head, self.relation, self.tail))
    
    def __eq__(self, other):
        if isinstance(other, Triple):
            return (self.head == other.head and 
                    self.relation == other.relation and 
                    self.tail == other.tail)
        return False
    
    def __str__(self):
        return f"({self.head}, {self.relation}, {self.tail})"


@dataclass
class Path:
    """
    路径
    
    由多个三元组组成的路径。
    """
    triples: List[Triple]
    utility: float = 0.0  # 路径效用值
    
    @property
    def length(self):
        return len(self.triples)
    
    def __str__(self):
        return " → ".join(str(t) for t in self.triples)


@dataclass
class FeedbackSignal:
    """
    反馈信号
    
    包含路径评估结果。
    """
    path_id: str
    query: str
    response: str
    supportiveness: float  # 支持度 (0-1)
    fidelity: float       # 贡献度 (0-1)
    conflict: float       # 冲突度 (0-1)
    feedback_type: FeedbackType
    timestamp: float = field(default_factory=lambda: time.time())


class EvoRAGEngine:
    """
    EvoRAG 引擎
    
    核心功能：
    1. 反馈驱动的反向传播
    2. 路径评估（Supportiveness、Fidelity、Conflict）
    3. 三元组级更新
    4. 关系中心的KG演化（Fusion/Suppression）
    5. 混合优先级检索
    
    算法流程：
    1. 前向计算：计算三元组选择概率和路径优先级
    2. 路径评估：评估路径效用
    3. 反向传播：将反馈传播到三元组级别
    4. KG演化：执行关系融合或抑制
    """
    
    def __init__(self, alpha: float = 0.5):
        self._logger = logger.bind(component="EvoRAGEngine")
        
        # 知识图谱存储
        self._triples: List[Triple] = []
        self._triple_scores: Dict[Triple, float] = {}  # 贡献分数 S_c(t)
        
        # 路径缓存
        self._paths: Dict[str, Path] = {}
        
        # 反馈历史
        self._feedback_history: List[FeedbackSignal] = []
        
        # 参数
        self._alpha = alpha  # 语义相似度与贡献分数的权衡参数
        
        # 演化阈值
        self._fusion_threshold = 0.7  # 关系融合阈值
        self._suppression_threshold = 0.2  # 关系抑制阈值
        
        # 统计信息
        self._query_count = 0
        
        self._logger.info("✅ EvoRAGEngine 初始化完成")
    
    def add_triple(self, head: str, relation: str, tail: str):
        """
        添加三元组到知识图谱
        
        Args:
            head: 头实体
            relation: 关系
            tail: 尾实体
        """
        triple = Triple(head, relation, tail)
        
        if triple not in self._triples:
            self._triples.append(triple)
            self._triple_scores[triple] = 0.5  # 初始贡献分数
        
        self._logger.debug(f"📥 添加三元组: {triple}")
    
    def get_triples(self) -> List[Triple]:
        """获取所有三元组"""
        return self._triples
    
    def get_triple_score(self, triple: Triple) -> float:
        """获取三元组的贡献分数"""
        return self._triple_scores.get(triple, 0.5)
    
    def _compute_semantic_similarity(self, triple: Triple, query: str) -> float:
        """
        计算三元组与查询的语义相似度
        
        Args:
            triple: 三元组
            query: 查询
        
        Returns:
            语义相似度分数 (0-1)
        """
        # 简化实现：基于关键词匹配
        query_lower = query.lower()
        triple_text = f"{triple.head} {triple.relation} {triple.tail}".lower()
        
        matches = sum(1 for word in query_lower.split() if word in triple_text)
        max_matches = len(query_lower.split())
        
        return matches / max_matches if max_matches > 0 else 0.0
    
    def compute_triple_probability(self, triple: Triple, query: str) -> float:
        """
        计算三元组选择概率
        
        P(t) = (1-α) · S_r(t) + α · S_c(t)
        
        Args:
            triple: 三元组
            query: 查询
        
        Returns:
            选择概率
        """
        s_r = self._compute_semantic_similarity(triple, query)
        s_c = self._triple_scores.get(triple, 0.5)
        
        return (1 - self._alpha) * s_r + self._alpha * s_c
    
    def compute_path_priority(self, path: Path, query: str) -> float:
        """
        计算路径优先级
        
        P(L_i) = exp(1/|L_i| * Σ log P(t)) / Σ exp(...)
        
        Args:
            path: 路径
            query: 查询
        
        Returns:
            路径优先级
        """
        if not path.triples:
            return 0.0
        
        # 计算路径内所有三元组的平均对数概率
        log_probs = []
        for triple in path.triples:
            p = self.compute_triple_probability(triple, query)
            if p > 0:
                log_probs.append(math.log(p))
        
        if not log_probs:
            return 0.0
        
        avg_log_prob = sum(log_probs) / len(log_probs)
        path_score = math.exp(avg_log_prob)
        
        return path_score
    
    def evaluate_path(self, path: Path, query: str, response: str) -> FeedbackSignal:
        """
        评估路径效用（三维度）
        
        Args:
            path: 路径
            query: 查询
            response: 响应
        
        Returns:
            反馈信号
        """
        # 简化实现：基于启发式规则计算三个维度
        
        # Supportiveness: 路径是否支持响应
        supportiveness = self._compute_supportiveness(path, response)
        
        # Fidelity: 路径对响应的贡献程度
        fidelity = self._compute_fidelity(path, response)
        
        # Conflict: 路径是否与响应矛盾
        conflict = self._compute_conflict(path, response)
        
        feedback = FeedbackSignal(
            path_id=str(id(path)),
            query=query,
            response=response,
            supportiveness=supportiveness,
            fidelity=fidelity,
            conflict=conflict,
            feedback_type=FeedbackType.LLM
        )
        
        self._feedback_history.append(feedback)
        
        return feedback
    
    def _compute_supportiveness(self, path: Path, response: str) -> float:
        """计算支持度：路径是否支持响应"""
        response_lower = response.lower()
        support_count = 0
        
        for triple in path.triples:
            triple_text = f"{triple.head} {triple.tail}".lower()
            if triple_text in response_lower:
                support_count += 1
        
        return support_count / max(len(path.triples), 1)
    
    def _compute_fidelity(self, path: Path, response: str) -> float:
        """计算贡献度：路径对响应的贡献程度"""
        # 简化实现：路径实体在响应中的覆盖率
        path_entities = set()
        for triple in path.triples:
            path_entities.add(triple.head.lower())
            path_entities.add(triple.tail.lower())
        
        response_lower = response.lower()
        covered = sum(1 for entity in path_entities if entity in response_lower)
        
        return covered / max(len(path_entities), 1)
    
    def _compute_conflict(self, path: Path, response: str) -> float:
        """计算冲突度：路径是否与响应矛盾"""
        # 简化实现：检查是否有明显矛盾
        response_lower = response.lower()
        
        for triple in path.triples:
            # 简单的矛盾检测
            if triple.relation.lower() == "not" and triple.tail.lower() in response_lower:
                return 1.0
            if triple.relation.lower() == "is" and triple.tail.lower() not in response_lower:
                return 0.5
        
        return 0.0
    
    def backpropagate_feedback(self, feedback: FeedbackSignal, path: Path):
        """
        反向传播反馈到三元组级别
        
        Args:
            feedback: 反馈信号
            path: 路径
        """
        # 只有当 Fidelity 高且 Conflict 低时，才更新
        if feedback.fidelity > 0.5 and feedback.conflict < 0.3:
            # 计算路径效用
            path_utility = feedback.supportiveness
            
            # 更新路径效用
            path.utility = path_utility
            
            # 反向传播到三元组
            self._update_triple_scores(path, path_utility)
            
            # 检查是否需要演化
            self._check_evolution(path)
    
    def _update_triple_scores(self, path: Path, utility: float):
        """
        更新三元组的贡献分数
        
        Args:
            path: 路径
            utility: 路径效用
        """
        for triple in path.triples:
            current_score = self._triple_scores.get(triple, 0.5)
            
            # 累积更新：新分数 = 旧分数 * 0.9 + 效用 * 0.1
            new_score = current_score * 0.9 + utility * 0.1
            
            # 限制在 [0, 1] 范围内
            new_score = max(0.0, min(1.0, new_score))
            
            self._triple_scores[triple] = new_score
            
            self._logger.debug(f"🔄 更新三元组分数: {triple} -> {new_score:.3f}")
    
    def _check_evolution(self, path: Path):
        """
        检查是否需要执行 KG 演化操作
        
        Args:
            path: 路径
        """
        if len(path.triples) >= 2:
            # 检查是否需要关系融合
            avg_score = sum(self._triple_scores.get(t, 0.5) for t in path.triples) / len(path.triples)
            
            if avg_score > self._fusion_threshold:
                self._perform_relation_fusion(path)
            elif avg_score < self._suppression_threshold:
                self._perform_relation_suppression(path)
    
    def _perform_relation_fusion(self, path: Path):
        """
        执行关系融合：添加快捷边连接多跳路径端点
        
        Args:
            path: 路径
        """
        if len(path.triples) >= 2:
            # 创建快捷边
            head = path.triples[0].head
            tail = path.triples[-1].tail
            
            # 生成快捷关系名称
            relations = [t.relation for t in path.triples]
            shortcut_relation = "→".join(relations)
            
            # 添加快捷三元组
            self.add_triple(head, shortcut_relation, tail)
            
            self._logger.info(f"🔗 关系融合: {head} -[{shortcut_relation}]-> {tail}")
    
    def _perform_relation_suppression(self, path: Path):
        """
        执行关系抑制：降低三元组的检索概率
        
        Args:
            path: 路径
        """
        for triple in path.triples:
            current_score = self._triple_scores.get(triple, 0.5)
            
            # 降低分数，但不低于最低阈值
            new_score = max(0.05, current_score * 0.5)
            self._triple_scores[triple] = new_score
            
            self._logger.info(f"🛑 关系抑制: {triple} -> {new_score:.3f}")
    
    def retrieve(self, query: str, top_k: int = 5) -> List[Tuple[Path, float]]:
        """
        混合优先级检索
        
        Args:
            query: 查询
            top_k: 返回结果数量
            
        Returns:
            (路径, 优先级) 列表
        """
        self._query_count += 1
        
        # 生成可能的路径（简化：单跳和双跳路径）
        paths = self._generate_paths(query)
        
        # 计算路径优先级
        path_priorities = []
        for path in paths:
            priority = self.compute_path_priority(path, query)
            path_priorities.append((path, priority))
        
        # 按优先级排序
        path_priorities.sort(key=lambda x: -x[1])
        
        return path_priorities[:top_k]
    
    def _generate_paths(self, query: str) -> List[Path]:
        """
        生成与查询相关的路径
        
        Args:
            query: 查询
            
        Returns:
            路径列表
        """
        paths = []
        
        # 单跳路径
        for triple in self._triples:
            if self._compute_semantic_similarity(triple, query) > 0:
                paths.append(Path([triple]))
        
        # 双跳路径（简化实现）
        for i, t1 in enumerate(self._triples):
            for j, t2 in enumerate(self._triples):
                if i != j and t1.tail == t2.head:
                    combined = Path([t1, t2])
                    paths.append(combined)
        
        return paths
    
    def get_feedback_history(self) -> List[FeedbackSignal]:
        """获取反馈历史"""
        return self._feedback_history
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        avg_score = sum(self._triple_scores.values()) / max(len(self._triple_scores), 1)
        
        return {
            "triple_count": len(self._triples),
            "query_count": self._query_count,
            "feedback_count": len(self._feedback_history),
            "avg_triple_score": avg_score,
            "fusion_threshold": self._fusion_threshold,
            "suppression_threshold": self._suppression_threshold
        }


# 创建全局实例
evo_rag_engine = EvoRAGEngine()


def get_evo_rag_engine() -> EvoRAGEngine:
    """获取EvoRAG引擎实例"""
    return evo_rag_engine


# 测试函数
async def test_evo_rag_engine():
    """测试EvoRAG引擎"""
    import sys
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 EvoRAGEngine")
    print("=" * 60)
    
    engine = EvoRAGEngine()
    
    # 1. 添加三元组
    print("\n[1] 添加三元组...")
    engine.add_triple("Alice", "WorksAt", "Google")
    engine.add_triple("Alice", "LivesIn", "NewYork")
    engine.add_triple("Google", "LocatedIn", "California")
    engine.add_triple("NewYork", "State", "USA")
    print(f"    ✓ 三元组数量: {len(engine.get_triples())}")
    
    # 2. 测试三元组概率计算
    print("\n[2] 测试三元组概率计算...")
    triple = Triple("Alice", "WorksAt", "Google")
    prob = engine.compute_triple_probability(triple, "Alice在哪里工作？")
    print(f"    ✓ 三元组概率: {prob:.3f}")
    
    # 3. 测试检索
    print("\n[3] 测试检索...")
    results = engine.retrieve("Alice在哪里工作？", top_k=3)
    print(f"    ✓ 检索结果数量: {len(results)}")
    for path, priority in results:
        print(f"      - {path} (优先级: {priority:.3f})")
    
    # 4. 测试路径评估
    print("\n[4] 测试路径评估...")
    path = Path([Triple("Alice", "WorksAt", "Google")])
    feedback = engine.evaluate_path(path, "Alice在哪里工作？", "Alice在Google工作。")
    print(f"    ✓ Supportiveness: {feedback.supportiveness:.3f}")
    print(f"    ✓ Fidelity: {feedback.fidelity:.3f}")
    print(f"    ✓ Conflict: {feedback.conflict:.3f}")
    
    # 5. 测试反向传播
    print("\n[5] 测试反向传播...")
    engine.backpropagate_feedback(feedback, path)
    score = engine.get_triple_score(triple)
    print(f"    ✓ 三元组更新后分数: {score:.3f}")
    
    # 6. 测试关系融合
    print("\n[6] 测试关系融合...")
    # 创建一个高分路径触发融合
    for _ in range(10):
        engine._triple_scores[Triple("Alice", "WorksAt", "Google")] = 0.9
        engine._triple_scores[Triple("Google", "LocatedIn", "California")] = 0.9
    
    path2 = Path([
        Triple("Alice", "WorksAt", "Google"),
        Triple("Google", "LocatedIn", "California")
    ])
    engine._check_evolution(path2)
    print(f"    ✓ 融合后三元组数量: {len(engine.get_triples())}")
    
    # 7. 获取统计信息
    print("\n[7] 获取统计信息...")
    stats = engine.get_stats()
    print(f"    ✓ 查询次数: {stats['query_count']}")
    print(f"    ✓ 反馈次数: {stats['feedback_count']}")
    print(f"    ✓ 平均三元组分数: {stats['avg_triple_score']:.3f}")
    
    print("\n" + "=" * 60)
    print("🎉 所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_evo_rag_engine())