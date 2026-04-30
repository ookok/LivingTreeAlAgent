"""
长程掌握算法 (Long-term Mastery Algorithm)

核心功能：
1. 记忆曲线模型 - 基于艾宾浩斯遗忘曲线的改进算法
2. 非线性学习支持 - 处理非连续学习场景
3. 知识衰减解决方案 - 预测和缓解知识遗忘
4. 长期知识保持 - 优化检索和复习策略

参考 Wondering 的长程掌握算法设计
"""

import math
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class MemoryTrace:
    """记忆痕迹"""
    node_id: str
    user_id: str
    last_access_time: float
    access_count: int
    strength: float = 1.0  # 记忆强度 0-1
    stability: float = 1.0  # 记忆稳定性
    last_mastery_score: float = 0.0
    decay_rate: float = 0.01  # 衰减率


@dataclass
class ForgettingCurvePrediction:
    """遗忘曲线预测"""
    node_id: str
    user_id: str
    predicted_strength: float
    time_points: List[float]  # 时间点列表
    strength_points: List[float]  # 对应时间点的强度
    optimal_review_time: float
    half_life_days: float


@dataclass
class MasteryState:
    """掌握状态"""
    node_id: str
    user_id: str
    level: str = "unknown"  # unknown, introduced, familiar, proficient, mastered
    confidence: float = 0.0
    last_practiced: float = 0.0
    next_review: float = 0.0


