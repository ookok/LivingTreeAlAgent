# -*- coding: utf-8 -*-
"""
智能搜索建议模块
类似百度搜索建议的智能联想功能

功能：
- 实时联想（300ms 防抖）
- 10行纵向排列
- 按时间排序（最新的在前）
- 调用知识库获取建议
- 键盘导航支持
"""

from .suggestion_model import (
    SearchSuggestion,
    SuggestionManager,
    get_suggestion_manager,
    add_search_history,
    get_suggestions,
)
from .suggestion_popup import (
    SearchSuggestionPopup,
    SuggestionListWidget,
    SuggestionController,
)
from .knowledge_query import (
    KnowledgeQuery,
    get_knowledge_query,
    query_knowledge,
)
from .cache import (
    LRUCache,
    SuggestionCache,
    get_suggestion_cache,
)

__all__ = [
    # 数据模型
    'SearchSuggestion',
    'SuggestionManager',
    'get_suggestion_manager',
    'add_search_history',
    'get_suggestions',
    
    # UI 组件
    'SearchSuggestionPopup',
    'SuggestionListWidget',
    'SuggestionController',
    
    # 知识库查询
    'KnowledgeQuery',
    'get_knowledge_query',
    'query_knowledge',
    
    # 缓存
    'LRUCache',
    'SuggestionCache',
    'get_suggestion_cache',
]
