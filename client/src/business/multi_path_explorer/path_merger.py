"""
多路径探索器 - 路径合并策略

合并多条探索路径的结果和见解
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum

from .path_models import ExplorationPath, ExplorationResult


class MergeStrategy(Enum):
    """合并策略类型"""
    BEST_ONLY = "best_only"              # 仅保留最佳
    WEIGHTED_AVERAGE = "weighted_average"  # 加权平均
    VOTE = "vote"                        # 投票
    ENSEMBLE = "ensemble"                # 集成
    SELECTIVE = "selective"              # 选择性合并


@dataclass
class MergeConfig:
    """合并配置"""
    strategy: MergeStrategy = MergeStrategy.WEIGHTED_AVERAGE
    
    # 权重相关
    use_score_as_weight: bool = True    # 使用评分作为权重
    use_confidence_as_weight: bool = True
    
    # 投票相关
    min_vote_threshold: float = 0.5      # 投票通过阈值
    
    # 选择性合并
    selective_fields: List[str] = None   # 选择性合并的字段
    
    # 集成参数
    ensemble_method: str = "mean"        # mean/max/stack
    
    def __post_init__(self):
        if self.selective_fields is None:
            self.selective_fields = ["result", "insights"]


class PathMerger(ABC):
    """
    路径合并器基类
    """
    
    def __init__(self, config: Optional[MergeConfig] = None):
        self.config = config or MergeConfig()
    
    @abstractmethod
    def merge(
        self,
        paths: List[ExplorationPath],
        primary: Optional[ExplorationPath] = None
    ) -> Dict[str, Any]:
        """
        合并路径
        
        Args:
            paths: 待合并的路径列表
            primary: 主要路径
            
        Returns:
            合并后的结果
        """
        pass
    
    def _get_weight(self, path: ExplorationPath) -> float:
        """获取路径权重"""
        weight = 1.0
        
        if self.config.use_score_as_weight:
            weight *= path.score if path.score > 0 else 1.0
        
        if self.config.use_confidence_as_weight:
            weight *= path.confidence if path.confidence > 0 else 1.0
        
        return max(0.1, weight)


class BestOnlyMerger(PathMerger):
    """
    仅保留最佳路径
    """
    
    def merge(
        self,
        paths: List[ExplorationPath],
        primary: Optional[ExplorationPath] = None
    ) -> Dict[str, Any]:
        if primary and primary.result:
            return {
                "result": primary.result,
                "source": primary.path_id,
                "score": primary.score,
                "merge_type": "best_only"
            }
        
        # 找到最佳路径
        best = max(
            [p for p in paths if p.result],
            key=lambda p: (p.score, p.confidence),
            default=None
        )
        
        if best:
            return {
                "result": best.result,
                "source": best.path_id,
                "score": best.score,
                "merge_type": "best_only"
            }
        
        return {"error": "No successful paths to merge", "merge_type": "best_only"}


class WeightedAverageMerger(PathMerger):
    """
    加权平均合并
    
    对数值结果进行加权平均
    """
    
    def merge(
        self,
        paths: List[ExplorationPath],
        primary: Optional[ExplorationPath] = None
    ) -> Dict[str, Any]:
        successful = [p for p in paths if p.result]
        if not successful:
            return {"error": "No successful paths", "merge_type": "weighted_average"}
        
        # 计算总权重
        total_weight = sum(self._get_weight(p) for p in successful)
        
        # 加权合并数值字段
        merged = {
            "_meta": {
                "source_paths": [p.path_id for p in successful],
                "weights": {p.path_id: self._get_weight(p) / total_weight for p in successful},
                "merge_type": "weighted_average"
            }
        }
        
        # 尝试合并结果字段
        if primary and primary.result:
            merged["result"] = primary.result.copy()
        else:
            merged["result"] = {}
        
        # 对公共键进行加权
        numeric_keys = self._find_numeric_keys(successful)
        for key in numeric_keys:
            values = []
            weights = []
            for p in successful:
                if p.result and key in p.result:
                    val = p.result[key]
                    if isinstance(val, (int, float)):
                        values.append(val)
                        weights.append(self._get_weight(p))
            
            if values and weights:
                merged["result"][key] = sum(v * w for v, w in zip(values, weights)) / sum(weights)
        
        return merged
    
    def _find_numeric_keys(self, paths: List[ExplorationPath]) -> List[str]:
        """找出所有路径共有的数值键"""
        if not paths:
            return []
        
        # 收集所有键及其类型
        key_types: Dict[str, List[type]] = {}
        for path in paths:
            if path.result:
                for key, value in path.result.items():
                    if isinstance(value, (int, float)) and not key.startswith("_"):
                        if key not in key_types:
                            key_types[key] = []
                        key_types[key].append(type(value))
        
        # 返回类型一致的键
        return [
            key for key, types in key_types.items()
            if len(set(types)) == 1
        ]


class VoteMerger(PathMerger):
    """
    投票合并
    
    对分类/选择结果进行投票
    """
    
    def merge(
        self,
        paths: List[ExplorationPath],
        primary: Optional[ExplorationPath] = None
    ) -> Dict[str, Any]:
        successful = [p for p in paths if p.result]
        if not successful:
            return {"error": "No successful paths", "merge_type": "vote"}
        
        # 收集所有可能的决策键
        decision_keys = set()
        for p in successful:
            if p.result:
                decision_keys.update(p.result.keys())
        
        merged = {
            "_meta": {
                "source_paths": [p.path_id for p in successful],
                "vote_results": {},
                "merge_type": "vote"
            }
        }
        
        # 对每个决策键进行投票
        for key in decision_keys:
            votes: Dict[Any, float] = {}
            for p in successful:
                if p.result and key in p.result:
                    value = p.result[key]
                    weight = self._get_weight(p)
                    if value not in votes:
                        votes[value] = 0.0
                    votes[value] += weight
            
            # 找出获胜者
            if votes:
                winner = max(votes.items(), key=lambda x: x[1])
                total = sum(votes.values())
                merged["_meta"]["vote_results"][key] = {
                    "winner": winner[0],
                    "confidence": winner[1] / total,
                    "all_votes": votes
                }
                
                # 将结果添加到主结果
                if key not in merged:
                    merged[key] = winner[0]
        
        # 使用主路径的结果作为基础
        if primary and primary.result:
            merged.update(primary.result)
        
        return merged


class EnsembleMerger(PathMerger):
    """
    集成合并
    
    使用机器学习集成技术合并结果
    """
    
    def __init__(self, config: Optional[MergeConfig] = None):
        super().__init__(config)
        self._ensemble_method = config.ensemble_method if config else "mean"
    
    def merge(
        self,
        paths: List[ExplorationPath],
        primary: Optional[ExplorationPath] = None
    ) -> Dict[str, Any]:
        successful = [p for p in paths if p.result]
        if not successful:
            return {"error": "No successful paths", "merge_type": "ensemble"}
        
        # 根据方法合并
        if self._ensemble_method == "mean":
            return self._ensemble_mean(successful)
        elif self._ensemble_method == "max":
            return self._ensemble_max(successful)
        elif self._ensemble_method == "stack":
            return self._ensemble_stack(successful)
        else:
            return self._ensemble_mean(successful)
    
    def _ensemble_mean(self, paths: List[ExplorationPath]) -> Dict[str, Any]:
        """平均集成"""
        merger = WeightedAverageMerger(self.config)
        return merger.merge(paths)
    
    def _ensemble_max(self, paths: List[ExplorationPath]) -> Dict[str, Any]:
        """最大集成 - 选择评分最高的路径"""
        merger = BestOnlyMerger(self.config)
        return merger.merge(paths)
    
    def _ensemble_stack(self, paths: List[ExplorationPath]) -> Dict[str, Any]:
        """堆叠集成 - 收集所有结果"""
        merged = {
            "_meta": {
                "source_paths": [p.path_id for p in paths],
                "all_results": [p.result for p in paths if p.result],
                "merge_type": "ensemble_stack"
            }
        }
        
        # 收集见解
        insights = []
        for p in paths:
            if p.metadata.get("insight"):
                insights.append({
                    "path_id": p.path_id,
                    "insight": p.metadata["insight"],
                    "weight": self._get_weight(p)
                })
        
        if insights:
            merged["insights"] = insights
        
        # 使用最佳路径作为主要结果
        best = max(paths, key=lambda p: (p.score, p.confidence))
        merged["result"] = best.result
        
        return merged


class SelectiveMerger(PathMerger):
    """
    选择性合并
    
    只合并指定的字段
    """
    
    def merge(
        self,
        paths: List[ExplorationPath],
        primary: Optional[ExplorationPath] = None
    ) -> Dict[str, Any]:
        successful = [p for p in paths if p.result]
        if not successful:
            return {"error": "No successful paths", "merge_type": "selective"}
        
        fields = self.config.selective_fields
        merged = {
            "_meta": {
                "selected_fields": fields,
                "merge_type": "selective"
            }
        }
        
        # 收集每个字段的最佳值
        for field in fields:
            if field == "result":
                continue
            
            best_value = None
            best_weight = 0.0
            best_path_id = None
            
            for p in successful:
                if p.result and field in p.result:
                    weight = self._get_weight(p)
                    if weight > best_weight:
                        best_weight = weight
                        best_value = p.result[field]
                        best_path_id = p.path_id
            
            if best_value is not None:
                merged[field] = best_value
                merged[f"_{field}_source"] = best_path_id
        
        # 使用主路径的结果
        if primary and primary.result:
            merged["result"] = primary.result
        
        return merged


class PathMergerFactory:
    """路径合并器工厂"""
    
    @staticmethod
    def create(
        strategy: MergeStrategy,
        config: Optional[MergeConfig] = None
    ) -> PathMerger:
        """创建合并器"""
        mergers = {
            MergeStrategy.BEST_ONLY: BestOnlyMerger,
            MergeStrategy.WEIGHTED_AVERAGE: WeightedAverageMerger,
            MergeStrategy.VOTE: VoteMerger,
            MergeStrategy.ENSEMBLE: EnsembleMerger,
            MergeStrategy.SELECTIVE: SelectiveMerger
        }
        
        merger_class = mergers.get(strategy, WeightedAverageMerger)
        return merger_class(config)
    
    @staticmethod
    def create_from_config(config: MergeConfig) -> PathMerger:
        """从配置创建合并器"""
        return PathMergerFactory.create(config.strategy, config)


class SmartMerger(PathMerger):
    """
    智能合并器
    
    根据结果类型自动选择最佳合并策略
    """
    
    def __init__(self, config: Optional[MergeConfig] = None):
        super().__init__(config)
        self._config = config or MergeConfig()
    
    def merge(
        self,
        paths: List[ExplorationPath],
        primary: Optional[ExplorationPath] = None
    ) -> Dict[str, Any]:
        successful = [p for p in paths if p.result]
        if not successful:
            return {"error": "No successful paths", "merge_type": "smart"}
        
        # 分析结果类型
        result_types = self._analyze_result_types(successful)
        
        # 根据类型选择策略
        if result_types["is_numeric_heavy"]:
            # 数值结果为主，使用加权平均
            merger = WeightedAverageMerger(self._config)
        elif result_types["is_categorical_heavy"]:
            # 分类结果为主，使用投票
            merger = VoteMerger(self._config)
        elif result_types["has_multiple_insights"]:
            # 有多个见解，使用集成
            merger = EnsembleMerger(self._config)
        else:
            # 默认使用最佳
            merger = BestOnlyMerger(self._config)
        
        return merger.merge(paths, primary)
    
    def _analyze_result_types(
        self,
        paths: List[ExplorationPath]
    ) -> Dict[str, bool]:
        """分析结果类型"""
        numeric_count = 0
        categorical_count = 0
        has_insights = False
        
        for p in paths:
            if p.result:
                for key, value in p.result.items():
                    if isinstance(value, (int, float)):
                        numeric_count += 1
                    elif isinstance(value, (str, bool)):
                        categorical_count += 1
                
                if "insight" in p.result or p.metadata.get("insight"):
                    has_insights = True
        
        return {
            "is_numeric_heavy": numeric_count > categorical_count,
            "is_categorical_heavy": categorical_count > numeric_count,
            "has_multiple_insights": has_insights and len(paths) > 1
        }