class LongTermMasteryAlgorithm:
    """长程掌握算法"""
    
    MASTERY_LEVELS = {
        "unknown": {"label": "未知", "threshold": 0},
        "introduced": {"label": "初识", "threshold": 0.2},
        "familiar": {"label": "熟悉", "threshold": 0.4},
        "proficient": {"label": "熟练", "threshold": 0.7},
        "mastered": {"label": "精通", "threshold": 0.9}
    }
    
    DECAY_PARAMETERS = {
        "base_decay_rate": 0.01,      # 基础衰减率
        "stability_factor": 0.5,      # 稳定性影响因子
        "strength_factor": 0.3,       # 强度影响因子
        "practice_boost": 0.2,        # 练习提升量
        "stability_boost": 0.1        # 稳定性提升量
    }
    
    def __init__(self):
        self._logger = logger.bind(component="LongTermMasteryAlgorithm")
        self._memory_traces: Dict[str, MemoryTrace] = {}  # key: user_id_node_id
        
        self._logger.info("长程掌握算法初始化完成")
    
    def _get_trace_key(self, user_id: str, node_id: str) -> str:
        """生成记忆痕迹键"""
        return f"{user_id}_{node_id}"
    
    def record_access(self, user_id: str, node_id: str, mastery_score: float = 0.0):
        """
        记录知识访问
        
        Args:
            user_id: 用户ID
            node_id: 知识节点ID
            mastery_score: 掌握分数
        """
        key = self._get_trace_key(user_id, node_id)
        now = time.time()
        
        if key in self._memory_traces:
            trace = self._memory_traces[key]
            
            # 更新访问计数和时间
            trace.access_count += 1
            trace.last_access_time = now
            trace.last_mastery_score = mastery_score
            
            # 更新记忆强度（基于练习提升）
            trace.strength = min(1.0, trace.strength + self.DECAY_PARAMETERS["practice_boost"])
            
            # 更新稳定性（随着练习次数增加）
            trace.stability = min(1.0, trace.stability + self.DECAY_PARAMETERS["stability_boost"] * math.log(trace.access_count + 1))
            
            # 根据掌握分数调整衰减率
            trace.decay_rate = self._calculate_decay_rate(trace, mastery_score)
            
            self._logger.debug(f"更新记忆痕迹: {key} - 强度: {trace.strength:.2f}")
        else:
            # 创建新的记忆痕迹
            trace = MemoryTrace(
                node_id=node_id,
                user_id=user_id,
                last_access_time=now,
                access_count=1,
                strength=0.5 + mastery_score * 0.5,
                stability=0.3,
                last_mastery_score=mastery_score,
                decay_rate=self._calculate_initial_decay_rate(mastery_score)
            )
            self._memory_traces[key] = trace
            
            self._logger.debug(f"创建记忆痕迹: {key}")
    
    def _calculate_decay_rate(self, trace: MemoryTrace, mastery_score: float) -> float:
        """计算衰减率"""
        base_rate = self.DECAY_PARAMETERS["base_decay_rate"]
        
        # 掌握分数越高，衰减越慢
        score_factor = 1.0 - mastery_score * 0.5
        
        # 稳定性越高，衰减越慢
        stability_factor = 1.0 - trace.stability * 0.3
        
        # 访问次数越多，衰减越慢
        access_factor = max(0.3, 1.0 - math.log(trace.access_count + 1) * 0.1)
        
        return base_rate * score_factor * stability_factor * access_factor
    
    def _calculate_initial_decay_rate(self, mastery_score: float) -> float:
        """计算初始衰减率"""
        return self.DECAY_PARAMETERS["base_decay_rate"] * (1.0 - mastery_score * 0.3)
    
    def predict_forgetting_curve(self, user_id: str, node_id: str, 
                                prediction_days: int = 30) -> ForgettingCurvePrediction:
        """
        预测遗忘曲线
        
        Args:
            user_id: 用户ID
            node_id: 知识节点ID
            prediction_days: 预测天数
        
        Returns:
            遗忘曲线预测
        """
        key = self._get_trace_key(user_id, node_id)
        
        if key not in self._memory_traces:
            # 如果没有记忆痕迹，返回默认预测
            return ForgettingCurvePrediction(
                node_id=node_id,
                user_id=user_id,
                predicted_strength=0.5,
                time_points=[0],
                strength_points=[0.5],
                optimal_review_time=time.time() + 86400,  # 1天后
                half_life_days=1
            )
        
        trace = self._memory_traces[key]
        now = time.time()
        
        # 计算时间点和对应的强度
        time_points = []
        strength_points = []
        optimal_review_time = now
        target_strength = 0.7  # 最佳复习时机的目标强度
        
        # 模拟未来30天的遗忘曲线
        for day in range(prediction_days + 1):
            elapsed_hours = day * 24
            time_point = now + elapsed_hours * 3600
            strength = self._predict_strength(trace, elapsed_hours)
            
            time_points.append(time_point)
            strength_points.append(strength)
            
            # 找到强度降到目标值以下的时间点（最佳复习时机）
            if strength < target_strength and optimal_review_time == now:
                optimal_review_time = time_point
        
        # 计算半衰期
        half_life_days = self._calculate_half_life(trace)
        
        return ForgettingCurvePrediction(
            node_id=node_id,
            user_id=user_id,
            predicted_strength=strength_points[-1],
            time_points=time_points,
            strength_points=strength_points,
            optimal_review_time=optimal_review_time,
            half_life_days=half_life_days
        )
    
    def _predict_strength(self, trace: MemoryTrace, elapsed_hours: float) -> float:
        """预测经过一定时间后的记忆强度"""
        # 改进的艾宾浩斯遗忘曲线公式
        # 考虑记忆强度、稳定性和衰减率的综合影响
        
        # 基础衰减
        base_decay = math.exp(-trace.decay_rate * elapsed_hours)
        
        # 稳定性影响
        stability_effect = math.pow(trace.stability, elapsed_hours / 24)
        
        # 非线性衰减因子（考虑学习曲线）
        nonlinear_factor = 1.0 - (1.0 - trace.strength) * math.pow(elapsed_hours / 168, 0.5)
        
        # 综合计算
        predicted_strength = trace.strength * base_decay * stability_effect * nonlinear_factor
        
        return max(0.01, min(1.0, predicted_strength))
    
    def _calculate_half_life(self, trace: MemoryTrace) -> float:
        """计算记忆半衰期（天数）"""
        if trace.decay_rate <= 0:
            return 365  # 默认一年
        
        # 半衰期 = ln(2) / 衰减率（转换为天数）
        return math.log(2) / (trace.decay_rate * 24)
    
    def get_mastery_state(self, user_id: str, node_id: str) -> MasteryState:
        """
        获取知识掌握状态
        
        Args:
            user_id: 用户ID
            node_id: 知识节点ID
        
        Returns:
            掌握状态
        """
        key = self._get_trace_key(user_id, node_id)
        
        if key not in self._memory_traces:
            return MasteryState(
                node_id=node_id,
                user_id=user_id,
                level="unknown",
                confidence=0.0
            )
        
        trace = self._memory_traces[key]
        
        # 预测当前强度（考虑时间衰减）
        elapsed_hours = (time.time() - trace.last_access_time) / 3600
        current_strength = self._predict_strength(trace, elapsed_hours)
        
        # 确定掌握等级
        level = self._determine_mastery_level(current_strength)
        
        # 计算下次复习时间
        prediction = self.predict_forgetting_curve(user_id, node_id, 7)
        next_review = prediction.optimal_review_time
        
        return MasteryState(
            node_id=node_id,
            user_id=user_id,
            level=level,
            confidence=current_strength,
            last_practiced=trace.last_access_time,
            next_review=next_review
        )
    
    def _determine_mastery_level(self, strength: float) -> str:
        """根据强度确定掌握等级"""
        levels = list(self.MASTERY_LEVELS.keys())
        
        for level in reversed(levels):
            if strength >= self.MASTERY_LEVELS[level]["threshold"]:
                return level
        
        return "unknown"
    
    def optimize_retrieval(self, user_id: str, node_ids: List[str]) -> List[str]:
        """
        优化检索顺序
        
        根据记忆强度和需要复习的紧急程度排序知识节点
        
        Args:
            user_id: 用户ID
            node_ids: 知识节点ID列表
        
        Returns:
            优化后的节点顺序
        """
        now = time.time()
        scored_nodes = []
        
        for node_id in node_ids:
            key = self._get_trace_key(user_id, node_id)
            
            if key in self._memory_traces:
                trace = self._memory_traces[key]
                
                # 计算当前强度（考虑时间衰减）
                elapsed_hours = (now - trace.last_access_time) / 3600
                current_strength = self._predict_strength(trace, elapsed_hours)
                
                # 计算优先级分数
                # - 低强度的节点优先级更高（需要复习）
                # - 访问次数少的节点优先级更高
                priority = (1.0 - current_strength) * 0.6 + (1.0 / (trace.access_count + 1)) * 0.4
                
                scored_nodes.append((node_id, priority))
            else:
                # 从未访问过的节点，优先级中等
                scored_nodes.append((node_id, 0.5))
        
        # 按优先级排序（降序）
        scored_nodes.sort(key=lambda x: x[1], reverse=True)
        
        return [node_id for node_id, _ in scored_nodes]
    
    def get_user_memory_summary(self, user_id: str) -> Dict:
        """
        获取用户记忆摘要
        
        Args:
            user_id: 用户ID
        
        Returns:
            记忆摘要
        """
        user_traces = [t for t in self._memory_traces.values() if t.user_id == user_id]
        
        if not user_traces:
            return {
                "user_id": user_id,
                "total_nodes": 0,
                "average_strength": 0.0,
                "mastery_distribution": {level: 0 for level in self.MASTERY_LEVELS},
                "needs_review": 0
            }
        
        now = time.time()
        total_strength = 0.0
        mastery_distribution = {level: 0 for level in self.MASTERY_LEVELS}
        needs_review = 0
        
        for trace in user_traces:
            elapsed_hours = (now - trace.last_access_time) / 3600
            current_strength = self._predict_strength(trace, elapsed_hours)
            total_strength += current_strength
            
            level = self._determine_mastery_level(current_strength)
            mastery_distribution[level] += 1
            
            # 强度低于0.5需要复习
            if current_strength < 0.5:
                needs_review += 1
        
        return {
            "user_id": user_id,
            "total_nodes": len(user_traces),
            "average_strength": total_strength / len(user_traces),
            "mastery_distribution": {
                level: {"count": count, "label": self.MASTERY_LEVELS[level]["label"]}
                for level, count in mastery_distribution.items()
            },
            "needs_review": needs_review
        }
    
    def forget_node(self, user_id: str, node_id: str):
        """
        遗忘知识节点
        
        Args:
            user_id: 用户ID
            node_id: 知识节点ID
        """
        key = self._get_trace_key(user_id, node_id)
        if key in self._memory_traces:
            del self._memory_traces[key]
            self._logger.debug(f"遗忘知识节点: {key}")


