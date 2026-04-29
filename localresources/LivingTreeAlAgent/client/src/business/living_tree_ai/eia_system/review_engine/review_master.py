"""
智能审查主引擎 - 整合所有审查能力
==========================================

将五大创新审查能力整合为一个统一的审查系统：
1. 数字孪生验证 - 预测结果复算、空间验证
2. 知识图谱合规 - 标准合规、跨章节推理
3. 智能修复 - 分级建议、自动补丁
4. 对抗性测试 - 不确定性分析、极端情景
5. 分布式审查 - 集体智慧、共识机制
"""

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from .digital_twin_verifier import (
    DigitalTwinVerifier,
    VerificationReport,
    VerificationStatus,
    get_verifier,
    verify_prediction_async,
    verify_distance_async,
)
from .knowledge_graph_compliance import (
    ComplianceReport,
    ComplianceStatus,
    KnowledgeGraphComplianceEngine,
    get_compliance_engine,
    check_compliance_async,
)
from .smart_repair_engine import (
    SmartRepairEngine,
    SmartRepairReport,
    RepairSuggestion,
    AutoPatch,
    get_repair_engine,
    analyze_and_repair_async,
)
from .adversarial_tester import (
    AdversarialTester,
    UncertaintyResult,
    ExtremeScenario,
    TestReport,
    get_tester,
    run_adversarial_test_async,
)
from .distributed_review_network import (
    DistributedReviewNetwork,
    ReviewTask,
    ReviewVote,
    ConsensusResult,
    ConsensusLevel,
    VoteStatus,
    get_review_network,
)


class ReviewMode(Enum):
    """审查模式"""
    AUTO = "auto"                  # 全自动审查
    SEMI_AUTO = "semi_auto"        # 半自动（AI + 人工确认）
    MANUAL = "manual"              # 人工审查模式
    DISTRIBUTED = "distributed"    # 分布式集体审查


class ReviewStage(Enum):
    """审查阶段"""
    INITIALIZATION = "initialization"
    DIGITAL_TWIN = "digital_twin"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    SMART_REPAIR = "smart_repair"
    ADVERSARIAL_TEST = "adversarial_test"
    DISTRIBUTED_REVIEW = "distributed_review"
    REPORT_GENERATION = "report_generation"
    COMPLETED = "completed"


@dataclass
class ReviewSession:
    """审查会话"""
    session_id: str
    report_id: str
    project_name: str
    mode: ReviewMode

    # 阶段状态
    current_stage: ReviewStage = ReviewStage.INITIALIZATION
    stage_progress: Dict[str, float] = field(default_factory=dict)

    # 各模块结果
    verification_report: Optional[VerificationReport] = None
    compliance_report: Optional[ComplianceReport] = None
    repair_report: Optional[SmartRepairReport] = None
    test_report: Optional[TestReport] = None
    distributed_task: Optional[ReviewTask] = None
    consensus_result: Optional[ConsensusResult] = None

    # 时间戳
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    # 元数据
    triggered_by: str = "system"  # system, user, distributed
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "report_id": self.report_id,
            "project_name": self.project_name,
            "mode": self.mode.value,
            "current_stage": self.current_stage.value,
            "stage_progress": self.stage_progress,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def get_overall_score(self) -> float:
        """计算综合评分"""
        scores = []

        if self.verification_report:
            score = self.verification_report.get_pass_rate()
            scores.append(("数字孪生验证", score))

        if self.compliance_report:
            if self.compliance_report.risk_level == "LOW":
                scores.append(("合规性", 100))
            elif self.compliance_report.risk_level == "MEDIUM":
                scores.append(("合规性", 75))
            elif self.compliance_report.risk_level == "HIGH":
                scores.append(("合规性", 50))
            else:
                scores.append(("合规性", 25))

        if self.test_report:
            # 不确定性得分 = 100 - 平均不确定度
            if self.test_report.uncertainty_results:
                avg_uncertainty = sum(
                    r.uncertainty_percent for r in self.test_report.uncertainty_results
                ) / len(self.test_report.uncertainty_results)
                scores.append(("鲁棒性", 100 - avg_uncertainty))
            else:
                scores.append(("鲁棒性", 100))

        if not scores:
            return 0.0

        return sum(s[1] for s in scores) / len(scores)


