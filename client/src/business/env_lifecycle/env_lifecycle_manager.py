"""
环保全生命周期管理器 - Environmental Lifecycle Manager
=====================================================

核心职责：
1. 环保数字护照管理 - 每个项目的终身数字身份
2. 阶段状态追踪 - 七阶段闭环管理
3. 事件驱动协调 - 各模块间消息传递
4. 知识沉淀与复用 - 历史经验积累
"""

import json
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from collections import defaultdict


class LifecycleStage(Enum):
    """生命周期阶段枚举"""
    EIA = "eia"                    # 环境影响评价
    CONSTRUCTION = "construction"  # 建设期监理
    ACCEPTANCE = "acceptance"      # 竣工环保验收
    PERMIT = "permit"             # 排污许可
    OPERATION = "operation"        # 运营期
    EMERGENCY = "emergency"       # 环境应急
    DECOMMISSION = "decommission" # 退役期


class LifecycleStatus(Enum):
    """阶段状态"""
    PENDING = "pending"           # 待开始
    IN_PROGRESS = "in_progress"   # 进行中
    REVIEW = "review"            # 审核中
    APPROVED = "approved"         # 已通过
    REJECTED = "rejected"         # 被驳回
    EXPIRED = "expired"          # 已过期
    CANCELLED = "cancelled"      # 已取消


class AutopilotLevel(Enum):
    """自动驾驶等级"""
    L1_ASSISTED = 1   # 辅助生成报告
    L2_SEMI_AUTO = 2  # 半自动化
    L3_CONDITIONAL = 3  # 条件自动化
    L4_HIGHLY_AUTO = 4  # 高度自动化
    L5_FULL_AUTO = 5     # 完全自动化


@dataclass
class ProjectRecord:
    """项目记录 - 环保数字护照的核心单元"""
    project_id: str
    project_name: str
    company_id: str
    company_name: str

    # 基本信息
    industry: str = ""                    # 行业类别
    region: str = ""                     # 所属区域
    investment: float = 0.0              # 投资额(万元)
    capacity: str = ""                    # 产能规模

    # 地理位置
    latitude: float = 0.0
    longitude: float = 0.0
    address: str = ""

    # 阶段信息
    current_stage: LifecycleStage = LifecycleStage.EIA
    stage_status: LifecycleStatus = LifecycleStatus.PENDING
    autopilot_level: AutopilotLevel = AutopilotLevel.L1_ASSISTED

    # 时间线
    created_at: str = ""
    updated_at: str = ""
    stage_deadlines: Dict[str, str] = field(default_factory=dict)

    # 数字护照数据
    documents: List[Dict] = field(default_factory=list)    # 文档清单
    monitoring_data: List[Dict] = field(default_factory=list)  # 监测数据
    violations: List[Dict] = field(default_factory=list)   # 违规记录
    approvals: List[Dict] = field(default_factory=list)    # 审批记录

    # 元数据
    tags: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'ProjectRecord':
        if isinstance(data.get('current_stage'), str):
            data['current_stage'] = LifecycleStage(data['current_stage'])
        if isinstance(data.get('stage_status'), str):
            data['stage_status'] = LifecycleStatus(data['stage_status'])
        if isinstance(data.get('autopilot_level'), int):
            data['autopilot_level'] = AutopilotLevel(data['autopilot_level'])
        return cls(**data)


