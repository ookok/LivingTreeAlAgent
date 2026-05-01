"""
EWC保护模块 - Elastic Weight Consolidation

功能：
1. 保护重要权重不被更新
2. 计算Fisher信息矩阵
3. 生成EWC正则化项
4. 防止灾难性遗忘
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class EWCWeight:
    """EWC权重记录"""
    parameter_name: str
    value: float
    importance: float  # Fisher信息
    protection_factor: float  # 保护系数
    task_id: str
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class EWCProtection:
    """
    EWC保护机制 - Elastic Weight Consolidation
    
    核心思想：
    1. 在学习新任务前，计算每个参数的重要性（Fisher信息）
    2. 在学习新任务时，对重要参数施加正则化约束
    3. 保护旧知识不被覆盖
    """
    
    def __init__(self):
        self._protected_weights: Dict[str, List[EWCWeight]] = {}
        self._fisher_cache: Dict[str, Dict[str, float]] = {}
        self._current_task = None
    
    def protect_task(self, task_id: str, model_weights: Dict[str, np.ndarray],
                     importance_threshold: float = 0.01):
        """
        保护当前任务的重要权重
        
        Args:
            task_id: 任务ID
            model_weights: 模型权重
            importance_threshold: 重要性阈值
        """
        logger.info(f"保护任务权重: {task_id}")
        
        # 计算Fisher信息（简化实现）
        fisher_info = self._estimate_fisher_info(model_weights)
        
        # 保存保护的权重
        protected = []
        for param_name, value in model_weights.items():
            importance = fisher_info.get(param_name, 0.0)
            
            if importance >= importance_threshold:
                protected.append(EWCWeight(
                    parameter_name=param_name,
                    value=float(np.mean(value)),  # 简化：使用均值
                    importance=importance,
                    protection_factor=min(1.0, importance * 10),
                    task_id=task_id
                ))
        
        self._protected_weights[task_id] = protected
        self._fisher_cache[task_id] = fisher_info
        
        logger.info(f"保护了 {len(protected)} 个重要权重")
    
    def get_ewc_penalty(self, current_weights: Dict[str, np.ndarray]) -> float:
        """
        计算EWC正则化惩罚项
        
        Args:
            current_weights: 当前模型权重
        
        Returns:
            EWC惩罚值
        """
        penalty = 0.0
        
        for task_id, protected_weights in self._protected_weights.items():
            for ewc_weight in protected_weights:
                if ewc_weight.parameter_name in current_weights:
                    current_value = float(np.mean(current_weights[ewc_weight.parameter_name]))
                    diff = current_value - ewc_weight.value
                    penalty += ewc_weight.importance * (diff ** 2)
        
        return penalty
    
    def apply_protection(self, gradients: Dict[str, np.ndarray],
                        learning_rate: float = 0.01) -> Dict[str, np.ndarray]:
        """
        应用EWC保护到梯度
        
        Args:
            gradients: 梯度字典
            learning_rate: 学习率
        
        Returns:
            应用保护后的梯度
        """
        protected_gradients = {}
        
        for param_name, grad in gradients.items():
            # 找到该参数的保护信息
            protection_factor = 1.0
            
            for task_weights in self._protected_weights.values():
                for ewc_weight in task_weights:
                    if ewc_weight.parameter_name == param_name:
                        # 降低重要参数的学习率
                        protection_factor *= (1 - ewc_weight.protection_factor * 0.5)
                        break
            
            # 应用保护
            protected_gradients[param_name] = grad * protection_factor * learning_rate
        
        return protected_gradients
    
    def _estimate_fisher_info(self, model_weights: Dict[str, np.ndarray]) -> Dict[str, float]:
        """
        估算Fisher信息矩阵（简化实现）
        
        Args:
            model_weights: 模型权重
        
        Returns:
            参数重要性字典
        """
        fisher_info = {}
        
        for param_name, value in model_weights.items():
            # 简化：使用权重绝对值的方差作为重要性指标
            importance = float(np.var(np.abs(value)))
            fisher_info[param_name] = importance
        
        return fisher_info
    
    def get_protected_tasks(self) -> List[str]:
        """获取已保护的任务列表"""
        return list(self._protected_weights.keys())
    
    def get_protection_info(self, task_id: str) -> Optional[List[EWCWeight]]:
        """获取任务的保护信息"""
        return self._protected_weights.get(task_id)
    
    def forget_task(self, task_id: str):
        """忘记任务（移除保护）"""
        if task_id in self._protected_weights:
            del self._protected_weights[task_id]
            if task_id in self._fisher_cache:
                del self._fisher_cache[task_id]
            logger.info(f"已忘记任务: {task_id}")
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        total_protected = sum(len(weights) for weights in self._protected_weights.values())
        
        return {
            'protected_tasks': len(self._protected_weights),
            'total_protected_weights': total_protected,
            'avg_protection_factor': sum(
                ewc.protection_factor
                for weights in self._protected_weights.values()
                for ewc in weights
            ) / total_protected if total_protected > 0 else 0
        }