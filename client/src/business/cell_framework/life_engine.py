"""
生命系统引擎 - LifeEngine

实现主动推理和自由能原理，让AI系统像生命体一样思考。

核心理论：
1. 预测编码（Predictive Coding）- 大脑的工作原理
2. 主动推理（Active Inference）- 自由能原理的实现
3. 贝叶斯大脑假说 - 大脑作为概率推理引擎
4. 神经符号AI - 结合符号推理和神经网络

架构层次：
┌─────────────────────────────────────────────────────────────┐
│                    自我意识层                              │
│  (元认知、反思、自我监控)                                   │
├─────────────────────────────────────────────────────────────┤
│                    主动推理层                              │
│  (自由能最小化、预测误差、信念更新)                         │
├─────────────────────────────────────────────────────────────┤
│                    细胞协作层                              │
│  (细胞群体、涌现智能、Hebbian学习)                         │
├─────────────────────────────────────────────────────────────┤
│                    免疫系统层                              │
│  (异常检测、自我修复、有害隔离)                             │
├─────────────────────────────────────────────────────────────┤
│                    代谢系统层                              │
│  (资源管理、能量效率、休眠机制)                             │
└─────────────────────────────────────────────────────────────┘
"""

import asyncio
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Callable
import numpy as np
from collections import defaultdict


class BeliefState(Enum):
    """信念状态"""
    CERTAIN = "certain"
    CONFIDENT = "confident"
    UNCERTAIN = "uncertain"
    CONFLICTED = "conflicted"


class InferenceMode(Enum):
    """推理模式"""
    PERCEPTION = "perception"      # 感知推理
    ACTION = "action"              # 行动推理
    REFLECTION = "reflection"      # 反思推理
    PLANNING = "planning"          # 规划推理


class FreeEnergyCalculator:
    """自由能计算器"""
    
    @staticmethod
    def calculate(
        prediction_error: float,
        entropy: float = 0.0,
        complexity: float = 0.0
    ) -> float:
        """
        计算自由能
        
        自由能 = 预测误差 + 复杂度 - 熵
        
        Args:
            prediction_error: 预测误差
            entropy: 熵（不确定性的度量）
            complexity: 模型复杂度
        
        Returns:
            自由能值
        """
        return prediction_error + complexity - entropy


class BayesianPosterior:
    """贝叶斯后验分布"""
    
    def __init__(self):
        self.beliefs: Dict[str, float] = {}  # 信念: 概率
        self.priors: Dict[str, float] = {}    # 先验概率
        self.likelihoods: Dict[str, float] = {}  # 似然度
    
    def update(self, evidence: Dict[str, Any]):
        """根据证据更新后验概率"""
        # 过滤出数值类型的证据值
        numeric_evidence = {k: v for k, v in evidence.items() if isinstance(v, (int, float))}
        total_evidence = sum(numeric_evidence.values()) if numeric_evidence else 1.0
        
        for belief, prior in self.priors.items():
            likelihood = numeric_evidence.get(belief, 1.0) / total_evidence
            self.likelihoods[belief] = likelihood
            self.beliefs[belief] = (prior * likelihood) / total_evidence
        
        # 归一化
        total = sum(self.beliefs.values()) if self.beliefs else 1.0
        for belief in self.beliefs:
            self.beliefs[belief] /= total
    
    def get_most_likely(self) -> Optional[str]:
        """获取最可能的信念"""
        if not self.beliefs:
            return None
        return max(self.beliefs, key=self.beliefs.get)
    
    def get_entropy(self) -> float:
        """计算熵"""
        if not self.beliefs:
            return 0.0
        entropy = 0.0
        for prob in self.beliefs.values():
            if prob > 0:
                entropy -= prob * np.log2(prob)
        return entropy


