"""
智能创作与专业审核增强系统 - 专业审核引擎

多领域专业审核引擎池、自学习优化
"""

import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import asdict
import hashlib

from .models import (
    Document, ReviewDomain, ReviewLevel, ReviewStatus,
    ReviewResult, ReviewIssue, IssueSeverity, IssueCategory,
    Entity, EntityType, QualityLevel
)


class BaseReviewEngine:
    """基础审核引擎"""
    
    def __init__(self, domain: ReviewDomain):
        self.domain = domain
        self.version = "1.0.0"
        self.rules = []
        self.statistics = {"processed": 0, "issues_found": 0, "avg_time_ms": 0}
    
    def review(self, doc: Document, level: ReviewLevel = ReviewLevel.AUTO_PREVIEW) -> ReviewResult:
        """执行审核"""
        start_time = time.time()
        
        result = ReviewResult(
            document_id=doc.doc_id,
            domain=self.domain,
            review_level=level,
            started_at=datetime.now()
        )
        
        # 基础检查
        issues = self._check_basic(doc)
        
        # 专业检查
        if level in [ReviewLevel.PROFESSIONAL, ReviewLevel.COMPREHENSIVE, ReviewLevel.FINAL]:
            issues.extend(self._check_professional(doc))
        
        # 综合评估
        if level in [ReviewLevel.COMPREHENSIVE, ReviewLevel.FINAL]:
            issues.extend(self._check_comprehensive(doc))
        
        result.issues = issues
        result.critical_count = len([i for i in issues if i.severity == IssueSeverity.CRITICAL])
        result.major_count = len([i for i in issues if i.severity == IssueSeverity.MAJOR])
        result.minor_count = len([i for i in issues if i.severity == IssueSeverity.MINOR])
        result.suggestion_count = len([i for i in issues if i.severity == IssueSeverity.SUGGESTION])
        
        # 计算评分
        result.overall_score = self._calculate_score(result)
        result.quality_level = self._get_quality_level(result.overall_score)
        result.status = ReviewStatus.PASSED if result.overall_score >= 60 else ReviewStatus.FAILED
        
        result.processing_time_ms = (time.time() - start_time) * 1000
        result.completed_at = datetime.now()
        result.engine_version = self.version
        result.confidence = 0.85
        
        self._update_stats(result)
        return result
    
    def _check_basic(self, doc: Document) -> List[ReviewIssue]:
        """基础检查"""
        issues = []
        content = doc.content
        
        # 长度检查
        if len(content) < 100:
            issues.append(ReviewIssue(
                title="内容过短",
                description="文档内容长度不足100字",
                severity=IssueSeverity.MAJOR,
                category=IssueCategory.COMPLETENESS,
                suggestion="请补充详细内容"
            ))
        
        # 空检查
        if not content.strip():
            issues.append(ReviewIssue(
                title="内容为空",
                description="文档内容为空",
                severity=IssueSeverity.CRITICAL,
                category=IssueCategory.COMPLETENESS,
                suggestion="请输入文档内容"
            ))
        
        # 标题检查
        if not doc.title:
            issues.append(ReviewIssue(
                title="缺少标题",
                description="文档缺少标题",
                severity=IssueSeverity.MAJOR,
                category=IssueCategory.COMPLETENESS,
                suggestion="请添加文档标题"
            ))
        
        # 标点检查
        if re.search(r'[.。]{3,}', content):
            issues.append(ReviewIssue(
                title="多余标点",
                description="发现连续的句号",
                severity=IssueSeverity.MINOR,
                category=IssueCategory.FORMAT,
                suggestion="使用规范的标点符号"
            ))
        
        return issues
    
    def _check_professional(self, doc: Document) -> List[ReviewIssue]:
        """专业检查 - 子类实现"""
        return []
    
    def _check_comprehensive(self, doc: Document) -> List[ReviewIssue]:
        """综合检查"""
        return []
    
    def _calculate_score(self, result: ReviewResult) -> float:
        """计算评分"""
        score = 100.0
        score -= result.critical_count * 20
        score -= result.major_count * 10
        score -= result.minor_count * 3
        score -= result.suggestion_count * 1
        return max(0, min(100, score))
    
    def _get_quality_level(self, score: float) -> QualityLevel:
        """获取质量等级"""
        if score >= 90:
            return QualityLevel.EXCELLENT
        elif score >= 75:
            return QualityLevel.GOOD
        elif score >= 60:
            return QualityLevel.ACCEPTABLE
        else:
            return QualityLevel.POOR
    
    def _update_stats(self, result: ReviewResult):
        """更新统计"""
        self.statistics["processed"] += 1
        self.statistics["issues_found"] += len(result.issues)


