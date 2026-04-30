"""
智能任务路由器
Intelligent Task Router

基于 RouteLLM 的路由算法，实现智能任务路由和资源优化
from __future__ import annotations
"""


import asyncio
import logging
import time
from typing import Dict, List, Optional, Set, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from business.enterprise.node_manager import EnterpriseNode
from business.enterprise.task_scheduler import EnterpriseTask, TaskType, TaskState

logger = logging.getLogger(__name__)


class TaskComplexity(Enum):
    """任务复杂度"""
    LOW = 1      # 低复杂度
    MEDIUM = 2   # 中等复杂度
    HIGH = 3     # 高复杂度
    VERY_HIGH = 4  # 极高复杂度


class NodeCapabilityLevel(Enum):
    """节点能力等级"""
    BASIC = 1     # 基础能力
    STANDARD = 2  # 标准能力
    ADVANCED = 3  # 高级能力
    PREMIUM = 4   #  premium 能力


@dataclass
class TaskFeature:
    """任务特征"""
    complexity: TaskComplexity
    required_skills: List[str]
    resource_demand: Dict[str, float]  # CPU, memory, storage, bandwidth
    estimated_duration: float  # 预估执行时间（秒）
    priority: int


@dataclass
class NodeProfile:
    """节点配置文件"""
    node_id: str
    capability_level: NodeCapabilityLevel
    available_resources: Dict[str, float]  # 可用资源
    skills: List[str]  # 节点具备的技能
    historical_performance: Dict[str, float]  # 历史性能数据
    cost_per_hour: float  # 每小时成本


class RouterBase(ABC):
    """路由器基类"""
    
    @abstractmethod
    def route_task(self, task: EnterpriseTask, nodes: List[EnterpriseNode]) -> Optional[str]:
        """路由任务到合适的节点"""
        pass


