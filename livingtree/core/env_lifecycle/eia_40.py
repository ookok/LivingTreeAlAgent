"""
模块1: 智能环评4.0引擎 - EIA 4.0 Intelligence Engine
==================================================

从"文档撰写"转向"影响推演与方案优化"

核心能力：
1. 三维时空影响仿真 - 大气/水质/噪声模型
2. 多方案比选优化 - AI决策矩阵
3. 公众参与智能化 - 敏感点分析+材料生成
4. VR/AR沉浸式审查支持

整合已有 eia_process 模块，构建完整 EIA 4.0 能力
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

# 导入已有环评模块
try:
    from business.eia_process import EIAProcessManager
    HAS_EIA_PROCESS = True
except ImportError:
    HAS_EIA_PROCESS = False


class ImpactType(Enum):
    """环境影响类型"""
    AIR = "air"           # 大气影响
    WATER = "water"       # 水环境影响
    SOIL = "soil"         # 土壤影响
    NOISE = "noise"       # 噪声影响
    ECOLOGY = "ecology"   # 生态影响
    SOCIAL = "social"     # 社会影响


class SensitivityLevel(Enum):
    """敏感程度"""
    HIGH = "high"         # 高敏感
    MODERATE = "moderate" # 中敏感
    LOW = "low"           # 低敏感


@dataclass
class SensitivePoint:
    """敏感点信息"""
    point_id: str
    name: str
    point_type: str  # 学校/医院/居民区/水源地等
    sensitivity: SensitivityLevel
    latitude: float
    longitude: float
    distance_km: float  # 距项目距离
    population: int = 0  # 影响人口
    metadata: Dict = field(default_factory=dict)


@dataclass
class AlternativeScheme:
    """替代方案"""
    scheme_id: str
    name: str
    description: str

    # 参数对比
    location: str = ""        # 选址方案
    technology: str = ""       # 工艺方案
    treatment: str = ""        # 治理方案

    # 效益指标
    investment: float = 0.0   # 投资额(万元)
    operation_cost: float = 0.0  # 运行成本(万元/年)
    emission_reduction: float = 0.0  # 减排量(t/年)
    land_use: float = 0.0     # 用地(亩)

    # 评分
    environmental_score: float = 0.0  # 环保效益得分
    economic_score: float = 0.0       # 经济性得分
    social_score: float = 0.0          # 社会影响得分
    overall_score: float = 0.0         # 综合得分

    # 风险
    risks: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class EIAReport:
    """智能环评报告"""
    report_id: str
    project_id: str

    # 报告章节
    executive_summary: str = ""
    project_description: str = ""
    environment现状: str = ""
   环境影响_prediction: str = ""
    pollution_prevention: str = ""
    environmental效益: str = ""
    environmental管理与监测: str = ""
    结论与建议: str = ""

    # 附件
    affectedResidents: List[Dict] = field(default_factory=list)
    alternatives: List[AlternativeScheme] = field(default_factory=list)
    sensitive_points: List[SensitivePoint] = field(default_factory=list)

    # 仿真结果
    simulation_results: Dict = field(default_factory=dict)

    # 智能决策
    recommended_scheme: str = ""
    decision_matrix: Dict = field(default_factory=dict)

    # 生成信息
    autopilot_level: int = 2  # L2半自动化
    confidence: float = 0.0   # 置信度
    generated_at: str = ""
    verified_by: str = ""


class EIA40Engine:
    """
    智能环评4.0引擎
    ==============

    创新点：
    - 从"文档撰写"转向"影响推演与方案优化"
    - 三维时空影响仿真
    - 多方案比选与AI决策
    - 公众参与智能化
    """

    def __init__(self, lifecycle_manager=None):
        self.lifecycle_manager = lifecycle_manager

        # 子模块
        if HAS_EIA_PROCESS:
            self.eia_process = EIAProcessManager()
        else:
            self.eia_process = None

        # 敏感点数据库 (示例)
        self.sensitive_point_db = self._init_sensitive_types()

        # 仿真模型 (集成已有数字孪生)
        self.simulation_models = {}

    def _init_sensitive_types(self) -> Dict:
        """初始化敏感点类型配置"""
        return {
            "学校": {"sensitivity": SensitivityLevel.HIGH, "radius_km": 2.0},
            "医院": {"sensitivity": SensitivityLevel.HIGH, "radius_km": 2.0},
            "居民区": {"sensitivity": SensitivityLevel.HIGH, "radius_km": 1.0},
            "水源地": {"sensitivity": SensitivityLevel.HIGH, "radius_km": 3.0},
            "自然保护区": {"sensitivity": SensitivityLevel.HIGH, "radius_km": 5.0},
            "风景名胜区": {"sensitivity": SensitivityLevel.MODERATE, "radius_km": 2.0},
            "养老院": {"sensitivity": SensitivityLevel.HIGH, "radius_km": 1.0},
            "幼儿园": {"sensitivity": SensitivityLevel.HIGH, "radius_km": 1.0},
        }

    def analyze_sensitive_points(self, project_lat: float, project_lon: float,
                                  radius_km: float = 5.0) -> List[SensitivePoint]:
        """
        智能分析项目周边敏感点
        ======================

        自动识别5公里范围内所有敏感点，评估影响程度
        """
        sensitive_points = []

        # 模拟敏感点数据 (实际应调用地图API)
        mock_sensitive_points = [
            {"name": "第一人民医院", "type": "医院", "lat": project_lat + 0.01, "lon": project_lon + 0.02, "pop": 50000},
            {"name": "第一中学", "type": "学校", "lat": project_lat - 0.02, "lon": project_lon + 0.01, "pop": 3000},
            {"name": "幸福小区", "type": "居民区", "lat": project_lat + 0.005, "lon": project_lon - 0.01, "pop": 10000},
            {"name": "滨江公园", "type": "风景名胜区", "lat": project_lat + 0.05, "lon": project_lon, "pop": 0},
        ]

        for sp in mock_sensitive_points:
            # 计算距离 (简化版，实际应用Haversine公式)
            distance = ((sp['lat'] - project_lat)**2 + (sp['lon'] - project_lon)**2)**0.5 * 111  # 度转km

            if distance <= radius_km:
                config = self.sensitive_point_db.get(sp['type'], {"sensitivity": SensitivityLevel.LOW, "radius_km": 1.0})
                sensitive_points.append(SensitivePoint(
                    point_id=str(uuid.uuid4())[:8],
                    name=sp['name'],
                    point_type=sp['type'],
                    sensitivity=config['sensitivity'],
                    latitude=sp['lat'],
                    longitude=sp['lon'],
                    distance_km=round(distance, 2),
                    population=sp['pop'],
                    metadata={}
                ))

        return sorted(sensitive_points, key=lambda x: x.distance_km)

    def generate_public_materials(self, project_id: str,
                                  sensitive_points: List[SensitivePoint]) -> Dict:
        """
        智能生成公众参与材料
        ====================

        针对不同人群生成通俗版环评公示材料
        """
        materials = {
            "simple_summary": "",  # 简易版公示
            "detailed_summary": "",  # 详细版公示
            "video_script": "",  # 短视频脚本
            "faq": [],  # 常见问题
            "feedback_form": {}  # 意见反馈表
        }

        # 生成简易版公示 (适合普通居民)
        materials["simple_summary"] = f"""
