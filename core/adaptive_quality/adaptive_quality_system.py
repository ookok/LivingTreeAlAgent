# -*- coding: utf-8 -*-
"""
Adaptive Quality Assurance System - 自适应质量保障系统
=====================================================

动态质量感知 + 智能模型升级 + 成本优化

核心理念：
1. 质量优先 - 确保最终输出质量
2. 成本优化 - 尽量使用低成本方案
3. 自适应 - 根据实际情况动态调整
4. 可扩展 - 支持不断加入新模型

Author: LivingTreeAI Agent
Date: 2026-04-24
"""

from __future__ import annotations

import time
from typing import Optional, List, Dict, Any, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import threading


# ═══════════════════════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ModelConfig:
    """模型配置"""
    level: int
    name: str
    endpoint: str
    api_key: Optional[str] = None
    max_tokens: int = 8192
    avg_latency_ms: float = 3000
    cost_per_1k: float = 0.0
    capabilities: List[str] = field(default_factory=list)
    is_local: bool = True


@dataclass
class QualityBudget:
    """质量预算"""
    max_attempts: int = 3
    max_latency_ms: float = 15000
    max_cost: float = 1.0
    quality_threshold: float = 0.6


@dataclass
class ExecutionResult:
    """执行结果"""
    response: str
    quality_score: float
    quality_level: Any  # QualityLevel
    model_level: int
    latency_ms: float
    cost: float
    upgrade_attempts: int
    success: bool
    quality_report: Any = None
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# 自适应质量保障系统
# ═══════════════════════════════════════════════════════════════════════════════

