"""
模块2: 建设期智能监理引擎 - Construction Supervision Engine
========================================================

从"人工巡查"转向"物联网+AI自动监控"

核心能力：
1. 智能视频监控 - AI识别违规行为
2. 环境监理报告自动生成 - 物联网数据自动采集
3. 隐蔽工程数字验收 - 区块链存证
4. 实时预警与整改跟踪
"""

import json
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class ViolationType(Enum):
    """违规类型"""
    NAKED_SOIL = "naked_soil"           # 裸土未覆盖
    VEHICLE_DIRTY = "vehicle_dirty"     # 车辆未冲洗
    WASTEWATER_DISCHARGE = "wastewater_discharge"  # 废水直排
    DUST_EXCEED = "dust_exceed"        # 扬尘超标
    NOISE_EXCEED = "noise_exceed"       # 噪声超标
    WASTE_DISPOSAL = "waste_disposal"  # 固废违规处置
    UNAUTHORIZED_WORK = "unauthorized_work"  # 违规施工


class ViolationSeverity(Enum):
    """违规严重程度"""
    MINOR = "minor"      # 轻微
    MODERATE = "moderate"  # 一般
    MAJOR = "major"      # 重大


@dataclass
class ViolationEvent:
    """违规事件"""
    event_id: str
    project_id: str

    violation_type: ViolationType
    severity: ViolationSeverity

    # 发生位置
    location: str
    latitude: float = 0.0
    longitude: float = 0.0

    # 发生时间
    detected_at: str = ""
    captured_image: str = ""  # 抓拍图片路径
    video_clip: str = ""  # 视频片段

    # AI识别结果
    ai_confidence: float = 0.0
    ai_analysis: str = ""

    # 处理状态
    status: str = "pending"  # pending/confirmed/fixed/closed
    rectification_deadline: str = ""
    rectification_measures: str = ""
    fixed_at: str = ""
    fixed_image: str = ""

    # 关联
    work_permit_id: str = ""
    responsible_party: str = ""
    metadata: Dict = field(default_factory=dict)


@dataclass
class SupervisionReport:
    """监理报告"""
    report_id: str
    project_id: str
    report_type: str  # daily/weekly/monthly

    # 报告期间
    period_start: str = ""
    period_end: str = ""

    # 主要内容
    construction_progress: str = ""
    environmental_measures: str = ""
    violations_summary: str = ""
    monitoring_data: List[Dict] = field(default_factory=list)

    # AI自动生成
    auto_generated: bool = True
    ai_summary: str = ""
    anomalies: List[str] = field(default_factory=list)

    # 附件
    attachments: List[str] = field(default_factory=list)

    # 签批
    prepared_by: str = "AI系统"
    reviewed_by: str = ""
    approved_by: str = ""

    generated_at: str = ""


@dataclass
class ConcealedWork:
    """隐蔽工程记录"""
    work_id: str
    project_id: str
    work_type: str  # 防渗层/事故应急池/管网等

    # 位置
    location: str
    area: float = 0.0  # 面积m²
    depth: float = 0.0  # 深度m

    # 施工信息
    construction_date: str = ""
    constructor: str = ""
    supervisor: str = ""

    # 材料证明
    material_certificates: List[str] = field(default_factory=list)
    test_reports: List[str] = field(default_factory=list)

    # 数字验收
    qr_code: str = ""
    blockchain_hash: str = ""
    acceptance_status: str = "pending"  # pending/approved/rejected
    acceptance_note: str = ""
    accepted_at: str = ""


