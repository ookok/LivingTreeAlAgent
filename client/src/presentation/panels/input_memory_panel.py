# -*- coding: utf-8 -*-
"""
输入记忆系统面板 - Input Memory Panel
======================================

展示三层记忆系统的工作状态、预测统计、进化进度

Author: Hermes Desktop Team
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QProgressBar, QTableWidget, QTableWidgetItem,
    QGroupBox, QGridLayout, QScrollArea, QFrame, QProgressDialog,
    QLineEdit, QTextEdit, QListWidget, QListWidgetItem,
    QStyledItemDelegate, QStyleOptionProgressBar, QStyle
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QPalette, QColor, QPainter, QLinearGradient, QGradient

try:
    from ...business.input_memory import (
        get_prediction_engine,
        UserStats,
        PredictionCandidate,
        PredictionEngine,
    )
    from ...business.digital_life import InputFingerprint
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from business.input_memory import (
        get_prediction_engine,
        UserStats,
        PredictionCandidate,
        PredictionEngine,
    )
    from business.digital_life import InputFingerprint


class InputMemoryPanel(QWidget):
    """输入记忆系统面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = None
        self.init_ui()
        self.init_engine()

        # 定时刷新
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_stats)
        self.refresh_timer.start(5000)  # 5秒刷新

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("🌿 输入记忆系统")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Tab页
        tabs = QTabWidget()
        tabs.addTab(self._create_overview_tab(), "📊 总览")
        tabs.addTab(self._create_evolution_tab(), "🌱 进化")
        tabs.addTab(self._create_stats_tab(), "📈 统计")
        tabs.addTab(self._create_memory_tab(), "🧠 记忆层")

        layout.addWidget(tabs)

    def _create_overview_tab(self) -> QWidget:
        """创建总览Tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 核心指标卡片
        metrics_layout = QGridLayout()

        # 首字响应
        self.latency_label = QLabel("加载中...")
        metrics_layout.addWidget(self._create_metric_card("⚡ 首字响应", self.latency_label), 0, 0)

        # 预测准确率
        self.accuracy_label = QLabel("加载中...")
        metrics_layout.addWidget(self._create_metric_card("🎯 预测准确率", self.accuracy_label), 0, 1)

        # 采纳率
        self.acceptance_label = QLabel("加载中...")
        metrics_layout.addWidget(self._create_metric_card("✅ 预测采纳率", self.acceptance_label), 1, 0)

        # 总预测数
        self.total_pred_label = QLabel("加载中...")
        metrics_layout.addWidget(self._create_metric_card("📝 总预测数", self.total_pred_label), 1, 1)

        layout.addLayout(metrics_layout)

        # 进化进度
        evolution_group = QGroupBox("🌱 道境进化进度")
        evolution_layout = QVBoxLayout()

        self.evolution_progress = QProgressBar()
        self.evolution_progress.setMinimum(0)
        self.evolution_progress.setMaximum(100)
        self.evolution_progress.setFormat("%v / %m (%p%)")
        evolution_layout.addWidget(self.evolution_progress)

        self.evolution_info = QLabel("加载中...")
        evolution_layout.addWidget(self.evolution_info)

        evolution_group.setLayout(evolution_layout)
        layout.addWidget(evolution_group)

        # 能力解锁
        ability_group = QGroupBox("🔓 已解锁能力")
        ability_layout = QHBoxLayout()

        self.cross_app_label = QLabel("❌ 跨应用预测")
        self.semantic_label = QLabel("❌ 语义预测")

        ability_layout.addWidget(self.cross_app_label)
        ability_layout.addWidget(self.semantic_label)
        ability_layout.addStretch()

        ability_group.setLayout(ability_layout)
        layout.addWidget(ability_group)

        layout.addStretch()
        return widget

    def _create_evolution_tab(self) -> QWidget:
        """创建进化Tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 道境信息
        self.dao_realm_label = QLabel("当前道境: 加载中...")
        self.dao_realm_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(self.dao_realm_label)

        # 进化等级显示
        level_layout = QHBoxLayout()

        self.level_label = QLabel("Lv.1")
        self.level_label.setFont(QFont("Microsoft YaHei", 48, QFont.Weight.Bold))
        level_layout.addWidget(self.level_label)

        level_info = QVBoxLayout()
        self.exp_label = QLabel("经验值: 0 / 100")
        self.exp_bar = QProgressBar()
        self.exp_bar.setMinimum(0)
        self.exp_bar.setMaximum(100)
        level_info.addWidget(self.exp_label)
        level_info.addWidget(self.exp_bar)
        level_layout.addLayout(level_info)

        layout.addLayout(level_layout)

        # 术语库
        terms_group = QGroupBox("📚 专属术语库")
        terms_layout = QVBoxLayout()

        self.terms_list = QListWidget()
        self.terms_list.setMaximumHeight(150)
        terms_layout.addWidget(self.terms_list)

        terms_btn_layout = QHBoxLayout()
        self.refresh_terms_btn = QPushButton("🔄 刷新术语")
        self.refresh_terms_btn.clicked.connect(self.refresh_terms)
        terms_btn_layout.addWidget(self.refresh_terms_btn)
        terms_btn_layout.addStretch()

        terms_group.setLayout(terms_layout)
        layout.addWidget(terms_group)

        # 进化历史
        history_group = QGroupBox("📜 进化历程")
        history_layout = QVBoxLayout()

        self.history_list = QListWidget()
        self.history_list.setMaximumHeight(150)
        history_layout.addWidget(self.history_list)

        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

        layout.addStretch()
        return widget

    def _create_stats_tab(self) -> QWidget:
        """创建统计Tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 时段分布
        hour_group = QGroupBox("⏰ 输入时段分布")
        hour_layout = QVBoxLayout()

        self.hour_chart = HourDistributionChart()
        hour_layout.addWidget(self.hour_chart)

        hour_group.setLayout(hour_layout)
        layout.addWidget(hour_group)

        # 应用偏好
        app_group = QGroupBox("📱 应用使用频率")
        app_layout = QVBoxLayout()

        self.app_table = QTableWidget()
        self.app_table.setColumnCount(2)
        self.app_table.setHorizontalHeaderLabels(["应用", "使用次数"])
        self.app_table.setMaximumHeight(200)
        app_layout.addWidget(self.app_table)

        app_group.setLayout(app_layout)
        layout.addWidget(app_group)

        layout.addStretch()
        return widget

    def _create_memory_tab(self) -> QWidget:
        """创建记忆层Tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # L0 短期记忆
        l0_group = QGroupBox("💨 L0 短期记忆 (实时上下文)")
        l0_layout = QVBoxLayout()

        self.l0_status = QLabel("状态: 活跃")
        l0_layout.addWidget(self.l0_status)

        self.l0_recent = QListWidget()
        self.l0_recent.setMaximumHeight(80)
        l0_layout.addWidget(QLabel("最近输入:"))
        l0_layout.addWidget(self.l0_recent)

        l0_group.setLayout(l0_layout)
        layout.addWidget(l0_group)

        # L1 中期记忆
        l1_group = QGroupBox("📈 L1 中期记忆 (习惯模型)")
        l1_layout = QVBoxLayout()

        self.l1_ngram_label = QLabel("N-gram 模型: 已加载")
        l1_layout.addWidget(self.l1_ngram_label)

        self.l1_model_size = QLabel("模型大小: 计算中...")
        l1_layout.addWidget(self.l1_model_size)

        l1_group.setLayout(l1_layout)
        layout.addWidget(l1_group)

        # L2 长期记忆
        l2_group = QGroupBox("🧬 L2 长期记忆 (道境指纹)")
        l2_layout = QVBoxLayout()

        self.l2_fingerprint = QLabel("指纹等级: Lv.1")
        l2_layout.addWidget(self.l2_fingerprint)

        self.l2_terms_count = QLabel("专长术语: 0")
        l2_layout.addWidget(self.l2_terms_count)

        l2_group.setLayout(l2_layout)
        layout.addWidget(l2_group)

        # 操作按钮
        btn_layout = QHBoxLayout()
        self.clear_l0_btn = QPushButton("🗑️ 清空短期记忆")
        self.clear_l0_btn.clicked.connect(self.clear_short_term)
        btn_layout.addWidget(self.clear_l0_btn)

        self.compress_btn = QPushButton("📦 压缩模型")
        self.compress_btn.clicked.connect(self.compress_model)
        btn_layout.addWidget(self.compress_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

        return widget

    def _create_metric_card(self, title: str, value_label: QLabel) -> QFrame:
        """创建指标卡片"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        layout = QVBoxLayout(frame)

        title_label = QLabel(title)
        title_label.setFont(QFont("Microsoft YaHei", 9))
        layout.addWidget(title_label)

        value_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        layout.addWidget(value_label)

        return frame

    def init_engine(self):
        """初始化预测引擎"""
        try:
            self.engine = get_prediction_engine()
            self.refresh_all()
        except Exception as e:
            print(f"初始化预测引擎失败: {e}")

    def refresh_all(self):
        """刷新所有数据"""
        self.refresh_stats()
        self.refresh_evolution()
        self.refresh_memory_layers()

    def refresh_stats(self):
        """刷新统计"""
        if not self.engine:
            return

        try:
            stats = self.engine.get_performance_stats()

            # 更新指标
            self.latency_label.setText(f"{stats['avg_latency_ms']:.1f} ms")

            # 准确率（基于采纳率）
            acceptance = stats['acceptance_rate']
            self.accuracy_label.setText(f"{acceptance * 100:.1f}%")

            self.acceptance_label.setText(f"{acceptance * 100:.1f}%")

            total = stats['total_predictions_offered']
            self.total_pred_label.setText(str(total))

            # 更新时段图表
            user_stats = stats.get('user_stats', {})
            hourly = user_stats.get('active_hours', {})
            self.hour_chart.set_data(hourly)

            # 更新应用表格
            self.update_app_table(user_stats.get('active_hours', {}))

        except Exception as e:
            print(f"刷新统计失败: {e}")

    def refresh_evolution(self):
        """刷新进化信息"""
        if not self.engine:
            return

        try:
            info = self.engine.fingerprint.get_evolution_info()

            # 道境
            self.dao_realm_label.setText(f"当前道境: {info['dao_realm']}")

            # 等级
            self.level_label.setText(f"Lv.{info['level']}")

            # 经验
            exp = info['current_exp']
            exp_needed = info['exp_needed']
            self.exp_label.setText(f"经验值: {exp} / {exp_needed}")
            self.exp_bar.setMaximum(exp_needed)
            self.exp_bar.setValue(exp)

            # 进化进度
            progress = int(info['progress'] * 100)
            self.evolution_progress.setValue(progress)

            evol_info = f"进化进度: {info['level']}级 | 术语数: {info['terms_count']}"
            if info['cross_app_enabled']:
                evol_info += " | ✅ 跨应用"
            if info['semantic_enabled']:
                evol_info += " | ✅ 语义"
            self.evolution_info.setText(evol_info)

            # 能力状态
            self.cross_app_label.setText("✅ 跨应用预测" if info['cross_app_enabled'] else "❌ 跨应用预测")
            self.semantic_label.setText("✅ 语义预测" if info['semantic_enabled'] else "❌ 语义预测")

            # 术语列表
            self.refresh_terms()

        except Exception as e:
            print(f"刷新进化信息失败: {e}")

    def refresh_terms(self):
        """刷新术语列表"""
        if not self.engine:
            return

        try:
            glossary = self.engine.fingerprint.get_dao_glossary()
            self.terms_list.clear()
            for term in glossary[:20]:  # 最多显示20个
                self.terms_list.addItem(term)
        except Exception as e:
            print(f"刷新术语失败: {e}")

    def refresh_memory_layers(self):
        """刷新记忆层状态"""
        if not self.engine:
            return

        try:
            # L0 状态
            l0_count = len(self.engine.short_term.memory)
            self.l0_status.setText(f"状态: 活跃 | 缓存: {l0_count}条")

            # L0 最近输入
            recent = self.engine.short_term.get_recent_inputs(5)
            self.l0_recent.clear()
            for inp in recent:
                self.l0_recent.addItem(inp[:30] + "..." if len(inp) > 30 else inp)

            # L1 模型大小
            model_path = self.engine.habit._model_path()
            if model_path.exists():
                size_kb = model_path.stat().st_size / 1024
                self.l1_model_size.setText(f"模型大小: {size_kb:.1f} KB")

            # L2 指纹
            info = self.engine.fingerprint.get_evolution_info()
            self.l2_fingerprint.setText(f"指纹等级: Lv.{info['level']} ({info['dao_realm']})")
            self.l2_terms_count.setText(f"专长术语: {info['terms_count']}个")

        except Exception as e:
            print(f"刷新记忆层失败: {e}")

    def update_app_table(self, hourly_data: dict):
        """更新应用表格"""
        # 简化：使用hourly_data作为应用数据
        self.app_table.setRowCount(0)

        apps = list(hourly_data.items())[:10]  # 最多10行
        for i, (app, count) in enumerate(apps):
            self.app_table.insertRow(i)
            self.app_table.setItem(i, 0, QTableWidgetItem(str(app)))
            self.app_table.setItem(i, 1, QTableWidgetItem(str(count)))

    def clear_short_term(self):
        """清空短期记忆"""
        if self.engine:
            self.engine.short_term.clear()
            self.refresh_memory_layers()

    def compress_model(self):
        """压缩模型"""
        if self.engine:
            self.engine.habit.compress_model()
            self.refresh_memory_layers()

    def closeEvent(self, event):
        """关闭时保存"""
        if self.engine:
            self.engine.habit._save_model()
            self.engine.fingerprint._save_fingerprint()
        super().closeEvent(event)


class HourDistributionChart(QWidget):
    """小时分布图表"""
    MAX_HEIGHT = 100

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data: Dict[int, int] = {}
        self.setMinimumHeight(self.MAX_HEIGHT + 20)

    def set_data(self, data: Dict[int, int]):
        self.data = data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self.data:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "暂无数据")
            return

        # 计算最大值
        max_val = max(self.data.values()) if self.data else 1

        # 绘制柱状图
        width = self.width()
        bar_width = width / 24  # 24小时

        for hour in range(24):
            count = self.data.get(hour, 0)
            bar_height = (count / max_val) * self.MAX_HEIGHT if max_val > 0 else 0

            x = hour * bar_width
            y = self.MAX_HEIGHT - bar_height

            # 颜色渐变
            if hour >= 6 and hour <= 18:
                color = QColor(46, 125, 50)  # 白天绿色
            else:
                color = QColor(21, 101, 192)  # 夜晚蓝色

            painter.fillRect(int(x), int(y), int(bar_width - 1), int(bar_height), color)

        # 绘制底部标签
        painter.setPen(Qt.GlobalColor.gray)
        for hour in [0, 6, 12, 18, 23]:
            x = hour * bar_width
            painter.drawText(int(x), self.MAX_HEIGHT + 15, str(hour))


class InputMemoryIntegration:
    """输入记忆系统集成助手"""

    def __init__(self, engine: PredictionEngine):
        self.engine = engine

    def get_prediction_for_context(self, partial: str, context: dict) -> list:
        """获取预测建议"""
        return self.engine.predict(partial, context)

    def record_and_learn(self, text: str, context: dict, duration_ms: float = 0):
        """记录输入并学习"""
        self.engine.record_input(text, context, duration_ms)

    def on_prediction_accepted(self, text: str):
        """预测被采纳"""
        self.engine.record_adoption(text)


def get_input_memory_panel() -> InputMemoryPanel:
    """获取输入记忆面板"""
    return InputMemoryPanel()


__all__ = [
    'InputMemoryPanel',
    'HourDistributionChart',
    'InputMemoryIntegration',
    'get_input_memory_panel',
]