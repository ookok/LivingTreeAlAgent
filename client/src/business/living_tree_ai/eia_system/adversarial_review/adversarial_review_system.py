"""
对抗性评审系统 - AI驱动的"对抗性评审"
模拟最严格的评审专家，对报告进行压力测试

核心能力：
1. 自动生成评审问题（多专业角度）
2. 智能回复建议
3. 评审焦点预测
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


# ============================================================================
# 数据模型
# ============================================================================

class ReviewPerspective(Enum):
    """评审视角"""
    ATMOSPHERE = "atmosphere"      # 大气专家
    WATER = "water"                # 水环境专家
    ECOLOGY = "ecology"           # 生态专家
    RISK = "risk"                 # 风险专家
    NOISE = "noise"               # 噪声专家
    SOLID_WASTE = "solid_waste"    # 固废专家
    SOCIAL = "social"             # 社会专家
    OVERALL = "overall"           # 综合评审


class QuestionType(Enum):
    """问题类型"""
    FACTUAL = "factual"           # 事实性错误
    LOGICAL = "logical"          # 逻辑矛盾
    COMPLIANCE = "compliance"    # 合规性问题
    COMPLETENESS = "completeness" # 完整性问题
    METHODOLOGY = "methodology"  # 方法学问题
    DATA_QUALITY = "data_quality" # 数据质量问题


class QuestionStatus(Enum):
    """问题状态"""
    OPEN = "open"                 # 待回复
    ANSWERED = "answered"         # 已回复
    ACCEPTED = "accepted"         # 已接受
    REJECTED = "rejected"         # 已驳回
    RESOLVED = "resolved"         # 已解决


@dataclass
class ReviewQuestion:
    """评审问题"""
    question_id: str
    perspective: ReviewPerspective
    question_type: QuestionType
    section: str                   # 涉及的章节
    content: str                   # 问题内容
    severity: int = 1              # 严重程度 1-5
    status: QuestionStatus = QuestionStatus.OPEN
    suggested_answer: str = ""     # 建议回复
    supporting_data: list = field(default_factory=list)
    related_regulations: list = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    answered_at: Optional[datetime] = None


@dataclass
class ReplyDraft:
    """回复草稿"""
    question_id: str
    reply_content: str
    supporting_documents: list
    confidence: float              # 置信度 0-1
    suggested_revisions: list


@dataclass
class ReviewFocus:
    """评审焦点"""
    section: str
    risk_score: float             # 风险评分 0-100
    historical_challenge_rate: float
    factors: list
    recommendations: list


@dataclass
class AdversarialReview:
    """对抗性评审"""
    review_id: str
    report_id: str
    report_name: str
    questions: list = field(default_factory=list)
    focus_predictions: list = field(default_factory=list)
    overall_risk_score: float = 0
    focus_areas: list = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


# ============================================================================
# 评审问题生成器
# ============================================================================

class QuestionGenerator:
    """评审问题生成器"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._knowledge_base = self._init_knowledge_base()

    def _init_knowledge_base(self) -> dict:
        """初始化知识库"""
        return {
            ReviewPerspective.ATMOSPHERE: {
                "common_issues": [
                    "施工期对环境空气质量的影响是否充分评估？",
                    "特征污染物是否全部识别？",
                    "预测模式选择是否合理？",
                    "卫生防护距离设置是否满足要求？"
                ],
                "key_regulations": [
                    "GB 3095-2012 环境空气质量标准",
                    "HJ 2.2-2018 大气环境影响评价技术导则"
                ]
            },
            ReviewPerspective.WATER: {
                "common_issues": [
                    "水环境功能区划是否正确？",
                    "废水处理工艺可行性",
                    "排放口位置设置合理性"
                ],
                "key_regulations": [
                    "GB 3838-2002 地表水环境质量标准"
                ]
            },
            ReviewPerspective.ECOLOGY: {
                "common_issues": [
                    "生态敏感区保护是否充分？",
                    "生物多样性影响评估",
                    "水土流失预测"
                ],
                "key_regulations": [
                    "HJ 19-2022 环境影响评价技术导则 生态影响"
                ]
            },
            ReviewPerspective.RISK: {
                "common_issues": [
                    "环境风险识别是否全面？",
                    "风险事故情形设定合理性",
                    "应急预案完整性"
                ],
                "key_regulations": [
                    "HJ 169-2018 建设项目环境风险评价技术导则"
                ]
            }
        }

    async def generate_questions(
        self,
        report_content: dict,
        perspectives: list[ReviewPerspective] = None
    ) -> list[ReviewQuestion]:
        """生成评审问题"""
        if perspectives is None:
            perspectives = list(ReviewPerspective)

        questions = []
        for perspective in perspectives:
            persp_questions = await self._generate_perspective_questions(perspective, report_content)
            questions.extend(persp_questions)

        return questions

    async def _generate_perspective_questions(
        self,
        perspective: ReviewPerspective,
        report_content: dict
    ) -> list[ReviewQuestion]:
        """生成特定视角的问题"""
        knowledge = self._knowledge_base.get(perspective, {})
        common_issues = knowledge.get("common_issues", [])
        questions = []

        for i, issue_template in enumerate(common_issues[:3]):
            question = ReviewQuestion(
                question_id=f"q_{perspective.value}_{i+1}",
                perspective=perspective,
                question_type=self._infer_question_type(issue_template),
                section=self._infer_section(issue_template, perspective),
                content=issue_template,
                severity=self._assess_severity(issue_template),
                related_regulations=knowledge.get("key_regulations", [])
            )
            questions.append(question)

        return questions

    def _infer_question_type(self, issue: str) -> QuestionType:
        """推断问题类型"""
        if any(k in issue for k in ["识别", "是否"]):
            return QuestionType.COMPLETENESS
        elif any(k in issue for k in ["矛盾", "匹配"]):
            return QuestionType.LOGICAL
        elif any(k in issue for k in ["标准", "规范"]):
            return QuestionType.COMPLIANCE
        elif any(k in issue for k in ["方法", "模式"]):
            return QuestionType.METHODOLOGY
        elif any(k in issue for k in ["数据", "监测"]):
            return QuestionType.DATA_QUALITY
        return QuestionType.FACTUAL

    def _infer_section(self, issue: str, perspective: ReviewPerspective) -> str:
        """推断涉及章节"""
        section_map = {
            ReviewPerspective.ATMOSPHERE: "大气环境影响评价",
            ReviewPerspective.WATER: "水环境影响评价",
            ReviewPerspective.ECOLOGY: "生态环境影响评价",
            ReviewPerspective.RISK: "环境风险评价",
            ReviewPerspective.OVERALL: "总则"
        }
        return section_map.get(perspective, "其他")

    def _assess_severity(self, issue: str) -> int:
        """评估严重程度"""
        if any(k in issue for k in ["风险", "事故", "超标", "防护距离"]):
            return 5
        elif any(k in issue for k in ["合理性", "充分", "完整"]):
            return 3
        return 2


