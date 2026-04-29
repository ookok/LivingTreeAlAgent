"""
信号监控面板
==================
实时展示 EigenFlux 信号总线的统计信息与可视化。

功能：
1. 信号流量实时图表（折线图）
2. 信号类型分布（饼图）
3. 匹配效率指标
4. 订阅者状态列表
5. 信号历史浏览

Author: LivingTree AI Agent
Date: 2026-04-29
"""

import time
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QPushButton, QTableWidget, QTableWidgetItem,
        QHeaderView, QFrame, QGroupBox, QTabWidget
    )
    from PyQt6.QtCore import QTimer, Qt, QSize
    from PyQt6.QtGui import QFont, QColor, QPalette, QPainter, QPen, QBrush, QLinearGradient
    HAS_PYQT6 = True
except ImportError:
    HAS_PYQT6 = False

# ==================== 数据模型 ====================

@dataclass
class SignalMetrics:
    """信号指标数据"""
    timestamp: float
    signals_sent: int
    signals_delivered: int
    signals_filtered: int
    signals_cached: int
    signals_duplicates: int
    active_subscribers: int
    delivery_rate: float = 0.0
    filter_rate: float = 0.0
    type_counts: Dict[str, int] = None
    
    def __post_init__(self):
        if self.type_counts is None:
            self.type_counts = {}


class MetricsHistory:
    """指标历史记录"""
    
    MAX_HISTORY = 200  # 最多保存 200 条
    
    def __init__(self, max_size: int = MAX_HISTORY):
        self._history: deque = deque(maxlen=max_size)
    
    def add(self, metrics: SignalMetrics):
        """添加指标"""
        self._history.append(metrics)
    
    def get_all(self) -> List[SignalMetrics]:
        """获取所有历史"""
        return list(self._history)
    
    def get_recent(self, count: int = 50) -> List[SignalMetrics]:
        """获取最近 N 条"""
        return list(self._history)[-count:]
    
    def clear(self):
        """清除历史"""
        self._history.clear()


# ==================== 自定义图表组件 ====================

