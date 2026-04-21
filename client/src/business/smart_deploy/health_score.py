"""
智能部署健康度评分系统 - DeploymentHealthScore
创新理念：让每次部署都有"风险分数"，从被动救火到主动预防

功能：
1. 多维度健康度评估
2. 历史成功率追踪
3. 风险因素自动识别
4. 部署前风险预警
"""

import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class HealthLevel(Enum):
    """健康等级"""
    EXCELLENT = "excellent"   # 90-100分
    GOOD = "good"           # 70-89分
    FAIR = "fair"           # 50-69分
    POOR = "poor"           # 30-49分
    CRITICAL = "critical"   # 0-29分


class RiskFactor(Enum):
    """风险因素"""
    HIGH_FAILURE_RATE = "high_failure_rate"
    RESOURCE_CONSTRAINED = "resource_constrained"
    NETWORK_UNSTABLE = "network_unstable"
    OUTDATED_ENV = "outdated_env"
    COMPLEX_DEPENDENCIES = "complex_dependencies"
    UNTESTED_STRATEGY = "untested_strategy"
    RUSH_HOUR = "rush_hour"


@dataclass
class HealthScore:
    """健康度评分"""
    total_score: float           # 总分 0-100
    level: HealthLevel
    factors: List[Dict]          # 评分因素
    risk_factors: List[RiskFactor]  # 识别的风险因素
    recommendations: List[str]   # 改进建议
    timestamp: datetime
    server_ip: str
    strategy_used: str


@dataclass
class DeploymentRecord:
    """部署记录"""
    deployment_id: str
    timestamp: datetime
    server_ip: str
    strategy: str
    success: bool
    duration_seconds: float
    failure_reason: Optional[str]
    health_score: float          # 部署前的健康度评分


