"""
LivingTree Knowledge Wiki - EvoRAG 反馈管理系统
==============================================

实现反馈驱动反向传播机制。

从 client/src/business/llm_wiki/feedback_manager.py 迁移而来。
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path

try:
    import numpy as np
except ImportError:
    np = None

from loguru import logger


@dataclass
class FeedbackRecord:
    """反馈记录"""
    query: str
    response: str
    paths: List[List[str]]
    feedback_score: float
    feedback_type: str = "human"
    utility_scores: Dict[str, float] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TripletScore:
    """三元组评分"""
    triplet_id: str
    semantic_similarity: float = 0.5
    contribution_score: float = 0.5
    priority: float = 0.5
    update_count: int = 0
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())


class FeedbackManager:
    """
    反馈驱动反向传播管理器
    实现 EvoRAG 的反馈驱动机制
    """

    def __init__(
        self,
        feedback_db_path: Optional[str] = None,
        learning_rate: float = 0.5,
        alpha: float = 0.5,
        high_threshold: float = 0.7,
        low_threshold: float = 0.3
    ):
        self.feedback_db_path = feedback_db_path or \
            "client/data/llm_wiki/feedback_db.json"
        self.learning_rate = learning_rate
        self.alpha = alpha
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold

        self.feedback_records: List[FeedbackRecord] = []
        self.triplet_scores: Dict[str, TripletScore] = {}
        self.path_utility_cache: Dict[str, float] = {}

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
        record = FeedbackRecord(
            query=query,
            response=response,
            paths=paths,
            feedback_score=feedback_score,
            feedback_type=feedback_type
        )

        self.feedback_records.append(record)
        self._compute_path_utilities(record)
        self._backward_propagation(record)
        self._save_feedback_db()

        logger.info(f"[FeedbackManager] 添加反馈记录, "
                    f"查询: {query[:50]}..., "
                    f"分数: {feedback_score}, "
                    f"路径数: {len(paths)}")

        return record.timestamp

    def _compute_path_utilities(self, record: FeedbackRecord) -> None:
        for path_idx, path in enumerate(record.paths):
            path_id = f"{record.timestamp}_{path_idx}"

            utility = self._estimate_path_utility(
                query=record.query,
                response=record.response,
                path=path,
                feedback_score=record.feedback_score
            )

            record.utility_scores[path_id] = utility
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
        normalized_score = (feedback_score - 3) / 2
        path_length_factor = min(len(path) / 5.0, 1.0)
        utility = normalized_score * path_length_factor
        return max(-1.0, min(1.0, utility))

    def _backward_propagation(self, record: FeedbackRecord) -> None:
        if not record.utility_scores:
            logger.warning("[FeedbackManager] 无路径效用分数, 跳过反向传播")
            return

        all_triplets = set()
        for path in record.paths:
            all_triplets.update(path)

        triplet_gradients = {}

        for path_idx, path in enumerate(record.paths):
            path_id = f"{record.timestamp}_{path_idx}"
            utility = record.utility_scores.get(path_id, 0.0)
            path_priority = self._compute_path_priority(path)

            for triplet_id in path:
                if triplet_id not in self.triplet_scores:
                    self.triplet_scores[triplet_id] = TripletScore(
                        triplet_id=triplet_id
                    )

                gradient = self._compute_triplet_gradient(
                    triplet_id=triplet_id,
                    path=path,
                    utility=utility,
                    path_priority=path_priority
                )

                if triplet_id not in triplet_gradients:
                    triplet_gradients[triplet_id] = 0.0
                triplet_gradients[triplet_id] += gradient

        for triplet_id, gradient in triplet_gradients.items():
            score_obj = self.triplet_scores[triplet_id]
            score_obj.contribution_score -= self.learning_rate * gradient
            score_obj.contribution_score = max(
                0.0, min(1.0, score_obj.contribution_score)
            )
            score_obj.update_count += 1
            score_obj.last_updated = datetime.now().isoformat()

        self._update_alpha_parameter(record)

        logger.info(f"[FeedbackManager] 反向传播完成, "
                    f"更新三元组数: {len(triplet_gradients)}, "
                    f"当前α: {self.alpha:.3f}")

    def _compute_path_priority(self, path: List[str]) -> float:
        if not path:
            return 0.0

        if np is None:
            return 0.5

        log_sum = 0.0
        for triplet_id in path:
            priority = self.get_triplet_priority(triplet_id)
            if priority > 0:
                log_sum += np.log(priority)
            else:
                log_sum += np.log(1e-10)

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
        all_utilities = []
        for record in self.feedback_records:
            if record.utility_scores:
                all_utilities.extend(record.utility_scores.values())

        if not all_utilities:
            expected_utility = 0.5
        else:
            if np is None:
                expected_utility = sum(all_utilities) / len(all_utilities)
            else:
                expected_utility = float(np.mean(all_utilities))

        if expected_utility == 0:
            expected_utility = 0.5

        vi = (path_priority / len(path)) * (utility - expected_utility)
        gradient = -self.alpha / (2 * expected_utility) * vi

        return gradient

    def _update_alpha_parameter(self, record: FeedbackRecord) -> None:
        avg_utility = sum(record.utility_scores.values()) / len(record.utility_scores)
        alpha_gradient = 0.1 * (avg_utility - 0.5)
        self.alpha -= self.learning_rate * alpha_gradient
        self.alpha = max(0.0, min(1.0, self.alpha))

    def get_triplet_priority(self, triplet_id: str) -> float:
        if triplet_id not in self.triplet_scores:
            return 0.5

        score_obj = self.triplet_scores[triplet_id]
        priority = (1 - self.alpha) * score_obj.semantic_similarity + \
                   self.alpha * score_obj.contribution_score

        return priority

    def update_semantic_similarity(
        self,
        triplet_id: str,
        semantic_similarity: float
    ) -> None:
        if triplet_id not in self.triplet_scores:
            self.triplet_scores[triplet_id] = TripletScore(
                triplet_id=triplet_id
            )

        self.triplet_scores[triplet_id].semantic_similarity = semantic_similarity
        self.triplet_scores[triplet_id].last_updated = datetime.now().isoformat()

    def get_kg_evolution_candidates(self) -> Tuple[List[str], List[str]]:
        if not self.triplet_scores:
            return [], []

        scores = [s.contribution_score for s in self.triplet_scores.values()]

        if np is None:
            mean_score = sum(scores) / len(scores)
            variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
            std_score = variance ** 0.5
        else:
            mean_score = float(np.mean(scores))
            std_score = float(np.std(scores))

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
        db_path = Path(self.feedback_db_path)

        if not db_path.exists():
            logger.info(f"[FeedbackManager] 反馈数据库不存在, 将创建新数据库")
            return

        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for record_data in data.get('feedback_records', []):
                record = FeedbackRecord(**record_data)
                self.feedback_records.append(record)

            for triplet_id, score_data in data.get('triplet_scores', {}).items():
                self.triplet_scores[triplet_id] = TripletScore(**score_data)

            self.alpha = data.get('alpha', 0.5)
            self.learning_rate = data.get('learning_rate', 0.5)

            logger.info(f"[FeedbackManager] 加载反馈数据库成功, "
                        f"记录数: {len(self.feedback_records)}, "
                        f"三元组数: {len(self.triplet_scores)}")

        except Exception as e:
            logger.error(f"[FeedbackManager] 加载反馈数据库失败: {e}")

    def _save_feedback_db(self) -> None:
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
        if not self.triplet_scores:
            return {
                'total_feedback': len(self.feedback_records),
                'total_triplets': 0,
                'alpha': self.alpha,
                'avg_contribution_score': 0.0
            }

        scores = [s.contribution_score for s in self.triplet_scores.values()]

        if np is None:
            avg_score = sum(scores) / len(scores)
            variance = sum((s - avg_score) ** 2 for s in scores) / len(scores)
            std_score = variance ** 0.5
            avg_score = float(avg_score)
            std_score = float(std_score)
        else:
            avg_score = float(np.mean(scores))
            std_score = float(np.std(scores))

        return {
            'total_feedback': len(self.feedback_records),
            'total_triplets': len(self.triplet_scores),
            'alpha': self.alpha,
            'avg_contribution_score': avg_score,
            'std_contribution_score': std_score,
            'high_quality_count': sum(1 for s in scores if s > self.high_threshold),
            'low_quality_count': sum(1 for s in scores if s < self.low_threshold)
        }