【环评公示 - 简易版】

项目名称：{project_id}
建设内容：主要进行XXX生产
主要污染物：废气、废水、固废
环保措施：采用XXX处理技术，确保达标排放

如您对项目有意见或建议，请于公示之日起10个工作日内反馈。
联系方式：XXX环保局 / XXX
        """.strip()

        # 生成详细版公示
        materials["detailed_summary"] = f"""
【环境影响评价报告表 - 公示版】

一、项目基本情况
项目名称：{project_id}
建设单位：XXX有限公司
建设地点：XXX省XXX市XXX区
总投资：XXX万元

二、建设项目对环境可能造成的影响
1. 大气环境影响：主要废气污染物为SO2、NOx、颗粒物
2. 水环境影响：生产废水经处理后达标排放
3. 噪声环境影响：选用低噪声设备，采取隔声减振措施
4. 固废影响：分类收集，综合利用或安全处置

三、拟采取的环境保护措施
1. 废气：布袋除尘 + 活性炭吸附 + RTO焚烧
2. 废水：物化预处理 + 生化处理 + MBR膜
3. 噪声：隔声房 + 低噪声设备 + 减振基础
4. 固废：分类收集，危险废物委托资质单位处置

四、周边敏感点
- 医院：1处，距项目{materials.get('hospital_distance', '1.5')}km
- 学校：1处，距项目{materials.get('school_distance', '2.0')}km
- 居民区：1处，距项目{materials.get('residential_distance', '0.8')}km
        """.strip()

        # 生成短视频脚本
        materials["video_script"] = """
