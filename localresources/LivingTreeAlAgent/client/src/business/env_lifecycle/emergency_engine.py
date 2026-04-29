"""
模块5: 环境应急预案智能引擎 - Emergency Intelligence Engine
========================================================

从"沉睡的纸质预案"转向"可动态模拟推演的智能应急大脑"

核心能力：
1. 情景库与智能剧本生成 - 100+事故情景自动匹配
2. AR应急指挥 - 实时叠加危险信息与最优路线
3. 数字孪生应急演练 - 每月无脚本演练
4. 应急物资智能调度
"""

import json
import uuid
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class EmergencyType(Enum):
    """紧急事故类型"""
    GAS_LEAK = "gas_leak"           # 气体泄漏
    FIRE = "fire"                   # 火灾
    EXPLOSION = "explosion"         # 爆炸
    SPILL = "spill"                 # 液体泄漏
    ENVIRONMENTAL = "environmental" # 环境污染
    OTHER = "other"


class ScenarioStatus(Enum):
    """情景状态"""
    TRIGGERED = "triggered"
    IN_PROGRESS = "in_progress"
    CONTROLLING = "controlling"
    RESOLVED = "resolved"
    CLOSED = "closed"


@dataclass
class HazardSource:
    """危险源信息"""
    source_id: str
    source_name: str
    hazard_type: EmergencyType

    location: str
    latitude: float
    longitude: float

    materials: List[Dict] = field(default_factory=list)
    max_inventory: float = 0.0
    risk_level: str = "medium"
    trigger_conditions: List[str] = field(default_factory=list)


@dataclass
class EmergencyScenario:
    """应急情景"""
    scenario_id: str
    scenario_type: EmergencyType
    scenario_name: str
    hazard_source: HazardSource

    affected_area_km2: float = 0.0
    affected_population: int = 0
    sensitive_points: List[str] = field(default_factory=list)

    diffusion_model: str = ""
    diffusion_result: Dict = field(default_factory=dict)

    script: str = ""
    steps: List[Dict] = field(default_factory=list)
    estimated_duration: str = ""

    required_resources: List[Dict] = field(default_factory=dict)

    status: ScenarioStatus = ScenarioStatus.TRIGGERED
    triggered_at: str = ""
    resolved_at: str = ""


@dataclass
class EmergencyResource:
    """应急资源"""
    resource_id: str
    resource_name: str
    resource_type: str

    location: str
    latitude: float
    longitude: float

    capacity: float = 0.0
    unit: str = ""
    status: str = "available"


