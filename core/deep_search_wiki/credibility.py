"""
来源可信度评估器
"""

import re
from typing import Dict, Optional
from datetime import datetime
from .models import SourceInfo, SourceType


class CredibilityEvaluator:
    """来源可信度评估器"""
    
    # 权威域名列表及其基础分
    AUTHORITY_DOMAINS: Dict[str, float] = {
        # 官方文档
        "github.com": 85,
        "docs.python.org": 95,
        "docs.microsoft.com": 95,
        "developer.mozilla.org": 95,
        "kubernetes.io": 90,
        "docs.docker.com": 90,
        "learn.microsoft.com": 92,
        
        # 学术机构
        "arxiv.org": 88,
        "nature.com": 95,
        "science.org": 95,
        "ieee.org": 90,
        "acm.org": 90,
        "springer.com": 88,
        "wiley.com": 88,
        "elsevier.com": 88,
        "stanford.edu": 95,
        "mit.edu": 95,
        "berkeley.edu": 95,
        
        # 技术博客
        "medium.com": 70,
        "dev.to": 75,
        "stackoverflow.com": 80,
        "知乎.com": 75,
        "bilibili.com": 65,
        
        # 知名科技公司博客
        "blog.google": 85,
        "blog.openai.com": 88,
        "ai.googleblog.com": 90,
        "engineering.fb.com": 85,
        "blog.cloudflare.com": 82,
        
        # 新闻媒体
        "reuters.com": 85,
        "bbc.com": 82,
        "cnn.com": 80,
        "apnews.com": 83,
    }
    
    # 高风险域名
    HIGH_RISK_DOMAINS = [
        "bit.ly",
        "tinyurl.com",
        "goo.gl",
        "t.co",
    ]
    
    def evaluate(self, source: SourceInfo) -> SourceInfo:
        """评估来源可信度"""
        
        # 1. 权威性评估
        source.authority_score = self._evaluate_authority(source)
        
        # 2. 内容质量评估
        source.content_score = self._evaluate_content(source)
        
        # 3. 技术指标评估
        source.technical_score = self._evaluate_technical(source)
        
        # 4. 计算综合可信度
        source.calculate_credibility()
        
        # 5. 调整可信度
        source.credibility = self._adjust_credibility(source)
        
        return source
    
    def _evaluate_authority(self, source: SourceInfo) -> float:
        """评估权威性"""
        score = 50.0  # 默认分
        
        # 域名权威性
        domain = source.domain.lower()
        for auth_domain, auth_score in self.AUTHORITY_DOMAINS.items():
            if auth_domain in domain:
                score = max(score, auth_score)
                break
        
        # 来源类型权威性
        type_scores = {
            SourceType.OFFICIAL_DOCS: 15,
            SourceType.PAPER: 20,
            SourceType.QNA: 10,
            SourceType.BLOG: 5,
            SourceType.VIDEO: 5,
            SourceType.SOCIAL: -5,
        }
        score += type_scores.get(source.source_type, 0)
        
        # 作者权威性
        if source.author:
            # 检查是否是知名作者
            known_authors = ["google", "microsoft", "openai", "stanford", "mit"]
            if any(k in source.author.lower() for k in known_authors):
                score += 10
        
        return min(100, max(0, score))
    
    def _evaluate_content(self, source: SourceInfo) -> float:
        """评估内容质量"""
        score = 50.0
        
        # 标题质量
        if source.title:
            # 标题长度适中
            if 10 <= len(source.title) <= 100:
                score += 10
            
            # 包含关键词
            quality_indicators = ["tutorial", "guide", "introduction", "official", "docs"]
            if any(ind in source.title.lower() for ind in quality_indicators):
                score += 10
        
        # 发布日期
        if source.publish_date:
            days_old = (datetime.now() - source.publish_date).days
            if days_old < 365:  # 1年内
                score += 15
            elif days_old < 1825:  # 5年内
                score += 5
            # 太旧的内容扣分
            else:
                score -= 10
        
        # 浏览量（如果有）
        if source.views > 0:
            if source.views > 1000000:
                score += 15
            elif source.views > 100000:
                score += 10
            elif source.views > 10000:
                score += 5
        
        # 点赞数（如果有）
        if source.likes > 0:
            score += min(10, source.likes / 100)
        
        return min(100, max(0, score))
    
    def _evaluate_technical(self, source: SourceInfo) -> float:
        """评估技术指标"""
        score = 50.0
        
        # 引用次数
        if source.citations > 0:
            if source.citations > 1000:
                score += 25
            elif source.citations > 100:
                score += 15
            elif source.citations > 10:
                score += 5
        
        # URL风险检测
        for risk_domain in self.HIGH_RISK_DOMAINS:
            if risk_domain in source.url:
                score -= 30
                break
        
        # URL长度异常
        if len(source.url) > 500:
            score -= 10
        
        # HTTPS
        if source.url.startswith("https://"):
            score += 10
        
        return min(100, max(0, score))
    
    def _adjust_credibility(self, source: SourceInfo) -> float:
        """调整可信度"""
        credibility = source.credibility
        
        # 时间衰减：过旧的内容降低可信度
        if source.publish_date:
            days_old = (datetime.now() - source.publish_date).days
            if days_old > 1825:  # 超过5年
                credibility *= 0.8
            elif days_old > 365:  # 超过1年
                credibility *= 0.9
        
        # 引用数加权
        if source.citations > 100:
            credibility = min(100, credibility * 1.1)
        
        return round(credibility, 1)
    
    def get_risk_level(self, source: SourceInfo) -> str:
        """获取风险等级"""
        if source.credibility >= 80:
            return "🟢 低风险"
        elif source.credibility >= 60:
            return "🟡 中等风险"
        else:
            return "🔴 高风险"
    
    def format_credibility_report(self, source: SourceInfo) -> str:
        """格式化可信度报告"""
        self.evaluate(source)
        
        report = [
            f"## 📊 来源可信度报告",
            "",
            f"**标题**: {source.title}",
            f"**URL**: {source.url}",
            f"**域名**: {source.domain}",
            f"**类型**: {source.source_type.value}",
            "",
            f"### 评分详情",
            "",
            f"| 评估维度 | 得分 |",
            f"|----------|------|",
            f"| 权威性 | {source.authority_score:.1f} |",
            f"| 内容质量 | {source.content_score:.1f} |",
            f"| 技术指标 | {source.technical_score:.1f} |",
            f"| **综合可信度** | **{source.credibility:.1f}** |",
            "",
            f"### 风险评估: {self.get_risk_level(source)}",
            "",
        ]
        
        if source.publish_date:
            report.append(f"**发布日期**: {source.publish_date.strftime('%Y-%m-%d')}")
        
        if source.citations > 0:
            report.append(f"**引用次数**: {source.citations}")
        
        if source.views > 0:
            report.append(f"**浏览量**: {source.views:,}")
        
        return "\n".join(report)
