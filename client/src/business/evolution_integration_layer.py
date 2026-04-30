"""
进化集成层 (Evolution Integration Layer)
========================================

将自我进化模块与系统深度集成：
1. 进化优化循环 - 自我进化与优化引擎的闭环
2. 策略自动部署 - 进化策略自动应用到系统
3. 性能反馈回路 - 系统性能反馈到进化引擎
4. 自适应系统配置 - 根据进化结果自动调整配置

核心特性：
- 深度集成自我进化引擎与优化系统
- 自动部署进化策略
- 性能反馈驱动进化
- 自适应系统配置

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = __import__('logging').getLogger(__name__)


class IntegrationStatus(Enum):
    """集成状态"""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class EvolutionTrigger(Enum):
    """进化触发条件"""
    PERFORMANCE_DROP = "performance_drop"
    PERIODIC = "periodic"
    MANUAL = "manual"
    THRESHOLD_VIOLATION = "threshold_violation"


@dataclass
class IntegrationStats:
    """集成统计"""
    total_evolution_cycles: int = 0
    successful_deployments: int = 0
    failed_deployments: int = 0
    avg_cycle_duration: float = 0.0
    last_evolution_time: float = 0.0


class EvolutionIntegrationLayer:
    """
    进化集成层
    
    将自我进化引擎深度集成到系统中：
    
    核心功能：
    1. 进化-优化闭环 - 将进化策略应用到优化引擎
    2. 性能反馈回路 - 收集系统性能反馈驱动进化
    3. 策略自动部署 - 自动将进化策略部署到生产环境
    4. 自适应配置 - 根据进化结果调整系统配置
    
    工作流程：
    1. 收集性能数据
    2. 触发进化
    3. 评估策略
    4. 部署最优策略
    5. 监控效果
    6. 反馈到进化引擎
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 组件引用（延迟加载）
        self._evolution_engine = None
        self._open_evolution = None
        self._rl_improvement = None
        self._optimization_engine = None
        
        # 集成状态
        self._status = IntegrationStatus.INITIALIZING
        
        # 集成统计
        self._stats = IntegrationStats()
        
        # 进化循环任务
        self._evolution_loop_task = None
        self._evolution_interval = 60  # 60秒检查一次
        
        # 性能阈值
        self._performance_thresholds = {
            "min_optimization_rate": 0.5,
            "min_cache_hit_rate": 0.6,
            "max_cost": 100.0,
        }
        
        # 已部署策略
        self._deployed_strategies: Dict[str, Dict[str, Any]] = {}
        
        self._initialized = True
        logger.info("[EvolutionIntegrationLayer] 进化集成层初始化完成")
    
    async def initialize(self):
        """初始化集成层"""
        try:
            # 延迟加载组件
            self._lazy_load_components()
            
            # 启动进化循环
            await self._start_evolution_loop()
            
            self._status = IntegrationStatus.RUNNING
            logger.info("[EvolutionIntegrationLayer] 进化集成层已启动")
            
            return {"success": True, "message": "进化集成层初始化完成"}
        
        except Exception as e:
            self._status = IntegrationStatus.ERROR
            logger.error(f"[EvolutionIntegrationLayer] 初始化失败: {e}")
            return {"success": False, "message": str(e)}
    
    def _lazy_load_components(self):
        """延迟加载组件"""
        try:
            from business.self_evolution_engine import get_self_evolution_engine
            from business.open_ended_evolution import create_open_ended_evolution
            from business.rl_driven_improvement import create_rl_improvement, RLAlgorithm
            from business.intelligent_optimization_engine import get_intelligent_optimization_engine
            
            self._evolution_engine = get_self_evolution_engine()
            self._open_evolution = create_open_ended_evolution()
            self._rl_improvement = create_rl_improvement(RLAlgorithm.REINFORCE)
            self._optimization_engine = get_intelligent_optimization_engine()
            
            logger.info("[EvolutionIntegrationLayer] 所有组件加载完成")
        
        except Exception as e:
            logger.error(f"[EvolutionIntegrationLayer] 加载组件失败: {e}")
            raise
    
    async def _start_evolution_loop(self):
        """启动进化循环"""
        if self._evolution_loop_task:
            return
        
        async def loop():
            while self._status == IntegrationStatus.RUNNING:
                try:
                    # 检查是否需要进化
                    trigger = await self._check_evolution_trigger()
                    
                    if trigger:
                        logger.info(f"[EvolutionIntegrationLayer] 触发进化: {trigger.value}")
                        await self._execute_evolution_cycle(trigger)
                    
                except Exception as e:
                    logger.error(f"[EvolutionIntegrationLayer] 进化循环错误: {e}")
                
                await asyncio.sleep(self._evolution_interval)
        
        self._evolution_loop_task = asyncio.create_task(loop())
        logger.info("[EvolutionIntegrationLayer] 进化循环已启动")
    
    async def _check_evolution_trigger(self) -> Optional[EvolutionTrigger]:
        """检查进化触发条件"""
        if self._optimization_engine:
            stats = self._optimization_engine.get_dashboard_stats()
            
            # 检查性能下降
            if stats.get("optimization_rate", 1.0) < self._performance_thresholds["min_optimization_rate"]:
                return EvolutionTrigger.PERFORMANCE_DROP
            
            # 检查缓存命中率
            if stats.get("cache_hit_rate", 1.0) < self._performance_thresholds["min_cache_hit_rate"]:
                return EvolutionTrigger.THRESHOLD_VIOLATION
        
        # 定期进化（每10次检查触发一次）
        if self._stats.total_evolution_cycles % 10 == 0:
            return EvolutionTrigger.PERIODIC
        
        return None
    
    async def _execute_evolution_cycle(self, trigger: EvolutionTrigger):
        """执行进化周期"""
        start_time = time.time()
        self._stats.total_evolution_cycles += 1
        
        logger.info(f"[EvolutionIntegrationLayer] 开始进化周期 #{self._stats.total_evolution_cycles}")
        
        try:
            # 1. 收集性能数据
            performance_data = await self._collect_performance_data()
            
            # 2. 执行开放式进化
            open_result = self._open_evolution.evolve()
            
            # 3. 执行自我进化引擎
            evolution_step = await self._evolution_engine.execute_evolution_step()
            
            # 4. 执行强化学习
            await self._execute_rl_step(performance_data)
            
            # 5. 获取最佳策略
            best_strategies = self._open_evolution.get_best_strategies(3)
            
            # 6. 部署最优策略
            for strategy in best_strategies:
                deployed = await self._deploy_strategy(strategy)
                if deployed:
                    self._stats.successful_deployments += 1
                else:
                    self._stats.failed_deployments += 1
            
            # 7. 更新统计
            cycle_duration = time.time() - start_time
            self._stats.avg_cycle_duration = (
                self._stats.avg_cycle_duration * 0.9 + cycle_duration * 0.1
            )
            self._stats.last_evolution_time = time.time()
            
            logger.info(f"[EvolutionIntegrationLayer] 进化周期完成，耗时 {cycle_duration:.2f}秒")
            
        except Exception as e:
            logger.error(f"[EvolutionIntegrationLayer] 进化周期失败: {e}")
            self._stats.failed_deployments += 1
    
    async def _collect_performance_data(self) -> Dict[str, Any]:
        """收集性能数据"""
        data = {}
        
        if self._optimization_engine:
            data.update(self._optimization_engine.get_dashboard_stats())
        
        if self._evolution_engine:
            data["evolution_stats"] = self._evolution_engine.get_evolution_stats()
        
        return data
    
    async def _execute_rl_step(self, performance_data: Dict[str, Any]):
        """执行强化学习步骤"""
        if not self._rl_improvement:
            return
        
        from business.rl_driven_improvement import StateFeature
        
        # 设置状态
        self._rl_improvement.set_current_state({
            StateFeature.SYSTEM_LOAD: performance_data.get("system_load", 0.5),
            StateFeature.OPTIMIZATION_RATE: performance_data.get("optimization_rate", 0.5),
            StateFeature.CACHE_HIT_RATE: performance_data.get("cache_hit_rate", 0.5),
            StateFeature.COST_EFFICIENCY: performance_data.get("cost_efficiency", 0.5),
            StateFeature.USER_SATISFACTION: performance_data.get("user_satisfaction", 0.5),
        })
        
        # 选择动作
        action = self._rl_improvement.select_action()
        
        # 执行动作
        await self._execute_action(action)
        
        # 更新学习
        self._rl_improvement.end_episode(performance_data.get("optimization_rate", 0.5) * 10)
    
    async def _execute_action(self, action):
        """执行动作"""
        action_type = action.type.value
        
        if action_type == "adjust_optimization":
            level = action.parameters.get("level", 0.5)
            strategy = action.parameters.get("strategy", "balanced")
            await self._adjust_optimization(level, strategy)
        
        elif action_type == "switch_model":
            model = action.parameters.get("model", "claude-3-sonnet")
            await self._switch_model(model)
        
        elif action_type == "modify_cache":
            ttl = action.parameters.get("ttl", 3600)
            max_entries = action.parameters.get("max_entries", 1000)
            await self._modify_cache(ttl, max_entries)
        
        elif action_type == "update_strategy":
            strategy_name = action.parameters.get("strategy_name", "")
            await self._update_strategy(strategy_name)
    
    async def _adjust_optimization(self, level: float, strategy: str):
        """调整优化级别"""
        if self._optimization_engine:
            profile_name = {
                "conservative": "conservative",
                "balanced": "default",
                "aggressive": "aggressive",
            }.get(strategy, "default")
            self._optimization_engine.set_profile(profile_name)
            logger.info(f"[EvolutionIntegrationLayer] 调整优化级别: {level}, 策略: {strategy}")
    
    async def _switch_model(self, model: str):
        """切换模型"""
        logger.info(f"[EvolutionIntegrationLayer] 切换模型: {model}")
        # 这里可以添加实际的模型切换逻辑
    
    async def _modify_cache(self, ttl: int, max_entries: int):
        """修改缓存设置"""
        logger.info(f"[EvolutionIntegrationLayer] 修改缓存: TTL={ttl}, 最大条目={max_entries}")
        # 这里可以添加实际的缓存修改逻辑
    
    async def _update_strategy(self, strategy_name: str):
        """更新策略"""
        logger.info(f"[EvolutionIntegrationLayer] 更新策略: {strategy_name}")
        # 这里可以添加实际的策略更新逻辑
    
    async def _deploy_strategy(self, strategy) -> bool:
        """部署策略"""
        try:
            strategy_type = strategy.parameters.get("type", "")
            
            if strategy_type == "token_optimization":
                await self._deploy_token_optimization(strategy)
            elif strategy_type == "cache_optimization":
                await self._deploy_cache_optimization(strategy)
            elif strategy_type == "context_awareness":
                await self._deploy_context_awareness(strategy)
            elif strategy_type == "cost_management":
                await self._deploy_cost_management(strategy)
            
            self._deployed_strategies[strategy.name] = {
                "parameters": strategy.parameters,
                "fitness": strategy.fitness,
                "deployed_at": time.time(),
            }
            
            logger.info(f"[EvolutionIntegrationLayer] 部署策略成功: {strategy.name}")
            return True
        
        except Exception as e:
            logger.error(f"[EvolutionIntegrationLayer] 部署策略失败: {strategy.name}, 错误: {e}")
            return False
    
    async def _deploy_token_optimization(self, strategy):
        """部署Token优化策略"""
        if self._optimization_engine:
            target_ratio = strategy.parameters.get("target_ratio", 0.5)
            profile = self._optimization_engine.get_profile()
            profile.target_compression_ratio = target_ratio
            logger.info(f"[EvolutionIntegrationLayer] 部署Token优化: 目标比率={target_ratio}")
    
    async def _deploy_cache_optimization(self, strategy):
        """部署缓存优化策略"""
        ttl = strategy.parameters.get("ttl", 3600)
        max_entries = strategy.parameters.get("max_entries", 1000)
        logger.info(f"[EvolutionIntegrationLayer] 部署缓存优化: TTL={ttl}, 最大条目={max_entries}")
    
    async def _deploy_context_awareness(self, strategy):
        """部署上下文感知策略"""
        threshold = strategy.parameters.get("detection_threshold", 0.8)
        logger.info(f"[EvolutionIntegrationLayer] 部署上下文感知: 阈值={threshold}")
    
    async def _deploy_cost_management(self, strategy):
        """部署成本管理策略"""
        budget = strategy.parameters.get("budget_limit", 100.0)
        logger.info(f"[EvolutionIntegrationLayer] 部署成本管理: 预算={budget}")
    
    def trigger_evolution(self, reason: str = "manual"):
        """手动触发进化"""
        logger.info(f"[EvolutionIntegrationLayer] 手动触发进化: {reason}")
        # 可以通过事件循环触发进化
    
    def get_status(self) -> IntegrationStatus:
        """获取集成状态"""
        return self._status
    
    def get_stats(self) -> IntegrationStats:
        """获取集成统计"""
        return self._stats
    
    def get_deployed_strategies(self) -> Dict[str, Dict[str, Any]]:
        """获取已部署策略"""
        return self._deployed_strategies.copy()
    
    def pause(self):
        """暂停进化循环"""
        self._status = IntegrationStatus.PAUSED
        logger.info("[EvolutionIntegrationLayer] 进化循环已暂停")
    
    def resume(self):
        """恢复进化循环"""
        self._status = IntegrationStatus.RUNNING
        logger.info("[EvolutionIntegrationLayer] 进化循环已恢复")
    
    def stop(self):
        """停止进化循环"""
        if self._evolution_loop_task:
            self._evolution_loop_task.cancel()
            self._evolution_loop_task = None
        self._status = IntegrationStatus.PAUSED
        logger.info("[EvolutionIntegrationLayer] 进化循环已停止")


# 便捷函数
def get_evolution_integration_layer() -> EvolutionIntegrationLayer:
    """获取进化集成层单例"""
    return EvolutionIntegrationLayer()


async def initialize_evolution_integration() -> Dict[str, Any]:
    """初始化进化集成"""
    layer = get_evolution_integration_layer()
    return await layer.initialize()


__all__ = [
    "IntegrationStatus",
    "EvolutionTrigger",
    "IntegrationStats",
    "EvolutionIntegrationLayer",
    "get_evolution_integration_layer",
    "initialize_evolution_integration",
]