class LifeEngine:
    """
    生命系统引擎 - 核心控制模块
    
    实现主动推理循环：
    1. 预测：根据当前信念生成预测
    2. 感知：获取感官输入
    3. 比较：计算预测误差
    4. 更新：最小化自由能，更新信念
    5. 行动：选择最小化预测误差的行动
    """
    
    def __init__(self):
        self.id = str(uuid.uuid4())[:8]
        self.birth_time = datetime.now()
        self.last_update = datetime.now()
        
        # 主动推理相关
        self.bayesian_posterior = BayesianPosterior()
        self.free_energy = 1.0  # 初始自由能
        self.prediction_error = 0.0
        self.belief_state = BeliefState.UNCERTAIN
        
        # 当前推理模式
        self.inference_mode = InferenceMode.PERCEPTION
        
        # 预测模型
        self.predictive_models: Dict[str, Any] = {}
        
        # 记忆系统
        self.short_term_memory: List[Dict] = []
        self.long_term_memory: Dict[str, Any] = {}
        
        # 目标和动机
        self.goals: List[Dict] = []
        self.current_goal: Optional[Dict] = None
        
        # 内部状态
        self.awareness_level = 0.0  # 意识水平 0-1
        self.focus_of_attention: Optional[str] = None
        
        # 学习率
        self.learning_rate = 0.01
        
        # 推理历史
        self.inference_history: List[Dict] = []
        
        # 系统状态
        self.is_alive = True
        self.health = 1.0  # 健康状态 0-1
    
    async def run_inference_cycle(self) -> Dict[str, Any]:
        """
        运行主动推理循环
        
        返回:
            推理结果包含自由能、预测误差、信念状态等
        """
        # 1. 生成预测
        predictions = await self._generate_predictions()
        
        # 2. 获取感官输入
        sensory_input = await self._get_sensory_input()
        
        # 3. 计算预测误差
        self.prediction_error = await self._calculate_prediction_error(predictions, sensory_input)
        
        # 4. 更新信念（最小化自由能）
        await self._update_beliefs(sensory_input)
        
        # 5. 选择行动
        action = await self._select_action()
        
        # 6. 更新意识水平
        self._update_awareness()
        
        # 记录推理历史
        self.inference_history.append({
            'timestamp': datetime.now(),
            'free_energy': self.free_energy,
            'prediction_error': self.prediction_error,
            'belief_state': self.belief_state.value,
            'action': action,
            'awareness_level': self.awareness_level
        })
        
        return {
            'free_energy': self.free_energy,
            'prediction_error': self.prediction_error,
            'belief_state': self.belief_state.value,
            'action': action,
            'awareness_level': self.awareness_level
        }
    
    async def _generate_predictions(self) -> Dict[str, Any]:
        """生成预测"""
        predictions = {}
        
        # 根据当前信念和目标生成预测
        for model_name, model in self.predictive_models.items():
            predictions[model_name] = model.predict()
        
        # 添加默认预测
        if self.current_goal:
            predictions['goal_progress'] = self._predict_goal_progress()
        
        return predictions
    
    def _predict_goal_progress(self) -> float:
        """预测目标进度"""
        if not self.current_goal:
            return 0.0
        
        progress = self.current_goal.get('progress', 0.0)
        confidence = self.current_goal.get('confidence', 0.5)
        
        return min(1.0, progress + confidence * 0.01)
    
    async def _get_sensory_input(self) -> Dict[str, Any]:
        """获取感官输入"""
        # 这是一个抽象方法，实际实现需要连接感知细胞
        return {
            'timestamp': datetime.now(),
            'input_type': 'abstract',
            'data': {}
        }
    
    async def _calculate_prediction_error(self, predictions: Dict, sensory_input: Dict) -> float:
        """计算预测误差"""
        error = 0.0
        total_predictions = len(predictions)
        
        if total_predictions == 0:
            return 0.0
        
        for key, prediction in predictions.items():
            # 简化的误差计算
            error += abs(prediction - 0.5)  # 假设期望是0.5
        
        self.prediction_error = error / total_predictions
        
        # 计算自由能
        entropy = self.bayesian_posterior.get_entropy()
        self.free_energy = FreeEnergyCalculator.calculate(
            prediction_error=self.prediction_error,
            entropy=entropy,
            complexity=0.1
        )
        
        return self.prediction_error
    
    async def _update_beliefs(self, evidence: Dict[str, Any]):
        """更新信念"""
        # 设置先验（基于历史经验）
        self.bayesian_posterior.priors = {
            'environment_stable': 0.7,
            'goal_achievable': 0.6,
            'self_competent': 0.75
        }
        
        # 更新后验
        self.bayesian_posterior.update(evidence)
        
        # 更新信念状态
        self._update_belief_state()
    
    def _update_belief_state(self):
        """更新信念状态"""
        entropy = self.bayesian_posterior.get_entropy()
        max_belief = max(self.bayesian_posterior.beliefs.values(), default=0.5)
        
        if max_belief > 0.9:
            self.belief_state = BeliefState.CERTAIN
        elif max_belief > 0.7:
            self.belief_state = BeliefState.CONFIDENT
        elif entropy > 0.8:
            self.belief_state = BeliefState.CONFLICTED
        else:
            self.belief_state = BeliefState.UNCERTAIN
    
    async def _select_action(self) -> Optional[str]:
        """选择行动"""
        if self.prediction_error < 0.1:
            # 预测准确，维持现状
            return None
        
        # 根据自由能选择行动
        if self.free_energy > 0.5:
            # 高自由能，需要探索
            return 'explore'
        else:
            # 低自由能，利用现有知识
            return 'exploit'
    
    def _update_awareness(self):
        """更新意识水平"""
        # 意识水平与预测误差和自由能相关
        error_factor = 1.0 - self.prediction_error
        energy_factor = 1.0 - self.free_energy
        
        self.awareness_level = (error_factor + energy_factor) / 2
        self.awareness_level = max(0.0, min(1.0, self.awareness_level))
    
    def set_goal(self, goal: Dict):
        """设置目标"""
        goal['id'] = str(uuid.uuid4())[:8]
        goal['created_at'] = datetime.now()
        goal['progress'] = 0.0
        goal['confidence'] = 0.5
        self.goals.append(goal)
        self.current_goal = goal
    
    def learn_from_experience(self, experience: Dict):
        """从经验中学习"""
        # 更新长期记忆
        experience_id = experience.get('id', str(uuid.uuid4()))
        self.long_term_memory[experience_id] = experience
        
        # 更新预测模型
        self._update_predictive_models(experience)
    
    def _update_predictive_models(self, experience: Dict):
        """更新预测模型"""
        # 简化的学习机制
        if 'outcome' in experience:
            model_name = experience.get('context', 'default')
            if model_name not in self.predictive_models:
                self.predictive_models[model_name] = SimplePredictor()
            
            self.predictive_models[model_name].learn(experience)
    
    def reflect(self) -> Dict[str, Any]:
        """反思当前状态"""
        reflection = {
            'timestamp': datetime.now(),
            'free_energy': self.free_energy,
            'prediction_error': self.prediction_error,
            'belief_state': self.belief_state.value,
            'awareness_level': self.awareness_level,
            'health': self.health,
            'goals': len(self.goals),
            'memory_size': len(self.long_term_memory),
            'inference_cycles': len(self.inference_history)
        }
        
        return reflection
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            'id': self.id,
            'age': (datetime.now() - self.birth_time).total_seconds(),
            'is_alive': self.is_alive,
            'health': self.health,
            'awareness_level': self.awareness_level,
            'free_energy': self.free_energy,
            'belief_state': self.belief_state.value,
            'current_goal': self.current_goal.get('name') if self.current_goal else None
        }