@dataclass
class IntegratedReviewReport:
    """综合审查报告"""
    session_id: str
    report_id: str
    project_name: str
    generated_at: datetime

    # 各维度评分
    verification_score: float = 0.0       # 数字孪生验证评分
    compliance_score: float = 0.0          # 合规性评分
    robustness_score: float = 0.0         # 鲁棒性评分
    consensus_score: float = 0.0          # 共识评分（如果有）

    # 综合评分
    overall_score: float = 0.0

    # 风险等级
    risk_level: str = "UNKNOWN"          # LOW, MEDIUM, HIGH, CRITICAL

    # 问题汇总
    total_issues: int = 0
    fatal_issues: List[str] = field(default_factory=list)
    error_issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    # 可执行项
    auto_patches: List[Dict] = field(default_factory=list)
    repair_suggestions: List[Dict] = field(default_factory=list)

    # 审查结论
    conclusion: str = ""
    recommendation: str = ""  # ACCEPT, REVISE, REJECT
    next_steps: List[str] = field(default_factory=list)

    # 审查追溯
    review_hash: str = ""

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "report_id": self.report_id,
            "project_name": self.project_name,
            "generated_at": self.generated_at.isoformat(),
            "verification_score": self.verification_score,
            "compliance_score": self.compliance_score,
            "robustness_score": self.robustness_score,
            "consensus_score": self.consensus_score,
            "overall_score": self.overall_score,
            "risk_level": self.risk_level,
            "total_issues": self.total_issues,
            "fatal_issues": self.fatal_issues,
            "error_issues": self.error_issues,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "auto_patches": self.auto_patches,
            "repair_suggestions": self.repair_suggestions,
            "conclusion": self.conclusion,
            "recommendation": self.recommendation,
            "next_steps": self.next_steps,
            "review_hash": self.review_hash,
        }


