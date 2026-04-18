"""
office_preview/tab_manager.py - 多标签页管理器

借鉴 AionUi 的标签页管理设计：
- 智能标签复用（同一文件不会重复打开）
- 溢出处理（淡出效果 + 滚动支持）
- 标签右键菜单
- 键盘快捷键支持
"""

import os
import uuid
import time
from typing import Dict, List, Optional, Callable, Set
from dataclasses import dataclass, field

from .models import PreviewTab, PreviewFileType, TabState, EditorMode, FileInfo


@dataclass
class TabManagerConfig:
    """标签页管理器配置"""
    max_tabs: int = 20                   # 最大标签数
    max_recent: int = 50                # 最近文件记录数
    auto_preview: bool = True            # 打开时自动预览
    remember_position: bool = True        # 记住位置


class TabManager:
    """
    多标签页管理器

    借鉴 AionUi 的智能标签管理：
    - 标签唯一性：相同文件不会重复打开
    - LRU 驱逐：超出最大数量时关闭最老的标签
    - 最近文件：记录并快速访问最近文件
    - 多路订阅：支持多窗口同时管理
    """

    def __init__(self, config: TabManagerConfig = None):
        self.config = config or TabManagerConfig()
        self._tabs: Dict[str, PreviewTab] = {}      # tab_id -> PreviewTab
        self._path_to_tab: Dict[str, str] = {}       # file_path -> tab_id
        self._order: List[str] = []                  # 标签顺序
        self._recent: List[str] = []                 # 最近文件路径
        self._subscribers: Set[Callable] = set()     # 变化通知订阅者
        self._active_tab_id: Optional[str] = None

    # ============ 标签管理核心 ============

    def open_file(self, file_path: str, content: str = '',
                  editor_mode: EditorMode = EditorMode.PREVIEW_ONLY,
                  activate: bool = True) -> PreviewTab:
        """
        打开文件到新标签页

        Args:
            file_path: 文件路径
            content: 文件内容（可选，用于编辑器模式）
            editor_mode: 编辑模式
            activate: 是否激活新标签

        Returns:
            PreviewTab 对象
        """
        abs_path = os.path.abspath(file_path)

        # 检查是否已打开
        existing = self.get_tab_by_path(abs_path)
        if existing:
            if activate:
                self.activate_tab(existing.tab_id)
            return existing

        # 驱逐策略
        if len(self._tabs) >= self.config.max_tabs:
            self._evict_oldest()

        # 创建标签
        file_info = FileInfo.from_path(abs_path)
        tab = PreviewTab(
            tab_id=str(uuid.uuid4())[:8],
            file_path=abs_path,
            file_info=file_info,
            content=content or (self._read_file_content(abs_path) if os.path.exists(abs_path) else ''),
            original_content=content or (self._read_file_content(abs_path) if os.path.exists(abs_path) else ''),
            editor_mode=editor_mode,
            state=TabState.CLEAN
        )

        self._tabs[tab.tab_id] = tab
        self._path_to_tab[abs_path] = tab.tab_id
        self._order.append(tab.tab_id)

        # 更新最近
        self._add_recent(abs_path)

        # 通知订阅者
        self._notify('tab_opened', tab)

        if activate:
            self._active_tab_id = tab.tab_id
            self._notify('tab_activated', tab)

        return tab

    def close_tab(self, tab_id: str) -> bool:
        """关闭标签页"""
        if tab_id not in self._tabs:
            return False

        tab = self._tabs[tab_id]

        # 检查未保存
        if tab.is_modified:
            # TODO: 返回确认对话框
            pass

        # 移除
        self._tabs.pop(tab_id)
        self._path_to_tab.pop(tab.file_path, None)
        self._order.remove(tab_id)

        # 激活其他标签
        if self._active_tab_id == tab_id:
            if self._order:
                self.activate_tab(self._order[-1])
            else:
                self._active_tab_id = None

        self._notify('tab_closed', tab)
        return True

    def close_other_tabs(self, keep_tab_id: str):
        """关闭除指定标签外的所有标签"""
        to_close = [tid for tid in self._order if tid != keep_tab_id]
        for tid in to_close:
            self.close_tab(tid)

    def close_all_tabs(self):
        """关闭所有标签"""
        for tab_id in list(self._order):
            self.close_tab(tab_id)

    def activate_tab(self, tab_id: str) -> bool:
        """激活标签页"""
        if tab_id not in self._tabs:
            return False

        if self._active_tab_id != tab_id:
            self._active_tab_id = tab_id
            self._notify('tab_activated', self._tabs[tab_id])

        return True

    def activate_next_tab(self):
        """激活下一个标签"""
        if not self._order:
            return
        current_idx = self._order.index(self._active_tab_id) if self._active_tab_id in self._order else -1
        next_idx = (current_idx + 1) % len(self._order)
        self.activate_tab(self._order[next_idx])

    def activate_prev_tab(self):
        """激活上一个标签"""
        if not self._order:
            return
        current_idx = self._order.index(self._active_tab_id) if self._active_tab_id in self._order else 0
        prev_idx = (current_idx - 1 + len(self._order)) % len(self._order)
        self.activate_tab(self._order[prev_idx])

    # ============ 内容管理 ============

    def update_content(self, tab_id: str, content: str):
        """更新标签内容"""
        if tab_id not in self._tabs:
            return

        tab = self._tabs[tab_id]
        tab.content = content
        tab.state = TabState.MODIFIED if content != tab.original_content else TabState.CLEAN
        self._notify('content_updated', tab)

    def save_tab(self, tab_id: str) -> bool:
        """保存标签内容到文件"""
        if tab_id not in self._tabs:
            return False

        tab = self._tabs[tab_id]
        try:
            with open(tab.file_path, 'w', encoding=tab.file_info.encoding) as f:
                f.write(tab.content)
            tab.original_content = tab.content
            tab.state = TabState.CLEAN
            self._notify('tab_saved', tab)
            return True
        except Exception as e:
            tab.error_message = str(e)
            tab.state = TabState.ERROR
            self._notify('save_error', tab)
            return False

    def reload_tab(self, tab_id: str) -> bool:
        """重新加载文件"""
        if tab_id not in self._tabs:
            return False

        tab = self._tabs[tab_id]
        try:
            content = self._read_file_content(tab.file_path)
            tab.content = content
            tab.original_content = content
            tab.state = TabState.CLEAN
            self._notify('tab_reloaded', tab)
            return True
        except Exception as e:
            tab.error_message = str(e)
            self._notify('reload_error', tab)
            return False

    # ============ 查询接口 ============

    def get_tab(self, tab_id: str) -> Optional[PreviewTab]:
        return self._tabs.get(tab_id)

    def get_tab_by_path(self, file_path: str) -> Optional[PreviewTab]:
        abs_path = os.path.abspath(file_path)
        tab_id = self._path_to_tab.get(abs_path)
        return self._tabs.get(tab_id)

    def get_active_tab(self) -> Optional[PreviewTab]:
        if self._active_tab_id:
            return self._tabs.get(self._active_tab_id)
        return None

    def get_all_tabs(self) -> List[PreviewTab]:
        return [self._tabs[tid] for tid in self._order if tid in self._tabs]

    def get_tabs_by_type(self, file_type: PreviewFileType) -> List[PreviewTab]:
        return [
            self._tabs[tid] for tid in self._order
            if tid in self._tabs and self._tabs[tid].file_info.file_type == file_type
        ]

    def get_modified_tabs(self) -> List[PreviewTab]:
        return [t for t in self._tabs.values() if t.is_modified]

    def get_recent_files(self, limit: int = None) -> List[str]:
        limit = limit or self.config.max_recent
        return self._recent[:limit]

    # ============ 订阅机制 ============

    def subscribe(self, callback: Callable):
        """订阅变化通知"""
        self._subscribers.add(callback)

    def unsubscribe(self, callback: Callable):
        """取消订阅"""
        self._subscribers.discard(callback)

    def _notify(self, event: str, tab: PreviewTab):
        """通知所有订阅者"""
        for cb in list(self._subscribers):
            try:
                cb(event, tab)
            except Exception:
                pass

    # ============ 辅助方法 ============

    def _read_file_content(self, file_path: str) -> str:
        """读取文件内容"""
        encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'latin-1']
        for enc in encodings:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        # 二进制文件
        with open(file_path, 'rb') as f:
            return f.read().decode('utf-8', errors='replace')[:10000]

    def _add_recent(self, file_path: str):
        """添加到最近文件"""
        if file_path in self._recent:
            self._recent.remove(file_path)
        self._recent.insert(0, file_path)
        self._recent = self._recent[:self.config.max_recent]

    def _evict_oldest(self):
        """驱逐最老的标签"""
        if not self._order:
            return
        # 跳过修改过的标签
        for tid in self._order:
            if tid in self._tabs and not self._tabs[tid].is_modified:
                self.close_tab(tid)
                return
        # 全部修改过，强制关闭第一个
        self.close_tab(self._order[0])


# 全局单例
_global_tab_manager: Optional[TabManager] = None


def get_tab_manager() -> TabManager:
    """获取全局标签管理器"""
    global _global_tab_manager
    if _global_tab_manager is None:
        _global_tab_manager = TabManager()
    return _global_tab_manager
