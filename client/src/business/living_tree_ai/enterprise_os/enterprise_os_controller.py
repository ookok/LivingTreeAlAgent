"""
企业数字中台主控制器

整合所有模块，提供企业全生命周期智能合规与运营服务。
"""

import json
import asyncio
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from enum import Enum
from datetime import datetime
from pathlib import Path

# 导入子模块
from .enterprise_digital_twin import (
    EnterpriseDigitalTwin,
    EnterpriseDigitalTwinManager,
    LifecycleStage,
    ComplianceStatus,
    get_twin_manager,
    create_enterprise_twin_async,
    get_enterprise_twin,
)

from .compliance_knowledge_graph import (
    ComplianceKnowledgeGraph,
    ComplianceCheckResult,
    get_knowledge_graph,
    query_compliance_async,
    build_enterprise_graph_async,
)

from .declaration_pipeline import (
    DeclarationPipeline,
    DeclarationTask,
    DeclarationType,
    PipelineStatus,
    get_pipeline_engine,
    create_pipeline_async,
    execute_declaration_async,
)

from .gov_site_adapter import (
    GovSiteAdapter,
    get_adapter,
)

from .risk_early_warning import (
    RiskEarlyWarningEngine,
    RiskAlert,
    RiskLevel,
    RiskCategory,
    get_risk_engine,
    check_risks_async,
)


# ==================== 数据模型 ====================

