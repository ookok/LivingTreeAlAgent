"""
模块6: 环境风险管理引擎 - Risk Management Engine
=============================================

从"被动应对"转向"预测性防控"

核心能力：
1. 风险动态评估 - 每日自动评估环境风险等级
2. 供应链风险穿透 - 监控上下游环保风险
3. 环保指数预测 - 预测未来30天被处罚概率
4. 预测性预警系统
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskCategory(Enum):
    """风险类别"""
    EMISSION = "emission"           # 排放风险
    EQUIPMENT = "equipment"         # 设备风险
    MANAGEMENT = "management"       # 管理风险
    SUPPLY_CHAIN = "supply_chain"   # 供应链风险
    REGULATORY = "regulatory"       # 监管风险
    SOCIAL = "social"               # 社会风险


@dataclass
class RiskFactor:
    """风险因子"""
    factor_id: str
    category: RiskCategory
    name: str
    description: str

    # 评估参数
    current_value: float = 0.0
    threshold_warning: float = 0.0
    threshold_critical: float = 0.0

    # 状态
    risk_level: RiskLevel = RiskLevel.LOW
    trend: str = "stable"  # rising/falling/stable
    updated_at: str = ""


@dataclass
class RiskAssessment:
    """风险评估报告"""
    assessment_id: str
    project_id: str
    company_id: str

    # 评估时间
    assessment_date: str = ""
    period_start: str = ""
    period_end: str = ""

    # 风险等级
    overall_risk_level: RiskLevel = RiskLevel.LOW
    risk_score: float = 0.0  # 0-100

    # 各类风险
    risk_by_category: Dict[RiskCategory, float] = field(default_factory=dict)

    # 主要风险因子
    top_risk_factors: List[RiskFactor] = field(default_factory=list)

    # 预警信号
    early_warnings: List[str] = field(default_factory=list)

    # 建议措施
    recommended_actions: List[str] = field(default_factory=list)

    # 预测
    risk_prediction_30d: Dict = field(default_factory=dict)


@dataclass
class SupplyChainRisk:
    """供应链风险"""
    supplier_id: str
    supplier_name: str
    supplier_industry: str

    # 风险信息
    risk_type: RiskCategory = RiskCategory.SUPPLY_CHAIN
    risk_level: RiskLevel = RiskLevel.LOW
    risk_description: str = ""

    # 影响评估
    impact_on_raw_materials: str = ""  # 对原料供应的影响
    impact_on_reputation: str = ""     # 对品牌声誉的影响

    # 事件记录
    incidents: List[Dict] = field(default_factory=list)

    # 状态
    status: str = "monitoring"
    last_updated: str = ""


class RiskManagementEngine:
    """
    环境风险管理引擎
    ===============

    创新点：
    - 从"被动应对"转向"预测性防控"
    - 每日自动评估企业环境风险等级
    - 供应链风险穿透式监控
    - "环保指数"预测被处罚概率
    """

    def __init__(self, lifecycle_manager=None):
        self.lifecycle_manager = lifecycle_manager

        # 风险因子库
        self._risk_factors: Dict[str, List[RiskFactor]] = {}

        # 评估历史
        self._assessment_history: Dict[str, List[RiskAssessment]] = {}

        # 供应链风险
        self._supply_chain_risks: Dict[str, List[SupplyChainRisk]] = {}

        # 风险因子模板
        self._factor_templates = self._init_factor_templates()

    def _init_factor_templates(self) -> Dict[RiskCategory, List[Dict]]:
        """初始化风险因子模板"""
        return {
            RiskCategory.EMISSION: [
                {"name": "排放浓度超标次数", "threshold_warning": 3, "threshold_critical": 5},
                {"name": "排放总量使用率", "threshold_warning": 0.8, "threshold_critical": 0.95},
                {"name": "在线监测数据有效率", "threshold_warning": 0.95, "threshold_critical": 0.90},
            ],
            RiskCategory.EQUIPMENT: [
                {"name": "治理设施运行时率", "threshold_warning": 0.95, "threshold_critical": 0.90},
                {"name": "设备故障次数", "threshold_warning": 2, "threshold_critical": 4},
                {"name": "维护保养及时率", "threshold_warning": 0.90, "threshold_critical": 0.80},
            ],
            RiskCategory.MANAGEMENT: [
                {"name": "台账记录完整率", "threshold_warning": 0.95, "threshold_critical": 0.90},
                {"name": "整改任务完成率", "threshold_warning": 0.90, "threshold_critical": 0.80},
                {"name": "人员培训覆盖率", "threshold_warning": 0.95, "threshold_critical": 0.85},
            ],
            RiskCategory.REGULATORY: [
                {"name": "许可证到期天数", "threshold_warning": 90, "threshold_critical": 30},
                {"name": "法规更新影响", "threshold_warning": 1, "threshold_critical": 2},
                {"name": "行政处罚次数", "threshold_warning": 1, "threshold_critical": 3},
            ],
        }

    def initialize_risk_factors(self, project_id: str, company_id: str) -> List[RiskFactor]:
        """初始化风险因子"""
        factors = []

        for category, templates in self._factor_templates.items():
            for template in templates:
                factor = RiskFactor(
                    factor_id=str(uuid.uuid4())[:12],
                    category=category,
                    name=template["name"],
                    description=template["name"],
                    threshold_warning=template["threshold_warning"],
                    threshold_critical=template["threshold_critical"],
                    updated_at=datetime.now().isoformat()
                )
                factors.append(factor)

        self._risk_factors[project_id] = factors
        return factors

    def update_risk_factor(self, project_id: str, factor_name: str,
                         value: float) -> RiskFactor:
        """更新风险因子"""
        factors = self._risk_factors.get(project_id, [])

        for factor in factors:
            if factor.name == factor_name:
                factor.current_value = value
                factor.updated_at = datetime.now().isoformat()

                # 计算风险等级
                if isinstance(factor.threshold_warning, float):
                    # 比例型因子
                    if value < factor.threshold_critical:
                        factor.risk_level = RiskLevel.CRITICAL
                    elif value < factor.threshold_warning:
                        factor.risk_level = RiskLevel.HIGH
                    else:
                        factor.risk_level = RiskLevel.LOW
                else:
                    # 次数型因子
                    if value >= factor.threshold_critical:
                        factor.risk_level = RiskLevel.CRITICAL
                    elif value >= factor.threshold_warning:
                        factor.risk_level = RiskLevel.HIGH
                    else:
                        factor.risk_level = RiskLevel.LOW

                return factor

        return None

    def run_daily_assessment(self, project_id: str, company_id: str) -> RiskAssessment:
        """
        每日风险评估
        ============

        每日自动评估企业环境风险等级
        """
        factors = self._risk_factors.get(project_id, [])
        if not factors:
            factors = self.initialize_risk_factors(project_id, company_id)

        # 模拟更新因子值
        self._simulate_factor_updates(project_id)

        # 计算各类风险
        risk_by_category = {}
        for category in RiskCategory:
            cat_factors = [f for f in factors if f.category == category]
            if cat_factors:
                # 加权平均
                scores = [self._factor_to_score(f) for f in cat_factors]
                risk_by_category[category] = sum(scores) / len(scores)

        # 计算综合风险得分
        overall_score = sum(risk_by_category.values()) / len(risk_by_category) if risk_by_category else 0

        # 确定风险等级
        if overall_score >= 80:
            overall_level = RiskLevel.CRITICAL
        elif overall_score >= 60:
            overall_level = RiskLevel.HIGH
        elif overall_score >= 40:
            overall_level = RiskLevel.MEDIUM
        else:
            overall_level = RiskLevel.LOW

        # 获取Top风险因子
        sorted_factors = sorted(factors, key=lambda x: self._factor_to_score(x), reverse=True)
        top_factors = sorted_factors[:5]

        # 生成预警信号
        warnings = []
        for f in top_factors:
            if f.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                warnings.append(f"{f.name}风险{f.risk_level.value}")

        # 生成建议措施
        actions = []
        for f in top_factors:
            if f.risk_level == RiskLevel.CRITICAL:
                actions.append(f"立即处理：{f.name}")
            elif f.risk_level == RiskLevel.HIGH:
                actions.append(f"重点关注：{f.name}")

        # 30天预测
        prediction = self._predict_risk_30d(project_id, factors)

        assessment = RiskAssessment(
            assessment_id=str(uuid.uuid4())[:12],
            project_id=project_id,
            company_id=company_id,
            assessment_date=datetime.now().strftime('%Y-%m-%d'),
            period_start=(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
            period_end=datetime.now().strftime('%Y-%m-%d'),
            overall_risk_level=overall_level,
            risk_score=round(overall_score, 1),
            risk_by_category=risk_by_category,
            top_risk_factors=top_factors,
            early_warnings=warnings,
            recommended_actions=actions,
            risk_prediction_30d=prediction
        )

        # 存储历史
        if project_id not in self._assessment_history:
            self._assessment_history[project_id] = []
        self._assessment_history[project_id].append(assessment)

        return assessment

    def _simulate_factor_updates(self, project_id: str):
        """模拟因子更新（实际应从数据源采集）"""
        factors = self._risk_factors.get(project_id, [])

        # 模拟数据
        import random
        mock_values = {
            "排放浓度超标次数": random.randint(0, 4),
            "排放总量使用率": random.uniform(0.5, 0.9),
            "在线监测数据有效率": random.uniform(0.88, 0.99),
            "治理设施运行时率": random.uniform(0.92, 0.99),
            "设备故障次数": random.randint(0, 3),
            "台账记录完整率": random.uniform(0.90, 0.99),
            "整改任务完成率": random.uniform(0.85, 0.98),
            "许可证到期天数": 120,
            "行政处罚次数": random.randint(0, 2),
        }

        for factor in factors:
            if factor.name in mock_values:
                self.update_risk_factor(project_id, factor.name, mock_values[factor.name])

    def _factor_to_score(self, factor: RiskFactor) -> float:
        """因子转换为0-100分数"""
        if factor.risk_level == RiskLevel.CRITICAL:
            return 100
        elif factor.risk_level == RiskLevel.HIGH:
            return 70
        elif factor.risk_level == RiskLevel.MEDIUM:
            return 40
        else:
            return 10

    def _predict_risk_30d(self, project_id: str, factors: List[RiskFactor]) -> Dict:
        """
        预测未来30天风险
        ===============

        预测未来30天被处罚概率
        """
        # 基于当前风险因子预测
        critical_count = sum(1 for f in factors if f.risk_level == RiskLevel.CRITICAL)
        high_count = sum(1 for f in factors if f.risk_level == RiskLevel.HIGH)

        # 基础概率
        base_probability = 0.05

        # 风险因子调整
        if critical_count > 0:
            base_probability += critical_count * 0.15
        if high_count > 0:
            base_probability += high_count * 0.05

        # 近期趋势
        history = self._assessment_history.get(project_id, [])
        if len(history) >= 7:
            recent_scores = [h.risk_score for h in history[-7:]]
            if all(recent_scores[i] >= recent_scores[i+1] for i in range(len(recent_scores)-1)):
                base_probability *= 1.5  # 上升趋势

        # 风险因素
        risk_factors_pred = []
        if critical_count > 0:
            risk_factors_pred.append(f"存在{critical_count}项重大风险")
        if high_count > 0:
            risk_factors_pred.append(f"存在{high_count}项较高风险")

        return {
            "probability": min(1.0, base_probability),
            "probability_percent": f"{base_probability*100:.1f}%",
            "risk_factors": risk_factors_pred,
            "confidence": 0.75,
            "trend": "stable" if len(history) < 7 else (
                "rising" if history[-1].risk_score > history[-7].risk_score else "falling"
            )
        }

    def monitor_supply_chain(self, company_id: str,
                            supplier_data: List[Dict]) -> List[SupplyChainRisk]:
        """
        供应链风险穿透监控
        ==================

        监控上游供应商的环保处罚、突发环境事件
        """
        risks = []

        for supplier in supplier_data:
            risk = SupplyChainRisk(
                supplier_id=supplier['id'],
                supplier_name=supplier['name'],
                supplier_industry=supplier.get('industry', ''),
                risk_description="",
                status="monitoring",
                last_updated=datetime.now().isoformat()
            )

            # 模拟风险检测
            import random
            has_incident = random.random() < 0.1  # 10%概率有事件

            if has_incident:
                risk.risk_level = RiskLevel(random.choice(['low', 'medium', 'high']))
                risk.risk_description = f"供应商{risk.supplier_name}近期发生环保违规事件"
                risk.incidents = [{
                    "type": "环保处罚",
                    "date": (datetime.now() - timedelta(days=random.randint(1, 30))).strftime('%Y-%m-%d'),
                    "description": "超标排放被罚款"
                }]
                risk.impact_on_raw_materials = "原材料供应可能受影响"
                risk.impact_on_reputation = "品牌形象风险上升"

            risks.append(risk)
            self._supply_chain_risks.setdefault(company_id, []).append(risk)

        return risks

    def get_environmental_index(self, project_id: str) -> Dict:
        """
        获取环保指数
        ===========

        类似"信用分"，为企业生成每日更新的环保健康指数
        """
        history = self._assessment_history.get(project_id, [])

        if not history:
            return {
                "index": 85,
                "grade": "A",
                "trend": "stable",
                "description": "暂无评估数据"
            }

        latest = history[-1]

        # 转换为100分制环保指数
        environmental_index = 100 - (latest.risk_score * 0.5)

        # 确定等级
        if environmental_index >= 90:
            grade = "A+"
        elif environmental_index >= 80:
            grade = "A"
        elif environmental_index >= 70:
            grade = "B"
        elif environmental_index >= 60:
            grade = "C"
        else:
            grade = "D"

        # 趋势
        if len(history) >= 7:
            if latest.risk_score < history[-7].risk_score:
                trend = "improving"
            elif latest.risk_score > history[-7].risk_score:
                trend = "deteriorating"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return {
            "index": round(environmental_index, 1),
            "grade": grade,
            "trend": trend,
            "description": f"环保指数{environmental_index:.0f}分，{grade}级",
            "risk_level": latest.overall_risk_level.value,
            "last_assessment": latest.assessment_date,
            "improvement_suggestions": latest.recommended_actions[:3]
        }

    def get_risk_report(self, project_id: str) -> Dict:
        """获取风险报告"""
        history = self._assessment_history.get(project_id, [])

        if not history:
            return {"error": "No assessment history"}

        latest = history[-1]

        return {
            "project_id": project_id,
            "report_date": latest.assessment_date,
            "overall_risk_level": latest.overall_risk_level.value,
            "risk_score": latest.risk_score,
            "environmental_index": self.get_environmental_index(project_id),
            "top_risks": [
                {
                    "factor": f.name,
                    "level": f.risk_level.value,
                    "value": f.current_value
                }
                for f in latest.top_risk_factors[:5]
            ],
            "risk_prediction_30d": latest.risk_prediction_30d,
            "recommended_actions": latest.recommended_actions,
            "early_warnings": latest.early_warnings
        }


def create_risk_engine(lifecycle_manager=None) -> RiskManagementEngine:
    """创建风险管理引擎"""
    return RiskManagementEngine(lifecycle_manager)