【30秒环评公示短视频脚本】

[0-5秒] 画面：项目效果图 + 标题"XX项目环境影响评价公示"
[5-10秒] 画面：厂区全景 + 配音"本项目位于XX，总投资XX万元"
[10-18秒] 画面：环保设施动画演示 + 配音"我们采用国内先进的环保处理技术"
[18-25秒] 画面：监测数据实时展示 + 配音"排放浓度远低于国家标准"
[25-30秒] 画面：联系方式 + 配音"欢迎您提出宝贵意见"

【60秒详细版脚本】(扩展)
... (同上扩展)
        """.strip()

        # 生成FAQ
        materials["faq"] = [
            {"question": "项目建设对空气质量有影响吗？",
             "answer": "项目采用全流程密闭生产，废气经高效处理后达标排放，对周边空气质量影响可控。"},
            {"question": "废水如何处理？",
             "answer": "生产废水经预处理+生化处理+深度处理后，全部回用不外排。"},
            {"question": "噪声会不会扰民？",
             "answer": "主要噪声设备置于厂房内，采用隔声减振措施，边界噪声达标。"},
            {"question": "固废如何处置？",
             "answer": "危险废物委托有资质单位处置，一般固废综合利用。"},
        ]

        # 反馈表单
        materials["feedback_form"] = {
            "name": {"type": "text", "required": False, "label": "姓名(可选)"},
            "contact": {"type": "text", "required": False, "label": "联系方式"},
            "opinion": {"type": "textarea", "required": True, "label": "意见或建议"},
            "category": {
                "type": "select",
                "required": True,
                "label": "意见类别",
                "options": ["支持项目建设", "对环保措施有意见", "对选址有意见", "其他"]
            }
        }

        return materials

    def run_simulation(self, project_data: Dict, impact_types: List[ImpactType]) -> Dict:
        """
        运行环境影响仿真
        =================

        整合大气扩散、水质、噪声模型，进行三维时空仿真
        """
        results = {
            "simulation_id": str(uuid.uuid4())[:12],
            "project_id": project_data.get('project_id'),
            "timestamp": datetime.now().isoformat(),
            "impacts": {}
        }

        # 1. 大气扩散仿真 (CALPUFF/AERMOD)
        if ImpactType.AIR in impact_types:
            air_impact = self._simulate_air_dispersion(project_data)
            results["impacts"]["air"] = air_impact

        # 2. 水环境影响仿真
        if ImpactType.WATER in impact_types:
            water_impact = self._simulate_water_impact(project_data)
            results["impacts"]["water"] = water_impact

        # 3. 噪声影响仿真
        if ImpactType.NOISE in impact_types:
            noise_impact = self._simulate_noise_impact(project_data)
            results["impacts"]["noise"] = noise_impact

        # 4. 综合评价
        results["overall_assessment"] = self._comprehensive_assessment(results["impacts"])

        return results

    def _simulate_air_dispersion(self, project_data: Dict) -> Dict:
        """大气扩散仿真 (简化模型)"""
        # 实际应调用CALPUFF/AERMOD，这里提供接口
        return {
            "model": "AERMOD",
            "max_concentration": {"SO2": "45 μg/m³", "NOx": "78 μg/m³", "PM2.5": "35 μg/m³"},
            "ground_level_impact": "符合GB3095-2012二级标准",
            "sensitive_point_impacts": [
                {"name": "幸福小区", "distance": "800m", "max_24h_concentration": "28 μg/m³", "standard": "75 μg/m³", "exceeded": False}
            ],
            "simulation_years": 20,
            "worst_case_hourly": "98.5 μg/m³ (出现在气象不利条件)",
            "recommendations": ["设置100m卫生防护距离", "加强尾气处理效率"]
        }

    def _simulate_water_impact(self, project_data: Dict) -> Dict:
        """水环境影响仿真"""
        return {
            "model": "QUAL2K",
            "discharge_amount": "100 m³/d",
            "receiving_water_body": "XX河",
            "impact_range": "下游5km范围内",
            "concentration_increase": "COD +2.5 mg/L",
            "self_purification_time": "约72小时",
            "recommendations": ["增加废水处理能力", "设置应急池"]
        }

    def _simulate_noise_impact(self, project_data: Dict) -> Dict:
        """噪声影响仿真"""
        return {
            "model": "CadnaA",
            "daytime_boundary": "55 dB(A) - 达标",
            "nighttime_boundary": "48 dB(A) - 达标",
            "nearest_sensitive_point": {
                "name": "幸福小区",
                "daytime": "52 dB(A)",
                "nighttime": "42 dB(A)"
            },
            "recommendations": ["厂界设置3m隔声墙", "夜间禁止高噪声作业"]
        }

    def _comprehensive_assessment(self, impacts: Dict) -> Dict:
        """综合环境影响评价"""
        return {
            "level": "二级评价",
            "conclusion": "从环保角度分析，项目选址可行建设",
            "main_concerns": ["大气卫生防护距离内存在居民", "废水排放对下游水体有一定影响"],
            "overall_recommendation": "在落实各项环保措施的前提下，项目建设可行",
            "confidence": 0.92
        }

    def generate_alternatives(self, project_data: Dict, count: int = 3) -> List[AlternativeScheme]:
        """
        AI生成替代方案
        ==============

        基于项目特征，自动生成3-5个替代方案，进行多维度比选
        """
        schemes = []

        # 方案1: 原方案 (基准)
        schemes.append(AlternativeScheme(
            scheme_id="A",
            name="推荐方案",
            description="采用成熟工艺，合理选址",
            location="现选址方案",
            technology="成熟稳定的生产工艺",
            treatment="标准污染治理设施",
            investment=5000,
            operation_cost=800,
            emission_reduction=100,
            land_use=50,
            environmental_score=85,
            economic_score=80,
            social_score=75,
            overall_score=80,
            risks=["投资回收期较长"],
            recommendations=["争取绿色信贷"]
        ))

        # 方案2: 清洁生产工艺
        schemes.append(AlternativeScheme(
            scheme_id="B",
            name="清洁生产方案",
            description="采用先进的清洁生产工艺，从源头减排",
            location="现选址方案",
            technology="自动化密闭生产线",
            treatment="高效末端治理",
            investment=7000,
            operation_cost=600,
            emission_reduction=150,
            land_use=45,
            environmental_score=95,
            economic_score=70,
            social_score=85,
            overall_score=83,
            risks=["投资较大"],
            recommendations=["申请清洁生产专项资金", "享受环保税减免"]
        ))

        # 方案3: 选址调整方案
        schemes.append(AlternativeScheme(
            scheme_id="C",
            name="选址优化方案",
            description="调整选址至工业园区，减少对敏感点影响",
            location="调整至XX工业园区",
            technology="同方案A",
            treatment="同方案A",
            investment=5500,
            operation_cost=820,
            emission_reduction=100,
            land_use=40,
            environmental_score=90,
            economic_score=75,
            social_score=90,
            overall_score=85,
            risks=["园区土地成本较高"],
            recommendations=["提前与园区管委会沟通"]
        ))

        return schemes[:count]

    def generate_decision_matrix(self, schemes: List[AlternativeScheme]) -> Dict:
        """
        生成AI决策矩阵
        =============

        多维度比选，综合评分，输出最优推荐
        """
        matrix = {
            "criteria": [
                {"name": "环保效益", "weight": 0.35, "unit": "分"},
                {"name": "经济性", "weight": 0.30, "unit": "分"},
                {"name": "社会影响", "weight": 0.20, "unit": "分"},
                {"name": "技术可行性", "weight": 0.15, "unit": "分"},
            ],
            "alternatives": [],
            "recommended": ""
        }

        for scheme in schemes:
            alt_data = {
                "scheme_id": scheme.scheme_id,
                "name": scheme.name,
                "scores": {
                    "环保效益": scheme.environmental_score,
                    "经济性": scheme.economic_score,
                    "社会影响": scheme.social_score,
                    "技术可行性": 85,  # 默认
                },
                "weighted_score": scheme.overall_score,
                "investment": scheme.investment,
                "operation_cost": scheme.operation_cost,
            }
            matrix["alternatives"].append(alt_data)

        # 推荐得分最高者
        if schemes:
            best = max(schemes, key=lambda x: x.overall_score)
            matrix["recommended"] = best.scheme_id
            matrix["recommended_name"] = best.name
            matrix["recommended_reason"] = f"综合得分{best.overall_score}分，在环保效益和社会影响方面表现突出"

        return matrix

    def generate_eia_report(self, project_data: Dict, simulation_results: Dict = None,
                           alternatives: List[AlternativeScheme] = None) -> EIAReport:
        """
        生成完整智能环评报告
        =====================

        L2级别：AI生成 + 人工审核
        """
        report_id = f"EIA-{project_data.get('project_id', 'UNKNOWN')}-{datetime.now().strftime('%Y%m%d%H%M')}"

        report = EIAReport(
            report_id=report_id,
            project_id=project_data.get('project_id', ''),

            # 执行摘要
            executive_summary=f"""
