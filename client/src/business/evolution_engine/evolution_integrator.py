"""
evolution_integrator.py - Evolution 集成入口
=============================================

整合 EvolutionDepthOptimizer 和 DepthHintLearner，提供统一的 Evolution + Optimal Config 接口。

功能：
1. 统一的配置获取接口
2. 评估→学习→调整 闭环
3. 任务类型自动推断
4. 批量评估支持

Author: Hermes Desktop Team
"""

import math
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# 导入组件
from client.src.business.evolution_engine.evolution_depth_optimizer import (
    EvolutionDepthOptimizer,
    DepthHistory,
    OptimizationResult,
    AdjustmentStrategy,
    create_optimizer,
)
from client.src.business.evolution_engine.depth_hint_learner import (
    DepthHintLearner,
    DepthHint,
    get_global_learner,
    learn_task,
    get_optimal_depth,
)

# ============= Mock logger =============

class MockLogger:
    def info(self, msg): print(f"[INFO] {msg}")
    def warning(self, msg): print(f"[WARN] {msg}")
    def debug(self, msg): pass

logger = MockLogger()


# ============= Fallback 配置 =============

def compute_optimal_config(depth: int) -> Dict[str, Any]:
    """Fallback 配置计算"""
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


# ============= 任务类型推断 =============

class TaskTypeInferrer:
    """任务类型推断器"""
    
    # 关键词模式
    PATTERNS = {
        'ping': [r'^ping$', r'^pong$', r'^echo'],
        'list': [r'^ls$', r'^dir$', r'^list'],
        'quick_fix': [r'quick', r'fast', r'hot'],
        'fix': [r'^fix$', r'^bug', r'error', r'crash', r'broken'],
        'code_fix': [r'code.*fix', r'fix.*code', r'修复.*代码'],
        'search': [r'^grep', r'^find', r'search', r'查找', r'搜索'],
        'refactor': [r'refactor', r'重构', r'reorganize', r'重新组织'],
        'optimize': [r'optimi', r'优化', r'improve'],
        'generate': [r'generat', r'写.*代码', r'创建.*代码', r'generate.*code'],
        'test': [r'^test', r'测试', r'unit'],
        'auto_fix': [r'auto.*fix', r'自动.*修复', r'self.*repair'],
        'architecture': [r'architect', r'架构', r'design.*pattern'],
        'evolve': [r'evol', r'进化', r'self.*improv'],
        'autonomous': [r'auto.*pilot', r'自动驾驶', r'full.*auto'],
    }
    
    @classmethod
    def infer(cls, intent: str) -> str:
        """
        从意图推断任务类型
        
        Args:
            intent: 用户意图描述
            
        Returns:
            str: 任务类型
        """
        intent_lower = intent.lower()
        
        # 按优先级匹配
        for task_type, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, intent_lower, re.IGNORECASE):
                    logger.debug(f"推断: '{intent}' → {task_type}")
                    return task_type
        
        logger.debug(f"推断: '{intent}' → general")
        return 'general'
    
    @classmethod
    def infer_batch(cls, intents: List[str]) -> List[str]:
        """批量推断"""
        return [cls.infer(i) for i in intents]


# ============= 集成器 =============

@dataclass
class EvolutionIntegrationResult:
    """集成结果"""
    task_type: str
    depth: int
    config: Dict[str, Any]
    confidence: float
    source: str  # 'optimizer' / 'learner' / 'default'
    adjustment_info: Optional[str] = None


