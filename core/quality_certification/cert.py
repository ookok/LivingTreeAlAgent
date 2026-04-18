"""
智能创作与专业审核增强系统 - 质量认证系统

质量评估、认证、信任体系
"""

import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class CertLevel(Enum):
    """认证级别"""
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    DIAMOND = "diamond"


class TrustLevel(Enum):
    """信任级别"""
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class QualityMetrics:
    """质量指标"""
    accuracy: float = 0.0      # 准确性
    completeness: float = 0.0   # 完整性
    consistency: float = 0.0  # 一致性
    clarity: float = 0.0       # 清晰度
    professionalism: float = 0.0  # 专业性
    innovation: float = 0.0    # 创新性
    
    @property
    def overall(self) -> float:
        weights = {"accuracy": 0.25, "completeness": 0.2, "consistency": 0.15, 
                   "clarity": 0.15, "professionalism": 0.15, "innovation": 0.1}
        return sum(getattr(self, k) * v for k, v in weights.items())


@dataclass
class QualityReport:
    """质量报告"""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    
    # 评分
    metrics: QualityMetrics = field(default_factory=QualityMetrics)
    overall_score: float = 0.0
    
    # 认证
    cert_level: CertLevel = CertLevel.BRONZE
    certified: bool = False
    certified_by: List[str] = field(default_factory=list)
    certified_at: Optional[datetime] = None
    
    # 有效期
    valid_until: Optional[datetime] = None
    
    # 详细信息
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    # 元数据
    reviewer_ids: List[str] = field(default_factory=list)
    review_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class TrustProfile:
    """信任档案"""
    user_id: str = ""
    
    # 信任分数
    trust_score: float = 50.0  # 0-100
    trust_level: TrustLevel = TrustLevel.UNKNOWN
    
    # 维度
    expertise: float = 50.0   # 专业能力
    reliability: float = 50.0  # 可靠性
    activity: float = 50.0     # 活跃度
    quality: float = 50.0      # 质量
    collaboration: float = 50.0  # 协作
    
    # 统计
    total_contributions: int = 0
    total_reviews: int = 0
    avg_quality_score: float = 0.0
    success_rate: float = 0.0  # 审核通过率
    
    # 历史
    badges: List[str] = field(default_factory=list)
    penalties: int = 0
    warnings: int = 0
    
    # 时间
    registered_at: datetime = field(default_factory=datetime.now)
    last_active: Optional[datetime] = None


@dataclass
class CertificationBadge:
    """认证徽章"""
    badge_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    level: CertLevel = CertLevel.BRONZE
    icon_url: str = ""
    criteria: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReviewChain:
    """审核链（溯源）"""
    chain_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    
    # 链信息
    entries: List[Dict] = field(default_factory=list)  # {action, user, time, hash}
    genesis_hash: str = ""
    current_hash: str = ""
    
    created_at: datetime = field(default_factory=datetime.now)


