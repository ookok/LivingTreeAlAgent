"""
上下文模式管理器 (Context Mode Manager)
======================================

参考 Context Mode 项目理念，实现智能上下文管理：
1. 自动模式 - 智能检测上下文需求
2. 手动模式 - 用户手动选择上下文
3. 选择性模式 - 基于意图的智能选择

核心特性：
- 多模式上下文管理
- 智能意图识别
- 上下文优先级排序
- 自动上下文收集

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import re
import asyncio
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = __import__('logging').getLogger(__name__)


class ContextMode(Enum):
    """上下文模式"""
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    SELECTIVE = "selective"


class ContextSource(Enum):
    """上下文来源"""
    CURRENT_FILE = "current_file"
    RECENT_FILES = "recent_files"
    PROJECT_STRUCTURE = "project_structure"
    CODE_HISTORY = "code_history"
    CHAT_HISTORY = "chat_history"
    DOCUMENTATION = "documentation"
    EXTERNAL_KNOWLEDGE = "external_knowledge"
    USER_DEFINED = "user_defined"


class ContextPriority(Enum):
    """上下文优先级"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class ContextItem:
    """上下文项"""
    id: str
    source: ContextSource
    title: str
    content: str
    priority: ContextPriority
    relevance_score: float = 0.0
    last_accessed: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextSuggestion:
    """上下文建议"""
    query_intent: str
    suggested_sources: List[ContextSource]
    recommended_contexts: List[ContextItem]
    excluded_contexts: List[ContextSource]
    explanation: str = ""


