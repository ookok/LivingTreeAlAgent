"""
企业Profile微服务

为企业提供统一的数字身份档案，实现"一企一档"的合规管理。

核心功能：
1. 企业数字档案（基于数字孪生）
2. 合规日历（证照有效期/申报节点）
3. 资产图谱（设备/专利/资质）
4. 数据同步引擎
"""

import json
import asyncio
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from enum import Enum
from datetime import datetime, timedelta


# ==================== 数据模型 ====================

class DataSource(Enum):
    """数据来源"""
    MANUAL = "manual"                    # 人工录入
    AUTO_EXTRACT = "auto_extract"        # AI自动提取
    GOV_SYNC = "gov_sync"               # 政府系统同步
    THIRD_PARTY = "third_party"          # 第三方接入


class DataConfidence(Enum):
    """数据置信度"""
    HIGH = "high"        # >90% 自动提交
    MEDIUM = "medium"    # 60-90% AI辅助
    LOW = "low"          # <60% 人工复核


@dataclass
class DataField:
    """数据字段"""
    key: str
    value: Any
    source: DataSource = DataSource.MANUAL
    confidence: DataConfidence = DataConfidence.HIGH
    last_updated: datetime = field(default_factory=datetime.now)
    verified: bool = False
    verified_by: str = ""
    history: List[Dict] = field(default_factory=list)  # 历史变更


@dataclass
class AssetNode:
    """资产节点"""
    asset_id: str
    asset_type: str                    # facility/patent/trademark/certificate/license
    name: str
    category: str
    properties: Dict[str, Any] = field(default_factory=dict)
    related_obligations: List[str] = field(default_factory=list)  # 关联合规义务
    status: str = "active"             # active/expired/revoked
    expiry_date: Optional[datetime] = None
    renewal_notice_days: int = 90       # 续期提醒天数


@dataclass
class ComplianceCalendarEvent:
    """合规日历事件"""
    event_id: str
    enterprise_id: str
    obligation_id: str                   # 关联合规义务ID
    event_type: str                     # license_expiry/annual_report/quarterly_report/filing
    title: str
    description: str = ""
    due_date: datetime
    reminder_days: List[int] = field(default_factory=lambda: [30, 60, 90])  # 提醒天数
    status: str = "pending"             # pending/completed/overdue
    auto_executable: bool = False       # 是否可自动执行
    confidence_threshold: float = 0.9   # 自动执行置信度阈值
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


@dataclass
class EnterpriseProfile:
    """
    企业Profile - 一企一档核心数据模型

    基于数字孪生，但更强调"合规日历"和"资产图谱"
    """
    # 核心标识
    profile_id: str
    twin_id: str                        # 关联的数字孪生ID
    credit_code: str
    company_name: str

    # 基础档案（从数字孪生同步）
    basic_info: Dict[str, DataField] = field(default_factory=dict)
    identity_info: Dict[str, DataField] = field(default_factory=dict)
    tax_info: Dict[str, DataField] = field(default_factory=dict)
    industry_info: Dict[str, DataField] = field(default_factory=dict)

    # 合规日历
    compliance_calendar: List[ComplianceCalendarEvent] = field(default_factory=list)

    # 资产图谱
    asset_graph: Dict[str, AssetNode] = field(default_factory=dict)  # asset_id -> AssetNode

    # 政府系统关联
    gov_system_accounts: Dict[str, Dict] = field(default_factory=dict)  # system -> account_info

    # 数据质量
    data_quality_score: float = 1.0     # 0-1
    last_full_sync: Optional[datetime] = None
    sync_status: str = "idle"          # idle/syncing/error

    # 租户隔离
    tenant_id: str = "default"         # 租户ID，确保数据隔离

    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


# ==================== 合规日历管理器 ====================

