"""
实验循环独立测试

完全独立测试实验循环核心功能，不依赖项目其他模块
"""

import time
import json
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any, Callable


# 模拟必要的类
class EvolutionDatabase:
    def __init__(self, db_path):
        self.db_path = db_path
        self.skills = {}
    
    def get_skill(self, skill_id):
        return self.skills.get(skill_id)
    
    def update_skill(self, skill_id, updates):
        if skill_id in self.skills:
            skill = self.skills[skill_id]
            for key, value in updates.items():
                setattr(skill, key, value)
            return True
        return False


@dataclass
class TaskSkill:
    skill_id: str
    name: str
    description: str
    execution_flow: List[Dict[str, Any]] = field(default_factory=list)
    tool_sequence: List[str] = field(default_factory=list)
    success_rate: float = 1.0
    avg_duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    updated_at: float = field(default_factory=time.time)


# 复制实验循环核心代码
class OptimizationGoal(Enum):
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


class MetricType(Enum):
    PERFORMANCE = "performance"
    CODE_QUALITY = "code_quality"
    SYSTEM_RESOURCE = "system_resource"
    CUSTOM = "custom"


@dataclass
class ExperimentResult:
    parameters: Dict[str, Any]
    metric_value: float
    success: bool
    duration: float
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentSummary:
    best_result: ExperimentResult
    average_metric: float
    total_experiments: int
    success_rate: float
    improvement: float
    execution_time: float


class ExperimentLoop:
    def __init__(self, database, target_metric, optimization_goal, metric_type=MetricType.CUSTOM):
        self.db = database
        self.target_metric = target_metric
        self.optimization_goal = optimization_goal
        self.metric_type = metric_type
        self.experiments = []
        self.best_result = None
        self.config = {
            "max_iterations": 50,
            "convergence_threshold": 0.01,
            "timeout": 300,
            "parallel_experiments": 1,
        }
    
    def run_experiment(self, parameters):
        start_time = time.time()
        try:
            result = self._execute_experiment(parameters)
            metric_value = self._evaluate_metric(result)
            experiment_result = ExperimentResult(
                parameters=parameters,
                metric_value=metric_value,
                success=result.get("success", True),
                duration=time.time() - start_time,
                metadata=result.get("metadata", {})
            )
            self._update_best_result(experiment_result)
            self.experiments.append(experiment_result)
            return experiment_result
        except Exception as e:
            experiment_result = ExperimentResult(
                parameters=parameters,
                metric_value=float('inf') if self.optimization_goal == OptimizationGoal.MINIMIZE else float('-inf'),
                success=False,
                duration=time.time() - start_time,
                metadata={"error": str(e)}
            )
            self.experiments.append(experiment_result)
            return experiment_result
    
    def optimize(self, initial_parameters, parameter_space, iterations=10):
        self.experiments = []
        self.best_result = None
        start_time = time.time()
        
        initial_result = self.run_experiment(initial_parameters)
        current_parameters = initial_parameters.copy()
        
        for i in range(iterations):
            new_parameters = self._generate_parameters(current_parameters, parameter_space)
            result = self.run_experiment(new_parameters)
            if self._is_better(result.metric_value):
                current_parameters = new_parameters
        
        return self._generate_summary()
    
    def _execute_experiment(self, parameters):
        raise NotImplementedError
    
    def _evaluate_metric(self, result):
        raise NotImplementedError
    
    def _generate_parameters(self, current_parameters, parameter_space):
        new_parameters = current_parameters.copy()
        if parameter_space:
            param_name = random.choice(list(parameter_space.keys()))
            possible_values = parameter_space[param_name]
            if possible_values:
                new_value = random.choice(possible_values)
                new_parameters[param_name] = new_value
        return new_parameters
    
    def _is_better(self, metric_value):
        if self.best_result is None:
            return True
        if self.optimization_goal == OptimizationGoal.MAXIMIZE:
            return metric_value > self.best_result.metric_value
        else:
            return metric_value < self.best_result.metric_value
    
    def _update_best_result(self, result):
        if self._is_better(result.metric_value):
            self.best_result = result
    
    def _generate_summary(self):
        if not self.experiments:
            raise ValueError("No experiments run")
        
        total_experiments = len(self.experiments)
        successful_experiments = sum(1 for exp in self.experiments if exp.success)
        success_rate = successful_experiments / total_experiments if total_experiments > 0 else 0
        
        valid_metrics = [exp.metric_value for exp in self.experiments if exp.success]
        average_metric = sum(valid_metrics) / len(valid_metrics) if valid_metrics else 0
        
        if len(valid_metrics) >= 2:
            first_metric = valid_metrics[0]
            last_metric = valid_metrics[-1]
            if self.optimization_goal == OptimizationGoal.MAXIMIZE:
                improvement = (last_metric - first_metric) / first_metric if first_metric != 0 else 0
            else:
                improvement = (first_metric - last_metric) / first_metric if first_metric != 0 else 0
        else:
            improvement = 0
        
        execution_time = time.time() - self.experiments[0].timestamp if self.experiments else 0
        
        return ExperimentSummary(
            best_result=self.best_result or self.experiments[0],
            average_metric=average_metric,
            total_experiments=total_experiments,
            success_rate=success_rate,
            improvement=improvement,
            execution_time=execution_time
        )