class SimilarityWeightedRouter(RouterBase):
    """相似度加权路由器
    基于任务与节点历史任务的相似度进行加权评分"""
    
    def __init__(self):
        self.history: Dict[str, List[Tuple[TaskFeature, float]]] = {}  # 节点ID -> [(任务特征, 性能评分)]
    
    def route_task(self, task: EnterpriseTask, nodes: List[EnterpriseNode]) -> Optional[str]:
        """路由任务"""
        if not nodes:
            return None
        
        # 计算任务特征
        task_feature = self._extract_task_feature(task)
        
        # 为每个节点计算得分
        scores = []
        for node in nodes:
            score = self._calculate_node_score(node, task_feature)
            scores.append((node.node_id, score))
        
        # 选择得分最高的节点
        if scores:
            scores.sort(key=lambda x: x[1], reverse=True)
            return scores[0][0]
        
        return None
    
    def _extract_task_feature(self, task: EnterpriseTask) -> TaskFeature:
        """提取任务特征"""
        # 基于任务类型和资源需求评估复杂度
        complexity_map = {
            TaskType.STORAGE: TaskComplexity.LOW,
            TaskType.NETWORK: TaskComplexity.MEDIUM,
            TaskType.COMPUTING: TaskComplexity.HIGH,
            TaskType.MAINTENANCE: TaskComplexity.LOW,
            TaskType.CUSTOM: TaskComplexity.MEDIUM
        }
        
        complexity = complexity_map.get(task.task_type, TaskComplexity.MEDIUM)
        
        # 基于资源需求调整复杂度
        if task.required_cpu > 4.0 or task.required_memory > 8192:
            complexity = TaskComplexity.VERY_HIGH
        elif task.required_cpu > 2.0 or task.required_memory > 4096:
            complexity = TaskComplexity.HIGH
        
        # 提取技能需求
        skills = []
        if task.task_type == TaskType.COMPUTING:
            skills.append("computing")
        elif task.task_type == TaskType.STORAGE:
            skills.append("storage")
        elif task.task_type == TaskType.NETWORK:
            skills.append("network")
        
        resource_demand = {
            "cpu": task.required_cpu,
            "memory": task.required_memory,
            "storage": task.required_storage,
            "bandwidth": task.required_bandwidth
        }
        
        return TaskFeature(
            complexity=complexity,
            required_skills=skills,
            resource_demand=resource_demand,
            estimated_duration=300.0,  # 默认5分钟
            priority=task.priority
        )
    
    def _calculate_node_score(self, node: EnterpriseNode, task_feature: TaskFeature) -> float:
        """计算节点得分"""
        # 基础得分：基于节点能力等级
        base_score = node.capability.uptime * 0.3
        
        # 资源匹配得分
        resource_score = self._calculate_resource_score(node, task_feature.resource_demand)
        
        # 技能匹配得分
        skill_score = self._calculate_skill_score(node, task_feature.required_skills)
        
        # 历史性能得分
        history_score = self._calculate_history_score(node.node_id, task_feature)
        
        # 成本优化得分（成本越低得分越高）
        cost_score = self._calculate_cost_score(node)
        
        # 综合得分
        total_score = (
            base_score * 0.2 +
            resource_score * 0.3 +
            skill_score * 0.2 +
            history_score * 0.2 +
            cost_score * 0.1
        )
        
        return total_score
    
    def _calculate_resource_score(self, node: EnterpriseNode, resource_demand: Dict[str, float]) -> float:
        """计算资源匹配得分"""
        score = 1.0
        
        # 检查CPU
        if resource_demand.get("cpu", 0) > 0:
            cpu_ratio = min(1.0, node.capability.cpu_available / resource_demand["cpu"])
            score *= cpu_ratio
        
        # 检查内存
        if resource_demand.get("memory", 0) > 0:
            memory_ratio = min(1.0, node.capability.memory_available / resource_demand["memory"])
            score *= memory_ratio
        
        # 检查存储
        if resource_demand.get("storage", 0) > 0:
            storage_ratio = min(1.0, node.capability.storage_available / resource_demand["storage"])
            score *= storage_ratio
        
        # 检查带宽
        if resource_demand.get("bandwidth", 0) > 0:
            bandwidth_ratio = min(1.0, node.capability.bandwidth / resource_demand["bandwidth"])
            score *= bandwidth_ratio
        
        return score
    
    def _calculate_skill_score(self, node: EnterpriseNode, required_skills: List[str]) -> float:
        """计算技能匹配得分"""
        if not required_skills:
            return 1.0
        
        # 简化处理：基于节点标签和角色判断技能
        node_skills = []
        if node.role == "master":
            node_skills.extend(["management", "coordination"])
        elif node.role == "worker":
            node_skills.extend(["computing", "processing"])
        elif node.role == "storage":
            node_skills.extend(["storage", "data_management"])
        
        # 添加标签作为技能
        node_skills.extend(node.tags)
        
        # 计算匹配度
        matched_skills = set(required_skills) & set(node_skills)
        return len(matched_skills) / len(required_skills)
    
    def _calculate_history_score(self, node_id: str, task_feature: TaskFeature) -> float:
        """计算历史性能得分"""
        if node_id not in self.history:
            return 0.5  # 默认得分
        
        # 查找相似任务的历史性能
        similar_tasks = []
        for history_task, performance in self.history[node_id]:
            similarity = self._calculate_task_similarity(history_task, task_feature)
            if similarity > 0.5:
                similar_tasks.append((similarity, performance))
        
        if not similar_tasks:
            return 0.5
        
        # 加权平均
        total_weight = sum(similarity for similarity, _ in similar_tasks)
        weighted_score = sum(similarity * performance for similarity, performance in similar_tasks)
        
        return weighted_score / total_weight
    
    def _calculate_task_similarity(self, task1: TaskFeature, task2: TaskFeature) -> float:
        """计算任务相似度"""
        # 复杂度相似度
        complexity_similarity = 1.0 - abs(task1.complexity.value - task2.complexity.value) / 3
        
        # 技能相似度
        common_skills = set(task1.required_skills) & set(task2.required_skills)
        total_skills = set(task1.required_skills) | set(task2.required_skills)
        skill_similarity = len(common_skills) / len(total_skills) if total_skills else 1.0
        
        # 资源需求相似度
        resource_similarity = 0.0
        resources = set(task1.resource_demand.keys()) | set(task2.resource_demand.keys())
        if resources:
            diff_sum = 0
            for resource in resources:
                val1 = task1.resource_demand.get(resource, 0)
                val2 = task2.resource_demand.get(resource, 0)
                max_val = max(val1, val2, 1)
                diff_sum += abs(val1 - val2) / max_val
            resource_similarity = 1.0 - (diff_sum / len(resources))
        else:
            resource_similarity = 1.0
        
        # 综合相似度
        return (complexity_similarity * 0.4 + skill_similarity * 0.3 + resource_similarity * 0.3)
    
    def _calculate_cost_score(self, node: EnterpriseNode) -> float:
        """计算成本得分"""
        # 简化处理：基于资源利用率计算成本效率
        total_storage = node.storage_allocated + node.capability.storage_available
        storage_utilization = node.storage_used / total_storage if total_storage > 0 else 0
        
        # 资源利用率越高，成本效率越高
        cost_efficiency = (storage_utilization + 0.5) / 1.5  # 归一化到0-1
        
        return cost_efficiency
    
    def update_history(self, node_id: str, task: EnterpriseTask, performance: float):
        """更新历史性能数据"""
        if node_id not in self.history:
            self.history[node_id] = []
        
        task_feature = self._extract_task_feature(task)
        self.history[node_id].append((task_feature, performance))
        
        # 限制历史记录数量
        if len(self.history[node_id]) > 100:
            self.history[node_id] = self.history[node_id][-100:]


