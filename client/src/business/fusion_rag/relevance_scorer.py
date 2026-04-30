"""
多维度相关性打分模块 (Relevance Scorer)

实现验证闭环的核心打分系统：
1. 领域匹配度：是否属于目标行业标签
2. 时效性：工业标准是否过期
3. 权威性：是否来自权威源
4. 置信度：是否有多个独立来源交叉验证

核心原则：低于阈值自动丢弃，建立相关性防火墙
"""

import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ScoreBreakdown:
    """打分明细"""
    domain_match: float = 0.0
    timeliness: float = 0.0
    authority: float = 0.0
    confidence: float = 0.0
    combined_score: float = 0.0


@dataclass
class ScoringResult:
    """打分结果"""
    passed: bool
    score: ScoreBreakdown
    reason: str
    threshold: float = 0.0
    uncertainty: str = ""


@dataclass
class ScoringConfig:
    """打分配置"""
    domain_weight: float = 0.35
    timeliness_weight: float = 0.25
    authority_weight: float = 0.25
    confidence_weight: float = 0.15
    pass_threshold: float = 0.6
    warning_threshold: float = 0.4
    source_visibility: bool = True  # 是否向用户暴露来源


class RelevanceScorer:
    """
    多维度相关性打分器
    
    对检索出的知识片段进行多维度打分：
    - 领域匹配度：是否属于目标行业标签
    - 时效性：工业标准是否过期
    - 权威性：是否来自权威源
    - 置信度：是否有多个独立来源交叉验证
    """
    
    def __init__(self, config: Optional[ScoringConfig] = None):
        self.config = config or ScoringConfig()
        
        # 权威来源权重
        self.authority_sources = {
            "国家标准": 1.0,
            "GB/T": 1.0,
            "GB": 0.95,
            "行业标准": 0.9,
            "JB/T": 0.9,
            "HG/T": 0.9,
            "YY/T": 0.9,
            "IEC": 0.95,
            "ISO": 0.95,
            "IEEE": 0.9,
            "专利": 0.85,
            "权威论文": 0.85,
            "技术手册": 0.75,
            "企业标准": 0.7,
            "内部文档": 0.5,
            "百科": 0.3,
            "论坛": 0.1,
            "博客": 0.1
        }
        
        # 行业关键词
        self.industry_keywords = {
            "机械制造": ["机械", "加工", "机床", "轴承", "齿轮", "液压", "气动", "公差"],
            "电子电气": ["电路", "PCB", "PLC", "MCU", "传感器", "继电器", "变频器"],
            "化工": ["反应釜", "精馏塔", "换热器", "催化剂", "溶剂", "工艺"],
            "汽车": ["汽车", "发动机", "变速箱", "ECU", "ESP", "ABS"],
            "医疗": ["医疗", "器械", "诊断", "药品", "CT", "MRI"],
            "能源": ["光伏", "风电", "储能", "逆变器", "充电桩", "电网"],
            "建筑": ["建筑", "结构", "施工", "BIM", "混凝土", "钢筋"]
        }
        
        # 统计
        self.score_count = 0
        self.pass_count = 0
        self.fail_count = 0
        self.warning_count = 0
        
        print("[RelevanceScorer] 初始化完成")
    
    def _score_domain_match(self, content: str, title: str, target_industry: str) -> float:
        """
        计算领域匹配度
        
        Args:
            content: 文档内容
            title: 文档标题
            target_industry: 目标行业
            
        Returns:
            领域匹配分数 (0-1)
        """
        text = (title + " " + content).lower()
        keywords = self.industry_keywords.get(target_industry, [])
        
        if not keywords:
            return 0.5  # 未知行业，默认中等
        
        matched = 0
        for keyword in keywords:
            if keyword.lower() in text:
                matched += 1
        
        score = matched / len(keywords)
        
        return min(1.0, score)
    
    def _score_timeliness(self, content: str, title: str) -> float:
        """
        计算时效性
        
        Args:
            content: 文档内容
            title: 文档标题
            
        Returns:
            时效性分数 (0-1)
        """
        text = title + " " + content
        current_year = datetime.now().year
        
        # 查找年份
        year_pattern = r'(20\d{2})'
        years = re.findall(year_pattern, text)
        
        if years:
            latest_year = max(int(y) for y in years)
            age = current_year - latest_year
            
            if age <= 2:
                return 1.0  # 最新
            elif age <= 5:
                return 0.8  # 较新
            elif age <= 10:
                return 0.5  # 有效
            else:
                return 0.2  # 过期
        
        # 检查修订标识
        if "修订" in text or "更新" in text:
            return 0.8
        
        # 检查标准版本号
        version_pattern = r'V?(\d+)\.(\d+)'
        match = re.search(version_pattern, text)
        if match:
            major = int(match.group(1))
            minor = int(match.group(2))
            if major >= 2 or (major == 1 and minor >= 5):
                return 0.7
        
        # 无法确定时返回中等分数
        return 0.6
    
    def _score_authority(self, source_type: str, title: str) -> float:
        """
        计算权威性
        
        Args:
            source_type: 来源类型
            title: 文档标题
            
        Returns:
            权威性分数 (0-1)
        """
        text = (title + " " + source_type).lower()
        
        # 检查权威来源
        max_score = 0.0
        for source, score in self.authority_sources.items():
            if source.lower() in text:
                max_score = max(max_score, score)
        
        # 如果没有匹配到已知来源，根据标题判断
        if max_score == 0.0:
            # 检查是否有标准号
            standard_patterns = [r'GB/T\s*\d+', r'GB\s*\d+', r'IEC\s*\d+', r'ISO\s*\d+']
            for pattern in standard_patterns:
                if re.search(pattern, text):
                    return 0.9
            
            # 默认中等
            return 0.5
        
        return max_score
    
    def _score_confidence(self, content: str, source_count: int = 1) -> float:
        """
        计算置信度（基于内容质量和来源数量）
        
        Args:
            content: 文档内容
            source_count: 独立来源数量
            
        Returns:
            置信度分数 (0-1)
        """
        score = 0.5
        
        # 内容长度检查
        content_len = len(content)
        if 100 <= content_len <= 2000:
            score += 0.2
        elif content_len < 50:
            score -= 0.1
        elif content_len > 5000:
            score -= 0.1
        
        # 结构化内容检查（包含列表、表格等）
        if any(pattern in content for pattern in ['\n- ', '\n* ', '|', '表格', '表1', '表2']):
            score += 0.1
        
        # 引用标注检查
        if any(pattern in content for pattern in ['引用', '来源', '参考', '参见']):
            score += 0.1
        
        # 来源数量加成
        if source_count >= 2:
            score += 0.1 * min(source_count - 1, 3)
        
        return min(1.0, max(0.0, score))
    
    def score(self, content: str, title: str, source_type: str, 
              target_industry: str, source_count: int = 1) -> ScoringResult:
        """
        计算多维度相关性分数
        
        Args:
            content: 文档内容
            title: 文档标题
            source_type: 来源类型
            target_industry: 目标行业
            source_count: 独立来源数量
            
        Returns:
            ScoringResult
        """
        self.score_count += 1
        
        # 计算各维度分数
        domain_score = self._score_domain_match(content, title, target_industry)
        timeliness_score = self._score_timeliness(content, title)
        authority_score = self._score_authority(source_type, title)
        confidence_score = self._score_confidence(content, source_count)
        
        # 加权融合
        combined = (
            domain_score * self.config.domain_weight +
            timeliness_score * self.config.timeliness_weight +
            authority_score * self.config.authority_weight +
            confidence_score * self.config.confidence_weight
        )
        
        # 构建结果
        score = ScoreBreakdown(
            domain_match=domain_score,
            timeliness=timeliness_score,
            authority=authority_score,
            confidence=confidence_score,
            combined_score=combined
        )
        
        # 判断是否通过
        if combined >= self.config.pass_threshold:
            self.pass_count += 1
            passed = True
            reason = "通过验证"
            uncertainty = ""
        elif combined >= self.config.warning_threshold:
            self.warning_count += 1
            passed = True
            reason = "通过验证（低置信度）"
            uncertainty = "该信息通用性较强，建议结合具体工况确认"
        else:
            self.fail_count += 1
            passed = False
            reason = f"未通过验证（综合分数 {combined:.2f} < {self.config.pass_threshold}）"
            uncertainty = ""
        
        return ScoringResult(
            passed=passed,
            score=score,
            reason=reason,
            threshold=self.config.pass_threshold,
            uncertainty=uncertainty
        )
    
    def score_batch(self, items: List[Dict[str, Any]], target_industry: str) -> List[ScoringResult]:
        """
        批量打分
        
        Args:
            items: 待打分项目列表，每个包含 content, title, source_type, source_count
            target_industry: 目标行业
            
        Returns:
            打分结果列表
        """
        results = []
        for item in items:
            result = self.score(
                content=item.get("content", ""),
                title=item.get("title", ""),
                source_type=item.get("source_type", "unknown"),
                target_industry=target_industry,
                source_count=item.get("source_count", 1)
            )
            results.append(result)
        return results
    
    def filter_by_score(self, items: List[Dict[str, Any]], target_industry: str,
                       min_score: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        根据分数过滤结果
        
        Args:
            items: 待过滤项目列表
            target_industry: 目标行业
            min_score: 最低分数阈值（默认使用配置的pass_threshold）
            
        Returns:
            过滤后的项目列表（带分数信息）
        """
        threshold = min_score or self.config.pass_threshold
        filtered = []
        
        for item in items:
            result = self.score(
                content=item.get("content", ""),
                title=item.get("title", ""),
                source_type=item.get("source_type", "unknown"),
                target_industry=target_industry,
                source_count=item.get("source_count", 1)
            )
            
            if result.score.combined_score >= threshold:
                filtered.append({
                    **item,
                    "relevance_score": result.score.combined_score,
                    "score_breakdown": {
                        "domain_match": result.score.domain_match,
                        "timeliness": result.score.timeliness,
                        "authority": result.score.authority,
                        "confidence": result.score.confidence
                    },
                    "uncertainty": result.uncertainty
                })
        
        # 按分数排序
        filtered.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return filtered
    
    def generate_source_attribution(self, title: str, source_type: str) -> str:
        """
        生成来源说明
        
        Args:
            title: 文档标题
            source_type: 来源类型
            
        Returns:
            来源说明文本
        """
        if not self.config.source_visibility:
            return ""
        
        if "GB/T" in title or "国家标准" in title:
            return f"参考《{title}》"
        elif "专利" in source_type:
            return f"专利文献：{title}"
        elif "论文" in source_type:
            return f"学术论文：{title}"
        elif "手册" in source_type:
            return f"技术手册：{title}"
        else:
            return f"来源：{title}"
    
    def get_stats(self) -> Dict[str, Any]:
        """获取打分器统计信息"""
        return {
            "total_scores": self.score_count,
            "passed": self.pass_count,
            "failed": self.fail_count,
            "warnings": self.warning_count,
            "pass_rate": self.pass_count / max(self.score_count, 1) * 100,
            "config": {
                "domain_weight": self.config.domain_weight,
                "timeliness_weight": self.config.timeliness_weight,
                "authority_weight": self.config.authority_weight,
                "confidence_weight": self.config.confidence_weight,
                "pass_threshold": self.config.pass_threshold,
                "warning_threshold": self.config.warning_threshold
            }
        }


def create_relevance_scorer(config: Optional[ScoringConfig] = None) -> RelevanceScorer:
    """创建相关性打分器实例"""
    return RelevanceScorer(config)


__all__ = [
    "RelevanceScorer",
    "ScoreBreakdown",
    "ScoringResult",
    "ScoringConfig",
    "create_relevance_scorer"
]