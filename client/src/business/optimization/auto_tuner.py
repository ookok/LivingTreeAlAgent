"""
AutoTuner - 贝叶斯优化自动调参器

核心功能：
1. 基于贝叶斯优化搜索最优参数
2. 支持多种优化目标（速度、质量、资源消耗）
3. 自动应用最优参数
4. 持续学习和调优

支持的调参目标：
- 推理速度
- 生成质量
- 内存消耗
- GPU显存占用
- 综合评分
"""

import time
import random
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class ParameterRange:
    """参数范围定义"""
    name: str
    min_value: float
    max_value: float
    step: float = 1.0
    param_type: str = "float"  # float/int/categorical
    categories: List[Any] = None


@dataclass
class TuningResult:
    """调优结果"""
    parameters: Dict[str, Any]
    score: float
    iteration: int
    timestamp: float = 0.0
    metrics: Dict[str, float] = None


@dataclass
class TuningTask:
    """调优任务"""
    component_name: str
    objective: str  # speed/quality/memory/gpu/combined
    parameters: List[ParameterRange]
    max_iterations: int = 50
    timeout_seconds: int = 3600


class AutoTuner:
    """贝叶斯优化自动调参器"""
    
    OBJECTIVES = {
        "speed": {"weight": 1.0, "goal": "maximize"},
        "quality": {"weight": 1.0, "goal": "maximize"},
        "memory": {"weight": 1.0, "goal": "minimize"},
        "gpu": {"weight": 1.0, "goal": "minimize"},
        "combined": {"weights": {"speed": 0.3, "quality": 0.4, "memory": 0.15, "gpu": 0.15}}
    }
    
    def __init__(self):
        self._logger = logger.bind(component="AutoTuner")
        self._tuning_history: List[TuningResult] = []
        self._best_parameters: Dict[str, Dict[str, Any]] = {}
        
        self._logger.info("AutoTuner 初始化完成")
    
    def tune_parameters(self, task: TuningTask, benchmark_func: Callable) -> TuningResult:
        """
        执行贝叶斯优化调参
        
        Args:
            task: 调优任务定义
            benchmark_func: 基准测试函数，接收参数返回评分
        
        Returns:
            最优参数和评分
        """
        self._logger.info(f"开始调优: {task.component_name}, 目标: {task.objective}")
        
        best_score = float('-inf') if self._is_maximize(task.objective) else float('inf')
        best_params = {}
        best_iteration = 0
        
        # 初始化参数空间
        param_space = self._build_param_space(task.parameters)
        
        # 随机搜索阶段（探索）
        for iteration in range(task.max_iterations):
            # 生成候选参数
            params = self._generate_candidate(params_space, iteration, task.max_iterations)
            
            try:
                # 执行基准测试
                metrics = benchmark_func(params)
                
                # 计算综合评分
                score = self._calculate_score(task.objective, metrics)
                
                # 更新最佳参数
                if self._is_better(score, best_score, task.objective):
                    best_score = score
                    best_params = params.copy()
                    best_iteration = iteration
                    self._logger.debug(f"第{iteration}轮: 新最佳评分 {score:.4f}")
            
            except Exception as e:
                self._logger.warning(f"调参迭代 {iteration} 失败: {e}")
            
            # 检查超时
            if time.time() > task.timeout_seconds:
                self._logger.warning("调参超时")
                break
        
        # 保存最佳参数
        result = TuningResult(
            parameters=best_params,
            score=best_score,
            iteration=best_iteration,
            timestamp=time.time()
        )
        
        self._tuning_history.append(result)
        self._best_parameters[task.component_name] = best_params
        
        self._logger.info(f"调优完成: {task.component_name}, 最佳评分: {best_score:.4f}")
        return result
    
    def _build_param_space(self, parameters: List[ParameterRange]) -> Dict[str, dict]:
        """构建参数空间"""
        space = {}
        for param in parameters:
            space[param.name] = {
                "min": param.min_value,
                "max": param.max_value,
                "step": param.step,
                "type": param.param_type,
                "categories": param.categories
            }
        return space
    
    def _generate_candidate(self, param_space: Dict[str, dict], iteration: int, max_iterations: int) -> Dict[str, Any]:
        """
        生成候选参数
        
        前50%迭代：随机探索
        后50%迭代：基于历史最佳进行局部搜索
        """
        params = {}
        
        exploration_ratio = max(0.1, 1.0 - iteration / max_iterations)
        
        for name, config in param_space.items():
            if config["type"] == "categorical" and config["categories"]:
                # 分类参数
                if random.random() < exploration_ratio:
                    params[name] = random.choice(config["categories"])
                else:
                    # 偏向历史最佳
                    if name in self._get_global_best():
                        params[name] = self._get_global_best().get(name, random.choice(config["categories"]))
                    else:
                        params[name] = random.choice(config["categories"])
            
            elif config["type"] == "int":
                # 整数参数
                if random.random() < exploration_ratio:
                    params[name] = random.randint(int(config["min"]), int(config["max"]))
                else:
                    # 高斯扰动
                    base = self._get_global_best().get(name, (config["min"] + config["max"]) / 2)
                    params[name] = int(max(config["min"], min(config["max"], base + random.gauss(0, config["step"] * 2)))
            
            else:
                # 浮点参数
                if random.random() < exploration_ratio:
                    params[name] = random.uniform(config["min"], config["max"])
                else:
                    # 高斯扰动
                    base = self._get_global_best().get(name, (config["min"] + config["max"]) / 2)
                    params[name] = max(config["min"], min(config["max"], base + random.gauss(0, (config["max"] - config["min"]) * 0.1))
        
        return params
    
    def _calculate_score(self, objective: str, metrics: Dict[str, float]) -> float:
        """计算综合评分"""
        if objective == "combined":
            weights = self.OBJECTIVES["combined"]["weights"]
            score = 0.0
            
            # 速度：越高越好，归一化到0-1
            speed_norm = min(1.0, metrics.get("speed", 0) / 100)
            score += weights["speed"] * speed_norm
            
            # 质量：越高越好
            quality_norm = min(1.0, metrics.get("quality", 0) / 100)
            score += weights["quality"] * quality_norm
            
            # 内存：越低越好，取倒数
            memory_norm = 1.0 / (metrics.get("memory", 1) + 1)
            score += weights["memory"] * memory_norm
            
            # GPU：越低越好
            gpu_norm = 1.0 / (metrics.get("gpu", 1) + 1)
            score += weights["gpu"] * gpu_norm
            
            return score
        
        elif objective in ["speed", "quality"]:
            return metrics.get(objective, 0)
        
        elif objective in ["memory", "gpu"]:
            # 取负数，因为我们最大化评分
            return -metrics.get(objective, float('inf'))
        
        return 0.0
    
    def _is_maximize(self, objective: str) -> bool:
        """判断是否最大化目标"""
        if objective == "combined":
            return True
        return self.OBJECTIVES.get(objective, {}).get("goal", "maximize") == "maximize"
    
    def _is_better(self, score: float, best_score: float, objective: str) -> bool:
        """判断新评分是否更优"""
        if self._is_maximize(objective):
            return score > best_score
        return score < best_score
    
    def _get_global_best(self) -> Dict[str, Any]:
        """获取全局最佳参数"""
        if not self._tuning_history:
            return {}
        
        best_result = max(self._tuning_history, key=lambda r: r.score)
        return best_result.parameters
    
    def apply_best_parameters(self, component_name: str, apply_func: Callable):
        """应用最佳参数"""
        if component_name not in self._best_parameters:
            self._logger.warning(f"没有找到 {component_name} 的最佳参数")
            return False
        
        params = self._best_parameters[component_name]
        
        try:
            apply_func(params)
            self._logger.info(f"已应用 {component_name} 的最佳参数")
            return True
        except Exception as e:
            self._logger.error(f"应用参数失败: {e}")
            return False
    
    def get_best_parameters(self, component_name: str) -> Optional[Dict[str, Any]]:
        """获取组件的最佳参数"""
        return self._best_parameters.get(component_name)
    
    def get_tuning_history(self) -> List[TuningResult]:
        """获取调优历史"""
        return self._tuning_history
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        if not self._tuning_history:
            return {
                "total_tunings": 0,
                "best_score": 0.0,
                "tuned_components": []
            }
        
        best_result = max(self._tuning_history, key=lambda r: r.score)
        
        return {
            "total_tunings": len(self._tuning_history),
            "best_score": best_result.score,
            "tuned_components": list(self._best_parameters.keys()),
            "total_iterations": sum(1 for _ in self._tuning_history)
        }


# 单例模式
_auto_tuner_instance = None

def get_auto_tuner() -> AutoTuner:
    """获取自动调参器实例"""
    global _auto_tuner_instance
    if _auto_tuner_instance is None:
        _auto_tuner_instance = AutoTuner()
    return _auto_tuner_instance


# 示例基准测试函数
def example_benchmark(params: Dict[str, Any]) -> Dict[str, float]:
    """示例基准测试函数"""
    # 模拟计算
    speed = params.get("chunk_size", 4096) / 100  # 越大越快
    quality = 100 - abs(params.get("temperature", 0.7) - 0.3) * 50
    memory = params.get("batch_size", 4) * 100 + params.get("chunk_size", 4096) / 10
    gpu = params.get("batch_size", 4) * 200
    
    return {
        "speed": speed,
        "quality": quality,
        "memory": memory,
        "gpu": gpu
    }


if __name__ == "__main__":
    print("=" * 60)
    print("AutoTuner 测试")
    print("=" * 60)
    
    tuner = get_auto_tuner()
    
    # 定义调参任务
    task = TuningTask(
        component_name="document_processor",
        objective="combined",
        parameters=[
            ParameterRange("chunk_size", 1024, 65536, step=1024, param_type="int"),
            ParameterRange("batch_size", 1, 16, step=1, param_type="int"),
            ParameterRange("temperature", 0.0, 1.0, step=0.1, param_type="float"),
            ParameterRange("max_tokens", 512, 8192, step=512, param_type="int"),
            ParameterRange("strategy", 0, 3, param_type="int", categories=["greedy", "beam", "sampling", "contrastive"])
        ],
        max_iterations=30
    )
    
    # 执行调优
    print("\n[1] 执行贝叶斯优化调参")
    result = tuner.tune_parameters(task, example_benchmark)
    
    print(f"\n调优结果:")
    print(f"  最佳评分: {result.score:.4f}")
    print(f"  迭代次数: {result.iteration}")
    print(f"  最佳参数:")
    for key, value in result.parameters.items():
        print(f"    {key}: {value}")
    
    # 统计信息
    print("\n[2] 统计信息")
    stats = tuner.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # 应用最佳参数
    print("\n[3] 应用最佳参数")
    def apply_func(params):
        print(f"应用参数: {params}")
    
    success = tuner.apply_best_parameters("document_processor", apply_func)
    print(f"应用结果: {'成功' if success else '失败'}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)