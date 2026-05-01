"""
Knowledge Timeline

知识时间线模块，支持追踪实体和页面的演变历史。

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TimelineEvent:
    """时间线事件"""
    id: str
    type: str  # create, update, delete, tag_add, tag_remove, link_add, link_remove
    page_id: str
    page_title: str
    author: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    description: str = ""
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    revision_number: int = 1


@dataclass
class TimelineEntry:
    """时间线条目"""
    date: str
    events: List[TimelineEvent] = field(default_factory=list)


class KnowledgeTimeline:
    """
    知识时间线
    
    核心功能：
    - 追踪页面变化历史
    - 展示实体演变过程
    - 版本对比
    """
    
    def __init__(self):
        """初始化知识时间线"""
        self._events: List[TimelineEvent] = []
        self._page_events: Dict[str, List[TimelineEvent]] = {}
        self._wiki_core = None
        
        self._init_dependencies()
        logger.info("KnowledgeTimeline 初始化完成")
    
    def _init_dependencies(self):
        """初始化依赖模块"""
        try:
            from .wiki_core import WikiCore
            self._wiki_core = WikiCore()
            logger.info("依赖模块加载成功")
        except ImportError as e:
            logger.warning(f"依赖模块加载失败: {e}")
    
    def add_event(self, event: TimelineEvent):
        """
        添加事件
        
        Args:
            event: 时间线事件
        """
        self._events.append(event)
        
        if event.page_id not in self._page_events:
            self._page_events[event.page_id] = []
        self._page_events[event.page_id].append(event)
        
        logger.debug(f"时间线事件添加: {event.type} - {event.page_title}")
    
    def record_page_create(self, page_id: str, page_title: str, author: str):
        """
        记录页面创建
        
        Args:
            page_id: 页面ID
            page_title: 页面标题
            author: 作者
        """
        event = TimelineEvent(
            id=f"create_{page_id}_{int(datetime.now().timestamp())}",
            type="create",
            page_id=page_id,
            page_title=page_title,
            author=author,
            description=f"创建页面「{page_title}」",
        )
        self.add_event(event)
    
    def record_page_update(self, page_id: str, page_title: str, author: str,
                          previous_content: str, new_content: str, revision: int):
        """
        记录页面更新
        
        Args:
            page_id: 页面ID
            page_title: 页面标题
            author: 作者
            previous_content: 更新前内容
            new_content: 更新后内容
            revision: 修订版本号
        """
        event = TimelineEvent(
            id=f"update_{page_id}_{revision}",
            type="update",
            page_id=page_id,
            page_title=page_title,
            author=author,
            description=f"更新页面「{page_title}」(修订版 {revision})",
            previous_state=previous_content[:100] if previous_content else None,
            new_state=new_content[:100] if new_content else None,
            revision_number=revision,
        )
        self.add_event(event)
    
    def record_page_delete(self, page_id: str, page_title: str, author: str):
        """
        记录页面删除
        
        Args:
            page_id: 页面ID
            page_title: 页面标题
            author: 作者
        """
        event = TimelineEvent(
            id=f"delete_{page_id}_{int(datetime.now().timestamp())}",
            type="delete",
            page_id=page_id,
            page_title=page_title,
            author=author,
            description=f"删除页面「{page_title}」",
        )
        self.add_event(event)
    
    def record_tag_change(self, page_id: str, page_title: str, author: str,
                         tag: str, added: bool):
        """
        记录标签变化
        
        Args:
            page_id: 页面ID
            page_title: 页面标题
            author: 作者
            tag: 标签名
            added: 是否添加（True=添加，False=移除）
        """
        event_type = "tag_add" if added else "tag_remove"
        event = TimelineEvent(
            id=f"{event_type}_{page_id}_{tag}_{int(datetime.now().timestamp())}",
            type=event_type,
            page_id=page_id,
            page_title=page_title,
            author=author,
            description=f"{'添加' if added else '移除'}标签「{tag}」到页面「{page_title}」",
        )
        self.add_event(event)
    
    def get_timeline(self, page_id: Optional[str] = None, 
                     start_date: Optional[str] = None, 
                     end_date: Optional[str] = None) -> List[TimelineEntry]:
        """
        获取时间线
        
        Args:
            page_id: 页面ID（可选）
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            List 时间线条目列表
        """
        # 过滤事件
        events = self._events
        if page_id:
            events = self._page_events.get(page_id, [])
        
        # 按日期分组
        date_groups = {}
        for event in events:
            date = event.timestamp.split("T")[0]
            
            # 日期过滤
            if start_date and date < start_date:
                continue
            if end_date and date > end_date:
                continue
            
            if date not in date_groups:
                date_groups[date] = []
            date_groups[date].append(event)
        
        # 转换为 TimelineEntry 列表并排序
        entries = []
        for date in sorted(date_groups.keys(), reverse=True):
            entries.append(TimelineEntry(
                date=date,
                events=sorted(date_groups[date], key=lambda e: e.timestamp, reverse=True),
            ))
        
        return entries
    
    def get_page_history(self, page_id: str) -> List[TimelineEvent]:
        """
        获取页面历史
        
        Args:
            page_id: 页面ID
            
        Returns:
            List 事件列表
        """
        events = self._page_events.get(page_id, [])
        return sorted(events, key=lambda e: e.timestamp)
    
    def compare_versions(self, page_id: str, version1: int, version2: int) -> Dict[str, Any]:
        """
        对比两个版本
        
        Args:
            page_id: 页面ID
            version1: 版本1
            version2: 版本2
            
        Returns:
            Dict 对比结果
        """
        if not self._wiki_core:
            return {"success": False, "message": "Wiki Core 不可用"}
        
        revisions = self._wiki_core.get_page_revisions(page_id)
        
        rev1 = next((r for r in revisions if r.revision_number == version1), None)
        rev2 = next((r for r in revisions if r.revision_number == version2), None)
        
        if not rev1 or not rev2:
            return {"success": False, "message": "版本不存在"}
        
        return {
            "success": True,
            "page_id": page_id,
            "version1": {
                "revision": rev1.revision_number,
                "timestamp": rev1.timestamp,
                "author": rev1.author,
                "content": rev1.content,
            },
            "version2": {
                "revision": rev2.revision_number,
                "timestamp": rev2.timestamp,
                "author": rev2.author,
                "content": rev2.content,
            },
            "diff": self._generate_diff(rev1.content, rev2.content),
        }
    
    def _generate_diff(self, content1: str, content2: str) -> str:
        """
        生成差异
        
        Args:
            content1: 原始内容
            content2: 新内容
            
        Returns:
            str 差异描述
        """
        lines1 = content1.split('\n')
        lines2 = content2.split('\n')
        
        added_lines = []
        removed_lines = []
        
        for i, line in enumerate(lines2):
            if i >= len(lines1) or line != lines1[i]:
                added_lines.append((i + 1, line))
        
        for i, line in enumerate(lines1):
            if i >= len(lines2) or line != lines2[i]:
                removed_lines.append((i + 1, line))
        
        diff_parts = []
        if removed_lines:
            diff_parts.append(f"删除 {len(removed_lines)} 行:")
            for line_num, line in removed_lines[:3]:
                diff_parts.append(f"  -{line_num}: {line[:50]}")
        
        if added_lines:
            diff_parts.append(f"添加 {len(added_lines)} 行:")
            for line_num, line in added_lines[:3]:
                diff_parts.append(f"  +{line_num}: {line[:50]}")
        
        return "\n".join(diff_parts)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        type_counts = {}
        for event in self._events:
            type_counts[event.type] = type_counts.get(event.type, 0) + 1
        
        return {
            "total_events": len(self._events),
            "total_pages_tracked": len(self._page_events),
            "event_type_distribution": type_counts,
        }


# 全局时间线实例
_timeline_instance = None

def get_knowledge_timeline() -> KnowledgeTimeline:
    """获取全局知识时间线实例"""
    global _timeline_instance
    if _timeline_instance is None:
        _timeline_instance = KnowledgeTimeline()
    return _timeline_instance