"""
行业过滤器模块 (Industry Filter)

实现基于行业标签的检索过滤和重排序：
1. 行业过滤器：基于源头tagging，过滤掉跨行业的干扰项
2. 行业感知重排序：优先提升包含标准号、型号规格的片段排名
3. 查询行业化改写：自动注入行业上下文

核心原则：确保检索结果的行业相关性
"""

import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field


@dataclass
class FilterResult:
    """过滤结果"""
    passed: bool
    reason: str = ""
    confidence: float = 0.0


@dataclass
class QueryRewriteResult:
    """查询重写结果"""
    original_query: str
    rewritten_query: str
    industry_context: str
    added_terms: List[str]
    confidence: float = 0.0


class IndustryFilter:
    """
    行业过滤器
    
    实现：
    1. 行业领域过滤：过滤掉跨行业的干扰项
    2. 行业感知重排序：提升行业相关文档排名
    3. 查询行业化改写：自动注入行业上下文
    """
    
    def __init__(self):
        # 行业领域定义
        self.industry_domains = {
            "机械制造": {
                "keywords": ["机械", "加工", "机床", "轴承", "齿轮", "夹具", "液压", "气动"],
                "standards": ["GB/T 1800", "GB/T 1182", "GB/T 3077", "JB/T"],
                "patterns": [r'GB/T\s*\d+', r'JB/T\s*\d+', r'公差等级', r'表面粗糙度']
            },
            "电子电气": {
                "keywords": ["电路", "PCB", "PLC", "MCU", "传感器", "继电器", "变频器"],
                "standards": ["GB/T 19001", "GB/T 28181", "IEC", "IEEE"],
                "patterns": [r'IEC\s*\d+', r'IEEE\s*\d+', r'GB/T\s*19001']
            },
            "化工": {
                "keywords": ["反应釜", "精馏塔", "换热器", "催化剂", "溶剂", "工艺"],
                "standards": ["GB/T 3723", "GB/T 6678", "HG/T"],
                "patterns": [r'HG/T\s*\d+', r'GB/T\s*3723', r'CAS号']
            },
            "汽车": {
                "keywords": ["汽车", "发动机", "变速箱", "ECU", "ESP", "ABS"],
                "standards": ["GB 7258", "GB/T 19056", "ISO/TS 16949"],
                "patterns": [r'GB\s*7258', r'ISO/TS\s*16949', r'VIN码']
            },
            "医疗": {
                "keywords": ["医疗", "器械", "诊断", "药品", "CT", "MRI", "手术"],
                "standards": ["GB 9706", "YY/T", "ISO 13485"],
                "patterns": [r'YY/T\s*\d+', r'ISO\s*13485', r'医疗器械']
            },
            "能源": {
                "keywords": ["光伏", "风电", "储能", "逆变器", "充电桩", "电网"],
                "standards": ["GB/T 19964", "GB/T 20046", "IEC 61727"],
                "patterns": [r'IEC\s*61727', r'GB/T\s*19964', r'kWp']
            },
            "建筑": {
                "keywords": ["建筑", "结构", "施工", "BIM", "混凝土", "钢筋"],
                "standards": ["GB 50010", "GB 50007", "JGJ"],
                "patterns": [r'JGJ\s*\d+', r'GB\s*50010', r'MPa']
            }
        }
        
        # 行业互斥规则（防止跨行业干扰）
        self.exclusion_rules: Dict[str, List[str]] = {
            "机械制造": ["医疗", "生物", "制药"],
            "电子电气": ["医疗", "食品", "化妆品"],
            "化工": ["医疗", "食品", "医药"],
            "医疗": ["化工", "机械制造", "能源"],
            "能源": ["医疗", "食品"]
        }
        
        # 标准号模式
        self.standard_patterns = [
            r'(GB/T\s*\d+(?:\.\d+)*)',
            r'(GB\s*\d+(?:\.\d+)*)',
            r'(JB/T\s*\d+(?:\.\d+)*)',
            r'(HG/T\s*\d+(?:\.\d+)*)',
            r'(YY/T\s*\d+(?:\.\d+)*)',
            r'(IEC\s*\d+(?:\.\d+)*)',
            r'(ISO\s*\d+(?:\.\d+)*)',
            r'(IEEE\s*\d+(?:\.\d+)*)'
        ]
        
        # 型号规格模式
        self.spec_patterns = [
            r'[A-Z]+\d+[-_]?\d*',  # 型号如: ABC123, XYZ-456
            r'\d+[x×]\d+[x×]\d+',  # 尺寸如: 100x200x300
            r'\d+(?:\.\d+)?\s*(mm|cm|m|kg|t|kW|A|V)',  # 带单位的数值
        ]
        
        # 目标行业
        self.target_industry = "通用"
        
        # 统计
        self.filter_count = 0
        self.pass_count = 0
        self.block_count = 0
        self.rewrite_count = 0
        
        print("[IndustryFilter] 初始化完成")
    
    def set_target_industry(self, industry: str):
        """
        设置目标行业
        
        Args:
            industry: 目标行业名称
        """
        if industry in self.industry_domains:
            self.target_industry = industry
            print(f"[IndustryFilter] 目标行业设置为: {industry}")
        else:
            print(f"[IndustryFilter] 未知行业: {industry}，使用默认值")
    
    def detect_industry(self, text: str) -> List[Tuple[str, float]]:
        """
        检测文本所属行业
        
        Args:
            text: 输入文本
            
        Returns:
            [(行业名称, 置信度)] 列表，按置信度排序
        """
        results = []
        
        for industry, config in self.industry_domains.items():
            score = 0
            matches = 0
            
            # 关键词匹配
            for keyword in config["keywords"]:
                if keyword in text:
                    score += 2
                    matches += 1
            
            # 标准号匹配
            for standard in config["standards"]:
                if standard.lower() in text.lower():
                    score += 3
                    matches += 1
            
            # 模式匹配
            for pattern in config["patterns"]:
                if re.search(pattern, text):
                    score += 2
                    matches += 1
            
            if matches > 0:
                confidence = min(1.0, score / 10.0)
                results.append((industry, confidence))
        
        # 排序
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results
    
    def filter_by_industry(self, doc_content: str, doc_title: str, 
                          target_industry: str) -> FilterResult:
        """
        根据目标行业过滤文档
        
        Args:
            doc_content: 文档内容
            doc_title: 文档标题
            target_industry: 目标行业
            
        Returns:
            FilterResult
        """
        self.filter_count += 1
        
        # 获取文档的行业标签
        doc_industries = self.detect_industry(doc_title + " " + doc_content)
        
        if not doc_industries:
            # 无法识别行业的文档，默认通过
            self.pass_count += 1
            return FilterResult(passed=True, reason="无法识别行业，默认通过", confidence=0.5)
        
        # 检查是否属于目标行业或相关行业
        doc_industry, confidence = doc_industries[0]
        
        # 如果置信度很高且明确属于目标行业
        if doc_industry == target_industry and confidence > 0.6:
            self.pass_count += 1
            return FilterResult(
                passed=True,
                reason=f"属于目标行业: {doc_industry}",
                confidence=confidence
            )
        
        # 检查互斥规则
        if target_industry in self.exclusion_rules:
            excluded = self.exclusion_rules[target_industry]
            if doc_industry in excluded:
                self.block_count += 1
                return FilterResult(
                    passed=False,
                    reason=f"行业互斥: {doc_industry} 与 {target_industry} 不兼容",
                    confidence=0.0
                )
        
        # 低置信度时通过（避免过度过滤）
        if confidence < 0.4:
            self.pass_count += 1
            return FilterResult(
                passed=True,
                reason=f"行业置信度低 ({confidence:.2f})，允许通过",
                confidence=confidence
            )
        
        # 其他情况根据相关性判断
        self.pass_count += 1
        return FilterResult(
            passed=True,
            reason=f"行业相关性: {doc_industry} (置信度: {confidence:.2f})",
            confidence=confidence
        )
    
    def rerank_by_industry(self, query: str, results: List[Dict[str, Any]],
                          target_industry: str) -> List[Dict[str, Any]]:
        """
        行业感知重排序
        
        Args:
            query: 用户查询
            results: 检索结果列表
            target_industry: 目标行业
            
        Returns:
            重新排序后的结果
        """
        scored_results = []
        
        for result in results:
            content = result.get("content", "")
            title = result.get("title", "")
            original_score = result.get("score", 0.0)
            
            bonus_score = 0.0
            
            # 检查标准号
            for pattern in self.standard_patterns:
                if re.search(pattern, content) or re.search(pattern, title):
                    bonus_score += 0.2
                    break
            
            # 检查型号规格
            for pattern in self.spec_patterns:
                if re.search(pattern, content):
                    bonus_score += 0.1
                    break
            
            # 检查行业关键词
            industry_config = self.industry_domains.get(target_industry)
            if industry_config:
                for keyword in industry_config["keywords"]:
                    if keyword in content:
                        bonus_score += 0.05
                        break
            
            # 综合分数
            final_score = original_score + bonus_score
            
            scored_results.append({
                **result,
                "original_score": original_score,
                "bonus_score": bonus_score,
                "final_score": final_score
            })
        
        # 排序
        scored_results.sort(key=lambda x: x["final_score"], reverse=True)
        
        return scored_results
    
    def rewrite_query(self, query: str, target_industry: str) -> QueryRewriteResult:
        """
        将查询改写为行业化查询
        
        Args:
            query: 原始查询
            target_industry: 目标行业
            
        Returns:
            QueryRewriteResult
        """
        self.rewrite_count += 1
        
        added_terms = []
        industry_config = self.industry_domains.get(target_industry)
        
        if not industry_config:
            return QueryRewriteResult(
                original_query=query,
                rewritten_query=query,
                industry_context="",
                added_terms=[]
            )
        
        # 添加行业关键词
        for keyword in industry_config["keywords"][:3]:
            if keyword not in query:
                added_terms.append(keyword)
        
        # 添加行业上下文
        if added_terms:
            rewritten = f"{query} 在 {target_industry} 中的应用"
        else:
            rewritten = query
        
        return QueryRewriteResult(
            original_query=query,
            rewritten_query=rewritten,
            industry_context=target_industry,
            added_terms=added_terms,
            confidence=0.8 if added_terms else 0.5
        )
    
    def validate_query_context(self, query: str) -> Dict[str, Any]:
        """
        验证查询的行业上下文
        
        Args:
            query: 用户查询
            
        Returns:
            {
                "detected_industries": [(行业, 置信度)],
                "recommended_industry": str,
                "needs_context": bool
            }
        """
        detected = self.detect_industry(query)
        
        needs_context = len(detected) == 0 or (len(detected) == 1 and detected[0][1] < 0.5)
        
        recommended = detected[0][0] if detected else "通用"
        
        return {
            "detected_industries": detected,
            "recommended_industry": recommended,
            "needs_context": needs_context
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取过滤器统计信息"""
        return {
            "filter_count": self.filter_count,
            "pass_count": self.pass_count,
            "block_count": self.block_count,
            "pass_rate": self.pass_count / max(self.filter_count, 1) * 100,
            "rewrite_count": self.rewrite_count,
            "supported_industries": list(self.industry_domains.keys())
        }


def create_industry_filter() -> IndustryFilter:
    """创建行业过滤器实例"""
    return IndustryFilter()


__all__ = [
    "IndustryFilter",
    "FilterResult",
    "QueryRewriteResult",
    "create_industry_filter"
]