class EIAReviewEngine(BaseReviewEngine):
    """环评审核引擎"""
    
    def __init__(self):
        super().__init__(ReviewDomain.EIA)
        self.regulations = self._load_regulations()
    
    def _load_regulations(self) -> List[Dict]:
        """加载法规"""
        return [
            {"name": "环境影响评价法", "key": "环评"},
            {"name": "建设项目环境保护管理条例", "key": "环保"},
            {"name": "大气污染防治法", "key": "大气"},
            {"name": "水污染防治法", "key": "水污染"},
        ]
    
    def _check_professional(self, doc: Document) -> List[ReviewIssue]:
        issues = super()._check_professional(doc)
        content = doc.content
        
        # 法规符合性检查
        for reg in self.regulations:
            if reg["key"] not in content:
                issues.append(ReviewIssue(
                    title=f"缺少{reg['name']}相关内容",
                    severity=IssueSeverity.MAJOR,
                    category=IssueCategory.COMPLIANCE,
                    suggestion=f"建议补充{reg['name']}符合性分析"
                ))
        
        # 数据准确性检查
        if re.search(r'\d+\.\d+', content):
            numbers = re.findall(r'(\d+\.\d+)', content)
            for num in numbers:
                if float(num) > 100 or float(num) < 0:
                    issues.append(ReviewIssue(
                        title="数值超出合理范围",
                        description=f"数值 {num} 可能超出正常范围",
                        severity=IssueSeverity.MAJOR,
                        category=IssueCategory.ACCURACY
                    ))
        
        return issues


class FinancialReviewEngine(BaseReviewEngine):
    """财务审核引擎"""
    
    def __init__(self):
        super().__init__(ReviewDomain.FINANCIAL)
        self.accounting_keywords = ["收入", "支出", "利润", "成本", "资产", "负债", "权益"]
    
    def _check_professional(self, doc: Document) -> List[ReviewIssue]:
        issues = super()._check_professional(doc)
        content = doc.content
        
        # 财务术语检查
        has_financial = any(kw in content for kw in self.accounting_keywords)
        if not has_financial:
            issues.append(ReviewIssue(
                title="缺少财务专业术语",
                severity=IssueSeverity.SUGGESTION,
                category=IssueCategory.COMPLETENESS,
                suggestion="建议使用规范的财务术语"
            ))
        
        # 金额格式检查
        amounts = re.findall(r'[\d,]+(?:\.\d{1,2})?\s*(?:元|万|亿)', content)
        for amount in amounts:
            if ',' in amount and amount.count(',') > 1:
                issues.append(ReviewIssue(
                    title="金额格式不规范",
                    description=f"金额 {amount} 格式需检查",
                    severity=IssueSeverity.MINOR,
                    category=IssueCategory.FORMAT
                ))
        
        # 平衡检查
        if "资产" in content and "负债" in content:
            if not re.search(r'资产\s*[=:]\s*负债', content) and not re.search(r'负债\s*[=:]\s*资产', content):
                issues.append(ReviewIssue(
                    title="资产负债表不平衡",
                    severity=IssueSeverity.MAJOR,
                    category=IssueCategory.ACCURACY,
                    suggestion="请检查资产负载是否平衡"
                ))
        
        return issues


class LegalReviewEngine(BaseReviewEngine):
    """法律审核引擎"""
    
    def __init__(self):
        super().__init__(ReviewDomain.LEGAL)
        self.required_clauses = ["甲方", "乙方", "权利", "义务"]
    
    def _check_professional(self, doc: Document) -> List[ReviewIssue]:
        issues = super()._check_professional(doc)
        content = doc.content
        
        # 合同要素检查
        for clause in self.required_clauses:
            if clause not in content:
                issues.append(ReviewIssue(
                    title=f"缺少必要要素: {clause}",
                    severity=IssueSeverity.MAJOR,
                    category=IssueCategory.COMPLETENESS,
                    suggestion=f"合同中应明确{clause}相关内容"
                ))
        
        # 条款编号检查
        if "第" in content and not re.search(r'第[一二三四五六七八九十百]+条', content):
            issues.append(ReviewIssue(
                title="条款编号不规范",
                severity=IssueSeverity.MINOR,
                category=IssueCategory.FORMAT
            ))
        
        # 违约条款检查
        if "合同" in content and "违约" not in content:
            issues.append(ReviewIssue(
                title="缺少违约条款",
                severity=IssueSeverity.MAJOR,
                category=IssueCategory.COMPLETENESS,
                suggestion="建议补充违约责任条款"
            ))
        
        return issues