@dataclass
class EnvPassport:
    """
    环保数字护照 - Environmental Digital Passport
    ============================================

    为每个项目建立的终身伴随的数字身份，贯穿项目全生命周期。

    数据结构：
    - 基本信息：项目身份
    - 阶段档案：各阶段的完整记录
    - 监测历史：持续积累的监测数据
    - 事件溯源：违规、整改、事故完整链条
    - 信用档案：环保信用评分
    """
    passport_id: str
    project_record: ProjectRecord

    # 阶段档案
    eia_archive: Dict = field(default_factory=dict)      # 环评档案
    construction_archive: Dict = field(default_factory=dict)  # 建设档案
    acceptance_archive: Dict = field(default_factory=dict)    # 验收档案
    permit_archive: Dict = field(default_factory=dict)       # 许可档案
    operation_archive: Dict = field(default_factory=dict)    # 运营档案
    emergency_archive: Dict = field(default_factory=dict)    # 应急档案
    decommission_archive: Dict = field(default_factory=dict)  # 退役档案

    # 统一数据湖引用
    data_sources: List[Dict] = field(default_factory=list)

    # 区块链锚定
    chain_hash: str = ""  # 链式哈希，确保不可篡改
    last_sync: str = ""

    def get_archive(self, stage: LifecycleStage) -> Dict:
        """获取指定阶段的档案"""
        archives = {
            LifecycleStage.EIA: self.eia_archive,
            LifecycleStage.CONSTRUCTION: self.construction_archive,
            LifecycleStage.ACCEPTANCE: self.acceptance_archive,
            LifecycleStage.PERMIT: self.permit_archive,
            LifecycleStage.OPERATION: self.operation_archive,
            LifecycleStage.EMERGENCY: self.emergency_archive,
            LifecycleStage.DECOMMISSION: self.decommission_archive,
        }
        return archives.get(stage, {})

    def get_health_score(self) -> float:
        """
        计算环保健康指数 (0-100)
        ========================
        类似于"信用分"，综合评估企业环保状态
        """
        score = 100.0

        # 违规扣分
        for violation in self.project_record.violations:
            severity = violation.get('severity', 'minor')
            if severity == 'major':
                score -= 20
            elif severity == 'moderate':
                score -= 10
            else:
                score -= 5

        # 超标排放扣分
        for data in self.project_record.monitoring_data:
            if data.get('exceeded', False):
                score -= 15

        # 逾期未整改扣分
        for doc in self.project_record.documents:
            if doc.get('overdue', False):
                score -= 5

        return max(0.0, min(100.0, score))

    def predict_risk_30d(self) -> Dict:
        """
        预测未来30天被处罚概率
        ======================
        返回: {probability: float, factors: List[str], suggestions: List[str]}
        """
        factors = []
        suggestions = []
        probability = 0.1  # 基础概率10%

        # 分析监测数据趋势
        recent_exceedances = sum(
            1 for d in self.project_record.monitoring_data[-30:]
            if d.get('exceeded', False)
        )
        if recent_exceedances > 5:
            probability += 0.2
            factors.append(f"近30天超标{recent_exceedances}次")
            suggestions.append("立即排查超标原因")

        # 检查许可证即将到期
        permit = self.permit_archive
        if permit.get('days_to_expire', 999) < 90:
            probability += 0.15
            factors.append("排污许可证即将到期")
            suggestions.append("提前90天准备延续申请")

        # 检查待整改项
        pending_fixes = sum(1 for v in self.project_record.violations if not v.get('fixed', False))
        if pending_fixes > 3:
            probability += 0.1 * pending_fixes
            factors.append(f"存在{pending_fixes}项待整改")
            suggestions.append("优先处理重大违规")

        # 行业风险系数
        high_risk_industries = ['化工', '造纸', '电镀', '皮革', '印染']
        if self.project_record.industry in high_risk_industries:
            probability *= 1.5
            factors.append("属于高风险行业")

        return {
            'probability': min(1.0, probability),
            'factors': factors,
            'suggestions': suggestions,
            'health_score': self.get_health_score()
        }


