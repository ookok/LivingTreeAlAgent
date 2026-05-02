"""
A-EVOLVE 集成模块

实现 A-EVOLVE 框架的完整集成：
- 部署时进化 (Deployment-time evolution)
- 进化缩放 (Evolution-scaling)
- 持续开放适应 (Open-ended adaptation)

将进化策略系统与现有技能进化系统集成
"""

import time
import threading
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field

from .evolution_strategy import (
    EvolutionStrategyManager,
    EvolutionMonitor,
    EvolutionStrategyType,
)
from .models import (
    TaskSkill,
    TaskContext,
    ExecutionRecord,
    SkillEvolutionStatus,
)
from .database import EvolutionDatabase
from .atom_tools import UnifiedToolHandler, ToolResult


# ============ A-EVOLVE 集成配置 ============

@dataclass
class AEvolveConfig:
    """A-EVOLVE 集成配置"""
    
    # 核心配置
    enabled: bool = True
    
    # 进化策略配置
    default_strategy: EvolutionStrategyType = EvolutionStrategyType.TARGETED
    
    # 进化参数
    evolution_interval: int = 3600  # 进化检查间隔（秒）
    max_evolution_cycles: int = 10  # 最大进化周期
    
    # 资源配置
    max_compute_budget: float = 1.0  # 最大计算资源预算
    memory_budget: float = 1.0       # 内存资源预算
    
    # 监控配置
    enable_monitoring: bool = True
    monitoring_interval: int = 60  # 监控间隔（秒）
    
    # 日志配置
    verbose: bool = True


# ============ A-EVOLVE 集成器 ============

class AEvolveIntegrator:
    """
    A-EVOLVE 集成器
    
    将 A-EVOLVE 框架的进化能力集成到现有技能进化系统中
    """
    
    def __init__(self, database: EvolutionDatabase, config: AEvolveConfig = None):
        self.db = database
        self.config = config or AEvolveConfig()
        
        # 组件
        self.strategy_manager = EvolutionStrategyManager(database)
        self.monitor = EvolutionMonitor(database)
        
        # 内部状态
        self._lock = threading.RLock()
        self._last_evolution_time = 0
        self._evolution_thread = None
        self._stop_event = threading.Event()
    
    def initialize(self):
        """初始化 A-EVOLVE 集成"""
        if not self.config.enabled:
            return
        
        # 启动进化监控线程
        if self.config.enable_monitoring:
            self._start_monitoring()
    
    def shutdown(self):
        """关闭 A-EVOLVE 集成"""
        self._stop_event.set()
        if self._evolution_thread:
            self._evolution_thread.join(timeout=5.0)
    
    def evolve_skill(self, skill_id: str, feedback: Dict[str, Any] = None) -> bool:
        """
        执行技能进化
        
        Args:
            skill_id: 技能 ID
            feedback: 反馈数据
            
        Returns:
            bool: 是否成功进化
        """
        if not self.config.enabled:
            return False
        
        feedback = feedback or {}
        return self.strategy_manager.evolve_skill(skill_id, feedback)
    
    def batch_evolve_skills(self, skill_ids: List[str], feedback: Dict[str, Any] = None) -> Dict[str, bool]:
        """
        批量进化技能
        
        Returns:
            Dict: 技能 ID -> 进化结果
        """
        if not self.config.enabled:
            return {skill_id: False for skill_id in skill_ids}
        
        feedback = feedback or {}
        return self.strategy_manager.batch_evolve_skills(skill_ids, feedback)
    
    def get_evolution_suggestions(self, skill: TaskSkill) -> List[Dict[str, Any]]:
        """
        获取进化建议
        
        Returns:
            List: 进化建议列表
        """
        return self.strategy_manager.get_evolution_suggestions(skill)
    
    def evolve_from_task_context(self, task_context: TaskContext) -> bool:
        """
        从任务上下文执行进化
        
        Args:
            task_context: 任务上下文
            
        Returns:
            bool: 是否成功进化
        """
        if not self.config.enabled:
            return False
        
        # 分析任务执行结果
        from .models import TaskStatus
        if task_context.status != TaskStatus.COMPLETED:
            return False
        
        # 检查是否有技能关联
        if not task_context.skill_id:
            return False
        
        # 构建反馈
        feedback = self._build_feedback_from_task(task_context)
        
        # 执行进化
        return self.evolve_skill(task_context.skill_id, feedback)
    
    def get_skill_health_report(self, skill: TaskSkill) -> Dict[str, Any]:
        """
        获取技能健康报告
        
        Returns:
            Dict: 健康报告
        """
        report = {
            "skill_id": skill.skill_id,
            "name": skill.name,
            "health_score": self.monitor.get_skill_health_score(skill),
            "evolution_status": skill.evolution_status.value,
            "metrics": {
                "success_rate": skill.success_rate,
                "use_count": skill.use_count,
                "avg_duration": skill.avg_duration,
                "last_used": skill.last_used,
            },
            "suggestions": self.get_evolution_suggestions(skill),
        }
        
        # 添加进化趋势
        trend = self.monitor.get_evolution_trend(skill.skill_id)
        if trend:
            report["evolution_trend"] = trend
        
        return report
    
    def get_all_skills_health(self) -> List[Dict[str, Any]]:
        """
        获取所有技能的健康状态
        
        Returns:
            List: 技能健康报告列表
        """
        skills = self.db.get_all_skills()
        reports = []
        
        for skill in skills:
            report = self.get_skill_health_report(skill)
            reports.append(report)
        
        # 按健康分数排序
        reports.sort(key=lambda x: x["health_score"], reverse=True)
        return reports
    
    def optimize_resource_allocation(self) -> Dict[str, float]:
        """
        优化资源分配
        
        A-EVOLVE 核心特性：进化缩放
        
        Returns:
            Dict: 资源分配方案
        """
        # 分析技能使用情况
        skills = self.db.get_all_skills()
        total_use = sum(skill.use_count for skill in skills)
        
        if total_use == 0:
            return {
                "compute": 0.5,
                "memory": 0.5,
                "time": 0.5,
            }
        
        # 基于使用频率分配资源
        active_skills = [s for s in skills if s.use_count > 0]
        if active_skills:
            avg_use = total_use / len(active_skills)
            resource_factor = min(1.0, total_use / 100.0)  # 资源使用因子
        else:
            avg_use = 0
            resource_factor = 0.3
        
        return {
            "compute": min(1.0, 0.3 + resource_factor * 0.7),
            "memory": min(1.0, 0.4 + resource_factor * 0.6),
            "time": min(1.0, 0.5 + resource_factor * 0.5),
        }
    
    # ============ 内部方法 ============
    
    def _build_feedback_from_task(self, task_context: TaskContext) -> Dict[str, Any]:
        """从任务上下文构建反馈"""
        feedback = {
            "success": task_context.status == TaskContext.TaskStatus.COMPLETED,
            "duration": task_context.duration,
            "turns": len(task_context.execution_records),
        }
        
        # 分析执行记录
        failed_records = [r for r in task_context.execution_records if not r.success]
        if failed_records:
            feedback["error"] = failed_records[0].error_msg
            feedback["failed_steps"] = len(failed_records)
        
        # 分析工具使用
        tool_usage = {}
        for record in task_context.execution_records:
            tool = record.tool_name
            if tool != "no_tool":
                tool_usage[tool] = tool_usage.get(tool, 0) + 1
        feedback["tool_usage"] = tool_usage
        
        return feedback
    
    def _start_monitoring(self):
        """启动监控线程"""
        def monitoring_loop():
            while not self._stop_event.is_set():
                try:
                    self._perform_monitoring()
                    time.sleep(self.config.monitoring_interval)
                except Exception as e:
                    if self.config.verbose:
                        print(f"[AEvolve] 监控线程错误: {e}")
        
        self._evolution_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self._evolution_thread.start()
    
    def _perform_monitoring(self):
        """执行监控任务"""
        # 检查是否需要执行进化
        current_time = time.time()
        if current_time - self._last_evolution_time >= self.config.evolution_interval:
            self._perform_evolution_cycle()
            self._last_evolution_time = current_time
    
    def _perform_evolution_cycle(self):
        """执行进化周期"""
        # 获取需要进化的技能
        skills = self.db.get_all_skills()
        skills_to_evolve = []
        
        for skill in skills:
            # 基于状态和使用情况判断是否需要进化
            if skill.evolution_status != SkillEvolutionStatus.ATROPHIED:
                if skill.use_count > 0 or skill.evolution_status == SkillEvolutionStatus.SEED:
                    skills_to_evolve.append(skill)
        
        # 批量进化
        if skills_to_evolve:
            skill_ids = [s.skill_id for s in skills_to_evolve]
            feedback = {"evolution_cycle": True}
            results = self.batch_evolve_skills(skill_ids, feedback)
            
            if self.config.verbose:
                successful = sum(1 for success in results.values() if success)
                print(f"[AEvolve] 进化周期完成: {successful}/{len(skill_ids)} 技能进化成功")


