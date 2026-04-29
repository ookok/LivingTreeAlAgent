"""
日历窗口 - Calendar

支持：
- 月视图显示
- 日程管理
- 事件提醒
- 任务标记
"""

from typing import List, Dict, Optional
from datetime import datetime, date

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QPushButton, QScrollArea,
    QDialog, QLineEdit, QTextEdit, QDateEdit
)
from PyQt6.QtCore import Qt, QDate

from client.src.presentation.framework.minimal_ui_framework import (
    ColorScheme, Spacing, MinimalCard, UIComponentFactory
)


class CalendarDay(QFrame):
    """日历日期单元格"""
    
    day_clicked = pyqtSignal(date)
    
    def __init__(self, day_date: date, events: List[Dict] = [], parent=None):
        super().__init__(parent)
        self._date = day_date
        self._events = events
        self._is_today = day_date == datetime.now().date()
        self._is_selected = False
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        
        # 设置背景样式
        self.setStyleSheet(self._get_style())
        
        # 日期数字
        day_label = QLabel(str(self._date.day))
        day_label.setStyleSheet("font-size: 13px;")
        day_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(day_label)
        
        # 事件指示点
        if self._events:
            dots = min(len(self._events), 3)
            dots_layout = QHBoxLayout()
            dots_layout.setSpacing(2)
            
            for i in range(dots):
                dot = QFrame()
                dot.setFixedSize(6, 6)
                dot.setStyleSheet("""
                    QFrame {
                        background-color: #3B82F6;
                        border-radius: 3px;
                    }
                """)
                dots_layout.addWidget(dot)
            
            layout.addLayout(dots_layout)
    
    def _get_style(self) -> str:
        """获取样式"""
        base_style = "QFrame { border-radius: 8px; padding: 4px; }"
        
        if self._is_today:
            base_style += " QFrame { background-color: #3B82F6; } QLabel { color: white; }"
        elif self._is_selected:
            base_style += " QFrame { background-color: #DBEAFE; }"
        
        return base_style
    
    def set_selected(self, selected: bool):
        """设置选中状态"""
        self._is_selected = selected
        self.setStyleSheet(self._get_style())
    
    def mousePressEvent(self, event):
        self.day_clicked.emit(self._date)


