"""
模型评估器 - Model Evaluator

负责在标准测试集上对新模型与旧模型进行自动化对比评测，
决定新模型是否"胜出"并可以部署。

评估维度：
1. 准确率/质量评分
2. 推理速度
3. 内存占用
4. 稳定性
"""

import subprocess
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger


@dataclass
class EvaluationResult:
    """评估结果"""
    winner: str  # "new", "old", "tie"
    new_model_score: float = 0.0
    old_model_score: float = 0.0
    new_model_metrics: Dict = field(default_factory=dict)
    old_model_metrics: Dict = field(default_factory=dict)
    improvement: float = 0.0  # 改进百分比
    success: bool = False
    error: Optional[str] = None


@dataclass
class TestCase:
    """测试用例"""
    query: str
    expected: Optional[str] = None
    intent: str = "general"
    difficulty: str = "medium"  # easy, medium, hard


class ModelEvaluator:
    """
    模型评估器
    
    在标准测试集上对新模型与旧模型进行自动化对比评测
    """
    
    def __init__(self):
        self._logger = logger.bind(component="ModelEvaluator")
        self._test_cases = self._load_test_cases()
    
    def _load_test_cases(self) -> List[TestCase]:
        """加载测试用例"""
        test_cases = []
        
        # 通用知识测试
        test_cases.extend([
            TestCase(
                query="什么是人工智能？",
                intent="simple_qa",
                difficulty="easy"
            ),
            TestCase(
                query="解释量子计算的基本原理",
                intent="complex_reasoning",
                difficulty="hard"
            ),
            TestCase(
                query="写一首关于春天的诗",
                intent="creative",
                difficulty="medium"
            ),
            TestCase(
                query="Python中如何实现装饰器？",
                intent="code_generation",
                difficulty="medium"
            ),
            TestCase(
                query="分析俄乌冲突的历史背景",
                intent="complex_reasoning",
                difficulty="hard"
            ),
            TestCase(
                query="什么是机器学习？",
                intent="simple_qa",
                difficulty="easy"
            ),
            TestCase(
                query="解释相对论的基本概念",
                intent="complex_reasoning",
                difficulty="hard"
            ),
            TestCase(
                query="写一段快速排序的代码",
                intent="code_generation",
                difficulty="medium"
            ),
            TestCase(
                query="描述光合作用的过程",
                intent="simple_qa",
                difficulty="medium"
            ),
            TestCase(
                query="分析ChatGPT的技术架构",
                intent="complex_reasoning",
                difficulty="hard"
            ),
        ])
        
        return test_cases
    
    def evaluate(self, new_model_path: str, old_model_name: str) -> Dict:
        """
        评估新模型
        
        Args:
            new_model_path: 新模型路径
            old_model_name: 旧模型名称
        
        Returns:
            评估结果
        """
        self._logger.info(f"开始评估: 新模型={new_model_path}, 旧模型={old_model_name}")
        
        try:
            # 测试新模型
            new_metrics = self._evaluate_model(new_model_path, is_new=True)
            
            # 测试旧模型
            old_metrics = self._evaluate_model(old_model_name, is_new=False)
            
            # 对比评估
            result = self._compare_models(new_metrics, old_metrics)
            
            self._logger.info(f"评估完成: 胜出者={result['winner']}, 改进={result.get('improvement', 0):.2f}%")
            return result
            
        except Exception as e:
            self._logger.error(f"评估失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "winner": "old"
            }
    
    def _evaluate_model(self, model_identifier: str, is_new: bool = False) -> Dict:
        """
        评估单个模型
        
        Args:
            model_identifier: 模型路径或名称
            is_new: 是否是新训练的模型
        
        Returns:
            模型指标
        """
        metrics = {
            "accuracy": 0.0,
            "speed": 0.0,
            "memory": 0.0,
            "quality": 0.0,
            "completions": 0,
            "errors": 0
        }
        
        total_time = 0
        total_quality = 0
        errors = 0
        
        for test_case in self._test_cases:
            try:
                start_time = time.time()
                
                # 生成响应
                response = self._generate_response(model_identifier, test_case.query, is_new)
                
                elapsed_time = time.time() - start_time
                total_time += elapsed_time
                
                # 评估质量
                quality = self._evaluate_response(test_case, response)
                total_quality += quality
                
                metrics["completions"] += 1
                
            except Exception as e:
                self._logger.warning(f"测试用例失败: {test_case.query[:30]}... {e}")
                errors += 1
        
        # 计算平均指标
        if metrics["completions"] > 0:
            metrics["speed"] = total_time / metrics["completions"]
            metrics["quality"] = total_quality / metrics["completions"]
        
        metrics["errors"] = errors
        metrics["accuracy"] = (metrics["completions"] / len(self._test_cases)) * 100
        
        return metrics
    
    def _generate_response(self, model_identifier: str, query: str, is_new: bool) -> str:
        """
        生成模型响应
        
        Args:
            model_identifier: 模型路径或名称
            query: 查询内容
            is_new: 是否是新模型
        
        Returns:
            模型响应
        """
        try:
            if is_new:
                # 新模型需要先加载
                response = self._run_new_model(model_identifier, query)
            else:
                # 旧模型使用当前运行的引擎
                response = self._run_current_model(model_identifier, query)
            
            return response
        except Exception as e:
            self._logger.warning(f"生成响应失败: {e}")
            return ""
    
    def _run_new_model(self, model_path: str, query: str) -> str:
        """运行新模型"""
        from client.src.infrastructure.ollama_runner import OllamaRunner
        
        runner = OllamaRunner()
        
        # 尝试加载新模型
        try:
            # 假设新模型已经转换为 Ollama 格式
            result = runner.generate(query, model_name=Path(model_path).stem)
            return result.get("response", "")
        except Exception as e:
            self._logger.warning(f"运行新模型失败: {e}")
            return ""
    
    def _run_current_model(self, model_name: str, query: str) -> str:
        """运行当前模型"""
        from client.src.infrastructure.ollama_runner import OllamaRunner
        
        runner = OllamaRunner()
        result = runner.generate(query, model_name=model_name)
        return result.get("response", "")
    
    def _evaluate_response(self, test_case: TestCase, response: str) -> float:
        """
        评估响应质量
        
        Args:
            test_case: 测试用例
            response: 模型响应
        
        Returns:
            质量分数 (0-1)
        """
        if not response:
            return 0.0
        
        score = 0.0
        
        # 基于长度评分
        if len(response) >= 50:
            score += 0.3
        elif len(response) >= 20:
            score += 0.15
        
        # 基于意图的评分
        if test_case.intent == "code_generation":
            if "def " in response or "function" in response.lower():
                score += 0.4
            if "return" in response:
                score += 0.2
        elif test_case.intent == "complex_reasoning":
            if "因为" in response or "因此" in response or "首先" in response:
                score += 0.3
            if len(response) >= 100:
                score += 0.3
        elif test_case.intent == "creative":
            if len(response) >= 80:
                score += 0.4
            if "，" in response and "。" in response:
                score += 0.2
        else:  # simple_qa
            if len(response) >= 30:
                score += 0.4
            if "是" in response or "指" in response:
                score += 0.2
        
        # 基于难度的调整
        if test_case.difficulty == "easy":
            score *= 1.1
        elif test_case.difficulty == "hard":
            score *= 0.9
        
        return min(score, 1.0)
    
    def _compare_models(self, new_metrics: Dict, old_metrics: Dict) -> Dict:
        """
        对比两个模型
        
        Args:
            new_metrics: 新模型指标
            old_metrics: 旧模型指标
        
        Returns:
            对比结果
        """
        # 计算综合评分（权重：质量60%，速度20%，准确率20%）
        new_score = (
            new_metrics["quality"] * 0.6 +
            (1.0 / max(new_metrics["speed"], 0.01)) * 0.2 +
            new_metrics["accuracy"] / 100 * 0.2
        )
        
        old_score = (
            old_metrics["quality"] * 0.6 +
            (1.0 / max(old_metrics["speed"], 0.01)) * 0.2 +
            old_metrics["accuracy"] / 100 * 0.2
        )
        
        # 判断胜出者
        if new_score > old_score * 1.05:  # 需要至少5%的改进
            winner = "new"
            improvement = ((new_score - old_score) / old_score) * 100
        elif old_score > new_score * 1.05:
            winner = "old"
            improvement = -((old_score - new_score) / old_score) * 100
        else:
            winner = "tie"
            improvement = 0
        
        return {
            "success": True,
            "winner": winner,
            "new_model_score": new_score,
            "old_model_score": old_score,
            "new_model_metrics": new_metrics,
            "old_model_metrics": old_metrics,
            "improvement": improvement
        }


# 快捷函数
def get_model_evaluator() -> ModelEvaluator:
    """获取模型评估器实例"""
    return ModelEvaluator()


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("模型评估器测试")
    print("=" * 60)
    
    evaluator = ModelEvaluator()
    
    print(f"测试用例数量: {len(evaluator._test_cases)}")
    
    # 测试评估流程
    result = evaluator.evaluate("./output/model", "qwen3.5:4b")
    print(f"评估结果: {result}")
    
    print("\n" + "=" * 60)