class CodeOptimizationExperiment(ExperimentLoop):
    def __init__(self, database):
        super().__init__(
            database=database,
            target_metric="execution_time",
            optimization_goal=OptimizationGoal.MINIMIZE,
            metric_type=MetricType.PERFORMANCE
        )
    
    def _execute_experiment(self, parameters):
        code = parameters.get("code", "")
        language = parameters.get("language", "python")
        iterations = parameters.get("iterations", 1000)
        
        start_time = time.time()
        
        try:
            if language == "python":
                exec_globals = {}
                exec(code, exec_globals)
                
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
    
    def _evaluate_metric(self, result):
        if not result.get("success", False):
            return float('inf')
        return result.get("execution_time", float('inf'))


class SystemResourceExperiment(ExperimentLoop):
    def __init__(self, database):
        super().__init__(
            database=database,
            target_metric="memory_usage",
            optimization_goal=OptimizationGoal.MINIMIZE,
            metric_type=MetricType.SYSTEM_RESOURCE
        )
    
    def _execute_experiment(self, parameters):
        memory_usage = random.uniform(10, 100)
        
        return {
            "success": True,
            "memory_usage": memory_usage,
            "metadata": {
                "parameters": parameters
            }
        }
    
    def _evaluate_metric(self, result):
        if not result.get("success", False):
            return float('inf')
        return result.get("memory_usage", float('inf'))


class CustomExperiment(ExperimentLoop):
    def __init__(self, database, target_metric, optimization_goal, evaluation_function):
        super().__init__(
            database=database,
            target_metric=target_metric,
            optimization_goal=optimization_goal,
            metric_type=MetricType.CUSTOM
        )
        self.evaluation_function = evaluation_function
    
    def _execute_experiment(self, parameters):
        return {
            "success": True,
            "parameters": parameters,
            "metadata": {}
        }
    
    def _evaluate_metric(self, result):
        if not result.get("success", False):
            return float('inf') if self.optimization_goal == OptimizationGoal.MINIMIZE else float('-inf')
        return self.evaluation_function(result.get("parameters", {}))


class ExperimentManager:
    def __init__(self, database):
        self.db = database
        self.experiments = {}
    
    def create_experiment(self, experiment_id, experiment_type, **kwargs):
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
    
    def get_experiment(self, experiment_id):
        return self.experiments.get(experiment_id)
    
    def list_experiments(self):
        return list(self.experiments.keys())
    
    def delete_experiment(self, experiment_id):
        if experiment_id in self.experiments:
            del self.experiments[experiment_id]
            return True
        return False
    
    def run_experiment(self, experiment_id, parameters):
        experiment = self.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")
        return experiment.run_experiment(parameters)
    
    def optimize(self, experiment_id, initial_parameters, parameter_space, iterations=10):
        experiment = self.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")
        return experiment.optimize(initial_parameters, parameter_space, iterations)


