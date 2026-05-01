"""
代码搜索器 - 智能代码搜索和推荐
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from .code_analyzer import CodeEntity

@dataclass
class SearchResult:
    """搜索结果"""
    score: float
    entity: CodeEntity
    snippet: str
    match_type: str  # name, content, docstring, dependency

@dataclass
class CodeRecommendation:
    """代码推荐"""
    entity: CodeEntity
    relevance: float
    reason: str

class CodeSearcher:
    """代码搜索器"""
    
    def __init__(self, code_analyzer):
        self.code_analyzer = code_analyzer
        self._build_index()
    
    def _build_index(self):
        """构建搜索索引"""
        self.inverted_index: Dict[str, List[CodeEntity]] = {}
        
        for entity in self.code_analyzer.entities.values():
            terms = self._extract_terms(entity)
            for term in terms:
                if term not in self.inverted_index:
                    self.inverted_index[term] = []
                self.inverted_index[term].append(entity)
    
    def _extract_terms(self, entity: CodeEntity) -> List[str]:
        """提取搜索词"""
        terms = []
        
        if entity.name:
            terms.extend(entity.name.lower().split('_'))
            terms.extend(entity.name.lower().split('-'))
        
        if entity.docstring:
            for word in re.findall(r'\w+', entity.docstring.lower()):
                if len(word) > 2:
                    terms.append(word)
        
        if entity.dependencies:
            for dep in entity.dependencies:
                terms.extend(dep.lower().split('_'))
        
        return list(set(terms))
    
    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """智能搜索代码"""
        results = []
        query_terms = self._extract_query_terms(query)
        
        for entity in self.code_analyzer.entities.values():
            score, match_type = self._calculate_score(entity, query_terms, query)
            if score > 0:
                snippet = self._get_snippet(entity)
                results.append(SearchResult(
                    score=score,
                    entity=entity,
                    snippet=snippet,
                    match_type=match_type
                ))
        
        results.sort(key=lambda x: -x.score)
        return results[:limit]
    
    def _extract_query_terms(self, query: str) -> List[str]:
        """提取查询词"""
        terms = []
        for word in re.findall(r'\w+', query.lower()):
            if len(word) > 1:
                terms.append(word)
        return terms
    
    def _calculate_score(self, entity: CodeEntity, query_terms: List[str], original_query: str) -> tuple:
        """计算匹配分数"""
        score = 0
        match_type = 'content'
        
        entity_name_lower = entity.name.lower()
        query_lower = original_query.lower()
        
        # 精确匹配名称
        if query_lower == entity_name_lower:
            score += 10
            match_type = 'name'
        elif query_lower in entity_name_lower:
            score += 5
            match_type = 'name'
        
        # 名称包含查询词
        for term in query_terms:
            if term in entity_name_lower:
                score += 2
        
        # 文档字符串匹配
        if entity.docstring:
            doc_lower = entity.docstring.lower()
            if query_lower in doc_lower:
                score += 3
                match_type = 'docstring'
            for term in query_terms:
                if term in doc_lower:
                    score += 1
        
        # 依赖匹配
        if entity.dependencies:
            for dep in entity.dependencies:
                if query_lower in dep.lower():
                    score += 2
                    match_type = 'dependency'
        
        # 类型匹配
        for term in query_terms:
            if term == entity.type:
                score += 3
        
        return score, match_type
    
    def _get_snippet(self, entity: CodeEntity, context_lines: int = 2) -> str:
        """获取代码片段"""
        try:
            with open(entity.file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            start = max(0, entity.line_start - 1 - context_lines)
            end = min(len(lines), entity.line_end + context_lines)
            
            snippet = ''.join(lines[start:end])
            return snippet.strip()[:500]
        except:
            return ""
    
    def recommend_code(self, context_entity: CodeEntity, limit: int = 5) -> List[CodeRecommendation]:
        """根据上下文推荐代码"""
        recommendations = []
        
        related_entities = self.code_analyzer.get_related_entities(context_entity.id)
        
        for entity in related_entities:
            relevance = self._calculate_relevance(context_entity, entity)
            if relevance > 0:
                recommendations.append(CodeRecommendation(
                    entity=entity,
                    relevance=relevance,
                    reason=self._get_recommendation_reason(context_entity, entity)
                ))
        
        recommendations.sort(key=lambda x: -x.relevance)
        return recommendations[:limit]
    
    def _calculate_relevance(self, source: CodeEntity, target: CodeEntity) -> float:
        """计算推荐相关性"""
        relevance = 0
        
        # 同类型优先
        if source.type == target.type:
            relevance += 2
        
        # 同文件优先
        if source.file_path == target.file_path:
            relevance += 1
        
        # 依赖关系
        if target.dependencies and source.name in target.dependencies:
            relevance += 3
        
        return relevance
    
    def _get_recommendation_reason(self, source: CodeEntity, target: CodeEntity) -> str:
        """获取推荐理由"""
        reasons = []
        
        if source.file_path == target.file_path:
            reasons.append("同一文件")
        if source.type == target.type:
            reasons.append("相同类型")
        if target.dependencies and source.name in target.dependencies:
            reasons.append("存在依赖关系")
        
        return ", ".join(reasons) if reasons else "相关代码"
    
    def find_similar_code(self, entity: CodeEntity, limit: int = 5) -> List[SearchResult]:
        """查找相似代码"""
        results = []
        
        for other in self.code_analyzer.entities.values():
            if other.id == entity.id:
                continue
            
            similarity = self._calculate_similarity(entity, other)
            if similarity > 0.3:
                snippet = self._get_snippet(other)
                results.append(SearchResult(
                    score=similarity,
                    entity=other,
                    snippet=snippet,
                    match_type='similar'
                ))
        
        results.sort(key=lambda x: -x.score)
        return results[:limit]
    
    def _calculate_similarity(self, entity1: CodeEntity, entity2: CodeEntity) -> float:
        """计算代码相似度"""
        score = 0
        max_score = 0
        
        # 类型相似度
        max_score += 1
        if entity1.type == entity2.type:
            score += 1
        
        # 名称相似度
        max_score += 1
        if entity1.name == entity2.name:
            score += 1
        
        # 依赖相似度
        if entity1.dependencies and entity2.dependencies:
            max_score += 2
            common_deps = set(entity1.dependencies) & set(entity2.dependencies)
            score += len(common_deps) / max(len(entity1.dependencies), len(entity2.dependencies)) * 2
        
        # 装饰器相似度
        if entity1.decorators and entity2.decorators:
            max_score += 1
            common_decorators = set(entity1.decorators) & set(entity2.decorators)
            if common_decorators:
                score += 1
        
        return score / max_score if max_score > 0 else 0