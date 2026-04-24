# -*- coding: utf-8 -*-
"""
插件商店 - Plugin Store
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set
import json

from .plugin import Plugin, PluginCategory, PluginStatus


@dataclass
class PluginListing:
    """插件列表项"""
    plugin: Plugin
    is_featured: bool = False
    is_trending: bool = False
    is_new: bool = False
    rank_score: float = 0.0
    
    def matches_search(self, query: str) -> bool:
        """搜索匹配"""
        query = query.lower()
        return (
            query in self.plugin.name.lower() or
            query in self.plugin.description.lower() or
            any(query in tag.lower() for tag in self.plugin.tags) or
            query in self.plugin.author_name.lower()
        )


class PluginStore:
    """
    插件商店
    
    管理插件的浏览、搜索、推荐
    """
    
    def __init__(self):
        self._plugins: Dict[str, Plugin] = {}  # plugin_id -> Plugin
        self._categories: Dict[PluginCategory, List[str]] = {}  # category -> plugin_ids
        self._slugs: Dict[str, str] = {}  # slug -> plugin_id
        self._featured_ids: Set[str] = set()
        self._trending_ids: Set[str] = set()
        self._tags_index: Dict[str, Set[str]] = {}  # tag -> plugin_ids
    
    def register_plugin(self, plugin: Plugin) -> bool:
        """注册插件"""
        if not plugin.id or not plugin.slug:
            return False
        
        if plugin.id in self._plugins:
            return False
        
        if plugin.slug in self._slugs:
            return False
        
        self._plugins[plugin.id] = plugin
        self._slugs[plugin.slug] = plugin.id
        
        # 分类索引
        if plugin.category not in self._categories:
            self._categories[plugin.category] = []
        self._categories[plugin.category].append(plugin.id)
        
        # 标签索引
        for tag in plugin.tags:
            if tag not in self._tags_index:
                self._tags_index[tag] = set()
            self._tags_index[tag].add(plugin.id)
        
        return True
    
    def get_plugin(self, plugin_id: str) -> Optional[Plugin]:
        """获取插件"""
        return self._plugins.get(plugin_id)
    
    def get_plugin_by_slug(self, slug: str) -> Optional[Plugin]:
        """通过 slug 获取插件"""
        pid = self._slugs.get(slug)
        return self._plugins.get(pid) if pid else None
    
    def get_all_plugins(
        self,
        status: Optional[PluginStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Plugin]:
        """获取所有插件"""
        plugins = list(self._plugins.values())
        
        if status:
            plugins = [p for p in plugins if p.status == status]
        
        # 排序：featured > trending > downloads
        plugins.sort(key=lambda p: (
            not p.is_featured,
            not (p.id in self._trending_ids),
            -p.downloads
        ))
        
        return plugins[offset:offset + limit]
    
    def get_by_category(
        self,
        category: PluginCategory,
        limit: int = 50
    ) -> List[Plugin]:
        """按分类获取"""
        plugin_ids = self._categories.get(category, [])
        plugins = [self._plugins[pid] for pid in plugin_ids if pid in self._plugins]
        return plugins[:limit]
    
    def get_featured(self, limit: int = 10) -> List[Plugin]:
        """获取精选插件"""
        plugins = [
            self._plugins[pid] for pid in self._featured_ids
            if pid in self._plugins
        ]
        return plugins[:limit]
    
    def get_trending(self, limit: int = 20) -> List[Plugin]:
        """获取热门插件"""
        plugin_ids = list(self._trending_ids)
        plugins = [self._plugins[pid] for pid in plugin_ids if pid in self._plugins]
        
        # 按下载量排序
        plugins.sort(key=lambda p: -p.downloads)
        return plugins[:limit]
    
    def get_new(self, limit: int = 20) -> List[Plugin]:
        """获取新插件"""
        plugins = [
            p for p in self._plugins.values()
            if p.status == PluginStatus.APPROVED
        ]
        
        # 按创建时间排序
        plugins.sort(key=lambda p: -p.created_at.timestamp())
        return plugins[:limit]
    
    def search(
        self,
        query: str,
        category: Optional[PluginCategory] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[Plugin]:
        """搜索插件"""
        query = query.lower()
        results = []
        
        for plugin in self._plugins.values():
            if plugin.status != PluginStatus.APPROVED:
                continue
            
            # 分类过滤
            if category and plugin.category != category:
                continue
            
            # 标签过滤
            if tags:
                if not any(tag in plugin.tags for tag in tags):
                    continue
            
            # 全文搜索
            score = self._calculate_relevance(plugin, query)
            if score > 0:
                results.append((plugin, score))
        
        # 按相关性排序
        results.sort(key=lambda x: -x[1])
        return [p for p, _ in results[:limit]]
    
    def _calculate_relevance(self, plugin: Plugin, query: str) -> float:
        """计算相关性分数"""
        score = 0.0
        
        # 名称匹配（最高权重）
        if query in plugin.name.lower():
            score += 10.0
        elif query in plugin.name.lower().split():
            score += 5.0
        
        # 描述匹配
        if query in plugin.description.lower():
            score += 3.0
        
        # 标签匹配
        for tag in plugin.tags:
            if query in tag.lower():
                score += 2.0
        
        # 作者匹配
        if query in plugin.author_name.lower():
            score += 1.0
        
        # 人气加成
        if plugin.downloads > 10000:
            score *= 1.2
        elif plugin.downloads > 1000:
            score *= 1.1
        
        # 评分加成
        if plugin.rating >= 4.5:
            score *= 1.1
        
        return score
    
    def get_by_tag(self, tag: str, limit: int = 50) -> List[Plugin]:
        """按标签获取"""
        plugin_ids = self._tags_index.get(tag, set())
        plugins = [self._plugins[pid] for pid in plugin_ids if pid in self._plugins]
        return plugins[:limit]
    
    def get_related(self, plugin_id: str, limit: int = 5) -> List[Plugin]:
        """获取相关插件"""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return []
        
        # 同分类
        related = self.get_by_category(plugin.category, limit * 2)
        
        # 移除自身
        related = [p for p in related if p.id != plugin_id]
        
        # 相关标签优先
        def tag_overlap(p: Plugin) -> int:
            return len(set(p.tags) & set(plugin.tags))
        
        related.sort(key=lambda p: -tag_overlap(p))
        return related[:limit]
    
    def set_featured(self, plugin_id: str, featured: bool = True):
        """设置精选"""
        if featured:
            self._featured_ids.add(plugin_id)
        else:
            self._featured_ids.discard(plugin_id)
    
    def set_trending(self, plugin_id: str, trending: bool = True):
        """设置热门"""
        if trending:
            self._trending_ids.add(plugin_id)
        else:
            self._trending_ids.discard(plugin_id)
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        approved = [p for p in self._plugins.values() if p.status == PluginStatus.APPROVED]
        
        category_stats = {}
        for cat in PluginCategory:
            category_stats[cat.value] = len(self._categories.get(cat, []))
        
        return {
            "total_plugins": len(self._plugins),
            "approved_plugins": len(approved),
            "total_downloads": sum(p.downloads for p in approved),
            "average_rating": sum(p.rating for p in approved) / len(approved) if approved else 0,
            "category_distribution": category_stats,
            "featured_count": len(self._featured_ids),
            "trending_count": len(self._trending_ids)
        }
    
    # ── 预加载示例插件 ──────────────────────────────────────────────────────────
    
    def load_sample_plugins(self):
        """加载示例插件"""
        samples = [
            {
                "id": "github-integration",
                "name": "GitHub Integration",
                "slug": "github-integration",
                "description": "集成 GitHub，查看 PR、Issue 和代码",
                "category": "integration",
                "tags": ["github", "code", "version-control"],
                "author_name": "Hermes Team",
                "downloads": 15420,
                "rating": 4.8,
                "is_featured": True
            },
            {
                "id": "slack-notify",
                "name": "Slack 通知",
                "slug": "slack-notify",
                "description": "将通知推送到 Slack 频道",
                "category": "communication",
                "tags": ["slack", "notification", "team"],
                "author_name": "Hermes Team",
                "downloads": 8930,
                "rating": 4.6
            },
            {
                "id": "data-visualizer",
                "name": "数据可视化",
                "slug": "data-visualizer",
                "description": "图表生成和数据分析",
                "category": "data_viz",
                "tags": ["chart", "visualization", "analytics"],
                "author_name": "Hermes Team",
                "downloads": 12300,
                "rating": 4.7,
                "is_featured": True
            },
            {
                "id": "auto-task",
                "name": "自动任务",
                "slug": "auto-task",
                "description": "基于规则的自动化工作流",
                "category": "automation",
                "tags": ["automation", "workflow", "tasks"],
                "author_name": "Hermes Team",
                "downloads": 7650,
                "rating": 4.5
            }
        ]
        
        for data in samples:
            plugin = Plugin.from_dict(data)
            plugin.status = PluginStatus.APPROVED
            self.register_plugin(plugin)
            
            if data.get('is_featured'):
                self.set_featured(plugin.id)


# ── 全局实例 ──────────────────────────────────────────────────────────────────

_plugin_store: Optional[PluginStore] = None


def get_plugin_store() -> PluginStore:
    """获取插件商店"""
    global _plugin_store
    if _plugin_store is None:
        _plugin_store = PluginStore()
        _plugin_store.load_sample_plugins()
    return _plugin_store
