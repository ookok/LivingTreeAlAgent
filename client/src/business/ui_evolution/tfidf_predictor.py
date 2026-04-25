# -*- coding: utf-8 -*-
"""
微型 TF-IDF 预测器 (Tiny TF-IDF Predictor)
==========================================

轻量级操作预测器，使用 TF-IDF + 规则模式匹配实现 <1ms 预测。

核心特性:
- 纯 Python 实现，零外部依赖
- <100KB 模型大小
- <1ms 响应时间
- 增量学习支持

Author: LivingTreeAI Team
Date: 2026-04-24
"""

from client.src.business.logger import get_logger
logger = get_logger('ui_evolution.tfidf_predictor')

import json
import re
import math
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from datetime import datetime
import threading
import hashlib


# =============================================================================
# 数据模型
# =============================================================================

@dataclass
class PredictionResult:
    """预测结果"""
    predicted_action: str           # 预测的操作
    confidence: float                # 置信度 0-1
    alternatives: List[Tuple[str, float]] = field(default_factory=list)  # 备选预测
    source: str = "unknown"          # 预测来源: tfidf, pattern, fallback
    reason: str = ""                 # 预测原因
    
    @property
    def is_confident(self) -> bool:
        return self.confidence >= 0.7


@dataclass
class TrainedModel:
    """训练好的模型数据"""
    vocabulary: Dict[str, int]       # 词表: action -> index
    idf_scores: Dict[str, float]     # IDF 分数
    transition_probs: Dict[str, Dict[str, int]]  # 转移概率
    action_frequency: Counter        # 动作频率
    sequence_patterns: Dict[str, List[str]]  # 序列模式 (key: json string of tuple)
    trained_at: datetime = field(default_factory=datetime.now)
    
    def save(self, path: Path):
        """保存模型"""
        # 转换 tuple key 为字符串
        patterns_str = {
            json.dumps(k): v 
            for k, v in self.sequence_patterns.items()
        }
        data = {
            "vocabulary": self.vocabulary,
            "idf_scores": self.idf_scores,
            "transition_probs": {k: dict(v) for k, v in self.transition_probs.items()},
            "action_frequency": dict(self.action_frequency),
            "sequence_patterns": patterns_str,
            "trained_at": self.trained_at.isoformat(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load(cls, path: Path) -> "TrainedModel":
        """加载模型"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 转换字符串 key 为 tuple
        patterns_tuple = {
            tuple(json.loads(k)): v 
            for k, v in data["sequence_patterns"].items()
        }
        
        return cls(
            vocabulary=data["vocabulary"],
            idf_scores=data["idf_scores"],
            transition_probs={k: defaultdict(int, v) for k, v in data["transition_probs"].items()},
            action_frequency=Counter(data["action_frequency"]),
            sequence_patterns=patterns_tuple,
            trained_at=datetime.fromisoformat(data["trained_at"]),
        )


# =============================================================================
# TF-IDF 预测器
# =============================================================================

class TFIDFPredictor:
    """
    微型 TF-IDF 操作预测器
    
    工作原理:
    1. 将操作序列转换为 TF 向量
    2. 使用 IDF 加权
    3. 基于历史模式预测下一步
    
    响应时间目标: <1ms
    """
    
    # 动作标准化规则
    ACTION_PATTERNS = [
        (r"click:(.+)_btn", r"click:\1"),        # click:send_btn -> click:send
        (r"input:(.+)_field:.+", r"input:\1"),   # input:msg_field:xxx -> input:msg
        (r"select:(.+)_dropdown:.+", r"select:\1"),  # 同上
        (r"scroll:(.+):(.+)", r"scroll:\1"),     # scroll:up:fast -> scroll:up
    ]
    
    def __init__(self, model_path: str = None):
        self.model_path = Path(model_path) if model_path else None
        self.model: Optional[TrainedModel] = None
        self._lock = threading.Lock()
        
        # 内嵌默认模式（冷启动）
        self._default_patterns = self._get_default_patterns()
        
        # 加载已有模型
        if self.model_path and self.model_path.exists():
            try:
                self.model = TrainedModel.load(self.model_path)
            except Exception:
                pass
    
    def _get_default_patterns(self) -> Dict[str, List[str]]:
        """获取默认模式（冷启动用）"""
        return {
            # 聊天模式
            ("click:input",): ["input:message"],
            ("input:message",): ["click:send"],
            ("click:send",): ["input:message"],
            
            # 模型选择模式
            ("click:model",): ["select:model_dropdown"],
            ("select:model_dropdown",): ["click:model_option"],
            
            # 设置模式
            ("click:settings",): ["click:settings_tab"],
            ("click:settings_tab",): ["click:save"],
        }
    
    def _normalize_action(self, action: str) -> str:
        """标准化动作"""
        normalized = action
        for pattern, replacement in self.ACTION_PATTERNS:
            normalized = re.sub(pattern, replacement, normalized)
        return normalized
    
    def _sequence_to_features(self, sequence: List[str]) -> List[str]:
        """将序列转换为特征"""
        features = []
        for action in sequence:
            normalized = self._normalize_action(action)
            features.append(normalized)
            
            # 添加 n-gram 特征
            parts = normalized.split(":")
            if len(parts) >= 2:
                features.append(f"{parts[0]}:{parts[1]}")
        
        return features
    
    def _calculate_tf(self, features: List[str]) -> Dict[str, float]:
        """计算 TF (词频)"""
        tf = defaultdict(float)
        if not features:
            return dict(tf)
        
        for feature in features:
            tf[feature] += 1.0
        
        # 归一化
        max_freq = max(tf.values())
        if max_freq > 0:
            for feature in tf:
                tf[feature] /= max_freq
        
        return dict(tf)
    
    def _get_idf(self, feature: str) -> float:
        """获取 IDF 分数"""
        if self.model and feature in self.model.idf_scores:
            return self.model.idf_scores[feature]
        
        # 默认 IDF（假设在所有文档中出现）
        return 1.0
    
    def _calculate_tfidf(self, features: List[str]) -> Dict[str, float]:
        """计算 TF-IDF"""
        tf = self._calculate_tf(features)
        tfidf = {}
        
        for feature, tf_score in tf.items():
            idf_score = self._get_idf(feature)
            tfidf[feature] = tf_score * idf_score
        
        return tfidf
    
    def _get_transition_prediction(
        self, 
        sequence: List[str]
    ) -> Optional[Tuple[str, float]]:
        """基于转移概率预测"""
        if not sequence:
            return None
        
        # 使用最近的动作作为上下文
        last_action = self._normalize_action(sequence[-1])
        
        # 从模型获取转移概率
        if self.model and last_action in self.model.transition_probs:
            transitions = self.model.transition_probs[last_action]
            if transitions:
                total = sum(transitions.values())
                if total > 0:
                    # 取最可能的下一个动作
                    best_action = max(transitions.items(), key=lambda x: x[1])
                    confidence = best_action[1] / total
                    return best_action[0], min(confidence, 1.0)
        
        # 使用默认模式
        for pattern, predictions in self._default_patterns.items():
            if last_action in pattern:
                return predictions[0], 0.6
        
        return None
    
    def _get_sequence_pattern_prediction(
        self,
        sequence: List[str]
    ) -> Optional[Tuple[str, float]]:
        """基于序列模式预测"""
        if len(sequence) < 2:
            return None
        
        # 查找匹配的模式
        for pattern_length in [3, 2]:
            if len(sequence) < pattern_length:
                continue
            
            pattern_key = tuple(sequence[-pattern_length:])
            
            if self.model and pattern_key in self.model.sequence_patterns:
                next_actions = self.model.sequence_patterns[pattern_key]
                if next_actions:
                    return next_actions[0], 0.75
        
        return None
    
    def predict(self, sequence: List[str]) -> PredictionResult:
        """
        预测下一步操作
        
        Args:
            sequence: 操作序列
            
        Returns:
            PredictionResult: 预测结果
        """
        if not sequence:
            return PredictionResult(
                predicted_action="",
                confidence=0.0,
                source="empty",
                reason="空序列",
            )
        
        with self._lock:
            # 方法1: 序列模式匹配
            pattern_result = self._get_sequence_pattern_prediction(sequence)
            if pattern_result:
                return PredictionResult(
                    predicted_action=pattern_result[0],
                    confidence=pattern_result[1],
                    source="pattern",
                    reason="匹配历史序列模式",
                    alternatives=self._get_alternatives(sequence),
                )
            
            # 方法2: 转移概率
            transition_result = self._get_transition_prediction(sequence)
            if transition_result:
                return PredictionResult(
                    predicted_action=transition_result[0],
                    confidence=transition_result[1],
                    source="tfidf",
                    reason="基于动作转移概率",
                    alternatives=self._get_alternatives(sequence),
                )
            
            # 方法3: 动作频率
            if self.model and self.model.action_frequency:
                most_common = self.model.action_frequency.most_common(1)
                if most_common:
                    return PredictionResult(
                        predicted_action=most_common[0][0],
                        confidence=0.3,
                        source="frequency",
                        reason="基于动作频率",
                        alternatives=[],
                    )
            
            # Fallback: 返回空
            return PredictionResult(
                predicted_action="",
                confidence=0.0,
                source="fallback",
                reason="无匹配模式",
                alternatives=[],
            )
    
    def _get_alternatives(self, sequence: List[str]) -> List[Tuple[str, float]]:
        """获取备选预测"""
        if not sequence or not self.model:
            return []
        
        last_action = self._normalize_action(sequence[-1])
        
        if last_action in self.model.transition_probs:
            transitions = self.model.transition_probs[last_action]
            total = sum(transitions.values())
            
            if total > 0:
                alternatives = [
                    (action, count / total)
                    for action, count in sorted(transitions.items(), key=lambda x: -x[1])[1:4]
                ]
                return alternatives
        
        return []
    
    def train(
        self,
        sequences: List[List[str]],
        save_path: str = None,
    ) -> TrainedModel:
        """
        训练模型
        
        Args:
            sequences: 操作序列列表
            save_path: 模型保存路径
        """
        model = TrainedModel(
            vocabulary={},
            idf_scores={},
            transition_probs=defaultdict(lambda: defaultdict(int)),
            action_frequency=Counter(),
            sequence_patterns={},
        )
        
        # 统计所有特征
        all_features: List[str] = []
        feature_doc_freq: Dict[str, int] = defaultdict(int)
        
        for sequence in sequences:
            features = self._sequence_to_features(sequence)
            all_features.extend(features)
            
            # 文档频率
            for feature in set(features):
                feature_doc_freq[feature] += 1
        
        # 构建词表
        unique_features = list(set(all_features))
        model.vocabulary = {f: i for i, f in enumerate(unique_features)}
        
        # 计算 IDF
        n_documents = len(sequences) if sequences else 1
        for feature, df in feature_doc_freq.items():
            model.idf_scores[feature] = math.log(n_documents / (df + 1)) + 1
        
        # 统计转移概率
        for sequence in sequences:
            for i in range(len(sequence) - 1):
                current = self._normalize_action(sequence[i])
                next_action = self._normalize_action(sequence[i + 1])
                model.transition_probs[current][next_action] += 1
        
        # 统计动作频率
        model.action_frequency = Counter(all_features)
        
        # 提取序列模式
        for sequence in sequences:
            for length in [2, 3]:
                for i in range(len(sequence) - length):
                    pattern = tuple(sequence[i:i + length])
                    next_action = sequence[i + length] if i + length < len(sequence) else None
                    
                    if next_action:
                        if pattern not in model.sequence_patterns:
                            model.sequence_patterns[pattern] = []
                        model.sequence_patterns[pattern].append(next_action)
        
        # 保存模型
        if save_path:
            model.save(Path(save_path))
        
        self.model = model
        return model
    
    def incremental_update(
        self,
        sequence: List[str],
        next_action: str,
        success: bool = True,
    ):
        """增量更新模型"""
        with self._lock:
            # 更新转移概率
            if sequence:
                last_action = self._normalize_action(sequence[-1])
                next_normalized = self._normalize_action(next_action)
                
                if self.model:
                    self.model.transition_probs[last_action][next_normalized] += 1
                    self.model.action_frequency[next_normalized] += 1
                    
                    # 更新序列模式
                    pattern = tuple(sequence[-2:]) if len(sequence) >= 2 else tuple(sequence)
                    if pattern not in self.model.sequence_patterns:
                        self.model.sequence_patterns[pattern] = []
                    self.model.sequence_patterns[pattern].append(next_action)
                    
                    # 保存更新
                    if self.model_path:
                        self.model.save(self.model_path)


# =============================================================================
# 全局实例
# =============================================================================

_instance: Optional[TFIDFPredictor] = None
_instance_lock = threading.Lock()


def get_predictor(model_path: str = None) -> TFIDFPredictor:
    """获取全局预测器实例"""
    global _instance
    
    with _instance_lock:
        if _instance is None:
            _instance = TFIDFPredictor(model_path)
        return _instance


# =============================================================================
# 便捷函数
# =============================================================================

def predict_next(sequence: List[str]) -> PredictionResult:
    """
    快速预测下一步操作
    
    使用示例:
    ```python
    from client.src.business.ui_evolution import predict_next

    
    # 预测
    result = predict_next(["click:send", "input:message"])
    logger.info(f"建议: {result.predicted_action}, 置信度: {result.confidence}")
    ```
    """
    predictor = get_predictor()
    return predictor.predict(sequence)


def quick_predict(current_action: str) -> Tuple[str, float]:
    """
    快速预测（单动作）
    
    使用示例:
    ```python
    action, confidence = quick_predict("click:send")
    ```
    """
    result = predict_next([current_action])
    return result.predicted_action, result.confidence
