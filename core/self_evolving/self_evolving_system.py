# -*- coding: utf-8 -*-
"""
自进化Agent系统
================

统一集成三个核心自进化模块：
1. 渐进式学习 (SkillEvolution) - 技能自动创建
2. 反思式Agent (ReflectiveAgent) - 执行-反思-改进
3. 错误学习系统 (ErrorMemory) - 错误修复记忆

自动调用链路：
用户消息 → 意图分类 → 质量监控 → 执行 → 反思评估 → 错误处理 → 学习固化

Author: LivingTreeAI Team
Date: 2026-04-24
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Any, Optional, Callable, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import traceback

# 配置日志
logger = logging.getLogger(__name__)


class ExecutionStage(Enum):
    """执行阶段枚举"""
    PLANNING = "planning"           # 规划阶段
    EXECUTING = "executing"         # 执行阶段
    EVALUATING = "evaluating"        # 评估阶段
    REFLECTING = "reflecting"        # 反思阶段
    LEARNING = "learning"            # 学习阶段
    ERROR_HANDLING = "error_handling"  # 错误处理阶段
    COMPLETED = "completed"          # 完成阶段


class QualityLevel(Enum):
    """质量等级"""
    EXCELLENT = 5   # 优秀
    GOOD = 4        # 良好
    ACCEPTABLE = 3  # 可接受
    POOR = 2        # 较差
    FAILED = 1      # 失败


@dataclass
class ExecutionContext:
    """执行上下文"""
    task: str
    stage: ExecutionStage = ExecutionStage.PLANNING
    model_level: int = 0
    response: str = ""
    quality_score: float = 0.0
    quality_level: QualityLevel = QualityLevel.ACCEPTABLE
    execution_time: float = 0.0
    attempts: int = 1
    max_attempts: int = 3
    needs_upgrade: bool = False
    upgrade_reason: str = ""
    error_info: Optional[Dict[str, Any]] = None
    reflection_notes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def should_continue(self) -> bool:
        """是否继续执行"""
        return (
            self.attempts < self.max_attempts and
            self.quality_level.value < QualityLevel.GOOD.value
        )


@dataclass
class EvolutionResult:
    """自进化结果"""
    response: str
    quality_score: float
    quality_level: QualityLevel
    model_level: int
    execution_time: float
    attempts: int
    was_upgraded: bool
    error_fixed: bool
    learned_new_skill: bool
    reflection_summary: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class SelfEvolvingSystem:
    """
    自进化Agent系统 - 统一入口
    
    集成三大核心模块：
    1. AdaptiveQualitySystem - 自适应质量保障
    2. ReflectiveAgent - 反思式Agent
    3. ErrorMemory - 错误修复记忆
    
    使用方式：
    ```python
    from core.self_evolving import SelfEvolvingSystem, get_evolution_system
    
    # 获取全局实例
    system = get_evolution_system()
    
    # 执行任务
    result = await system.execute("帮我写一个排序算法")
    print(f"质量: {result.quality_level}")
    ```
    """
    
    _instance: Optional['SelfEvolvingSystem'] = None
    
    def __init__(
        self,
        enable_quality: bool = True,
        enable_reflection: bool = True,
        enable_error_learning: bool = True,
        enable_skill_evolution: bool = True,
        quality_threshold: float = 0.5,
        max_upgrade_level: int = 4,
    ):
        """
        初始化自进化系统
        
        Args:
            enable_quality: 启用质量评估
            enable_reflection: 启用反思机制
            enable_error_learning: 启用错误学习
            enable_skill_evolution: 启用技能进化
            quality_threshold: 质量阈值
            max_upgrade_level: 最大升级级别
        """
        self._enabled = {
            'quality': enable_quality,
            'reflection': enable_reflection,
            'error_learning': enable_error_learning,
            'skill_evolution': enable_skill_evolution,
        }
        
        self._quality_threshold = quality_threshold
        self._max_upgrade_level = max_upgrade_level
        
        # 组件实例（延迟加载）
        self._quality_system = None
        self._reflection_loop = None
        self._error_memory = None
        self._skill_evolution = None
        
        # 执行器
        self._executors: Dict[str, Callable] = {}
        
        # 统计
        self._stats = {
            'total_tasks': 0,
            'successful_tasks': 0,
            'upgraded_tasks': 0,
            'errors_fixed': 0,
            'skills_learned': 0,
            'avg_quality_score': 0.0,
        }
        
        # 注册为单例
        SelfEvolvingSystem._instance = self
        
    @property
    def quality_system(self):
        """延迟加载质量系统"""
        if self._quality_system is None and self._enabled['quality']:
            try:
                from core.adaptive_quality import AdaptiveQualitySystem
                self._quality_system = AdaptiveQualitySystem()
                logger.info("Quality system loaded")
            except ImportError as e:
                logger.warning(f"Quality system not available: {e}")
                self._enabled['quality'] = False
        return self._quality_system
    
    @property
    def reflection_loop(self):
        """延迟加载反思循环"""
        if self._reflection_loop is None and self._enabled['reflection']:
            try:
                from client.src.business.reflective_agent import ReflectiveAgentLoop, ReflectiveLoopConfig
                config = ReflectiveLoopConfig(
                    max_reflection_turns=3,
                    improvement_threshold=0.7,
                )
                self._reflection_loop = ReflectiveAgentLoop(config)
                logger.info("Reflection loop loaded")
            except ImportError as e:
                logger.warning(f"Reflection loop not available: {e}")
                self._enabled['reflection'] = False
        return self._reflection_loop
    
    @property
    def error_memory(self):
        """延迟加载错误记忆"""
        if self._error_memory is None and self._enabled['error_learning']:
            try:
                from core.error_memory import ErrorLearningSystem
                self._error_memory = ErrorLearningSystem()
                logger.info("Error memory loaded")
            except ImportError as e:
                logger.warning(f"Error memory not available: {e}")
                self._enabled['error_learning'] = False
        return self._error_memory
    
    @property
    def skill_evolution(self):
        """延迟加载技能进化"""
        if self._skill_evolution is None and self._enabled['skill_evolution']:
            try:
                from core.skill_evolution import SkillEvolutionAgent
                self._skill_evolution = SkillEvolutionAgent()
                logger.info("Skill evolution loaded")
            except ImportError as e:
                logger.warning(f"Skill evolution not available: {e}")
                self._enabled['skill_evolution'] = False
        return self._skill_evolution
    
    def register_executor(self, name: str, executor: Callable):
        """
        注册执行器
        
        Args:
            name: 执行器名称
            executor: 执行函数，签名: async def executor(task: str, **kwargs) -> str
        """
        self._executors[name] = executor
        logger.info(f"Registered executor: {name}")
    
    async def execute(
        self,
        task: str,
        executor_name: str = "default",
        context: Optional[Dict[str, Any]] = None,
    ) -> EvolutionResult:
        """
        执行自进化任务
        
        完整流程：
        1. 规划 → 2. 执行 → 3. 评估 → 4. 反思 → 5. 学习
        
        Args:
            task: 任务描述
            executor_name: 执行器名称
            context: 额外上下文
            
        Returns:
            EvolutionResult: 执行结果
        """
        ctx = ExecutionContext(
            task=task,
            metadata=context or {},
        )
        
        start_time = time.time()
        self._stats['total_tasks'] += 1
        
        try:
            # 1. 规划阶段
            ctx.stage = ExecutionStage.PLANNING
            await self._planning_phase(ctx)
            
            # 2. 执行阶段（带质量重试）
            ctx.stage = ExecutionStage.EXECUTING
            await self._execution_phase(ctx, executor_name)
            
            # 3. 评估阶段
            ctx.stage = ExecutionStage.EVALUATING
            await self._evaluation_phase(ctx)
            
            # 4. 反思阶段
            if ctx.quality_level.value < QualityLevel.GOOD.value:
                ctx.stage = ExecutionStage.REFLECTING
                await self._reflection_phase(ctx)
                
                # 如果反思后质量提升，尝试重新执行
                if ctx.needs_upgrade and ctx.should_continue():
                    ctx.attempts += 1
                    ctx.response = ""
                    await self._execution_phase(ctx, executor_name)
                    await self._evaluation_phase(ctx)
            
            # 5. 学习阶段
            ctx.stage = ExecutionStage.LEARNING
            await self._learning_phase(ctx)
            
            ctx.stage = ExecutionStage.COMPLETED
            
        except Exception as e:
            ctx.stage = ExecutionStage.ERROR_HANDLING
            ctx.error_info = {
                'error': str(e),
                'traceback': traceback.format_exc(),
            }
            await self._error_handling_phase(ctx)
        
        ctx.execution_time = time.time() - start_time
        
        # 更新统计
        self._update_stats(ctx)
        
        return EvolutionResult(
            response=ctx.response,
            quality_score=ctx.quality_score,
            quality_level=ctx.quality_level,
            model_level=ctx.model_level,
            execution_time=ctx.execution_time,
            attempts=ctx.attempts,
            was_upgraded=ctx.needs_upgrade,
            error_fixed=ctx.error_info is not None and ctx.error_info.get('fixed', False),
            learned_new_skill=ctx.metadata.get('learned_skill', False),
            reflection_summary="\n".join(ctx.reflection_notes),
            metadata=ctx.metadata,
        )
    
    async def _planning_phase(self, ctx: ExecutionContext):
        """规划阶段"""
        logger.debug(f"[Planning] Task: {ctx.task[:50]}...")
        
        # 检查是否有相关技能
        if self.skill_evolution:
            skill = await self._find_matching_skill(ctx.task)
            if skill:
                ctx.metadata['matched_skill'] = skill
                ctx.metadata['skip_execution'] = False  # 仍然执行但可用技能辅助
    
    async def _execution_phase(self, ctx: ExecutionContext, executor_name: str):
        """执行阶段"""
        logger.debug(f"[Executing] Level: L{ctx.model_level}, Attempt: {ctx.attempts}")
        
        # 获取执行器
        executor = self._executors.get(executor_name)
        if not executor:
            # 默认执行器：使用质量系统或直接返回
            if self.quality_system:
                # 使用质量系统执行
                result = await self._execute_with_quality(ctx)
                ctx.response = result
            else:
                ctx.response = f"[Mock] Task: {ctx.task}"
        else:
            # 使用注册的执行器
            try:
                ctx.response = await executor(ctx.task, level=ctx.model_level)
            except Exception as e:
                ctx.error_info = {'error': str(e), 'stage': 'execution'}
                raise
    
    async def _execute_with_quality(self, ctx: ExecutionContext) -> str:
        """使用质量系统执行"""
        if not self.quality_system:
            return f"[Default] {ctx.task}"
        
        try:
            # 使用质量系统的异步执行接口
            result = await self.quality_system.execute_async(
                query=ctx.task,
                task_func=lambda level: self._mock_llm_call(ctx.task, level),
            )
            return result.response
        except Exception as e:
            logger.warning(f"Quality system execution failed: {e}")
            return f"[Default] {ctx.task}"
    
    async def _mock_llm_call(self, query: str, level: int) -> str:
        """模拟LLM调用"""
        models = ["qwen2.5:0.5b", "qwen2.5:1.5b", "qwen3.5:2b", "qwen3.5:4b", "qwen3.5:9b"]
        model = models[min(level, len(models) - 1)]
        return f"[{model}] Response for: {query[:30]}..."
    
    async def _evaluation_phase(self, ctx: ExecutionContext):
        """评估阶段"""
        logger.debug(f"[Evaluating] Response length: {len(ctx.response)}")
        
        # 质量评估
        if self.quality_system:
            score, needs_upgrade, target_level = await self._evaluate_quality(ctx)
            ctx.quality_score = score
            ctx.needs_upgrade = needs_upgrade
            
            if needs_upgrade:
                ctx.model_level = target_level
                ctx.upgrade_reason = "Quality below threshold"
                self._stats['upgraded_tasks'] += 1
            
            # 质量等级
            if score >= 0.8:
                ctx.quality_level = QualityLevel.EXCELLENT
            elif score >= 0.6:
                ctx.quality_level = QualityLevel.GOOD
            elif score >= 0.4:
                ctx.quality_level = QualityLevel.ACCEPTABLE
            elif score >= 0.2:
                ctx.quality_level = QualityLevel.POOR
            else:
                ctx.quality_level = QualityLevel.FAILED
        else:
            # 默认评估
            ctx.quality_score = 0.7 if ctx.response else 0.0
            ctx.quality_level = QualityLevel.GOOD if ctx.quality_score >= 0.6 else QualityLevel.ACCEPTABLE
    
    async def _evaluate_quality(
        self, 
        ctx: ExecutionContext
    ) -> Tuple[float, bool, int]:
        """评估质量"""
        try:
            from core.adaptive_quality import quick_evaluate
            score, needs_upgrade, level = quick_evaluate(ctx.response, ctx.task)
            return score, needs_upgrade, level
        except Exception:
            # 默认评估逻辑
            score = 0.7 if ctx.response else 0.0
            needs_upgrade = score < self._quality_threshold
            return score, needs_upgrade, min(ctx.model_level + 1, self._max_upgrade_level)
    
    async def _reflection_phase(self, ctx: ExecutionContext):
        """反思阶段"""
        logger.debug(f"[Reflecting] Quality: {ctx.quality_level.name}")
        
        reflection = f"Quality: {ctx.quality_level.name}, Score: {ctx.quality_score:.2f}"
        ctx.reflection_notes.append(reflection)
        
        # 反思改进建议
        if ctx.quality_score < 0.4:
            ctx.reflection_notes.append("- 质量过低，考虑使用更高级别模型或简化任务")
        elif ctx.quality_score < 0.6:
            ctx.reflection_notes.append("- 质量一般，可尝试补充更多上下文")
        
        ctx.needs_upgrade = ctx.quality_score < self._quality_threshold
    
    async def _learning_phase(self, ctx: ExecutionContext):
        """学习阶段"""
        logger.debug(f"[Learning] Quality level: {ctx.quality_level.name}")
        
        # 从成功中学习
        if ctx.quality_level.value >= QualityLevel.ACCEPTABLE.value:
            await self._learn_from_success(ctx)
        
        # 从错误中学习
        if ctx.error_info:
            await self._learn_from_error(ctx)
    
    async def _learn_from_success(self, ctx: ExecutionContext):
        """从成功中学习"""
        # 技能进化
        if self.skill_evolution and ctx.metadata.get('matched_skill') is None:
            try:
                # 记录成功的任务
                success = await self._record_success(ctx.task, ctx.response)
                if success:
                    self._stats['skills_learned'] += 1
                    ctx.metadata['learned_skill'] = True
            except Exception as e:
                logger.warning(f"Skill learning failed: {e}")
    
    async def _learn_from_error(self, ctx: ExecutionContext):
        """从错误中学习"""
        if self.error_memory and ctx.error_info:
            try:
                await self._record_error(ctx)
            except Exception as e:
                logger.warning(f"Error learning failed: {e}")
    
    async def _error_handling_phase(self, ctx: ExecutionContext):
        """错误处理阶段"""
        logger.error(f"[ErrorHandling] {ctx.error_info}")
        
        if self.error_memory and ctx.error_info:
            try:
                solution = await self._handle_error(ctx)
                if solution:
                    ctx.error_info['fixed'] = True
                    self._stats['errors_fixed'] += 1
            except Exception as e:
                logger.error(f"Error handling failed: {e}")
        
        # 确保有响应
        if not ctx.response:
            ctx.response = f"执行失败: {ctx.error_info.get('error', 'Unknown error')}"
    
    async def _handle_error(self, ctx: ExecutionContext) -> Optional[Dict]:
        """处理错误"""
        try:
            from core.error_memory import quick_fix_from_exception
            solution = quick_fix_from_exception(ctx.error_info['error'])
            return solution
        except Exception:
            return None
    
    async def _find_matching_skill(self, task: str) -> Optional[Dict]:
        """查找匹配的技能"""
        # TODO: 实现技能匹配
        return None
    
    async def _record_success(self, task: str, response: str) -> bool:
        """记录成功"""
        # TODO: 实现成功记录
        return True
    
    async def _record_error(self, ctx: ExecutionContext):
        """记录错误"""
        try:
            from core.error_memory import quick_learn
            quick_learn(ctx.error_info['error'], {'task': ctx.task})
        except Exception:
            pass
    
    def _update_stats(self, ctx: ExecutionContext):
        """更新统计"""
        if ctx.quality_level.value >= QualityLevel.ACCEPTABLE.value:
            self._stats['successful_tasks'] += 1
        
        # 滑动平均质量分数
        total = self._stats['total_tasks']
        current_avg = self._stats['avg_quality_score']
        self._stats['avg_quality_score'] = (
            (current_avg * (total - 1) + ctx.quality_score) / total
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self._stats.copy()
        stats['success_rate'] = (
            stats['successful_tasks'] / stats['total_tasks']
            if stats['total_tasks'] > 0 else 0.0
        )
        stats['upgrade_rate'] = (
            stats['upgraded_tasks'] / stats['total_tasks']
            if stats['total_tasks'] > 0 else 0.0
        )
        stats['enabled_modules'] = [k for k, v in self._enabled.items() if v]
        return stats
    
    def is_enabled(self, module: str) -> bool:
        """检查模块是否启用"""
        return self._enabled.get(module, False)


# 全局获取函数
def get_evolution_system() -> SelfEvolvingSystem:
    """获取全局自进化系统实例"""
    if SelfEvolvingSystem._instance is None:
        SelfEvolvingSystem._instance = SelfEvolvingSystem()
    return SelfEvolvingSystem._instance


def create_evolution_system(**kwargs) -> SelfEvolvingSystem:
    """创建新的自进化系统实例"""
    return SelfEvolvingSystem(**kwargs)


# 便捷函数
async def quick_evolve(task: str, **kwargs) -> EvolutionResult:
    """
    快速执行自进化任务
    
    Args:
        task: 任务描述
        **kwargs: 额外参数
        
    Returns:
        EvolutionResult
    """
    system = get_evolution_system()
    return await system.execute(task, **kwargs)


def evolve_sync(task: str, **kwargs) -> EvolutionResult:
    """
    同步方式执行自进化任务
    
    Args:
        task: 任务描述
        **kwargs: 额外参数
        
    Returns:
        EvolutionResult
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 在已有事件循环中创建任务
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, get_evolution_system().execute(task, **kwargs))
                return future.result()
        else:
            return asyncio.run(get_evolution_system().execute(task, **kwargs))
    except Exception as e:
        return EvolutionResult(
            response=f"Error: {e}",
            quality_score=0.0,
            quality_level=QualityLevel.FAILED,
            model_level=0,
            execution_time=0.0,
            attempts=1,
            was_upgraded=False,
            error_fixed=False,
            learned_new_skill=False,
            reflection_summary=str(e),
        )