class AdaptiveQualitySystem:
    """
    自适应质量保障系统
    
    使用方式：
    ```python
    from core.adaptive_quality import AdaptiveQualitySystem
    
    # 初始化
    aqs = AdaptiveQualitySystem()
    
    # 执行任务（自动质量保障）
    result = await aqs.execute(
        query="解释量子计算原理",
        task_func=lambda level: ollama.chat(prompts, model=models[level])
    )
    
    logger.info(f"质量评分: {result.quality_score}")
    logger.info(f"使用模型: L{result.model_level}")
    logger.info(f"响应: {result.response}")
    ```
    """

    # 默认模型配置
    DEFAULT_MODELS = {
        0: ModelConfig(
            level=0, name="qwen2.5:0.5b",
            endpoint="http://localhost:11434",
            capabilities=["greeting", "simple_qa", "fast"],
            is_local=True
        ),
        1: ModelConfig(
            level=1, name="qwen2.5:1.5b",
            endpoint="http://localhost:11434",
            capabilities=["general", "reasoning", "search"],
            is_local=True
        ),
        2: ModelConfig(
            level=2, name="qwen3.5:2b",
            endpoint="http://localhost:11434",
            capabilities=["code", "analysis"],
            is_local=True
        ),
        3: ModelConfig(
            level=3, name="qwen3.5:4b",
            endpoint="http://localhost:11434",
            capabilities=["deep_reasoning", "complex"],
            is_local=True
        ),
        4: ModelConfig(
            level=4, name="qwen3.5:9b",
            endpoint="http://localhost:11434",
            capabilities=["expert", "creative", "critical"],
            is_local=True
        ),
    }

    def __init__(
        self,
        models: Optional[Dict[int, ModelConfig]] = None,
        budget: Optional[QualityBudget] = None,
        auto_register: bool = True,
    ):
        """
        初始化系统
        
        Args:
            models: 模型配置字典 {level: ModelConfig}
            budget: 质量预算
            auto_register: 是否自动注册到 ExpertLearning
        """
        self.models = models or self.DEFAULT_MODELS.copy()
        self.budget = budget or QualityBudget()
        
        # 导入并初始化组件
        try:
            from .enhanced_evaluator import EnhancedQualityEvaluator, QualityLevel
            from .upgrade_engine import UpgradeDecisionEngine, UpgradeStrategy
        except ImportError:
            from enhanced_evaluator import EnhancedQualityEvaluator, QualityLevel
            from upgrade_engine import UpgradeDecisionEngine, UpgradeStrategy
        
        self._evaluator = EnhancedQualityEvaluator()
        self._upgrade_engine = UpgradeDecisionEngine()
        
        # 统计
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_upgrades": 0,
            "level_distribution": {i: 0 for i in range(5)},
        }
        self._stats_lock = threading.Lock()
        
        # 回调
        self._on_quality_check: Optional[Callable] = None
        self._on_upgrade: Optional[Callable] = None
        
        # 自动注册到 ExpertLearning
        if auto_register:
            self._register_to_expert_learning()
        
        logger.info(f"[AdaptiveQualitySystem] 已初始化，支持 {len(self.models)} 个模型级别")

    def _register_to_expert_learning(self):
        """注册到 ExpertLearning 系统"""
        try:
            from core.expert_learning.auto_model_selector import AutoModelSelector
            
            selector = AutoModelSelector()
            for level, config in self.models.items():
                selector.register_model(
                    model_id=f"adaptive_l{level}",
                    model_name=config.name,
                    capabilities={
                        "strengths": config.capabilities,
                        "avg_latency_ms": config.avg_latency_ms,
                        "quality_score": 0.5 + level * 0.1,
                        "cost_per_1k_tokens": config.cost_per_1k,
                    }
                )
            logger.info("[AdaptiveQualitySystem] 已注册到 ExpertLearning")
        except ImportError:
            logger.info("[AdaptiveQualitySystem] ExpertLearning 未安装，跳过注册")
        except Exception as e:
            logger.info(f"[AdaptiveQualitySystem] 注册到 ExpertLearning 失败: {e}")

    async def execute(
        self,
        query: str,
        task_func: Callable,  # 实际执行函数
        context: Optional[Dict[str, Any]] = None,
        force_level: Optional[int] = None,
    ) -> ExecutionResult:
        """
        执行带质量保障的任务
        
        Args:
            query: 用户查询
            task_func: 实际执行函数，签名为 (model_level) -> response
            context: 额外上下文
            force_level: 强制使用特定级别
            
        Returns:
            ExecutionResult: 执行结果
        """
        context = context or {}
        start_time = time.time()
        
        # 确定起始级别
        if force_level is not None:
            current_level = force_level
        else:
            # 预测性选择起始级别
            current_level = self._predict_start_level(query)
        
        upgrade_attempts = 0
        last_error = None
        
        while True:
            try:
                # 检查预算
                elapsed_ms = (time.time() - start_time) * 1000
                if elapsed_ms > self.budget.max_latency_ms:
                    raise TimeoutError(f"超过最大延迟 {self.budget.max_latency_ms}ms")
                
                # 执行任务
                response = await self._safe_execute(task_func, current_level, query)
                
                # 评估质量
                quality_report = self._evaluator.evaluate(
                    response, query, model_level=current_level
                )
                
                # 更新统计
                self._update_stats(current_level)
                
                # 检查是否需要升级
                if quality_report.needs_upgrade and upgrade_attempts < self.budget.max_attempts:
                    decision = self._upgrade_engine.decide(
                        query=query,
                        current_level=current_level,
                        quality_score=quality_report.overall_score,
                        quality_report=quality_report,
                        attempt_count=upgrade_attempts,
                    )
                    
                    if decision.should_upgrade:
                        # 记录升级前质量
                        quality_before = quality_report.overall_score
                        
                        # 执行升级
                        old_level = current_level
                        current_level = decision.target_level
                        upgrade_attempts += 1
                        
                        # 触发升级回调
                        if self._on_upgrade:
                            self._on_upgrade(old_level, current_level, decision.reasoning)
                        
                        # 重新执行
                        continue
                
                # 质量达标或无法再升级
                elapsed_ms = (time.time() - start_time) * 1000
                
                return ExecutionResult(
                    response=response,
                    quality_score=quality_report.overall_score,
                    quality_level=quality_report.overall_level,
                    model_level=current_level,
                    latency_ms=elapsed_ms,
                    cost=self._estimate_cost(current_level),
                    upgrade_attempts=upgrade_attempts,
                    success=True,
                    quality_report=quality_report,
                )
                
            except Exception as e:
                last_error = str(e)
                
                # 尝试降级重试
                if current_level > 0 and "timeout" in last_error.lower():
                    current_level -= 1
                    continue
                
                # 无法恢复
                return ExecutionResult(
                    response="",
                    quality_score=0.0,
                    quality_level=None,
                    model_level=current_level,
                    latency_ms=(time.time() - start_time) * 1000,
                    cost=0,
                    upgrade_attempts=upgrade_attempts,
                    success=False,
                    error=last_error,
                )

    async def _safe_execute(
        self,
        task_func: Callable,
        level: int,
        query: str,
    ) -> str:
        """安全执行任务"""
        try:
            # 如果是协程
            if hasattr(task_func, '__await__'):
                return await task_func(level)
            else:
                return task_func(level)
        except Exception as e:
            # 记录错误
            logger.info(f"[AQS] Level {level} 执行失败: {e}")
            raise

    def _predict_start_level(self, query: str) -> int:
        """预测性选择起始级别"""
        # 简单策略：根据查询特征
        
        # 关键领域直接高级
        critical_keywords = ["医疗", "法律", "金融", "投资", "诊断"]
        if any(k in query for k in critical_keywords):
            return 4
        
        # 创意任务
        creative_keywords = ["创作", "写作", "故事", "诗歌", "小说"]
        if any(k in query for k in creative_keywords):
            return 3
        
        # 代码相关
        code_keywords = ["代码", "编程", "function", "def ", "class "]
        if any(k in query for k in code_keywords):
            return 2
        
        # 分析推理
        reasoning_keywords = ["分析", "推理", "比较", "评估"]
        if any(k in query for k in reasoning_keywords):
            return 2
        
        # 简单问答
        simple_keywords = ["是什么", "什么是", "哪个", "多少"]
        if any(k in query for k in simple_keywords):
            return 0
        
        # 默认 L1
        return 1

    def _estimate_cost(self, level: int) -> float:
        """估算成本"""
        config = self.models.get(level)
        if config:
            return config.cost_per_1k * 2  # 假设平均 2k tokens
        return 0

    def _update_stats(self, level: int):
        """更新统计"""
        with self._stats_lock:
            self._stats["total_requests"] += 1
            self._stats["level_distribution"][level] = (
                self._stats["level_distribution"].get(level, 0) + 1
            )

    def get_stats(self) -> Dict:
        """获取统计"""
        with self._stats_lock:
            stats = self._stats.copy()
            stats["avg_level"] = sum(
                l * c for l, c in stats["level_distribution"].items()
            ) / max(1, stats["total_requests"])
            stats["upgrade_engine"] = self._upgrade_engine.get_stats()
            return stats

    def set_quality_check_callback(self, callback: Callable):
        """设置质量检查回调"""
        self._on_quality_check = callback

    def set_upgrade_callback(self, callback: Callable):
        """设置升级回调"""
        self._on_upgrade = callback