class IntelligentReviewEngine:
    """
    智能审查主引擎

    整合五大创新审查能力：
    1. 数字孪生验证 - 预测结果复算、空间验证
    2. 知识图谱合规 - 标准合规检查、跨章节推理
    3. 智能修复引擎 - 分级建议、自动补丁
    4. 对抗性测试 - 不确定性分析、极端情景
    5. 分布式审查 - 集体智慧、共识机制
    """

    def __init__(self):
        # 各模块实例
        self.digital_twin: DigitalTwinVerifier = get_verifier()
        self.compliance: KnowledgeGraphComplianceEngine = get_compliance_engine()
        self.repair: SmartRepairEngine = get_repair_engine()
        self.adversarial: AdversarialTester = get_tester()
        self.distributed: Optional[DistributedReviewNetwork] = None

        # 审查会话
        self.sessions: Dict[str, ReviewSession] = {}

        # 回调函数
        self.progress_callback: Optional[Callable] = None
        self.notification_callback: Optional[Callable] = None

    def set_progress_callback(self, callback: Callable):
        """设置进度回调"""
        self.progress_callback = callback

    def set_notification_callback(self, callback: Callable):
        """设置通知回调"""
        self.notification_callback = callback

    async def start_review(
        self,
        report_id: str,
        project_name: str,
        report_content: Dict[str, Any],
        project_context: Dict[str, Any],
        mode: ReviewMode = ReviewMode.AUTO
    ) -> ReviewSession:
        """
        开始审查

        Args:
            report_id: 报告ID
            project_name: 项目名称
            report_content: 报告内容
            project_context: 项目上下文
            mode: 审查模式

        Returns:
            ReviewSession: 审查会话
        """
        # 创建会话
        session_id = hashlib.sha256(
            f"{report_id}_{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        session = ReviewSession(
            session_id=session_id,
            report_id=report_id,
            project_name=project_name,
            mode=mode
        )
        self.sessions[session_id] = session

        try:
            # 阶段1: 数字孪生验证
            await self._run_digital_twin_review(session, report_content, project_context)

            # 阶段2: 知识图谱合规检查
            await self._run_compliance_review(session, report_content, project_context)

            # 阶段3: 智能修复分析
            await self._run_smart_repair(session, report_content, project_context)

            # 阶段4: 对抗性测试
            if project_context.get('enable_adversarial_test', True):
                await self._run_adversarial_test(session, report_content, project_context)

            # 阶段5: 分布式审查（如果启用）
            if mode == ReviewMode.DISTRIBUTED:
                await self._run_distributed_review(session, report_content, project_context)

            # 阶段6: 生成综合报告
            session.current_stage = ReviewStage.REPORT_GENERATION
            session.completed_at = datetime.now()

        except Exception as e:
            session.notes = f"审查出错: {str(e)}"

        session.current_stage = ReviewStage.COMPLETED
        return session

    async def _run_digital_twin_review(
        self,
        session: ReviewSession,
        report_content: Dict[str, Any],
        project_context: Dict[str, Any]
    ):
        """执行数字孪生验证"""
        session.current_stage = ReviewStage.DIGITAL_TWIN
        await self._report_progress(session, "正在执行数字孪生验证...")

        # 提取需要验证的预测结果
        predictions = report_content.get('predictions', [])
        distance_statements = report_content.get('distance_statements', [])

        # 执行验证
        verification_report = VerificationReport(
            report_id=session.report_id,
            project_name=session.project_name,
            verification_time=datetime.now()
        )

        # 验证预测结果
        for pred_text in predictions:
            result = await verify_prediction_async(pred_text, project_context)
            verification_report.predictions.append(result)

        # 验证距离陈述
        for desc in distance_statements:
            result = await verify_distance_async(
                desc,
                project_context.get('lat', 0),
                project_context.get('lon', 0),
                project_context
            )
            verification_report.distance_verifications.append(result)

        # 计算整体状态
        if verification_report.predictions or verification_report.distance_verifications:
            pass_rate = verification_report.get_pass_rate()
            if pass_rate >= 95:
                verification_report.overall_status = VerificationStatus.PASSED
            elif pass_rate >= 80:
                verification_report.overall_status = VerificationStatus.WARNING
            else:
                verification_report.overall_status = VerificationStatus.FAILED

            verification_report.risk_level = (
                "LOW" if pass_rate >= 95 else
                "MEDIUM" if pass_rate >= 80 else
                "HIGH" if pass_rate >= 60 else "CRITICAL"
            )

        session.verification_report = verification_report
        session.stage_progress[ReviewStage.DIGITAL_TWIN.value] = 1.0

        await self._report_progress(
            session,
            f"数字孪生验证完成，通过率{verification_report.get_pass_rate():.1f}%"
        )

    async def _run_compliance_review(
        self,
        session: ReviewSession,
        report_content: Dict[str, Any],
        project_context: Dict[str, Any]
    ):
        """执行知识图谱合规检查"""
        session.current_stage = ReviewStage.KNOWLEDGE_GRAPH
        await self._report_progress(session, "正在执行合规性检查...")

        compliance_report = await check_compliance_async(
            session.report_id,
            session.project_name,
            report_content,
            project_context
        )

        session.compliance_report = compliance_report
        session.stage_progress[ReviewStage.KNOWLEDGE_GRAPH.value] = 1.0

        issues = compliance_report.get_issue_count()
        await self._report_progress(
            session,
            f"合规检查完成，发现{issues}项问题"
        )

    async def _run_smart_repair(
        self,
        session: ReviewSession,
        report_content: Dict[str, Any],
        project_context: Dict[str, Any]
    ):
        """执行智能修复分析"""
        session.current_stage = ReviewStage.SMART_REPAIR
        await self._report_progress(session, "正在分析修复方案...")

        repair_report = await analyze_and_repair_async(
            session.report_id,
            session.project_name,
            report_content,
            project_context
        )

        session.repair_report = repair_report
        session.stage_progress[ReviewStage.SMART_REPAIR.value] = 1.0

        auto_count = repair_report.auto_repairable
        manual_count = repair_report.manual_required
        await self._report_progress(
            session,
            f"修复分析完成，{auto_count}项可自动修复，{manual_count}项需手动处理"
        )

    async def _run_adversarial_test(
        self,
        session: ReviewSession,
        report_content: Dict[str, Any],
        project_context: Dict[str, Any]
    ):
        """执行对抗性测试"""
        session.current_stage = ReviewStage.ADVERSARIAL_TEST
        await self._report_progress(session, "正在执行对抗性测试...")

        test_report = await run_adversarial_test_async(
            session.report_id,
            session.project_name,
            report_content,
            project_context
        )

        session.test_report = test_report
        session.stage_progress[ReviewStage.ADVERSARIAL_TEST.value] = 1.0

        await self._report_progress(
            session,
            f"对抗性测试完成，{len(test_report.extreme_scenarios)}个极端情景"
        )

    async def _run_distributed_review(
        self,
        session: ReviewSession,
        report_content: Dict[str, Any],
        project_context: Dict[str, Any]
    ):
        """执行分布式审查"""
        session.current_stage = ReviewStage.DISTRIBUTED_REVIEW
        await self._report_progress(session, "正在发起分布式审查...")

        # 初始化分布式网络
        if self.distributed is None:
            self.distributed = get_review_network()

        # 识别争议点
        disputed = []
        if session.verification_report:
            for p in session.verification_report.predictions:
                if p.calculation_status == VerificationStatus.WARNING:
                    disputed.append(f"预测-{p.compound}: {p.verification_message}")

        # 请求审查
        task_id = await self.distributed.request_review(
            session.report_id,
            session.project_name,
            report_content,
            project_context
        )

        session.distributed_task = self.distributed.tasks.get(task_id)
        session.stage_progress[ReviewStage.DISTRIBUTED_REVIEW.value] = 0.5  # 等待投票

        await self._report_progress(
            session,
            f"分布式审查已发起，等待节点投票..."
        )

    async def _report_progress(self, session: ReviewSession, message: str):
        """报告进度"""
        if self.progress_callback:
            await self.progress_callback(session, message)

    def generate_integrated_report(
        self,
        session: ReviewSession
    ) -> IntegratedReviewReport:
        """生成综合审查报告"""
        report = IntegratedReviewReport(
            session_id=session.session_id,
            report_id=session.report_id,
            project_name=session.project_name,
            generated_at=datetime.now()
        )

        # 汇总各维度评分
        if session.verification_report:
            report.verification_score = session.verification_report.get_pass_rate()

        if session.compliance_report:
            risk = session.compliance_report.risk_level
            report.compliance_score = 100 if risk == "LOW" else 75 if risk == "MEDIUM" else 50 if risk == "HIGH" else 25

        if session.test_report:
            if session.test_report.uncertainty_results:
                avg_uncertainty = sum(
                    r.uncertainty_percent for r in session.test_report.uncertainty_results
                ) / len(session.test_report.uncertainty_results)
                report.robustness_score = max(0, 100 - avg_uncertainty)

        if session.consensus_result:
            report.consensus_score = session.consensus_result.consensus_score * 100

        # 计算综合评分
        scores = [s for s in [
            report.verification_score,
            report.compliance_score,
            report.robustness_score,
            report.consensus_score
        ] if s > 0]

        if scores:
            report.overall_score = sum(scores) / len(scores)

        # 确定风险等级
        if report.overall_score >= 90:
            report.risk_level = "LOW"
        elif report.overall_score >= 75:
            report.risk_level = "MEDIUM"
        elif report.overall_score >= 60:
            report.risk_level = "HIGH"
        else:
            report.risk_level = "CRITICAL"

        # 汇总问题
        if session.verification_report:
            for p in session.verification_report.predictions:
                if p.calculation_status == VerificationStatus.FAILED:
                    report.fatal_issues.append(f"数据验证-{p.compound}: {p.verification_message}")
                elif p.calculation_status == VerificationStatus.WARNING:
                    report.warnings.append(f"数据验证-{p.compound}: {p.verification_message}")

            for d in session.verification_report.distance_verifications:
                if d.status == VerificationStatus.FAILED:
                    report.error_issues.append(f"距离验证-{d.sensitive_point}: {d.verification_message}")
                elif d.status == VerificationStatus.WARNING:
                    report.warnings.append(f"距离验证-{d.sensitive_point}: {d.verification_message}")

        if session.compliance_report:
            for check in session.compliance_report.standard_checks:
                if check.status == ComplianceStatus.NON_COMPLIANT:
                    report.error_issues.append(f"合规-{check.standard_code}: {check.description}")
                elif check.status == ComplianceStatus.WARNING:
                    report.warnings.append(f"合规-{check.standard_code}: {check.description}")

        if session.repair_report:
            for issue in session.repair_report.issues:
                if issue.issue_level.value == "fatal":
                    report.fatal_issues.append(f"修复-{issue.issue_description}")
                elif issue.issue_level.value == "error":
                    report.error_issues.append(f"修复-{issue.issue_description}")
                elif issue.issue_level.value == "warning":
                    report.warnings.append(f"修复-{issue.issue_description}")
                else:
                    report.suggestions.append(f"修复-{issue.issue_description}")

            # 自动补丁
            for patch in session.repair_report.auto_patches:
                report.auto_patches.append(patch.to_dict())

            # 修复建议
            for issue in session.repair_report.issues:
                report.repair_suggestions.append(issue.to_dict())

        # 生成结论
        report.total_issues = (
            len(report.fatal_issues) +
            len(report.error_issues) +
            len(report.warnings) +
            len(report.suggestions)
        )

        if report.risk_level == "LOW":
            report.conclusion = "报告质量良好，通过审查"
            report.recommendation = "ACCEPT"
            report.next_steps = ["可提交审批", "建议归档"]
        elif report.risk_level == "MEDIUM":
            report.conclusion = "报告存在一些问题，需要修订"
            report.recommendation = "REVISE"
            report.next_steps = ["处理所有警告项", "确认修复方案", "重新提交审查"]
        elif report.risk_level == "HIGH":
            report.conclusion = "报告存在严重问题，需要大幅修订"
            report.recommendation = "REVISE"
            report.next_steps = ["修复所有错误项", "重新验证数据", "重新提交审查"]
        else:
            report.conclusion = "报告存在致命问题，建议重新编写"
            report.recommendation = "REJECT"
            report.next_steps = ["重新收集数据", "重新编写报告", "重新提交审查"]

        # 生成审查哈希
        report.review_hash = hashlib.sha256(
            json.dumps(report.to_dict(), sort_keys=True).encode()
        ).hexdigest()[:16]

        return report

    def get_session(self, session_id: str) -> Optional[ReviewSession]:
        """获取审查会话"""
        return self.sessions.get(session_id)


# 全局实例
_review_engine_instance: Optional[IntelligentReviewEngine] = None


def get_review_engine() -> IntelligentReviewEngine:
    """获取智能审查引擎全局实例"""
    global _review_engine_instance
    if _review_engine_instance is None:
        _review_engine_instance = IntelligentReviewEngine()
    return _review_engine_instance


async def start_review_async(
    report_id: str,
    project_name: str,
    report_content: Dict[str, Any],
    project_context: Dict[str, Any],
    mode: ReviewMode = ReviewMode.AUTO
) -> ReviewSession:
    """异步开始审查的便捷函数"""
    engine = get_review_engine()
    return await engine.start_review(
        report_id, project_name, report_content, project_context, mode
    )


def generate_integrated_report(session: ReviewSession) -> IntegratedReviewReport:
    """生成综合审查报告的便捷函数"""
    engine = get_review_engine()
    return engine.generate_integrated_report(session)