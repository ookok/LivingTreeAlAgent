"""
实验循环与技能进化系统的集成

将实验循环功能集成到技能进化系统中，实现：
- 基于实验结果的技能进化
- 实验驱动的技能优化
- 技能性能评估
"""

import time
import threading
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field

from . import (
    ExperimentLoop,
    ExperimentManager,
    ExperimentResult,
    ExperimentSummary,
    OptimizationGoal,
    MetricType,
)
from ..skill_evolution import (
    TaskSkill,
    SkillEvolutionStatus,
    EvolutionDatabase,
    EvolutionEngine,
    AEvolveIntegrator,
)


# ============ 实验驱动的技能进化 ============

class ExperimentDrivenEvolution:
    """
    实验驱动的技能进化
    
    利用实验结果驱动技能的进化和优化
    """
    
    def __init__(self, 
                 database: EvolutionDatabase,
                 evolution_engine: EvolutionEngine,
                 a_evolve_integrator: AEvolveIntegrator):
        self.db = database
        self.evolution_engine = evolution_engine
        self.a_evolve_integrator = a_evolve_integrator
        self.experiment_manager = ExperimentManager(database)
        
        # 实验配置
        self.experiment_config = {
            "code_optimization": {
                "iterations": 1000,
                "timeout": 60,
            },
            "system_resource": {
                "measurements": 10,
                "timeout": 30,
            },
        }
    
    def evaluate_skill_performance(self, skill: TaskSkill) -> Dict[str, float]:
        """
        评估技能性能
        
        Args:
            skill: 技能对象
            
        Returns:
            Dict: 性能评估结果
        """
        # 分析技能执行流程
        if not skill.execution_flow:
            return {
                "complexity": 0,
                "estimated_duration": 0,
                "tool_diversity": 0,
            }
        
        # 计算复杂度
        complexity = len(skill.execution_flow)
        
        # 估计执行时间
        estimated_duration = sum(step.get("duration", 0) for step in skill.execution_flow)
        
        # 工具多样性
        tool_set = set(step.get("tool") for step in skill.execution_flow if step.get("tool"))
        tool_diversity = len(tool_set) / len(skill.execution_flow) if skill.execution_flow else 0
        
        return {
            "complexity": complexity,
            "estimated_duration": estimated_duration,
            "tool_diversity": tool_diversity,
            "success_rate": skill.success_rate,
            "avg_duration": skill.avg_duration,
        }
    
    def optimize_skill(self, skill_id: str, optimization_target: str = "performance") -> ExperimentSummary:
        """
        优化技能
        
        Args:
            skill_id: 技能 ID
            optimization_target: 优化目标 (performance, resource, quality)
            
        Returns:
            ExperimentSummary: 优化结果
        """
        skill = self.db.get_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill {skill_id} not found")
        
        # 根据优化目标选择实验类型
        if optimization_target == "performance":
            experiment_type = "code_optimization"
            target_metric = "execution_time"
            optimization_goal = OptimizationGoal.MINIMIZE
        elif optimization_target == "resource":
            experiment_type = "system_resource"
            target_metric = "memory_usage"
            optimization_goal = OptimizationGoal.MINIMIZE
        else:
            raise ValueError(f"Unknown optimization target: {optimization_target}")
        
        # 创建实验
        experiment_id = f"skill_{skill_id}_{optimization_target}_{int(time.time())}"
        experiment = self.experiment_manager.create_experiment(
            experiment_id=experiment_id,
            experiment_type=experiment_type
        )
        
        # 提取技能参数
        initial_parameters = self._extract_skill_parameters(skill)
        parameter_space = self._generate_parameter_space(skill, optimization_target)
        
        # 执行优化
        summary = self.experiment_manager.optimize(
            experiment_id=experiment_id,
            initial_parameters=initial_parameters,
            parameter_space=parameter_space,
            iterations=10
        )
        
        # 基于实验结果进化技能
        self._evolve_skill_based_on_experiment(skill, summary)
        
        return summary
    
    def batch_optimize_skills(self, 
                             skill_ids: List[str],
                             optimization_target: str = "performance") -> Dict[str, ExperimentSummary]:
        """
        批量优化技能
        
        Returns:
            Dict: 技能 ID -> 优化结果
        """
        results = {}
        for skill_id in skill_ids:
            try:
                summary = self.optimize_skill(skill_id, optimization_target)
                results[skill_id] = summary
            except Exception as e:
                results[skill_id] = None
        return results
    
    def get_skill_optimization_suggestions(self, skill: TaskSkill) -> List[Dict[str, Any]]:
        """
        获取技能优化建议
        
        Returns:
            List: 优化建议
        """
        performance = self.evaluate_skill_performance(skill)
        suggestions = []
        
        # 基于性能评估生成建议
        if performance["estimated_duration"] > 10:
            suggestions.append({
                "type": "performance",
                "message": "技能执行时间过长，建议优化执行流程",
                "priority": "high",
                "experiment_type": "code_optimization",
            })
        
        if performance["complexity"] > 10:
            suggestions.append({
                "type": "complexity",
                "message": "技能执行流程过于复杂，建议拆分或简化",
                "priority": "medium",
                "experiment_type": "code_optimization",
            })
        
        if performance["tool_diversity"] < 0.5:
            suggestions.append({
                "type": "diversity",
                "message": "工具使用过于单一，建议增加工具多样性",
                "priority": "low",
                "experiment_type": "code_optimization",
            })
        
        return suggestions
    
    # ============ 内部方法 ============
    
    def _extract_skill_parameters(self, skill: TaskSkill) -> Dict[str, Any]:
        """
        从技能中提取实验参数
        """
        # 简单实现：提取工具序列作为参数
        parameters = {
            "tool_sequence": skill.tool_sequence,
            "execution_steps": len(skill.execution_flow),
            "skill_id": skill.skill_id,
        }
        
        # 提取代码相关参数
        if skill.execution_flow:
            code_steps = [step for step in skill.execution_flow if step.get("tool") == "code_exec"]
            if code_steps:
                parameters["code"] = code_steps[0].get("args", {}).get("code", "")
                parameters["language"] = code_steps[0].get("args", {}).get("language", "python")
        
        return parameters
    
    def _generate_parameter_space(self, skill: TaskSkill, optimization_target: str) -> Dict[str, List[Any]]:
        """
        生成参数空间
        """
        parameter_space = {}
        
        if optimization_target == "performance":
            # 代码优化参数空间
            parameter_space["iterations"] = [100, 1000, 10000]
            parameter_space["optimization_level"] = ["basic", "advanced", "aggressive"]
        elif optimization_target == "resource":
            # 资源优化参数空间
            parameter_space["memory_limit"] = [128, 256, 512, 1024]
            parameter_space["cpu_cores"] = [1, 2, 4]
        
        return parameter_space
    
    def _evolve_skill_based_on_experiment(self, skill: TaskSkill, summary: ExperimentSummary):
        """
        基于实验结果进化技能
        """
        # 构建进化反馈
        feedback = {
            "experiment_summary": {
                "best_metric": summary.best_result.metric_value,
                "average_metric": summary.average_metric,
                "improvement": summary.improvement,
                "success_rate": summary.success_rate,
            },
            "optimization_target": self._get_optimization_target(summary),
            "experiment_parameters": summary.best_result.parameters,
        }
        
        # 使用 A-EVOLVE 执行进化
        self.a_evolve_integrator.evolve_skill(skill.skill_id, feedback)
        
        # 更新技能元数据
        if "experiment_history" not in skill.metadata:
            skill.metadata["experiment_history"] = []
        
        skill.metadata["experiment_history"].append({
            "timestamp": time.time(),
            "summary": {
                "best_metric": summary.best_result.metric_value,
                "improvement": summary.improvement,
                "total_experiments": summary.total_experiments,
            }
        })
        
        # 保存更新
        self.db.update_skill(skill.skill_id, {
            "metadata": skill.metadata,
            "updated_at": time.time(),
        })
    
    def _get_optimization_target(self, summary: ExperimentSummary) -> str:
        """
        获取优化目标
        """
        metric_name = summary.best_result.parameters.get("target_metric", summary.best_result.parameters.get("optimization_target", "unknown"))
        if "time" in metric_name.lower():
            return "performance"
        elif "memory" in metric_name.lower() or "resource" in metric_name.lower():
            return "resource"
        else:
            return "quality"


