"""
depth_hint_learner.py - 任务类型→Depth 映射学习器
=====================================================

从历史数据中学习任务类型到最优 depth 的映射关系。

功能：
1. 贝叶斯更新 depth 建议
2. 成功率追踪
3. 任务类型聚类
4. 自适应学习

Author: Hermes Desktop Team
"""

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# ============= Mock logger =============

class MockLogger:
    def info(self, msg): print(f"[INFO] {msg}")
    def warning(self, msg): print(f"[WARN] {msg}")
    def debug(self, msg): pass

logger = MockLogger()


# ============= 数据类 =============

@dataclass
class TaskTypeRecord:
    """任务类型记录"""
    task_type: str
    depth: int
    score: float
    timestamp: datetime = field(default_factory=datetime.now)
    execution_time: float = 0.0


@dataclass
class DepthHint:
    """Depth 提示"""
    task_type: str
    recommended_depth: int
    confidence: float  # 0-1
    sample_count: int
    avg_score: float
    success_rate: float
    last_updated: datetime = field(default_factory=datetime.now)


# ============= 核心学习器 =============

class DepthHintLearner:
    """
    任务类型 → Depth 映射学习器
    
    使用贝叶斯更新来学习每个任务类型的最优 depth。
    """
    
    # 默认深度建议
    DEFAULT_HINTS = {
        'ping': 1, 'list': 1, 'ls': 1, 'dir': 1,
        'quick_fix': 2, 'quickfix': 2,
        'fix': 3, 'bug': 3, 'error': 3, 'hotfix': 3,
        'code_fix': 3, 'codefix': 3,
        'search': 4, 'grep': 4, 'find': 4,
        'refactor': 5, '重构': 5, '优化': 5, 'optimize': 5,
        'generate': 5, 'generate_code': 5, '写代码': 5,
        'create': 5, '创建': 5,
        'test': 5, '测试': 5,
        'auto_fix': 7, 'autofix': 7, '自动修复': 7,
        'architecture': 8, '设计': 8, '架构': 8,
        'evolve': 9, '进化': 9, '自优化': 9,
        'autonomous': 10, '自动驾驶': 10,
        'general': 5, 'default': 5,
    }
    
    # 阈值
    SUCCESS_THRESHOLD = 0.8   # 成功率 > 80% 认为成功
    LOW_SUCCESS_THRESHOLD = 0.6  # 成功率 < 60% 需要调整
    HIGH_CONFIDENCE = 0.8     # 样本数 > 10 认为高置信度
    
    def __init__(
        self,
        learning_rate: float = 0.1,
        window_size: int = 20,
        min_samples: int = 3
    ):
        """
        初始化学习器
        
        Args:
            learning_rate: 学习率 (贝叶斯更新的权重)
            window_size: 滑动窗口大小
            min_samples: 最小样本数
        """
        self.learning_rate = learning_rate
        self.window_size = window_size
        self.min_samples = min_samples
        
        # 任务类型 → 记录列表
        self._records: Dict[str, List[TaskTypeRecord]] = defaultdict(list)
        
        # 任务类型 → DepthHint
        self._hints: Dict[str, DepthHint] = {}
        
        # 初始化默认提示
        for task_type, depth in self.DEFAULT_HINTS.items():
            self._hints[task_type] = DepthHint(
                task_type=task_type,
                recommended_depth=depth,
                confidence=0.3,  # 低置信度，等待学习
                sample_count=0,
                avg_score=0.0,
                success_rate=0.0
            )
        
        logger.info(f"DepthHintLearner 初始化 (learning_rate={learning_rate})")
    
    def record(
        self,
        task_type: str,
        depth: int,
        score: float,
        execution_time: float = 0.0
    ) -> DepthHint:
        """
        记录一次执行结果
        
        Args:
            task_type: 任务类型
            depth: 使用的 depth
            score: 评估分数 (0-1)
            execution_time: 执行时间
            
        Returns:
            DepthHint: 更新后的提示
        """
        # 创建记录
        record = TaskTypeRecord(
            task_type=task_type,
            depth=depth,
            score=score,
            execution_time=execution_time
        )
        
        # 添加到记录列表
        self._records[task_type].append(record)
        
        # 保持窗口大小
        if len(self._records[task_type]) > self.window_size:
            self._records[task_type] = self._records[task_type][-self.window_size:]
        
        # 更新提示
        hint = self._update_hint(task_type)
        
        logger.debug(f"记录: {task_type} depth={depth} score={score:.3f} → recommended={hint.recommended_depth}")
        
        return hint
    
    def _update_hint(self, task_type: str) -> DepthHint:
        """更新任务类型的提示"""
        records = self._records[task_type]
        
        if len(records) < self.min_samples:
            # 样本不足，返回默认
            return self._hints.get(task_type, self._hints['general'])
        
        # 计算统计
        scores = [r.score for r in records]
        depths = [r.depth for r in records]
        
        avg_score = sum(scores) / len(scores)
        success_count = sum(1 for s in scores if s >= self.SUCCESS_THRESHOLD)
        success_rate = success_count / len(scores)
        
        # 找出最佳 depth
        depth_scores: Dict[int, List[float]] = defaultdict(list)
        for r in records:
            depth_scores[r.depth].append(r.score)
        
        best_depth = max(
            depth_scores.keys(),
            key=lambda d: sum(depth_scores[d]) / len(depth_scores[d])
        )
        
        # 贝叶斯更新
        current_hint = self._hints.get(task_type)
        if current_hint:
            # 混合当前建议和新观察
            alpha = self.learning_rate  # 学习率
            new_depth = int(current_hint.recommended_depth * (1 - alpha) + best_depth * alpha)
            new_depth = max(1, min(10, new_depth))
            
            # 更新置信度
            sample_count = len(records)
            new_confidence = min(1.0, sample_count / 20)  # 20个样本达到高置信度
        else:
            new_depth = best_depth
            new_confidence = min(1.0, len(records) / 20)
        
        # 创建新提示
        hint = DepthHint(
            task_type=task_type,
            recommended_depth=new_depth,
            confidence=new_confidence,
            sample_count=len(records),
            avg_score=avg_score,
            success_rate=success_rate,
            last_updated=datetime.now()
        )
        
        self._hints[task_type] = hint
        return hint
    
    def get_hint(self, task_type: str) -> DepthHint:
        """
        获取任务类型的 depth 建议
        
        Args:
            task_type: 任务类型
            
        Returns:
            DepthHint: 建议
        """
        # 标准化任务类型
        normalized = self._normalize_task_type(task_type)
        
        # 查找最接近的任务类型
        hint = self._hints.get(normalized)
        if hint:
            return hint
        
        # 尝试部分匹配
        for key, h in self._hints.items():
            if key in normalized or normalized in key:
                logger.info(f"部分匹配: {task_type} → {key}")
                return h
        
        # 返回默认
        return self._hints['general']
    
    def _normalize_task_type(self, task_type: str) -> str:
        """标准化任务类型"""
        return task_type.lower().replace('-', '_').replace(' ', '_')
    
    def get_optimal_depth(self, task_type: str) -> int:
        """
        获取任务的最优 depth
        
        Args:
            task_type: 任务类型
            
        Returns:
            int: 最优 depth
        """
        hint = self.get_hint(task_type)
        return hint.recommended_depth
    
    def batch_learn(self, records: List[Tuple[str, int, float]]) -> Dict[str, DepthHint]:
        """
        批量学习
        
        Args:
            records: [(task_type, depth, score), ...]
            
        Returns:
            Dict[str, DepthHint]: 所有更新的提示
        """
        for task_type, depth, score in records:
            self.record(task_type, depth, score)
        
        return {k: v for k, v in self._hints.items() if v.sample_count >= self.min_samples}
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_records = sum(len(r) for r in self._records.values())
        learned_types = sum(1 for h in self._hints.values() if h.sample_count >= self.min_samples)
        
        return {
            'total_records': total_records,
            'learned_types': learned_types,
            'total_types': len(self._hints),
            'high_confidence_count': sum(1 for h in self._hints.values() if h.confidence >= self.HIGH_CONFIDENCE),
        }
    
    def export_hints(self) -> Dict[str, Dict[str, Any]]:
        """导出所有提示"""
        return {
            task_type: {
                'depth': hint.recommended_depth,
                'confidence': hint.confidence,
                'sample_count': hint.sample_count,
                'avg_score': hint.avg_score,
                'success_rate': hint.success_rate,
            }
            for task_type, hint in self._hints.items()
            if hint.sample_count > 0
        }
    
    def import_hints(self, hints: Dict[str, Dict[str, Any]]):
        """导入提示"""
        for task_type, data in hints.items():
            self._hints[task_type] = DepthHint(
                task_type=task_type,
                recommended_depth=data['depth'],
                confidence=data.get('confidence', 0.5),
                sample_count=data.get('sample_count', 0),
                avg_score=data.get('avg_score', 0.0),
                success_rate=data.get('success_rate', 0.0)
            )


