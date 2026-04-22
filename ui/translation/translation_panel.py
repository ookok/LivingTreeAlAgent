"""
翻译 PyQt6 UI 面板 - Translation Panel

功能:
1. 翻译引擎状态显示
2. 单条/批量翻译
3. 翻译历史
4. 统计信息
5. 缓存管理
"""

import asyncio
import time
from typing import Optional, List, Dict, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTextEdit, QLineEdit,
    QComboBox, QProgressBar, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame,
    QCheckBox, QSpinBox, QGroupBox, QScrollArea,
    QStatusBar, QMenuBar, QMenu
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QAction

from core.translation import (
    get_translation_hub,
    TranslatorType, TranslatorStatus,
    TranslationResult, TranslationTask,
    LANGUAGE_NAMES, normalize_language,
    SmartTranslateConfig
)


# ============ 样式定义 ============

TRANSLATION_STYLE = """
/* 主面板 */
QWidget#translation_panel {
    background-color: #1a1a2e;
    color: #e0e0e0;
}

/* 翻译框 */
.translation-box {
    background-color: #16162a;
    border-radius: 12px;
    padding: 16px;
}

/* 文本输入 */
QTextEdit {
    background-color: #2d2d44;
    border: 1px solid #3d3d54;
    border-radius: 8px;
    padding: 12px;
    color: white;
    font-size: 14px;
}
QTextEdit:focus {
    border-color: #2563eb;
}

/* 按钮 */
QPushButton {
    background-color: #2563eb;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 14px;
}
QPushButton:hover {
    background-color: #1d4ed8;
}
QPushButton:pressed {
    background-color: #1e40af;
}
QPushButton:disabled {
    background-color: #4b5563;
    color: #9ca3af;
}

/* 次要按钮 */
QPushButton.secondary {
    background-color: #3d3d54;
}
QPushButton.secondary:hover {
    background-color: #4d4d64;
}

/* 目标语言选择 */
QComboBox {
    background-color: #2d2d44;
    border: 1px solid #3d3d54;
    border-radius: 8px;
    padding: 8px 12px;
    color: white;
}
QComboBox:focus {
    border-color: #2563eb;
}
QComboBox::drop-down {
    border: none;
}
QComboBox QAbstractItemView {
    background-color: #2d2d44;
    border: 1px solid #3d3d54;
    selection-background-color: #2563eb;
}

/* 标签页 */
QTabWidget::pane {
    background-color: #1a1a2e;
    border: none;
}
QTabBar::tab {
    background-color: #16162a;
    color: #888;
    padding: 10px 20px;
    border: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}
QTabBar::tab:selected {
    background-color: #1a1a2e;
    color: white;
}
QTabBar::tab:hover {
    background-color: #1f1f35;
}

/* 表格 */
QTableWidget {
    background-color: #16162a;
    border: none;
    gridline-color: #2d2d44;
    color: white;
}
QTableWidget::item {
    padding: 8px;
}
QTableWidget::item:selected {
    background-color: #2563eb;
}
QHeaderView::section {
    background-color: #1f1f35;
    color: #888;
    padding: 8px;
    border: none;
}

/* 状态栏 */
QStatusBar {
    background-color: #16162a;
    color: #888;
    border-top: 1px solid #2d2d44;
}

/* 进度条 */
QProgressBar {
    background-color: #2d2d44;
    border: none;
    border-radius: 4px;
    height: 8px;
}
QProgressBar::chunk {
    background-color: #2563eb;
    border-radius: 4px;
}

/* 复选框 */
QCheckBox {
    color: #e0e0e0;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 2px solid #3d3d54;
}
QCheckBox::indicator:checked {
    background-color: #2563eb;
    border-color: #2563eb;
}

/* 分组框 */
QGroupBox {
    background-color: #1f1f35;
    border-radius: 8px;
    padding: 12px;
    margin-top: 8px;
}
QGroupBox::title {
    color: #888;
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}

/* 滚动条 */
QScrollBar:vertical {
    background-color: transparent;
    width: 8px;
}
QScrollBar::handle:vertical {
    background-color: #3d3d54;
    border-radius: 4px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

/* 标签 */
QLabel {
    color: #e0e0e0;
}
QLabel.title {
    font-size: 18px;
    font-weight: bold;
    color: white;
}
QLabel.subtitle {
    font-size: 14px;
    color: #888;
}
QLabel.success {
    color: #22c55e;
}
QLabel.error {
    color: #ef4444;
}
QLabel.warning {
    color: #eab308;
}
"""


