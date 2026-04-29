"""
EvoRAG反馈管理系统
实现反馈驱动反向传播机制
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
import numpy as np

from loguru import logger


@dataclass
class FeedbackRecord:
    """反馈记录"""
    query: str                              # 用户查询
    response: str                           # 生成的响应
    paths: List[List[str]]                  # 推理路径（三元组ID列表）
    feedback_score: float                   # 反馈分数 (1-5)
    feedback_type: str = "human"           # 反馈类型: human/llm/automatic
    utility_scores: Dict[str, float] = field(default_factory=dict)  # 路径效用分数 {path_id: utility}
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TripletScore:
    """三元组评分"""
    triplet_id: str
    semantic_similarity: float = 0.5       # Sr(t) - 语义相似度
    contribution_score: float = 0.5         # Sc(t) - 贡献分数（可学习）
    priority: float = 0.5                  # P(t) - 混合优先级
    update_count: int = 0                   # 更新次数
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())


class FeedbackManager:
    """
    反馈驱动反向传播管理器
    实现EvoRAG的反馈驱动机制
    """

    def __init__(
        self,
        feedback_db_path: Optional[str] = None,
        learning_rate: float = 0.5,
        alpha: float = 0.5,                 # 权衡参数 (1-α)·Sr + α·Sc
        high_threshold: float = 0.7,
        low_threshold: float = 0.3
    ):
        """
        初始化反馈管理器

        Args:
            feedback_db_path: 反馈数据库路径
            learning_rate: 学习率 η
            alpha: 权衡参数 α
            high_threshold: 高质量阈值 τhigh
            low_threshold: 低质量阈值 τlow
        """
        self.feedback_db_path = feedback_db_path or \
            "client/data/llm_wiki/feedback_db.json"
        self.learning_rate = learning_rate
        self.alpha = alpha
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold

        # 反馈记录
        self.feedback_records: List[FeedbackRecord] = []

        # 三元组评分表 {triplet_id: TripletScore}
        self.triplet_scores: Dict[str, TripletScore] = {}

        # 路径缓存 {path_signature: utility}
        self.path_utility_cache: Dict[str, float] = {}

        # 加载已有数据
        self._load_feedback_db()

        logger.info(f"[FeedbackManager] 初始化完成, "
                    f"已有反馈记录: {len(self.feedback_records)}, "
                    f"已追踪三元组: {len(self.triplet_scores)}")

    def add_feedback(
        self,
        query: str,
        response: str,
        paths: List[List[str]],
        feedback_score: float,
        feedback_type: str = "human"
    ) -> str:
        """
        添加反馈记录

        Args:
            query: 用户查询
            response: 生成的响应
            paths: 推理路径列表（每个路径是三元组ID列表）
            feedback_score: 反馈分数 (1-5)
            feedback_type: 反馈类型

        Returns:
            反馈记录ID
        """
        record = FeedbackRecord(
            query=query,
            response=response,
            paths=paths,
            feedback_score=feedback_score,
            feedback_type=feedback_type
        )

        self.feedback_records.append(record)

        # 计算路径效用
        self._compute_path_utilities(record)

        # 触发反向传播
        self._backward_propagation(record)

        # 保存数据库
        self._save_feedback_db()

        logger.info(f"[FeedbackManager] 添加反馈记录, "
                    f"查询: {query[:50]}..., "
                    f"分数: {feedback_score}, "
                    f"路径数: {len(paths)}")

        return record.timestamp

    def _compute_path_utilities(self, record: FeedbackRecord) -> None:
        """
        计算路径效用（公式1的简化版）
        U(L) = f(q, Rq, L, FS)

        EvoRAG原文使用LLM评估三个维度：
        - Supportiveness（支持度）
        - Fidelity（保真度）
        - Conflict（冲突度）

        这里使用简化版：基于反馈分数和路径特征
        """
        for path_idx, path in enumerate(record.paths):
            path_id = f"{record.timestamp}_{path_idx}"

            # 简化版效用计算
            # 真实场景应使用LLM评估三个维度
            utility = self._estimate_path_utility(
                query=record.query,
                response=record.response,
                path=path,
                feedback_score=record.feedback_score
            )

            record.utility_scores[path_id] = utility

            # 缓存路径效用
            path_signature = "->".join(path)
            self.path_utility_cache[path_signature] = utility

        logger.debug(f"[FeedbackManager] 计算路径效用完成, "
                     f"记录ID: {record.timestamp}, "
                     f"路径数: {len(record.paths)}")

    def _estimate_path_utility(
        self,
        query: str,
        response: str,
        path: List[str],
        feedback_score: float
    ) -> float:
        """
        估算路径效用（简化版）

        真实场景应使用LLM评估：
        - Supportiveness: 路径是否支持响应
        - Fidelity: 路径对响应的贡献程度
        - Conflict: 路径是否与响应矛盾

        Returns:
            效用分数 [-1, 1]
        """
        # 简化逻辑：
        # 1. 高反馈分数 + 长路径 → 高效用
        # 2. 低反馈分数 + 长路径 → 低效用
        # 3. 路径长度作为保真度代理

        normalized_score = (feedback_score - 3) / 2  # 映射到[-1, 1]

        # 路径长度因子（长路径通常信息更丰富）
        path_length_factor = min(len(path) / 5.0, 1.0)

        # 综合效用
        utility = normalized_score * path_length_factor

        return max(-1.0, min(1.0, utility))

    def _backward_propagation(self, record: FeedbackRecord) -> None:
        """
        反向传播（公式5-9）
        将路径效用传播到单个三元组
        """
        if not record.utility_scores:
            logger.warning("[FeedbackManager] 无路径效用分数, 跳过反向传播")
            return

        # 收集所有涉及的三元组
        all_triplets = set()
        for path in record.paths:
            all_triplets.update(path)

        # 计算每个三元组的梯度
        triplet_gradients = {}

        for path_idx, path in enumerate(record.paths):
            path_id = f"{record.timestamp}_{path_idx}"
            utility = record.utility_scores.get(path_id, 0.0)

            # 路径优先级（简化版）
            path_priority = self._compute_path_priority(path)

            # 对每个三元组计算梯度
            for triplet_id in path:
                if triplet_id not in self.triplet_scores:
                    # 初始化三元组评分
                    self.triplet_scores[triplet_id] = TripletScore(
                        triplet_id=triplet_id
                    )

                # 梯度计算（公式5的简化版）
                # ∇Sc(t)L = -α/(2E[U(L)]) · Σ(...) · Vi
                gradient = self._compute_triplet_gradient(
                    triplet_id=triplet_id,
                    path=path,
                    utility=utility,
                    path_priority=path_priority
                )

                if triplet_id not in triplet_gradients:
                    triplet_gradients[triplet_id] = 0.0
                triplet_gradients[triplet_id] += gradient

        # 更新三元组贡献分数
        for triplet_id, gradient in triplet_gradients.items():
            score_obj = self.triplet_scores[triplet_id]

            # 参数更新（公式8）
            # Sc(t) = Sc(t) - η·∇Sc(t)L
            score_obj.contribution_score -= self.learning_rate * gradient

            # 限制在[0, 1]范围
            score_obj.contribution_score = max(
                0.0, min(1.0, score_obj.contribution_score)
            )

            score_obj.update_count += 1
            score_obj.last_updated = datetime.now().isoformat()

        # 更新权衡参数α（公式9）
        self._update_alpha_parameter(record)

        logger.info(f"[FeedbackManager] 反向传播完成, "
                    f"更新三元组数: {len(triplet_gradients)}, "
                    f"当前α: {self.alpha:.3f}")

    def _compute_path_priority(self, path: List[str]) -> float:
        """
        计算路径优先级P(Li)（公式3的简化版）

        原文: P(Li) = exp((1/|Li|)·Σ(t∈Li) log P(t)) / Σ(...)

        Returns:
            路径优先级 [0, 1]
        """
        if not path:
            return 0.0

        log_sum = 0.0
        for triplet_id in path:
            priority = self.get_triplet_priority(triplet_id)
            if priority > 0:
                log_sum += np.log(priority)
            else:
                log_sum += np.log(1e-10)  # 避免log(0)

        avg_log = log_sum / len(path)
        priority = np.exp(avg_log)

        return priority

    def _compute_triplet_gradient(
        self,
        triplet_id: str,
        path: List[str],
        utility: float,
        path_priority: float
    ) -> float:
        """
        计算三元组梯度（公式5的简化版）

        原文: ∇Sc(t)L = -α/(2E[U(L)]) · Σ(ΠP(g)/P(t)) · Vi
        """
        # 计算期望效用E[U(L)]
        all_utilities = []
        for record in self.feedback_records:
            if record.utility_scores:
                all_utilities.extend(record.utility_scores.values())

        if not all_utilities:
            expected_utility = 0.5
        else:
            expected_utility = np.mean(all_utilities)

        if expected_utility == 0:
            expected_utility = 0.5

        # Vi = P(Li)/|Li| · (U(Li) - ΣP(Lj)·U(Lj))
        vi = (path_priority / len(path)) * (utility - expected_utility)

        # 梯度
        gradient = -self.alpha / (2 * expected_utility) * vi

        return gradient

    def _update_alpha_parameter(self, record: FeedbackRecord) -> None:
        """
        更新权衡参数α（公式9）

        原文: α = α - η·∇αL
        """
        # 计算α的梯度（公式7的简化版）
        # 这里使用简化逻辑
        avg_utility = np.mean(list(record.utility_scores.values()))

        # 如果效用高，增加α权重（更多依赖贡献分数）
        # 如果效用低，减少α权重（更多依赖语义相似度）
        alpha_gradient = 0.1 * (avg_utility - 0.5)

        self.alpha -= self.learning_rate * alpha_gradient

        # 限制α在[0, 1]范围
        self.alpha = max(0.0, min(1.0, self.alpha))

    def get_triplet_priority(self, triplet_id: str) -> float:
        """
        计算三元组混合优先级P(t)（公式2）

        P(t) = (1-α)·Sr(t) + α·Sc(t)

        Args:
            triplet_id: 三元组ID

        Returns:
            混合优先级 [0, 1]
        """
        if triplet_id not in self.triplet_scores:
            # 未追踪的三元组使用默认优先级
            return 0.5

        score_obj = self.triplet_scores[triplet_id]

        # P(t) = (1-α)·Sr(t) + α·Sc(t)
        priority = (1 - self.alpha) * score_obj.semantic_similarity + \
                   self.alpha * score_obj.contribution_score

        return priority

    def update_semantic_similarity(
        self,
        triplet_id: str,
        semantic_similarity: float
    ) -> None:
        """
        更新三元组语义相似度Sr(t)

        Args:
            triplet_id: 三元组ID
            semantic_similarity: 语义相似度 [0, 1]
        """
        if triplet_id not in self.triplet_scores:
            self.triplet_scores[triplet_id] = TripletScore(
                triplet_id=triplet_id
            )

        self.triplet_scores[triplet_id].semantic_similarity = semantic_similarity
        self.triplet_scores[triplet_id].last_updated = datetime.now().isoformat()

    def get_kg_evolution_candidates(self) -> Tuple[List[str], List[str]]:
        """
        获取KG进化候选（关系融合和抑制）

        Returns:
            (high_quality_triplets, low_quality_triplets)
        """
        if not self.triplet_scores:
            return [], []

        # 计算全局均值和标准差
        scores = [s.contribution_score for s in self.triplet_scores.values()]
        mean_score = np.mean(scores)
        std_score = np.std(scores)

        # 阈值计算
        tau_high = mean_score + std_score
        tau_low = mean_score - std_score

        high_quality = []
        low_quality = []

        for triplet_id, score_obj in self.triplet_scores.items():
            if score_obj.contribution_score > tau_high:
                high_quality.append(triplet_id)
            elif score_obj.contribution_score < tau_low:
                low_quality.append(triplet_id)

        logger.info(f"[FeedbackManager] KG进化候选, "
                    f"高质量: {len(high_quality)}, "
                    f"低质量: {len(low_quality)}, "
                    f"均值: {mean_score:.3f}, 标准差: {std_score:.3f}")

        return high_quality, low_quality

    def _load_feedback_db(self) -> None:
        """加载反馈数据库"""
        db_path = Path(self.feedback_db_path)

        if not db_path.exists():
            logger.info(f"[FeedbackManager] 反馈数据库不存在, 将创建新数据库")
            return

        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 加载反馈记录
            for record_data in data.get('feedback_records', []):
                record = FeedbackRecord(**record_data)
                self.feedback_records.append(record)

            # 加载三元组评分
            for triplet_id, score_data in data.get('triplet_scores', {}).items():
                self.triplet_scores[triplet_id] = TripletScore(**score_data)

            # 加载参数
            self.alpha = data.get('alpha', 0.5)
            self.learning_rate = data.get('learning_rate', 0.5)

            logger.info(f"[FeedbackManager] 加载反馈数据库成功, "
                        f"记录数: {len(self.feedback_records)}, "
                        f"三元组数: {len(self.triplet_scores)}")

        except Exception as e:
            logger.error(f"[FeedbackManager] 加载反馈数据库失败: {e}")

    def _save_feedback_db(self) -> None:
        """保存反馈数据库"""
        db_path = Path(self.feedback_db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            data = {
                'feedback_records': [
                    {
                        'query': r.query,
                        'response': r.response,
                        'paths': r.paths,
                        'feedback_score': r.feedback_score,
                        'feedback_type': r.feedback_type,
                        'utility_scores': r.utility_scores,
                        'timestamp': r.timestamp,
                        'metadata': r.metadata
                    }
                    for r in self.feedback_records
                ],
                'triplet_scores': {
                    tid: {
                        'triplet_id': ts.triplet_id,
                        'semantic_similarity': ts.semantic_similarity,
                        'contribution_score': ts.contribution_score,
                        'priority': ts.priority,
                        'update_count': ts.update_count,
                        'last_updated': ts.last_updated
                    }
                    for tid, ts in self.triplet_scores.items()
                },
                'alpha': self.alpha,
                'learning_rate': self.learning_rate,
                'last_updated': datetime.now().isoformat()
            }

            with open(db_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug(f"[FeedbackManager] 保存反馈数据库成功, "
                         f"路径: {db_path}")

        except Exception as e:
            logger.error(f"[FeedbackManager] 保存反馈数据库失败: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self.triplet_scores:
            return {
                'total_feedback': len(self.feedback_records),
                'total_triplets': 0,
                'alpha': self.alpha,
                'avg_contribution_score': 0.0
            }

        scores = [s.contribution_score for s in self.triplet_scores.values()]

        return {
            'total_feedback': len(self.feedback_records),
            'total_triplets': len(self.triplet_scores),
            'alpha': self.alpha,
            'avg_contribution_score': float(np.mean(scores)),
            'std_contribution_score': float(np.std(scores)),
            'high_quality_count': sum(1 for s in scores if s > self.high_threshold),
            'low_quality_count': sum(1 for s in scores if s < self.low_threshold)
        }


if __name__ == "__main__":
    # 测试反馈管理器
    manager = FeedbackManager()

    # 模拟反馈
    test_paths = [
        ["t1", "t2", "t3"],
        ["t2", "t4"],
        ["t3", "t5", "t6", "t7"]
    ]

    manager.add_feedback(
        query="什么是机器学习？",
        response="机器学习是...",
        paths=test_paths,
        feedback_score=4.5,
        feedback_type="human"
    )

    # 获取统计
    stats = manager.get_statistics()
    print(f"统计信息: {stats}")

    # 获取三元组优先级
    for tid in ["t1", "t2", "t3"]:
        priority = manager.get_triplet_priority(tid)
        print(f"三元组 {tid} 优先级: {priority:.3f}")

    # 获取KG进化候选
    high, low = manager.get_kg_evolution_candidates()
    print(f"高质量三元组: {high}")
    print(f"低质量三元组: {low}")