class EvolutionConfigIntegrator:
    """
    Evolution 配置集成器
    
    整合深度优化器和学习器，提供统一的配置接口。
    """
    
    def __init__(
        self,
        initial_depth: int = 5,
        strategy: AdjustmentStrategy = AdjustmentStrategy.MODERATE,
        enable_learning: bool = True
    ):
        """
        初始化集成器
        
        Args:
            initial_depth: 初始 depth
            strategy: 调整策略
            enable_learning: 是否启用学习
        """
        # 核心组件
        self.optimizer = create_optimizer(initial_depth, strategy.value)
        self.learner = get_global_learner() if enable_learning else None
        self.inferrer = TaskTypeInferrer()
        
        # 配置缓存
        self._config_cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"EvolutionConfigIntegrator 初始化 (depth={initial_depth}, learning={enable_learning})")
    
    def get_config(self, task_type: str = "general") -> EvolutionIntegrationResult:
        """
        获取任务的最优配置
        
        Args:
            task_type: 任务类型
            
        Returns:
            EvolutionIntegrationResult: 配置结果
        """
        # 1. 从学习器获取建议
        if self.learner:
            learner_hint = self.learner.get_hint(task_type)
            if learner_hint.sample_count >= self.learner.min_samples:
                config = compute_optimal_config(learner_hint.recommended_depth)
                return EvolutionIntegrationResult(
                    task_type=task_type,
                    depth=learner_hint.recommended_depth,
                    config=config,
                    confidence=learner_hint.confidence,
                    source='learner'
                )
        
        # 2. 从优化器获取配置
        config = self.optimizer.get_optimal_config()
        optimizer_hint = self.optimizer.get_optimal_config()
        
        return EvolutionIntegrationResult(
            task_type=task_type,
            depth=config['depth'],
            config=config,
            confidence=0.5,
            source='optimizer'
        )
    
    def get_config_for_intent(self, intent: str) -> EvolutionIntegrationResult:
        """
        从意图获取配置
        
        Args:
            intent: 用户意图
            
        Returns:
            EvolutionIntegrationResult: 配置结果
        """
        task_type = self.inferrer.infer(intent)
        return self.get_config(task_type)
    
    def record_and_adjust(
        self,
        task_type: str,
        score: float,
        execution_time: float = 0.0
    ) -> Tuple[EvolutionIntegrationResult, OptimizationResult]:
        """
        记录评估结果并自动调整
        
        Args:
            task_type: 任务类型
            score: 评估分数
            execution_time: 执行时间
            
        Returns:
            (配置结果, 优化结果)
        """
        # 1. 记录到学习器
        if self.learner:
            self.learner.record(task_type, self.optimizer.current_depth, score, execution_time)
        
        # 2. 记录到优化器
        self.optimizer.record_evaluation(score, task_type)
        
        # 3. 分析并调整
        optimization_result = self.optimizer.analyze_and_adjust()
        
        # 4. 获取新配置
        config_result = self.get_config(task_type)
        
        # 添加调整信息
        if optimization_result.adjustment != 0:
            config_result.adjustment_info = optimization_result.reason
        
        return config_result, optimization_result
    
    def batch_process(
        self,
        tasks: List[Tuple[str, str, float]]
    ) -> List[Tuple[EvolutionIntegrationResult, OptimizationResult]]:
        """
        批量处理任务
        
        Args:
            tasks: [(intent, task_type, score), ...]
            
        Returns:
            List[(配置结果, 优化结果)]
        """
        results = []
        for intent, task_type, score in tasks:
            config_result, opt_result = self.record_and_adjust(task_type, score)
            results.append((config_result, opt_result))
        
        return results
    
    def predict_depth(self, intent: str) -> int:
        """
        预测任务的最优 depth
        
        Args:
            intent: 用户意图
            
        Returns:
            int: 预测的 depth
        """
        task_type = self.inferrer.infer(intent)
        
        # 优先使用学习器的预测
        if self.learner:
            learner_hint = self.learner.get_hint(task_type)
            if learner_hint.sample_count >= self.learner.min_samples:
                return learner_hint.recommended_depth
        
        # 使用优化器的预测
        return self.optimizer.predict_best_depth(task_type)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            'optimizer': self.optimizer.get_statistics(),
            'learner': self.learner.get_statistics() if self.learner else None,
            'current_config': self.optimizer.get_optimal_config(),
        }
        return stats


# ============= 全局实例 =============

_integrator_instance: Optional[EvolutionConfigIntegrator] = None


def get_integrator() -> EvolutionConfigIntegrator:
    """获取全局集成器实例"""
    global _integrator_instance
    if _integrator_instance is None:
        _integrator_instance = EvolutionConfigIntegrator()
    return _integrator_instance


# ============= 快捷函数 =============

def get_evolution_config(task_type: str = "general") -> Dict[str, Any]:
    """快捷获取 Evolution 配置"""
    return get_integrator().get_config(task_type).config


def get_config_for_intent(intent: str) -> Dict[str, Any]:
    """快捷从意图获取配置"""
    return get_integrator().get_config_for_intent(intent).config


# ============= 测试 =============

if __name__ == "__main__":
    print("=" * 60)
    print("EvolutionConfigIntegrator 测试")
    print("=" * 60)
    
    # 创建集成器
    integrator = EvolutionConfigIntegrator(initial_depth=5, enable_learning=True)
    
    # 测试 1: 意图推断
    print("\n[Test 1] 意图推断")
    test_intents = [
        "修复这个bug",
        "重构这个函数",
        "设计一个新的架构",
        "写一个测试用例",
        "生成API代码",
        "ping服务器",
    ]
    for intent in test_intents:
        task_type = TaskTypeInferrer.infer(intent)
        print(f"  '{intent}' → {task_type}")
    
    # 测试 2: 配置获取
    print("\n[Test 2] 配置获取")
    result = integrator.get_config('refactor')
    print(f"  task_type: {result.task_type}")
    print(f"  depth: {result.depth}")
    print(f"  source: {result.source}")
    print(f"  timeout: {result.config['timeout']}s")
    
    # 测试 3: 意图→配置
    print("\n[Test 3] 意图→配置")
    intents = ["修复bug", "重构代码", "设计架构"]
    for intent in intents:
        result = integrator.get_config_for_intent(intent)
        print(f"  '{intent}' → depth={result.depth}, timeout={result.config['timeout']}s")
    
    # 测试 4: 学习闭环
    print("\n[Test 4] 学习闭环")
    learn_data = [
        ('code_fix', 3, 0.5),
        ('code_fix', 4, 0.6),
        ('code_fix', 5, 0.8),
        ('refactor', 5, 0.7),
        ('refactor', 6, 0.85),
        ('refactor', 7, 0.9),
    ]
    
    for task_type, depth, score in learn_data:
        config_result, opt_result = integrator.record_and_adjust(task_type, score)
        if opt_result.adjustment != 0:
            print(f"  {task_type}: depth {depth}→{config_result.depth} ({opt_result.reason})")
    
    # 测试 5: 预测
    print("\n[Test 5] 预测 depth")
    for intent in ["修复bug", "重构代码", "架构设计"]:
        depth = integrator.predict_depth(intent)
        print(f"  '{intent}' → depth={depth}")
    
    # 统计
    print("\n[统计]")
    stats = integrator.get_statistics()
    print(f"  optimizer: {stats['optimizer']['current_depth']}")
    print(f"  learner: {stats['learner']['learned_types']} learned")
    print(f"  config: timeout={stats['current_config']['timeout']}s")
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)
