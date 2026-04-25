# search.py — 全局搜索
# ============================================================================
#
# 负责全局搜索功能
# 支持搜索应用、功能、内容等
#
# ============================================================================

import re
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any
from enum import Enum

# ============================================================================
# 数据结构
# ============================================================================

class SearchCategory(Enum):
    """搜索类别"""

from core.logger import get_logger
logger = get_logger('desktop_environment.search')
    APP = "app"               # 应用
    FEATURE = "feature"      # 功能
    SETTING = "setting"       # 设置
    FILE = "file"            # 文件
    NETWORK = "network"      # 网络内容
    COMMAND = "command"      # 命令
    ALL = "all"              # 所有

@dataclass
class SearchResult:
    """搜索结果"""
    id: str                          # 结果 ID
    title: str                       # 标题
    description: str = ""             # 描述
    category: SearchCategory = SearchCategory.ALL  # 类别
    icon: str = ""                    # 图标
    url: str = ""                    # URL 或路径
    score: float = 0.0               # 匹配分数
    keywords: List[str] = field(default_factory=list)  # 关键词
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    action: Dict[str, Any] = field(default_factory=dict)  # 执行动作

# ============================================================================
# 全局搜索
# ============================================================================

class GlobalSearch:
    """
    全局搜索

    功能:
    1. 搜索已安装应用
    2. 搜索系统功能
    3. 搜索设置项
    4. 搜索网络内容 (通过智能路由)
    5. 搜索快捷命令
    6. 模糊匹配和排名
    """

    def __init__(self):
        # 搜索索引
        self._index: List[SearchResult] = []

        # 提供者
        self._providers: Dict[SearchCategory, Callable] = {}

        # 回调
        self._on_result_selected: Optional[Callable] = None

    # --------------------------------------------------------------------------
    # 索引管理
    # --------------------------------------------------------------------------

    def add_to_index(self, result: SearchResult):
        """添加到搜索索引"""
        # 避免重复
        for existing in self._index:
            if existing.id == result.id and existing.category == result.category:
                return
        self._index.append(result)

    def remove_from_index(self, result_id: str, category: SearchCategory = None):
        """从索引移除"""
        if category:
            self._index = [
                r for r in self._index
                if not (r.id == result_id and r.category == category)
            ]
        else:
            self._index = [r for r in self._index if r.id != result_id]

    def clear_index(self):
        """清空索引"""
        self._index.clear()

    def get_index(self) -> List[SearchResult]:
        """获取索引"""
        return self._index.copy()

    # --------------------------------------------------------------------------
    # 提供者管理
    # --------------------------------------------------------------------------

    def register_provider(
        self,
        category: SearchCategory,
        provider: Callable[[str], List[SearchResult]]
    ):
        """
        注册搜索提供者

        Args:
            category: 搜索类别
            provider: 提供者函数，输入搜索词，返回结果列表
        """
        self._providers[category] = provider

    def unregister_provider(self, category: SearchCategory):
        """注销提供者"""
        self._providers.pop(category, None)

    # --------------------------------------------------------------------------
    # 搜索
    # --------------------------------------------------------------------------

    def search(
        self,
        query: str,
        categories: List[SearchCategory] = None,
        limit: int = 20
    ) -> List[SearchResult]:
        """
        搜索

        Args:
            query: 搜索词
            categories: 搜索类别列表，None 表示所有
            limit: 返回结果数量限制

        Returns:
            搜索结果列表 (已排序)
        """
        if not query:
            return []

        categories = categories or [SearchCategory.ALL]

        results = []

        # 从索引搜索
        if SearchCategory.ALL in categories or SearchCategory.APP in categories:
            results.extend(self._search_index(query, SearchCategory.APP))

        if SearchCategory.ALL in categories or SearchCategory.FEATURE in categories:
            results.extend(self._search_index(query, SearchCategory.FEATURE))

        if SearchCategory.ALL in categories or SearchCategory.SETTING in categories:
            results.extend(self._search_index(query, SearchCategory.SETTING))

        if SearchCategory.ALL in categories or SearchCategory.COMMAND in categories:
            results.extend(self._search_index(query, SearchCategory.COMMAND))

        # 调用提供者获取动态结果
        for category, provider in self._providers.items():
            if category in categories or SearchCategory.ALL in categories:
                try:
                    provider_results = provider(query)
                    results.extend(provider_results)
                except Exception as e:
                    logger.info(f"Search provider {category} failed: {e}")

        # 去重
        seen = set()
        unique_results = []
        for r in results:
            key = (r.id, r.category)
            if key not in seen:
                seen.add(key)
                unique_results.append(r)

        # 排序
        unique_results.sort(key=lambda r: r.score, reverse=True)

        # 限制数量
        return unique_results[:limit]

    def _search_index(
        self,
        query: str,
        category: SearchCategory
    ) -> List[SearchResult]:
        """在索引中搜索"""
        query_lower = query.lower()
        query_terms = query_lower.split()
        results = []

        for item in self._index:
            if item.category != category:
                continue

            score = 0.0

            # 标题匹配
            title_lower = item.title.lower()
            if query_lower in title_lower:
                score += 10.0
                if title_lower.startswith(query_lower):
                    score += 5.0

            # 关键词匹配
            for term in query_terms:
                if term in title_lower:
                    score += 3.0
                if term in item.description.lower():
                    score += 1.0
                for keyword in item.keywords:
                    if term in keyword.lower():
                        score += 2.0

            # 模糊匹配
            if not score:
                if self._fuzzy_match(query_lower, title_lower):
                    score = 0.5

            if score > 0:
                result = SearchResult(
                    id=item.id,
                    title=item.title,
                    description=item.description,
                    category=item.category,
                    icon=item.icon,
                    url=item.url,
                    score=score,
                    keywords=item.keywords,
                    metadata=item.metadata,
                    action=item.action
                )
                results.append(result)

        return results

    def _fuzzy_match(self, query: str, text: str) -> bool:
        """模糊匹配"""
        # 简单的包含检查
        return query in text

    # --------------------------------------------------------------------------
    # 快捷搜索
    # --------------------------------------------------------------------------

    def quick_search(self, query: str) -> List[SearchResult]:
        """快速搜索 (限制结果数量)"""
        return self.search(query, limit=5)

    def search_apps(self, query: str) -> List[SearchResult]:
        """搜索应用"""
        return self.search(query, categories=[SearchCategory.APP])

    def search_features(self, query: str) -> List[SearchResult]:
        """搜索功能"""
        return self.search(query, categories=[SearchCategory.FEATURE])

    def search_settings(self, query: str) -> List[SearchResult]:
        """搜索设置"""
        return self.search(query, categories=[SearchCategory.SETTING])

    # --------------------------------------------------------------------------
    # 动作执行
    # --------------------------------------------------------------------------

    def execute_result(self, result: SearchResult) -> bool:
        """执行搜索结果动作"""
        if self._on_result_selected:
            return self._on_result_selected(result)

        # 默认动作
        action = result.action
        if not action:
            return False

        action_type = action.get("type")

        if action_type == "open_app":
            app_id = action.get("app_id")
            if app_id:
                from .app_manager import get_app_manager

                app_manager = get_app_manager()
                app_manager.start_app(app_id)
                return True

        elif action_type == "open_window":
            window_type = action.get("window")
            if window_type:
                # TODO: 打开指定窗口
                pass

        elif action_type == "run_command":
            command = action.get("command")
            if command:
                # TODO: 执行命令
                pass

        elif action_type == "navigate":
            url = action.get("url")
            if url:
                # TODO: 导航到 URL
                pass

        return False

    # --------------------------------------------------------------------------
    # 索引构建
    # --------------------------------------------------------------------------

    def build_index_from_apps(self, apps: List[Any]):
        """从应用列表构建索引"""
        for app in apps:
            result = SearchResult(
                id=app.id,
                title=app.name,
                description=app.description,
                category=SearchCategory.APP,
                icon=app.icon,
                url=f"app://{app.id}",
                keywords=app.tags,
                action={
                    "type": "open_app",
                    "app_id": app.id
                }
            )
            self.add_to_index(result)

    def build_index_from_commands(self, commands: List[Dict]):
        """从命令列表构建索引"""
        for cmd in commands:
            result = SearchResult(
                id=cmd["id"],
                title=cmd["name"],
                description=cmd.get("description", ""),
                category=SearchCategory.COMMAND,
                keywords=cmd.get("keywords", []),
                action={
                    "type": "run_command",
                    "command": cmd.get("command")
                }
            )
            self.add_to_index(result)

    # --------------------------------------------------------------------------
    # 事件
    # --------------------------------------------------------------------------

    def set_on_result_selected(self, callback: Callable[[SearchResult], bool]):
        """设置结果选择回调"""
        self._on_result_selected = callback