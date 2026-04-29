"""
PRISM 优化器模块

实现 Entroly PRISM 优化器的核心功能：
1. 4维评估体系（更新频率、使用频率、语义相似度、香农熵）
2. 协方差矩阵计算
3. 代码片段智能筛选
"""

import math
import time
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
import hashlib


@dataclass
class CodeFragment:
    """代码片段"""
    fragment_id: str
    content: str
    file_path: str
    language: str
    start_line: int
    end_line: int
    hash: str
    created_at: float
    updated_at: float


@dataclass
class FragmentMetrics:
    """片段度量"""
    fragment_id: str
    update_frequency: float = 0.0      # 更新频率
    usage_frequency: float = 0.0       # 使用频率
    semantic_similarity: float = 0.0   # 语义相似度
    shannon_entropy: float = 0.0       # 香农熵
    last_used: float = 0.0             # 上次使用时间
    use_count: int = 0                 # 使用次数
    importance_score: float = 0.0     # 综合重要性评分


@dataclass
class PRISMConfig:
    """PRISM 配置"""
    noise_filter_ratio: float = 0.8    # 噪音过滤比例（过滤80%）
    entropy_threshold: float = 0.3     # 熵阈值
    similarity_threshold: float = 0.5   # 相似度阈值
    decay_factor: float = 0.95          # 衰减因子
    time_window: int = 3600            # 时间窗口（秒）


class ShannonEntropyCalculator:
    """香农熵计算器"""

    @staticmethod
    def calculate_entropy(text: str) -> float:
        """
        计算香农熵

        公式: H(X) = -Σ p(xi) log2 p(xi)
        用于衡量信息的不确定性
        """
        if not text:
            return 0.0

        # 统计字符频率
        char_freq = defaultdict(int)
        total_chars = len(text)

        for char in text:
            char_freq[char] += 1

        # 计算熵
        entropy = 0.0
        for freq in char_freq.values():
            if freq > 0:
                p = freq / total_chars
                entropy -= p * math.log2(p)

        # 归一化（最大熵为 log2(字符集大小)）
        max_entropy = math.log2(len(char_freq)) if char_freq else 1
        return entropy / max_entropy if max_entropy > 0 else 0.0

    @staticmethod
    def calculate_token_entropy(tokens: List[str]) -> float:
        """
        计算 token 级别的熵
        """
        if not tokens:
            return 0.0

        token_freq = defaultdict(int)
        total_tokens = len(tokens)

        for token in tokens:
            token_freq[token] += 1

        entropy = 0.0
        for freq in token_freq.values():
            if freq > 0:
                p = freq / total_tokens
                entropy -= p * math.log2(p)

        return entropy

    @staticmethod
    def calculate_semantic_entropy(code: str, keywords: List[str]) -> float:
        """
        计算语义熵（考虑关键词的分布）
        """
        if not keywords:
            return ShannonEntropyCalculator.calculate_entropy(code)

        # 计算关键词出现位置的熵
        positions = []
        code_lower = code.lower()
        for keyword in keywords:
            pos = code_lower.find(keyword.lower())
            if pos >= 0:
                positions.append(pos / len(code) if len(code) > 0 else 0)

        if not positions:
            return ShannonEntropyCalculator.calculate_entropy(code)

        # 位置熵
        pos_freq = defaultdict(int)
        for pos in positions:
            bucket = int(pos * 10) / 10  # 分成10个桶
            pos_freq[bucket] += 1

        entropy = 0.0
        total = len(positions)
        for freq in pos_freq.values():
            p = freq / total
            entropy -= p * math.log2(p)

        return entropy


class CovarianceMatrixBuilder:
    """协方差矩阵构建器"""

    def __init__(self):
        self.dimensions = ["update_freq", "usage_freq", "semantic_sim", "shannon_entropy"]
        self.matrix: Optional[np.ndarray] = None

    def build_matrix(self, metrics: List[FragmentMetrics]) -> np.ndarray:
        """
        构建 4x4 协方差矩阵

        维度: [更新频率, 使用频率, 语义相似度, 香农熵]
        """
        if len(metrics) < 2:
            # 数据不足时返回单位矩阵
            return np.eye(4)

        # 提取特征
        features = np.array([
            [m.update_frequency for m in metrics],
            [m.usage_frequency for m in metrics],
            [m.semantic_similarity for m in metrics],
            [m.shannon_entropy for m in metrics]
        ])

        # 标准化
        mean = np.mean(features, axis=1, keepdims=True)
        std = np.std(features, axis=1, keepdims=True)
        std[std == 0] = 1  # 避免除零

        normalized = (features - mean) / std

        # 计算协方差矩阵
        cov_matrix = np.cov(normalized)

        self.matrix = cov_matrix
        return cov_matrix

    def get_covariance(self, metric1_idx: int, metric2_idx: int) -> float:
        """获取两个度量之间的协方差"""
        if self.matrix is None:
            return 0.0

        return float(self.matrix[metric1_idx, metric2_idx])

    def get_correlation(self, metric1_idx: int, metric2_idx: int) -> float:
        """获取两个度量之间的相关系数"""
        if self.matrix is None:
            return 0.0

        cov = self.matrix[metric1_idx, metric2_idx]
        var1 = self.matrix[metric1_idx, metric1_idx]
        var2 = self.matrix[metric2_idx, metric2_idx]

        if var1 == 0 or var2 == 0:
            return 0.0

        return cov / (math.sqrt(var1) * math.sqrt(var2))


