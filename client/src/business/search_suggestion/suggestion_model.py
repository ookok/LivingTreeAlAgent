# -*- coding: utf-8 -*-
"""
搜索建议数据模型
定义联想建议的数据结构和排序逻辑
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional
import heapq


@dataclass
class SearchSuggestion:
    """搜索建议项"""
    
    text: str                    # 建议文本
    source: str                  # 来源: 'history' | 'knowledge' | 'hot' | 'related'
    timestamp: datetime          # 创建时间
    score: float = 0.0          # 相关性分数
    search_count: int = 0       # 搜索次数
    category: Optional[str] = None  # 分类标签
    
    @property
    def time_weight(self) -> float:
        """计算时间权重（越新越高）"""
        now = datetime.now()
        diff = now - self.timestamp
        
        if diff < timedelta(hours=1):
            return 1.0  # 1小时内
        elif diff < timedelta(hours=24):
            return 0.9  # 1天内
        elif diff < timedelta(days=7):
            return 0.7  # 1周内
        elif diff < timedelta(days=30):
            return 0.5  # 1月内
        else:
            return 0.3  # 更早
    
    @property
    def final_score(self) -> float:
        """综合评分 = 相关性 * 时间权重 * 热度"""
        heat_factor = 1.0 + min(self.search_count / 100, 1.0) * 0.5
        return self.score * self.time_weight * heat_factor
    
    @property
    def time_label(self) -> str:
        """友好的时间标签"""
        now = datetime.now()
        diff = now - self.timestamp
        
        if diff < timedelta(minutes=5):
            return "刚刚"
        elif diff < timedelta(hours=1):
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes}分钟前"
        elif diff < timedelta(hours=24):
            hours = int(diff.total_seconds() / 3600)
            return f"{hours}小时前"
        elif diff < timedelta(days=7):
            days = diff.days
            return f"{days}天前"
        elif diff < timedelta(days=30):
            weeks = diff.days // 7
            return f"{weeks}周前"
        else:
            return self.timestamp.strftime("%m-%d")
    
    def matches_query(self, query: str) -> bool:
        """检查是否匹配查询"""
        q = query.lower().strip()
        t = self.text.lower()
        
        # 前缀匹配
        if t.startswith(q):
            return True
        # 包含匹配
        if q in t:
            return True
        # 拼音首字母匹配
        if self._match_pinyin_initial(q, t):
            return True
        return False
    
    @staticmethod
    def _match_pinyin_initial(query: str, text: str) -> bool:
        """简单的拼音首字母匹配"""
        # 简化的拼音首字母
        pinyin_map = {
            'a': '啊', 'b': '不', 'c': '从', 'd': '的', 'e': '恶',
            'f': '发', 'g': '个', 'h': '和', 'i': '一', 'j': '就',
            'k': '可', 'l': '了', 'm': '么', 'n': '你', 'o': '哦',
            'p': '批', 'q': '去', 'r': '如', 's': '是', 't': '他',
            'u': '无', 'v': '为', 'w': '我', 'x': '想', 'y': '一', 'z': '在'
        }
        
        query_initial = ''.join(c for c in query if c.isalpha() or c.isdigit())
        if not query_initial:
            return False
        
        # 检查文本中是否包含拼音首字母对应的汉字
        for char in text[:len(query_initial)]:
            for initial, chars in pinyin_map.items():
                if char in chars and initial == query_initial[0]:
                    return True
        return False


class SuggestionManager:
    """建议管理器 - 负责收集、排序、去重"""
    
    def __init__(self, max_results: int = 10):
        self.max_results = max_results
        self._history: List[SearchSuggestion] = []
        self._max_history = 1000
    
    def add_from_history(self, query: str, timestamp: datetime = None):
        """添加历史搜索"""
        suggestion = SearchSuggestion(
            text=query,
            source='history',
            timestamp=timestamp or datetime.now(),
            score=1.0,
            search_count=self._count_search(query)
        )
        self._add(suggestion)
    
    def add_from_knowledge(self, text: str, score: float = 0.5, 
                          category: str = None):
        """添加知识库结果"""
        suggestion = SearchSuggestion(
            text=text,
            source='knowledge',
            timestamp=datetime.now(),
            score=score,
            category=category
        )
        self._add(suggestion)
    
    def add_from_hot(self, text: str, score: float = 0.8):
        """添加热门搜索"""
        suggestion = SearchSuggestion(
            text=text,
            source='hot',
            timestamp=datetime.now(),
            score=score
        )
        self._add(suggestion)
    
    def add_from_related(self, text: str, score: float = 0.6):
        """添加相关搜索"""
        suggestion = SearchSuggestion(
            text=text,
            source='related',
            timestamp=datetime.now(),
            score=score
        )
        self._add(suggestion)
    
    def _add(self, suggestion: SearchSuggestion):
        """添加建议（去重）"""
        # 检查是否已存在
        for existing in self._history:
            if existing.text == suggestion.text:
                # 更新分数和时间
                if suggestion.final_score > existing.final_score:
                    existing.score = suggestion.score
                    existing.timestamp = suggestion.timestamp
                existing.search_count += 1
                return
        
        self._history.append(suggestion)
        
        # 限制历史大小
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
    
    def _count_search(self, query: str) -> int:
        """统计搜索次数"""
        count = 0
        for item in self._history:
            if item.text == query:
                count += item.search_count
        return count
    
    def get_suggestions(self, query: str, limit: int = None) -> List[SearchSuggestion]:
        """获取排序后的建议列表"""
        if not query or len(query.strip()) < 1:
            return []
        
        limit = limit or self.max_results
        
        # 过滤匹配的建议
        matched = [s for s in self._history if s.matches_query(query)]
        
        # 按综合评分排序（时间最新的优先）
        sorted_suggestions = sorted(
            matched,
            key=lambda x: (x.final_score, x.time_weight),
            reverse=True
        )
        
        return sorted_suggestions[:limit]
    
    def get_recent(self, limit: int = 10) -> List[SearchSuggestion]:
        """获取最近搜索（不排序）"""
        sorted_history = sorted(
            self._history,
            key=lambda x: x.timestamp,
            reverse=True
        )
        # 去重
        seen = set()
        result = []
        for s in sorted_history:
            if s.text not in seen:
                seen.add(s.text)
                result.append(s)
                if len(result) >= limit:
                    break
        return result


# 全局实例
_manager = SuggestionManager()


def get_suggestion_manager() -> SuggestionManager:
    """获取全局建议管理器"""
    return _manager


def add_search_history(query: str):
    """添加搜索历史（快捷函数）"""
    _manager.add_from_history(query)


def get_suggestions(query: str, limit: int = 10) -> List[SearchSuggestion]:
    """获取搜索建议（快捷函数）"""
    return _manager.get_suggestions(query, limit)