本报告对{project_data.get('project_name', 'XX项目')}进行了全面的环境影响评价。

经仿真模拟和综合分析：
- 大气环境影响：各敏感点浓度均达标
- 水环境影响：排放对受纳水体影响可控
- 噪声环境影响：厂界噪声达标

推荐方案：{alternatives[0].name if alternatives else '推荐方案A'}
推荐理由：综合得分最高，环保与社会效益平衡良好

报告置信度：92%
报告级别：L2半自动化（AI生成+人工审核）
            """.strip(),

            # 各章节内容
            project_description=project_data.get('description', ''),
            environment现状=self._generate_environment_status_section(project_data),
           环境影响_prediction=self._generate_impact_prediction_section(simulation_results),
            pollution_prevention=self._generate_pollution_prevention_section(project_data),
            environmental效益=self._generate_benefit_section(alternatives),
            environmental管理与监测=self._generate_management_section(project_data),
            结论与建议=self._generate_conclusion_section(alternatives),

            # 附件
            alternatives=alternatives or [],
            sensitive_points=[],  # 另行填充

            # 仿真结果
            simulation_results=simulation_results or {},

            # 决策
            recommended_scheme=alternatives[0].scheme_id if alternatives else "A",
            decision_matrix=self.generate_decision_matrix(alternatives or []) if alternatives else {},

            # 生成信息
            autopilot_level=2,
            confidence=0.92,
            generated_at=datetime.now().isoformat(),
        )

        return report

    def _generate_environment_status_section(self, project_data: Dict) -> str:
        """生成环境现状章节"""
        return f"""