class EnvLifecycleManager:
    """
    环保全生命周期管理器
    =====================

    核心功能：
    1. 项目注册与护照发放
    2. 阶段流转管理
    3. 事件记录与追溯
    4. 跨模块协调
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or "data/env_lifecycle.db"
        self._projects: Dict[str, ProjectRecord] = {}
        self._passports: Dict[str, EnvPassport] = {}
        self._event_log: List[Dict] = []
        self._stage_handlers = {}  # 阶段处理器

    def register_project(self, project_data: Dict) -> str:
        """
        注册新项目，发放环保数字护照
        ==============================

        Args:
            project_data: {
                "project_name": "XX化工项目",
                "company_id": "C001",
                "company_name": "XX化工有限公司",
                "industry": "化工",
                ...
            }

        Returns:
            passport_id: 环保数字护照ID
        """
        project_id = project_data.get('project_id') or str(uuid.uuid4())[:8]
        passport_id = f"EP-{project_id}-{datetime.now().strftime('%Y%m%d')}"

        # 创建项目记录
        project_record = ProjectRecord(
            project_id=project_id,
            project_name=project_data['project_name'],
            company_id=project_data['company_id'],
            company_name=project_data['company_name'],
            industry=project_data.get('industry', ''),
            region=project_data.get('region', ''),
            investment=project_data.get('investment', 0.0),
            capacity=project_data.get('capacity', ''),
            latitude=project_data.get('latitude', 0.0),
            longitude=project_data.get('longitude', 0.0),
            address=project_data.get('address', ''),
            current_stage=LifecycleStage.EIA,
            stage_status=LifecycleStatus.PENDING,
        )

        # 创建数字护照
        passport = EnvPassport(
            passport_id=passport_id,
            project_record=project_record
        )

        # 存储
        self._projects[project_id] = project_record
        self._passports[passport_id] = passport

        # 记录事件
        self._log_event(project_id, "PROJECT_REGISTERED", {
            "passport_id": passport_id,
            "stage": LifecycleStage.EIA.value
        })

        return passport_id

    def transition_stage(self, project_id: str, target_stage: LifecycleStage,
                         metadata: Dict = None) -> bool:
        """
        阶段流转 - 环保数字护照状态更新
        ================================

        流转规则：
        EIA → CONSTRUCTION → ACCEPTANCE → PERMIT → OPERATION
                                                          ↓
                                                    EMERGENCY (突发)
                                                          ↓
                                                    DECOMMISSION
        """
        project = self._projects.get(project_id)
        if not project:
            return False

        # 验证流转顺序
        stage_order = list(LifecycleStage)
        current_idx = stage_order.index(project.current_stage)
        target_idx = stage_order.index(target_stage)

        # 允许的跳转：正向一步、或者跳过(快速通道)、或者进入应急
        if target_stage == LifecycleStage.EMERGENCY:
            # 应急阶段可从任何运营阶段触发
            if project.current_stage not in [LifecycleStage.OPERATION, LifecycleStage.EMERGENCY]:
                return False
        elif target_idx > current_idx + 1:
            # 跳过阶段需要特殊许可
            if not metadata.get('fast_track', False):
                return False

        # 更新状态
        old_stage = project.current_stage
        project.current_stage = target_stage
        project.stage_status = LifecycleStatus.IN_PROGRESS
        project.updated_at = datetime.now().isoformat()

        # 记录流转
        self._log_event(project_id, "STAGE_TRANSITION", {
            "from": old_stage.value,
            "to": target_stage.value,
            "metadata": metadata or {}
        })

        return True

    def update_document(self, project_id: str, doc_type: str,
                        doc_data: Dict) -> bool:
        """更新项目文档"""
        project = self._projects.get(project_id)
        if not project:
            return False

        doc_entry = {
            "type": doc_type,
            "data": doc_data,
            "uploaded_at": datetime.now().isoformat(),
            "verified": False
        }
        project.documents.append(doc_entry)

        self._log_event(project_id, "DOCUMENT_UPDATED", {
            "doc_type": doc_type
        })

        return True

    def add_monitoring_data(self, project_id: str, monitoring_data: Dict) -> bool:
        """添加监测数据到数字护照"""
        project = self._projects.get(project_id)
        if not project:
            return False

        data_entry = {
            **monitoring_data,
            "recorded_at": datetime.now().isoformat()
        }

        # 自动判断是否超标
        if 'limit' in monitoring_data and 'value' in monitoring_data:
            data_entry['exceeded'] = monitoring_data['value'] > monitoring_data['limit']

        project.monitoring_data.append(data_entry)

        # 如果超标，触发预警
        if data_entry.get('exceeded', False):
            self._log_event(project_id, "EXCEEDANCE_DETECTED", {
                "pollutant": monitoring_data.get('pollutant'),
                "value": monitoring_data.get('value'),
                "limit": monitoring_data.get('limit')
            })

        return True

    def add_violation(self, project_id: str, violation_data: Dict) -> bool:
        """记录违规"""
        project = self._projects.get(project_id)
        if not project:
            return False

        violation_entry = {
            **violation_data,
            "recorded_at": datetime.now().isoformat(),
            "fixed": False
        }
        project.violations.append(violation_entry)

        self._log_event(project_id, "VIOLATION_RECORDED", {
            "severity": violation_data.get('severity'),
            "description": violation_data.get('description', '')[:50]
        })

        return True

    def fix_violation(self, project_id: str, violation_id: str,
                      fix_data: Dict = None) -> bool:
        """整改违规"""
        project = self._projects.get(project_id)
        if not project:
            return False

        for v in project.violations:
            if v.get('id') == violation_id:
                v['fixed'] = True
                v['fixed_at'] = datetime.now().isoformat()
                v['fix_data'] = fix_data or {}

                self._log_event(project_id, "VIOLATION_FIXED", {
                    "violation_id": violation_id
                })
                return True

        return False

    def get_passport(self, project_id: str = None,
                     passport_id: str = None) -> Optional[EnvPassport]:
        """获取环保数字护照"""
        if passport_id:
            return self._passports.get(passport_id)
        if project_id:
            project = self._projects.get(project_id)
            if project:
                # 查找对应的护照
                for passport in self._passports.values():
                    if passport.project_record.project_id == project_id:
                        return passport
        return None

    def get_project_status(self, project_id: str) -> Dict:
        """获取项目状态概览"""
        project = self._projects.get(project_id)
        if not project:
            return {}

        passport = self.get_passport(project_id=project_id)

        return {
            "project_id": project.project_id,
            "project_name": project.project_name,
            "company_name": project.company_name,
            "current_stage": project.current_stage.value,
            "stage_display": project.current_stage.name,
            "stage_status": project.stage_status.value,
            "autopilot_level": project.autopilot_level.value,
            "health_score": passport.get_health_score() if passport else None,
            "risk_prediction": passport.predict_risk_30d() if passport else None,
            "document_count": len(project.documents),
            "monitoring_count": len(project.monitoring_data),
            "violation_count": len(project.violations),
            "pending_violations": sum(1 for v in project.violations if not v.get('fixed')),
            "updated_at": project.updated_at,
        }

    def get_all_projects(self, stage: LifecycleStage = None,
                         status: LifecycleStatus = None) -> List[Dict]:
        """获取所有项目列表"""
        results = []
        for project in self._projects.values():
            if stage and project.current_stage != stage:
                continue
            if status and project.stage_status != status:
                continue
            results.append(self.get_project_status(project.project_id))
        return results

    def _log_event(self, project_id: str, event_type: str, event_data: Dict):
        """记录事件日志"""
        event = {
            "event_id": str(uuid.uuid4())[:12],
            "project_id": project_id,
            "event_type": event_type,
            "event_data": event_data,
            "timestamp": datetime.now().isoformat()
        }
        self._event_log.append(event)

    def get_event_log(self, project_id: str = None,
                      event_type: str = None,
                      limit: int = 100) -> List[Dict]:
        """查询事件日志"""
        events = self._event_log

        if project_id:
            events = [e for e in events if e['project_id'] == project_id]
        if event_type:
            events = [e for e in events if e['event_type'] == event_type]

        return events[-limit:]

    def export_passport(self, project_id: str) -> Dict:
        """导出不带敏感信息的护照摘要"""
        passport = self.get_passport(project_id=project_id)
        if not passport:
            return {}

        return {
            "passport_id": passport.passport_id,
            "project": {
                "name": passport.project_record.project_name,
                "company": passport.project_record.company_name,
                "industry": passport.project_record.industry,
                "region": passport.project_record.region,
            },
            "current_stage": passport.project_record.current_stage.value,
            "health_score": passport.get_health_score(),
            "risk_prediction": passport.predict_risk_30d(),
            "summary": {
                "total_documents": len(passport.project_record.documents),
                "total_monitoring": len(passport.project_record.monitoring_data),
                "total_violations": len(passport.project_record.violations),
                "pending_violations": sum(1 for v in passport.project_record.violations if not v.get('fixed')),
            },
            "chain_hash": passport.chain_hash,
            "exported_at": datetime.now().isoformat()
        }


# 全局单例
_lifecycle_manager = None

def get_lifecycle_manager() -> EnvLifecycleManager:
    """获取生命周期管理器单例"""
    global _lifecycle_manager
    if _lifecycle_manager is None:
        _lifecycle_manager = EnvLifecycleManager()
    return _lifecycle_manager