class QualityAssessment:
    """质量评估"""
    
    def __init__(self):
        self.assessment_rules = self._load_rules()
    
    def _load_rules(self) -> Dict[str, Any]:
        """加载评估规则"""
        return {
            "accuracy": {
                "weight": 0.25,
                "checks": ["事实准确性", "数据准确性", "引用准确性"]
            },
            "completeness": {
                "weight": 0.2,
                "checks": ["内容完整", "结构完整", "要素齐全"]
            },
            "consistency": {
                "weight": 0.15,
                "checks": ["逻辑一致", "格式一致", "术语一致"]
            },
            "clarity": {
                "weight": 0.15,
                "checks": ["表达清晰", "结构清晰", "易于理解"]
            },
            "professionalism": {
                "weight": 0.15,
                "checks": ["专业术语", "规范格式", "符合标准"]
            },
            "innovation": {
                "weight": 0.1,
                "checks": ["观点新颖", "方法创新", "见解独到"]
            }
        }
    
    def assess(self, document: Dict, review_result: Any = None) -> QualityMetrics:
        """评估质量"""
        metrics = QualityMetrics()
        
        content = document.get("content", "")
        title = document.get("title", "")
        
        # 准确性评估
        metrics.accuracy = self._assess_accuracy(content, review_result)
        
        # 完整性评估
        metrics.completeness = self._assess_completeness(content, title)
        
        # 一致性评估
        metrics.consistency = self._assess_consistency(content)
        
        # 清晰度评估
        metrics.clarity = self._assess_clarity(content)
        
        # 专业性评估
        metrics.professionalism = self._assess_professionalism(content)
        
        # 创新性评估
        metrics.innovation = self._assess_innovation(content)
        
        return metrics
    
    def _assess_accuracy(self, content: str, review_result: Any) -> float:
        """评估准确性"""
        if review_result:
            if hasattr(review_result, 'critical_count'):
                return 100 - review_result.critical_count * 20 - review_result.major_count * 10
            return 100
        return 75.0
    
    def _assess_completeness(self, content: str, title: str) -> float:
        """评估完整性"""
        score = 60.0
        if len(content) > 500: score += 10
        if len(content) > 1000: score += 10
        if title: score += 10
        if "\n\n" in content: score += 10
        return min(100, score)
    
    def _assess_consistency(self, content: str) -> float:
        """评估一致性"""
        return 80.0  # 简化实现
    
    def _assess_clarity(self, content: str) -> float:
        """评估清晰度"""
        avg_sentence_len = len(content) / max(len(content.split("。")), 1)
        if avg_sentence_len < 30:
            return 85.0
        elif avg_sentence_len < 50:
            return 75.0
        return 65.0
    
    def _assess_professionalism(self, content: str) -> float:
        """评估专业性"""
        professional_markers = ["根据", "依据", "按照", "规范", "标准", "规定", "要求"]
        score = 50.0
        for marker in professional_markers:
            if marker in content:
                score += 5
        return min(100, score)
    
    def _assess_innovation(self, content: str) -> float:
        """评估创新性"""
        innovation_markers = ["创新", "首创", "突破", "独特", "新颖"]
        score = 50.0
        for marker in innovation_markers:
            if marker in content:
                score += 10
        return min(100, score)


