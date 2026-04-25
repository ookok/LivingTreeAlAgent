"""
BookRAG - IFT 查询分类器
Information Flow Type Query Classifier

基于查询特征将用户问题分类为：
- SINGLE_HOP: 单跳查询（直接事实查找）
- MULTI_HOP: 多跳查询（需要推理/比较）
- GLOBAL_AGGREGATION: 全局聚合查询（统计/汇总）
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import re


class IFTQueryType(Enum):
    """信息流类型枚举"""
    SINGLE_HOP = "single_hop"           # 单跳查询
    MULTI_HOP = "multi_hop"             # 多跳查询
    GLOBAL_AGGREGATION = "global_aggregation"  # 全局聚合


@dataclass
class IFTClassificationResult:
    """IFT 分类结果"""
    query_type: IFTQueryType
    confidence: float  # 0.0 ~ 1.0
    reasoning: List[str] = field(default_factory=list)
    recommended_pipeline: List[str] = field(default_factory=list)
    keywords_matched: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        return (
            f"IFTClassificationResult(\n"
            f"  type={self.query_type.value},\n"
            f"  confidence={self.confidence:.2f},\n"
            f"  pipeline={self.recommended_pipeline},\n"
            f"  matched={self.keywords_matched}\n"
            f")"
        )


class IFTQueryClassifier:
    """
    IFT 查询分类器
    
    基于关键词特征和模式匹配进行查询类型分类。
    支持中英文混合查询。
    """
    
    # 多跳关键词模式
    MULTI_HOP_PATTERNS = [
        # 英文
        r'\bvs\b', r'\bversus\b', r'\bcompare\b', r'\bcomparison\b',
        r'\bdifference\b', r'\bdifferent from\b', r'\bsimilar to\b',
        r'\bbecause\b', r'\btherefore\b', r'\bthus\b', r'\bhence\b',
        r'\bwhy\b', r'\bhow does.*work\b', r'\bhow.*work\b',
        r'\brelation\b', r'\brelated to\b', r'\bconnect\b',
        # 中文
        r'和.*区别', r'与.*区别', r'比较', r'对比',
        r'为什么', r'因为', r'所以', r'因此',
        r'如何工作', r'怎么工作', r'是什么关系',
        r'还是', r'或者', r'或者.*更好',
    ]
    
    # 全局聚合关键词
    AGGREGATION_PATTERNS = [
        # 英文
        r'\bhow many\b', r'\bhow much\b', r'\btotal\b', r'\bsum\b',
        r'\bcount\b', r'\blist all\b', r'\ball.*mentioned\b',
        r'\bsummarize\b', r'\bsummary\b', r'\boverall\b',
        r'\bevery\b', r'\beach\b', r'\bnumber of\b',
        r'\btimes\b',  # "how many times"
        # 中文
        r'多少', r'一共', r'总计', r'总数',
        r'列出', r'列举', r'所有', r'全部',
        r'总结', r'概括', r'汇总', r'统计',
        r'有.*个', r'总.*多少', r'一共有',
        r'哪些', r'分别是什么',
    ]
    
    # 单跳特征词（用于增强 SINGLE_HOP 置信度）
    SINGLE_HOP_PATTERNS = [
        r'^什么是', r'^什么是\b', r'^什么是',
        r'^.*是谁', r'^.*是.*\?$',
        r'定义', r'概念', r'意思',
        r'\bwhat is\b', r'\bwho is\b', r'\bdefinition\b',
    ]
    
    def __init__(self, language: str = "auto"):
        """
        初始化分类器
        
        Args:
            language: "zh", "en", 或 "auto"（自动检测）
        """
        self.language = language
        self._compile_patterns()
    
    def _compile_patterns(self):
        """预编译正则表达式"""
        self.multi_hop_re = [
            re.compile(p, re.IGNORECASE) for p in self.MULTI_HOP_PATTERNS
        ]
        self.agg_re = [
            re.compile(p, re.IGNORECASE) for p in self.AGGREGATION_PATTERNS
        ]
        self.single_hop_re = [
            re.compile(p, re.IGNORECASE) for p in self.SINGLE_HOP_PATTERNS
        ]
    
    def classify(self, query: str) -> IFTClassificationResult:
        """
        分类查询类型
        
        Args:
            query: 用户查询文本
            
        Returns:
            IFTClassificationResult 分类结果
        """
        query = query.strip()
        reasoning = []
        matched_keywords = []
        
        # 检测语言
        detected_lang = self._detect_language(query)
        
        # 计算各类型匹配分数
        multi_hop_score = self._calculate_multi_hop_score(query)
        agg_score = self._calculate_agg_score(query)
        single_hop_score = self._calculate_single_hop_score(query)
        
        # 记录匹配的关键词
        matched_keywords.extend(self._get_matched_keywords(
            query, self.multi_hop_re
        ))
        matched_keywords.extend(self._get_matched_keywords(
            query, self.agg_re
        ))
        
        # 决策逻辑
        if agg_score > 0.5:
            query_type = IFTQueryType.GLOBAL_AGGREGATION
            confidence = min(agg_score, 0.95)
            reasoning.append(f"检测到聚合关键词，得分: {agg_score:.2f}")
            recommended_pipeline = ["selector", "aggregator", "synthesizer"]
            
        elif multi_hop_score > 0.4:
            query_type = IFTQueryType.MULTI_HOP
            confidence = min(multi_hop_score, 0.90)
            reasoning.append(f"检测到多跳/比较关键词，得分: {multi_hop_score:.2f}")
            recommended_pipeline = ["selector", "reasoner", "synthesizer"]
            
        elif single_hop_score > 0.3 and multi_hop_score < 0.2:
            query_type = IFTQueryType.SINGLE_HOP
            confidence = min(single_hop_score, 0.85)
            reasoning.append(f"单跳特征明显，得分: {single_hop_score:.2f}")
            recommended_pipeline = ["selector", "synthesizer"]
            
        else:
            # 默认单跳
            query_type = IFTQueryType.SINGLE_HOP
            confidence = 0.6
            reasoning.append("默认分类为单跳查询")
            recommended_pipeline = ["selector", "synthesizer"]
        
        # 添加调试信息
        reasoning.append(f"语言: {detected_lang}")
        reasoning.append(
            f"分数: multi_hop={multi_hop_score:.2f}, "
            f"agg={agg_score:.2f}, single={single_hop_score:.2f}"
        )
        
        return IFTClassificationResult(
            query_type=query_type,
            confidence=confidence,
            reasoning=reasoning,
            recommended_pipeline=recommended_pipeline,
            keywords_matched=matched_keywords,
            metadata={
                "language": detected_lang,
                "multi_hop_score": multi_hop_score,
                "agg_score": agg_score,
                "single_hop_score": single_hop_score,
            }
        )
    
    def _detect_language(self, query: str) -> str:
        """检测查询语言"""
        # 统计中文字符比例
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', query))
        total_chars = len(query.strip())
        
        if total_chars == 0:
            return "unknown"
        
        chinese_ratio = chinese_chars / total_chars
        
        if chinese_ratio > 0.3:
            return "zh"
        elif chinese_ratio > 0:
            return "mixed"
        else:
            return "en"
    
    def _calculate_multi_hop_score(self, query: str) -> float:
        """计算多跳查询得分"""
        matches = 0
        for pattern in self.multi_hop_re:
            if pattern.search(query):
                matches += 1
        
        if matches == 0:
            return 0.0
        
        # 归一化分数
        return min(matches / 2.0, 1.0)
    
    def _calculate_agg_score(self, query: str) -> float:
        """计算聚合查询得分"""
        matches = 0
        for pattern in self.agg_re:
            if pattern.search(query):
                matches += 1
        
        if matches == 0:
            return 0.0
        
        return min(matches / 2.0, 1.0)
    
    def _calculate_single_hop_score(self, query: str) -> float:
        """计算单跳查询得分"""
        matches = 0
        for pattern in self.single_hop_re:
            if pattern.search(query):
                matches += 1
        
        if matches == 0:
            return 0.0
        
        return min(matches / 1.5, 1.0)
    
    def _get_matched_keywords(
        self, 
        query: str, 
        patterns: List[re.Pattern]
    ) -> List[str]:
        """获取匹配的关键词"""
        matched = []
        for pattern in patterns:
            match = pattern.search(query)
            if match:
                matched.append(match.group())
        return matched


# 快捷函数
def classify_ift_query(query: str) -> IFTClassificationResult:
    """
    快捷函数：对查询进行 IFT 分类
    
    Example:
        >>> result = classify_ift_query("Python 和 Java 有什么区别？")
        >>> print(result.query_type)  # IFTQueryType.MULTI_HOP
    """
    classifier = IFTQueryClassifier()
    return classifier.classify(query)


# 批量分类
def batch_classify(queries: List[str]) -> List[IFTClassificationResult]:
    """
    批量分类查询
    
    Args:
        queries: 查询列表
        
    Returns:
        分类结果列表
    """
    classifier = IFTQueryClassifier()
    return [classifier.classify(q) for q in queries]