class ComplianceCalendarManager:
    """
    合规日历管理器

    核心功能：
    1. 自动生成合规事件（证照到期、申报截止）
    2. 智能提醒（30/60/90天提醒）
    3. 自动续期任务创建
    """

    # 内置合规事件模板
    EVENT_TEMPLATES = {
        "license_expiry": {
            "event_type": "license_expiry",
            "title_template": "{name}到期",
            "description_template": "{asset_type}证照即将到期，请及时续期",
            "auto_executable": True,
            "confidence_threshold": 0.9
        },
        "annual_report": {
            "event_type": "annual_report",
            "title_template": "年度报告提交",
            "description_template": "{category}年度报告提交截止日期",
            "auto_executable": True,
            "confidence_threshold": 0.85
        },
        "quarterly_report": {
            "event_type": "quarterly_report",
            "title_template": "季度报告提交",
            "description_template": "{category}季度报告提交",
            "auto_executable": True,
            "confidence_threshold": 0.9
        },
        "tax_filing": {
            "event_type": "tax_filing",
            "title_template": "税务申报",
            "description_template": "{tax_type}申报截止",
            "auto_executable": True,
            "confidence_threshold": 0.95
        }
    }

    def __init__(self):
        self._events: Dict[str, List[ComplianceCalendarEvent]] = {}  # profile_id -> events

    async def generate_calendar_events(
        self,
        profile: EnterpriseProfile,
        asset_graph: Dict[str, AssetNode]
    ) -> List[ComplianceCalendarEvent]:
        """
        从资产图谱自动生成合规日历事件

        Args:
            profile: 企业Profile
            asset_graph: 资产图谱

        Returns:
            生成的合规事件列表
        """
        events = []

        # 1. 从证照资产生成到期事件
        for asset_id, asset in asset_graph.items():
            if asset.asset_type in ["certificate", "license"]:
                event = self._create_expiry_event(profile, asset)
                events.append(event)

            # 关联的合规义务也生成事件
            for obligation_id in asset.related_obligations:
                events.extend(self._create_obligation_events(profile, obligation_id, asset))

        # 2. 添加周期性申报事件
        events.extend(self._create_periodic_events(profile))

        # 3. 更新Profile
        self._events[profile.profile_id] = events

        return events

    def _create_expiry_event(
        self,
        profile: EnterpriseProfile,
        asset: AssetNode
    ) -> ComplianceCalendarEvent:
        """创建证照到期事件"""
        template = self.EVENT_TEMPLATES["license_expiry"]

        # 计算提醒日期
        if asset.expiry_date:
            reminder_dates = [
                asset.expiry_date - timedelta(days=d)
                for d in template["reminder_days"]
            ]

        event_id = self._generate_event_id(profile.profile_id, asset.asset_id, "expiry")

        return ComplianceCalendarEvent(
            event_id=event_id,
            enterprise_id=profile.profile_id,
            obligation_id=asset.asset_id,
            event_type=template["event_type"],
            title=template["title_template"].format(name=asset.name),
            description=template["description_template"].format(
                asset_type=asset.asset_type
            ),
            due_date=asset.expiry_date or datetime.now() + timedelta(days=365),
            reminder_days=template["reminder_days"],
            auto_executable=template["auto_executable"],
            confidence_threshold=template["confidence_threshold"]
        )

    def _create_obligation_events(
        self,
        profile: EnterpriseProfile,
        obligation_id: str,
        asset: AssetNode
    ) -> List[ComplianceCalendarEvent]:
        """创建合规义务相关事件"""
        events = []

        # 根据义务类型创建对应事件
        obligation_templates = {
            "annual_report": "annual_report",
            "quarterly_report": "quarterly_report",
            "tax_filing": "tax_filing"
        }

        for obl_type, template_key in obligation_templates.items():
            template = self.EVENT_TEMPLATES[template_key]

            # 计算到期日期（简化逻辑）
            if asset.expiry_date:
                due_date = asset.expiry_date
            else:
                due_date = datetime.now() + timedelta(days=365)

            event_id = self._generate_event_id(
                profile.profile_id,
                f"{asset.asset_id}_{obl_type}",
                obl_type
            )

            events.append(ComplianceCalendarEvent(
                event_id=event_id,
                enterprise_id=profile.profile_id,
                obligation_id=obligation_id,
                event_type=template["event_type"],
                title=template["title_template"].format(
                    category=asset.category,
                    tax_type=obligation_id
                ),
                description=template["description_template"].format(
                    category=asset.category
                ),
                due_date=due_date,
                reminder_days=template["reminder_days"],
                auto_executable=template["auto_executable"],
                confidence_threshold=template["confidence_threshold"]
            ))

        return events

    def _create_periodic_events(
        self,
        profile: EnterpriseProfile
    ) -> List[ComplianceCalendarEvent]:
        """创建周期性申报事件"""
        events = []
        now = datetime.now()

        # 工商年报 - 每年6月30日前
        events.append(ComplianceCalendarEvent(
            event_id=self._generate_event_id(profile.profile_id, "annual_report", "industry"),
            enterprise_id=profile.profile_id,
            obligation_id="annual_report_industry",
            event_type="annual_report",
            title="工商年度报告提交",
            description="市场主体年度报告提交截止日期（每年6月30日）",
            due_date=datetime(now.year, 6, 30),
            reminder_days=[30, 60, 90],
            auto_executable=True,
            confidence_threshold=0.9
        ))

        # 税务汇算清缴 - 每年5月31日前
        events.append(ComplianceCalendarEvent(
            event_id=self._generate_event_id(profile.profile_id, "annual_report", "tax"),
            enterprise_id=profile.profile_id,
            obligation_id="annual_report_tax",
            event_type="annual_report",
            title="税务年度汇算清缴",
            description="企业所得税年度汇算清缴截止日期（每年5月31日）",
            due_date=datetime(now.year, 5, 31),
            reminder_days=[30, 60, 90],
            auto_executable=True,
            confidence_threshold=0.95
        ))

        return events

    async def get_upcoming_events(
        self,
        profile_id: str,
        days: int = 30
    ) -> List[ComplianceCalendarEvent]:
        """获取即将到期的事件"""
        events = self._events.get(profile_id, [])
        now = datetime.now()
        cutoff = now + timedelta(days=days)

        upcoming = [
            e for e in events
            if e.status == "pending"
            and now <= e.due_date <= cutoff
        ]

        return sorted(upcoming, key=lambda x: x.due_date)

    async def get_overdue_events(
        self,
        profile_id: str
    ) -> List[ComplianceCalendarEvent]:
        """获取逾期事件"""
        events = self._events.get(profile_id, [])
        now = datetime.now()

        return [
            e for e in events
            if e.status == "pending" and e.due_date < now
        ]

    def _generate_event_id(self, profile_id: str, asset_id: str, event_type: str) -> str:
        """生成事件ID"""
        raw = f"{profile_id}:{asset_id}:{event_type}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def mark_completed(self, profile_id: str, event_id: str) -> bool:
        """标记事件已完成"""
        events = self._events.get(profile_id, [])
        for event in events:
            if event.event_id == event_id:
                event.status = "completed"
                event.completed_at = datetime.now()
                return True
        return False


