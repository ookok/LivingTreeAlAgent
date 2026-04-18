"""
智能部署建议系统 - SmartDeployAdvisor
创新理念：让AI成为你的部署顾问，不仅告诉你怎么做，还告诉你什么时候做、为什么这样做

功能：
1. 最佳部署时间窗口预测
2. 策略推荐（基于历史成功率和环境）
3. 风险预警和缓解建议
4. 性能优化建议
"""

import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class AdviceLevel(Enum):
    """建议等级"""
    CRITICAL = "critical"   # 必须立即处理
    WARNING = "warning"     # 需要关注
    SUGGESTION = "suggestion"  # 建议考虑
    INFO = "info"          # 参考信息


@dataclass
class DeployAdvice:
    """部署建议"""
    level: AdviceLevel
    title: str
    description: str
    reasoning: str
    action_items: List[str]
    confidence: float  # 置信度 0-1


@dataclass
class BestTimeWindow:
    """最佳时间窗口"""
    start_hour: int
    end_hour: int
    day_of_week: List[int]  # 0=周一, 6=周日
    score: float
    reason: str


class SmartDeployAdvisor:
    """
    智能部署顾问

    核心能力：
    1. 分析历史部署数据，找出最佳部署时间
    2. 根据当前环境推荐最优策略
    3. 预测潜在风险并提供缓解方案
    4. 提供性能优化建议
    """

    def __init__(self):
        # 最佳部署时间窗口（基于统计数据）
        self._best_windows = [
            BestTimeWindow(
                start_hour=2, end_hour=5,
                day_of_week=[0, 1, 2, 3, 4],  # 工作日凌晨2-5点
                score=95,
                reason="用户流量最低，服务中断影响最小"
            ),
            BestTimeWindow(
                start_hour=0, end_hour=6,
                day_of_week=[5, 6],  # 周末全天都可以
                score=90,
                reason="周末用户量最低，适合进行维护"
            ),
            BestTimeWindow(
                start_hour=10, end_hour=12,
                day_of_week=[1, 2, 3, 4, 5],  # 工作日上午
                score=70,
                reason="有运维人员在线，问题响应快"
            ),
        ]

        # 风险等级阈值
        self._risk_thresholds = {
            "success_rate_low": 0.7,     # 成功率低于70%算高风险
            "resource_low": 0.3,           # 资源使用率高于30%算紧张
            "hour_rush": [9, 10, 11, 14, 15, 16, 17, 18]  # 上下班高峰
        }

    def get_advice(
        self,
        server_info: Any,
        strategy: str,
        deployment_history: List[Any],
        current_time: datetime = None
    ) -> List[DeployAdvice]:
        """
        获取部署建议

        Args:
            server_info: 服务器信息
            strategy: 部署策略
            deployment_history: 历史部署记录
            current_time: 当前时间

        Returns:
            List[DeployAdvice]: 建议列表
        """
        current_time = current_time or datetime.now()
        advices = []

        # 1. 检查服务器资源
        resource_advice = self._check_resource_status(server_info)
        if resource_advice:
            advices.append(resource_advice)

        # 2. 检查历史成功率
        success_advice = self._check_success_rate(server_info, deployment_history)
        if success_advice:
            advices.append(success_advice)

        # 3. 检查部署时机
        timing_advice = self._check_timing(current_time, deployment_history)
        if timing_advice:
            advices.append(timing_advice)

        # 4. 检查策略适用性
        strategy_advice = self._check_strategy适用性(strategy, server_info, deployment_history)
        if strategy_advice:
            advices.append(strategy_advice)

        # 5. 提供优化建议
        optimization_advice = self._get_optimization_advice(
            server_info, strategy, deployment_history
        )
        if optimization_advice:
            advices.append(optimization_advice)

        return advices

    def _check_resource_status(self, server_info: Any) -> Optional[DeployAdvice]:
        """检查服务器资源状态"""
        if not server_info:
            return DeployAdvice(
                level=AdviceLevel.WARNING,
                title="服务器信息不完整",
                description="无法获取服务器资源信息，建议手动确认",
                reasoning="完整的服务器信息有助于更准确的风险评估",
                action_items=[
                    "运行完整的环境检测",
                    "手动检查服务器负载",
                    "确认网络连接状态"
                ],
                confidence=0.8
            )

        warnings = []
        critical = []

        # 检查内存
        if hasattr(server_info, 'memory_available_mb'):
            if server_info.memory_available_mb < 256:
                critical.append(f"内存严重不足: {server_info.memory_available_mb}MB")
            elif server_info.memory_available_mb < 512:
                warnings.append(f"内存偏低: {server_info.memory_available_mb}MB")

        # 检查磁盘
        if hasattr(server_info, 'disk_available_gb'):
            if server_info.disk_available_gb < 2:
                critical.append(f"磁盘空间严重不足: {server_info.disk_available_gb}GB")
            elif server_info.disk_available_gb < 5:
                warnings.append(f"磁盘空间偏低: {server_info.disk_available_gb}GB")

        # 检查CPU（如果有）
        if hasattr(server_info, 'cpu_cores'):
            if server_info.cpu_cores < 2:
                warnings.append(f"CPU核心数较少: {server_info.cpu_cores}核")

        if critical:
            return DeployAdvice(
                level=AdviceLevel.CRITICAL,
                title="服务器资源严重不足",
                description=" | ".join(critical),
                reasoning="资源不足可能导致部署失败或服务不稳定",
                action_items=[
                    "扩容服务器资源",
                    "清理不必要的进程或文件",
                    "考虑使用更高配置的服务器"
                ],
                confidence=0.95
            )

        if warnings:
            return DeployAdvice(
                level=AdviceLevel.WARNING,
                title="服务器资源偏低",
                description=" | ".join(warnings),
                reasoning="资源偏低可能影响部署性能和稳定性",
                action_items=[
                    "监控部署过程中的资源使用",
                    "准备备用资源以便扩容",
                    "选择轻量级的部署策略"
                ],
                confidence=0.85
            )

        return None

    def _check_success_rate(
        self,
        server_info: Any,
        deployment_history: List[Any]
    ) -> Optional[DeployAdvice]:
        """检查历史部署成功率"""
        if not deployment_history:
            return DeployAdvice(
                level=AdviceLevel.INFO,
                title="无历史部署记录",
                description="这是首次部署，无法参考历史数据",
                reasoning="新服务器或新环境需要更谨慎的操作",
                action_items=[
                    "选择在低峰期部署",
                    "准备详细的回滚方案",
                    "增加监控频率"
                ],
                confidence=0.9
            )

        # 计算成功率
        total = len(deployment_history)
        success = sum(1 for d in deployment_history if hasattr(d, 'success') and d.success)
        rate = success / total if total > 0 else 0

        if rate < 0.5:
            return DeployAdvice(
                level=AdviceLevel.CRITICAL,
                title=f"历史成功率极低 ({rate:.0%})",
                description=f"在 {total} 次部署中仅有 {success} 次成功",
                reasoning="成功率低于50%说明存在系统性问题，需要先解决根本原因",
                action_items=[
                    "排查部署失败的根本原因",
                    "修复环境问题后再尝试",
                    "考虑重建服务器环境"
                ],
                confidence=0.95
            )
        elif rate < 0.7:
            return DeployAdvice(
                level=AdviceLevel.WARNING,
                title=f"历史成功率偏低 ({rate:.0%})",
                description=f"在 {total} 次部署中有 {success} 次成功",
                reasoning="成功率低于70%需要额外注意",
                action_items=[
                    "仔细检查部署日志",
                    "确保回滚方案可用",
                    "在低峰期进行部署"
                ],
                confidence=0.85
            )

        return None

    def _check_timing(
        self,
        current_time: datetime,
        deployment_history: List[Any]
    ) -> Optional[DeployAdvice]:
        """检查部署时机"""
        hour = current_time.hour
        day = current_time.weekday()
        is_weekend = day >= 5

        # 检查是否为高风险时段
        if hour in self._risk_thresholds["hour_rush"] and not is_weekend:
            return DeployAdvice(
                level=AdviceLevel.SUGGESTION,
                title=f"当前处于业务高峰时段 ({hour}:00)",
                description="用户访问量较高，部署可能影响用户体验",
                reasoning="高峰时段部署风险较高，建议选择低峰期",
                action_items=[
                    "如果必须此时部署，确保快速回滚方案可用",
                    "考虑使用蓝绿部署减少影响",
                    "增加用户通知"
                ],
                confidence=0.8
            )

        # 检查是否为深夜
        if 0 <= hour < 6:
            # 检查是否有运维人员
            return DeployAdvice(
                level=AdviceLevel.INFO,
                title="深夜时段部署",
                description="当前是深夜，建议确认运维响应安排",
                reasoning="深夜响应可能不及时，需要确认有值班人员",
                action_items=[
                    "确认值班人员在线",
                    "设置更详细的监控告警",
                    "准备快速沟通渠道"
                ],
                confidence=0.7
            )

        return None

    def _check_strategy适用性(
        self,
        strategy: str,
        server_info: Any,
        deployment_history: List[Any]
    ) -> Optional[DeployAdvice]:
        """检查策略适用性"""
        if not server_info:
            return None

        # Docker策略但没有Docker
        if strategy == "docker" or strategy == "docker_compose":
            if hasattr(server_info, 'docker_available'):
                if not server_info.docker_available:
                    return DeployAdvice(
                        level=AdviceLevel.CRITICAL,
                        title="Docker不可用",
                        description="选择了Docker策略但服务器未安装Docker",
                        reasoning="策略与实际环境不匹配",
                        action_items=[
                            "修改部署策略为非Docker方式",
                            "或先在服务器上安装Docker"
                        ],
                        confidence=0.95
                    )

        # 低配服务器使用重量级策略
        low_end_strategies = ["kubernetes", "docker_compose"]
        if strategy in low_end_strategies:
            if hasattr(server_info, 'capability'):
                if server_info.capability.value == "low":
                    return DeployAdvice(
                        level=AdviceLevel.WARNING,
                        title="策略可能过于重量级",
                        description=f"在低配服务器上使用{strategy}策略",
                        reasoning="低配服务器可能无法流畅运行容器编排",
                        action_items=[
                            "考虑使用更轻量的策略",
                            "或升级服务器配置"
                        ],
                        confidence=0.8
                    )

        return None

    def _get_optimization_advice(
        self,
        server_info: Any,
        strategy: str,
        deployment_history: List[Any]
    ) -> Optional[DeployAdvice]:
        """获取优化建议"""
        suggestions = []

        # 基于历史的优化建议
        if deployment_history:
            recent = deployment_history[-5:]
            avg_duration = sum(
                getattr(d, 'duration_seconds', 0) for d in recent
            ) / len(recent) if recent else 0

            if avg_duration > 600:  # 超过10分钟
                suggestions.append(f"近期部署平均耗时 {avg_duration/60:.1f} 分钟，可考虑优化部署流程")

        # 基于服务器的优化建议
        if server_info:
            if hasattr(server_info, 'memory_available_mb'):
                if server_info.memory_available_mb > 4096:
                    suggestions.append("服务器内存充足，适合运行多服务架构")

            if hasattr(server_info, 'docker_available'):
                if server_info.docker_available:
                    suggestions.append("推荐使用Docker实现环境一致性")

        if not suggestions:
            return None

        return DeployAdvice(
            level=AdviceLevel.INFO,
            title="优化建议",
            description=" | ".join(suggestions),
            reasoning="基于当前环境分析",
            action_items=suggestions,
            confidence=0.7
        )

    def get_best_time_window(self) -> BestTimeWindow:
        """获取当前最佳部署时间窗口"""
        now = datetime.now()
        current_hour = now.hour
        current_day = now.weekday()

        best = None
        best_score = -1

        for window in self._best_windows:
            # 计算匹配度
            day_match = current_day in window.day_of_week
            hour_match = window.start_hour <= current_hour < window.end_hour

            if day_match and hour_match:
                score = window.score
            elif day_match:
                # 白天匹配但时间不对，计算距离下一个窗口的时间
                score = window.score * 0.3
            else:
                score = 0

            if score > best_score:
                best_score = score
                best = window

        return best or self._best_windows[0]

    def should_proceed(self, advices: List[DeployAdvice]) -> tuple:
        """
        判断是否应该继续部署

        Returns:
            (should_proceed: bool, reason: str)
        """
        critical = [a for a in advices if a.level == AdviceLevel.CRITICAL]
        if critical:
            return False, f"存在 {len(critical)} 个严重问题，必须先解决"

        warnings = [a for a in advices if a.level == AdviceLevel.WARNING]
        if len(warnings) >= 3:
            return False, f"存在 {len(warnings)} 个警告，建议先处理"

        return True, "可以继续部署，但请留意上述建议"


# 全局实例
smart_advisor = SmartDeployAdvisor()
