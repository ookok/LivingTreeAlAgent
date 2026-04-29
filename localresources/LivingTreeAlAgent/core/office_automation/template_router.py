"""
🎯 智能模板路由系统

多维度匹配最优模板：
- 文档类型匹配
- 受众匹配
- 行业匹配
- 重要程度匹配
- 动态权重调整 (基于使用反馈)
"""

import json
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class CoverStyle(Enum):
    """封面风格 (参考 minimax-pdf 15种封面风格)"""
    CLASSIC = "classic"            # 经典简约
    MODERN = "modern"             # 现代几何
    ELEGANT = "elegant"           # 优雅曲线
    BOLD = "bold"                 # 大胆色块
    MINIMAL = "minimal"           # 极简线条
    CORPORATE = "corporate"       # 企业标准
    TECH = "tech"                 # 科技网格
    CREATIVE = "creative"         # 创意拼接
    NATURE = "nature"             # 自然元素
    ABSTRACT = "abstract"         # 抽象艺术
    PHOTO = "photo"               # 照片背景
    GRADIENT = "gradient"         # 渐变流光
    TYPOGRAPHY = "typography"     # 字体排版
    GEOLOGY = "geology"           # 地质纹理
    AURORA = "aurora"             # 极光效果


@dataclass
class TemplateMatch:
    """模板匹配结果"""
    template_id: str
    score: float
    reasons: List[str] = field(default_factory=list)
    cover_style: CoverStyle = CoverStyle.CLASSIC
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "score": round(self.score, 3),
            "reasons": self.reasons,
            "cover_style": self.cover_style.value,
            "confidence": round(self.confidence, 3),
        }


@dataclass
class TemplateInfo:
    """模板信息"""
    template_id: str
    name: str
    document_types: List[str] = field(default_factory=list)
    audiences: List[str] = field(default_factory=list)
    industries: List[str] = field(default_factory=list)
    importance_levels: List[str] = field(default_factory=list)
    cover_style: CoverStyle = CoverStyle.CLASSIC
    output_format: str = "docx"
    description: str = ""
    tags: List[str] = field(default_factory=list)
    usage_count: int = 0
    rating: float = 0.0
    file_path: Optional[str] = None