class PRISMOptimizer:
    """
    PRISM 优化器

    核心功能：
    1. 多维度评估代码片段
    2. 构建协方差矩阵
    3. 过滤无效噪音，保留核心代码
    """

    def __init__(self, config: Optional[PRISMConfig] = None):
        """初始化 PRISM 优化器"""
        self.config = config or PRISMConfig()
        self.entropy_calculator = ShannonEntropyCalculator()
        self.matrix_builder = CovarianceMatrixBuilder()
        self.fragment_metrics: Dict[str, FragmentMetrics] = {}
        self.fragment_history: Dict[str, List[float]] = defaultdict(list)

    def add_fragment(self, fragment: CodeFragment) -> FragmentMetrics:
        """
        添加代码片段并计算度量

        Args:
            fragment: 代码片段

        Returns:
            FragmentMetrics: 片段度量
        """
        # 计算香农熵
        entropy = self.entropy_calculator.calculate_entropy(fragment.content)

        # 创建度量
        metrics = FragmentMetrics(
            fragment_id=fragment.fragment_id,
            update_frequency=0.0,
            usage_frequency=0.0,
            semantic_similarity=0.0,
            shannon_entropy=entropy,
            last_used=time.time(),
            use_count=0,
            importance_score=0.0
        )

        self.fragment_metrics[fragment.fragment_id] = metrics
        return metrics

    def update_metrics(
        self,
        fragment_id: str,
        is_used: bool = False,
        semantic_context: Optional[str] = None
    ) -> FragmentMetrics:
        """
        更新片段度量

        Args:
            fragment_id: 片段 ID
            is_used: 是否被使用
            semantic_context: 语义上下文

        Returns:
            FragmentMetrics: 更新后的度量
        """
        if fragment_id not in self.fragment_metrics:
            raise ValueError(f"Fragment not found: {fragment_id}")

        metrics = self.fragment_metrics[fragment_id]
        now = time.time()

        # 更新频率（时间衰减）
        time_since_update = now - metrics.last_used
        metrics.update_frequency = math.exp(-time_since_update / self.config.time_window)

        # 使用频率
        if is_used:
            metrics.use_count += 1
            metrics.usage_frequency = min(1.0, metrics.use_count / 10)  # 归一化
            metrics.last_used = now

        # 语义相似度
        if semantic_context:
            metrics.semantic_similarity = self._calculate_similarity(
                fragment_id, semantic_context
            )

        # 重新计算重要性评分
        metrics.importance_score = self._calculate_importance(metrics)

        return metrics

    def _calculate_importance(self, metrics: FragmentMetrics) -> float:
        """计算综合重要性评分"""
        # 权重配置
        weights = {
            "update": 0.2,
            "usage": 0.35,
            "similarity": 0.25,
            "entropy": 0.2
        }

        # 综合评分
        score = (
            weights["update"] * metrics.update_frequency +
            weights["usage"] * metrics.usage_frequency +
            weights["similarity"] * metrics.semantic_similarity +
            weights["entropy"] * (1 - metrics.shannon_entropy)  # 低熵 = 高价值
        )

        return score

    def _calculate_similarity(self, fragment_id: str, context: str) -> float:
        """计算语义相似度（简单词频重叠）"""
        if fragment_id not in self.fragment_metrics:
            return 0.0

        fragment = self.fragment_metrics[fragment_id]
        # 简单实现：统计关键词重叠度
        fragment_words = set(fragment.fragment_id.lower().split())
        context_words = set(context.lower().split())

        if not fragment_words or not context_words:
            return 0.0

        overlap = len(fragment_words & context_words)
        return overlap / len(fragment_words | context_words)

    def build_covariance_matrix(self) -> np.ndarray:
        """构建协方差矩阵"""
        metrics_list = list(self.fragment_metrics.values())
        return self.matrix_builder.build_matrix(metrics_list)

    def filter_noise(
        self,
        query: str,
        top_k: Optional[int] = None
    ) -> List[Tuple[str, float]]:
        """
        过滤噪音，保留核心代码片段

        Args:
            query: 查询字符串
            top_k: 保留前 k 个片段

        Returns:
            List[Tuple[fragment_id, importance_score]]: 排序后的核心片段
        """
        # 更新所有片段的语义相似度
        for fragment_id in self.fragment_metrics:
            self.update_metrics(fragment_id, semantic_context=query)

        # 获取所有片段及其评分
        scored_fragments = [
            (fragment_id, metrics.importance_score)
            for fragment_id, metrics in self.fragment_metrics.items()
        ]

        # 按评分降序排序
        scored_fragments.sort(key=lambda x: x[1], reverse=True)

        # 计算保留数量（默认保留20%，即过滤80%噪音）
        if top_k is None:
            total = len(scored_fragments)
            keep_count = max(1, int(total * (1 - self.config.noise_filter_ratio)))
            top_k = keep_count

        # 返回 top_k
        return scored_fragments[:top_k]

    def get_fragment_report(self) -> Dict[str, Any]:
        """获取优化报告"""
        total_fragments = len(self.fragment_metrics)
        avg_importance = 0.0
        avg_entropy = 0.0

        if total_fragments > 0:
            avg_importance = sum(m.importance_score for m in self.fragment_metrics.values()) / total_fragments
            avg_entropy = sum(m.shannon_entropy for m in self.fragment_metrics.values()) / total_fragments

        return {
            "total_fragments": total_fragments,
            "average_importance": avg_importance,
            "average_entropy": avg_entropy,
            "dimensions": self.matrix_builder.dimensions,
            "noise_filter_ratio": self.config.noise_filter_ratio,
            "filtered_count": int(total_fragments * self.config.noise_filter_ratio),
            "retained_count": int(total_fragments * (1 - self.config.noise_filter_ratio))
        }