class DeploymentHealthScore:
    """
    部署健康度评分系统

    评估维度：
    1. 历史成功率（30%权重）
    2. 服务器资源状态（20%权重）
    3. 环境一致性（15%权重）
    4. 依赖复杂度（15%权重）
    5. 时机因素（10%权重）
    6. 策略熟悉度（10%权重）
    """

    def __init__(self):
        self._records: List[DeploymentRecord] = []
        self._max_history = 1000  # 最多保存1000条记录

    def evaluate(
        self,
        server_info,
        strategy: str,
        intent_result = None,
        environment_info: Dict = None
    ) -> HealthScore:
        """
        评估部署健康度

        Args:
            server_info: 服务器信息
            strategy: 部署策略
            intent_result: 意图理解结果
            environment_info: 环境信息

        Returns:
            HealthScore: 健康度评分
        """
        factors = []
        risk_factors = []
        recommendations = []
        total_score = 100.0

        # 1. 历史成功率（30%权重）
        history_score, history_factor, history_risks = self._evaluate_history(
            server_info.ip_address if server_info else "unknown",
            strategy
        )
        factors.append(history_factor)
        total_score = total_score * 0.7 + history_score * 0.3
        risk_factors.extend(history_risks)

        # 2. 服务器资源状态（20%权重）
        resource_score, resource_factor, resource_risks = self._evaluate_resources(server_info)
        factors.append(resource_factor)
        total_score = total_score * 0.8 + resource_score * 0.2
        risk_factors.extend(resource_risks)

        # 3. 环境一致性（15%权重）
        env_score, env_factor, env_risks = self._evaluate_environment(
            server_info, environment_info
        )
        factors.append(env_factor)
        total_score = total_score * 0.85 + env_score * 0.15
        risk_factors.extend(env_risks)

        # 4. 依赖复杂度（15%权重）
        dep_score, dep_factor, dep_risks = self._evaluate_dependencies(intent_result)
        factors.append(dep_factor)
        total_score = total_score * 0.85 + dep_score * 0.15
        risk_factors.extend(dep_risks)

        # 5. 时机因素（10%权重）
        timing_score, timing_factor, timing_risks = self._evaluate_timing()
        factors.append(timing_factor)
        total_score = total_score * 0.9 + timing_score * 0.1
        risk_factors.extend(timing_risks)

        # 6. 策略熟悉度（10%权重）
        strategy_score, strategy_factor, strategy_risks = self._evaluate_strategy_familiarity(
            server_info.ip_address if server_info else "unknown",
            strategy
        )
        factors.append(strategy_factor)
        total_score = total_score * 0.9 + strategy_score * 0.1
        risk_factors.extend(strategy_risks)

        # 计算最终分数
        total_score = max(0, min(100, total_score))

        # 确定健康等级
        level = self._get_health_level(total_score)

        # 生成建议
        recommendations = self._generate_recommendations(
            total_score, risk_factors, server_info
        )

        return HealthScore(
            total_score=total_score,
            level=level,
            factors=factors,
            risk_factors=risk_factors,
            recommendations=recommendations,
            timestamp=datetime.now(),
            server_ip=server_info.ip_address if server_info else "unknown",
            strategy_used=strategy
        )

    def _evaluate_history(
        self,
        server_ip: str,
        strategy: str
    ) -> tuple:
        """评估历史成功率"""
        score = 100.0
        factor = {"name": "历史成功率", "score": 100.0, "details": "无历史记录，默认满分"}
        risks = []

        # 获取该服务器的历史记录
        server_records = [r for r in self._records if r.server_ip == server_ip]

        if len(server_records) >= 3:
            # 有足够的历史记录
            success_count = sum(1 for r in server_records if r.success)
            success_rate = success_count / len(server_records)

            score = success_rate * 100

            # 如果成功率低于70%，标记为高风险
            if success_rate < 0.7:
                risks.append(RiskFactor.HIGH_FAILURE_RATE)
                factor["details"] = f"成功率 {success_rate:.0%}，低于70%阈值"
            else:
                factor["details"] = f"成功率 {success_rate:.0%}，基于{len(server_records)}次部署"

        # 检查该策略的历史
        strategy_records = [r for r in server_records if r.strategy == strategy]
        if len(strategy_records) == 0:
            risks.append(RiskFactor.UNTESTED_STRATEGY)
            score *= 0.8  # 未测试的策略扣20分
            factor["details"] += "，策略未经测试"

        factor["score"] = score
        return score, factor, risks

    def _evaluate_resources(self, server_info) -> tuple:
        """评估服务器资源状态"""
        score = 100.0
        factor = {"name": "服务器资源", "score": 100.0, "details": "资源充足"}
        risks = []

        if not server_info:
            return score, factor, risks

        # 检查内存
        if hasattr(server_info, 'memory_available_mb'):
            if server_info.memory_available_mb < 512:
                score -= 30
                risks.append(RiskFactor.RESOURCE_CONSTRAINED)
                factor["details"] = f"可用内存仅 {server_info.memory_available_mb}MB，过低"
            elif server_info.memory_available_mb < 1024:
                score -= 15
                factor["details"] = f"可用内存 {server_info.memory_available_mb}MB，偏低"

        # 检查CPU
        if hasattr(server_info, 'cpu_cores'):
            if server_info.cpu_cores < 2:
                score -= 20
                factor["details"] = f"CPU仅 {server_info.cpu_cores} 核，偏弱"

        # 检查磁盘空间
        if hasattr(server_info, 'disk_available_gb'):
            if server_info.disk_available_gb < 5:
                score -= 20
                risks.append(RiskFactor.RESOURCE_CONSTRAINED)
                factor["details"] = f"磁盘空间仅 {server_info.disk_available_gb}GB，过低"

        factor["score"] = max(0, score)
        return max(0, score), factor, risks

    def _evaluate_environment(
        self,
        server_info,
        environment_info: Dict = None
    ) -> tuple:
        """评估环境一致性"""
        score = 100.0
        factor = {"name": "环境一致性", "score": 100.0, "details": "环境正常"}
        risks = []

        if not environment_info:
            return score, factor, risks

        # 检查Python版本
        if 'python_version' in environment_info:
            py_version = environment_info['python_version']
            if py_version and py_version.startswith('2'):
                score -= 30
                risks.append(RiskFactor.OUTDATED_ENV)
                factor["details"] = f"Python版本 {py_version} 已过时"

        # 检查Docker版本
        if 'docker_version' in environment_info:
            docker_ver = environment_info['docker_version']
            if not docker_ver:
                score -= 15
                factor["details"] = "Docker未安装"

        factor["score"] = max(0, score)
        return max(0, score), factor, risks

    def _evaluate_dependencies(self, intent_result) -> tuple:
        """评估依赖复杂度"""
        score = 100.0
        factor = {"name": "依赖复杂度", "score": 100.0, "details": "无额外依赖"}
        risks = []

        if not intent_result:
            return score, factor, risks

        # 检查依赖数量
        env = getattr(intent_result, 'environment', {})
        ports = env.get('ports', [])

        if len(ports) > 3:
            score -= 10
            factor["details"] = f"需要开放 {len(ports)} 个端口，复杂度较高"

        # 检查是否需要sudo
        if 'requires_sudo' in env and env['requires_sudo']:
            score -= 15
            factor["details"] = "需要sudo权限，增加了风险"

        if len(ports) > 5:
            risks.append(RiskFactor.COMPLEX_DEPENDENCIES)

        factor["score"] = max(0, score)
        return max(0, score), factor, risks

    def _evaluate_timing(self) -> tuple:
        """评估部署时机"""
        score = 100.0
        factor = {"name": "部署时机", "score": 100.0, "details": "时机良好"}
        risks = []

        now = datetime.now()
        hour = now.hour

        # 检查是否为工作时间（可能有较多用户）
        if 9 <= hour <= 18:
            score -= 10
            factor["details"] = f"当前时间 {hour}:00，处于工作时间"
            # 不标记为风险，只是建议

        # 检查是否为深夜（可能有运维人员不足）
        if 0 <= hour < 6:
            score -= 20
            risks.append(RiskFactor.RUSH_HOUR)
            factor["details"] = "深夜部署，运维响应可能不及时"

        # 检查是否为周末
        if now.weekday() >= 5:
            score -= 5
            factor["details"] = "周末部署"

        factor["score"] = max(0, score)
        return max(0, score), factor, risks

    def _evaluate_strategy_familiarity(
        self,
        server_ip: str,
        strategy: str
    ) -> tuple:
        """评估策略熟悉度"""
        score = 100.0
        factor = {"name": "策略熟悉度", "score": 100.0, "details": "策略已验证"}
        risks = []

        # 获取该策略在此服务器上的使用次数
        strategy_count = sum(
            1 for r in self._records
            if r.server_ip == server_ip and r.strategy == strategy
        )

        if strategy_count == 0:
            score -= 30
            risks.append(RiskFactor.UNTESTED_STRATEGY)
            factor["details"] = "策略未在此服务器上使用过"
        elif strategy_count < 3:
            score -= 10
            factor["details"] = f"策略使用次数较少（{strategy_count}次）"

        factor["score"] = max(0, score)
        return max(0, score), factor, risks

    def _get_health_level(self, score: float) -> HealthLevel:
        """根据分数获取健康等级"""
        if score >= 90:
            return HealthLevel.EXCELLENT
        elif score >= 70:
            return HealthLevel.GOOD
        elif score >= 50:
            return HealthLevel.FAIR
        elif score >= 30:
            return HealthLevel.POOR
        else:
            return HealthLevel.CRITICAL

    def _generate_recommendations(
        self,
        score: float,
        risks: List[RiskFactor],
        server_info
    ) -> List[str]:
        """生成改进建议"""
        recommendations = []

        if score < 70:
            recommendations.append("⚠️ 建议推迟部署，先解决环境问题")

        if RiskFactor.HIGH_FAILURE_RATE in risks:
            recommendations.append("🔧 该服务器历史失败率较高，建议先进行环境检查")

        if RiskFactor.RESOURCE_CONSTRAINED in risks:
            recommendations.append("💾 服务器资源不足，建议扩容或清理后再部署")

        if RiskFactor.UNTESTED_STRATEGY in risks:
            recommendations.append("🧪 建议先在测试环境验证策略")

        if RiskFactor.RUSH_HOUR in risks:
            recommendations.append("🌙 深夜部署有风险，建议选择工作时间部署")

        if score >= 90:
            recommendations.append("✅ 健康度优秀，适合部署")

        return recommendations

    def record_deployment(
        self,
        deployment_id: str,
        server_ip: str,
        strategy: str,
        success: bool,
        duration_seconds: float,
        failure_reason: Optional[str] = None,
        health_score: float = 0.0
    ):
        """记录部署结果"""
        record = DeploymentRecord(
            deployment_id=deployment_id,
            timestamp=datetime.now(),
            server_ip=server_ip,
            strategy=strategy,
            success=success,
            duration_seconds=duration_seconds,
            failure_reason=failure_reason,
            health_score=health_score
        )

        self._records.append(record)

        # 保持记录数量限制
        if len(self._records) > self._max_history:
            self._records = self._records[-self._max_history:]

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._records:
            return {
                "total_deployments": 0,
                "success_rate": 0.0,
                "avg_duration": 0.0,
                "avg_health_score": 0.0
            }

        success_count = sum(1 for r in self._records if r.success)
        total_duration = sum(r.duration_seconds for r in self._records)
        total_health = sum(r.health_score for r in self._records if r.health_score > 0)

        return {
            "total_deployments": len(self._records),
            "success_rate": success_count / len(self._records),
            "avg_duration": total_duration / len(self._records),
            "avg_health_score": total_health / len(self._records) if self._records else 0.0,
            "recent_failures": [
                r for r in self._records[-10:] if not r.success
            ]
        }


# 全局实例
health_score_system = DeploymentHealthScore()
