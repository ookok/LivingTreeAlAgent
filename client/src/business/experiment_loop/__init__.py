"""
实验循环模块

实现 pi-autoresearch 的自主实验循环功能：
- 尝试想法
- 测量结果
- 保留有效方法
- 丢弃无效方法
- 重复执行

支持多种优化目标：测试速度、代码质量、系统性能等
"""

import time
import threading
import random
from typing import List, Optional, Dict, Any, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

from ..skill_evolution.models import (
    TaskContext,
    TaskStatus,
    ExecutionRecord,
    TaskSkill,
    SkillEvolutionStatus,
)
from ..skill_evolution.database import EvolutionDatabase
from ..skill_evolution.atom_tools import UnifiedToolHandler, ToolResult


# ============ 优化目标类型 ============

class OptimizationGoal(Enum):
    """优化目标类型"""
    MAXIMIZE = "maximize"  # 最大化
    MINIMIZE = "minimize"  # 最小化


class MetricType(Enum):
    """指标类型"""
    PERFORMANCE = "performance"  # 性能指标
    CODE_QUALITY = "code_quality"  # 代码质量
    SYSTEM_RESOURCE = "system_resource"  # 系统资源
    CUSTOM = "custom"  # 自定义指标


# ============ 实验结果 ============

@dataclass
class ExperimentResult:
    """实验结果"""
    parameters: Dict[str, Any]  # 实验参数
    metric_value: float  # 指标值
    success: bool  # 是否成功
    duration: float  # 执行时间
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentSummary:
    """实验摘要"""
    best_result: ExperimentResult  # 最佳结果
    average_metric: float  # 平均指标
    total_experiments: int  # 总实验次数
    success_rate: float  # 成功率
    improvement: float  # 改进率
    execution_time: float  # 总执行时间


# ============ 实验循环 ============