# 单例模式
_long_term_mastery_instance = None

def get_long_term_mastery() -> LongTermMasteryAlgorithm:
    """获取长程掌握算法实例"""
    global _long_term_mastery_instance
    if _long_term_mastery_instance is None:
        _long_term_mastery_instance = LongTermMasteryAlgorithm()
    return _long_term_mastery_instance


if __name__ == "__main__":
    print("=" * 60)
    print("长程掌握算法测试")
    print("=" * 60)
    
    mastery = get_long_term_mastery()
    
    # 1. 记录知识访问
    print("\n[1] 记录知识访问")
    mastery.record_access("user_001", "node_python", 0.8)
    mastery.record_access("user_001", "node_ml", 0.6)
    mastery.record_access("user_001", "node_deeplearning", 0.4)
    mastery.record_access("user_001", "node_python", 0.9)  # 再次访问
    print("知识访问记录完成")
    
    # 2. 预测遗忘曲线
    print("\n[2] 预测遗忘曲线")
    prediction = mastery.predict_forgetting_curve("user_001", "node_python", 7)
    print(f"节点ID: {prediction.node_id}")
    print(f"预测强度: {prediction.predicted_strength:.2f}")
    print(f"半衰期: {prediction.half_life_days:.1f} 天")
    print(f"最佳复习时间: {time.strftime('%Y-%m-%d %H:%M', time.localtime(prediction.optimal_review_time))}")
    
    # 3. 获取掌握状态
    print("\n[3] 获取掌握状态")
    state = mastery.get_mastery_state("user_001", "node_python")
    print(f"节点ID: {state.node_id}")
    print(f"掌握等级: {state.level} ({mastery.MASTERY_LEVELS[state.level]['label']})")
    print(f"置信度: {state.confidence:.2f}")
    print(f"下次复习: {time.strftime('%Y-%m-%d %H:%M', time.localtime(state.next_review))}")
    
    # 4. 优化检索顺序
    print("\n[4] 优化检索顺序")
    node_ids = ["node_ml", "node_python", "node_deeplearning", "node_new"]
    optimized = mastery.optimize_retrieval("user_001", node_ids)
    print(f"原始顺序: {node_ids}")
    print(f"优化顺序: {optimized}")
    
    # 5. 获取用户记忆摘要
    print("\n[5] 获取用户记忆摘要")
    summary = mastery.get_user_memory_summary("user_001")
    print(f"用户ID: {summary['user_id']}")
    print(f"总节点数: {summary['total_nodes']}")
    print(f"平均强度: {summary['average_strength']:.2f}")
    print(f"需要复习: {summary['needs_review']} 个")
    print("掌握分布:")
    for level, info in summary['mastery_distribution'].items():
        print(f"  {info['label']}: {info['count']} 个")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)