# ============= 便捷函数 =============

_learner_instance: Optional[DepthHintLearner] = None


def get_global_learner() -> DepthHintLearner:
    """获取全局学习器实例"""
    global _learner_instance
    if _learner_instance is None:
        _learner_instance = DepthHintLearner()
    return _learner_instance


def learn_task(task_type: str, depth: int, score: float) -> DepthHint:
    """快捷学习函数"""
    return get_global_learner().record(task_type, depth, score)


def get_optimal_depth(task_type: str) -> int:
    """快捷获取最优 depth"""
    return get_global_learner().get_optimal_depth(task_type)


# ============= 测试 =============

if __name__ == "__main__":
    print("=" * 60)
    print("DepthHintLearner 测试")
    print("=" * 60)
    
    # 创建学习器
    learner = DepthHintLearner(learning_rate=0.2, min_samples=2)
    
    # 模拟数据
    test_data = [
        # code_fix 类型 - 不同 depth 的表现
        ('code_fix', 3, 0.5),
        ('code_fix', 4, 0.6),
        ('code_fix', 5, 0.75),
        ('code_fix', 5, 0.8),
        ('code_fix', 5, 0.85),
        ('code_fix', 4, 0.7),
        ('code_fix', 5, 0.9),
        
        # refactor 类型
        ('refactor', 5, 0.7),
        ('refactor', 6, 0.8),
        ('refactor', 7, 0.85),
        ('refactor', 7, 0.9),
        ('refactor', 6, 0.82),
        
        # architecture 类型
        ('architecture', 8, 0.6),
        ('architecture', 9, 0.75),
        ('architecture', 9, 0.8),
    ]
    
    print("\n[批量学习]")
    for task_type, depth, score in test_data:
        learner.record(task_type, depth, score)
    
    # 显示结果
    print("\n[学习结果]")
    test_types = ['code_fix', 'refactor', 'architecture', 'auto_fix', 'general']
    for task_type in test_types:
        hint = learner.get_hint(task_type)
        print(f"\n  {task_type}:")
        print(f"    推荐 depth: {hint.recommended_depth}")
        print(f"    置信度: {hint.confidence:.2f}")
        print(f"    样本数: {hint.sample_count}")
        print(f"    平均分: {hint.avg_score:.3f}")
        print(f"    成功率: {hint.success_rate:.2%}")
    
    # 统计
    print("\n[统计]")
    stats = learner.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # 导出测试
    print("\n[导出测试]")
    hints = learner.export_hints()
    print(f"  导出 {len(hints)} 个提示")
    
    # 新任务测试
    print("\n[新任务测试]")
    new_hint = learner.get_hint('new_task_type')
    print(f"  未知任务 → depth={new_hint.recommended_depth} (默认)")
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)
