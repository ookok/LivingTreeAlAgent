"""
模块3: 竣工环保验收引擎 - Acceptance Engine
==========================================

从"预定式检查"转向"无感式智能验收"

核心能力：
1. 验收条件智能符合性判断 - AI自动比对56项要求
2. 验收监测方案自动生成 - 智能布点
3. 大数据辅助验收决策 - 识别作弊嫌疑
4. 重大变更自动识别
"""

import json
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class ComplianceStatus(Enum):
    """符合性状态"""
    COMPLIANT = "compliant"           # 符合
    NON_COMPLIANT = "non_compliant"   # 不符合
    PARTIAL = "partial"              # 部分符合
    PENDING = "pending"              # 待核实
    NA = "not_applicable"            # 不适用


class ChangeType(Enum):
    """变更类型"""
    MAJOR = "major"      # 重大变更（需重新报批）
    MINOR = "minor"      # 一般变更（备案）
    NO_CHANGE = "no_change"  # 无变更


@dataclass
class EIALedgerItem:
    """环评批复要求条目"""
    item_id: str
    description: str
    requirement: str
    verification_method: str  # how to verify
    standard: str  # applicable standard

    # 比对结果
    status: ComplianceStatus = ComplianceStatus.PENDING
    actual_value: str = ""
    is_exceeded: bool = False
    notes: str = ""


@dataclass
class MonitoringPoint:
    """验收监测点位"""
    point_id: str
    point_name: str
    location: str
    latitude: float
    longitude: float

    # 监测因子
    pollutants: List[str]

    # 监测频次
    frequency: str  # "daily_24h" / "4_times_per_day" / "once"
    duration_days: int = 1

    # 状态
    status: str = "planned"  # planned/measured/verified


@dataclass
class AcceptanceReport:
    """竣工验收报告"""
    report_id: str
    project_id: str

    # 基本信息
    acceptance_date: str = ""
    acceptance_type: str = "self_check"  # self_check/third_party/inspection

    # 符合性分析
    eia_compliance: List[EIALedgerItem] = field(default_factory=list)
    compliance_rate: float = 0.0
    major_issues: List[str] = field(default_factory=list)

    # 监测方案
    monitoring_points: List[MonitoringPoint] = field(default_factory=list)
    monitoring_report_ref: str = ""

    # 变更分析
    change_analysis: ChangeType = ChangeType.NO_CHANGE
    change_details: str = ""

    # 大数据核查
    data_verification: Dict = field(default_factory=dict)

    # 结论
    conclusion: str = ""
    approved: bool = False
    approved_by: str = ""

    # 生成信息
    auto_generated: bool = True
    confidence: float = 0.0
    generated_at: str = ""