class ContextModeManager:
    """
    上下文模式管理器
    
    功能：
    1. 管理上下文模式切换
    2. 智能意图识别
    3. 上下文优先级排序
    4. 自动上下文收集
    """
    
    def __init__(self):
        # 当前模式
        self._current_mode = ContextMode.AUTOMATIC
        
        # 上下文存储
        self._context_items: List[ContextItem] = []
        
        # 意图关键词映射
        self._intent_keywords = {
            "code_understanding": ["解释", "理解", "什么意思", "什么是", "说明", "describe", "explain"],
            "code_modification": ["修改", "更改", "编辑", "调整", "update", "modify", "change"],
            "bug_fixing": ["bug", "错误", "修复", "问题", "fix", "debug"],
            "code_generation": ["写", "创建", "生成", "实现", "write", "create", "generate"],
            "code_review": ["审查", "检查", "review", "audit"],
            "testing": ["测试", "test", "单元测试", "testcase"],
            "documentation": ["文档", "注释", "doc", "document"],
            "refactoring": ["重构", "优化", "refactor", "optimize"],
            "search": ["搜索", "查找", "search", "find"],
            "configuration": ["配置", "设置", "config", "setting"],
        }
        
        # 意图到上下文源的映射
        self._intent_context_map = {
            "code_understanding": [ContextSource.CURRENT_FILE, ContextSource.DOCUMENTATION],
            "code_modification": [ContextSource.CURRENT_FILE, ContextSource.RECENT_FILES, ContextSource.CODE_HISTORY],
            "bug_fixing": [ContextSource.CURRENT_FILE, ContextSource.CODE_HISTORY, ContextSource.CHAT_HISTORY],
            "code_generation": [ContextSource.PROJECT_STRUCTURE, ContextSource.EXTERNAL_KNOWLEDGE],
            "code_review": [ContextSource.CURRENT_FILE, ContextSource.RECENT_FILES],
            "testing": [ContextSource.CURRENT_FILE, ContextSource.RECENT_FILES],
            "documentation": [ContextSource.CURRENT_FILE, ContextSource.DOCUMENTATION],
            "refactoring": [ContextSource.CURRENT_FILE, ContextSource.PROJECT_STRUCTURE],
            "search": [ContextSource.PROJECT_STRUCTURE, ContextSource.EXTERNAL_KNOWLEDGE],
            "configuration": [ContextSource.PROJECT_STRUCTURE, ContextSource.DOCUMENTATION],
        }
        
        logger.info("[ContextModeManager] 上下文模式管理器初始化完成")
    
    def set_mode(self, mode: str):
        """
        设置上下文模式
        
        Args:
            mode: 模式名称（automatic/manual/selective）
        """
        try:
            self._current_mode = ContextMode(mode)
            logger.info(f"[ContextModeManager] 上下文模式已设置为: {mode}")
        except ValueError:
            logger.error(f"[ContextModeManager] 无效的上下文模式: {mode}")
    
    def get_mode(self) -> ContextMode:
        """获取当前模式"""
        return self._current_mode
    
    def get_modes(self) -> List[str]:
        """获取所有可用模式"""
        return [mode.value for mode in ContextMode]
    
    def get_suggestion(self, query: str) -> Dict[str, Any]:
        """
        获取上下文建议
        
        Args:
            query: 用户查询
            
        Returns:
            上下文建议
        """
        # 识别意图
        intent = self._recognize_intent(query)
        
        # 获取建议的上下文源
        suggested_sources = self._intent_context_map.get(intent, [])
        
        # 获取推荐的上下文
        recommended_contexts = self._get_recommended_contexts(intent, query)
        
        # 排除的上下文
        excluded_contexts = [
            src for src in ContextSource 
            if src not in suggested_sources
        ]
        
        suggestion = ContextSuggestion(
            query_intent=intent,
            suggested_sources=suggested_sources,
            recommended_contexts=recommended_contexts,
            excluded_contexts=excluded_contexts,
            explanation=self._generate_explanation(intent, query),
        )
        
        return {
            "intent": suggestion.query_intent,
            "suggested_sources": [s.value for s in suggestion.suggested_sources],
            "recommended_contexts": [self._context_item_to_dict(c) for c in suggestion.recommended_contexts],
            "excluded_contexts": [s.value for s in suggestion.excluded_contexts],
            "explanation": suggestion.explanation,
        }
    
    def _recognize_intent(self, query: str) -> str:
        """
        识别用户意图
        
        Args:
            query: 用户查询
            
        Returns:
            意图名称
        """
        query_lower = query.lower()
        
        # 匹配意图关键词
        for intent, keywords in self._intent_keywords.items():
            for keyword in keywords:
                if keyword.lower() in query_lower:
                    return intent
        
        # 默认返回通用意图
        return "search"
    
    def _get_recommended_contexts(self, intent: str, query: str) -> List[ContextItem]:
        """
        获取推荐的上下文
        
        Args:
            intent: 用户意图
            query: 用户查询
            
        Returns:
            推荐的上下文项列表
        """
        recommended = []
        
        # 根据意图过滤上下文
        for item in self._context_items:
            if item.source in self._intent_context_map.get(intent, []):
                # 计算相关性
                relevance = self._calculate_relevance(item, query)
                item.relevance_score = relevance
                
                if relevance > 0.3:
                    recommended.append(item)
        
        # 按相关性排序
        recommended.sort(key=lambda x: x.relevance_score, reverse=True)
        
        # 返回前5个
        return recommended[:5]
    
    def _calculate_relevance(self, item: ContextItem, query: str) -> float:
        """
        计算上下文相关性
        
        Args:
            item: 上下文项
            query: 用户查询
            
        Returns:
            相关性分数 (0-1)
        """
        score = 0.0
        query_lower = query.lower()
        
        # 标题匹配
        if query_lower in item.title.lower():
            score += 0.3
        
        # 内容匹配
        if query_lower in item.content.lower():
            score += 0.4
        
        # 关键词匹配
        for keyword in self._intent_keywords.get("search", []):
            if keyword.lower() in item.title.lower() or keyword.lower() in item.content.lower():
                score += 0.1
        
        # 优先级加成
        if item.priority == ContextPriority.CRITICAL:
            score += 0.2
        elif item.priority == ContextPriority.HIGH:
            score += 0.1
        
        return min(1.0, score)
    
    def _generate_explanation(self, intent: str, query: str) -> str:
        """
        生成解释说明
        
        Args:
            intent: 用户意图
            query: 用户查询
            
        Returns:
            解释文本
        """
        explanations = {
            "code_understanding": "检测到您需要理解代码，已为您准备当前文件和相关文档。",
            "code_modification": "检测到您需要修改代码，已为您准备当前文件和最近文件历史。",
            "bug_fixing": "检测到您需要修复问题，已为您准备相关代码历史和聊天记录。",
            "code_generation": "检测到您需要生成代码，已为您准备项目结构和外部知识库。",
            "code_review": "检测到您需要审查代码，已为您准备当前文件和相关文件。",
            "testing": "检测到您需要编写测试，已为您准备相关代码文件。",
            "documentation": "检测到您需要编写文档，已为您准备当前文件和文档模板。",
            "refactoring": "检测到您需要重构代码，已为您准备当前文件和项目结构。",
            "search": "正在为您搜索相关上下文...",
            "configuration": "检测到您需要配置设置，已为您准备项目结构和配置文档。",
        }
        
        return explanations.get(intent, "正在为您准备相关上下文...")
    
    async def collect_context(self, sources: Optional[List[ContextSource]] = None) -> List[ContextItem]:
        """
        收集上下文
        
        Args:
            sources: 上下文源列表（可选，默认收集所有）
            
        Returns:
            上下文项列表
        """
        if sources is None:
            sources = list(ContextSource)
        
        collected = []
        
        for source in sources:
            items = await self._collect_from_source(source)
            collected.extend(items)
        
        # 更新存储
        self._context_items.extend(collected)
        
        return collected
    
    async def _collect_from_source(self, source: ContextSource) -> List[ContextItem]:
        """
        从指定源收集上下文
        
        Args:
            source: 上下文源
            
        Returns:
            上下文项列表
        """
        items = []
        
        # 根据源类型生成模拟数据
        if source == ContextSource.CURRENT_FILE:
            items.append(ContextItem(
                id="current_file",
                source=source,
                title="当前文件",
                content="这是当前正在编辑的文件内容...",
                priority=ContextPriority.CRITICAL,
            ))
        
        elif source == ContextSource.RECENT_FILES:
            items.append(ContextItem(
                id="recent_1",
                source=source,
                title="最近文件 1",
                content="最近打开的文件内容...",
                priority=ContextPriority.HIGH,
            ))
        
        elif source == ContextSource.PROJECT_STRUCTURE:
            items.append(ContextItem(
                id="project_structure",
                source=source,
                title="项目结构",
                content="项目目录结构...",
                priority=ContextPriority.MEDIUM,
            ))
        
        elif source == ContextSource.CHAT_HISTORY:
            items.append(ContextItem(
                id="chat_history",
                source=source,
                title="聊天历史",
                content="最近的聊天记录摘要...",
                priority=ContextPriority.MEDIUM,
            ))
        
        elif source == ContextSource.DOCUMENTATION:
            items.append(ContextItem(
                id="documentation",
                source=source,
                title="文档",
                content="相关文档内容...",
                priority=ContextPriority.LOW,
            ))
        
        return items
    
    def add_context_item(self, item: ContextItem):
        """
        添加上下文项
        
        Args:
            item: 上下文项
        """
        self._context_items.append(item)
    
    def remove_context_item(self, item_id: str):
        """
        移除上下文项
        
        Args:
            item_id: 上下文项ID
        """
        self._context_items = [item for item in self._context_items if item.id != item_id]
    
    def clear_context(self):
        """清空所有上下文"""
        self._context_items.clear()
    
    def get_context_items(self) -> List[ContextItem]:
        """获取所有上下文项"""
        return self._context_items
    
    def filter_context(self, sources: List[ContextSource]) -> List[ContextItem]:
        """
        根据源过滤上下文
        
        Args:
            sources: 上下文源列表
            
        Returns:
            过滤后的上下文项列表
        """
        return [item for item in self._context_items if item.source in sources]
    
    def _context_item_to_dict(self, item: ContextItem) -> Dict[str, Any]:
        """将上下文项转换为字典"""
        return {
            "id": item.id,
            "source": item.source.value,
            "title": item.title,
            "priority": item.priority.value,
            "relevance_score": item.relevance_score,
        }


# 便捷函数
def create_context_mode_manager() -> ContextModeManager:
    """创建上下文模式管理器实例"""
    return ContextModeManager()


__all__ = [
    "ContextMode",
    "ContextSource",
    "ContextPriority",
    "ContextItem",
    "ContextSuggestion",
    "ContextModeManager",
    "create_context_mode_manager",
]