# ==================== 资产图谱管理器 ====================

class AssetGraphManager:
    """
    资产图谱管理器

    管理企业资产网络，包括：
    - 生产设施
    - 环保设施
    - 安全设施
    - 知识产权（专利、商标）
    - 资质证照
    """

    ASSET_TYPES = {
        "facility": {"label": "生产设施", "color": "#1890ff"},
        "environmental": {"label": "环保设施", "color": "#52c41a"},
        "safety": {"label": "安全设施", "color": "#faad14"},
        "patent": {"label": "专利", "color": "#722ed1"},
        "trademark": {"label": "商标", "color": "#eb2f96"},
        "certificate": {"label": "资质证书", "color": "#13c2c2"},
        "license": {"label": "许可证", "color": "#f5222d"}
    }

    def __init__(self):
        self._graphs: Dict[str, Dict[str, AssetNode]] = {}  # profile_id -> {asset_id: AssetNode}
        self._relations: Dict[str, List[Dict]] = {}        # profile_id -> [{from, to, type}]

    async def build_asset_graph(
        self,
        profile: EnterpriseProfile,
        assets_data: List[Dict]
    ) -> Dict[str, AssetNode]:
        """
        从资产数据构建资产图谱

        Args:
            profile: 企业Profile
            assets_data: 资产数据列表

        Returns:
            资产图谱 {asset_id: AssetNode}
        """
        graph = {}

        for asset_data in assets_data:
            node = self._create_asset_node(profile.profile_id, asset_data)
            graph[node.asset_id] = node

        # 建立关联关系
        self._build_relations(profile.profile_id, graph)

        # 存储
        self._graphs[profile.profile_id] = graph

        return graph

    def _create_asset_node(
        self,
        profile_id: str,
        asset_data: Dict
    ) -> AssetNode:
        """创建资产节点"""
        asset_id = self._generate_asset_id(
            profile_id,
            asset_data.get("asset_type", ""),
            asset_data.get("name", "")
        )

        # 解析到期日期
        expiry_date = None
        if asset_data.get("expiry_date"):
            if isinstance(asset_data["expiry_date"], str):
                try:
                    expiry_date = datetime.fromisoformat(asset_data["expiry_date"])
                except:
                    expiry_date = None

        # 计算续期提醒
        renewal_notice_days = asset_data.get("renewal_notice_days", 90)

        return AssetNode(
            asset_id=asset_id,
            asset_type=asset_data.get("asset_type", "facility"),
            name=asset_data.get("name", ""),
            category=asset_data.get("category", ""),
            properties=asset_data.get("properties", {}),
            related_obligations=asset_data.get("related_obligations", []),
            status=asset_data.get("status", "active"),
            expiry_date=expiry_date,
            renewal_notice_days=renewal_notice_days
        )

    def _build_relations(
        self,
        profile_id: str,
        graph: Dict[str, AssetNode]
    ):
        """建立资产之间的关系"""
        relations = []

        # 1. 设施 -> 许可证 关系
        for asset_id, asset in graph.items():
            if asset.asset_type == "facility":
                # 查找关联的许可证
                for other_id, other in graph.items():
                    if other.asset_type == "license":
                        if asset.name in other.properties.get("related_facility", ""):
                            relations.append({
                                "from": asset_id,
                                "to": other_id,
                                "type": "requires_license"
                            })

            # 2. 许可证 -> 资质 关系
            if asset.asset_type == "license":
                for other_id, other in graph.items():
                    if other.category == asset.category:
                        if other.asset_type in ["certificate", "patent"]:
                            relations.append({
                                "from": asset_id,
                                "to": other_id,
                                "type": "supports"
                            })

        self._relations[profile_id] = relations

    async def get_expiring_assets(
        self,
        profile_id: str,
        days: int = 90
    ) -> List[AssetNode]:
        """获取即将到期的资产"""
        graph = self._graphs.get(profile_id, {})
        now = datetime.now()
        cutoff = now + timedelta(days=days)

        expiring = []
        for asset in graph.values():
            if asset.expiry_date and asset.status == "active":
                if now <= asset.expiry_date <= cutoff:
                    expiring.append(asset)

        return sorted(expiring, key=lambda x: x.expiry_date)

    async def get_asset_dependencies(
        self,
        profile_id: str,
        asset_id: str
    ) -> Dict[str, List[AssetNode]]:
        """
        获取资产的依赖关系

        Returns:
            {
                "requires": [...],  # 被依赖的资产
                "supports": [...]   # 支持的资产
            }
        """
        relations = self._relations.get(profile_id, [])
        graph = self._graphs.get(profile_id, {})

        requires = []
        supports = []

        for rel in relations:
            if rel["from"] == asset_id:
                target = graph.get(rel["to"])
                if target:
                    if rel["type"] == "requires_license":
                        requires.append(target)
                    elif rel["type"] == "supports":
                        supports.append(target)

        return {"requires": requires, "supports": supports}

    def _generate_asset_id(self, profile_id: str, asset_type: str, name: str) -> str:
        """生成资产ID"""
        raw = f"{profile_id}:{asset_type}:{name}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    def export_graph_json(self, profile_id: str) -> Dict:
        """导出图谱为JSON（用于可视化）"""
        graph = self._graphs.get(profile_id, {})
        relations = self._relations.get(profile_id, [])

        nodes = []
        for asset in graph.values():
            type_info = self.ASSET_TYPES.get(asset.asset_type, {})
            nodes.append({
                "id": asset.asset_id,
                "label": asset.name,
                "type": asset.asset_type,
                "typeLabel": type_info.get("label", asset.asset_type),
                "color": type_info.get("color", "#999"),
                "status": asset.status,
                "expiryDate": asset.expiry_date.isoformat() if asset.expiry_date else None
            })

        return {
            "nodes": nodes,
            "edges": relations
        }


