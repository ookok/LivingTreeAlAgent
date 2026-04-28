"""
实验循环功能测试

验证 pi-autoresearch 集成的实验循环功能
"""

import time
import json
from pathlib import Path

# 直接测试实验循环核心功能
from client.src.business.experiment_loop import (
    ExperimentManager,
    OptimizationGoal,
    MetricType,
    CodeOptimizationExperiment,
    SystemResourceExperiment,
    CustomExperiment,
)

from client.src.business.skill_evolution.database import EvolutionDatabase


def test_experiment_manager():
    """测试实验管理器"""
    print("=== 测试实验管理器 ===")
    
    # 创建临时数据库
    db_path = Path("~/.hermes-desktop/evolution/test_experiment.db").expanduser()
    db = EvolutionDatabase(db_path)
    
    # 创建实验管理器
    manager = ExperimentManager(db)
    
    # 测试创建代码优化实验
    experiment_id = "test_code_optimization"
    experiment = manager.create_experiment(
        experiment_id=experiment_id,
        experiment_type="code_optimization"
    )
    print(f"创建代码优化实验: {experiment_id}")
    print(f"实验类型: {experiment.__class__.__name__}")
    print(f"目标指标: {experiment.target_metric}")
    print(f"优化目标: {experiment.optimization_goal.value}")
    
    # 测试运行代码优化实验
    test_code = """
import time
result = 0
for i in range(1000):
    result += i
print(result)
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
    print(f"执行时间: {result.duration:.2f}秒")
    
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
    print(f"成功率: {system_result.success}")
    
    # 测试自定义实验
    print("\n=== 测试自定义实验 ===")
    def custom_evaluator(parameters):
        """自定义评估函数"""
        x = parameters.get("x", 0)
        y = parameters.get("y", 0)
        return x * x + y * y  # 最小化目标
    
    custom_experiment_id = "test_custom"
    custom_experiment = manager.create_experiment(
        experiment_id=custom_experiment_id,
        experiment_type="custom",
        target_metric="custom_score",
        optimization_goal=OptimizationGoal.MINIMIZE,
        evaluation_function=custom_evaluator,
    )
    
    custom_parameters = {
        "x": 3,
        "y": 4,
    }
    
    print("运行自定义实验...")
    custom_result = custom_experiment.run_experiment(custom_parameters)
    print(f"实验结果: 自定义分数 = {custom_result.metric_value:.2f}")
    print(f"成功率: {custom_result.success}")
    
    # 测试优化功能
    print("\n=== 测试优化功能 ===")
    initial_parameters = {
        "x": 10,
        "y": 10,
    }
    
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
    
    # 测试删除实验
    deleted = manager.delete_experiment(experiment_id)
    print(f"删除实验 {experiment_id}: {'成功' if deleted else '失败'}")
    
    experiments = manager.list_experiments()
    print(f"删除后实验列表: {experiments}")
    
    print("\n实验管理器测试完成!")


def test_code_optimization():
    """测试代码优化实验"""
    print("\n=== 测试代码优化实验 ===")
    
    # 创建临时数据库
    db_path = Path("~/.hermes-desktop/evolution/test_code_opt.db").expanduser()
    db = EvolutionDatabase(db_path)
    
    # 创建代码优化实验
    experiment = CodeOptimizationExperiment(db)
    
    # 测试不同代码的执行时间
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
    
    # 找出最快的代码
    if results:
        fastest = min(results, key=lambda x: x["execution_time"])
        print(f"\n最快的实现: {fastest['name']} ({fastest['execution_time']:.4f}秒)")
    
    print("代码优化实验测试完成!")


def test_experiment_dashboard():
    """测试实验仪表板"""
    print("\n=== 测试实验仪表板 ===")
    
    # 创建临时数据库
    db_path = Path("~/.hermes-desktop/evolution/test_dashboard.db").expanduser()
    db = EvolutionDatabase(db_path)
    
    # 创建实验管理器
    manager = ExperimentManager(db)
    
    # 创建仪表板
    from client.src.business.experiment_loop import ExperimentDashboard
    dashboard = ExperimentDashboard(manager)
    
    # 创建并运行实验
    experiment_id = "test_dashboard_exp"
    experiment = manager.create_experiment(
        experiment_id=experiment_id,
        experiment_type="code_optimization"
    )
    
    # 运行几个实验
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
    
    # 获取实验状态
    status = dashboard.get_experiment_status(experiment_id)
    print("实验状态:")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    
    # 获取实验摘要
    summary = dashboard.get_experiment_summary(experiment_id)
    print("\n实验摘要:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    
    # 导出实验结果
    export_json = dashboard.export_experiment_results(experiment_id, format="json")
    print("\n导出 JSON 结果:")
    print(export_json[:500] + "..." if len(export_json) > 500 else export_json)
    
    export_csv = dashboard.export_experiment_results(experiment_id, format="csv")
    print("\n导出 CSV 结果:")
    print(export_csv)
    
    print("实验仪表板测试完成!")


if __name__ == "__main__":
    print("实验循环功能测试开始")
    
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
