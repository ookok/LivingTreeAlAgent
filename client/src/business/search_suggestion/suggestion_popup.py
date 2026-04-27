# -*- coding: utf-8 -*-
"""
搜索建议弹窗组件
类似百度搜索建议的智能联想功能
"""

import asyncio
import logging
from typing import List, Callable, Optional, Any
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QRect, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QListWidget, QListWidgetItem,
    QAbstractItemView, QScrollArea,
)
from PyQt6.QtGui import QFont, QPainter, QColor, QBrush, QPen, QCursor

from .suggestion_model import SearchSuggestion, get_suggestion_manager, add_search_history
from .knowledge_query import query_knowledge, get_knowledge_query
from .cache import get_suggestion_cache

logger = logging.getLogger(__name__)


class SuggestionItem(QWidget):
    """建议项组件"""
    
    selected = pyqtSignal(int)  # index
    
    def __init__(self, suggestion: SearchSuggestion, index: int, parent=None):
        super().__init__(parent)
        self.suggestion = suggestion
        self.index = index
        self._is_selected = False
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        self.setFixedHeight(40)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)
        
        # 序号
        self.index_label = QLabel(f"{self.index + 1}.")
        self.index_label.setStyleSheet("""
            color: #94a3b8;
            font-size: 12px;
            font-weight: bold;
            min-width: 24px;
        """)
        layout.addWidget(self.index_label)
        
        # 图标
        icon_map = {
            'history': '🕐',
            'knowledge': '📚',
            'hot': '🔥',
            'related': '🔗',
        }
        self.icon_label = QLabel(icon_map.get(self.suggestion.source, '📝'))
        self.icon_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.icon_label)
        
        # 文本
        self.text_label = QLabel(self.suggestion.text)
        self.text_label.setStyleSheet("""
            color: #1e293b;
            font-size: 13px;
        """)
        self.text_label.setMaximumWidth(400)
        layout.addWidget(self.text_label, 1)
        
        # 时间标签
        self.time_label = QLabel(self.suggestion.time_label)
        self.time_label.setStyleSheet("""
            color: #94a3b8;
            font-size: 11px;
        """)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.time_label)
        
        # 来源标签
        source_map = {
            'history': '历史',
            'knowledge': '知识库',
            'hot': '热门',
            'related': '相关',
        }
        self.source_label = QLabel(source_map.get(self.suggestion.source, ''))
        source_colors = {
            'history': '#3b82f6',
            'knowledge': '#10b981',
            'hot': '#ef4444',
            'related': '#8b5cf6',
        }
        color = source_colors.get(self.suggestion.source, '#94a3b8')
        self.source_label.setStyleSheet(f"""
            color: {color};
            font-size: 11px;
            background: {color}15;
            padding: 2px 6px;
            border-radius: 4px;
        """)
        self.source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.source_label)
    
    def set_selected(self, selected: bool):
        """设置选中状态"""
        self._is_selected = selected
        if selected:
            self.setStyleSheet("""
                SuggestionItem {
                    background: #f1f5f9;
                    border-left: 3px solid #3b82f6;
                }
            """)
        else:
            self.setStyleSheet("""
                SuggestionItem {
                    background: white;
                    border-left: 3px solid transparent;
                }
                SuggestionItem:hover {
                    background: #f8fafc;
                }
            """)
    
    def enterEvent(self, event):
        """鼠标进入"""
        if not self._is_selected:
            self.setStyleSheet("""
                SuggestionItem {
                    background: #f8fafc;
                    border-left: 3px solid #e2e8f0;
                }
            """)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开"""
        if not self._is_selected:
            self.setStyleSheet("""
                SuggestionItem {
                    background: white;
                    border-left: 3px solid transparent;
                }
            """)
        super().leaveEvent(event)


class SuggestionListWidget(QListWidget):
    """自定义列表控件"""
    
    item_selected = pyqtSignal(int)  # 选中项索引
    item_double_clicked = pyqtSignal(int)  # 双击项索引
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: List[SuggestionItem] = []
        self._current_index = -1
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        self.setWindowFlags(Qt.WindowType.Popup)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        self.setStyleSheet("""
            QListWidget {
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                outline: none;
            }
            QListWidget::item {
                border: none;
                border-bottom: 1px solid #f1f5f9;
            }
            QListWidget::item:selected {
                background: transparent;
            }
            QScrollBar:vertical {
                width: 6px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                border-radius: 3px;
            }
        """)
    
    def set_suggestions(self, suggestions: List[SearchSuggestion]):
        """设置建议列表"""
        self.clear()
        self._items.clear()
        
        for i, suggestion in enumerate(suggestions):
            item = QListWidgetItem(self)
            item.setSizeHint(QSize(-1, 42))  # 固定高度
            
            widget = SuggestionItem(suggestion, i)
            self._items.append(widget)
            
            self.addItem(item)
            self.setItemWidget(item, widget)
        
        self._current_index = -1
        self._update_selection()
    
    def _update_selection(self):
        """更新选中状态"""
        for i, widget in enumerate(self._items):
            widget.set_selected(i == self._current_index)
    
    def keyPressEvent(self, event):
        """键盘事件"""
        if event.key() == Qt.Key.Key_Down:
            self.select_next()
            event.accept()
        elif event.key() == Qt.Key.Key_Up:
            self.select_prev()
            event.accept()
        elif event.key() == Qt.Key.Key_Enter or event.key() == Qt.Key.Key_Return:
            self.confirm_selection()
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
        else:
            super().keyPressEvent(event)
    
    def select_next(self):
        """选择下一项"""
        if not self._items:
            return
        self._current_index = (self._current_index + 1) % len(self._items)
        self._update_selection()
        self.scrollToItem(self.currentItem())
    
    def select_prev(self):
        """选择上一项"""
        if not self._items:
            return
        self._current_index = (self._current_index - 1) % len(self._items)
        self._update_selection()
        self.scrollToItem(self.currentItem())
    
    def confirm_selection(self):
        """确认选择"""
        if 0 <= self._current_index < len(self._items):
            self.item_selected.emit(self._current_index)
            self.hide()
    
    def get_selected_text(self) -> Optional[str]:
        """获取选中的文本"""
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index].suggestion.text
        return None
    
    def get_current_suggestions(self) -> List[SearchSuggestion]:
        """获取当前建议列表"""
        return [item.suggestion for item in self._items]


class SearchSuggestionPopup(QFrame):
    """
    搜索建议弹窗
    
    特点：
    - 10行纵向排列
    - 按时间排序（最新的在前）
    - 调用知识库获取建议
    - 300ms 防抖
    - 键盘导航支持
    """
    
    # 信号
    suggestion_selected = pyqtSignal(str)  # 选中的建议文本
    suggestion_clicked = pyqtSignal(str)   # 点击的建议文本
    hidden_changed = pyqtSignal(bool)      # 显示状态变化
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._suggestions: List[SearchSuggestion] = []
        self._current_index = -1
        self._query = ""
        self._is_visible = False
        
        self._setup_ui()
        self._setup_animations()
    
    def _setup_ui(self):
        """设置UI"""
        self.setWindowFlags(
            Qt.WindowType.Popup | 
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        
        # 样式
        self.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)
        
        # 标题栏
        header = QLabel("💡 搜索建议")
        header.setStyleSheet("""
            color: #64748b;
            font-size: 11px;
            font-weight: bold;
            padding: 6px 12px;
            background: #f8fafc;
            border-bottom: 1px solid #e2e8f0;
        """)
        layout.addWidget(header)
        
        # 建议列表
        self.list_widget = SuggestionListWidget()
        self.list_widget.item_selected.connect(self._on_item_selected)
        self.list_widget.item_double_clicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.list_widget)
        
        # 底部提示
        footer = QLabel("↑↓ 选择 • Enter 确认 • Esc 关闭")
        footer.setStyleSheet("""
            color: #94a3b8;
            font-size: 10px;
            padding: 4px 12px;
            background: #f8fafc;
            border-top: 1px solid #e2e8f0;
        """)
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)
    
    def _setup_animations(self):
        """设置动画"""
        self._fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self._fade_animation.setDuration(150)
    
    def showPopup(self, input_widget: QWidget, suggestions: List[SearchSuggestion]):
        """
        显示弹窗
        
        Args:
            input_widget: 输入框组件（用于定位）
            suggestions: 建议列表
        """
        if not suggestions:
            self.hidePopup()
            return
        
        self._suggestions = suggestions
        
        # 设置列表数据
        self.list_widget.set_suggestions(suggestions)
        
        # 计算位置和大小
        pos = input_widget.mapToGlobal(input_widget.rect().bottomLeft())
        
        # 限制宽度（与输入框对齐）
        width = max(input_widget.width(), 500)
        height = min(len(suggestions) * 42 + 60, 500)  # 10行 + 头部 + 底部
        
        self.setGeometry(pos.x(), pos.y(), width, height)
        
        # 显示
        self.show()
        self._is_visible = True
        self.raise_()
        
        self.hidden_changed.emit(False)
    
    def hidePopup(self):
        """隐藏弹窗"""
        self.hide()
        self._is_visible = False
        self._suggestions.clear()
        self._current_index = -1
        self.hidden_changed.emit(True)
    
    def update_suggestions(self, suggestions: List[SearchSuggestion]):
        """更新建议列表"""
        self._suggestions = suggestions
        self.list_widget.set_suggestions(suggestions)
        
        if suggestions:
            self.show()
            self._is_visible = True
        else:
            self.hidePopup()
    
    def _on_item_selected(self, index: int):
        """项被选中"""
        if 0 <= index < len(self._suggestions):
            text = self._suggestions[index].text
            self.suggestion_selected.emit(text)
            self.hidePopup()
    
    def _on_item_double_clicked(self, index: int):
        """项被双击"""
        if 0 <= index < len(self._suggestions):
            text = self._suggestions[index].text
            self.suggestion_clicked.emit(text)
            self.hidePopup()
    
    def keyPressEvent(self, event):
        """键盘事件"""
        if event.key() == Qt.Key.Key_Escape:
            self.hidePopup()
            event.accept()
        elif event.key() == Qt.Key.Key_Up:
            self.list_widget.select_prev()
            event.accept()
        elif event.key() == Qt.Key.Key_Down:
            self.list_widget.select_next()
            event.accept()
        elif event.key() == Qt.Key.Key_Enter or event.key() == Qt.Key.Key_Return:
            self.list_widget.confirm_selection()
            event.accept()
        else:
            super().keyPressEvent(event)
    
    def is_visible(self) -> bool:
        """是否显示"""
        return self._is_visible
    
    def get_current_suggestions(self) -> List[SearchSuggestion]:
        """获取当前建议"""
        return self._suggestions


class SuggestionController:
    """
    建议控制器
    协调输入框、弹窗、知识库查询
    """
    
    def __init__(self, input_widget, popup: SearchSuggestionPopup = None):
        self.input_widget = input_widget
        self.popup = popup or SearchSuggestionPopup()
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._do_query)
        self._debounce_ms = 300  # 防抖延迟
        
        self._manager = get_suggestion_manager()
        self._cache = get_suggestion_cache()
        self._query_task: Optional[asyncio.Task] = None
        
        # 连接信号
        self.popup.suggestion_selected.connect(self._on_suggestion_selected)
        self.popup.suggestion_clicked.connect(self._on_suggestion_clicked)
    
    def _on_suggestion_selected(self, text: str):
        """建议被选中"""
        self.input_widget.setText(text)
        self.input_widget.setFocus()
    
    def _on_suggestion_clicked(self, text: str):
        """建议被点击"""
        self.input_widget.setText(text)
        self.input_widget.returnPressed.emit()
    
    def on_text_changed(self, text: str):
        """文本变化时调用"""
        self._query = text
        
        if not text or len(text.strip()) < 1:
            self.popup.hidePopup()
            return
        
        # 重置防抖计时器
        self._debounce_timer.start(self._debounce_ms)
    
    def _do_query(self):
        """执行查询"""
        query = self._query.strip()
        if not query:
            return
        
        # 取消之前的查询任务
        if self._query_task and not self._query_task.done():
            self._query_task.cancel()
        
        # 启动新的查询任务
        loop = asyncio.get_event_loop()
        self._query_task = loop.create_task(self._query_suggestions(query))
    
    async def _query_suggestions(self, query: str):
        """查询建议"""
        try:
            suggestions = []
            
            # 1. 从历史记录获取
            history = self._manager.get_suggestions(query, limit=5)
            for s in history:
                suggestions.append(s)
            
            # 2. 从知识库获取
            kb_suggestions = await query_knowledge(query, limit=8)
            for s in kb_suggestions:
                # 避免重复
                if not any(ex.text == s.text for ex in suggestions):
                    suggestions.append(s)
            
            # 3. 合并后排序（时间最新的优先）
            suggestions = sorted(
                suggestions,
                key=lambda x: (x.final_score, x.time_weight),
                reverse=True
            )[:10]  # 最多10条
            
            # 在主线程更新UI
            if query == self._query:  # 确保是最新的查询
                self.popup.update_suggestions(suggestions)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"查询建议失败: {e}")
    
    def add_to_history(self, query: str):
        """添加搜索历史"""
        self._manager.add_from_history(query)
        self._cache.add_to_history(query)
    
    def show(self):
        """显示弹窗"""
        query = self.input_widget.text().strip()
        if query:
            # 手动触发查询
            self._debounce_timer.stop()
            self._query = query
            self._do_query()
    
    def hide(self):
        """隐藏弹窗"""
        self.popup.hidePopup()
    
    @property
    def debounce_ms(self) -> int:
        return self._debounce_ms
    
    @debounce_ms.setter
    def debounce_ms(self, value: int):
        self._debounce_ms = value