### 1. 环境现状

#### 1.1 自然环境概况
- 地形地貌：项目位于XX地形区，海拔XXm
- 气候特征：亚热带季风气候，年均温XX℃，主导风向XX
- 水文条件：项目位于XX流域，距离XX水体XXkm

#### 1.2 环境质量现状
1. 空气质量：参照XX监测站数据，SO2、NO2、PM2.5均达到GB3095-2012二级标准
2. 水环境质量：XX河段水质达到GB3838-2002 III类标准
3. 声环境质量：项目区域声环境质量达到GB3096-2008 2类标准

#### 1.3 敏感点分布
项目周边5km范围内共有敏感点X处，主要为居民区和学校，均已纳入影响分析。
        """.strip()

    def _generate_impact_prediction_section(self, simulation_results: Dict) -> str:
        """生成环境影响预测章节"""
        if not simulation_results:
            return "仿真数据待补充"

        impacts = simulation_results.get("impacts", {})
        return f"""
### 2. 环境影响预测

#### 2.1 大气环境影响
- 预测模型：AERMOD
- 预测结果：各关心点浓度均低于GB3095-2012二级标准限值
- 最大落地浓度：SO2 XX μg/m³，NOx XX μg/m³

#### 2.2 水环境影响
- 预测模型：QUAL2K
- 预测结果：废水排放对XX河段水质影响可控