class CalendarWindow(QWidget):
    """日历主窗口"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_date = datetime.now().date()
        self._selected_date = None
        self._events = self._load_events()
        self._setup_ui()
    
    def _load_events(self) -> Dict[str, List[Dict]]:
        """加载日程事件"""
        today = datetime.now().date()
        return {
            today.strftime("%Y-%m-%d"): [
                {"title": "团队会议", "time": "10:00", "color": "#3B82F6"},
                {"title": "项目评审", "time": "14:00", "color": "#10B981"}
            ],
            (today.replace(day=today.day + 1)).strftime("%Y-%m-%d"): [
                {"title": "客户演示", "time": "09:00", "color": "#F59E0B"}
            ],
            (today.replace(day=today.day + 3)).strftime("%Y-%m-%d"): [
                {"title": "团建活动", "time": "14:00", "color": "#8B5CF6"}
            ]
        }
    
    def _setup_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #FAFAFA;
                font-family: 'Segoe UI', 'PingFang SC', sans-serif;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题栏
        title_bar = QFrame()
        title_bar.setFixedHeight(56)
        title_bar.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-bottom: 1px solid #E5E7EB;
            }
        """)
        
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 16, 0)
        title_layout.setSpacing(16)
        
        title_label = UIComponentFactory.create_label(
            title_bar, "📅 日历", ColorScheme.TEXT_PRIMARY, 16
        )
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # 导航按钮
        prev_btn = QPushButton("◀")
        prev_btn.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                border: none;
                border-radius: 8px;
                padding: 4px 12px;
                font-size: 16px;
            }
        """)
        prev_btn.clicked.connect(self._prev_month)
        title_layout.addWidget(prev_btn)
        
        # 当前日期显示
        self.month_label = QLabel(f"{self._current_date.year}年{self._current_date.month}月")
        self.month_label.setStyleSheet("font-size: 14px; color: #374151;")
        title_layout.addWidget(self.month_label)
        
        next_btn = QPushButton("▶")
        next_btn.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                border: none;
                border-radius: 8px;
                padding: 4px 12px;
                font-size: 16px;
            }
        """)
        next_btn.clicked.connect(self._next_month)
        title_layout.addWidget(next_btn)
        
        layout.addWidget(title_bar)
        
        # 主内容区
        main_content = QWidget()
        main_layout = QHBoxLayout(main_content)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)
        
        # 月视图
        calendar_card = MinimalCard()
        calendar_layout = calendar_card.layout()
        
        # 星期标题
        week_days = ["日", "一", "二", "三", "四", "五", "六"]
        week_layout = QHBoxLayout()
        
        for day in week_days:
            label = UIComponentFactory.create_label(
                calendar_card, day, ColorScheme.TEXT_SECONDARY, 12
            )
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            week_layout.addWidget(label)
        
        calendar_layout.addLayout(week_layout)
        
        # 日期网格
        self.days_grid = QGridLayout()
        self._render_calendar()
        calendar_layout.addLayout(self.days_grid)
        
        main_layout.addWidget(calendar_card)
        
        # 日程列表
        events_card = MinimalCard()
        events_card.setFixedWidth(300)
        events_layout = events_card.layout()
        
        events_title = UIComponentFactory.create_label(
            events_card, "今日日程", ColorScheme.TEXT_PRIMARY, 14
        )
        events_layout.addWidget(events_title)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        events_widget = QWidget()
        events_vlayout = QVBoxLayout(events_widget)
        
        today_events = self._events.get(datetime.now().date().strftime("%Y-%m-%d"), [])
        for event in today_events:
            event_frame = QFrame()
            event_frame.setStyleSheet("""
                QFrame {
                    background-color: #F8FAFC;
                    border-radius: 8px;
                    padding: 8px;
                    margin-bottom: 8px;
                }
            """)
            
            event_layout = QVBoxLayout(event_frame)
            
            time_label = QLabel(event["time"])
            time_label.setStyleSheet("font-size: 12px; color: #6B7280;")
            event_layout.addWidget(time_label)
            
            title_label = QLabel(event["title"])
            title_label.setStyleSheet(f"font-size: 13px; color: {event['color']};")
            event_layout.addWidget(title_label)
            
            events_vlayout.addWidget(event_frame)
        
        scroll_area.setWidget(events_widget)
        events_layout.addWidget(scroll_area)
        
        add_btn = UIComponentFactory.create_button(
            events_card, "添加日程", variant="primary", size="sm"
        )
        add_btn.clicked.connect(self._add_event)
        events_layout.addWidget(add_btn)
        
        main_layout.addWidget(events_card)
        
        layout.addWidget(main_content, 1)
    
    def _render_calendar(self):
        """渲染日历"""
        # 清除旧网格
        while self.days_grid.count() > 0:
            item = self.days_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 获取当月第一天是星期几
        first_day = date(self._current_date.year, self._current_date.month, 1)
        start_weekday = first_day.weekday()
        
        # 获取当月天数
        if self._current_date.month == 12:
            last_day = date(self._current_date.year + 1, 1, 1)
        else:
            last_day = date(self._current_date.year, self._current_date.month + 1, 1)
        
        num_days = (last_day - first_day).days
        
        # 填充空白
        for i in range(start_weekday):
            empty = QFrame()
            empty.setStyleSheet("background-color: transparent;")
            self.days_grid.addWidget(empty, 0, i)
        
        # 填充日期
        current_week = 0
        for day in range(1, num_days + 1):
            day_date = date(self._current_date.year, self._current_date.month, day)
            day_str = day_date.strftime("%Y-%m-%d")
            events = self._events.get(day_str, [])
            
            day_widget = CalendarDay(day_date, events)
            day_widget.day_clicked.connect(self._on_day_clicked)
            day_widget.setFixedSize(80, 80)
            
            col = (start_weekday + day - 1) % 7
            row = (start_weekday + day - 1) // 7
            
            self.days_grid.addWidget(day_widget, row, col)
    
    def _prev_month(self):
        """上一月"""
        if self._current_date.month == 1:
            self._current_date = date(self._current_date.year - 1, 12, 1)
        else:
            self._current_date = date(self._current_date.year, self._current_date.month - 1, 1)
        
        self.month_label.setText(f"{self._current_date.year}年{self._current_date.month}月")
        self._render_calendar()
    
    def _next_month(self):
        """下一月"""
        if self._current_date.month == 12:
            self._current_date = date(self._current_date.year + 1, 1, 1)
        else:
            self._current_date = date(self._current_date.year, self._current_date.month + 1, 1)
        
        self.month_label.setText(f"{self._current_date.year}年{self._current_date.month}月")
        self._render_calendar()
    
    def _on_day_clicked(self, day_date: date):
        """日期点击处理"""
        print(f"选中日期: {day_date}")
    
    def _add_event(self):
        """添加日程"""
        dialog = QDialog(self)
        dialog.setWindowTitle("添加日程")
        dialog.setMinimumWidth(300)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        title_input = QLineEdit()
        title_input.setPlaceholderText("日程标题")
        layout.addWidget(title_input)
        
        time_input = QLineEdit()
        time_input.setPlaceholderText("时间 (如: 10:00)")
        layout.addWidget(time_input)
        
        date_input = QDateEdit()
        date_input.setDate(QDate.currentDate())
        layout.addWidget(date_input)
        
        description_input = QTextEdit()
        description_input.setPlaceholderText("备注")
        layout.addWidget(description_input)
        
        ok_btn = UIComponentFactory.create_button(dialog, "保存", variant="primary", size="md")
        ok_btn.clicked.connect(dialog.accept)
        layout.addWidget(ok_btn)
        
        dialog.exec()