class ExperimentLoop:
    """
    自主实验循环
    
    实现 pi-autoresearch 的核心功能：尝试 → 测量 → 保留 → 丢弃 → 重复
    """
    
    def __init__(self, 
                 database: EvolutionDatabase,
                 target_metric: str,
                 optimization_goal: OptimizationGoal,
                 metric_type: MetricType = MetricType.CUSTOM):
        """
        初始化实验循环
        
        Args:
            database: 进化数据库
            target_metric: 目标指标名称
            optimization_goal: 优化目标（最大化/最小化）
            metric_type: 指标类型
        """
        self.db = database
        self.target_metric = target_metric
        self.optimization_goal = optimization_goal
        self.metric_type = metric_type
        
        # 实验历史
        self.experiments: List[ExperimentResult] = []
        self.best_result: Optional[ExperimentResult] = None
        
        # 配置
        self.config = {
            "max_iterations": 50,  # 最大迭代次数
            "convergence_threshold": 0.01,  # 收敛阈值
            "timeout": 300,  # 超时时间（秒）
            "parallel_experiments": 1,  # 并行实验数
        }
        
        # 回调
        self.on_experiment_start: Callable[[Dict[str, Any]], None] = None
        self.on_experiment_complete: Callable[[ExperimentResult], None] = None
        self.on_optimization_complete: Callable[[ExperimentSummary], None] = None
        
        # 内部状态
        self._lock = threading.RLock()
        self._running = False
        self._start_time = 0
    
    def run_experiment(self, parameters: Dict[str, Any]) -> ExperimentResult:
        """
        运行单次实验
        
        Args:
            parameters: 实验参数
            
        Returns:
            ExperimentResult: 实验结果
        """
        if self.on_experiment_start:
            self.on_experiment_start(parameters)
        
        start_time = time.time()
        
        try:
            # 执行实验
            result = self._execute_experiment(parameters)
            
            # 评估指标
            metric_value = self._evaluate_metric(result)
            
            # 构建实验结果
            experiment_result = ExperimentResult(
                parameters=parameters,
                metric_value=metric_value,
                success=result.get("success", True),
                duration=time.time() - start_time,
                metadata=result.get("metadata", {})
            )
            
            # 更新最佳结果
            self._update_best_result(experiment_result)
            
            # 记录实验
            self.experiments.append(experiment_result)
            
            if self.on_experiment_complete:
                self.on_experiment_complete(experiment_result)
            
            return experiment_result
            
        except Exception as e:
            # 实验失败
            experiment_result = ExperimentResult(
                parameters=parameters,
                metric_value=float('inf') if self.optimization_goal == OptimizationGoal.MINIMIZE else float('-inf'),
                success=False,
                duration=time.time() - start_time,
                metadata={"error": str(e)}
            )
            
            self.experiments.append(experiment_result)
            
            if self.on_experiment_complete:
                self.on_experiment_complete(experiment_result)
            
            return experiment_result
    
    def optimize(self, 
                 initial_parameters: Dict[str, Any],
                 parameter_space: Dict[str, List[Any]],
                 iterations: int = 10) -> ExperimentSummary:
        """
        执行优化循环
        
        Args:
            initial_parameters: 初始参数
            parameter_space: 参数空间 {参数名: [可能值]}
            iterations: 迭代次数
            
        Returns:
            ExperimentSummary: 实验摘要
        """
        self._running = True
        self._start_time = time.time()
        self.experiments = []
        self.best_result = None
        
        try:
            # 运行初始实验
            initial_result = self.run_experiment(initial_parameters)
            
            # 迭代优化
            current_parameters = initial_parameters.copy()
            
            for i in range(iterations):
                if not self._running:
                    break
                
                # 生成新参数
                new_parameters = self._generate_parameters(current_parameters, parameter_space)
                
                # 运行实验
                result = self.run_experiment(new_parameters)
                
                # 更新当前参数
                if self._is_better(result.metric_value):
                    current_parameters = new_parameters
            
            # 生成摘要
            summary = self._generate_summary()
            
            if self.on_optimization_complete:
                self.on_optimization_complete(summary)
            
            return summary
            
        finally:
            self._running = False
    
    def stop(self):
        """停止实验"""
        self._running = False
    
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running
    
    def get_experiment_history(self) -> List[ExperimentResult]:
        """获取实验历史"""
        return self.experiments.copy()
    
    def get_best_result(self) -> Optional[ExperimentResult]:
        """获取最佳结果"""
        return self.best_result
    
    # ============ 内部方法 ============
    
    def _execute_experiment(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行实验
        
        子类需要实现此方法
        """
        raise NotImplementedError
    
    def _evaluate_metric(self, result: Dict[str, Any]) -> float:
        """
        评估指标
        
        子类需要实现此方法
        """
        raise NotImplementedError
    
    def _generate_parameters(self, 
                           current_parameters: Dict[str, Any],
                           parameter_space: Dict[str, List[Any]]) -> Dict[str, Any]:
        """
        生成新参数
        
        Args:
            current_parameters: 当前参数
            parameter_space: 参数空间
            
        Returns:
            Dict: 新参数
        """
        new_parameters = current_parameters.copy()
        
        # 随机选择一个参数进行变异
        if parameter_space:
            param_name = random.choice(list(parameter_space.keys()))
            possible_values = parameter_space[param_name]
            
            if possible_values:
                # 随机选择一个值
                new_value = random.choice(possible_values)
                new_parameters[param_name] = new_value
        
        return new_parameters
    
    def _is_better(self, metric_value: float) -> bool:
        """
        判断是否更好
        
        Args:
            metric_value: 指标值
            
        Returns:
            bool: 是否更好
        """
        if self.best_result is None:
            return True
        
        if self.optimization_goal == OptimizationGoal.MAXIMIZE:
            return metric_value > self.best_result.metric_value
        else:  # MINIMIZE
            return metric_value < self.best_result.metric_value
    
    def _update_best_result(self, result: ExperimentResult):
        """
        更新最佳结果
        
        Args:
            result: 实验结果
        """
        if self._is_better(result.metric_value):
            self.best_result = result
    
    def _generate_summary(self) -> ExperimentSummary:
        """
        生成实验摘要
        
        Returns:
            ExperimentSummary: 实验摘要
        """
        if not self.experiments:
            raise ValueError("No experiments run")
        
        # 计算统计信息
        total_experiments = len(self.experiments)
        successful_experiments = sum(1 for exp in self.experiments if exp.success)
        success_rate = successful_experiments / total_experiments if total_experiments > 0 else 0
        
        valid_metrics = [exp.metric_value for exp in self.experiments if exp.success]
        average_metric = sum(valid_metrics) / len(valid_metrics) if valid_metrics else 0
        
        # 计算改进率
        if len(valid_metrics) >= 2:
            first_metric = valid_metrics[0]
            last_metric = valid_metrics[-1]
            if self.optimization_goal == OptimizationGoal.MAXIMIZE:
                improvement = (last_metric - first_metric) / first_metric if first_metric != 0 else 0
            else:  # MINIMIZE
                improvement = (first_metric - last_metric) / first_metric if first_metric != 0 else 0
        else:
            improvement = 0
        
        # 总执行时间
        execution_time = time.time() - self._start_time
        
        return ExperimentSummary(
            best_result=self.best_result or self.experiments[0],
            average_metric=average_metric,
            total_experiments=total_experiments,
            success_rate=success_rate,
            improvement=improvement,
            execution_time=execution_time
        )


# ============ 具体实验循环实现 ============

class CodeOptimizationExperiment(ExperimentLoop):
    """
    代码优化实验
    
    优化目标：代码执行速度
    """
    
    def __init__(self, database: EvolutionDatabase):
        super().__init__(
            database=database,
            target_metric="execution_time",
            optimization_goal=OptimizationGoal.MINIMIZE,
            metric_type=MetricType.PERFORMANCE
        )
    
    def _execute_experiment(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行代码优化实验
        
        Args:
            parameters: 实验参数，包含 code, language, iterations
            
        Returns:
            Dict: 执行结果
        """
        code = parameters.get("code", "")
        language = parameters.get("language", "python")
        iterations = parameters.get("iterations", 1000)
        
        # 执行代码并测量时间
        start_time = time.time()
        
        try:
            if language == "python":
                # 执行Python代码
                exec_globals = {}
                exec(code, exec_globals)
                
                # 测量执行时间
                total_time = 0
                for _ in range(iterations):
                    iter_start = time.time()
                    exec(code, exec_globals)
                    total_time += time.time() - iter_start
                
                avg_time = total_time / iterations
                
                return {
                    "success": True,
                    "execution_time": avg_time,
                    "metadata": {
                        "iterations": iterations,
                        "language": language
                    }
                }
            else:
                return {
                    "success": False,
                    "error": f"Unsupported language: {language}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _evaluate_metric(self, result: Dict[str, Any]) -> float:
        """
        评估执行时间指标
        """
        if not result.get("success", False):
            return float('inf')
        return result.get("execution_time", float('inf'))


class SystemResourceExperiment(ExperimentLoop):
    """
    系统资源实验
    
    优化目标：内存使用
    """
    
    def __init__(self, database: EvolutionDatabase):
        super().__init__(
            database=database,
            target_metric="memory_usage",
            optimization_goal=OptimizationGoal.MINIMIZE,
            metric_type=MetricType.SYSTEM_RESOURCE
        )
    
    def _execute_experiment(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行系统资源实验
        """
        # 模拟内存使用测量
        memory_usage = random.uniform(10, 100)  # 模拟内存使用（MB）
        
        return {
            "success": True,
            "memory_usage": memory_usage,
            "metadata": {
                "parameters": parameters
            }
        }
    
    def _evaluate_metric(self, result: Dict[str, Any]) -> float:
        """
        评估内存使用指标
        """
        if not result.get("success", False):
            return float('inf')
        return result.get("memory_usage", float('inf'))


class CustomExperiment(ExperimentLoop):
    """
    自定义实验
    
    支持用户定义的评估函数
    """
    
    def __init__(self, 
                 database: EvolutionDatabase,
                 target_metric: str,
                 optimization_goal: OptimizationGoal,
                 evaluation_function: Callable[[Dict[str, Any]], float]):
        super().__init__(
            database=database,
            target_metric=target_metric,
            optimization_goal=optimization_goal,
            metric_type=MetricType.CUSTOM
        )
        self.evaluation_function = evaluation_function
    
    def _execute_experiment(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行自定义实验
        """
        return {
            "success": True,
            "parameters": parameters,
            "metadata": {}
        }
    
    def _evaluate_metric(self, result: Dict[str, Any]) -> float:
        """
        使用自定义评估函数
        """
        if not result.get("success", False):
            return float('inf') if self.optimization_goal == OptimizationGoal.MINIMIZE else float('-inf')
        return self.evaluation_function(result.get("parameters", {}))


# ============ 实验管理器 ============

class ExperimentManager:
    """
    实验管理器
    
    管理多个实验循环，提供统一的接口
    """
    
    def __init__(self, database: EvolutionDatabase):
        self.db = database
        self.experiments: Dict[str, ExperimentLoop] = {}
        self._lock = threading.RLock()
    
    def create_experiment(self, 
                         experiment_id: str,
                         experiment_type: str,
                         **kwargs) -> ExperimentLoop:
        """
        创建实验
        
        Args:
            experiment_id: 实验 ID
            experiment_type: 实验类型 (code_optimization, system_resource, custom)
            **kwargs: 额外参数
            
        Returns:
            ExperimentLoop: 实验循环实例
        """
        with self._lock:
            if experiment_type == "code_optimization":
                experiment = CodeOptimizationExperiment(self.db)
            elif experiment_type == "system_resource":
                experiment = SystemResourceExperiment(self.db)
            elif experiment_type == "custom":
                target_metric = kwargs.get("target_metric", "custom")
                optimization_goal = kwargs.get("optimization_goal", OptimizationGoal.MAXIMIZE)
                evaluation_function = kwargs.get("evaluation_function")
                if not evaluation_function:
                    raise ValueError("Custom experiment requires evaluation_function")
                experiment = CustomExperiment(
                    self.db,
                    target_metric,
                    optimization_goal,
                    evaluation_function
                )
            else:
                raise ValueError(f"Unknown experiment type: {experiment_type}")
            
            self.experiments[experiment_id] = experiment
            return experiment
    
    def get_experiment(self, experiment_id: str) -> Optional[ExperimentLoop]:
        """
        获取实验
        """
        return self.experiments.get(experiment_id)
    
    def list_experiments(self) -> List[str]:
        """
        列出所有实验
        """
        return list(self.experiments.keys())
    
    def delete_experiment(self, experiment_id: str) -> bool:
        """
        删除实验
        """
        with self._lock:
            if experiment_id in self.experiments:
                del self.experiments[experiment_id]
                return True
            return False
    
    def run_experiment(self, 
                      experiment_id: str,
                      parameters: Dict[str, Any]) -> ExperimentResult:
        """
        运行指定实验
        """
        experiment = self.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")
        return experiment.run_experiment(parameters)
    
    def optimize(self, 
                experiment_id: str,
                initial_parameters: Dict[str, Any],
                parameter_space: Dict[str, List[Any]],
                iterations: int = 10) -> ExperimentSummary:
        """
        执行优化
        """
        experiment = self.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")
        return experiment.optimize(initial_parameters, parameter_space, iterations)


# ============ 导出组件 ============

__all__ = [
    # 枚举
    "OptimizationGoal",
    "MetricType",
    # 数据类
    "ExperimentResult",
    "ExperimentSummary",
    # 核心组件
    "ExperimentLoop",
    "CodeOptimizationExperiment",
    "SystemResourceExperiment",
    "CustomExperiment",
    "ExperimentManager",
    # 集成
    "ExperimentDrivenEvolution",
    "ExperimentDashboard",
    # 工具函数
    "create_experiment_driven_evolution",
    "create_experiment_dashboard",
]


# 导入集成模块
from .integration import (
    ExperimentDrivenEvolution,
    ExperimentDashboard,
    create_experiment_driven_evolution,
    create_experiment_dashboard,
)