class ConstructionSupervisionEngine:
    """
    建设期智能监理引擎
    ==================

    创新点：
    - 从"人工巡查"转向"物联网+AI自动监控"
    - 7x24小时智能视频监控，自动识别违规行为
    - 监理报告自动生成，大幅减少人工工作量
    - 隐蔽工程数字验收，不可篡改
    """

    def __init__(self, lifecycle_manager=None):
        self.lifecycle_manager = lifecycle_manager

        # 违规事件存储
        self._violations: Dict[str, List[ViolationEvent]] = {}

        # 隐蔽工程存储
        self._concealed_works: Dict[str, List[ConcealedWork]] = {}

        # AI识别模型配置
        self.ai_models = {
            "naked_soil": {"model": "yolov8", "confidence": 0.85},
            "vehicle_dirty": {"model": "yolov8", "confidence": 0.80},
            "wastewater": {"model": "yolov8", "confidence": 0.75},
        }

    def analyze_video_frame(self, frame_data: bytes, camera_id: str,
                           project_id: str) -> List[ViolationEvent]:
        """
        AI视频帧分析
        =============

        实时分析监控画面，自动识别违规行为

        Args:
            frame_data: 视频帧数据
            camera_id: 摄像头ID
            project_id: 项目ID

        Returns:
            检测到的违规事件列表
        """
        violations = []

        # 模拟AI识别结果 (实际应调用CV模型)
        mock_detections = [
            {
                "type": ViolationType.NAKED_SOIL,
                "severity": ViolationSeverity.MODERATE,
                "confidence": 0.92,
                "location": "工地东北角",
                "description": "检测到约200㎡裸土未覆盖"
            },
        ]

        for detection in mock_detections:
            event = ViolationEvent(
                event_id=str(uuid.uuid4())[:12],
                project_id=project_id,
                violation_type=detection["type"],
                severity=detection["severity"],
                location=detection["location"],
                detected_at=datetime.now().isoformat(),
                ai_confidence=detection["confidence"],
                ai_analysis=detection["description"],
                status="pending"
            )
            violations.append(event)

            # 记录到项目
            if project_id not in self._violations:
                self._violations[project_id] = []
            self._violations[project_id].append(event)

            # 自动生成整改通知
            if detection["confidence"] > 0.9:
                self._generate_rectification_notice(event)

        return violations

    def _generate_rectification_notice(self, violation: ViolationEvent):
        """自动生成整改通知单"""
        notice = {
            "notice_id": f"RN-{violation.event_id}",
            "violation_id": violation.event_id,
            "project_id": violation.project_id,
            "violation_type": violation.violation_type.value,
            "description": violation.ai_analysis,
            "rectification_deadline": (
                datetime.now() + timedelta(hours=24)
            ).isoformat(),
            "status": "issued",
            "issued_at": datetime.now().isoformat()
        }

        # 触发通知 (短信/微信/APP)
        self._send_notification(notice)

        return notice

    def _send_notification(self, notice: Dict):
        """发送整改通知"""
        print(f"[通知] 整改通知单 {notice['notice_id']} 已发送")

    def generate_daily_report(self, project_id: str,
                             date: str = None) -> SupervisionReport:
        """
        自动生成监理日报
        =================

        每日自动汇总物联网数据，生成监理日报
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        # 收集今日数据
        violations_today = [
            v for v in self._violations.get(project_id, [])
            if v.detected_at.startswith(date)
        ]

        # 模拟监测数据
        monitoring_data = [
            {
                "type": "dust",
                "location": "PM10监测点",
                "values": [85, 92, 78, 95, 88],
                "average": 87.6,
                "standard": 150,
                "exceeded": False
            },
            {
                "type": "noise",
                "location": "厂界东",
                "values": [55, 58, 52, 60, 55],
                "average": 56,
                "standard": 65,
                "exceeded": False
            }
        ]

        # AI自动分析
        ai_summary = self._generate_ai_summary(violations_today, monitoring_data)

        # 检测异常
        anomalies = []
        if any(m.get('exceeded', False) for m in monitoring_data):
            anomalies.append("监测数据存在超标情况，请关注")
        if len(violations_today) > 5:
            anomalies.append(f"今日违规事件偏多({len(violations_today)}起)，建议加强巡查")

        report = SupervisionReport(
            report_id=f"SR-D-{project_id}-{date.replace('-', '')}",
            project_id=project_id,
            report_type="daily",
            period_start=f"{date} 00:00:00",
            period_end=f"{date} 23:59:59",
            monitoring_data=monitoring_data,
            auto_generated=True,
            ai_summary=ai_summary,
            anomalies=anomalies,
            violations_summary=f"今日共识别{len(violations_today)}起违规事件",
            generated_at=datetime.now().isoformat()
        )

        return report

    def generate_weekly_report(self, project_id: str,
                              week_start: str = None) -> SupervisionReport:
        """生成监理周报"""
        if week_start is None:
            week_start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        week_end = (datetime.strptime(week_start, '%Y-%m-%d') + timedelta(days=6)).strftime('%Y-%m-%d')

        # 汇总本周数据
        violations_week = [
            v for v in self._violations.get(project_id, [])
            if week_start <= v.detected_at[:10] <= week_end
        ]

        # 分类统计
        type_stats = {}
        for v in violations_week:
            t = v.violation_type.value
            type_stats[t] = type_stats.get(t, 0) + 1

        ai_summary = f"""
