"""
三大场景数据联动引擎
====================

核心价值：让数据流动起来，形成飞轮效应

数据流向：
┌─────────────┐
│  环评报告   │ ──(源强、位置、标准)──→ ┌─────────────┐
└─────────────┘                          │  应急预案   │
     ↑                                    └─────────────┘
     │                                         ↑
     │                                    (危险物质、影响范围)
     │
└─────────────┐                              ┌─────────────┐
│  验收监测   │ ──(实测数据、达标判定)──→    │  排污许可   │
└─────────────┘                              └─────────────┘
     ↑
(实测 vs 预测)
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..emergency_response import (
    EmergencyPlan,
    HazardousSubstance,
    AccidentScenario,
    get_emergency_engine,
)
from ..acceptance_monitoring import (
    AcceptanceMonitoringReport,
    MonitoringType,
    EvaluationResult,
    get_monitoring_engine,
)
from ..pollution_permit import (
    PollutionPermit,
    PermitApplication,
    MonitoringReminder,
    get_permit_engine,
)


class ScenarioType(Enum):
    """场景类型"""
    EIA_REPORT = "eia_report"           # 环评报告
    EMERGENCY_PLAN = "emergency_plan"  # 应急预案
    ACCEPTANCE_MONITORING = "acceptance_monitoring"  # 验收监测
    POLLUTION_PERMIT = "pollution_permit"  # 排污许可


class DataFlowDirection(Enum):
    """数据流向"""
    EIA_TO_EMERGENCY = "eia_emergency"
    EIA_TO_ACCEPTANCE = "eia_acceptance"
    EIA_TO_PERMIT = "eia_permit"
    ACCEPTANCE_TO_PERMIT = "acceptance_permit"
    PERMIT_TO_MONITORING = "permit_monitoring"
    MONITORING_TO_EIA_FEEDBACK = "monitoring_eia_feedback"


@dataclass
class DataLink:
    """数据链接"""
    link_id: str
    source_scenario: ScenarioType
    target_scenario: ScenarioType
    data_type: str                      # 数据类型
    data_fields: List[str]               # 字段列表
    transformation: Optional[str] = None  # 转换规则
    last_synced: Optional[datetime] = None


@dataclass
class SyncedData:
    """同步数据"""
    data_id: str
    source: ScenarioType
    target: ScenarioType
    data_type: str
    content: Dict[str, Any]
    synced_at: datetime
    validation: bool = True

    def to_dict(self) -> Dict:
        return {
            "data_id": self.data_id,
            "source": self.source.value,
            "target": self.target.value,
            "data_type": self.data_type,
            "synced_at": self.synced_at.isoformat(),
            "validation": self.validation,
        }


@dataclass
class KnowledgeParticle:
    """知识颗粒 - 用于P2P网络共享"""
    particle_id: str
    category: str                      # 区域本底/行业参数/预测模型
    region: str                        # 区域
    industry: Optional[str] = None
    content: Dict[str, Any]
    quality: float = 0.0               # 数据质量 0-1
    shared_at: datetime = field(default_factory=datetime.now)
    usage_count: int = 0              # 被使用次数

    def to_dict(self) -> Dict:
        return {
            "particle_id": self.particle_id,
            "category": self.category,
            "region": self.region,
            "content": self.content,
            "quality": self.quality,
            "shared_at": self.shared_at.isoformat(),
            "usage_count": self.usage_count,
        }


@dataclass
class ModelFeedback:
    """模型反馈 - 用于AI模型进化"""
    feedback_id: str
    project_id: str
    pollutant: str
    predicted_value: float
    measured_value: float
    relative_error: float
    feedback_time: datetime = field(default_factory=datetime.now)
    is_valid: bool = True

    def to_dict(self) -> Dict:
        return {
            "feedback_id": self.feedback_id,
            "project_id": self.project_id,
            "pollutant": self.pollutant,
            "predicted_value": self.predicted_value,
            "measured_value": self.measured_value,
            "relative_error": self.relative_error,
            "feedback_time": self.feedback_time.isoformat(),
        }


@dataclass
class IntegratedLifecycleReport:
    """全生命周期集成报告"""
    project_id: str
    project_name: str
    current_stage: ScenarioType

    # 各阶段摘要
    eia_summary: Optional[Dict] = None
    emergency_summary: Optional[Dict] = None
    acceptance_summary: Optional[Dict] = None
    permit_summary: Optional[Dict] = None

    # 数据链路
    data_flows: List[Dict] = field(default_factory=list)

    # 知识沉淀
    knowledge_particles: List[Dict] = field(default_factory=list)

    # 模型进化
    model_feedbacks: List[Dict] = field(default_factory=list)

    # 综合结论
    lifecycle_status: str = "active"  # active/completed
    next_action: str = ""
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "current_stage": self.current_stage.value,
            "eia_summary": self.eia_summary,
            "emergency_summary": self.emergency_summary,
            "acceptance_summary": self.acceptance_summary,
            "permit_summary": self.permit_summary,
            "lifecycle_status": self.lifecycle_status,
            "next_action": self.next_action,
            "recommendations": self.recommendations,
        }


class DataLinkageEngine:
    """
    三大场景数据联动引擎

    核心能力：
    1. 环评报告 → 应急预案：继承危险物质、储罐位置
    2. 环评报告 → 验收监测：提供源强、敏感点位置
    3. 环评报告 → 排污许可：继承许可量、执行标准
    4. 验收监测 → 排污许可：提供实测数据、达标判定
    5. 知识沉淀：将验收数据脱敏后进入P2P网络
    6. 模型进化：将预测误差反馈给AI模型
    """

    def __init__(self):
        # 引擎实例
        self.emergency_engine = get_emergency_engine()
        self.monitoring_engine = get_monitoring_engine()
        self.permit_engine = get_permit_engine()

        # 数据链接注册
        self.data_links: Dict[str, DataLink] = {}
        self._register_default_links()

        # 已同步数据记录
        self.synced_data: List[SyncedData] = []

        # 知识颗粒库
        self.knowledge_particles: List[KnowledgeParticle] = []

        # 模型反馈记录
        self.model_feedbacks: List[ModelFeedback] = []

        # P2P回调（用于网络共享）
        self.p2p_share_callback: Optional[Callable] = None

    def _register_default_links(self):
        """注册默认数据链接"""
        default_links = [
            DataLink(
                link_id="link_eia_emergency",
                source_scenario=ScenarioType.EIA_REPORT,
                target_scenario=ScenarioType.EMERGENCY_PLAN,
                data_type="hazardous_substances",
                data_fields=["substance_name", "quantity", "state", "toxicity", "location"],
            ),
            DataLink(
                link_id="link_eia_acceptance",
                source_scenario=ScenarioType.EIA_REPORT,
                target_scenario=ScenarioType.ACCEPTANCE_MONITORING,
                data_type="source_parameters",
                data_fields=["source_strength", "location", "sensitive_points"],
            ),
            DataLink(
                link_id="link_eia_permit",
                source_scenario=ScenarioType.EIA_REPORT,
                target_scenario=ScenarioType.POLLUTION_PERMIT,
                data_type="approval_quantities",
                data_fields=["approved_emission_quantities", "execution_standards"],
            ),
            DataLink(
                link_id="link_acceptance_permit",
                source_scenario=ScenarioType.ACCEPTANCE_MONITORING,
                target_scenario=ScenarioType.POLLUTION_PERMIT,
                data_type="measured_data",
                data_fields=["evaluation_results", "prediction_comparison"],
            ),
        ]

        for link in default_links:
            self.data_links[link.link_id] = link

    def set_p2p_callback(self, callback: Callable):
        """设置P2P共享回调"""
        self.p2p_share_callback = callback

    # ============ 场景生成 ============

    async def generate_emergency_plan_from_eia(
        self,
        eia_report: Dict[str, Any],
        project_context: Dict[str, Any]
    ) -> EmergencyPlan:
        """
        从环评报告生成应急预案

        数据流向：环评报告 → 应急预案
        """
        # 直接使用应急预案引擎生成
        plan = await self.emergency_engine.generate_from_eia_report(
            eia_report, project_context
        )

        # 记录数据同步
        self._record_sync(
            source=ScenarioType.EIA_REPORT,
            target=ScenarioType.EMERGENCY_PLAN,
            data_type="hazardous_substances",
            content={"substances": [s.name for s in plan.hazardous_substances]}
        )

        return plan

    async def generate_monitoring_scheme_from_eia(
        self,
        eia_report: Dict[str, Any],
        project_context: Dict[str, Any],
        monitoring_type: MonitoringType = MonitoringType.AIR
    ) -> Dict:
        """
        从环评报告生成验收监测方案

        数据流向：环评报告 → 验收监测
        """
        # 使用监测引擎生成布点方案
        project_context['monitoring_type'] = monitoring_type.value
        report = await self.monitoring_engine.generate_monitoring_report(
            project_context, eia_report
        )

        # 记录数据同步
        self._record_sync(
            source=ScenarioType.EIA_REPORT,
            target=ScenarioType.ACCEPTANCE_MONITORING,
            data_type="source_parameters",
            content={"monitoring_points": len(report.layout_scheme.points)}
        )

        return report.to_dict()

    async def generate_permit_application_from_eia_and_acceptance(
        self,
        eia_report: Dict[str, Any],
        acceptance_report: Optional[Dict[str, Any]],
        project_context: Dict[str, Any]
    ) -> PermitApplication:
        """
        从环评报告和验收监测生成排污许可申请

        数据流向：环评报告 + 验收监测 → 排污许可
        """
        # 生成申请
        application = await self.permit_engine.generate_application(
            project_context, eia_report, acceptance_report
        )

        # 记录数据同步
        self._record_sync(
            source=ScenarioType.EIA_REPORT,
            target=ScenarioType.POLLUTION_PERMIT,
            data_type="approval_quantities",
            content={"sources": len(application.pollution_sources)}
        )

        if acceptance_report:
            self._record_sync(
                source=ScenarioType.ACCEPTANCE_MONITORING,
                target=ScenarioType.POLLUTION_PERMIT,
                data_type="measured_data",
                content={"evaluation_results": len(acceptance_report.get('evaluation_results', []))}
            )

        return application

    # ============ 知识沉淀 ============

    async def沉淀_monitoring_data(
        self,
        project_context: Dict[str, Any],
        acceptance_report: AcceptanceMonitoringReport
    ) -> List[KnowledgeParticle]:
        """
        将验收监测数据沉淀为知识颗粒

        用于P2P网络共享，形成区域环境本底数据库
        """
        particles = []
        region = project_context.get('region', '未知')
        industry = project_context.get('industry_type', '')

        # 1. 沉淀区域本底数据
        for result in acceptance_report.evaluation_results:
            if result.evaluation == EvaluationResult.COMPLIANT:
                particle = KnowledgeParticle(
                    particle_id=f"KP_bg_{region}_{result.parameter}_{datetime.now().strftime('%Y%m%d')}",
                    category="region_baseline",
                    region=region,
                    industry=industry,
                    content={
                        "parameter": result.parameter,
                        "background_value": result.measured_value,
                        "standard": result.standard_value,
                        "data_source": "acceptance_monitoring",
                    },
                    quality=0.8
                )
                particles.append(particle)

        # 2. 沉淀预测误差
        for param, comparison in acceptance_report.prediction_comparison.items():
            if comparison.get('ratio'):
                particle = KnowledgeParticle(
                    particle_id=f"KP_model_{region}_{param}_{datetime.now().strftime('%Y%m%d')}",
                    category="prediction_model",
                    region=region,
                    industry=industry,
                    content={
                        "parameter": param,
                        "predicted_measured_ratio": comparison['ratio'],
                        "model_type": "AERMOD/CALPUFF",
                    },
                    quality=abs(1 - comparison['ratio'])  # 误差越小，质量越高
                )
                particles.append(particle)

        # 3. 记录并可选择共享
        self.knowledge_particles.extend(particles)

        # 如果设置了P2P回调，进行网络共享
        if self.p2p_share_callback and particles:
            for particle in particles:
                await self.p2p_share_callback(particle)

        return particles

    async def沉淀_model_feedback(
        self,
        project_id: str,
        acceptance_report: AcceptanceMonitoringReport
    ) -> List[ModelFeedback]:
        """
        将实测与预测的差异反馈给AI模型

        用于模型进化，持续优化预测准确性
        """
        feedbacks = []

        for param, comparison in acceptance_report.prediction_comparison.items():
            predicted = comparison.get('predicted', 0)
            measured = comparison.get('measured', 0)

            if predicted > 0:
                error = abs(measured - predicted) / predicted

                feedback = ModelFeedback(
                    feedback_id=f"FB_{project_id}_{param}_{datetime.now().strftime('%Y%m%H%M%S')}",
                    project_id=project_id,
                    pollutant=param,
                    predicted_value=predicted,
                    measured_value=measured,
                    relative_error=error
                )
                feedbacks.append(feedback)

                # 更新知识颗粒中的模型质量
                self._update_model_quality(param, error)

        self.model_feedbacks.extend(feedbacks)
        return feedbacks

    def _update_model_quality(self, parameter: str, error: float):
        """更新模型质量"""
        # 查找相关知识颗粒
        for particle in self.knowledge_particles:
            if particle.category == "prediction_model" and particle.content.get('parameter') == parameter:
                # 使用新的误差更新质量
                new_quality = max(0.1, 1 - error)
                particle.quality = (particle.quality + new_quality) / 2

    # ============ 数据查询 ============

    async def query_knowledge_particles(
        self,
        category: Optional[str] = None,
        region: Optional[str] = None,
        industry: Optional[str] = None
    ) -> List[KnowledgeParticle]:
        """查询知识颗粒"""
        results = self.knowledge_particles

        if category:
            results = [p for p in results if p.category == category]
        if region:
            results = [p for p in results if p.region == region]
        if industry:
            results = [p for p in results if p.industry == industry]

        return results

    async def get_optimized_parameters(
        self,
        region: str,
        industry: str,
        parameter: str
    ) -> Dict:
        """
        获取优化后的模型参数

        基于P2P网络中的历史数据
        """
        # 查找相关知识颗粒
        relevant_particles = [
            p for p in self.knowledge_particles
            if p.region == region
            and p.content.get('parameter') == parameter
            and p.quality > 0.5
        ]

        if not relevant_particles:
            return {}

        # 使用加权平均（质量越高，权重越大）
        total_weight = sum(p.quality for p in relevant_particles)
        weighted_value = sum(
            p.content.get('predicted_measured_ratio', 1) * p.quality
            for p in relevant_particles
        ) / total_weight

        return {
            "parameter": parameter,
            "optimized_ratio": weighted_value,
            "confidence": min(total_weight / len(relevant_particles), 1.0),
            "data_sources": len(relevant_particles)
        }

    # ============ 全生命周期管理 ============

    async def generate_lifecycle_report(
        self,
        project_id: str,
        project_context: Dict[str, Any],
        eia_report: Optional[Dict] = None,
        emergency_plan: Optional[EmergencyPlan] = None,
        acceptance_report: Optional[AcceptanceMonitoringReport] = None,
        permit: Optional[PollutionPermit] = None
    ) -> IntegratedLifecycleReport:
        """
        生成全生命周期集成报告

        整合环评、应急、验收、许可四个阶段
        """
        report = IntegratedLifecycleReport(
            project_id=project_id,
            project_name=project_context.get('project_name', '未知项目'),
            current_stage=ScenarioType.EIA_REPORT
        )

        # 确定当前阶段
        stages = []
        if eia_report:
            stages.append(ScenarioType.EIA_REPORT)
            report.eia_summary = {
                "project_name": project_context.get('project_name'),
                "industry_type": project_context.get('industry_type'),
                "key_approved": list(eia_report.get('approved_emission_quantities', {}).keys())[:5]
            }

        if emergency_plan:
            stages.append(ScenarioType.EMERGENCY_PLAN)
            report.emergency_summary = {
                "scenarios_count": len(emergency_plan.accident_scenarios),
                "high_risk_scenarios": sum(1 for s in emergency_plan.accident_scenarios if s.hazard_level.value == 'extreme'),
                "resource_gaps": len(emergency_plan.resource_gaps)
            }

        if acceptance_report:
            stages.append(ScenarioType.ACCEPTANCE_MONITORING)
            report.acceptance_summary = {
                "monitoring_type": acceptance_report.monitoring_type.value,
                "evaluation": acceptance_report.overall_conclusion,
                "is_accepted": acceptance_report.is_accepted,
                "prediction_comparison": acceptance_report.prediction_comparison
            }

            # 触发知识沉淀
            await self.沉淀_monitoring_data(project_context, acceptance_report)
            await self.沉淀_model_feedback(project_id, acceptance_report)

        if permit:
            stages.append(ScenarioType.POLLUTION_PERMIT)
            report.permit_summary = {
                "permit_type": permit.status,
                "valid_until": permit.valid_until.isoformat() if permit.valid_until else None,
                "reminders_count": len(permit.reminders),
                "overdue_reminders": sum(1 for r in permit.reminders if r.is_overdue)
            }

        # 确定当前阶段
        if permit:
            report.current_stage = ScenarioType.POLLUTION_PERMIT
        elif acceptance_report:
            report.current_stage = ScenarioType.ACCEPTANCE_MONITORING
        elif emergency_plan:
            report.current_stage = ScenarioType.EMERGENCY_PLAN
        else:
            report.current_stage = ScenarioType.EIA_REPORT

        # 生成下一步建议
        report.next_action = self._generate_next_action(stages, report)
        report.recommendations = self._generate_recommendations(report)

        # 记录数据流
        report.data_flows = [s.to_dict() for s in self.synced_data[-10:]]

        # 记录知识颗粒
        report.knowledge_particles = [p.to_dict() for p in self.knowledge_particles[-10:]]

        # 记录模型反馈
        report.model_feedbacks = [f.to_dict() for f in self.model_feedbacks[-10:]]

        return report

    def _generate_next_action(self, stages: List[ScenarioType], report: IntegratedLifecycleReport) -> str:
        """生成下一步行动建议"""
        if ScenarioType.EIA_REPORT not in stages:
            return "完成环评报告编制"
        if ScenarioType.EMERGENCY_PLAN not in stages:
            return "编制应急预案"
        if ScenarioType.ACCEPTANCE_MONITORING not in stages:
            return "开展验收监测"
        if ScenarioType.POLLUTION_PERMIT not in stages:
            return "申请排污许可证"
        return "执行证后管理"

    def _generate_recommendations(self, report: IntegratedLifecycleReport) -> List[str]:
        """生成建议"""
        recommendations = []

        # 基于当前阶段生成建议
        if report.current_stage == ScenarioType.EIA_REPORT:
            recommendations.append("建议同步启动应急预案编制工作")
            recommendations.append("提前规划验收监测方案")

        elif report.current_stage == ScenarioType.EMERGENCY_PLAN:
            recommendations.append("尽快完成应急资源缺口补充")
            recommendations.append("组织应急演练")

        elif report.current_stage == ScenarioType.ACCEPTANCE_MONITORING:
            if report.acceptance_summary and not report.acceptance_summary.get('is_accepted'):
                recommendations.append("针对超标指标进行整改")
            recommendations.append("将监测数据用于P2P网络知识共享")

        elif report.current_stage == ScenarioType.POLLUTION_PERMIT:
            recommendations.append("按许可证要求执行自行监测")
            recommendations.append("关注证后管理日历提醒")

        return recommendations

    # ============ 辅助方法 ============

    def _record_sync(
        self,
        source: ScenarioType,
        target: ScenarioType,
        data_type: str,
        content: Dict
    ):
        """记录数据同步"""
        synced = SyncedData(
            data_id=f"SYNC_{source.value}_{target.value}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            source=source,
            target=target,
            data_type=data_type,
            content=content,
            synced_at=datetime.now()
        )
        self.synced_data.append(synced)


# 全局实例
_linkage_engine_instance: Optional[DataLinkageEngine] = None


def get_linkage_engine() -> DataLinkageEngine:
    """获取数据联动引擎全局实例"""
    global _linkage_engine_instance
    if _linkage_engine_instance is None:
        _linkage_engine_instance = DataLinkageEngine()
    return _linkage_engine_instance


async def generate_lifecycle_async(
    project_id: str,
    project_context: Dict[str, Any],
    **kwargs
) -> IntegratedLifecycleReport:
    """异步生成全生命周期的便捷函数"""
    engine = get_linkage_engine()
    return await engine.generate_lifecycle_report(
        project_id, project_context, **kwargs
    )