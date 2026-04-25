"""
test_evolution_integrator.py - 独立测试版本
"""

import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

print("=" * 60)
print("EvolutionConfigIntegrator 独立测试")
print("=" * 60)

# ============= 基础组件 (内联) =============

class MockLogger:
    def info(self, msg): print(f"[INFO] {msg}")
    def warning(self, msg): print(f"[WARN] {msg}")
    def debug(self, msg): pass

logger = MockLogger()

def compute_optimal_config(depth: int) -> Dict[str, Any]:
    depth = max(1, min(10, depth))
    return {
        'depth': depth,
        'timeout': int(30 * (1 + 0.3 * depth ** 0.7)),
        'max_retries': max(1, 2 + int(math.log2(depth))),
        'max_tokens': int(2048 * depth ** 1.5),
        'max_workers': max(1, 2 * int(math.sqrt(depth))),
        'memory_limit': depth * 128,
        'context_window': 4096 * depth,
    }

# ============= DepthHintLearner (简化版) =============

@dataclass
class DepthHint:
    task_type: str
    recommended_depth: int
    confidence: float
    sample_count: int
    avg_score: float
    success_rate: float

DEFAULT_HINTS = {
    'ping': 1, 'list': 1, 'quick_fix': 2, 'fix': 3, 'code_fix': 3,
    'search': 4, 'refactor': 5, 'generate': 5, 'test': 5,
    'auto_fix': 7, 'architecture': 8, 'evolve': 9, 'autonomous': 10, 'general': 5,
}

class DepthHintLearner:
    def __init__(self):
        self._records: Dict[str, List[Tuple[int, float]]] = {}
        self._hints: Dict[str, DepthHint] = {
            k: DepthHint(k, v, 0.3, 0, 0.0, 0.0) for k, v in DEFAULT_HINTS.items()
        }
    
    def record(self, task_type: str, depth: int, score: float) -> DepthHint:
        if task_type not in self._records:
            self._records[task_type] = []
        self._records[task_type].append((depth, score))
        
        records = self._records[task_type]
        if len(records) < 2:
            return self._hints.get(task_type, self._hints['general'])
        
        # 找最佳 depth
        depth_scores: Dict[int, float] = {}
        for d, s in records:
            if d not in depth_scores:
                depth_scores[d] = []
            depth_scores[d].append(s)
        
        best_depth = max(depth_scores.keys(), key=lambda d: sum(depth_scores[d])/len(depth_scores[d]))
        avg_score = sum(s for _, s in records) / len(records)
        
        success_rate = sum(1 for d, s in records if s >= 0.8) / len(records)
        self._hints[task_type] = DepthHint(
            task_type, best_depth, min(1.0, len(records)/10),
            len(records), avg_score, success_rate
        )
        return self._hints[task_type]
    
    def get_hint(self, task_type: str) -> DepthHint:
        return self._hints.get(task_type, self._hints['general'])

_learner = DepthHintLearner()

# ============= EvolutionDepthOptimizer (简化版) =============

class AdjustmentStrategy(Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"

@dataclass
class DepthHistory:
    depth: int
    score: float
    task_type: str

class EvolutionDepthOptimizer:
    def __init__(self, initial_depth: int = 5, strategy: AdjustmentStrategy = AdjustmentStrategy.MODERATE):
        self.current_depth = initial_depth
        self.strategy = strategy
        self.history: List[DepthHistory] = []
    
    def record_evaluation(self, score: float, task_type: str = "") -> DepthHistory:
        record = DepthHistory(self.current_depth, score, task_type)
        self.history.append(record)
        return record
    
    def analyze_and_adjust(self):
        if len(self.history) < 3:
            return self.current_depth, 0, "样本不足"
        
        recent = self.history[-3:]
        avg_score = sum(h.score for h in recent) / 3
        
        step = {'conservative': 1, 'moderate': 2, 'aggressive': 3}.get(self.strategy.value, 2)
        
        if avg_score < 0.6:
            new_depth = min(10, self.current_depth + step)
            adj = new_depth - self.current_depth
            self.current_depth = new_depth
            return new_depth, adj, f"低分 {avg_score:.2f} < 0.6，增加 depth"
        elif avg_score > 0.85:
            new_depth = max(1, self.current_depth - step)
            adj = new_depth - self.current_depth
            self.current_depth = new_depth
            return new_depth, adj, f"高分 {avg_score:.2f} > 0.85，尝试降低"
        else:
            return self.current_depth, 0, f"分数正常，保持 depth={self.current_depth}"
    
    def get_optimal_config(self) -> Dict[str, Any]:
        return compute_optimal_config(self.current_depth)

_optimizer = EvolutionDepthOptimizer(5)

# ============= TaskTypeInferrer =============

class TaskTypeInferrer:
    PATTERNS = {
        'ping': [r'^ping$', r'^pong$'],
        'list': [r'^ls$', r'^dir$'],
        'fix': [r'^fix$', r'bug', r'error'],
        'code_fix': [r'code.*fix', r'fix.*code'],
        'search': [r'grep', r'find', r'search'],
        'refactor': [r'refactor', r'重构'],
        'architecture': [r'architect', r'架构'],
        'test': [r'^test', r'测试'],
        'generate': [r'generat', r'写.*代码'],
        'auto_fix': [r'auto.*fix', r'自动.*修复'],
        'evolve': [r'evol', r'进化'],
    }
    
    @classmethod
    def infer(cls, intent: str) -> str:
        for task_type, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, intent.lower()):
                    return task_type
        return 'general'

# ============= EvolutionIntegrationResult =============

@dataclass
class EvolutionIntegrationResult:
    task_type: str
    depth: int
    config: Dict[str, Any]
    confidence: float
    source: str

# ============= 测试 =============

print("\n[Test 1] 意图推断")
test_intents = ["修复这个bug", "重构函数", "设计架构", "写测试", "生成代码", "ping"]
for intent in test_intents:
    task_type = TaskTypeInferrer.infer(intent)
    print(f"  '{intent}' -> {task_type}")

print("\n[Test 2] 配置获取")
config = compute_optimal_config(5)
print(f"  depth=5: timeout={config['timeout']}s, max_tokens={config['max_tokens']}")

print("\n[Test 3] 学习闭环")
learn_data = [
    ('code_fix', 3, 0.5), ('code_fix', 4, 0.6), ('code_fix', 5, 0.8),
    ('refactor', 5, 0.7), ('refactor', 6, 0.85), ('refactor', 7, 0.9),
]
for task_type, depth, score in learn_data:
    _learner.record(task_type, depth, score)
    _optimizer.record_evaluation(score, task_type)

print("\n[Test 4] 分析调整")
for _ in range(3):
    new_depth, adj, reason = _optimizer.analyze_and_adjust()
    if adj != 0:
        print(f"  depth -> {new_depth}: {reason}")
    else:
        print(f"  保持 depth={new_depth}")

print("\n[Test 5] 预测")
for intent in ["修复bug", "重构代码", "架构设计"]:
    task_type = TaskTypeInferrer.infer(intent)
    hint = _learner.get_hint(task_type)
    print(f"  '{intent}' -> {task_type} -> depth={hint.recommended_depth}")

print("\n" + "=" * 60)
print("测试完成!")
print("=" * 60)