class FragmentManager:
    """代码片段管理器"""

    def __init__(self, prism_optimizer: Optional[PRISMOptimizer] = None):
        """初始化片段管理器"""
        self.fragments: Dict[str, CodeFragment] = {}
        self.prism = prism_optimizer or PRISMOptimizer()

    def add_fragment(
        self,
        content: str,
        file_path: str,
        language: str,
        start_line: int,
        end_line: int
    ) -> str:
        """
        添加代码片段

        Args:
            content: 代码内容
            file_path: 文件路径
            language: 编程语言
            start_line: 起始行
            end_line: 结束行

        Returns:
            str: 片段 ID
        """
        fragment_id = hashlib.md5(f"{file_path}:{start_line}:{end_line}".encode()).hexdigest()[:12]

        fragment = CodeFragment(
            fragment_id=fragment_id,
            content=content,
            file_path=file_path,
            language=language,
            start_line=start_line,
            end_line=end_line,
            hash=hashlib.md5(content.encode()).hexdigest(),
            created_at=time.time(),
            updated_at=time.time()
        )

        self.fragments[fragment_id] = fragment
        self.prism.add_fragment(fragment)

        return fragment_id

    def get_fragment(self, fragment_id: str) -> Optional[CodeFragment]:
        """获取片段"""
        return self.fragments.get(fragment_id)

    def get_core_fragments(self, query: str, max_tokens: int = 4000) -> List[CodeFragment]:
        """
        获取核心片段

        Args:
            query: 查询字符串
            max_tokens: 最大 token 数

        Returns:
            List[CodeFragment]: 核心片段列表
        """
        # 过滤噪音
        filtered = self.prism.filter_noise(query)

        # 获取片段
        fragments = []
        total_tokens = 0

        for fragment_id, score in filtered:
            fragment = self.fragments.get(fragment_id)
            if not fragment:
                continue

            # 估算 token 数
            tokens = len(fragment.content.split())
            if total_tokens + tokens > max_tokens:
                break

            fragments.append(fragment)
            total_tokens += tokens

        return fragments


# 全局实例
_global_prism_optimizer: Optional[PRISMOptimizer] = None


def get_prism_optimizer() -> PRISMOptimizer:
    """获取 PRISM 优化器"""
    global _global_prism_optimizer
    if _global_prism_optimizer is None:
        _global_prism_optimizer = PRISMOptimizer()
    return _global_prism_optimizer