class QualityCertificationSystem:
    """质量认证系统"""
    
    def __init__(self):
        self.assessment = QualityAssessment()
        self.certifications: Dict[str, QualityReport] = {}  # document_id -> report
        self.trust_profiles: Dict[str, TrustProfile] = {}  # user_id -> profile
        self.badges = self._init_badges()
        self.review_chains: Dict[str, ReviewChain] = {}  # document_id -> chain
    
    def _init_badges(self) -> Dict[str, CertificationBadge]:
        """初始化徽章"""
        return {
            "first_review": CertificationBadge(name="初审员", description="完成首次审核", level=CertLevel.BRONZE),
            "quality_master": CertificationBadge(name="质量大师", description="10次审核通过率>90%", level=CertLevel.SILVER),
            "expert": CertificationBadge(name="专家", description="专业领域贡献突出", level=CertLevel.GOLD),
            "top_contributor": CertificationBadge(name="最佳贡献者", description="月度贡献榜首", level=CertLevel.PLATINUM),
        }
    
    def certify(self, document: Dict, creator_id: str, review_result: Any = None) -> QualityReport:
        """认证文档"""
        doc_id = document.get("id", str(uuid.uuid4()))
        
        # 评估质量
        metrics = self.assessment.assess(document, review_result)
        
        # 确定认证级别
        score = metrics.overall
        if score >= 95:
            level = CertLevel.DIAMOND
        elif score >= 90:
            level = CertLevel.PLATINUM
        elif score >= 80:
            level = CertLevel.GOLD
        elif score >= 70:
            level = CertLevel.SILVER
        else:
            level = CertLevel.BRONZE
        
        # 创建报告
        report = QualityReport(
            document_id=doc_id,
            metrics=metrics,
            overall_score=score,
            cert_level=level,
            certified=score >= 70,
            certified_by=["system"],
            certified_at=datetime.now() if score >= 70 else None,
            valid_until=datetime.now() + timedelta(days=365) if score >= 70 else None
        )
        
        # 添加优点和缺点
        self._analyze_strengths_weaknesses(report, metrics)
        
        self.certifications[doc_id] = report
        
        # 更新创作者信任
        if creator_id:
            self._update_trust_profile(creator_id, score)
        
        # 创建溯源链
        self._create_review_chain(doc_id, creator_id, report)
        
        return report
    
    def _analyze_strengths_weaknesses(self, report: QualityReport, metrics: QualityMetrics):
        """分析优缺点"""
        # 优点
        if metrics.accuracy >= 85:
            report.strengths.append("内容准确可靠")
        if metrics.completeness >= 85:
            report.strengths.append("内容完整详尽")
        if metrics.professionalism >= 85:
            report.strengths.append("专业性突出")
        
        # 缺点
        if metrics.accuracy < 70:
            report.weaknesses.append("准确性有待提高")
        if metrics.completeness < 70:
            report.weaknesses.append("内容不够完整")
        if metrics.clarity < 70:
            report.weaknesses.append("表达不够清晰")
        
        # 建议
        if metrics.innovation < 70:
            report.recommendations.append("可增加更多创新性观点")
        if metrics.consistency < 70:
            report.recommendations.append("建议统一文章格式")
    
    def _update_trust_profile(self, user_id: str, quality_score: float):
        """更新信任档案"""
        if user_id not in self.trust_profiles:
            self.trust_profiles[user_id] = TrustProfile(user_id=user_id)
        
        profile = self.trust_profiles[user_id]
        profile.total_contributions += 1
        profile.last_active = datetime.now()
        
        # 更新平均质量
        total = profile.avg_quality_score * (profile.total_contributions - 1) + quality_score
        profile.avg_quality_score = total / profile.total_contributions
        
        # 更新信任分数
        profile.quality = profile.avg_quality_score
        profile.trust_score = (profile.expertise + profile.reliability + profile.activity + 
                              profile.quality + profile.collaboration) / 5
        
        # 更新信任级别
        if profile.trust_score >= 90:
            profile.trust_level = TrustLevel.VERY_HIGH
        elif profile.trust_score >= 75:
            profile.trust_level = TrustLevel.HIGH
        elif profile.trust_score >= 50:
            profile.trust_level = TrustLevel.MEDIUM
        else:
            profile.trust_level = TrustLevel.LOW
        
        # 授予徽章
        self._check_and_award_badges(profile)
    
    def _check_and_award_badges(self, profile: TrustProfile):
        """检查并授予徽章"""
        if profile.total_contributions >= 1 and "first_review" not in profile.badges:
            profile.badges.append("first_review")
        
        if profile.total_contributions >= 10 and profile.avg_quality_score >= 90:
            if "quality_master" not in profile.badges:
                profile.badges.append("quality_master")
    
    def _create_review_chain(self, doc_id: str, creator_id: str, report: QualityReport):
        """创建审核链"""
        chain = ReviewChain(document_id=doc_id)
        chain.genesis_hash = hashlib.sha256(f"{doc_id}{creator_id}".encode()).hexdigest()
        
        chain.entries.append({
            "action": "create",
            "user": creator_id,
            "time": datetime.now().isoformat(),
            "hash": chain.genesis_hash
        })
        
        chain.current_hash = chain.genesis_hash
        self.review_chains[doc_id] = chain
    
    def get_certification(self, document_id: str) -> Optional[QualityReport]:
        """获取认证"""
        return self.certifications.get(document_id)
    
    def get_trust_profile(self, user_id: str) -> TrustProfile:
        """获取信任档案"""
        if user_id not in self.trust_profiles:
            self.trust_profiles[user_id] = TrustProfile(user_id=user_id)
        return self.trust_profiles[user_id]
    
    def verify_chain(self, document_id: str) -> bool:
        """验证溯源链"""
        chain = self.review_chains.get(document_id)
        if not chain:
            return False
        
        # 验证哈希链
        expected_hash = chain.genesis_hash
        for entry in chain.entries:
            expected_hash = hashlib.sha256(
                f"{expected_hash}{entry['user']}{entry['time']}".encode()
            ).hexdigest()
        
        return expected_hash == chain.current_hash
    
    def get_statistics(self) -> Dict[str, Any]:
        """统计"""
        certs = list(self.certifications.values())
        
        return {
            "total_certifications": len(certs),
            "certified_count": len([c for c in certs if c.certified]),
            "avg_score": sum(c.overall_score for c in certs) / max(len(certs), 1),
            "level_distribution": {
                "diamond": len([c for c in certs if c.cert_level == CertLevel.DIAMOND]),
                "platinum": len([c for c in certs if c.cert_level == CertLevel.PLATINUM]),
                "gold": len([c for c in certs if c.cert_level == CertLevel.GOLD]),
                "silver": len([c for c in certs if c.cert_level == CertLevel.SILVER]),
                "bronze": len([c for c in certs if c.cert_level == CertLevel.BRONZE]),
            },
            "trust_stats": {
                "total_users": len(self.trust_profiles),
                "avg_trust": sum(p.trust_score for p in self.trust_profiles.values()) / max(len(self.trust_profiles), 1)
            }
        }


def create_quality_certification_system() -> QualityCertificationSystem:
    return QualityCertificationSystem()