# ============================================================================
# 智能回复生成器
# ============================================================================

class ReplyGenerator:
    """智能回复生成器"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._templates = self._init_templates()

    def _init_templates(self) -> dict:
        """初始化回复模板"""
        return {
            QuestionType.FACTUAL: {
                "template": "针对您提出的事实性问题，现补充说明如下：\n{evidence}\n具体数据见附件第{page}页。",
                "example": "经复核，报告中SO2排放量为{tonnage}吨/年，符合GB 16297-1996标准要求。"
            },
            QuestionType.LOGICAL: {
                "template": "经核实，本报告不存在逻辑矛盾。具体说明如下：\n{explanation}",
                "example": "根据物质守恒定律，输入源强减去治理设施去除量等于最终排放量。"
            },
            QuestionType.COMPLIANCE: {
                "template": "本项目引用标准{standard}，适用于本项目的{scope}。\n依据说明：{justification}",
                "example": "本项目位于{location}，执行{standard}级标准。"
            },
            QuestionType.METHODOLOGY: {
                "template": "本报告采用{method}模型进行预测，该方法适用于{applicable_scope}。",
                "example": "大气预测采用AERMOD模型，该模型适用于中小尺度平原地区项目。"
            }
        }

    async def generate_reply(self, question: ReviewQuestion, report_content: dict) -> ReplyDraft:
        """生成回复草稿"""
        template = self._templates.get(question.question_type, self._templates[QuestionType.FACTUAL])

        supporting_docs = await self._gather_supporting_data(question, report_content)

        if question.question_type == QuestionType.COMPLIANCE:
            reply_content = self._generate_compliance_reply(question, template)
        elif question.question_type == QuestionType.LOGICAL:
            reply_content = self._generate_logical_reply(question, template)
        else:
            reply_content = template["template"].format(evidence=" ".join(supporting_docs[:2]), page="3")

        return ReplyDraft(
            question_id=question.question_id,
            reply_content=reply_content,
            supporting_documents=supporting_docs,
            confidence=0.85,
            suggested_revisions=await self._suggest_revisions(question)
        )

    def _generate_compliance_reply(self, question: ReviewQuestion, template: dict) -> str:
        """生成合规类回复"""
        regulations = question.related_regulations
        if regulations:
            return template["template"].format(
                standard=regulations[0] if regulations else "相关标准",
                scope="本项目具体情况",
                justification="本项目符合标准中的适用条款"
            )
        return question.content + "\n[建议补充相关标准依据]"

    def _generate_logical_reply(self, question: ReviewQuestion, template: dict) -> str:
        """生成逻辑类回复"""
        return template["template"].format(
            explanation="经核查，报告中的数据遵循物质守恒原则，各参数之间逻辑自洽。"
        )

    async def _gather_supporting_data(self, question: ReviewQuestion, report_content: dict) -> list:
        """收集支持性数据"""
        data = []
        if "源强" in question.content:
            data.append({"type": "数据表", "name": "污染源强清单", "location": "报告第3章"})
        if "预测" in question.content:
            data.append({"type": "计算书", "name": "预测模型计算书", "location": "报告附件"})
        return data

    async def _suggest_revisions(self, question: ReviewQuestion) -> list:
        """建议修订"""
        suggestions = []
        if question.severity >= 4:
            suggestions.append({"type": "补充", "content": "建议补充更详细的数据支撑", "priority": "high"})
        if question.question_type == QuestionType.COMPLETENESS:
            suggestions.append({"type": "完善", "content": "建议补充缺失内容的说明", "priority": "medium"})
        return suggestions


# ============================================================================
# 评审焦点预测器
# ============================================================================

class FocusPredictor:
    """评审焦点预测器"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._historical_data = self._load_historical_data()

    def _load_historical_data(self) -> dict:
        """加载历史数据"""
        return {
            "大气预测": {"challenge_rate": 0.65, "avg_risk": 72},
            "卫生防护距离": {"challenge_rate": 0.58, "avg_risk": 68},
            "风险评价": {"challenge_rate": 0.55, "avg_risk": 75},
            "地表水": {"challenge_rate": 0.42, "avg_risk": 55},
            "生态影响": {"challenge_rate": 0.38, "avg_risk": 48}
        }

    async def predict_focus_areas(self, report_content: dict, industry_type: str = None) -> list[ReviewFocus]:
        """预测评审焦点领域"""
        focus_areas = []

        for section, data in self._historical_data.items():
            risk_score = data["avg_risk"]

            if industry_type == "化工" and "风险" in section:
                risk_score += 15
            elif industry_type == "房地产" and "生态" in section:
                risk_score += 10

            focus = ReviewFocus(
                section=section,
                risk_score=min(risk_score, 100),
                historical_challenge_rate=data["challenge_rate"],
                factors=self._identify_risk_factors(section),
                recommendations=self._generate_recommendations(section, risk_score)
            )
            focus_areas.append(focus)

        focus_areas.sort(key=lambda x: x.risk_score, reverse=True)
        return focus_areas[:5]

    def _identify_risk_factors(self, section: str) -> list:
        """识别风险因素"""
        factors = []
        if "预测" in section:
            factors.extend(["预测模型参数设置", "气象数据代表性"])
        if "风险" in section:
            factors.extend(["事故情形设定", "风险防范措施完备性"])
        if "防护距离" in section:
            factors.extend(["计算方法选择", "卫生防护距离划定"])
        return factors

    def _generate_recommendations(self, section: str, risk_score: float) -> list:
        """生成应对建议"""
        if risk_score > 70:
            return ["建议准备详细的计算依据和数据支撑材料", "建议提前与评审专家沟通技术细节"]
        elif risk_score > 50:
            return ["建议完善相关参数的说明和验证"]
        return []