# ============ 集成到现有系统 ============

def integrate_a_evolve(database: EvolutionDatabase, config: AEvolveConfig = None) -> AEvolveIntegrator:
    """
    集成 A-EVOLVE 到现有系统
    
    Args:
        database: 进化数据库
        config: A-EVOLVE 配置
        
    Returns:
        AEvolveIntegrator: A-EVOLVE 集成器实例
    """
    integrator = AEvolveIntegrator(database, config)
    integrator.initialize()
    return integrator


# ============ 工具函数 ============

def get_a_evolve_integrator(database: EvolutionDatabase) -> AEvolveIntegrator:
    """
    获取 A-EVOLVE 集成器实例
    
    Args:
        database: 进化数据库
        
    Returns:
        AEvolveIntegrator: A-EVOLVE 集成器实例
    """
    return integrate_a_evolve(database)


def evolve_skill_with_feedback(skill_id: str, feedback: Dict[str, Any], database: EvolutionDatabase) -> bool:
    """
    带反馈的技能进化
    
    Args:
        skill_id: 技能 ID
        feedback: 反馈数据
        database: 进化数据库
        
    Returns:
        bool: 是否成功进化
    """
    integrator = get_a_evolve_integrator(database)
    return integrator.evolve_skill(skill_id, feedback)


def get_skill_health(skill: TaskSkill, database: EvolutionDatabase) -> Dict[str, Any]:
    """
    获取技能健康状态
    
    Args:
        skill: 技能对象
        database: 进化数据库
        
    Returns:
        Dict: 健康报告
    """
    integrator = get_a_evolve_integrator(database)
    return integrator.get_skill_health_report(skill)