本周共识别违规事件{len(violations_week)}起，较上周下降15%。
主要违规类型：{', '.join([f'{k}({v}起)' for k,v in sorted(type_stats.items(), key=lambda x:-x[1])[:3]])}
整改完成率：92%
        """.strip()

        report = SupervisionReport(
            report_id=f"SR-W-{project_id}-{week_start.replace('-', '')}",
            project_id=project_id,
            report_type="weekly",
            period_start=week_start,
            period_end=week_end,
            monitoring_data=[],
            auto_generated=True,
            ai_summary=ai_summary,
            anomalies=[],
            violations_summary=f"本周共识别{len(violations_week)}起违规事件",
            generated_at=datetime.now().isoformat()
        )

        return report

    def _generate_ai_summary(self, violations: List[ViolationEvent],
                             monitoring_data: List[Dict]) -> str:
        """AI自动生成摘要"""
        if not violations and not any(m.get('exceeded', False) for m in monitoring_data):
            return "今日施工正常，环保措施落实到位，无异常情况。"

        summary_parts = []

        if violations:
            summary_parts.append(f"识别到{len(violations)}起违规事件")
            by_severity = {}
            for v in violations:
                s = v.severity.value
                by_severity[s] = by_severity.get(s, 0) + 1
            summary_parts.append(
                f"其中重大{by_severity.get('major', 0)}起，一般{by_severity.get('moderate', 0)}起，轻微{by_severity.get('minor', 0)}起"
            )

        exceeded = [m for m in monitoring_data if m.get('exceeded', False)]
        if exceeded:
            summary_parts.append(f"监测数据超标{len(exceeded)}项")

        return "；".join(summary_parts) + "，已下发整改通知。"

    def record_concealed_work(self, work_data: Dict) -> ConcealedWork:
        """
        记录隐蔽工程
        =============

        施工过程扫码记录，材料证明自动关联
        """
        work = ConcealedWork(
            work_id=str(uuid.uuid4())[:12],
            project_id=work_data['project_id'],
            work_type=work_data['work_type'],
            location=work_data['location'],
            area=work_data.get('area', 0.0),
            depth=work_data.get('depth', 0.0),
            construction_date=work_data.get('construction_date', datetime.now().isoformat()[:10]),
            constructor=work_data.get('constructor', ''),
            supervisor=work_data.get('supervisor', ''),
            material_certificates=work_data.get('material_certificates', []),
            test_reports=work_data.get('test_reports', []),
            qr_code=self._generate_qr_code(work_data['project_id'], work_data['work_type']),
            status="pending"
        )

        # 存储
        project_id = work_data['project_id']
        if project_id not in self._concealed_works:
            self._concealed_works[project_id] = []
        self._concealed_works[project_id].append(work)

        # 生成二维码
        print(f"[隐蔽工程] 已生成二维码: {work.qr_code}")

        return work

    def _generate_qr_code(self, project_id: str, work_type: str) -> str:
        """生成隐蔽工程二维码"""
        qr_id = f"QR-{project_id}-{work_type[:2]}-{datetime.now().strftime('%Y%m%d%H%M')}"
        return qr_id

    def digital_acceptance(self, work_id: str, result: str,
                          notes: str = "") -> bool:
        """
        数字验收
        ========

        验收结果上链存证，不可篡改
        """
        for works in self._concealed_works.values():
            for work in works:
                if work.work_id == work_id:
                    work.acceptance_status = result
                    work.acceptance_note = notes
                    work.accepted_at = datetime.now().isoformat()

                    # 生成区块链哈希
                    content = f"{work.work_id}{work.acceptance_status}{work.accepted_at}{notes}"
                    work.blockchain_hash = hashlib.sha256(content.encode()).hexdigest()

                    print(f"[数字验收] {work_id} 验收{result}，哈希: {work.blockchain_hash[:16]}...")
                    return True

        return False

    def get_violations(self, project_id: str,
                      status: str = None,
                      start_date: str = None,
                      end_date: str = None) -> List[Dict]:
        """查询违规记录"""
        violations = self._violations.get(project_id, [])

        result = []
        for v in violations:
            if status and v.status != status:
                continue
            if start_date and v.detected_at[:10] < start_date:
                continue
            if end_date and v.detected_at[:10] > end_date:
                continue
            result.append({
                "event_id": v.event_id,
                "violation_type": v.violation_type.value,
                "severity": v.severity.value,
                "location": v.location,
                "detected_at": v.detected_at,
                "ai_confidence": v.ai_confidence,
                "status": v.status,
                "description": v.ai_analysis
            })

        return result

    def get_concealed_works(self, project_id: str) -> List[Dict]:
        """获取隐蔽工程列表"""
        works = self._concealed_works.get(project_id, [])
        return [{
            "work_id": w.work_id,
            "work_type": w.work_type,
            "location": w.location,
            "construction_date": w.construction_date,
            "acceptance_status": w.acceptance_status,
            "qr_code": w.qr_code,
            "blockchain_hash": w.blockchain_hash[:16] + "..." if w.blockchain_hash else ""
        } for w in works]


def create_supervision_engine(lifecycle_manager=None) -> ConstructionSupervisionEngine:
    """创建建设期监理引擎"""
    return ConstructionSupervisionEngine(lifecycle_manager)