# ============ 主面板 ============

class TranslationPanel(QWidget):
    """
    翻译面板

    布局:
    ┌────────────────────────────────────────────────┐
    │  🔄 翻译中心                                    │
    ├────────────────────────────────────────────────┤
    │  ┌──────────────────┐  ┌──────────────────┐  │
    │  │  源文本           │  │  译文             │  │
    │  │                  │  │                   │  │
    │  │  [输入框]         │  │  [输出框]          │  │
    │  │                  │  │                   │  │
    │  └──────────────────┘  └──────────────────┘  │
    │  [源语言: 自动 ▼] [目标: 中文 ▼] [翻译] [清空] │
    ├────────────────────────────────────────────────┤
    │  📊 翻译引擎状态  │  📜 历史记录  │  ⚙️ 设置   │
    ├────────────────────────────────────────────────┤
    │  (内容区域)                                    │
    └────────────────────────────────────────────────┘
    │  🟢 状态: 就绪 | 缓存: 45% | 平均延迟: 120ms   │
    └────────────────────────────────────────────────┘
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.translation_hub = get_translation_hub()
        self.current_translator: Optional[TranslatorType] = None
        self._is_translating = False
        self._setup_ui()
        self._setup_connections()
        self._update_translator_status()

    def _setup_ui(self):
        """设置 UI"""
        self.setObjectName("translation_panel")
        self.setStyleSheet(TRANSLATION_STYLE)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # ===== 顶部标题 =====
        title_layout = QHBoxLayout()
        title = QLabel("🔄 翻译中心")
        title.setObjectName("title")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        title_layout.addWidget(title)
        title_layout.addStretch()
        main_layout.addLayout(title_layout)

        # ===== 翻译区域 =====
        translate_layout = QHBoxLayout()
        translate_layout.setSpacing(16)

        # 源文本
        source_box = QFrame()
        source_box.setStyleSheet("background-color: #16162a; border-radius: 12px; padding: 12px;")
        source_layout = QVBoxLayout(source_box)
        source_layout.setContentsMargins(0, 0, 0, 0)

        source_header = QHBoxLayout()
        source_label = QLabel("源文本")
        source_label.setStyleSheet("font-weight: bold;")
        self.source_lang_combo = QComboBox()
        self.source_lang_combo.addItems(["自动检测"] + list(LANGUAGE_NAMES.values())[1:])  # 排除 AUTO
        self.source_lang_combo.setCurrentText("自动检测")
        self.source_lang_combo.setFixedWidth(120)
        source_header.addWidget(source_label)
        source_header.addStretch()
        source_header.addWidget(QLabel("语言:"))
        source_header.addWidget(self.source_lang_combo)
        source_layout.addLayout(source_header)

        self.source_text = QTextEdit()
        self.source_text.setPlaceholderText("输入要翻译的文本...")
        self.source_text.setStyleSheet("""
            QTextEdit {
                background-color: #2d2d44;
                border: 1px solid #3d3d54;
                border-radius: 8px;
                padding: 12px;
                color: white;
                font-size: 14px;
            }
        """)
        source_layout.addWidget(self.source_text, 1)

        translate_layout.addWidget(source_box, 1)

        # 目标文本
        target_box = QFrame()
        target_box.setStyleSheet("background-color: #16162a; border-radius: 12px; padding: 12px;")
        target_layout = QVBoxLayout(target_box)
        target_layout.setContentsMargins(0, 0, 0, 0)

        target_header = QHBoxLayout()
        target_label = QLabel("译文")
        target_label.setStyleSheet("font-weight: bold;")
        self.target_lang_combo = QComboBox()
        self.target_lang_combo.addItems(list(LANGUAGE_NAMES.values())[1:])  # 排除 AUTO
        self.target_lang_combo.setCurrentText("中文")
        self.target_lang_combo.setFixedWidth(120)
        target_header.addWidget(target_label)
        target_header.addStretch()
        target_header.addWidget(QLabel("语言:"))
        target_header.addWidget(self.target_lang_combo)
        target_layout.addLayout(target_header)

        self.target_text = QTextEdit()
        self.target_text.setReadOnly(True)
        self.target_text.setPlaceholderText("翻译结果将显示在这里...")
        self.target_text.setStyleSheet("""
            QTextEdit {
                background-color: #1f1f35;
                border: 1px solid #3d3d54;
                border-radius: 8px;
                padding: 12px;
                color: white;
                font-size: 14px;
            }
        """)
        target_layout.addWidget(self.target_text, 1)

        translate_layout.addWidget(target_box, 1)

        main_layout.addLayout(translate_layout, 1)

        # ===== 操作按钮 =====
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        self.translate_btn = QPushButton("🔄 翻译")
        self.translate_btn.clicked.connect(self._on_translate)
        button_layout.addWidget(self.translate_btn)

        self.clear_btn = QPushButton("🗑️ 清空")
        self.clear_btn.setObjectName("secondary")
        self.clear_btn.clicked.connect(self._on_clear)
        button_layout.addWidget(self.clear_btn)

        button_layout.addStretch()

        # 翻译器选择
        self.translator_combo = QComboBox()
        self.translator_combo.addItems([
            "🧠 智能分层 (推荐)",
            "📦 离线翻译 (Argos)",
            "🌐 在线翻译 (DeepTranslator)"
        ])
        self.translator_combo.setFixedWidth(200)
        button_layout.addWidget(QLabel("引擎:"))
        button_layout.addWidget(self.translator_combo)

        main_layout.addLayout(button_layout)

        # ===== 标签页 =====
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                background-color: #1a1a2e;
                border: none;
            }
        """)

        # 引擎状态页
        self._create_engine_tab()

        # 历史记录页
        self._create_history_tab()

        # 设置页
        self._create_settings_tab()

        main_layout.addWidget(self.tabs, 1)

        # ===== 状态栏 =====
        self.status_bar = QStatusBar()
        self.status_label = QLabel("🟢 就绪")
        self.cache_label = QLabel("缓存: --")
        self.latency_label = QLabel("延迟: --")
        self.stats_label = QLabel("请求: 0")
        self.status_bar.addPermanentWidget(self.status_label)
        self.status_bar.addPermanentWidget(self.cache_label)
        self.status_bar.addPermanentWidget(self.latency_label)
        self.status_bar.addPermanentWidget(self.stats_label)
        main_layout.addWidget(self.status_bar)

    def _create_engine_tab(self):
        """创建引擎状态页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)

        # 引擎卡片
        self.engine_cards = QVBoxLayout()
        self.engine_cards.setSpacing(12)
        layout.addLayout(self.engine_cards)

        layout.addStretch()

        self.tabs.addTab(tab, "📊 引擎状态")

    def _create_history_tab(self):
        """创建历史记录页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)

        # 历史表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(["时间", "原文", "译文", "语言对"])
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.setStyleSheet("""
            QTableWidget {
                background-color: #16162a;
                border: none;
                gridline-color: #2d2d44;
                color: white;
            }
        """)
        layout.addWidget(self.history_table, 1)

        # 按钮
        btn_layout = QHBoxLayout()
        self.refresh_history_btn = QPushButton("🔄 刷新")
        self.refresh_history_btn.clicked.connect(self._refresh_history)
        btn_layout.addWidget(self.refresh_history_btn)

        self.clear_history_btn = QPushButton("🗑️ 清空历史")
        self.clear_history_btn.setObjectName("secondary")
        self.clear_history_btn.clicked.connect(self._on_clear_history)
        btn_layout.addWidget(self.clear_history_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.tabs.addTab(tab, "📜 历史记录")

    def _create_settings_tab(self):
        """创建设置页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 缓存设置
        cache_group = QGroupBox("🗃️ 缓存设置")
        cache_layout = QVBoxLayout(cache_group)

        self.enable_cache_check = QCheckBox("启用翻译缓存")
        self.enable_cache_check.setChecked(True)
        self.enable_cache_check.stateChanged.connect(self._on_cache_toggled)
        cache_layout.addWidget(self.enable_cache_check)

        cache_size_layout = QHBoxLayout()
        cache_size_layout.addWidget(QLabel("缓存大小:"))
        self.cache_size_spin = QSpinBox()
        self.cache_size_spin.setRange(100, 10000)
        self.cache_size_spin.setValue(1000)
        self.cache_size_spin.valueChanged.connect(self._on_cache_size_changed)
        cache_size_layout.addWidget(self.cache_size_spin)
        cache_size_layout.addWidget(QLabel("条"))
        cache_size_layout.addStretch()
        cache_layout.addLayout(cache_size_layout)

        layout.addWidget(cache_group)

        # 翻译策略
        strategy_group = QGroupBox("⚙️ 翻译策略")
        strategy_layout = QVBoxLayout(strategy_group)

        self.offline_first_check = QCheckBox("离线优先 (短文本使用本地翻译)")
        self.offline_first_check.setChecked(True)
        strategy_layout.addWidget(self.offline_first_check)

        self.fallback_check = QCheckBox("离线失败时自动切换到在线翻译")
        self.fallback_check.setChecked(True)
        strategy_layout.addWidget(self.fallback_check)

        layout.addWidget(strategy_group)

        layout.addStretch()

        self.tabs.addTab(tab, "⚙️ 设置")

    def _setup_connections(self):
        """设置信号连接"""
        # 定时更新状态
        self._status_timer = QTimer()
        self._status_timer.timeout.connect(self._update_status_bar)
        self._status_timer.start(2000)

    # ============ 事件处理 ============

    def _on_translate(self):
        """翻译按钮点击"""
        if self._is_translating:
            return

        source_text = self.source_text.toPlainText().strip()
        if not source_text:
            return

        # 获取语言
        source_lang = self._get_selected_lang(self.source_lang_combo)
        target_lang = self._get_selected_lang(self.target_lang_combo)

        # 获取翻译器类型
        translator_type = self._get_translator_type()

        # 显示正在翻译
        self._is_translating = True
        self.translate_btn.setEnabled(False)
        self.target_text.setPlainText("翻译中...")

        # 异步翻译
        asyncio.create_task(self._translate_async(source_text, source_lang, target_lang, translator_type))

    async def _translate_async(self, text: str, source_lang: str, target_lang: str, translator_type: TranslatorType):
        """异步翻译"""
        try:
            if translator_type == TranslatorType.SMART:
                result = await self.translation_hub.translate_async(text, source_lang, target_lang)
            elif translator_type in (TranslatorType.ARGOS, TranslatorType.EASY_NMT, TranslatorType.HELSINKI):
                result = await self.translation_hub.translate_async(text, source_lang, target_lang)
            else:
                result = await self.translation_hub.translate_async(text, source_lang, target_lang)

            # 在主线程更新 UI
            self.target_text.setPlainText(result.translated or "翻译失败")

        except Exception as e:
            self.target_text.setPlainText(f"翻译失败: {str(e)}")

        finally:
            self._is_translating = False
            self.translate_btn.setEnabled(True)
            self._refresh_history()

    def _on_clear(self):
        """清空按钮点击"""
        self.source_text.clear()
        self.target_text.clear()

    def _get_selected_lang(self, combo: QComboBox) -> str:
        """获取选中的语言"""
        text = combo.currentText()
        # 反向查找语言代码
        for code, name in LANGUAGE_NAMES.items():
            if name == text:
                return code
        return "auto"

    def _get_translator_type(self) -> TranslatorType:
        """获取选中的翻译器类型"""
        index = self.translator_combo.currentIndex()
        if index == 0:
            return TranslatorType.SMART
        elif index == 1:
            return TranslatorType.ARGOS
        else:
            return TranslatorType.DEEP_TRANSLATOR

    def _update_status_bar(self):
        """更新状态栏"""
        stats = self.translation_hub.get_stats()
        cache_stats = stats.get("cache", {})

        self.stats_label.setText(f"请求: {stats.get('total_requests', 0)}")
        if cache_stats:
            hit_rate = cache_stats.get("hit_rate", 0) * 100
            self.cache_label.setText(f"缓存: {hit_rate:.0f}%")
        self.latency_label.setText(f"延迟: {stats.get('avg_latency_ms', 0):.0f}ms")

    def _update_translator_status(self):
        """更新翻译器状态"""
        # 清空现有卡片
        while self.engine_cards.count():
            item = self.engine_cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 获取可用翻译器
        translators = self.translation_hub.get_available_translators()

        for t in translators:
            card = self._create_engine_card(t)
            self.engine_cards.addWidget(card)

    def _create_engine_card(self, info: Dict) -> QFrame:
        """创建引擎状态卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #1f1f35;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        layout = QHBoxLayout(card)

        # 状态指示
        status_icon = "🟢" if info.get("is_offline") else "🌐"
        status_label = QLabel(f"{status_icon} {info['name']}")
        status_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        # 语言支持
        langs = ", ".join(info.get("languages", [])[:5])
        if len(info.get("languages", [])) > 5:
            langs += "..."

        lang_label = QLabel(f"支持: {langs}")
        lang_label.setStyleSheet("color: #888; font-size: 12px;")

        layout.addWidget(status_label)
        layout.addWidget(lang_label, 1)
        layout.addStretch()

        return card

    def _refresh_history(self):
        """刷新历史记录"""
        history = self.translation_hub.get_history(limit=50)

        self.history_table.setRowCount(len(history))
        for i, task in enumerate(history):
            import datetime
            dt = datetime.datetime.fromtimestamp(task.created_at)
            time_str = dt.strftime("%H:%M:%S")

            self.history_table.setItem(i, 0, QTableWidgetItem(time_str))
            self.history_table.setItem(i, 1, QTableWidgetItem(task.text[:50] + "..." if len(task.text) > 50 else task.text))
            self.history_table.setItem(i, 2, QTableWidgetItem(task.translated_text[:50] + "..." if len(task.translated_text) > 50 else task.translated_text))
            self.history_table.setItem(i, 3, QTableWidgetItem(f"{task.source_lang} → {task.target_lang}"))

        self.history_table.resizeColumnsToContents()

    def _on_clear_history(self):
        """清空历史"""
        self.translation_hub.clear_history()
        self._refresh_history()

    def _on_cache_toggled(self, state: int):
        """缓存开关切换"""
        enabled = state == Qt.CheckState.Checked.value
        self.translation_hub.enable_cache(enabled)

    def _on_cache_size_changed(self, value: int):
        """缓存大小改变"""
        config = SmartTranslateConfig()
        config.cache_max_size = value
        # 应用配置到翻译中心
        if hasattr(self, 'translation_hub') and self.translation_hub:
            self.translation_hub.set_config(config)
            self.translation_hub.enable_cache(config.cache_enabled)
        self._show_toast(f"缓存大小已调整为: {value} MB", "info")


# ============ 入口函数 ============

def get_translation_panel() -> TranslationPanel:
    """获取翻译面板实例"""
    return TranslationPanel()
