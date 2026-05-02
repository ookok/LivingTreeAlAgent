"""
EWC保护模块 - Elastic Weight Consolidation
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class EWCWeight:
    parameter_name: str
    value: float
    importance: float
    protection_factor: float
    task_id: str
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class EWCProtection:

    def __init__(self):
        self._protected_weights: Dict[str, List[EWCWeight]] = {}
        self._fisher_cache: Dict[str, Dict[str, float]] = {}
        self._current_task = None

    def protect_task(self, task_id: str, model_weights: Dict[str, np.ndarray],
                     importance_threshold: float = 0.01):
        logger.info(f"保护任务权重: {task_id}")
        fisher_info = self._estimate_fisher_info(model_weights)
        protected = []
        for param_name, value in model_weights.items():
            importance = fisher_info.get(param_name, 0.0)
            if importance >= importance_threshold:
                protected.append(EWCWeight(
                    parameter_name=param_name,
                    value=float(np.mean(value)),
                    importance=importance,
                    protection_factor=min(1.0, importance * 10),
                    task_id=task_id
                ))
        self._protected_weights[task_id] = protected
        self._fisher_cache[task_id] = fisher_info
        logger.info(f"保护了 {len(protected)} 个重要权重")

    def get_ewc_penalty(self, current_weights: Dict[str, np.ndarray]) -> float:
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
        protected_gradients = {}
        for param_name, grad in gradients.items():
            protection_factor = 1.0
            for task_weights in self._protected_weights.values():
                for ewc_weight in task_weights:
                    if ewc_weight.parameter_name == param_name:
                        protection_factor *= (1 - ewc_weight.protection_factor * 0.5)
                        break
            protected_gradients[param_name] = grad * protection_factor * learning_rate
        return protected_gradients

    def _estimate_fisher_info(self, model_weights: Dict[str, np.ndarray]) -> Dict[str, float]:
        fisher_info = {}
        for param_name, value in model_weights.items():
            importance = float(np.var(np.abs(value)))
            fisher_info[param_name] = importance
        return fisher_info

    def get_protected_tasks(self) -> List[str]:
        return list(self._protected_weights.keys())

    def get_protection_info(self, task_id: str) -> Optional[List[EWCWeight]]:
        return self._protected_weights.get(task_id)

    def forget_task(self, task_id: str):
        if task_id in self._protected_weights:
            del self._protected_weights[task_id]
            if task_id in self._fisher_cache:
                del self._fisher_cache[task_id]
            logger.info(f"已忘记任务: {task_id}")

    def get_stats(self) -> Dict:
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