if HAS_PYQT6:
    class SignalLineChart(QFrame):
        """信号流量折线图"""
        
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setMinimumHeight(200)
            self.setFrameStyle(QFrame.Shape.StyledPanel)
            self._data: deque = deque(maxlen=60)
            self._labels: List[str] = []
            self._max_value = 100
            self._colors = {
                "sent": QColor("#4CAF50"),      # 绿色
                "delivered": QColor("#2196F3"), # 蓝色
                "filtered": QColor("#FF9800"),  # 橙色
            }
        
        def set_data(self, data: List[Dict]):
            """设置图表数据"""
            self._data.clear()
            self._labels.clear()
            
            for item in data[-60:]:
                self._data.append({
                    "sent": item.get("signals_sent", 0),
                    "delivered": item.get("signals_delivered", 0),
                    "filtered": item.get("signals_filtered", 0),
                })
                ts = item.get("timestamp", 0)
                if ts:
                    self._labels.append(
                        datetime.fromtimestamp(ts).strftime("%H:%M:%S")
                    )
            
            # 计算最大值
            max_val = 1
            for d in self._data:
                for v in d.values():
                    max_val = max(max_val, v)
            self._max_value = max_val * 1.2
            
            self.update()
        
        def paintEvent(self, event):
            if not self._data:
                return
            
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            w, h = self.width(), self.height()
            padding = {"left": 50, "right": 20, "top": 20, "bottom": 40}
            chart_w = w - padding["left"] - padding["right"]
            chart_h = h - padding["top"] - padding["bottom"]
            
            # 绘制网格
            painter.setPen(QColor("#333333"))
            for i in range(5):
                y = padding["top"] + chart_h * i / 4
                painter.drawLine(padding["left"], y, w - padding["right"], y)
                value = int(self._max_value * (4 - i) / 4)
                painter.drawText(
                    padding["left"] - 5, y + 5,
                    str(value)
                )
            
            # 绘制折线
            if len(self._data) < 2:
                return
            
            step_x = chart_w / max(len(self._data) - 1, 1)
            
            for key, color in self._colors.items():
                painter.setPen(QPen(color, 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                
                points = []
                for i, d in enumerate(self._data):
                    x = padding["left"] + i * step_x
                    y = padding["top"] + chart_h * (1 - d.get(key, 0) / self._max_value)
                    points.append((x, y))
                
                for i in range(len(points) - 1):
                    painter.drawLine(*points[i], *points[i + 1])
            
            # 图例
            legend_y = h - 10
            legend_x = padding["left"]
            for key, color in self._colors.items():
                painter.setBrush(QBrush(color))
                painter.drawRect(legend_x, legend_y - 8, 12, 12)
                painter.setPen(QColor("#CCCCCC"))
                painter.drawText(legend_x + 18, legend_y + 3, {
                    "sent": "发送",
                    "delivered": "投递",
                    "filtered": "过滤"
                }.get(key, key))
                legend_x += 80


    class SignalPieChart(QFrame):
        """信号类型分布饼图"""
        
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setMinimumHeight(180)
            self.setFrameStyle(QFrame.Shape.StyledPanel)
            self._data: Dict[str, int] = {}
            self._colors = [
                QColor("#4CAF50"),  # KNOWLEDGE - 绿
                QColor("#2196F3"),  # NEED - 蓝
                QColor("#FF9800"),  # CAPABILITY - 橙
                QColor("#9C27B0"),  # TASK - 紫
                QColor("#F44336"),  # BROADCAST - 红
            ]
        
        def set_data(self, data: Dict[str, int]):
            """设置饼图数据"""
            self._data = data or {}
            self.update()
        
        def paintEvent(self, event):
            if not self._data:
                # 绘制空状态
                painter = QPainter(self)
                painter.setPen(QColor("#666666"))
                painter.drawText(
                    self.rect(), Qt.AlignmentFlag.AlignCenter,
                    "暂无数据"
                )
                return
            
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            w, h = self.width(), self.height()
            size = min(w * 0.6, h * 0.8)
            
            cx, cy = w * 0.35, h * 0.5
            radius = size / 2
            
            total = sum(self._data.values())
            if total == 0:
                return
            
            start_angle = 90 * 16  # 从顶部开始
            colors = iter(self._colors)
            
            for key, value in self._data.items():
                span = int(360 * 16 * value / total)
                painter.setBrush(next(colors))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawPie(
                    int(cx - radius), int(cy - radius),
                    int(size), int(size),
                    int(start_angle), span
                )
                start_angle += span
            
            # 绘制图例
            legend_x = w * 0.65
            legend_y = h * 0.2
            colors = iter(self._colors)
            labels = {
                "knowledge": "知识",
                "need": "需求",
                "capability": "能力",
                "task": "任务",
                "broadcast": "广播",
            }
            
            for key, value in self._data.items():
                painter.setBrush(next(colors))
                painter.setPen(QColor("#333333"))
                painter.drawRect(int(legend_x), int(legend_y), 12, 12)
                painter.drawText(
                    int(legend_x + 18), int(legend_y + 10),
                    f"{labels.get(key, key)}: {value}"
                )
                legend_y += 22


# ==================== 监控面板 ====================

class SignalMonitorPanel:
    """
    信号监控面板
    ==================
    实时展示信号总线统计信息
    """
    
    def __init__(self, signal_bus, parent=None):
        self._bus = signal_bus
        self._parent = parent
        self._history = MetricsHistory()
        self._widgets: Dict[str, Any] = {}
        self._update_interval = 1000  # ms
        self._timer: Optional[Any] = None
        
        if HAS_PYQT6 and parent:
            self._setup_ui(parent)
            self._start_monitoring()
    
    def _setup_ui(self, parent):
        """设置 UI"""
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 标题栏
        title_bar = self._create_title_bar()
        layout.addWidget(title_bar)
        
        # 指标卡片
        metrics_grid = self._create_metrics_grid()
        layout.addWidget(metrics_grid)
        
        # 图表区域
        charts_widget = QTabWidget()
        
        # 流量图表
        flow_tab = QWidget()
        flow_layout = QVBoxLayout(flow_tab)
        self._widgets["line_chart"] = SignalLineChart() if HAS_PYQT6 else None
        if self._widgets["line_chart"]:
            flow_layout.addWidget(self._widgets["line_chart"])
        charts_widget.addTab(flow_tab, "信号流量")
        
        # 分布图表
        dist_tab = QWidget()
        dist_layout = QVBoxLayout(dist_tab)
        self._widgets["pie_chart"] = SignalPieChart() if HAS_PYQT6 else None
        if self._widgets["pie_chart"]:
            dist_layout.addWidget(self._widgets["pie_chart"])
        charts_widget.addTab(dist_tab, "类型分布")
        
        layout.addWidget(charts_widget, stretch=1)
        
        # 订阅者表格
        table_group = QGroupBox("订阅者状态")
        table_layout = QVBoxLayout(table_group)
        self._widgets["table"] = self._create_subscriber_table()
        table_layout.addWidget(self._widgets["table"])
        layout.addWidget(table_group, stretch=1)
    
    def _create_title_bar(self) -> QWidget:
        """创建标题栏"""
        bar = QFrame()
        bar.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(bar)
        
        title = QLabel("EigenFlux 信号监控")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # 状态指示
        self._widgets["status"] = QLabel("● 运行中")
        self._widgets["status"].setStyleSheet("color: #4CAF50;")
        layout.addWidget(self._widgets["status"])
        
        layout.addStretch()
        
        # 按钮
        self._widgets["btn_clear"] = QPushButton("清除数据")
        self._widgets["btn_clear"].clicked.connect(self._on_clear)
        layout.addWidget(self._widgets["btn_clear"])
        
        return bar
    
    def _create_metrics_grid(self) -> QWidget:
        """创建指标卡片网格"""
        grid = QGridLayout()
        grid.setSpacing(10)
        
        self._widgets["cards"] = {}
        metrics = [
            ("signals_sent", "发送信号", "signals_sent"),
            ("signals_delivered", "投递信号", "signals_delivered"),
            ("signals_filtered", "过滤信号", "signals_filtered"),
            ("active_subscribers", "活跃订阅", "active_subscribers"),
            ("cache_hit_rate", "缓存命中率", "cache_hit_rate"),
            ("delivery_rate", "投递率", "delivery_rate"),
        ]
        
        for i, (key, label, stat_key) in enumerate(metrics):
            card = self._create_metric_card(label, stat_key)
            self._widgets["cards"][key] = card
            grid.addWidget(card, i // 3, i % 3)
        
        return grid
    
    def _create_metric_card(self, label: str, stat_key: str) -> QWidget:
        """创建单个指标卡片"""
        card = QFrame()
        card.setFrameStyle(QFrame.Shape.StyledPanel)
        card.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border: 1px solid #333;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout(card)
        
        name_label = QLabel(label)
        name_label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(name_label)
        
        value_label = QLabel("0")
        value_label.setObjectName(f"value_{stat_key}")
        value_label.setStyleSheet("color: #fff; font-size: 24px; font-weight: bold;")
        layout.addWidget(value_label)
        
        return card
    
    def _create_subscriber_table(self) -> QWidget:
        """创建订阅者表格"""
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["订阅者 ID", "信号类型", "关键词", "状态"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setAlternatingRowColors(True)
        table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                alternate-background-color: #252525;
                color: #fff;
            }
            QHeaderView::section {
                background-color: #333;
                color: #fff;
                padding: 5px;
            }
        """)
        return table
    
    def _start_monitoring(self):
        """启动监控"""
        if HAS_PYQT6 and self._parent:
            self._timer = QTimer(self._parent)
            self._timer.timeout.connect(self._update)
            self._timer.start(self._update_interval)
    
    def _update(self):
        """更新数据"""
        stats = self._bus.get_stats()
        
        # 记录历史
        metrics = SignalMetrics(
            timestamp=time.time(),
            signals_sent=stats.get("signals_sent", 0),
            signals_delivered=stats.get("signals_delivered", 0),
            signals_filtered=stats.get("signals_filtered", 0),
            signals_cached=stats.get("signals_cached", 0),
            signals_duplicates=stats.get("signals_duplicates", 0),
            active_subscribers=stats.get("active_subscribers", 0),
            delivery_rate=stats.get("delivery_rate", 0),
            filter_rate=stats.get("filter_rate", 0),
        )
        self._history.add(metrics)
        
        # 更新指标卡片
        self._widgets["cards"]["signals_sent"].findChild(QLabel, "value_signals_sent").setText(
            str(stats.get("signals_sent", 0))
        )
        self._widgets["cards"]["signals_delivered"].findChild(QLabel, "value_signals_delivered").setText(
            str(stats.get("signals_delivered", 0))
        )
        self._widgets["cards"]["signals_filtered"].findChild(QLabel, "value_signals_filtered").setText(
            str(stats.get("signals_filtered", 0))
        )
        self._widgets["cards"]["active_subscribers"].findChild(QLabel, "value_active_subscribers").setText(
            str(stats.get("active_subscribers", 0))
        )
        
        # 缓存命中率
        cache_stats = stats.get("cache", {})
        hit_rate = cache_stats.get("hit_rate", 0)
        self._widgets["cards"]["cache_hit_rate"].findChild(QLabel, "value_cache_hit_rate").setText(
            f"{hit_rate:.1%}"
        )
        
        # 投递率
        delivery_rate = stats.get("delivery_rate", 0)
        self._widgets["cards"]["delivery_rate"].findChild(QLabel, "value_delivery_rate").setText(
            f"{delivery_rate:.1%}"
        )
        
        # 更新图表
        if self._widgets.get("line_chart"):
            self._widgets["line_chart"].set_data(
                [{"timestamp": m.timestamp, **m.__dict__} for m in self._history.get_recent(60)]
            )
        
        # 更新订阅者表格
        self._update_subscriber_table()
    
    def _update_subscriber_table(self):
        """更新订阅者表格"""
        table = self._widgets.get("table")
        if not table:
            return
        
        subscribers = self._bus.get_subscribers()
        table.setRowCount(len(subscribers))
        
        for i, sub in enumerate(subscribers):
            table.setItem(i, 0, QTableWidgetItem(sub.subscriber_id))
            table.setItem(i, 1, QTableWidgetItem(
                ", ".join(t.value for t in sub.signal_types)
            ))
            table.setItem(i, 2, QTableWidgetItem(
                ", ".join(sub.interests) if sub.interests else "-"
            ))
            status = "活跃" if sub.is_active else "离线"
            item = QTableWidgetItem(status)
            item.setForeground(QColor("#4CAF50" if sub.is_active else "#F44336"))
            table.setItem(i, 3, item)
    
    def _on_clear(self):
        """清除数据"""
        self._bus.clear_all()
        self._history.clear()


# ==================== 文本模式监控器（无 PyQt6）====================

class TextSignalMonitor:
    """文本模式信号监控器"""
    
    def __init__(self, signal_bus, interval: float = 1.0):
        self._bus = signal_bus
        self._interval = interval
        self._history = MetricsHistory()
        self._running = False
        self._last_stats: Dict = {}
    
    def start(self):
        """启动监控"""
        self._running = True
        self._update()
    
    def stop(self):
        """停止监控"""
        self._running = False
    
    def _update(self):
        """更新统计"""
        if not self._running:
            return
        
        stats = self._bus.get_stats()
        
        # 检测变化
        changes = self._detect_changes(stats)
        
        if changes:
            self._print_stats(stats, changes)
        
        self._last_stats = stats.copy()
        
        # 记录历史
        metrics = SignalMetrics(
            timestamp=time.time(),
            signals_sent=stats.get("signals_sent", 0),
            signals_delivered=stats.get("signals_delivered", 0),
            signals_filtered=stats.get("signals_filtered", 0),
            signals_cached=stats.get("signals_cached", 0),
            signals_duplicates=stats.get("signals_duplicates", 0),
            active_subscribers=stats.get("active_subscribers", 0),
            delivery_rate=stats.get("delivery_rate", 0),
        )
        self._history.add(metrics)
    
    def _detect_changes(self, stats: Dict) -> List[str]:
        """检测统计变化"""
        changes = []
        for key in ["signals_sent", "signals_delivered", "signals_filtered"]:
            curr = stats.get(key, 0)
            prev = self._last_stats.get(key, 0)
            if curr != prev:
                changes.append(key)
        return changes
    
    def _print_stats(self, stats: Dict, changes: List):
        """打印统计信息"""
        print("\n" + "=" * 60)
        print(f"📡 EigenFlux 信号监控 - {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 60)
        
        # 核心指标
        print(f"\n核心指标:")
        print(f"  发送信号: {stats.get('signals_sent', 0)}")
        print(f"  投递信号: {stats.get('signals_delivered', 0)}")
        print(f"  过滤信号: {stats.get('signals_filtered', 0)}")
        print(f"  活跃订阅: {stats.get('active_subscribers', 0)}")
        
        # 效率指标
        print(f"\n效率指标:")
        print(f"  投递率: {stats.get('delivery_rate', 0):.1%}")
        print(f"  过滤率: {stats.get('filter_rate', 0):.1%}")
        
        # 缓存统计
        if stats.get("cache"):
            cache = stats["cache"]
            print(f"\n缓存统计:")
            print(f"  命中数: {cache.get('hits', 0)}")
            print(f"  未命中: {cache.get('misses', 0)}")
            print(f"  命中率: {cache.get('hit_rate', 0):.1%}")
        
        # 批处理统计
        if stats.get("batch"):
            batch = stats["batch"]
            print(f"\n批处理统计:")
            print(f"  批次数: {batch.get('batches_processed', 0)}")
            print(f"  待处理: {batch.get('pending', 0)}")
        
        # 最近信号
        recent = self._bus.get_recent_signals(3)
        if recent:
            print(f"\n最近信号:")
            for sig in recent:
                print(f"  [{sig.metadata.signal_type.value}] "
                      f"{sig.metadata.sender_id}: {sig.payload}")
        
        print("=" * 60)
    
    def get_summary(self) -> Dict:
        """获取汇总信息"""
        return {
            "history_size": len(self._history.get_all()),
            "current_stats": self._bus.get_stats(),
            "efficiency": self._calculate_efficiency(),
        }
    
    def _calculate_efficiency(self) -> Dict:
        """计算效率评分"""
        stats = self._bus.get_stats()
        total = stats.get("signals_sent", 1)
        delivered = stats.get("signals_delivered", 0)
        filtered = stats.get("signals_filtered", 0)
        
        return {
            "delivery_score": delivered / total if total > 0 else 0,
            "filter_score": filtered / total if total > 0 else 0,
            "cache_score": stats.get("cache", {}).get("hit_rate", 0),
        }