# ==================== 企业Profile服务 ====================

class EnterpriseProfileService:
    """
    企业Profile微服务

    统一的企业数字档案管理服务，实现：
    1. 一企一档
    2. 合规日历自动化
    3. 资产图谱可视化
    4. 多源数据同步
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path
        self._profiles: Dict[str, EnterpriseProfile] = {}
        self._calendar_mgr = ComplianceCalendarManager()
        self._asset_mgr = AssetGraphManager()

    async def create_profile(
        self,
        company_name: str,
        credit_code: str,
        twin_id: str = None,
        basic_info: Dict = None
    ) -> EnterpriseProfile:
        """
        创建企业Profile

        Args:
            company_name: 公司名称
            credit_code: 统一社会信用代码
            twin_id: 关联的数字孪生ID
            basic_info: 基础信息

        Returns:
            EnterpriseProfile
        """
        profile_id = self._generate_profile_id(credit_code)

        profile = EnterpriseProfile(
            profile_id=profile_id,
            twin_id=twin_id or profile_id,
            credit_code=credit_code,
            company_name=company_name
        )

        # 初始化基础信息
        if basic_info:
            for key, value in basic_info.items():
                profile.basic_info[key] = DataField(
                    key=key,
                    value=value,
                    source=DataSource.MANUAL
                )

        self._profiles[profile_id] = profile

        return profile

    async def get_profile(self, profile_id: str) -> Optional[EnterpriseProfile]:
        """获取企业Profile"""
        return self._profiles.get(profile_id)

    async def get_profile_by_credit_code(self, credit_code: str) -> Optional[EnterpriseProfile]:
        """通过统一社会信用代码获取Profile"""
        for profile in self._profiles.values():
            if profile.credit_code == credit_code:
                return profile
        return None

    async def update_profile_data(
        self,
        profile_id: str,
        data_category: str,
        key: str,
        value: Any,
        source: DataSource = DataSource.MANUAL,
        confidence: DataConfidence = DataConfidence.HIGH
    ) -> bool:
        """
        更新Profile数据

        Args:
            profile_id: Profile ID
            data_category: 数据类别（basic_info/identity_info/tax_info/industry_info）
            key: 数据键
            value: 数据值
            source: 数据来源
            confidence: 置信度

        Returns:
            是否成功
        """
        profile = self._profiles.get(profile_id)
        if not profile:
            return False

        # 获取对应的数据字段字典
        data_dict = getattr(profile, data_category, None)
        if not data_dict:
            return False

        # 记录历史
        old_value = None
        if key in data_dict:
            old_value = data_dict[key].value

        # 创建新字段
        data_dict[key] = DataField(
            key=key,
            value=value,
            source=source,
            confidence=confidence,
            last_updated=datetime.now(),
            history=[
                {"old": old_value, "timestamp": datetime.now().isoformat()}
            ] if old_value else []
        )

        profile.updated_at = datetime.now()
        return True

    async def sync_from_twin(
        self,
        profile_id: str,
        twin_data: Dict
    ) -> bool:
        """
        从数字孪生同步数据

        Args:
            profile_id: Profile ID
            twin_data: 数字孪生数据

        Returns:
            是否成功
        """
        profile = self._profiles.get(profile_id)
        if not profile:
            return False

        profile.sync_status = "syncing"

        try:
            # 同步身份信息
            if "identity" in twin_data:
                for key, value in twin_data["identity"].items():
                    await self.update_profile_data(
                        profile_id,
                        "identity_info",
                        key,
                        value,
                        source=DataSource.GOV_SYNC,
                        confidence=DataConfidence.HIGH
                    )

            # 同步税务信息
            if "tax" in twin_data:
                for key, value in twin_data["tax"].items():
                    await self.update_profile_data(
                        profile_id,
                        "tax_info",
                        key,
                        value,
                        source=DataSource.GOV_SYNC,
                        confidence=DataConfidence.HIGH
                    )

            # 同步行业信息
            if "industry" in twin_data:
                for key, value in twin_data["industry"].items():
                    await self.update_profile_data(
                        profile_id,
                        "industry_info",
                        key,
                        value,
                        source=DataSource.GOV_SYNC,
                        confidence=DataConfidence.MEDIUM
                    )

            profile.last_full_sync = datetime.now()
            profile.sync_status = "idle"
            profile.data_quality_score = self._calculate_data_quality(profile)

            return True

        except Exception as e:
            profile.sync_status = "error"
            return False

    async def generate_compliance_calendar(
        self,
        profile_id: str
    ) -> List[ComplianceCalendarEvent]:
        """生成合规日历"""
        profile = self._profiles.get(profile_id)
        if not profile:
            return []

        # 从资产图谱生成事件
        events = await self._calendar_mgr.generate_calendar_events(
            profile,
            profile.asset_graph
        )

        profile.compliance_calendar = events
        return events

    async def get_compliance_dashboard(
        self,
        profile_id: str
    ) -> Dict:
        """
        获取合规仪表盘

        Returns:
            {
                "compliance_score": 85.5,
                "risk_level": "MEDIUM",
                "upcoming_events": [...],
                "overdue_events": [...],
                "expiring_assets": [...],
                "pending_tasks": [...]
            }
        """
        profile = self._profiles.get(profile_id)
        if not profile:
            return {}

        # 获取即将到期事件
        upcoming = await self._calendar_mgr.get_upcoming_events(profile_id, days=30)
        overdue = await self._calendar_mgr.get_overdue_events(profile_id)
        expiring_assets = await self._asset_mgr.get_expiring_assets(profile_id, days=90)

        # 计算合规评分
        base_score = profile.data_quality_score * 100

        # 逾期扣分
        overdue_penalty = len(overdue) * 5
        upcoming_penalty = len([e for e in upcoming if e.due_date < datetime.now() + timedelta(days=7)]) * 2

        compliance_score = max(0, base_score - overdue_penalty - upcoming_penalty)

        # 风险等级
        if overdue:
            risk_level = "HIGH"
        elif len(upcoming) > 5:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return {
            "compliance_score": round(compliance_score, 1),
            "risk_level": risk_level,
            "upcoming_events": [
                {
                    "event_id": e.event_id,
                    "title": e.title,
                    "due_date": e.due_date.isoformat(),
                    "auto_executable": e.auto_executable
                }
                for e in upcoming[:5]
            ],
            "overdue_events": [
                {
                    "event_id": e.event_id,
                    "title": e.title,
                    "due_date": e.due_date.isoformat(),
                    "days_overdue": (datetime.now() - e.due_date).days
                }
                for e in overdue
            ],
            "expiring_assets": [
                {
                    "asset_id": a.asset_id,
                    "name": a.name,
                    "type": a.asset_type,
                    "expiry_date": a.expiry_date.isoformat() if a.expiry_date else None,
                    "days_until_expiry": (a.expiry_date - datetime.now()).days if a.expiry_date else None
                }
                for a in expiring_assets[:5]
            ],
            "pending_tasks": len([e for e in upcoming if e.auto_executable])
        }

    async def add_government_account(
        self,
        profile_id: str,
        system_name: str,
        account_info: Dict
    ) -> bool:
        """
        添加政府系统账号

        Args:
            profile_id: Profile ID
            system_name: 系统名称（如"国家税务总局电子税务局"）
            account_info: 账号信息

        Returns:
            是否成功
        """
        profile = self._profiles.get(profile_id)
        if not profile:
            return False

        profile.gov_system_accounts[system_name] = {
            "account": account_info.get("account", ""),
            "encrypted_password": account_info.get("encrypted_password", ""),
            "login_url": account_info.get("login_url", ""),
            "added_at": datetime.now().isoformat(),
            "last_login": None,
            "status": "active"
        }

        profile.updated_at = datetime.now()
        return True

    def _generate_profile_id(self, credit_code: str) -> str:
        """生成Profile ID"""
        return f"EP:{credit_code}"

    def _calculate_data_quality(self, profile: EnterpriseProfile) -> float:
        """计算数据质量分数"""
        total_fields = (
            len(profile.basic_info) +
            len(profile.identity_info) +
            len(profile.tax_info) +
            len(profile.industry_info)
        )

        if total_fields == 0:
            return 0.5

        high_confidence = sum(
            1 for d in list(profile.basic_info.values()) +
                      list(profile.identity_info.values()) +
                      list(profile.tax_info.values()) +
                      list(profile.industry_info.values())
            if d.confidence == DataConfidence.HIGH
        )

        return high_confidence / total_fields


# ==================== 单例模式 ====================

_profile_service: Optional[EnterpriseProfileService] = None


def get_profile_service() -> EnterpriseProfileService:
    """获取企业Profile服务单例"""
    global _profile_service
    if _profile_service is None:
        _profile_service = EnterpriseProfileService()
    return _profile_service


async def create_enterprise_profile(
    company_name: str,
    credit_code: str,
    twin_id: str = None,
    basic_info: Dict = None
) -> EnterpriseProfile:
    """创建企业Profile的便捷函数"""
    service = get_profile_service()
    return await service.create_profile(company_name, credit_code, twin_id, basic_info)