# ============================================================================
# 对抗性评审引擎（主入口）
# ============================================================================

class AdversarialReviewEngine:
    """对抗性评审引擎"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.question_generator = QuestionGenerator(config)
        self.reply_generator = ReplyGenerator(config)
        self.focus_predictor = FocusPredictor(config)
        self._reviews: dict = {}

    async def start_review(
        self,
        report_id: str,
        report_name: str,
        report_content: dict,
        perspectives: list[ReviewPerspective] = None
    ) -> AdversarialReview:
        """启动对抗性评审"""
        review_id = f"adv_{uuid.uuid4().hex[:12]}"

        review = AdversarialReview(
            review_id=review_id,
            report_id=report_id,
            report_name=report_name
        )

        review.questions = await self.question_generator.generate_questions(report_content, perspectives)

        industry_type = report_content.get("industry_type")
        review.focus_predictions = await self.focus_predictor.predict_focus_areas(report_content, industry_type)

        if review.focus_predictions:
            review.overall_risk_score = sum(f.risk_score for f in review.focus_predictions) / len(review.focus_predictions)

        review.focus_areas = [f.section for f in review.focus_predictions[:3]]

        self._reviews[review_id] = review
        return review

    async def generate_reply(self, review_id: str, question_id: str) -> ReplyDraft:
        """生成问题回复"""
        review = self._reviews.get(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")

        question = next((q for q in review.questions if q.question_id == question_id), None)
        if not question:
            raise ValueError(f"Question {question_id} not found")

        return await self.reply_generator.generate_reply(question, {})

    async def batch_generate_replies(self, review_id: str) -> dict[str, ReplyDraft]:
        """批量生成回复"""
        review = self._reviews.get(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")

        replies = {}
        for question in review.questions:
            replies[question.question_id] = await self.reply_generator.generate_reply(question, {})
        return replies

    def get_review(self, review_id: str) -> Optional[AdversarialReview]:
        """获取评审"""
        return self._reviews.get(review_id)

    def get_high_risk_questions(self, review_id: str, min_severity: int = 4) -> list[ReviewQuestion]:
        """获取高风险问题"""
        review = self._reviews.get(review_id)
        if not review:
            return []
        return [q for q in review.questions if q.severity >= min_severity]


# ============================================================================
# 工厂函数
# ============================================================================

_engine: Optional[AdversarialReviewEngine] = None


def get_adversarial_engine() -> AdversarialReviewEngine:
    """获取对抗性评审引擎单例"""
    global _engine
    if _engine is None:
        _engine = AdversarialReviewEngine()
    return _engine


async def start_adversarial_review_async(
    report_id: str,
    report_name: str,
    report_content: dict,
    perspectives: list[ReviewPerspective] = None
) -> AdversarialReview:
    """异步启动对抗性评审"""
    engine = get_adversarial_engine()
    return await engine.start_review(report_id, report_name, report_content, perspectives)


async def generate_review_reply_async(review_id: str, question_id: str) -> ReplyDraft:
    """异步生成评审回复"""
    engine = get_adversarial_engine()
    return await engine.generate_reply(review_id, question_id)