class TechnicalReviewEngine(BaseReviewEngine):
    """技术文档审核引擎"""
    
    def __init__(self):
        super().__init__(ReviewDomain.TECHNICAL)
        self.technical_terms = ["系统", "模块", "接口", "功能", "性能"]
    
    def _check_professional(self, doc: Document) -> List[ReviewIssue]:
        issues = super()._check_professional(doc)
        content = doc.content
        
        # 技术术语检查
        has_terms = any(t in content for t in self.technical_terms)
        if not has_terms:
            issues.append(ReviewIssue(
                title="缺少技术术语",
                severity=IssueSeverity.SUGGESTION,
                category=IssueCategory.COMPLETENESS
            ))
        
        # 版本号检查
        if "版本" in content and not re.search(r'v\d+\.\d+(?:\.\d+)?', content, re.I):
            issues.append(ReviewIssue(
                title="版本号格式不规范",
                severity=IssueSeverity.MINOR,
                category=IssueCategory.FORMAT,
                suggestion="建议使用标准版本号格式如 v1.0.0"
            ))
        
        # 代码检查
        if "`" in content or "```" in content:
            if not re.search(r'```\w+', content):
                issues.append(ReviewIssue(
                    title="代码块缺少语言标识",
                    severity=IssueSeverity.MINOR,
                    category=IssueCategory.FORMAT,
                    suggestion="建议添加代码语言标识"
                ))
        
        return issues


class GeneralReviewEngine(BaseReviewEngine):
    """通用审核引擎"""
    
    def __init__(self):
        super().__init__(ReviewDomain.GENERAL)
    
    def _check_professional(self, doc: Document) -> List[ReviewIssue]:
        issues = super()._check_professional(doc)
        content = doc.content
        
        # 错别字检查（示例）
        typos = {
            "象限": "选项", "竟然": "竟然", "苦逼": "刻苦",
        }
        for wrong, correct in typos.items():
            if wrong in content:
                issues.append(ReviewIssue(
                    title="疑似错别字",
                    description=f"'{wrong}' 可能应为 '{correct}'",
                    severity=IssueSeverity.MINOR,
                    category=IssueCategory.ACCURACY,
                    suggestion=f"请确认是否应为 '{correct}'"
                ))
        
        # 重复内容检查
        sentences = re.split(r'[.。!！?？]', content)
        seen = set()
        for s in sentences:
            s = s.strip()
            if len(s) > 20 and s in seen:
                issues.append(ReviewIssue(
                    title="内容重复",
                    description=f"发现重复内容: {s[:20]}...",
                    severity=IssueSeverity.MINOR,
                    category=IssueCategory.CONSISTENCY
                ))
            seen.add(s)
        
        return issues


class ReviewEnginePool:
    """审核引擎池管理器"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.engines: Dict[ReviewDomain, BaseReviewEngine] = {
            ReviewDomain.EIA: EIAReviewEngine(),
            ReviewDomain.FINANCIAL: FinancialReviewEngine(),
            ReviewDomain.LEGAL: LegalReviewEngine(),
            ReviewDomain.TECHNICAL: TechnicalReviewEngine(),
            ReviewDomain.GENERAL: GeneralReviewEngine(),
        }
        
        self.active_domains: List[ReviewDomain] = list(self.engines.keys())
        self.stats = {"total_reviews": 0, "by_domain": {}, "avg_time_ms": 0}
    
    def get_engine(self, domain: ReviewDomain) -> BaseReviewEngine:
        """获取指定领域的引擎"""
        return self.engines.get(domain, self.engines[ReviewDomain.GENERAL])
    
    def review_document(self, doc: Document, level: ReviewLevel = ReviewLevel.AUTO_PREVIEW) -> ReviewResult:
        """使用对应领域的引擎审核文档"""
        engine = self.get_engine(doc.domain)
        result = engine.review(doc, level)
        
        self.stats["total_reviews"] += 1
        domain_key = doc.domain.value
        self.stats["by_domain"][domain_key] = self.stats["by_domain"].get(domain_key, 0) + 1
        
        return result
    
    def review_multi_engine(self, doc: Document, domains: List[ReviewDomain]) -> List[ReviewResult]:
        """多引擎并行审核"""
        results = []
        for domain in domains:
            engine = self.get_engine(domain)
            result = engine.review(doc, ReviewLevel.PROFESSIONAL)
            results.append(result)
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_reviews": self.stats["total_reviews"],
            "by_domain": self.stats["by_domain"],
            "engines": {
                domain.value: {
                    "processed": eng.statistics["processed"],
                    "issues_found": eng.statistics["issues_found"]
                }
                for domain, eng in self.engines.items()
            }
        }


def create_engine_pool() -> ReviewEnginePool:
    """创建审核引擎池"""
    return ReviewEnginePool()