# ═══════════════════════════════════════════════════════════════════════════════
# 同步包装器（兼容同步代码）
# ═══════════════════════════════════════════════════════════════════════════════

class SyncAdaptiveQualitySystem:
    """同步包装器"""

    def __init__(self, **kwargs):
        import threading
        self._async_system = AdaptiveQualitySystem(**kwargs)
        self._loop = None
        self._thread = None

    def execute(self, query: str, task_func: Callable, **kwargs) -> ExecutionResult:
        """同步执行"""
        import asyncio
from core.logger import get_logger
logger = get_logger('adaptive_quality.adaptive_quality_system')

        
        async def wrapper():
            return await self._async_system.execute(query, task_func, **kwargs)
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在已有事件循环中
                future = asyncio.ensure_future(wrapper())
                return asyncio.get_event_loop().run_until_complete(future)
            else:
                return loop.run_until_complete(wrapper())
        except RuntimeError:
            # 没有事件循环，创建新的
            return asyncio.run(wrapper())

    def get_stats(self) -> Dict:
        return self._async_system.get_stats()


# ═══════════════════════════════════════════════════════════════════════════════
# 工厂函数
# ═══════════════════════════════════════════════════════════════════════════════

_system: Optional[AdaptiveQualitySystem] = None


def get_adaptive_system() -> AdaptiveQualitySystem:
    """获取全局自适应系统实例"""
    global _system
    if _system is None:
        _system = AdaptiveQualitySystem()
    return _system


def quick_execute(
    query: str,
    responses_by_level: Dict[int, str],
) -> Tuple[str, int, float]:
    """
    快速执行（用于已有多个级别响应的情况）
    
    Args:
        query: 用户查询
        responses_by_level: {level: response} 字典
        
    Returns:
        (最佳响应, 最佳级别, 质量评分)
    """
    evaluator = get_adaptive_system()._evaluator
    
    best_response = ""
    best_level = 0
    best_score = 0.0
    
    for level, response in responses_by_level.items():
        report = evaluator.evaluate(response, query, model_level=level)
        if report.overall_score > best_score:
            best_score = report.overall_score
            best_response = response
            best_level = level
    
    return best_response, best_level, best_score