class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """任务优先级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class ComplianceTask:
    """合规任务"""
    task_id: str
    enterprise_id: str
    task_type: str              # eia_report/pollution_permit/annual_report等
    title: str
    description: str = ""
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING

    # 时间
    due_date: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 关联
    related_documents: List[str] = field(default_factory=list)
    risk_alerts: List[str] = field(default_factory=list)  # alert_ids

    # 执行
    pipeline_id: str = ""       # 关联的申报流水线ID
    result: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EnterpriseOSConfig:
    """企业数字中台配置"""
    name: str = "Enterprise OS"
    version: str = "1.0"

    # 能力开关
    enable_auto_filing: bool = True           # 自动申报
    enable_risk_monitoring: bool = True       # 风险监控
    enable_compliance_check: bool = True      # 合规检查
    enable_knowledge_graph: bool = True       # 知识图谱

    # 监控配置
    risk_check_interval: int = 3600          # 风险检查间隔(秒)
    policy_monitor_interval: int = 86400     # 政策监测间隔(秒)

    # 申报配置
    auto_retry: bool = True                 # 自动重试
    max_retries: int = 3                    # 最大重试次数
    notify_on_complete: bool = True          # 完成通知


@dataclass
class DashboardData:
    """仪表盘数据"""
    enterprise_id: str
    company_name: str
    lifecycle_stage: str

    # 合规状态
    compliance_score: float
    compliance_status: str
    pending_tasks: int
    overdue_tasks: int

    # 风险状态
    risk_level: str
    active_alerts: int
    critical_alerts: int

    # 近期动态
    recent_activities: List[Dict] = field(default_factory=list)

    # 统计
    stats: Dict[str, Any] = field(default_factory=dict)


# ==================== 企业数字中台主控制器 ====================

class EnterpriseOSController:
    """
    企业数字中台主控制器

    整合所有模块，提供企业全生命周期智能合规与运营服务。

    功能：
    - 企业数字孪生管理
    - 合规知识图谱
    - 智能申报流水线
    - 政府网站适配
    - 风险预警监控
    - 智能工作流编排
    """

    def __init__(self, config: EnterpriseOSConfig = None):
        self.config = config or EnterpriseOSConfig()

        # 初始化子模块
        self._twin_manager = get_twin_manager()
        self._kg = get_knowledge_graph()
        self._pipeline = get_pipeline_engine()
        self._gov_adapter = get_adapter()
        self._risk_engine = get_risk_engine()

        # 任务管理
        self._tasks: Dict[str, ComplianceTask] = {}

        # 定时任务
        self._scheduled_tasks: List[Dict] = []
        self._running = False

    # ==================== 企业生命周期管理 ====================

    async def register_enterprise(
        self,
        company_name: str,
        credit_code: str,
        identity_info: Dict = None
    ) -> EnterpriseDigitalTwin:
        """
        注册企业

        Args:
            company_name: 公司名称
            credit_code: 统一社会信用代码
            identity_info: 身份信息

        Returns:
            EnterpriseDigitalTwin: 企业数字孪生
        """
        # 创建数字孪生
        twin = await create_enterprise_twin_async(
            company_name,
            credit_code,
            identity_info
        )

        # 构建知识图谱
        if identity_info:
            await build_enterprise_graph_async({
                "credit_code": credit_code,
                "company_name": company_name,
                **identity_info
            })

        return twin

    async def get_enterprise(self, credit_code: str = None, twin_id: str = None) -> Optional[EnterpriseDigitalTwin]:
        """获取企业数字孪生"""
        if twin_id:
            return self._twin_manager.get_twin(twin_id)
        elif credit_code:
            return self._twin_manager.get_twin_by_credit_code(credit_code)
        return None

    async def update_lifecycle_stage(
        self,
        enterprise_id: str,
        stage: LifecycleStage
    ) -> bool:
        """更新生命周期阶段"""
        twin = self._twin_manager.get_twin(enterprise_id)
        if not twin:
            return False

        return await self._twin_manager.update_lifecycle_stage(enterprise_id, stage)

    # ==================== 合规任务管理 ====================

    async def create_compliance_task(
        self,
        enterprise_id: str,
        task_type: str,
        title: str,
        description: str = "",
        due_date: datetime = None,
        priority: TaskPriority = TaskPriority.MEDIUM
    ) -> ComplianceTask:
        """
        创建合规任务

        Args:
            enterprise_id: 企业ID
            task_type: 任务类型
            title: 标题
            description: 描述
            due_date: 截止日期
            priority: 优先级

        Returns:
            ComplianceTask: 创建的任务
        """
        task_id = self._generate_task_id(enterprise_id, task_type)

        task = ComplianceTask(
            task_id=task_id,
            enterprise_id=enterprise_id,
            task_type=task_type,
            title=title,
            description=description,
            priority=priority,
            due_date=due_date
        )

        self._tasks[task_id] = task
        return task

    async def execute_task(
        self,
        task_id: str,
        context: Dict = None
    ) -> ComplianceTask:
        """
        执行合规任务

        Args:
            task_id: 任务ID
            context: 执行上下文

        Returns:
            ComplianceTask: 执行结果
        """
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now()

        try:
            # 根据任务类型选择执行策略
            if task.task_type in ["eia_report", "pollution_permit", "safety_permit"]:
                # 需要申报流水线
                result = await self._execute_declaration_task(task, context)
            elif task.task_type == "compliance_check":
                # 合规检查
                result = await self._execute_compliance_check(task, context)
            elif task.task_type == "risk_assessment":
                # 风险评估
                result = await self._execute_risk_assessment(task, context)
            else:
                result = {"success": False, "error": f"未知的任务类型: {task.task_type}"}

            task.result = result
            task.status = TaskStatus.COMPLETED

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.result = {"success": False, "error": str(e)}

        finally:
            task.completed_at = datetime.now()

        return task

    async def _execute_declaration_task(
        self,
        task: ComplianceTask,
        context: Dict
    ) -> Dict:
        """执行申报任务"""
        # 获取企业数据
        twin = self._twin_manager.get_twin(task.enterprise_id)
        if not twin:
            return {"success": False, "error": "企业不存在"}

        # 创建申报流水线
        decl_type_map = {
            "eia_report": DeclarationType.EIA_REPORT,
            "pollution_permit": DeclarationType.POLLUTION_PERMIT,
            "safety_permit": DeclarationType.SAFETY_PERMIT,
            "annual_report": DeclarationType.ANNUAL_REPORT,
        }

        decl_type = decl_type_map.get(task.task_type, DeclarationType.OTHER)

        pipeline_task = await create_pipeline_async(
            decl_type.value,
            task.enterprise_id,
            task.title
        )

        task.pipeline_id = pipeline_task.task_id

        # 执行流水线
        result = await execute_declaration_async(
            pipeline_task.task_id,
            context or {}
        )

        return {
            "success": result.status == PipelineStatus.COMPLETED,
            "pipeline_id": pipeline_task.task_id,
            "result": result.result
        }

    async def _execute_compliance_check(
        self,
        task: ComplianceTask,
        context: Dict
    ) -> Dict:
        """执行合规检查"""
        twin = self._twin_manager.get_twin(task.enterprise_id)
        if not twin:
            return {"success": False, "error": "企业不存在"}

        # 执行合规检查
        check_result = await query_compliance_async(
            task.enterprise_id,
            context.get("regulation_id")
        )

        return {
            "success": True,
            "check_result": {
                "is_compliant": check_result.is_compliant,
                "issues": check_result.issues,
                "risk_level": check_result.risk_level
            }
        }

    async def _execute_risk_assessment(
        self,
        task: ComplianceTask,
        context: Dict
    ) -> Dict:
        """执行风险评估"""
        twin = self._twin_manager.get_twin(task.enterprise_id)
        if not twin:
            return {"success": False, "error": "企业不存在"}

        # 执行风险检查
        alerts = await check_risks_async(
            task.enterprise_id,
            context or {}
        )

        return {
            "success": True,
            "alerts_count": len(alerts),
            "critical_count": len([a for a in alerts if a.risk_level == RiskLevel.CRITICAL])
        }

    def get_task(self, task_id: str) -> Optional[ComplianceTask]:
        """获取任务"""
        return self._tasks.get(task_id)

    def get_tasks_by_enterprise(
        self,
        enterprise_id: str,
        status: TaskStatus = None
    ) -> List[ComplianceTask]:
        """获取企业的任务"""
        tasks = [t for t in self._tasks.values() if t.enterprise_id == enterprise_id]

        if status:
            tasks = [t for t in tasks if t.status == status]

        return sorted(tasks, key=lambda x: x.created_at, reverse=True)

    # ==================== 仪表盘 ====================

    async def get_dashboard(self, enterprise_id: str) -> DashboardData:
        """
        获取企业仪表盘

        Args:
            enterprise_id: 企业ID

        Returns:
            DashboardData: 仪表盘数据
        """
        twin = self._twin_manager.get_twin(enterprise_id)

        if not twin:
            return DashboardData(
                enterprise_id=enterprise_id,
                company_name="未知",
                lifecycle_stage="未知",
                compliance_score=0.0,
                compliance_status="UNKNOWN",
                pending_tasks=0,
                overdue_tasks=0,
                risk_level="UNKNOWN",
                active_alerts=0,
                critical_alerts=0
            )

        # 获取任务统计
        tasks = self.get_tasks_by_enterprise(enterprise_id)
        pending_tasks = len([t for t in tasks if t.status == TaskStatus.PENDING])
        overdue_tasks = len([
            t for t in tasks
            if t.due_date and t.due_date < datetime.now() and t.status != TaskStatus.COMPLETED
        ])

        # 获取风险统计
        risk_stats = self._risk_engine.get_statistics(enterprise_id)

        # 获取合规评分
        compliance_score = twin.compliance_score

        return DashboardData(
            enterprise_id=enterprise_id,
            company_name=twin.company_name,
            lifecycle_stage=twin.lifecycle_stage.value,
            compliance_score=compliance_score,
            compliance_status="HEALTHY" if compliance_score > 80 else "WARNING" if compliance_score > 60 else "CRITICAL",
            pending_tasks=pending_tasks,
            overdue_tasks=overdue_tasks,
            risk_level=risk_stats.get("risk_level", "LOW"),
            active_alerts=risk_stats.get("unresolved", 0),
            critical_alerts=risk_stats.get("critical", 0),
            recent_activities=[],
            stats={
                "total_tasks": len(tasks),
                "completed_tasks": len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
                "risk_stats": risk_stats
            }
        )

    # ==================== 定时任务 ====================

    async def start_monitoring(self):
        """启动监控"""
        self._running = True

        while self._running:
            try:
                # 风险检查
                for twin in self._twin_manager.get_all_twins():
                    await check_risks_async(
                        twin.twin_id,
                        self._twin_to_data(twin)
                    )

                # 等待下一次检查
                await asyncio.sleep(self.config.risk_check_interval)

            except Exception as e:
                print(f"监控异常: {e}")
                await asyncio.sleep(60)

    def stop_monitoring(self):
        """停止监控"""
        self._running = False

    def _twin_to_data(self, twin: EnterpriseDigitalTwin) -> Dict:
        """将数字孪生转换为数据字典"""
        return {
            "credit_code": twin.credit_code,
            "company_name": twin.company_name,
            "permits": [
                {"permit_type": ob.obligation_type, "expiry_date": str(ob.due_date) if ob.due_date else None}
                for ob in twin.dimensions.compliance
            ],
            "emission_data": twin.dimensions.operational_data.financial
        }

    def _generate_task_id(self, enterprise_id: str, task_type: str) -> str:
        """生成任务ID"""
        timestamp = datetime.now().isoformat()
        raw = f"{enterprise_id}_{task_type}_{timestamp}"
        return f"task_{hashlib.md5(raw.encode()).hexdigest()[:12]}"


# ==================== 便捷函数 ====================

_os_instance: Optional[EnterpriseOSController] = None


def get_enterprise_os(config: EnterpriseOSConfig = None) -> EnterpriseOSController:
    """获取企业数字中台单例"""
    global _os_instance
    if _os_instance is None:
        _os_instance = EnterpriseOSController(config)
    return _os_instance


async def create_enterprise_os_async(
    company_name: str,
    credit_code: str,
    identity_info: Dict = None
) -> EnterpriseDigitalTwin:
    """创建企业的便捷函数"""
    os_controller = get_enterprise_os()
    return await os_controller.register_enterprise(company_name, credit_code, identity_info)


async def execute_lifecycle_task_async(
    task_type: str,
    enterprise_id: str,
    context: Dict = None
) -> ComplianceTask:
    """执行生命周期任务的便捷函数"""
    os_controller = get_enterprise_os()

    # 创建任务
    task = await os_controller.create_compliance_task(
        enterprise_id=enterprise_id,
        task_type=task_type,
        title=f"{task_type}任务",
        description=f"执行{task_type}相关任务"
    )

    # 执行任务
    return await os_controller.execute_task(task.task_id, context)
