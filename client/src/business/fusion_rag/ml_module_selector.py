"""
ML驱动模块选择器 (ML-Powered Module Selector)
=============================================

使用机器学习预测最佳模块选择：
1. 特征提取（任务类型、上下文长度、资源状态）
2. 预测模型训练（集成学习）
3. 动态模型更新

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

import asyncio
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from loguru import logger


class FeatureType(Enum):
    """特征类型"""
    TASK_TYPE = "task_type"
    QUERY_LENGTH = "query_length"
    DOCUMENT_PRESENT = "document_present"
    REQUIRED_CAPABILITIES = "required_capabilities"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    GPU_AVAILABLE = "gpu_available"
    HISTORICAL_SUCCESS = "historical_success"
    AVG_LATENCY = "avg_latency"


@dataclass
class TrainingSample:
    """训练样本"""
    features: Dict[str, float]
    label: str  # 最佳模块名称
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    reward: float = 1.0  # 奖励值（0-1）


class MLModuleSelector:
    """
    ML驱动的模块选择器
    
    使用集成学习方法预测最佳模块：
    - 基于历史执行数据训练
    - 支持在线学习
    - 动态模型更新
    """
    
    def __init__(self):
        """初始化选择器"""
        self._training_data: List[TrainingSample] = []
        self._model = None
        self._feature_names = []
        self._module_names = []
        self._is_trained = False
        self._update_lock = asyncio.Lock()
        
    def extract_features(self, context: Any, resource_info: Dict[str, float]) -> Dict[str, float]:
        """
        提取特征
        
        Args:
            context: 任务上下文
            resource_info: 资源信息
            
        Returns:
            特征字典
        """
        features = {}
        
        # 任务类型特征
        if hasattr(context, 'task_type'):
            task_type_mapping = {
                'document_analysis': 0,
                'question_answering': 1,
                'knowledge_retrieval': 2,
                'graph_building': 3,
                'feedback_learning': 4,
                'industry_governance': 5,
                'multi_modal_analysis': 6
            }
            task_type_str = str(context.task_type.value) if hasattr(context.task_type, 'value') else str(context.task_type)
            features['task_type'] = task_type_mapping.get(task_type_str, 0)
            
        # 查询长度特征
        if hasattr(context, 'query') and context.query:
            features['query_length'] = min(len(context.query) / 1000, 1.0)
        else:
            features['query_length'] = 0.0
            
        # 文档存在特征
        if hasattr(context, 'document_path') and context.document_path:
            features['document_present'] = 1.0
        else:
            features['document_present'] = 0.0
            
        # 功能需求特征
        if hasattr(context, 'required_capabilities') and context.required_capabilities:
            features['num_capabilities'] = min(len(context.required_capabilities) / 10, 1.0)
        else:
            features['num_capabilities'] = 0.0
            
        # 资源特征
        features['cpu_usage'] = resource_info.get('cpu_usage', 0.0) / 100.0
        features['memory_usage'] = resource_info.get('memory_usage', 0.0) / 100.0
        features['gpu_available'] = 1.0 if resource_info.get('gpu_available', False) else 0.0
        
        return features
        
    def add_training_sample(self, features: Dict[str, float], module_name: str, reward: float = 1.0):
        """
        添加训练样本
        
        Args:
            features: 特征
            module_name: 模块名称
            reward: 奖励值
        """
        sample = TrainingSample(
            features=features,
            label=module_name,
            reward=reward
        )
        self._training_data.append(sample)
        
        # 更新特征名称和模块名称列表
        for key in features.keys():
            if key not in self._feature_names:
                self._feature_names.append(key)
        if module_name not in self._module_names:
            self._module_names.append(module_name)
            
    def train(self):
        """训练模型"""
        if len(self._training_data) < 10:
            logger.warning("[MLModuleSelector] 训练数据不足，跳过训练")
            return
            
        logger.info(f"[MLModuleSelector] 开始训练，样本数: {len(self._training_data)}")
        
        # 训练简单的加权模型（基于历史成功率）
        self._model = self._train_weighted_model()
        self._is_trained = True
        
        logger.info("[MLModuleSelector] 训练完成")
        
    def _train_weighted_model(self) -> Dict[str, Dict[str, float]]:
        """
        训练加权模型
        
        Returns:
            模型参数
        """
        model = defaultdict(lambda: defaultdict(float))
        
        # 计算每个模块在不同特征组合下的成功率
        feature_module_counts = defaultdict(lambda: defaultdict(int))
        feature_module_successes = defaultdict(lambda: defaultdict(int))
        
        for sample in self._training_data:
            # 简化：使用任务类型作为主要特征
            task_type = int(sample.features.get('task_type', 0))
            feature_key = f"task_{task_type}"
            
            feature_module_counts[feature_key][sample.label] += 1
            feature_module_successes[feature_key][sample.label] += sample.reward
            
        # 计算成功率
        for feature_key, module_counts in feature_module_counts.items():
            for module_name, count in module_counts.items():
                success_rate = feature_module_successes[feature_key][module_name] / count
                model[feature_key][module_name] = success_rate
                
        return dict(model)
        
    def predict(self, features: Dict[str, float], candidates: List[str]) -> List[str]:
        """
        预测最佳模块
        
        Args:
            features: 特征
            candidates: 候选模块列表
            
        Returns:
            排序后的模块列表
        """
        if not self._is_trained or not self._model:
            # 如果模型未训练，返回原始顺序
            return candidates
            
        try:
            # 获取任务类型特征
            task_type = int(features.get('task_type', 0))
            feature_key = f"task_{task_type}"
            
            # 获取该特征下各模块的成功率
            if feature_key in self._model:
                module_scores = self._model[feature_key]
            else:
                module_scores = {}
                
            # 为候选模块打分
            scored_candidates = []
            for module_name in candidates:
                # 使用模型预测的成功率，否则使用默认值
                score = module_scores.get(module_name, 0.5)
                
                # 考虑资源因素
                if features.get('cpu_usage', 0) > 0.7:
                    # CPU 使用率高，轻量级模块加分
                    lightweight_modules = ['EvidenceMemory', 'DocumentNavigator', 'VisualDocumentParser']
                    if module_name in lightweight_modules:
                        score *= 1.1
                        
                scored_candidates.append((module_name, score))
                
            # 按分数排序
            scored_candidates.sort(key=lambda x: x[1], reverse=True)
            return [name for name, score in scored_candidates]
            
        except Exception as e:
            logger.warning(f"[MLModuleSelector] 预测失败: {e}")
            return candidates
            
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            'is_trained': self._is_trained,
            'training_samples': len(self._training_data),
            'feature_names': self._feature_names,
            'module_names': self._module_names
        }
