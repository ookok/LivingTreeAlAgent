"""
任务积分估算器 (Task Estimator)
================================

根据任务规格和插件配置，计算任务的积分消耗。

核心逻辑：
1. 计算直接积分消耗（CPU、内存、API调用等）
2. 计算时间积分成本（用户等待时间的机会成本）
3. 综合评估任务的实际"总成本"
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import math

from .credit_registry import (
    CreditRegistry, PluginCreditProfile, UserCreditProfile,
    PluginType, TaskType, RegionLatency
)


@dataclass
class TaskSpec:
    """
    任务规格

    描述一个任务的完整属性，用于调度器决策。
    """
    task_id: str                          # 任务唯一标识
    task_type: TaskType                   # 任务类型
    input_length: int                     # 输入长度（字符数）
    input_data: Optional[Any] = None      # 输入数据
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据

    # 用户约束
    min_quality: int = 60                # 最低质量要求
    max_wait_time: float = 60.0          # 最大等待时间（秒）
    budget: float = 1000.0               # 任务预算
    preferred_region: str = "default"    # 偏好地域

    # 任务特性
    is_compliance_required: bool = False  # 是否强制合规（敏感任务）
    tags: List[str] = field(default_factory=list)  # 任务标签

    @property
    def length_kchar(self) -> float:
        """输入长度（千字符）"""
        return self.input_length / 1000


@dataclass
class EstimationResult:
    """
    估算结果

    包含单个插件对任务的完整成本估算。
    """
    plugin_id: str
    plugin_name: str
    task_id: str

    # 直接积分消耗
    direct_credits: float = 0.0          # 直接积分消耗
    base_cost: float = 0.0               # 基础消耗
    cpu_cost: float = 0.0                # CPU消耗
    mem_cost: float = 0.0                # 内存消耗
    api_cost: float = 0.0                # API消耗（per_kchar）
    network_cost: float = 0.0            # 网络传输消耗

    # 时间成本
    estimated_time_sec: float = 0.0      # 预估耗时（秒）
    time_credits: float = 0.0            # 时间积分成本
    region_latency_ms: float = 0.0       # 地域延迟

    # 质量
    quality_score: int = 0               # 质量分数

    # 综合
    total_credits: float = 0.0          # 总积分消耗
    is_feasible: bool = True             # 是否可行
    feasibility_reason: str = ""         # 不可行原因

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "plugin_name": self.plugin_name,
            "task_id": self.task_id,
            "direct_credits": self.direct_credits,
            "estimated_time_sec": self.estimated_time_sec,
            "time_credits": self.time_credits,
            "quality_score": self.quality_score,
            "total_credits": self.total_credits,
            "is_feasible": self.is_feasible,
            "feasibility_reason": self.feasibility_reason,
        }


class TaskEstimator:
    """
    任务积分估算器

    核心职责：根据任务规格和插件配置，计算任务的积分消耗。
    """

    def __init__(self, registry: Optional[CreditRegistry] = None):
        self.registry = registry or CreditRegistry.get_instance()

    def estimate(
        self,
        task: TaskSpec,
        plugin: PluginCreditProfile,
        user: Optional[UserCreditProfile] = None
    ) -> EstimationResult:
        """
        估算单个插件对任务的积分消耗

        Args:
            task: 任务规格
            plugin: 插件配置
            user: 用户配置（用于计算时间积分成本）

        Returns:
            估算结果
        """
        result = EstimationResult(
            plugin_id=plugin.plugin_id,
            plugin_name=plugin.name,
            task_id=task.task_id,
        )

        # 检查可行性
        feasible, reason = self._check_feasibility(task, plugin)
        if not feasible:
            result.is_feasible = False
            result.feasibility_reason = reason
            return result

        # 计算直接积分消耗
        result = self._calculate_direct_credits(task, plugin, result)

        # 计算时间成本
        result = self._calculate_time_cost(task, plugin, result)

        # 计算时间积分成本（用户等待的机会成本）
        if user:
            result.time_credits = result.estimated_time_sec * user.time_value_per_sec

        # 综合成本 = 直接消耗 + 时间成本
        result.total_credits = result.direct_credits + result.time_credits

        # 记录质量分数
        result.quality_score = plugin.capability.quality_score

        return result

    def estimate_batch(
        self,
        task: TaskSpec,
        plugins: List[PluginCreditProfile],
        user: Optional[UserCreditProfile] = None
    ) -> List[EstimationResult]:
        """
        批量估算 - 多个插件的积分消耗

        Args:
            task: 任务规格
            plugins: 插件列表
            user: 用户配置

        Returns:
            估算结果列表（按总积分升序）
        """
        results = []
        for plugin in plugins:
            result = self.estimate(task, plugin, user)
            results.append(result)

        # 按总积分升序排列
        results.sort(key=lambda x: x.total_credits)
        return results

    def find_best_plugin(
        self,
        task: TaskSpec,
        user: Optional[UserCreditProfile] = None
    ) -> Optional[EstimationResult]:
        """
        找到最佳插件（综合成本最低且满足约束）

        Args:
            task: 任务规格
            user: 用户配置

        Returns:
            最佳估算结果，如果没有满足条件的插件返回None
        """
        # 获取符合条件的插件
        plugins = self.registry.list_plugins(
            task_type=task.task_type,
            enabled_only=True,
            min_quality=task.min_quality
        )

        if not plugins:
            return None

        # 批量估算
        results = self.estimate_batch(task, plugins, user)

        # 过滤可行方案
        feasible_results = [r for r in results if r.is_feasible]

        if not feasible_results:
            return None

        # 按预算过滤
        budget_filtered = [
            r for r in feasible_results
            if r.total_credits <= task.budget
        ]

        if budget_filtered:
            return budget_filtered[0]  # 返回成本最低的

        # 如果没有满足预算的，返回最便宜的
        return feasible_results[0]

    def _check_feasibility(
        self,
        task: TaskSpec,
        plugin: PluginCreditProfile
    ) -> Tuple[bool, str]:
        """
        检查任务是否可以使用该插件执行

        Returns:
            (是否可行, 不可行原因)
        """
        # 检查输入长度
        if task.input_length > plugin.capability.max_input_length:
            return False, f"输入长度{task.input_length}超过插件上限{plugin.capability.max_input_length}"

        # 检查质量要求
        if plugin.capability.quality_score < task.min_quality:
            return False, f"质量分数{plugin.capability.quality_score}低于要求{task.min_quality}"

        # 检查等待时间
        estimated_time = self._estimate_time(task, plugin)
        if estimated_time > task.max_wait_time:
            return False, f"预估时间{estimated_time:.1f}秒超过最大等待时间{task.max_wait_time}秒"

        # 合规检查
        if task.is_compliance_required:
            if plugin.compliance.required:
                # 插件强制要求合规 - 检查是否允许
                if plugin.compliance.allowed_plugins:
                    if plugin.plugin_id not in plugin.compliance.allowed_plugins:
                        return False, f"合规限制：该插件不在允许列表中"
                if plugin.compliance.blocked_plugins:
                    if plugin.plugin_id in plugin.compliance.blocked_plugins:
                        return False, f"合规限制：该插件被禁用"
            else:
                # 任务要求合规，但插件不满足
                return False, "合规限制：该任务要求本地处理"

        return True, ""

    def _estimate_time(
        self,
        task: TaskSpec,
        plugin: PluginCreditProfile
    ) -> float:
        """估算处理时间"""
        base_time = task.length_kchar * plugin.capability.avg_time_sec_per_kchar

        # 加上地域延迟
        latency_sec = 0.0
        for region in plugin.region_latency:
            if region.region == "default":
                latency_sec = region.base_latency_ms / 1000
                break

        return base_time + latency_sec

    def _calculate_direct_credits(
        self,
        task: TaskSpec,
        plugin: PluginCreditProfile,
        result: EstimationResult
    ) -> EstimationResult:
        """计算直接积分消耗"""
        model = plugin.credit_model

        # 基础消耗
        result.base_cost = model.base
        result.direct_credits += model.base

        # API调用消耗（按字符数）
        if model.per_kchar > 0:
            result.api_cost = model.per_kchar * task.length_kchar
            result.direct_credits += result.api_cost

        # CPU消耗
        if plugin.plugin_type == PluginType.LOCAL_PLUGIN:
            estimated_time = self._estimate_time(task, plugin)
            result.estimated_time_sec = estimated_time
            result.cpu_cost = model.cpu_per_sec * estimated_time
            result.direct_credits += result.cpu_cost

            # 内存消耗（假设输入数据占用一定内存）
            estimated_mem_mb = task.input_length / 1000  # 简化为1字符=1KB
            result.mem_cost = model.mem_per_mb * estimated_mem_mb
            result.direct_credits += result.mem_cost

        # 网络传输消耗（外部API）
        if plugin.plugin_type == PluginType.EXTERNAL_API:
            # 估算网络传输量
            network_kb = task.input_length / 1000  # 输入
            output_length = int(task.input_length * 1.2)  # 估算输出略大
            network_kb += output_length / 1000  # 输出
            result.network_cost = model.network_per_kb * network_kb
            result.direct_credits += result.network_cost

            # 更新预估时间
            result.estimated_time_sec = self._estimate_time(task, plugin)

        return result

    def _calculate_time_cost(
        self,
        task: TaskSpec,
        plugin: PluginCreditProfile,
        result: EstimationResult
    ) -> EstimationResult:
        """计算地域延迟成本"""
        # 查找匹配的地域延迟
        for region in plugin.region_latency:
            if region.region == task.preferred_region or region.region == "default":
                result.region_latency_ms = region.base_latency_ms
                # 地域延迟的积分成本
                result.time_credits += region.base_latency_ms * region.credit_per_ms
                break

        return result

    def calculate_workflow_credits(
        self,
        task_specs: List[Tuple[str, TaskSpec]],  # [(node_id, task_spec), ...]
        plugin_assignments: Dict[str, str],       # {node_id: plugin_id}
        user: Optional[UserCreditProfile] = None
    ) -> Dict[str, Any]:
        """
        计算工作流（多插件编排）的总积分消耗

        Args:
            task_specs: 任务规格列表
            plugin_assignments: 节点到插件的映射
            user: 用户配置

        Returns:
            工作流总成本分析
        """
        total_direct = 0.0
        total_time = 0.0
        node_results = {}

        for node_id, task_spec in task_specs:
            plugin_id = plugin_assignments.get(node_id)
            if not plugin_id:
                continue

            plugin = self.registry.get_plugin(plugin_id)
            if not plugin:
                continue

            result = self.estimate(task_spec, plugin, user)
            node_results[node_id] = result
            total_direct += result.direct_credits
            total_time += result.time_credits

        # 检测串行 vs 并行
        # 简化：假设所有节点串行执行
        total_estimated_time = sum(r.estimated_time_sec for r in node_results.values())
        total_time_credits = total_estimated_time * (user.time_value_per_sec if user else 0)

        return {
            "total_direct_credits": total_direct,
            "total_time_credits": total_time_credits,
            "total_credits": total_direct + total_time_credits,
            "estimated_time_sec": total_estimated_time,
            "node_results": {k: v.to_dict() for k, v in node_results.items()},
        }


def get_task_estimator() -> TaskEstimator:
    """获取任务估算器实例"""
    return TaskEstimator()