class SimplePredictor:
    """简单预测器"""
    
    def __init__(self):
        self.history: List[float] = []
        self.learning_rate = 0.1
    
    def predict(self) -> float:
        """生成预测"""
        if not self.history:
            return 0.5
        
        # 简单的移动平均预测
        return sum(self.history[-10:]) / min(len(self.history), 10)
    
    def learn(self, experience: Dict):
        """学习经验"""
        outcome = experience.get('outcome', 0.5)
        self.history.append(outcome)
        
        # 限制历史长度
        if len(self.history) > 100:
            self.history = self.history[-100:]


class NeuralSymbolicIntegrator:
    """
    神经符号AI整合器
    
    结合：
    - 神经网络的模式学习能力
    - 符号逻辑的精确推理能力
    """
    
    def __init__(self):
        self.symbolic_knowledge: Dict[str, Any] = {}
        self.neural_patterns: Dict[str, List[float]] = {}
    
    def add_symbolic_rule(self, rule_name: str, condition: Callable, action: Callable):
        """添加符号规则"""
        self.symbolic_knowledge[rule_name] = {
            'condition': condition,
            'action': action
        }
    
    def add_neural_pattern(self, pattern_name: str, features: List[float]):
        """添加神经模式"""
        if pattern_name not in self.neural_patterns:
            self.neural_patterns[pattern_name] = []
        self.neural_patterns[pattern_name].append(features)
    
    def infer(self, input_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        执行神经符号推理
        
        1. 使用神经网络检测模式
        2. 使用符号规则进行推理
        3. 结合两者的结果
        """
        results = []
        
        # 符号推理
        for rule_name, rule in self.symbolic_knowledge.items():
            if rule['condition'](input_data):
                result = rule['action'](input_data)
                results.append({
                    'type': 'symbolic',
                    'rule': rule_name,
                    'result': result
                })
        
        # 模式匹配
        for pattern_name, patterns in self.neural_patterns.items():
            if self._match_pattern(input_data, pattern_name):
                results.append({
                    'type': 'neural',
                    'pattern': pattern_name,
                    'confidence': self._calculate_pattern_confidence(input_data, pattern_name)
                })
        
        return results
    
    def _match_pattern(self, input_data: Dict, pattern_name: str) -> bool:
        """匹配模式"""
        patterns = self.neural_patterns.get(pattern_name, [])
        if not patterns:
            return False
        
        # 简化的模式匹配
        input_features = self._extract_features(input_data)
        for pattern in patterns:
            similarity = self._calculate_similarity(input_features, pattern)
            if similarity > 0.8:
                return True
        
        return False
    
    def _extract_features(self, input_data: Dict) -> List[float]:
        """提取特征"""
        features = []
        for key in sorted(input_data.keys()):
            value = input_data[key]
            if isinstance(value, (int, float)):
                features.append(value)
            elif isinstance(value, str):
                features.append(hash(value) % 1000 / 1000)
        return features
    
    def _calculate_similarity(self, features1: List[float], features2: List[float]) -> float:
        """计算相似度"""
        if len(features1) != len(features2):
            return 0.0
        
        if not features1:
            return 0.0
        
        diffs = [abs(f1 - f2) for f1, f2 in zip(features1, features2)]
        return 1.0 - (sum(diffs) / len(diffs))
    
    def _calculate_pattern_confidence(self, input_data: Dict, pattern_name: str) -> float:
        """计算模式匹配置信度"""
        patterns = self.neural_patterns.get(pattern_name, [])
        if not patterns:
            return 0.0
        
        input_features = self._extract_features(input_data)
        similarities = []
        
        for pattern in patterns:
            similarity = self._calculate_similarity(input_features, pattern)
            similarities.append(similarity)
        
        return sum(similarities) / len(similarities)