class MatrixFactorizationRouter(RouterBase):
    """矩阵分解路由器
    基于偏好数据训练的矩阵分解模型"""
    
    def __init__(self):
        # 简化实现：使用基于规则的评分
        self.similarity_router = SimilarityWeightedRouter()
    
    def route_task(self, task: EnterpriseTask, nodes: List[EnterpriseNode]) -> Optional[str]:
        """路由任务"""
        # 简化实现：使用相似度加权路由器
        return self.similarity_router.route_task(task, nodes)


class AITaskRouter(RouterBase):
    """AI任务专用路由器
    针对不同复杂度的AI任务进行智能路由"""
    
    def __init__(self):
        self.similarity_router = SimilarityWeightedRouter()
    
    def route_task(self, task: EnterpriseTask, nodes: List[EnterpriseNode]) -> Optional[str]:
        """路由任务"""
        # 检查是否为AI相关任务
        if task.task_type == TaskType.COMPUTING and "ai" in task.title.lower():
            # 基于AI任务复杂度进行路由
            return self._route_ai_task(task, nodes)
        else:
            # 使用通用路由
            return self.similarity_router.route_task(task, nodes)
    
    def _route_ai_task(self, task: EnterpriseTask, nodes: List[EnterpriseNode]) -> Optional[str]:
        """路由AI任务"""
        # 评估AI任务复杂度
        ai_complexity = self._evaluate_ai_complexity(task)
        
        # 筛选适合的节点
        suitable_nodes = []
        for node in nodes:
            if self._is_node_suitable_for_ai(node, ai_complexity):
                suitable_nodes.append(node)
        
        if not suitable_nodes:
            return None
        
        # 使用相似度路由器选择最佳节点
        return self.similarity_router.route_task(task, suitable_nodes)
    
    def _evaluate_ai_complexity(self, task: EnterpriseTask) -> TaskComplexity:
        """评估AI任务复杂度"""
        # 基于资源需求评估
        if task.required_cpu > 8.0 or task.required_memory > 16384:
            return TaskComplexity.VERY_HIGH
        elif task.required_cpu > 4.0 or task.required_memory > 8192:
            return TaskComplexity.HIGH
        elif task.required_cpu > 2.0 or task.required_memory > 4096:
            return TaskComplexity.MEDIUM
        else:
            return TaskComplexity.LOW
    
    def _is_node_suitable_for_ai(self, node: EnterpriseNode, complexity: TaskComplexity) -> bool:
        """检查节点是否适合AI任务"""
        # 基于节点能力和资源检查
        if complexity == TaskComplexity.VERY_HIGH:
            return (node.capability.cpu_available >= 8.0 and 
                    node.capability.memory_available >= 16384 and
                    "ai" in node.tags)
        elif complexity == TaskComplexity.HIGH:
            return (node.capability.cpu_available >= 4.0 and 
                    node.capability.memory_available >= 8192)
        elif complexity == TaskComplexity.MEDIUM:
            return (node.capability.cpu_available >= 2.0 and 
                    node.capability.memory_available >= 4096)
        else:
            return True


class IntelligentTaskRouter:
    """智能任务路由器
    整合多种路由策略"""
    
    def __init__(self):
        self.routers = {
            "sw_ranking": SimilarityWeightedRouter(),
            "mf": MatrixFactorizationRouter(),
            "ai_specialized": AITaskRouter()
        }
        self.default_router = "sw_ranking"
    
    def route_task(self, task: EnterpriseTask, nodes: List[EnterpriseNode], router_type: str = None) -> Optional[str]:
        """路由任务"""
        if not nodes:
            return None
        
        # 选择路由器
        router_name = router_type or self.default_router
        router = self.routers.get(router_name, self.routers[self.default_router])
        
        # 执行路由
        node_id = router.route_task(task, nodes)
        
        return node_id
    
    def update_task_performance(self, node_id: str, task: EnterpriseTask, performance: float):
        """更新任务性能数据"""
        # 更新相似度路由器的历史数据
        if "sw_ranking" in self.routers:
            self.routers["sw_ranking"].update_history(node_id, task, performance)
    
    def get_router(self, router_type: str) -> Optional[RouterBase]:
        """获取指定类型的路由器"""
        return self.routers.get(router_type)


