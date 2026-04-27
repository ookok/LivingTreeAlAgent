"""
专家路由层 - ExpertRouter

智能判断何时使用专家模型 vs 通用模型。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum


class QueryDomain(Enum):
    GENERAL = "通用"
    FINANCE = "金融"
    TECHNOLOGY = "技术"
    LAW = "法律"
    MEDICAL = "医疗"
    CODE = "代码"

    @classmethod
    def from_name(cls, name: str):
        """从名称查找（支持中文别名）"""
        # 中文别名映射
        aliases = {"金融": "FINANCE", "技术": "TECHNOLOGY", "法律": "LAW", "医疗": "MEDICAL", "代码": "CODE", "通用": "GENERAL"}
        if name in aliases:
            return cls[aliases[name]]
        return cls[name]


class ComplexityLevel(Enum):
    SIMPLE = 1
    MODERATE = 2
    COMPLEX = 3
    EXPERT = 4


class RouteStrategy(Enum):
    EXPERT_MODEL = "expert"
    L4_MODEL = "l4"
    HYBRID = "hybrid"


@dataclass
class RoutingDecision:
    strategy: RouteStrategy
    primary_domain: QueryDomain
    complexity: ComplexityLevel
    confidence: float
    expert_model: Optional[str]
    reasoning: str
    hints: List[str] = field(default_factory=list)


class QueryClassifier:
    DOMAIN_KEYWORDS = {
        QueryDomain.FINANCE: ["股票", "债券", "基金", "投资", "市值", "市盈率", "股价", "涨跌", "ipo", "估值", "财报", "营收", "利润"],
        QueryDomain.TECHNOLOGY: ["代码", "bug", "api", "架构", "性能", "部署", "服务器", "数据库", "缓存", "队列", "算法", "安全"],
        QueryDomain.LAW: ["合同", "协议", "条款", "法律", "法规", "合规", "侵权", "违约", "诉讼", "权利", "义务"],
        QueryDomain.MEDICAL: ["症状", "诊断", "治疗", "药物", "检查", "血压", "血糖", "心率", "ct", "mri", "医生", "医院"],
        QueryDomain.CODE: ["python", "javascript", "java", "函数", "class", "import", "def", "function", "method", "sql", "git"],
    }

    COMPLEXITY_WORDS = {
        ComplexityLevel.SIMPLE: ["是什么", "什么是", "定义", "介绍", "告诉我"],
        ComplexityLevel.MODERATE: ["分析", "比较", "区别", "如何", "怎么", "评估", "建议"],
        ComplexityLevel.COMPLEX: ["深入", "详细", "全面", "综合", "多维度", "系统性"],
        ComplexityLevel.EXPERT: ["专家", "资深", "学术", "研究", "框架", "架构设计", "体系"],
    }

    def classify_domain(self, query: str) -> Tuple[QueryDomain, float]:
        query_lower = query.lower()
        scores = {}
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            score = sum(1 for k in keywords if k.lower() in query_lower)
            if score > 0:
                scores[domain] = score

        if not scores:
            return QueryDomain.GENERAL, 0.5
        max_score = max(scores.values())
        primary = max(scores, key=scores.get)
        return primary, min(scores[primary] / max_score, 1.0)

    def assess_complexity(self, query: str) -> Tuple[ComplexityLevel, float]:
        query_lower = query.lower()
        for level, words in reversed(list(self.COMPLEXITY_WORDS.items())):
            if any(w in query_lower for w in words):
                return level, 0.8
        return ComplexityLevel.MODERATE, 0.6


class ExpertRouter:
    def __init__(self, classifier: Optional[QueryClassifier] = None):
        self.classifier = classifier or QueryClassifier()
        self.expert_models: Dict[QueryDomain, List[Dict]] = {}

    def register_expert(self, domain: QueryDomain, model_id: str, model_path: str, priority: int = 0):
        if domain not in self.expert_models:
            self.expert_models[domain] = []
        self.expert_models[domain].append({"model_id": model_id, "model_path": model_path, "priority": priority})
        self.expert_models[domain].sort(key=lambda x: -x["priority"])

    def decide(self, query: str, force_domain: Optional[QueryDomain] = None) -> RoutingDecision:
        primary_domain, domain_conf = self.classifier.classify_domain(query) if not force_domain else (force_domain, 1.0)
        complexity, complexity_conf = self.classifier.assess_complexity(query)
        has_expert = primary_domain in self.expert_models and len(self.expert_models[primary_domain]) > 0

        if not has_expert:
            return RoutingDecision(RouteStrategy.L4_MODEL, primary_domain, complexity, domain_conf, None, "无可用专家模型，使用L4")

        if complexity == ComplexityLevel.SIMPLE and domain_conf > 0.7:
            expert = self.expert_models[primary_domain][-1]
            return RoutingDecision(RouteStrategy.EXPERT_MODEL, primary_domain, complexity, domain_conf, expert["model_id"], "简单任务使用专家模型", ["快速响应"])

        if complexity == ComplexityLevel.EXPERT:
            return RoutingDecision(RouteStrategy.L4_MODEL, primary_domain, complexity, domain_conf, None, "专家级任务使用L4")

        if complexity in [ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX] and has_expert:
            expert = self.expert_models[primary_domain][len(self.expert_models[primary_domain]) // 2]
            return RoutingDecision(RouteStrategy.HYBRID, primary_domain, complexity, domain_conf, expert["model_id"], "混合模式：专家+L4", ["专家结构+大模型细节"])

        return RoutingDecision(RouteStrategy.L4_MODEL, primary_domain, complexity, domain_conf, None, "默认使用L4")


def quick_route(query: str) -> RoutingDecision:
    router = ExpertRouter()
    return router.decide(query)