class AcceptanceEngine:
    """
    竣工环保验收引擎
    ===============

    创新点：
    - 从"预定式检查"转向"无感式智能验收"
    - AI自动比对环评批复要求
    - 验收监测方案智能生成
    - 大数据辅助识别"人为制造好天气"作弊
    """

    def __init__(self, lifecycle_manager=None):
        self.lifecycle_manager = lifecycle_manager

        # 存储
        self._acceptance_reports: Dict[str, AcceptanceReport] = {}

    def load_eia_requirements(self, project_id: str,
                              eia_archive: Dict) -> List[EIALedgerItem]:
        """
        加载环评批复要求
        ================

        模拟：从环评档案中提取56项要求
        """
        # 模拟56项要求 (实际从eia_archive提取)
        mock_requirements = [
            {"description": "废气排气筒高度", "requirement": "≥15m", "verification": "现场测量", "standard": "GB16297"},
            {"description": "废水排放标准", "requirement": "GB8978一级", "verification": "水质监测", "standard": "GB8978"},
            {"description": "噪声厂界标准", "requirement": "昼间65dB夜间55dB", "verification": "噪声监测", "standard": "GB12348"},
            {"description": "固废贮存场所", "requirement": "防渗硬化+雨棚", "verification": "现场检查", "standard": "GB18599"},
            {"description": "事故应急池容积", "requirement": "≥100m³", "verification": "容积核算", "standard": "环评批复"},
            {"description": "卫生防护距离", "requirement": "100m", "verification": "距离测量", "standard": "环评批复"},
            {"description": "绿化率", "requirement": "≥20%", "verification": "绿化面积核算", "standard": "总体规划"},
            {"description": "排污口规范化", "requirement": "规范化建设", "verification": "现场检查", "standard": "环保部令"},
            # ... 模拟更多项，实际应为56项
        ]

        items = []
        for i, req in enumerate(mock_requirements):
            item = EIALedgerItem(
                item_id=f"REQ-{project_id}-{i+1:02d}",
                description=req["description"],
                requirement=req["requirement"],
                verification_method=req["verification"],
                standard=req["standard"],
                status=ComplianceStatus.PENDING
            )
            items.append(item)

        return items

    def check_compliance(self, project_id: str,
                        requirements: List[EIALedgerItem],
                        actual_data: Dict) -> List[EIALedgerItem]:
        """
        智能符合性检查
        ==============

        AI自动比对每项要求与实际情况
        """
        results = []

        for req in requirements:
            item = req
            actual = actual_data.get(req.description, {})

            if not actual:
                item.status = ComplianceStatus.PENDING
            else:
                item.actual_value = str(actual.get('value', ''))

                # 自动判断
                if req.description == "废气排气筒高度":
                    value = actual.get('value', 0)
                    if value >= 15:
                        item.status = ComplianceStatus.COMPLIANT
                    else:
                        item.status = ComplianceStatus.NON_COMPLIANT
                        item.is_exceeded = True
                        item.notes = f"实测高度{value}m，不满足≥15m要求"

                elif req.description == "废水排放标准":
                    # 水质是否达标
                    if actual.get('compliant', True):
                        item.status = ComplianceStatus.COMPLIANT
                    else:
                        item.status = ComplianceStatus.NON_COMPLIANT
                        item.is_exceeded = True

                elif req.description == "噪声厂界标准":
                    day_value = actual.get('day', 0)
                    night_value = actual.get('night', 0)
                    if day_value <= 65 and night_value <= 55:
                        item.status = ComplianceStatus.COMPLIANT
                    else:
                        item.status = ComplianceStatus.NON_COMPLIANT
                        item.is_exceeded = True

                # ... 其他项的判断逻辑

            results.append(item)

        return results

    def analyze_major_change(self, eia_archive: Dict,
                            actual_construction: Dict) -> ChangeType:
        """
        重大变更分析
        ============

        自动识别是否存在重大变更，判断是否需要重新报批

        重大变更标准（根据环保部相关文件）：
        - 产能变化 > 30%
        - 地址变化
        - 生产工艺重大调整
        - 污染防治措施重大变化
        """
        changes = []

        # 产能变化
        eia_capacity = eia_archive.get('capacity', 0)
        actual_capacity = actual_construction.get('capacity', 0)
        if eia_capacity > 0:
            change_ratio = abs(actual_capacity - eia_capacity) / eia_capacity
            if change_ratio > 0.3:
                changes.append(f"产能变化{change_ratio*100:.1f}%，超过30%阈值")

        # 生产工艺
        eia_process = set(eia_archive.get('process', []))
        actual_process = set(actual_construction.get('process', []))
        new_process = actual_process - eia_process
        removed_process = eia_process - actual_process
        if new_process or removed_process:
            changes.append(f"工艺变化: 新增{new_process}，减少{removed_process}")

        # 污染治理措施
        eia_treatment = set(eia_archive.get('treatment', []))
        actual_treatment = set(actual_construction.get('treatment', []))
        if eia_treatment != actual_treatment:
            changes.append(f"治理措施变化")

        # 判断变更级别
        if len(changes) >= 2:
            return ChangeType.MAJOR
        elif len(changes) == 1:
            return ChangeType.MINOR
        else:
            return ChangeType.NO_CHANGE

    def generate_monitoring_plan(self, project_data: Dict,
                                process_nodes: List[Dict]) -> List[MonitoringPoint]:
        """
        验收监测方案自动生成
        ====================

        基于工艺图谱和产污节点，智能布设监测点位
        """
        points = []

        # 废气有组织排放点
        for i, stack in enumerate(project_data.get('stacks', [])):
            point = MonitoringPoint(
                point_id=f"MP-A-{i+1:02d}",
                point_name=f"废气排气筒{i+1}（{stack.get('type', '工艺废气')}）",
                location=stack.get('location', ''),
                latitude=stack.get('lat', 0.0),
                longitude=stack.get('lon', 0.0),
                pollutants=stack.get('pollutants', ['SO2', 'NOx', '颗粒物', 'VOCs']),
                frequency="4_times_per_day",
                duration_days=2
            )
            points.append(point)

        # 废气无组织排放点
        boundary_points = [
            {"name": "厂界东", "direction": "E"},
            {"name": "厂界南", "direction": "S"},
            {"name": "厂界西", "direction": "W"},
            {"name": "厂界北", "direction": "N"},
        ]
        for i, bp in enumerate(boundary_points):
            point = MonitoringPoint(
                point_id=f"MP-AF-{i+1:02d}",
                point_name=f"无组织监测点{bp['name']}",
                location=f"厂界{bp['name']}",
                latitude=0.0,
                longitude=0.0,
                pollutants=['颗粒物', 'VOCs'],
                frequency="daily_24h",
                duration_days=2
            )
            points.append(point)

        # 废水排放口
        for i, outlet in enumerate(project_data.get('outlets', [])):
            point = MonitoringPoint(
                point_id=f"MP-W-{i+1:02d}",
                point_name=f"废水排放口{i+1}",
                location=outlet.get('location', ''),
                latitude=outlet.get('lat', 0.0),
                longitude=outlet.get('lon', 0.0),
                pollutants=['pH', 'COD', 'BOD', 'NH3-N', 'TP', '石油类'],
                frequency="4_times_per_day",
                duration_days=2
            )
            points.append(point)

        # 噪声
        noise_points = [
            {"name": "厂界东噪声", "location": "厂界东"},
            {"name": "厂界南噪声", "location": "厂界南"},
            {"name": "厂界西噪声", "location": "厂界西"},
            {"name": "厂界北噪声", "location": "厂界北"},
        ]
        for i, np in enumerate(noise_points):
            point = MonitoringPoint(
                point_id=f"MP-N-{i+1:02d}",
                point_name=np['name'],
                location=np['location'],
                latitude=0.0,
                longitude=0.0,
                pollutants=['Leq(A)'],
                frequency="once",
                duration_days=1
            )
            points.append(point)

        return points

    def verify_data_integrity(self, project_id: str,
                            monitoring_data: Dict,
                            reference_stations: List[str]) -> Dict:
        """
        大数据辅助验收决策
        ==================

        对比项目监测数据与周边国控/省控站点同期数据
        识别是否存在"监测期间人为制造好天气"的作弊嫌疑
        """
        verification = {
            "project_id": project_id,
            "verification_stations": reference_stations,
            "anomalies": [],
            "risk_level": "low",  # low/medium/high
            "details": {}
        }

        project_aqi = monitoring_data.get('aqi', 50)
        project_pm25 = monitoring_data.get('pm25', 35)

        # 模拟对比数据
        # 实际应调用环境监测数据API
        reference_data = {
            "regional_avg_pm25": 45,  # 区域平均PM2.5
            "regional_avg_aqi": 65,
        }

        # 计算偏差
        pm25_deviation = abs(project_pm25 - reference_data['regional_avg_pm25']) / reference_data['regional_avg_pm25']
        aqi_deviation = abs(project_aqi - reference_data['regional_avg_aqi']) / reference_data['regional_avg_aqi']

        verification['details'] = {
            "project_pm25": project_pm25,
            "regional_avg_pm25": reference_data['regional_avg_pm25'],
            "pm25_deviation_pct": f"{pm25_deviation*100:.1f}%",
            "project_aqi": project_aqi,
            "regional_avg_aqi": reference_data['regional_avg_aqi'],
            "aqi_deviation_pct": f"{aqi_deviation*100:.1f}%",
        }

        # 异常检测
        if pm25_deviation > 0.5:  # 项目数据比区域平均值好50%以上
            verification['anomalies'].append(
                f"PM2.5数据异常偏低（比区域平均低{pm25_deviation*100:.0f}%），建议核实监测条件"
            )
            verification['risk_level'] = 'high'
        elif pm25_deviation > 0.3:
            verification['anomalies'].append(
                f"PM2.5数据略偏低（比区域平均低{pm25_deviation*100:.0f}%），建议关注"
            )
            if verification['risk_level'] != 'high':
                verification['risk_level'] = 'medium'

        # 检查风速条件
        wind_speed = monitoring_data.get('wind_speed', 2.0)
        if wind_speed < 1.5:
            verification['anomalies'].append(
                f"监测期间风速偏低（{wind_speed}m/s），扩散条件不利，数据需核实"
            )
            verification['risk_level'] = 'high'

        return verification

    def generate_acceptance_report(self, project_id: str,
                                  requirements: List[EIALedgerItem],
                                  monitoring_plan: List[MonitoringPoint],
                                  compliance_results: List[EIALedgerItem],
                                  data_verification: Dict) -> AcceptanceReport:
        """
        生成竣工验收报告
        ================

        L2级别：AI生成 + 专家审核
        """
        # 计算符合率
        total = len(compliance_results)
        compliant = sum(1 for r in compliance_results if r.status == ComplianceStatus.COMPLIANT)
        compliance_rate = compliant / total * 100 if total > 0 else 0

        # 重大问题
        major_issues = [r.description for r in compliance_results if r.is_exceeded]

        # 结论
        if compliance_rate >= 95 and not major_issues:
            conclusion = "同意通过竣工环保验收"
            approved = True
        elif compliance_rate >= 85:
            conclusion = "基本符合验收条件，整改后可验收"
            approved = False
        else:
            conclusion = "不符合验收条件，需整改后重新验收"
            approved = False

        report = AcceptanceReport(
            report_id=f"AR-{project_id}-{datetime.now().strftime('%Y%m%d')}",
            project_id=project_id,
            acceptance_date=datetime.now().isoformat(),
            eia_compliance=compliance_results,
            compliance_rate=compliance_rate,
            major_issues=major_issues,
            monitoring_points=monitoring_plan,
            data_verification=data_verification,
            conclusion=conclusion,
            approved=approved,
            auto_generated=True,
            confidence=0.90,
            generated_at=datetime.now().isoformat()
        )

        self._acceptance_reports[project_id] = report
        return report

    def get_acceptance_report(self, project_id: str) -> Optional[AcceptanceReport]:
        """获取验收报告"""
        return self._acceptance_reports.get(project_id)

    def get_compliance_summary(self, project_id: str) -> Dict:
        """获取符合性汇总"""
        report = self._acceptance_reports.get(project_id)
        if not report:
            return {}

        return {
            "project_id": project_id,
            "compliance_rate": f"{report.compliance_rate:.1f}%",
            "total_requirements": len(report.eia_compliance),
            "compliant": sum(1 for r in report.eia_compliance if r.status == ComplianceStatus.COMPLIANT),
            "non_compliant": sum(1 for r in report.eia_compliance if r.status == ComplianceStatus.NON_COMPLIANT),
            "pending": sum(1 for r in report.eia_compliance if r.status == ComplianceStatus.PENDING),
            "major_issues": report.major_issues,
            "conclusion": report.conclusion,
            "approved": report.approved
        }


def create_acceptance_engine(lifecycle_manager=None) -> AcceptanceEngine:
    """创建竣工验收引擎"""
    return AcceptanceEngine(lifecycle_manager)