class ExperimentDashboard:
    def __init__(self, experiment_manager):
        self.experiment_manager = experiment_manager
    
    def get_experiment_status(self, experiment_id):
        experiment = self.experiment_manager.get_experiment(experiment_id)
        if not experiment:
            return {"status": "not_found"}
        
        history = experiment.experiments
        best_result = experiment.best_result
        
        return {
            "status": "completed",
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
    
    def get_experiment_summary(self, experiment_id):
        experiment = self.experiment_manager.get_experiment(experiment_id)
        if not experiment:
            return {"error": "Experiment not found"}
        
        history = experiment.experiments
        best_result = experiment.best_result
        
        if not history:
            return {"error": "No experiments run"}
        
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


# 测试函数
def test_experiment_manager():
    print("=== 测试实验管理器 ===")
    
    db = EvolutionDatabase("test.db")
    manager = ExperimentManager(db)
    
    # 测试代码优化实验
    experiment_id = "test_code_optimization"
    experiment = manager.create_experiment(
        experiment_id=experiment_id,
        experiment_type="code_optimization"
    )
    print(f"创建代码优化实验: {experiment_id}")
    print(f"目标指标: {experiment.target_metric}")
    print(f"优化目标: {experiment.optimization_goal.value}")
    
    # 测试运行实验
    test_code = """
result = 0
for i in range(1000):
    result += i
"""
    
    parameters = {
        "code": test_code,
        "language": "python",
        "iterations": 100,
    }
    
    print("\n运行代码优化实验...")
    result = experiment.run_experiment(parameters)
    print(f"实验结果: 执行时间 = {result.metric_value:.4f}秒")
    print(f"成功率: {result.success}")
    
    # 测试系统资源实验
    print("\n=== 测试系统资源实验 ===")
    system_experiment_id = "test_system_resource"
    system_experiment = manager.create_experiment(
        experiment_id=system_experiment_id,
        experiment_type="system_resource"
    )
    
    system_parameters = {
        "memory_limit": 256,
        "cpu_cores": 2,
    }
    
    print("运行系统资源实验...")
    system_result = system_experiment.run_experiment(system_parameters)
    print(f"实验结果: 内存使用 = {system_result.metric_value:.2f}MB")
    
    # 测试自定义实验
    print("\n=== 测试自定义实验 ===")
    def custom_evaluator(parameters):
        x = parameters.get("x", 0)
        y = parameters.get("y", 0)
        return x * x + y * y
    
    custom_experiment_id = "test_custom"
    custom_experiment = manager.create_experiment(
        experiment_id=custom_experiment_id,
        experiment_type="custom",
        target_metric="custom_score",
        optimization_goal=OptimizationGoal.MINIMIZE,
        evaluation_function=custom_evaluator,
    )
    
    custom_parameters = {"x": 3, "y": 4}
    print("运行自定义实验...")
    custom_result = custom_experiment.run_experiment(custom_parameters)
    print(f"实验结果: 自定义分数 = {custom_result.metric_value:.2f}")
    
    # 测试优化功能
    print("\n=== 测试优化功能 ===")
    initial_parameters = {"x": 10, "y": 10}
    parameter_space = {
        "x": [1, 5, 10, 15, 20],
        "y": [1, 5, 10, 15, 20],
    }
    
    print("执行优化...")
    summary = custom_experiment.optimize(
        initial_parameters=initial_parameters,
        parameter_space=parameter_space,
        iterations=5
    )
    
    print(f"优化完成!")
    print(f"最佳结果: {summary.best_result.metric_value:.2f}")
    print(f"最佳参数: {summary.best_result.parameters}")
    print(f"平均指标: {summary.average_metric:.2f}")
    print(f"总实验次数: {summary.total_experiments}")
    print(f"成功率: {summary.success_rate:.2f}")
    print(f"改进率: {summary.improvement:.2f}")
    print(f"总执行时间: {summary.execution_time:.2f}秒")
    
    # 测试实验管理
    print("\n=== 测试实验管理 ===")
    experiments = manager.list_experiments()
    print(f"当前实验列表: {experiments}")
    
    deleted = manager.delete_experiment(experiment_id)
    print(f"删除实验 {experiment_id}: {'成功' if deleted else '失败'}")
    
    experiments = manager.list_experiments()
    print(f"删除后实验列表: {experiments}")


def test_code_optimization():
    print("\n=== 测试代码优化实验 ===")
    
    db = EvolutionDatabase("test_code_opt.db")
    experiment = CodeOptimizationExperiment(db)
    
    test_codes = [
        {
            "name": "普通循环",
            "code": """
result = 0
for i in range(1000000):
    result += i
"""
        },
        {
            "name": "列表推导式",
            "code": """
result = sum([i for i in range(1000000)])
"""
        },
        {
            "name": "生成器表达式",
            "code": """
result = sum(i for i in range(1000000))
"""
        },
    ]
    
    results = []
    for test in test_codes:
        parameters = {
            "code": test["code"],
            "language": "python",
            "iterations": 10,
        }
        
        print(f"测试: {test['name']}")
        result = experiment.run_experiment(parameters)
        results.append({
            "name": test["name"],
            "execution_time": result.metric_value,
            "success": result.success,
        })
        print(f"  执行时间: {result.metric_value:.4f}秒")
    
    if results:
        fastest = min(results, key=lambda x: x["execution_time"])
        print(f"\n最快的实现: {fastest['name']} ({fastest['execution_time']:.4f}秒)")


def test_experiment_dashboard():
    print("\n=== 测试实验仪表板 ===")
    
    db = EvolutionDatabase("test_dashboard.db")
    manager = ExperimentManager(db)
    dashboard = ExperimentDashboard(manager)
    
    experiment_id = "test_dashboard_exp"
    experiment = manager.create_experiment(
        experiment_id=experiment_id,
        experiment_type="code_optimization"
    )
    
    test_code = """
result = 0
for i in range(100000):
    result += i
"""
    
    for i in range(3):
        parameters = {
            "code": test_code,
            "language": "python",
            "iterations": 50 + i * 10,
        }
        experiment.run_experiment(parameters)
        time.sleep(0.5)
    
    status = dashboard.get_experiment_status(experiment_id)
    print("实验状态:")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    
    summary = dashboard.get_experiment_summary(experiment_id)
    print("\n实验摘要:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    print("实验循环独立测试开始")
    
    try:
        test_experiment_manager()
        test_code_optimization()
        test_experiment_dashboard()
        print("\n✅ 所有测试通过!")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n测试完成")