class TemplateRouter:
    """
    智能模板路由器

    匹配维度:
    1. 文档类型 (40%)
    2. 受众 (20%)
    3. 行业 (15%)
    4. 重要程度 (10%)
    5. 使用反馈 (15%) - 基于历史评分和使用频率
    """

    # 内置模板库
    BUILTIN_TEMPLATES = [
        TemplateInfo(
            template_id="corp_report_v1",
            name="企业标准报告",
            document_types=["report", "analysis", "summary"],
            audiences=["internal", "executive"],
            industries=["general"],
            importance_levels=["important", "critical"],
            cover_style=CoverStyle.CORPORATE,
            output_format="docx",
            description="适用于企业内部正式报告，包含封面、目录、正文、附录",
        ),
        TemplateInfo(
            template_id="contract_standard",
            name="标准合同模板",
            document_types=["contract"],
            audiences=["external", "client"],
            industries=["general"],
            importance_levels=["critical"],
            cover_style=CoverStyle.CLASSIC,
            output_format="docx",
            description="适用于商业合同、协议书，包含标准条款和签署页",
        ),
        TemplateInfo(
            template_id="proposal_tech",
            name="技术方案模板",
            document_types=["proposal", "plan"],
            audiences=["technical", "client"],
            industries=["tech", "it"],
            importance_levels=["important", "critical"],
            cover_style=CoverStyle.TECH,
            output_format="docx",
            description="适用于技术方案、项目建议书",
        ),
        TemplateInfo(
            template_id="resume_minimal",
            name="简约简历",
            document_types=["resume"],
            audiences=["external"],
            industries=["general"],
            importance_levels=["normal"],
            cover_style=CoverStyle.MINIMAL,
            output_format="docx",
            description="简约风格个人简历，适合各类职位申请",
        ),
        TemplateInfo(
            template_id="gov_document",
            name="政务公文",
            document_types=["policy", "memo", "letter"],
            audiences=["government", "internal"],
            industries=["government"],
            importance_levels=["important", "critical"],
            cover_style=CoverStyle.CLASSIC,
            output_format="docx",
            description="符合国标的政务公文模板",
        ),
        TemplateInfo(
            template_id="pitch_deck",
            name="融资路演",
            document_types=["presentation", "proposal"],
            audiences=["executive", "client"],
            industries=["startup", "finance"],
            importance_levels=["critical"],
            cover_style=CoverStyle.BOLD,
            output_format="pptx",
            description="适用于融资路演、商业计划展示",
        ),
        TemplateInfo(
            template_id="data_report",
            name="数据分析报告",
            document_types=["analysis", "report"],
            audiences=["technical", "executive"],
            industries=["general"],
            importance_levels=["important"],
            cover_style=CoverStyle.MODERN,
            output_format="xlsx",
            description="数据分析报告，含图表和汇总",
        ),
        TemplateInfo(
            template_id="invoice_standard",
            name="标准发票",
            document_types=["invoice"],
            audiences=["external", "client"],
            industries=["general"],
            importance_levels=["normal", "important"],
            cover_style=CoverStyle.MINIMAL,
            output_format="xlsx",
            description="标准发票/收据模板",
        ),
        TemplateInfo(
            template_id="training_manual",
            name="培训手册",
            document_types=["manual"],
            audiences=["internal", "technical"],
            industries=["general"],
            importance_levels=["normal"],
            cover_style=CoverStyle.CREATIVE,
            output_format="docx",
            description="培训手册/操作指南模板",
        ),
        TemplateInfo(
            template_id="certificate_elegant",
            name="荣誉证书",
            document_types=["certificate"],
            audiences=["external"],
            industries=["general"],
            importance_levels=["normal"],
            cover_style=CoverStyle.ELEGANT,
            output_format="pdf",
            description="荣誉证书/授权书模板",
        ),
    ]

    # 封面风格推荐映射
    COVER_STYLE_RECOMMENDATIONS = {
        "report": [CoverStyle.CORPORATE, CoverStyle.MODERN, CoverStyle.CLASSIC],
        "contract": [CoverStyle.CLASSIC, CoverStyle.MINIMAL],
        "proposal": [CoverStyle.TECH, CoverStyle.BOLD, CoverStyle.MODERN],
        "resume": [CoverStyle.MINIMAL, CoverStyle.MODERN],
        "presentation": [CoverStyle.BOLD, CoverStyle.GRADIENT, CoverStyle.CREATIVE],
        "invoice": [CoverStyle.MINIMAL],
        "certificate": [CoverStyle.ELEGANT, CoverStyle.CLASSIC],
        "policy": [CoverStyle.CLASSIC],
        "manual": [CoverStyle.CREATIVE, CoverStyle.TECH],
    }

    def __init__(self, custom_templates_dir: Optional[str] = None):
        self.templates: Dict[str, TemplateInfo] = {}
        self.feedback_history: List[dict] = []
        self.custom_templates_dir = custom_templates_dir

        # 加载内置模板
        for t in self.BUILTIN_TEMPLATES:
            self.templates[t.template_id] = t

        # 加载自定义模板
        if custom_templates_dir:
            self._load_custom_templates(custom_templates_dir)

    def _load_custom_templates(self, dir_path: str):
        """从目录加载自定义模板"""
        path = Path(dir_path)
        if not path.exists():
            return

        for f in path.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    t = TemplateInfo(
                        template_id=data.get("id", f.stem),
                        name=data.get("name", f.stem),
                        document_types=data.get("document_types", []),
                        audiences=data.get("audiences", []),
                        industries=data.get("industries", []),
                        importance_levels=data.get("importance_levels", []),
                        cover_style=CoverStyle(data.get("cover_style", "classic")),
                        output_format=data.get("output_format", "docx"),
                        description=data.get("description", ""),
                        tags=data.get("tags", []),
                        file_path=str(f),
                    )
                    self.templates[t.template_id] = t
            except Exception as e:
                logger.warning(f"加载模板 {f} 失败: {e}")

    def route(self, document_type: str, audience: str = "general",
              industry: str = "general", importance: str = "normal",
              output_format: str = None) -> TemplateMatch:
        """
        智能路由 - 匹配最优模板

        Args:
            document_type: 文档类型
            audience: 目标受众
            industry: 行业
            importance: 重要程度
            output_format: 输出格式

        Returns:
            TemplateMatch 匹配结果
        """
        scores = {}

        for tid, template in self.templates.items():
            score = 0.0
            reasons = []

            # 1. 文档类型匹配 (权重 40%)
            if document_type in template.document_types:
                score += 0.4
                reasons.append(f"文档类型匹配: {document_type}")
            elif any(t in template.document_types for t in ["general", document_type.split("_")[0]]):
                score += 0.2
                reasons.append(f"文档类型部分匹配")

            # 2. 受众匹配 (权重 20%)
            if audience in template.audiences:
                score += 0.2
                reasons.append(f"受众匹配: {audience}")
            elif "general" in template.audiences:
                score += 0.1

            # 3. 行业匹配 (权重 15%)
            if industry in template.industries:
                score += 0.15
                reasons.append(f"行业匹配: {industry}")
            elif "general" in template.industries:
                score += 0.075

            # 4. 重要程度匹配 (权重 10%)
            if importance in template.importance_levels:
                score += 0.1
                reasons.append(f"重要程度匹配")

            # 5. 格式匹配
            if output_format and template.output_format == output_format:
                score += 0.05

            # 6. 使用反馈 (权重 15%)
            feedback_score = self._get_feedback_score(tid)
            score += feedback_score * 0.15

            scores[tid] = (score, reasons)

        if not scores:
            return TemplateMatch(
                template_id="corp_report_v1",
                score=0.0,
                reasons=["无匹配模板，使用默认"],
            )

        # 选择最高分
        best_tid = max(scores, key=lambda x: scores[x][0])
        best_score, best_reasons = scores[best_tid]

        # 推荐封面风格
        cover_style = self._recommend_cover_style(document_type)

        return TemplateMatch(
            template_id=best_tid,
            score=best_score,
            reasons=best_reasons,
            cover_style=cover_style,
            confidence=min(best_score, 1.0),
        )

    def _recommend_cover_style(self, document_type: str) -> CoverStyle:
        """推荐封面风格"""
        styles = self.COVER_STYLE_RECOMMENDATIONS.get(document_type, [CoverStyle.CLASSIC])
        return styles[0]

    def _get_feedback_score(self, template_id: str) -> float:
        """获取模板的使用反馈分数"""
        template = self.templates.get(template_id)
        if not template or template.usage_count == 0:
            return 0.5  # 无反馈时给中等分

        # 评分 × 使用频率归一化
        rating_score = template.rating / 5.0 if template.rating > 0 else 0.5
        usage_score = min(template.usage_count / 100.0, 1.0)

        return rating_score * 0.7 + usage_score * 0.3

    def record_feedback(self, template_id: str, rating: float, used: bool = True):
        """记录使用反馈"""
        if template_id in self.templates:
            t = self.templates[template_id]
            if used:
                t.usage_count += 1
            # 更新评分 (加权平均)
            if t.rating == 0:
                t.rating = rating
            else:
                t.rating = t.rating * 0.8 + rating * 0.2

        self.feedback_history.append({
            "template_id": template_id,
            "rating": rating,
            "used": used,
            "timestamp": datetime.now().isoformat(),
        })

    def list_templates(self, document_type: str = None) -> List[dict]:
        """列出可用模板"""
        results = []
        for tid, t in self.templates.items():
            if document_type and document_type not in t.document_types:
                continue
            results.append({
                "id": tid,
                "name": t.name,
                "types": t.document_types,
                "format": t.output_format,
                "cover_style": t.cover_style.value,
                "usage_count": t.usage_count,
                "rating": round(t.rating, 1),
            })
        return results