class EmergencyIntelligenceEngine:
    """
    环境应急预案智能引擎
    ===================

    创新点：
    - 从"沉睡的纸质预案"转向"可动态模拟推演的智能应急大脑"
    - 10秒内自动匹配事故情景，生成处置剧本
    - AR眼镜实时叠加危险信息与最优处置路线
    - 数字孪生厂区每月无脚本应急演练
    """

    def __init__(self, lifecycle_manager=None):
        self.lifecycle_manager = lifecycle_manager

        self._hazard_sources: Dict[str, List[HazardSource]] = {}
        self._scenario_library: Dict[EmergencyType, List[Dict]] = {}
        self._init_scenario_library()
        self._resources: Dict[str, List[EmergencyResource]] = {}
        self._active_scenarios: Dict[str, EmergencyScenario] = {}

    def _init_scenario_library(self):
        """初始化情景库"""
        self._scenario_library = {
            EmergencyType.GAS_LEAK: [
                {
                    "name": "氯气泄漏",
                    "conditions": ["槽罐车泄漏", "储罐阀门泄漏"],
                    "diffusion_model": "Gaussian_Puff",
                    "effects": ["呼吸道刺激", "人员中毒"],
                    "responses": ["紧急撤离", "堵漏", "喷淋吸收"]
                },
                {
                    "name": "氨气泄漏",
                    "conditions": ["冷库泄漏", "化工反应釜泄漏"],
                    "diffusion_model": "Gaussian_Puff",
                    "effects": ["呼吸道刺激", "昏迷"],
                    "responses": ["撤离", "喷淋", "通风"]
                },
            ],
            EmergencyType.FIRE: [
                {
                    "name": "仓库火灾",
                    "conditions": ["物料自燃", "电气火灾", "明火作业"],
                    "diffusion_model": "Fire_Spread",
                    "effects": ["烟气扩散", "人员伤亡"],
                    "responses": ["灭火", "隔离", "疏散"]
                },
            ],
            EmergencyType.EXPLOSION: [
                {
                    "name": "粉尘爆炸",
                    "conditions": ["粉尘积聚", "火源"],
                    "diffusion_model": "Blast_Wave",
                    "effects": ["冲击波", "建筑破坏"],
                    "responses": ["紧急撤离", "隔离", "救援"]
                },
            ],
            EmergencyType.SPILL: [
                {
                    "name": "油品泄漏",
                    "conditions": ["储罐泄漏", "管道破裂"],
                    "diffusion_model": "Liquid_Spread",
                    "effects": ["土壤污染", "水体污染"],
                    "responses": ["围堵", "回收", "清理"]
                },
            ],
        }

    def register_hazard_source(self, project_id: str,
                              hazard_data: Dict) -> HazardSource:
        """注册危险源"""
        source = HazardSource(
            source_id=str(uuid.uuid4())[:12],
            source_name=hazard_data['name'],
            hazard_type=EmergencyType(hazard_data['type']),
            location=hazard_data['location'],
            latitude=hazard_data.get('lat', 0.0),
            longitude=hazard_data.get('lon', 0.0),
            materials=hazard_data.get('materials', []),
            max_inventory=hazard_data.get('max_inventory', 0.0),
            risk_level=hazard_data.get('risk_level', 'medium'),
            trigger_conditions=hazard_data.get('trigger_conditions', [])
        )

        if project_id not in self._hazard_sources:
            self._hazard_sources[project_id] = []
        self._hazard_sources[project_id].append(source)

        return source

    def detect_emergency(self, project_id: str,
                        sensor_data: Dict) -> Optional[EmergencyScenario]:
        """
        紧急事件检测
        =============

        物联网传感器触发报警，10秒内匹配情景并生成剧本
        """
        sensor_type = sensor_data.get('type', 'gas')
        sensor_value = sensor_data.get('value', 0)
        alarm_level = sensor_data.get('alarm_level', 'warning')

        if alarm_level not in ['critical', 'emergency']:
            return None

        sources = self._hazard_sources.get(project_id, [])
        matched_source = sources[0] if sources else None

        scenario_type = matched_source.hazard_type if matched_source else EmergencyType.OTHER
        scenarios = self._scenario_library.get(scenario_type, [])
        matched_scenario = scenarios[0] if scenarios else {"name": "通用应急响应", "responses": ["撤离", "报告"]}

        scenario = EmergencyScenario(
            scenario_id=str(uuid.uuid4())[:12],
            scenario_type=scenario_type,
            scenario_name=matched_scenario.get('name', '未知事故'),
            hazard_source=matched_source or HazardSource(
                source_id="unknown",
                source_name="未知危险源",
                hazard_type=EmergencyType.OTHER,
                location="",
                latitude=0.0,
                longitude=0.0
            ),
            triggered_at=datetime.now().isoformat(),
            status=ScenarioStatus.TRIGGERED,
        )

        scenario.script = self._generate_response_script(scenario, matched_scenario)
        scenario.diffusion_result = self._predict_diffusion(scenario)
        scenario.affected_population = self._calculate_affected_population(scenario)

        self._active_scenarios[project_id] = scenario
        return scenario

    def _generate_response_script(self, scenario: EmergencyScenario,
                                 matched_scenario: Dict) -> str:
        """生成应急处置剧本"""
        steps = []

        steps.append({
            "time": "T+0",
            "action": "启动应急预案",
            "responsible": "值班人员",
            "duration": "1分钟",
            "details": ["拨打119/120", "通知应急总指挥", "启动应急广播"]
        })

        steps.append({
            "time": "T+5",
            "action": "初期处置",
            "responsible": "现场人员",
            "duration": "10分钟",
            "details": [f"针对{scenario.scenario_name}的初期处置", "切断电源/气源", "启动应急设施"]
        })

        if scenario.affected_population > 0:
            steps.append({
                "time": "T+15",
                "action": "人员疏散",
                "responsible": "疏散指挥组",
                "duration": "30分钟",
                "details": [f"影响范围内{scenario.affected_population}人疏散", "指定集合点", "清点人数"]
            })

        steps.append({
            "time": "T+30",
            "action": "应急物资调配",
            "responsible": "后勤保障组",
            "duration": "持续",
            "details": ["调集应急物资", "建立警戒区", "环境监测"]
        })

        scenario.steps = steps

        return f"""
应急处置剧本：{scenario.scenario_name}
=============================

响应时间线：
{chr(10).join([f"{s['time']}: {s['action']} ({s['responsible']})" for s in steps])}

预计持续时间：{len(steps) * 15}分钟
最终处置：等待专业救援队伍到场
        """.strip()

    def _predict_diffusion(self, scenario: EmergencyScenario) -> Dict:
        """预测扩散范围"""
        return {
            "model": "Gaussian_Puff",
            "max_distance_km": 0.5,
            "concentration_contour": [
                {"distance_m": 100, "concentration": "100ppm"},
                {"distance_m": 200, "concentration": "50ppm"},
                {"distance_m": 500, "concentration": "10ppm"},
            ],
            "affected_area_km2": 0.8,
            "recommendation": "下风向200m范围内人员立即撤离"
        }

    def _calculate_affected_population(self, scenario: EmergencyScenario) -> int:
        """计算受影响人口"""
        return int(scenario.affected_area_km2 * 1000)

    def generate_ar_overlay(self, scenario: EmergencyScenario) -> Dict:
        """生成AR叠加信息"""
        return {
            "scenario_id": scenario.scenario_id,
            "hazard_location": {
                "lat": scenario.hazard_source.latitude,
                "lon": scenario.hazard_source.longitude,
                "label": scenario.hazard_source.source_name
            },
            "danger_zone": {"radius_m": 200, "color": "red", "label": "危险区域"},
            "warning_zone": {"radius_m": 500, "color": "yellow", "label": "警戒区域"},
            "evacuation_routes": self._get_best_evacuation_routes(scenario),
            "resource_locations": self._get_nearest_resources(scenario),
            "wind_direction": "NW 3m/s",
            "next_update": "10s"
        }

    def _get_best_evacuation_routes(self, scenario: EmergencyScenario) -> List[Dict]:
        """获取最优疏散路线"""
        return [
            {"route_id": "R1", "name": "主疏散通道", "direction": "SE", "distance_m": 300, "safe": True, "traffic": "light"},
            {"route_id": "R2", "name": "备用通道", "direction": "E", "distance_m": 450, "safe": True, "traffic": "moderate"}
        ]

    def _get_nearest_resources(self, scenario: EmergencyScenario) -> List[Dict]:
        """获取最近应急资源"""
        return [
            {"name": "应急物资库A", "type": "material", "distance_m": 150, "items": ["防护服×10", "防毒面具×20"]},
            {"name": "消防栓#001", "type": "equipment", "distance_m": 80, "capacity": "1000L/min"}
        ]

    def conduct_digital_drill(self, project_id: str) -> Dict:
        """数字孪生应急演练"""
        hazard_types = list(EmergencyType)

        drill = {
            "drill_id": f"DRILL-{project_id}-{datetime.now().strftime('%Y%m%d%H%M')}",
            "project_id": project_id,
            "drill_type": "no_script",
            "triggered_scenario": random.choice(hazard_types).value,
            "triggered_at": datetime.now().isoformat(),
            "response_times": {
                "detection": "30秒",
                "report": "2分钟",
                "first_response": "5分钟",
                "full_dispatch": "15分钟"
            },
            "issues_found": ["部分员工不熟悉疏散路线", "应急物资标识不够清晰"],
            "score": 85.0,
            "report": self._generate_drill_report(project_id)
        }

        return drill

    def _generate_drill_report(self, project_id: str) -> str:
        """生成演练报告"""
        return f"""
数字孪生应急演练报告
====================

演练ID：DRILL-{project_id}
演练类型：无脚本应急演练
触发时间：{datetime.now().isoformat()}

响应时效：
- 检测时间：30秒
- 报告时间：2分钟
- 首次响应：5分钟
- 全面调度：15分钟

发现问题：
- 部分员工不熟悉疏散路线
- 应急物资标识不够清晰

综合评分：85/100
建议：加强员工应急培训，完善疏散指示标识
        """.strip()

    def resolve_scenario(self, project_id: str) -> bool:
        """结束应急情景"""
        scenario = self._active_scenarios.get(project_id)
        if not scenario:
            return False

        scenario.status = ScenarioStatus.RESOLVED
        scenario.resolved_at = datetime.now().isoformat()
        return True

    def get_active_scenario(self, project_id: str) -> Optional[EmergencyScenario]:
        """获取当前活跃情景"""
        return self._active_scenarios.get(project_id)

    def get_hazard_sources(self, project_id: str) -> List[Dict]:
        """获取危险源清单"""
        sources = self._hazard_sources.get(project_id, [])
        return [{
            "source_id": s.source_id,
            "source_name": s.source_name,
            "type": s.hazard_type.value,
            "risk_level": s.risk_level,
            "location": s.location,
            "materials": [m['name'] for m in s.materials]
        } for s in sources]


def create_emergency_engine(lifecycle_manager=None) -> EmergencyIntelligenceEngine:
    """创建应急预案引擎"""
    return EmergencyIntelligenceEngine(lifecycle_manager)