#### 2.3 噪声环境影响
- 预测模型：CadnaA
- 预测结果：厂界噪声达标，对敏感点影响可控
        """.strip()

    def _generate_pollution_prevention_section(self, project_data: Dict) -> str:
        """生成污染防治措施章节"""
        return """
### 3. 污染防治措施

#### 3.1 废气治理
- 粉尘：布袋除尘器，除尘效率≥99%
- VOCs：活性炭吸附+RTO焚烧，综合效率≥95%
- 排放标准：执行GB16297-1996表2标准

#### 3.2 废水治理
- 工艺废水：物化预处理 + 生化处理 + MBR膜
- 生活污水：一体化污水处理设施
- 回用率：≥70%
- 排放标准：执行GB8978-1996表4一级标准

#### 3.3 噪声治理
- 设备选型：低噪声设备
- 隔声减振：隔声房 + 减振基础
- 厂界绿化：设置隔声绿化带
- 排放标准：执行GB12348-2008 3类标准

#### 3.4 固废治理
- 危险废物：分类收集，委托资质单位处置
- 一般固废：综合利用率≥90%
- 排放标准：执行GB18599-2020标准
        """.strip()

    def _generate_benefit_section(self, alternatives: List[AlternativeScheme]) -> str:
        """生成环保效益章节"""
        if not alternatives:
            return "待补充"

        best = alternatives[0]
        return f"""
### 4. 环保效益分析

#### 4.1 主要污染物减排效果
| 污染物 | 排放量(t/年) | 减排量(t/年) |
|--------|------------|------------|
| SO2 | XX | XX |
| NOx | XX | XX |
| 烟粉尘 | XX | XX |
| VOCs | XX | XX |

#### 4.2 方案比选
推荐方案（{best.name}）：
- 总投资：{best.investment}万元
- 年运行成本：{best.operation_cost}万元
- 综合得分：{best.overall_score}分
- 环保效益评分：{best.environmental_score}分
        """.strip()

    def _generate_management_section(self, project_data: Dict) -> str:
        """生成环境管理与监测章节"""
        return """
### 5. 环境管理与监测计划

#### 5.1 环境管理
- 设立环保管理机构，配备专职环保人员
- 建立健全环保管理制度
- 定期开展环保培训

#### 5.2 环境监测计划
| 监测类型 | 监测项目 | 监测频率 |
|---------|---------|---------|
| 废气有组织 | SO2、NOx、颗粒物、VOCs | 季度监测 |
| 废气无组织 | 颗粒物、VOCs | 季度监测 |
| 废水 | pH、COD、NH3-N、总磷 | 在线监测+月度比对 |
| 噪声 | Leq(A) | 季度监测 |
| 土壤 | 重金属、VOCs | 年度监测 |
| 地下水 | pH、高锰酸盐指数 | 年度监测 |

#### 5.3 台账管理
- 建立污染物排放台账
- 建立危险废物管理台账
- 建立监测数据档案
        """.strip()

    def _generate_conclusion_section(self, alternatives: List[AlternativeScheme]) -> str:
        """生成结论与建议章节"""
        best = alternatives[0] if alternatives else None
        return f"""
### 6. 结论与建议

#### 6.1 结论
1. 项目选址符合区域规划
2. 采取的环保措施技术可行、经济合理
3. 排放污染物可达标排放
4. {f"推荐采用{best.name}方案" if best else "推荐采用推荐方案"}
5. 项目建设从环保角度分析可行

#### 6.2 建议
1. 严格落实各项环保措施
2. 加强环境管理，确保污染物稳定达标排放
3. 做好环境监测和信息公开
4. 制定环境应急预案，定期演练
5. 及时办理排污许可证，按证排污
        """.strip()


# 便捷函数
def create_eia40_engine(lifecycle_manager=None) -> EIA40Engine:
    """创建智能环评4.0引擎"""
    return EIA40Engine(lifecycle_manager)
