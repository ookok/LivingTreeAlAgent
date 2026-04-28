"""
EmbeddingOptimizer - 嵌入模型优化器

评估当前嵌入模型性能，支持切换到 FlagEmbedding LLM 或 Cohere。

遵循自我进化原则：
- 自动评估不同嵌入模型的性能
- 根据评估结果自动选择最佳模型
- 从使用中学习优化嵌入策略
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from enum import Enum


class EmbeddingModel(Enum):
    """嵌入模型类型"""
    DEFAULT = "default"
    FLAG_EMBEDDING = "flag_embedding"
    COHERE = "cohere"
    OPENAI = "openai"
    OLLAMA = "ollama"


@dataclass
class ModelPerformance:
    """模型性能评估结果"""
    model_name: str
    accuracy: float = 0.0
    speed: float = 0.0  # tokens/second
    memory_usage: float = 0.0  # MB
    cost_per_token: float = 0.0  # dollars
    ranking: int = 0


class EmbeddingOptimizer:
    """
    嵌入模型优化器
    
    评估当前嵌入模型性能，支持自动选择最佳模型。
    """

    def __init__(self):
        self._logger = logger.bind(component="EmbeddingOptimizer")
        self._current_model = EmbeddingModel.DEFAULT
        self._model_performance: Dict[str, ModelPerformance] = {}
        self._evaluation_history = []

    async def evaluate_models(self, test_corpus: Optional[List[str]] = None) -> List[ModelPerformance]:
        """
        评估可用的嵌入模型
        
        Args:
            test_corpus: 测试语料（可选）
            
        Returns:
            模型性能列表（按评分排序）
        """
        self._logger.info("开始评估嵌入模型")

        if test_corpus is None:
            test_corpus = [
                "人工智能是研究、开发用于模拟、延伸和扩展人的智能的理论、方法、技术及应用系统的一门新的技术科学。",
                "机器学习是人工智能的一个分支，它使计算机系统能够从数据中学习并改进其性能，而无需进行明确编程。",
                "深度学习是机器学习的一个子集，使用多层神经网络来模拟人脑的学习过程。",
                "自然语言处理是人工智能的一个领域，使计算机能够理解、解释和生成人类语言。",
                "计算机视觉是人工智能的一个领域，使计算机能够从图像和视频中提取信息。"
            ]

        # 评估每个模型
        evaluations = []
        
        for model_type in EmbeddingModel:
            try:
                performance = await self._evaluate_model(model_type, test_corpus)
                evaluations.append(performance)
                self._model_performance[model_type.value] = performance
            except Exception as e:
                self._logger.warning(f"评估模型 {model_type.value} 失败: {e}")

        # 按评分排序
        evaluations.sort(key=lambda x: x.ranking)
        
        # 记录评估历史
        self._evaluation_history.append({
            "timestamp": len(self._evaluation_history),
            "models_evaluated": len(evaluations),
            "best_model": evaluations[0].model_name if evaluations else None
        })

        return evaluations

    async def _evaluate_model(self, model_type: EmbeddingModel, test_corpus: List[str]) -> ModelPerformance:
        """
        评估单个模型
        
        Args:
            model_type: 模型类型
            test_corpus: 测试语料
            
        Returns:
            模型性能
        """
        import time
        import psutil
        
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / (1024 * 1024)

        # 模拟嵌入生成
        embeddings = []
        for text in test_corpus:
            if model_type == EmbeddingModel.FLAG_EMBEDDING:
                embedding = await self._generate_flag_embedding(text)
            elif model_type == EmbeddingModel.COHERE:
                embedding = await self._generate_cohere_embedding(text)
            elif model_type == EmbeddingModel.OPENAI:
                embedding = await self._generate_openai_embedding(text)
            elif model_type == EmbeddingModel.OLLAMA:
                embedding = await self._generate_ollama_embedding(text)
            else:
                embedding = await self._generate_default_embedding(text)
            
            embeddings.append(embedding)

        end_time = time.time()
        end_memory = psutil.Process().memory_info().rss / (1024 * 1024)

        # 计算性能指标
        speed = len(test_corpus) / max(end_time - start_time, 0.001)
        memory_usage = end_memory - start_memory

        # 模拟准确度评分（基于向量质量评估）
        accuracy = self._calculate_accuracy(embeddings, test_corpus)

        # 计算综合排名（越小越好）
        ranking = self._calculate_ranking(accuracy, speed, memory_usage, model_type)

        return ModelPerformance(
            model_name=model_type.value,
            accuracy=accuracy,
            speed=speed,
            memory_usage=memory_usage,
            cost_per_token=self._get_cost_per_token(model_type),
            ranking=ranking
        )

    async def _generate_flag_embedding(self, text: str) -> List[float]:
        """生成 FlagEmbedding 嵌入"""
        # 模拟嵌入向量
        return [0.1] * 768

    async def _generate_cohere_embedding(self, text: str) -> List[float]:
        """生成 Cohere 嵌入"""
        # 模拟嵌入向量
        return [0.2] * 768

    async def _generate_openai_embedding(self, text: str) -> List[float]:
        """生成 OpenAI 嵌入"""
        # 模拟嵌入向量
        return [0.3] * 1536

    async def _generate_ollama_embedding(self, text: str) -> List[float]:
        """生成 Ollama 嵌入"""
        # 模拟嵌入向量
        return [0.4] * 512

    async def _generate_default_embedding(self, text: str) -> List[float]:
        """生成默认嵌入"""
        # 模拟嵌入向量
        return [0.5] * 384

    def _calculate_accuracy(self, embeddings: List[List[float]], corpus: List[str]) -> float:
        """计算准确度（模拟）"""
        # 简单计算：基于向量维度和假设的质量评分
        if embeddings:
            dim = len(embeddings[0])
            # 假设维度越高，潜在准确度越高
            return min(1.0, dim / 1536 * 0.8 + 0.2)
        return 0.5

    def _calculate_ranking(self, accuracy: float, speed: float, memory_usage: float, model_type: EmbeddingModel) -> int:
        """计算综合排名"""
        # 权重：准确度 40%，速度 30%，内存 20%，成本 10%
        score = (accuracy * 40 + 
                min(speed / 100, 1) * 30 + 
                max(1 - memory_usage / 500, 0) * 20 + 
                (1 - self._get_cost_per_token(model_type)) * 10)
        return int(100 - score)

    def _get_cost_per_token(self, model_type: EmbeddingModel) -> float:
        """获取每 token 成本（美元）"""
        cost_map = {
            EmbeddingModel.DEFAULT: 0.0,  # 本地模型，无成本
            EmbeddingModel.FLAG_EMBEDDING: 0.0,  # 开源模型，本地运行
            EmbeddingModel.COHERE: 0.0001,  # Cohere API 成本
            EmbeddingModel.OPENAI: 0.0001,  # OpenAI API 成本
            EmbeddingModel.OLLAMA: 0.0,  # 本地模型
        }
        return cost_map.get(model_type, 0.001)

    async def select_best_model(self) -> EmbeddingModel:
        """选择最佳模型"""
        if not self._model_performance:
            await self.evaluate_models()

        # 选择排名最高的模型
        best_model = min(
            self._model_performance.items(),
            key=lambda x: x[1].ranking
        )
        
        self._current_model = EmbeddingModel(best_model[0])
        self._logger.info(f"选择最佳嵌入模型: {self._current_model.value}")
        
        return self._current_model

    def get_current_model(self) -> EmbeddingModel:
        """获取当前模型"""
        return self._current_model

    def get_performance_history(self) -> List[Dict[str, Any]]:
        """获取评估历史"""
        return self._evaluation_history

    def get_stats(self) -> Dict[str, Any]:
        """获取优化器统计信息"""
        return {
            "current_model": self._current_model.value,
            "evaluations_count": len(self._evaluation_history),
            "available_models": [m.value for m in EmbeddingModel],
            "model_performance": {k: v.__dict__ for k, v in self._model_performance.items()}
        }