# ============ 实验仪表板 ============

class ExperimentDashboard:
    """
    实验仪表板
    
    提供实验结果的可视化和管理
    """
    
    def __init__(self, experiment_manager: ExperimentManager):
        self.experiment_manager = experiment_manager
        self._lock = threading.RLock()
    
    def get_experiment_status(self, experiment_id: str) -> Dict[str, Any]:
        """
        获取实验状态
        
        Returns:
            Dict: 实验状态
        """
        experiment = self.experiment_manager.get_experiment(experiment_id)
        if not experiment:
            return {"status": "not_found"}
        
        history = experiment.get_experiment_history()
        best_result = experiment.get_best_result()
        
        return {
            "status": "running" if experiment.is_running() else "completed",
            "total_experiments": len(history),
            "best_result": {
                "metric_value": best_result.metric_value if best_result else None,
                "parameters": best_result.parameters if best_result else {},
                "timestamp": best_result.timestamp if best_result else None,
            },
            "recent_results": [
                {
                    "metric_value": exp.metric_value,
                    "timestamp": exp.timestamp,
                    "success": exp.success,
                }
                for exp in history[-5:]
            ],
        }
    
    def get_all_experiments_status(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有实验状态
        
        Returns:
            Dict: 实验 ID -> 状态
        """
        statuses = {}
        for experiment_id in self.experiment_manager.list_experiments():
            statuses[experiment_id] = self.get_experiment_status(experiment_id)
        return statuses
    
    def get_experiment_summary(self, experiment_id: str) -> Dict[str, Any]:
        """
        获取实验摘要
        
        Returns:
            Dict: 实验摘要
        """
        experiment = self.experiment_manager.get_experiment(experiment_id)
        if not experiment:
            return {"error": "Experiment not found"}
        
        history = experiment.get_experiment_history()
        best_result = experiment.get_best_result()
        
        if not history:
            return {"error": "No experiments run"}
        
        # 计算统计信息
        successful = sum(1 for exp in history if exp.success)
        success_rate = successful / len(history)
        
        valid_metrics = [exp.metric_value for exp in history if exp.success]
        average_metric = sum(valid_metrics) / len(valid_metrics) if valid_metrics else 0
        
        return {
            "experiment_id": experiment_id,
            "target_metric": experiment.target_metric,
            "optimization_goal": experiment.optimization_goal.value,
            "total_experiments": len(history),
            "success_rate": success_rate,
            "average_metric": average_metric,
            "best_metric": best_result.metric_value if best_result else None,
            "best_parameters": best_result.parameters if best_result else {},
            "metric_type": experiment.metric_type.value,
        }
    
    def export_experiment_results(self, experiment_id: str, format: str = "json") -> str:
        """
        导出实验结果
        
        Args:
            experiment_id: 实验 ID
            format: 导出格式 (json, csv)
            
        Returns:
            str: 导出结果
        """
        experiment = self.experiment_manager.get_experiment(experiment_id)
        if not experiment:
            return "{\"error\": \"Experiment not found\"}"
        
        history = experiment.get_experiment_history()
        
        if format == "json":
            import json
            results = [
                {
                    "parameters": exp.parameters,
                    "metric_value": exp.metric_value,
                    "success": exp.success,
                    "duration": exp.duration,
                    "timestamp": exp.timestamp,
                    "metadata": exp.metadata,
                }
                for exp in history
            ]
            return json.dumps(results, ensure_ascii=False, indent=2)
        elif format == "csv":
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # 写入表头
            writer.writerow(["timestamp", "metric_value", "success", "duration", "parameters"])
            
            # 写入数据
            for exp in history:
                writer.writerow([
                    exp.timestamp,
                    exp.metric_value,
                    exp.success,
                    exp.duration,
                    str(exp.parameters),
                ])
            
            return output.getvalue()
        else:
            return "{\"error\": \"Unsupported format\"}"


# ============ 集成工具函数 ============

def create_experiment_driven_evolution(database: EvolutionDatabase, 
                                      evolution_engine: EvolutionEngine,
                                      a_evolve_integrator: AEvolveIntegrator) -> ExperimentDrivenEvolution:
    """
    创建实验驱动的进化实例
    
    Args:
        database: 进化数据库
        evolution_engine: 进化引擎
        a_evolve_integrator: A-EVOLVE 集成器
        
    Returns:
        ExperimentDrivenEvolution: 实验驱动的进化实例
    """
    return ExperimentDrivenEvolution(database, evolution_engine, a_evolve_integrator)

def create_experiment_dashboard(experiment_manager: ExperimentManager) -> ExperimentDashboard:
    """
    创建实验仪表板
    
    Args:
        experiment_manager: 实验管理器
        
    Returns:
        ExperimentDashboard: 实验仪表板实例
    """
    return ExperimentDashboard(experiment_manager)
