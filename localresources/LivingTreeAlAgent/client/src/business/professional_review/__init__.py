"""
专业审核增强系统 - 统一调度器
"""

from .models import (
    ReviewDomain, ReviewLevel, ReviewStatus, IssueSeverity,
    Document, ReviewResult, ReviewIssue, ReviewOpinion,
    QualityLevel, QualityCertification, SystemStats
)
from .engine import (
    ReviewEnginePool, BaseReviewEngine,
    EIAReviewEngine, FinancialReviewEngine, LegalReviewEngine,
    TechnicalReviewEngine, GeneralReviewEngine,
    create_engine_pool
)


class ProfessionalReviewSystem:
    """专业审核增强系统"""
    
    def __init__(self):
        self.engine_pool = create_engine_pool()
        self.documents = {}
        self.review_history = []
        self.certifications = {}
    
    def create_document(self, title: str, content: str, 
                       domain: ReviewDomain = ReviewDomain.GENERAL,
                       author: str = "") -> Document:
        """创建文档"""
        doc = Document(
            title=title,
            content=content,
            domain=domain,
            author=author
        )
        self.documents[doc.doc_id] = doc
        return doc
    
    def review(self, doc_id: str, level: ReviewLevel = ReviewLevel.AUTO_PREVIEW) -> ReviewResult:
        """审核文档"""
        doc = self.documents.get(doc_id)
        if not doc:
            raise ValueError(f"Document {doc_id} not found")
        
        result = self.engine_pool.review_document(doc, level)
        doc.review_result = result
        
        self.review_history.append({
            "doc_id": doc_id,
            "result_id": result.result_id,
            "timestamp": result.completed_at,
            "score": result.overall_score
        })
        
        return result
    
    def multi_review(self, doc_id: str, domains: list[ReviewDomain]) -> list[ReviewResult]:
        """多领域审核"""
        doc = self.documents.get(doc_id)
        if not doc:
            raise ValueError(f"Document {doc_id} not found")
        
        return self.engine_pool.review_multi_engine(doc, domains)
    
    def generate_opinion(self, result: ReviewResult, reviewer_id: str = "system") -> ReviewOpinion:
        """生成审核意见"""
        opinion = ReviewOpinion(
            reviewer_id=reviewer_id,
            reviewer_name="System Reviewer"
        )
        
        # 摘要
        opinion.summary = f"文档总体评分为{result.overall_score:.1f}分"
        if result.overall_score >= 90:
            opinion.summary += "，质量优秀。"
        elif result.overall_score >= 75:
            opinion.summary += "，质量良好。"
        elif result.overall_score >= 60:
            opinion.summary += "，质量合格，需小幅修改。"
        else:
            opinion.summary += "，质量不合格，需要大幅修改。"
        
        # 判定
        opinion.verdict = "通过" if result.overall_score >= 60 else "不通过"
        
        # 关键发现
        if result.critical_count > 0:
            opinion.key_findings.append(f"发现{result.critical_count}个严重问题")
        if result.major_count > 0:
            opinion.key_findings.append(f"发现{result.major_count}个主要问题")
        if result.minor_count > 0:
            opinion.key_findings.append(f"发现{result.minor_count}个次要问题")
        
        # 优点
        if result.overall_score >= 75:
            opinion.strengths.append("文档结构清晰")
            opinion.strengths.append("内容较为完整")
        
        # 改进点
        if result.issues:
            for issue in result.issues[:5]:
                if issue.severity in [IssueSeverity.CRITICAL, IssueSeverity.MAJOR]:
                    opinion.improvements.append(f"{issue.title}: {issue.suggestion}")
        
        return opinion
    
    def get_statistics(self) -> SystemStats:
        """获取系统统计"""
        stats = SystemStats()
        
        stats.total_documents = len(self.documents)
        stats.total_reviews = len(self.review_history)
        
        if self.review_history:
            scores = [h["score"] for h in self.review_history]
            stats.avg_score = sum(scores) / len(scores)
            stats.pass_rate = len([s for s in scores if s >= 60]) / len(scores) * 100
        
        return stats
    
    def get_quality_distribution(self) -> dict:
        """获取质量分布"""
        distribution = {"excellent": 0, "good": 0, "acceptable": 0, "poor": 0}
        
        for doc in self.documents.values():
            if doc.review_result:
                level = doc.review_result.quality_level.value
                distribution[level] = distribution.get(level, 0) + 1
        
        return distribution


def create_professional_review_system() -> ProfessionalReviewSystem:
    """创建专业审核系统"""
    return ProfessionalReviewSystem()
