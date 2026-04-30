# -*- coding: utf-8 -*-
"""
知识库查询接口
从本地知识库获取搜索建议
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime
import asyncio

from .suggestion_model import SearchSuggestion
from .cache import get_suggestion_cache

logger = logging.getLogger(__name__)


class KnowledgeQuery:
    """知识库查询器"""
    
    def __init__(self):
        self._cache = get_suggestion_cache()
        self._knowledge_base = None  # 知识库实例
        self._initialized = False
    
    async def initialize(self):
        """初始化知识库连接"""
        if self._initialized:
            return
        
        try:
            # 尝试导入知识库
            from business.knowledge_base.unified_kb import get_knowledge_base
            self._knowledge_base = await get_knowledge_base()
            self._initialized = True
            logger.info("知识库查询器初始化成功")
        except ImportError:
            logger.warning("未找到知识库模块，使用模拟数据")
            self._initialized = True
        except Exception as e:
            logger.error(f"知识库初始化失败: {e}")
            self._initialized = True
    
    async def query(self, query: str, limit: int = 10) -> List[SearchSuggestion]:
        """
        查询知识库获取建议
        
        Args:
            query: 搜索查询
            limit: 返回数量限制
            
        Returns:
            搜索建议列表
        """
        if not query or len(query.strip()) < 1:
            return []
        
        query = query.strip().lower()
        
        # 检查缓存
        cached = self._cache.get_knowledge(query)
        if cached:
            return [SearchSuggestion(**item) for item in cached]
        
        # 执行查询
        suggestions = []
        
        if self._knowledge_base:
            try:
                suggestions = await self._query_knowledge_base(query, limit)
            except Exception as e:
                logger.warning(f"知识库查询失败: {e}")
                suggestions = self._generate_mock_suggestions(query, limit)
        else:
            suggestions = self._generate_mock_suggestions(query, limit)
        
        # 缓存结果
        if suggestions:
            self._cache.set_knowledge(query, [
                {
                    "text": s.text,
                    "source": s.source,
                    "timestamp": s.timestamp.isoformat(),
                    "score": s.score,
                    "category": s.category
                }
                for s in suggestions
            ])
        
        return suggestions
    
    async def _query_knowledge_base(self, query: str, limit: int) -> List[SearchSuggestion]:
        """查询实际知识库"""
        suggestions = []
        
        try:
            # 语义搜索
            semantic_results = await self._knowledge_base.search(
                query=query,
                limit=limit,
                mode="semantic"
            )
            
            for item in semantic_results:
                suggestions.append(SearchSuggestion(
                    text=item.get("title", item.get("content", "")[:50]),
                    source="knowledge",
                    timestamp=datetime.now(),
                    score=item.get("score", 0.5),
                    category=item.get("category", "文档")
                ))
            
            # 相关搜索（如果有）
            related = await self._knowledge_base.get_related(query, limit=3)
            for item in related:
                suggestions.append(SearchSuggestion(
                    text=item.get("text", ""),
                    source="related",
                    timestamp=datetime.now(),
                    score=item.get("score", 0.4)
                ))
                
        except Exception as e:
            logger.error(f"知识库查询异常: {e}")
        
        return suggestions
    
    def _generate_mock_suggestions(self, query: str, limit: int) -> List[SearchSuggestion]:
        """生成模拟建议（知识库不可用时）"""
        suggestions = []
        now = datetime.now()
        
        # 基于查询生成智能建议
        base_terms = query.split() if query else []
        
        # 常见搜索后缀
        suffixes = [
            "教程", "详解", "使用方法", "最佳实践", "常见问题",
            "配置", "安装", "调试", "优化", "原理"
        ]
        
        # 根据查询类型添加不同建议
        if any(term in query for term in ["python", "Python", "py"]):
            templates = [
                f"{query} 异步编程",
                f"{query} 异步 async await",
                f"{query} 并发 vs 多线程",
                f"{query} 性能优化",
                f"{query} 内存管理",
            ]
        elif any(term in query for term in ["http", "api", "rest"]):
            templates = [
                f"{query} 请求详解",
                f"{query} 请求头设置",
                f"{query} 认证方式",
                f"{query} 错误处理",
                f"{query} 性能优化",
            ]
        elif any(term in query for term in ["git", "github"]):
            templates = [
                f"{query} 使用教程",
                f"{query} 合并冲突",
                f"{query} 回退版本",
                f"{query} 分支管理",
                f"{query} 提交规范",
            ]
        else:
            templates = [
                f"{query} 是什么",
                f"{query} 怎么用",
                f"{query} 教程",
                f"{query} 详解",
                f"{query} 常见问题",
            ]
        
        # 添加搜索建议
        for i, text in enumerate(templates[:limit]):
            suggestions.append(SearchSuggestion(
                text=text,
                source="knowledge",
                timestamp=now,
                score=1.0 - (i * 0.1),  # 递减分数
                category="技术"
            ))
        
        return suggestions
    
    async def get_popular(self, limit: int = 10) -> List[SearchSuggestion]:
        """获取热门搜索建议"""
        suggestions = []
        now = datetime.now()
        
        # 模拟热门搜索
        popular_terms = [
            ("Python异步编程", 0.95),
            ("Git使用教程", 0.90),
            ("Docker部署", 0.88),
            ("RESTful API设计", 0.85),
            ("React组件开发", 0.82),
            ("MongoDB查询优化", 0.80),
            ("Redis缓存策略", 0.78),
            ("Kubernetes入门", 0.75),
            ("GraphQL vs REST", 0.72),
            ("CI/CD自动化部署", 0.70),
        ]
        
        for term, score in popular_terms[:limit]:
            suggestions.append(SearchSuggestion(
                text=term,
                source="hot",
                timestamp=now,
                score=score
            ))
        
        return suggestions
    
    async def get_related(self, query: str, limit: int = 5) -> List[SearchSuggestion]:
        """获取相关搜索建议"""
        suggestions = []
        now = datetime.now()
        
        # 相关搜索映射
        related_map = {
            "python": ["Django", "Flask", "FastAPI", "Scrapy"],
            "git": ["GitHub", "GitLab", "SVN", "版本控制"],
            "docker": ["Kubernetes", "容器化", "Dockerfile", "镜像"],
            "react": ["Vue", "Angular", "前端框架", "TypeScript"],
            "mysql": ["PostgreSQL", "MongoDB", "数据库优化", "Redis"],
        }
        
        # 查找相关词
        query_lower = query.lower()
        for key, related in related_map.items():
            if key in query_lower:
                for i, term in enumerate(related[:limit]):
                    suggestions.append(SearchSuggestion(
                        text=f"{query} {term}",
                        source="related",
                        timestamp=now,
                        score=0.8 - (i * 0.1)
                    ))
                break
        
        if not suggestions:
            # 通用相关搜索
            for i in range(limit):
                suggestions.append(SearchSuggestion(
                    text=f"{query} 相关话题{i + 1}",
                    source="related",
                    timestamp=now,
                    score=0.5 - (i * 0.05)
                ))
        
        return suggestions


# 全局实例
_query_instance: Optional[KnowledgeQuery] = None


async def get_knowledge_query() -> KnowledgeQuery:
    """获取知识库查询器实例"""
    global _query_instance
    if _query_instance is None:
        _query_instance = KnowledgeQuery()
        await _query_instance.initialize()
    return _query_instance


async def query_knowledge(query: str, limit: int = 10) -> List[SearchSuggestion]:
    """快捷函数：查询知识库"""
    kq = await get_knowledge_query()
    return await kq.query(query, limit)