class CostOptimizer:
    """成本优化器
    基于 RouteLLM 的成本优化策略"""
    
    def __init__(self):
        self.cost_history: Dict[str, List[Tuple[EnterpriseTask, float, float]]] = {}  # 节点ID -> [(任务, 实际成本, 性能)]
    
    def optimize_resource_allocation(self, task: EnterpriseTask, nodes: List[EnterpriseNode]) -> List[Tuple[str, float]]:
        """优化资源分配
        返回节点ID和预计成本的列表，按成本从低到高排序"""
        if not nodes:
            return []
        
        # 为每个节点计算预计成本
        node_costs = []
        for node in nodes:
            estimated_cost = self._estimate_task_cost(task, node)
            if estimated_cost > 0:
                node_costs.append((node.node_id, estimated_cost))
        
        # 按成本排序
        node_costs.sort(key=lambda x: x[1])
        
        return node_costs
    
    def _estimate_task_cost(self, task: EnterpriseTask, node: EnterpriseNode) -> float:
        """估计任务成本"""
        # 基于资源需求和节点性能计算成本
        
        # 计算所需资源
        required_cpu = task.required_cpu or 0.1
        required_memory = task.required_memory or 128
        required_storage = task.required_storage or 0
        required_bandwidth = task.required_bandwidth or 0
        
        # 基于资源利用率计算成本系数
        cpu_utilization = required_cpu / node.capability.cpu_available if node.capability.cpu_available > 0 else 0
        memory_utilization = required_memory / node.capability.memory_available if node.capability.memory_available > 0 else 0
        
        # 计算基础成本
        base_cost = (required_cpu * 0.05 +  # CPU成本
                    required_memory * 0.001 +  # 内存成本
                    required_storage * 0.0001 +  # 存储成本
                    required_bandwidth * 0.01)  # 带宽成本
        
        # 基于利用率调整成本
        utilization_factor = 1.0
        if cpu_utilization > 0.8 or memory_utilization > 0.8:
            utilization_factor = 1.5  # 高利用率时成本增加
        elif cpu_utilization < 0.3 and memory_utilization < 0.3:
            utilization_factor = 0.8  # 低利用率时成本降低
        
        # 基于历史性能调整
        performance_factor = self._get_performance_factor(node.node_id, task)
        
        # 综合成本
        estimated_cost = base_cost * utilization_factor * performance_factor
        
        return estimated_cost
    
    def _get_performance_factor(self, node_id: str, task: EnterpriseTask) -> float:
        """获取性能因子"""
        if node_id not in self.cost_history:
            return 1.0
        
        # 查找相似任务的历史性能
        similar_tasks = []
        for history_task, cost, performance in self.cost_history[node_id]:
            if self._is_task_similar(history_task, task):
                similar_tasks.append((cost, performance))
        
        if not similar_tasks:
            return 1.0
        
        # 计算平均性能成本比
        avg_performance_cost_ratio = sum(performance / cost for cost, performance in similar_tasks) / len(similar_tasks)
        
        # 性能成本比越高，性能因子越低（成本越低）
        return max(0.5, 1.0 / (avg_performance_cost_ratio + 0.5))
    
    def _is_task_similar(self, task1: EnterpriseTask, task2: EnterpriseTask) -> bool:
        """判断任务是否相似"""
        # 基于任务类型和资源需求判断
        if task1.task_type != task2.task_type:
            return False
        
        # 资源需求相似度
        resource_similarity = True
        resources = ['required_cpu', 'required_memory', 'required_storage', 'required_bandwidth']
        for resource in resources:
            val1 = getattr(task1, resource, 0)
            val2 = getattr(task2, resource, 0)
            if val1 > 0 and val2 > 0:
                ratio = max(val1, val2) / min(val1, val2)
                if ratio > 2.0:
                    resource_similarity = False
                    break
        
        return resource_similarity
    
    def update_cost_history(self, node_id: str, task: EnterpriseTask, actual_cost: float, performance: float):
        """更新成本历史"""
        if node_id not in self.cost_history:
            self.cost_history[node_id] = []
        
        self.cost_history[node_id].append((task, actual_cost, performance))
        
        # 限制历史记录数量
        if len(self.cost_history[node_id]) > 50:
            self.cost_history[node_id] = self.cost_history[node_id][-50:]
    
    def get_cost_analysis(self, node_id: str) -> Dict[str, Any]:
        """获取成本分析"""
        if node_id not in self.cost_history:
            return {"node_id": node_id, "total_tasks": 0, "average_cost": 0}
        
        history = self.cost_history[node_id]
        total_cost = sum(cost for _, cost, _ in history)
        total_performance = sum(performance for _, _, performance in history)
        
        return {
            "node_id": node_id,
            "total_tasks": len(history),
            "average_cost": total_cost / len(history),
            "average_performance": total_performance / len(history),
            "cost_performance_ratio": total_cost / total_performance if total_performance > 0 else 0
        }


# 全局实例
intelligent_router = IntelligentTaskRouter()
cost_optimizer = CostOptimizer()


def get_intelligent_router() -> IntelligentTaskRouter:
    """获取智能任务路由器"""
    return intelligent_router


def get_cost_optimizer() -> CostOptimizer:
    """获取成本优化器"""
    return cost_optimizer
