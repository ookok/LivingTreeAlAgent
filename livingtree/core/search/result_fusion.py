"""
结果融合与质量保障引擎

核心功能：
- 多源结果去重
- 智能排序
- 质量评分
- 摘要生成
"""

import re
from typing import List, Dict, Tuple, Set, Optional
from datetime import datetime
from collections import Counter

from .models import SearchResult, TierLevel, QueryType, FusionResult


class ResultFusion:
    """
    结果融合引擎
    
    处理多源搜索结果的融合、去重、排序
    """
    
    def __init__(self):
        # 标题相似度阈值
        self.title_similarity_threshold = 0.85
        
        # 内容相似度阈值
        self.content_similarity_threshold = 0.70
        
        # 高质量域名
        self.quality_domains = {
            "gov.cn": 1.0, "gov.uk": 1.0, "edu.cn": 0.95, "edu": 0.95,
            "github.com": 0.9, "arxiv.org": 0.9,
            "zhihu.com": 0.7, "stackoverflow.com": 0.8,
            "wikipedia.org": 0.75, "baidu.com": 0.6,
        }
        
        # 低质量关键词
        self.low_quality_keywords = {
            "广告", "推广", "Sponsored", "Advertisement",
            "best", "top", "buy", "cheap", "discount",
            "click here", "learn more", "必看", "收藏",
        }
    
    def fuse(
        self, 
        results: List[SearchResult], 
        query: str,
        query_type: QueryType = QueryType.GENERAL,
        max_results: int = 10
    ) -> FusionResult:
        """
        融合搜索结果
        
        Args:
            results: 原始结果列表
            query: 原始查询
            query_type: 查询类型
            max_results: 最大返回数量
            
        Returns:
            FusionResult: 融合后的结果
        """
        if not results:
            return FusionResult(
                results=[],
                query=query,
                query_type=query_type,
            )
        
        # 1. SEO过滤
        filtered = self._filter_seo(results)
        
        # 2. 去重
        deduplicated = self._deduplicate(filtered)
        
        # 3. 质量评分
        scored = self._score_results(deduplicated, query, query_type)
        
        # 4. 排序
        sorted_results = self._rank_results(scored, query, query_type)
        
        # 5. 截取结果
        final_results = sorted_results[:max_results]
        
        # 6. 构建融合结果
        fusion_result = self._build_fusion_result(final_results, query, query_type)
        
        return fusion_result
    
    def _filter_seo(self, results: List[SearchResult]) -> List[SearchResult]:
        """过滤SEO垃圾内容"""
        filtered = []
        
        for result in results:
            combined = (result.title + " " + result.snippet).lower()
            
            # 检查低质量关键词
            low_quality_count = sum(1 for kw in self.low_quality_keywords if kw in combined)
            if low_quality_count >= 2:
                continue
            
            # 检查SEO模式
            seo_patterns = [
                r'^\d+[、，]',  # 列表堆砌
                r'点击量', r'观看量',
                r'必看', r'收藏', r'转发',
            ]
            for pattern in seo_patterns:
                if re.search(pattern, combined):
                    continue
            
            filtered.append(result)
        
        return filtered
    
    def _deduplicate(self, results: List[SearchResult]) -> List[SearchResult]:
        """去重处理"""
        seen_urls: Set[str] = set()
        seen_titles: Set[str] = set()
        deduplicated: List[SearchResult] = []
        
        for result in results:
            # URL去重
            if result.url in seen_urls:
                continue
            
            # 标题相似度去重
            normalized_title = self._normalize_text(result.title)
            is_duplicate = False
            
            for seen_title in seen_titles:
                if self._calculate_similarity(normalized_title, seen_title) >= self.title_similarity_threshold:
                    is_duplicate = True
                    break
            
            if is_duplicate:
                continue
            
            seen_urls.add(result.url)
            seen_titles.add(normalized_title)
            deduplicated.append(result)
        
        return deduplicated
    
    def _normalize_text(self, text: str) -> str:
        """标准化文本"""
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        text = ' '.join(text.split())
        return text
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _score_results(
        self, 
        results: List[SearchResult], 
        query: str,
        query_type: QueryType
    ) -> List[SearchResult]:
        """对结果进行质量评分"""
        query_words = set(query.lower().split())
        
        for result in results:
            score = 0.0
            
            # 1. 来源权威性（0-3分）
            authority = self._get_authority_score(result)
            score += authority
            
            # 2. 内容相关性（0-3分）
            relevance = self._get_relevance_score(result, query_words)
            score += relevance
            
            # 3. 时效性（0-2分）
            freshness = self._get_freshness_score(result)
            score += freshness
            
            # 4. 内容完整性（0-2分）
            completeness = self._get_completeness_score(result)
            score += completeness
            
            result.quality_score = score
            result.relevance_score = relevance
        
        return results
    
    def _get_authority_score(self, result: SearchResult) -> float:
        """获取权威性评分"""
        url_lower = result.url.lower()
        
        for domain, score in self.quality_domains.items():
            if domain in url_lower:
                return score * 3
        
        return 1.5
    
    def _get_relevance_score(self, result: SearchResult, query_words: Set[str]) -> float:
        """获取内容相关性评分"""
        title_words = set(result.title.lower().split())
        snippet_words = set(result.snippet.lower().split())
        
        title_coverage = len(query_words & title_words) / max(len(query_words), 1)
        snippet_coverage = len(query_words & snippet_words) / max(len(query_words), 1)
        
        coverage = title_coverage * 0.6 + snippet_coverage * 0.4
        
        return min(coverage * 3, 3.0)
    
    def _get_freshness_score(self, result: SearchResult) -> float:
        """获取时效性评分"""
        if not result.date:
            return 1.0
        
        try:
            year_match = re.search(r'20\d{2}', result.date)
            if year_match:
                year = int(year_match.group())
                current_year = datetime.now().year
                
                if year >= current_year:
                    return 2.0
                elif year >= current_year - 1:
                    return 1.5
                elif year >= current_year - 3:
                    return 1.0
                else:
                    return 0.5
        except:
            pass
        
        return 1.0
    
    def _get_completeness_score(self, result: SearchResult) -> float:
        """获取内容完整性评分"""
        score = 0.0
        
        if result.title:
            score += 0.5
        
        if result.snippet and len(result.snippet) > 50:
            score += 0.5
        
        if result.url:
            score += 0.5
        
        if result.date:
            score += 0.5
        
        return min(score, 2.0)
    
    def _rank_results(
        self, 
        results: List[SearchResult],
        query: str,
        query_type: QueryType
    ) -> List[SearchResult]:
        """对结果进行排序"""
        
        def rank_key(result: SearchResult) -> Tuple[float, float, float]:
            tier_weight = {
                TierLevel.TIER_1_CN_HIGH: 1.0,
                TierLevel.TIER_2_CN_VERTICAL: 0.9,
                TierLevel.TIER_3_GLOBAL: 0.7,
                TierLevel.TIER_4_FALLBACK: 0.5,
            }.get(result.tier, 0.5)
            
            type_weight = self._get_type_match_weight(result, query_type)
            
            total_score = (
                result.quality_score * 0.4 + 
                result.relevance_score * 0.4 +
                tier_weight * type_weight * 0.2
            )
            
            return (-total_score, -result.quality_score, -result.relevance_score)
        
        return sorted(results, key=rank_key)
    
    def _get_type_match_weight(self, result: SearchResult, query_type: QueryType) -> float:
        """获取类型匹配权重"""
        url_lower = result.url.lower()
        
        type_matches = {
            QueryType.NEWS: ["news", "xinhuanet", "sina", "tencent"],
            QueryType.TECHNICAL: ["github", "stackoverflow", "docs"],
            QueryType.ACADEMIC: ["arxiv", "scholar", "cnki"],
            QueryType.ENTERTAINMENT: ["douban", "movie", "music"],
            QueryType.POLICY: ["gov.cn", "gov"],
            QueryType.LIFE: ["amap", "weather", "map"],
        }
        
        keywords = type_matches.get(query_type, [])
        for kw in keywords:
            if kw in url_lower:
                return 1.0
        
        return 0.5
    
    def _build_fusion_result(
        self, 
        results: List[SearchResult],
        query: str,
        query_type: QueryType
    ) -> FusionResult:
        """构建融合结果"""
        
        source_counter = Counter(r.source for r in results)
        tier_counter = Counter(r.tier for r in results)
        
        avg_quality = sum(r.quality_score for r in results) / max(len(results), 1)
        avg_relevance = sum(r.relevance_score for r in results) / max(len(results), 1)
        
        fresh_count = sum(1 for r in results if self._is_recent(r.date))
        freshness = fresh_count / max(len(results), 1)
        
        return FusionResult(
            results=results,
            total_sources=len(source_counter),
            unique_urls=len(set(r.url for r in results)),
            tier_distribution=dict(tier_counter),
            avg_quality_score=avg_quality,
            avg_relevance_score=avg_relevance,
            freshness_score=freshness,
            sources_used=list(source_counter.keys()),
            query=query,
            query_type=query_type,
        )
    
    def _is_recent(self, date_str: Optional[str]) -> bool:
        """检查是否近期内容"""
        if not date_str:
            return False
        
        try:
            year_match = re.search(r'20\d{2}', date_str)
            if year_match:
                year = int(year_match.group())
                return year >= datetime.now().year - 1
        except:
            pass
        
        return False


__all__ = ["ResultFusion"]
