# =================================================================
# 生命之树·彩蛋发现面板 - Easter Egg Discovery Panel
# =================================================================
# "道在日常生活中显现，彩蛋即是道在平凡中的闪光"
# =================================================================

from typing import List, Dict, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout, QTabWidget, QListWidget,
    QListWidgetItem, QProgressBar, QToolButton, QDialog, QTextEdit,
    QGroupBox, QStackedWidget
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QPalette, QColor, QPainter, QPixmap, QIcon
from PyQt6.QtSvg import QSvgWidget

import random


class EasterEggCard(QFrame):
    """彩蛋卡片组件"""

    def __init__(self, egg_type: str, name: str, description: str,
                 icon: str, discovered: bool = False, parent=None):
        super().__init__(parent)
        self.egg_type = egg_type
        self.name = name
        self.description = description
        self.icon = icon
        self.discovered = discovered

        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setMinimumSize(280, 160)

        # 根据发现状态设置样式
        if self.discovered:
            self.setStyleSheet("""
                EasterEggCard {
                    background-color: #1a3a1a;
                    border: 2px solid #4a7c4a;
                    border-radius: 12px;
                }
            """)
        else:
            self.setStyleSheet("""
                EasterEggCard {
                    background-color: #2a2a2a;
                    border: 2px solid #444;
                    border-radius: 12px;
                    opacity: 0.7;
                }
            """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # 图标和名称
        header = QHBoxLayout()
        icon_label = QLabel(self.icon)
        icon_label.setStyleSheet("font-size: 32px;")
        icon_label.setFixedSize(48, 48)

        name_label = QLabel(self.name)
        name_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        name_label.setStyleSheet("color: #c4e8c4;" if self.discovered else "color: #888;")

        header.addWidget(icon_label)
        header.addWidget(name_label, 1)
        header.addStretch()

        layout.addLayout(header)

        # 描述
        desc_label = QLabel(self.description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        layout.addWidget(desc_label)

        # 状态标签
        if self.discovered:
            status_label = QLabel("✨ 已发现")
            status_label.setStyleSheet("""
                background-color: #2d5a2d;
                color: #7fff7f;
                padding: 4px 12px;
                border-radius: 8px;
                font-size: 11px;
            """)
            layout.addWidget(status_label, 0, Qt.AlignmentFlag.AlignRight)
        else:
            hint_label = QLabel("🔮 待发现")
            hint_label.setStyleSheet("""
                background-color: #3a3a3a;
                color: #666;
                padding: 4px 12px;
                border-radius: 8px;
                font-size: 11px;
            """)
            layout.addWidget(hint_label, 0, Qt.AlignmentFlag.AlignRight)


class FragmentCollectionDialog(QDialog):
    """碎片收集对话框"""

    def __init__(self, fragments: List[Dict], parent=None):
        super().__init__(parent)
        self.fragments = fragments
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        self.setWindowTitle("📜 断简残篇收藏")
        self.setMinimumSize(600, 400)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
            }
            QLabel {
                color: #c4e8c4;
            }
        """)

        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("古籍碎片收集")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffd700;")
        layout.addWidget(title)

        # 进度
        collected = len([f for f in self.fragments if not f.get("is_synthesized", False)])
        total = len(self.fragments) if self.fragments else 10

        progress = QProgressBar()
        progress.setMaximum(10)
        progress.setValue(min(collected, 10))
        progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #4a7c4a;
                border-radius: 4px;
                background-color: #2a2a2a;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #4a7c4a;
            }
        """)
        layout.addWidget(progress)

        progress_label = QLabel(f"已收集：{collected}/10 片 (总计：{total})")
        progress_label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(progress_label)

        # 碎片列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")

        container = QWidget()
        container_layout = QVBoxLayout(container)

        for fragment in self.fragments:
            frag_card = self._create_fragment_card(fragment)
            container_layout.addWidget(frag_card)

        if not self.fragments:
            empty_label = QLabel("尚未收集任何碎片...\n在知识林地中探索古籍关键词，或许会有收获")
            empty_label.setStyleSheet("color: #666; text-align: center; padding: 40px;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            container_layout.addWidget(empty_label)

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a7c4a;
                color: white;
                border: none;
                padding: 8px 24px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #5a8c5a;
            }
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignRight)

    def _create_fragment_card(self, fragment: Dict) -> QWidget:
        """创建碎片卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 12px;
                margin: 4px 0;
            }
        """)
        layout = QHBoxLayout(card)

        # 来源
        source_label = QLabel(f"📖 {fragment.get('source', '未知来源')}")
        source_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        source_label.setStyleSheet("color: #ffd700;")
        layout.addWidget(source_label)

        layout.addStretch()

        # 内容预览
        content = fragment.get('content', '')
        content_label = QLabel(content[:30] + "..." if len(content) > 30 else content)
        content_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        layout.addWidget(content_label)

        # 状态
        if fragment.get('is_synthesized', False):
            synthesized_label = QLabel("✅ 已合成")
            synthesized_label.setStyleSheet("color: #7fff7f; font-size: 11px;")
            layout.addWidget(synthesized_label)

        return card


class CipherCollectionDialog(QDialog):
    """密文符号收集对话框"""

    def __init__(self, symbols: List[Dict], parent=None):
        super().__init__(parent)
        self.symbols = symbols
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        self.setWindowTitle("🔮 根系密文符号")
        self.setMinimumSize(500, 400)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
            }
        """)

        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("根系暗码收集")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #9b59b6;")
        layout.addWidget(title)

        # 提示
        hint = QLabel("集齐7个不同图腾，可拼出完整密文...")
        hint.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(hint)

        # 进度
        collected = len(self.symbols)
        progress = QProgressBar()
        progress.setMaximum(7)
        progress.setValue(collected)
        progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #8e44ad;
                border-radius: 4px;
                background-color: #2a2a2a;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #8e44ad;
            }
        """)
        layout.addWidget(progress)

        # 符号网格
        grid = QGridLayout()
        grid.setSpacing(12)

        rarity_colors = {
            "common": "#888",
            "rare": "#3498db",
            "epic": "#9b59b6",
            "legendary": "#f39c12"
        }

        for i, symbol in enumerate(self.symbols):
            row, col = i // 4, i % 4

            symbol_frame = QFrame()
            symbol_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: #2a2a2a;
                    border: 2px solid {rarity_colors.get(symbol.get('rarity', 'common'), '#888')};
                    border-radius: 8px;
                    padding: 8px;
                }}
            """)
            symbol_layout = QVBoxLayout(symbol_frame)

            symbol_char = QLabel(symbol.get('symbol', '?'))
            symbol_char.setFont(QFont("Arial", 24))
            symbol_char.setAlignment(Qt.AlignmentFlag.AlignCenter)
            symbol_layout.addWidget(symbol_char)

            symbol_name = QLabel(symbol.get('name', ''))
            symbol_name.setFont(QFont("Microsoft YaHei", 9))
            symbol_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
            symbol_name.setStyleSheet("color: #c0c0c0;")
            symbol_layout.addWidget(symbol_name)

            grid.addWidget(symbol_frame, row, col)

        # 空槽位
        for i in range(collected, 7):
            row, col = i // 4, i % 4
            empty_frame = QFrame()
            empty_frame.setStyleSheet("""
                QFrame {
                    background-color: #1a1a1a;
                    border: 2px dashed #444;
                    border-radius: 8px;
                    padding: 8px;
                    min-height: 80px;
                }
            """)
            empty_layout = QVBoxLayout(empty_frame)
            empty_label = QLabel("?")
            empty_label.setFont(QFont("Arial", 24))
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setStyleSheet("color: #444;")
            empty_layout.addWidget(empty_label)
            grid.addWidget(empty_frame, row, col)

        layout.addLayout(grid)
        layout.addStretch()

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #8e44ad;
                color: white;
                border: none;
                padding: 8px 24px;
                border-radius: 6px;
            }
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignRight)


class AstronomicalEventDialog(QDialog):
    """天文事件对话框"""

    def __init__(self, event_data: Dict, parent=None):
        super().__init__(parent)
        self.event_data = event_data
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        self.setWindowTitle("🌌 天象异动")
        self.setMinimumSize(500, 350)
        self.setStyleSheet("""
            QDialog {
                background-color: #0a0a1a;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 星空背景效果（用标签模拟）
        starfield = QLabel("✨ ★ ⭐ ✦ ★ ✧ ⭐ ★ ✦ ★")
        starfield.setStyleSheet("""
            color: #ffd700;
            font-size: 48px;
            qproperty-alignment: AlignCenter;
        """)
        starfield.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(starfield)

        # 事件名称
        event_name = QLabel(self.event_data.get('event_name', '天象'))
        event_name.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        event_name.setStyleSheet("color: #ffd700;")
        event_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(event_name)

        # 古语
        ancient_saying = QLabel(f"""
            <p style="font-family: 'KaiTi', 'STKaiti', serif; font-size: 16px; color: #c4a000; text-align: center; margin: 20px 0;">
                「{self.event_data.get('ancient_saying', '')}」
            </p>
        """)
        ancient_saying.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ancient_saying)

        # 提示
        hint = QLabel(f"天象频率：{self.event_data.get('frequency', '不定期')}")
        hint.setStyleSheet("color: #666; font-size: 12px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        layout.addStretch()

        # 关闭按钮
        close_btn = QPushButton("静心感悟")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a3a1a;
                color: #7fff7f;
                border: 2px solid #4a7c4a;
                padding: 10px 32px;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2a4a2a;
            }
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignCenter)


class EasterEggDiscoveryPanel(QWidget):
    """
    彩蛋发现面板 - 显示所有彩蛋的收集进度
    """

    # 信号
    egg_triggered = pyqtSignal(str, dict)  # egg_type, data

    def __init__(self, egg_manager=None, parent=None):
        super().__init__(parent)
        self.egg_manager = egg_manager
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        """设置UI"""
        self.setMinimumWidth(800)
        self.setMinimumHeight(500)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 标题区
        header = QHBoxLayout()

        title = QLabel("🌿 彩蛋发现")
        title.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #c4e8c4;")
        header.addWidget(title)

        header.addStretch()

        # 总览标签
        summary_label = QLabel()
        summary_label.setStyleSheet("color: #888; font-size: 12px;")
        header.addWidget(summary_label)
        self.summary_label = summary_label

        main_layout.addLayout(header)

        # Tab 页
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #333;
                background-color: #1a1a1a;
                border-radius: 8px;
            }
            QTabBar::tab {
                background-color: #2a2a2a;
                color: #888;
                padding: 10px 20px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background-color: #1a3a1a;
                color: #7fff7f;
            }
        """)

        # 彩蛋总览页
        overview_tab = self._create_overview_tab()
        tabs.addTab(overview_tab, "✨ 彩蛋总览")

        # 天文彩蛋页
        astronomical_tab = self._create_astronomical_tab()
        tabs.addTab(astronomical_tab, "🌌 星辰对话")

        # 古籍彩蛋页
        ancient_tab = self._create_ancient_tab()
        tabs.addTab(ancient_tab, "📜 断简残篇")

        # 音律彩蛋页
        music_tab = self._create_music_tab()
        tabs.addTab(music_tab, "🎵 林间回响")

        # 密文彩蛋页
        cipher_tab = self._create_cipher_tab()
        tabs.addTab(cipher_tab, "🔮 根系暗码")

        # 时代彩蛋页
        era_tab = self._create_era_tab()
        tabs.addTab(era_tab, "🌊 道韵潮汐")

        main_layout.addWidget(tabs, 1)

    def _create_overview_tab(self) -> QWidget:
        """创建彩蛋总览页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 七重彩蛋介绍
        egg_intro = [
            ("🌌", "天文彩蛋", "星辰对话", "在天文事件发生时触发，感受古人之观星智慧"),
            ("📜", "古籍彩蛋", "断简残篇", "深度检索古籍关键词，收集失传的古文碎片"),
            ("🎵", "音律彩蛋", "林间回响", "在安静环境下语音输入，开启林间密语模式"),
            ("🌱", "生长彩蛋", "意外共生", "连续七日深度探索，触发意外的道分支萌发"),
            ("🔄", "轮回彩蛋", "前世记忆", "改名时若寓意相反，唤醒前世的记忆片段"),
            ("🔮", "密文彩蛋", "根系暗码", "输入特定密码序列，收集神秘的根系图腾"),
            ("🌊", "时代彩蛋", "道韵潮汐", "在节气与节日时使用，感悟天时之道"),
        ]

        for icon, name, subtitle, desc in egg_intro:
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background-color: #2a2a2a;
                    border: 1px solid #333;
                    border-radius: 8px;
                    padding: 12px;
                    margin: 4px 0;
                }
            """)
            card_layout = QHBoxLayout(card)

            icon_label = QLabel(icon)
            icon_label.setStyleSheet("font-size: 28px;")
            icon_label.setFixedSize(50, 50)
            card_layout.addWidget(icon_label)

            text_layout = QVBoxLayout()
            name_label = QLabel(f"{name} · {subtitle}")
            name_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
            name_label.setStyleSheet("color: #c4e8c4;")
            text_layout.addWidget(name_label)

            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: #888; font-size: 11px;")
            text_layout.addWidget(desc_label)

            card_layout.addLayout(text_layout, 1)

            # 占位符
            card_layout.addSpacing(50)

            layout.addWidget(card)

        layout.addStretch()
        return widget

    def _create_astronomical_tab(self) -> QWidget:
        """创建天文彩蛋页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        title = QLabel("🌌 天象观测记录")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffd700;")
        layout.addWidget(title)

        hint = QLabel("在天文事件发生时可触发星辰对话，连续观测三次可解锁观星术雏形")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint)

        # 观测次数
        obs_count = self.egg_manager.get_observation_count() if self.egg_manager else 0
        obs_label = QLabel(f"已记录观测：{obs_count}/3 次")
        obs_label.setStyleSheet("color: #c4e8c4; font-size: 13px; margin: 10px 0;")
        layout.addWidget(obs_label)

        # 天象列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")

        container = QWidget()
        container_layout = QVBoxLayout(container)

        events_intro = [
            ("超级月亮", "每年3-4次", "🌕"),
            ("流星雨", "每年4次", "☄️"),
            ("日食", "每年2-5次", "🌑"),
            ("月食", "每年2-4次", "🌒"),
            ("冬至", "每年一次", "❄️"),
            ("夏至", "每年一次", "☀️"),
            ("春分", "每年一次", "🌸"),
            ("秋分", "每年一次", "🍂"),
        ]

        for name, frequency, icon in events_intro:
            event_card = QFrame()
            event_card.setStyleSheet("""
                QFrame {
                    background-color: #1a1a2a;
                    border: 1px solid #333;
                    border-radius: 8px;
                    padding: 10px;
                    margin: 3px 0;
                }
            """)
            event_layout = QHBoxLayout(event_card)

            icon_label = QLabel(icon)
            icon_label.setStyleSheet("font-size: 24px;")
            event_layout.addWidget(icon_label)

            name_label = QLabel(name)
            name_label.setStyleSheet("color: #c0c0c0; font-size: 13px;")
            event_layout.addWidget(name_label)

            event_layout.addStretch()

            freq_label = QLabel(frequency)
            freq_label.setStyleSheet("color: #666; font-size: 11px;")
            event_layout.addWidget(freq_label)

            container_layout.addWidget(event_card)

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        return widget

    def _create_ancient_tab(self) -> QWidget:
        """创建古籍彩蛋页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        title = QLabel("📜 断简残篇收藏")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffd700;")
        layout.addWidget(title)

        hint = QLabel("在知识林地中检索古籍关键词可收集碎片，集齐10片可合成完整古文")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint)

        # 收集按钮
        btn = QPushButton("📚 查看碎片收藏")
        btn.setStyleSheet("""
            QPushButton {
                background-color: #4a7c4a;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                margin: 10px 0;
            }
            QPushButton:hover {
                background-color: #5a8c5a;
            }
        """)
        btn.clicked.connect(self._show_fragment_dialog)
        layout.addWidget(btn)

        # 碎片列表（简化版）
        fragments = self.egg_manager.get_fragment_collection() if self.egg_manager else []

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout(container)

        if fragments:
            for f in fragments:
                frag_label = QLabel(f"📖 {f.get('source', '')}：{f.get('content', '')[:20]}...")
                frag_label.setStyleSheet("color: #a0a0a0; font-size: 11px; padding: 4px;")
                container_layout.addWidget(frag_label)
        else:
            empty = QLabel("尚未收集任何碎片...\n检索古籍关键词如「道德经」「易经」等可开始收集")
            empty.setStyleSheet("color: #666; text-align: center; padding: 30px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            container_layout.addWidget(empty)

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        return widget

    def _create_music_tab(self) -> QWidget:
        """创建音律彩蛋页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        title = QLabel("🎵 林间回响")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #9b59b6;")
        layout.addWidget(title)

        hint = QLabel("在安静环境（低环境音）下语音输入，将开启古琴泛音式的文字显现效果")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # 密语记录
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout(container)

        empty = QLabel("🎋 林间密语会被加密保存\n只有您和您的数字生命可以回顾\n\n在安静环境下说些什么吧...")
        empty.setStyleSheet("color: #666; text-align: center; padding: 50px; line-height: 1.8;")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(empty)

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        return widget

    def _create_cipher_tab(self) -> QWidget:
        """创建密文彩蛋页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        title = QLabel("🔮 根系暗码")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #9b59b6;")
        layout.addWidget(title)

        hint = QLabel("输入特定密码可收集神秘图腾，集齐7个不同图腾可拼出完整密文")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint)

        # 收集按钮
        btn = QPushButton("🔮 查看符号收藏")
        btn.setStyleSheet("""
            QPushButton {
                background-color: #8e44ad;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                margin: 10px 0;
            }
        """)
        btn.clicked.connect(self._show_cipher_dialog)
        layout.addWidget(btn)

        # 符号网格预览
        symbols = self.egg_manager.get_cipher_collection() if self.egg_manager else []

        grid = QGridLayout()
        grid.setSpacing(8)

        rarity_colors = {"common": "#888", "rare": "#3498db", "epic": "#9b59b6", "legendary": "#f39c12"}

        for i in range(7):
            row, col = i // 4, i % 4

            if i < len(symbols):
                sym = symbols[i]
                sym_frame = QFrame()
                sym_frame.setStyleSheet(f"""
                    background-color: #2a2a2a;
                    border: 2px solid {rarity_colors.get(sym.get('rarity', 'common'), '#888')};
                    border-radius: 6px;
                    padding: 8px;
                """)
                sym_layout = QVBoxLayout(sym_frame)
                sym_char = QLabel(sym.get('symbol', '?'))
                sym_char.setFont(QFont("Arial", 20))
                sym_char.setAlignment(Qt.AlignmentFlag.AlignCenter)
                sym_layout.addWidget(sym_char)
                sym_name = QLabel(sym.get('name', ''))
                sym_name.setFont(QFont("Microsoft YaHei", 8))
                sym_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
                sym_name.setStyleSheet("color: #888;")
                sym_layout.addWidget(sym_name)
            else:
                sym_frame = QFrame()
                sym_frame.setStyleSheet("""
                    background-color: #1a1a1a;
                    border: 2px dashed #444;
                    border-radius: 6px;
                    padding: 8px;
                    min-height: 60px;
                """)
                sym_layout = QVBoxLayout(sym_frame)
                sym_char = QLabel("?")
                sym_char.setFont(QFont("Arial", 20))
                sym_char.setAlignment(Qt.AlignmentFlag.AlignCenter)
                sym_char.setStyleSheet("color: #444;")
                sym_layout.addWidget(sym_char)

            grid.addWidget(sym_frame, row, col)

        layout.addLayout(grid)
        layout.addStretch()

        return widget

    def _create_era_tab(self) -> QWidget:
        """创建时代彩蛋页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        title = QLabel("🌊 道韵潮汐")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #3498db;")
        layout.addWidget(title)

        hint = QLabel("在节气与节日时使用客户端将获得特殊体验，相关大道修行效率临时提升50%")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # 当前节气/节日
        if self.egg_manager:
            solar_term = self.egg_manager.check_solar_term()
            festival = self.egg_manager.get_current_festival()

            if solar_term:
                term_card = QFrame()
                term_card.setStyleSheet(f"""
                    QFrame {{
                        background-color: {solar_term.get('color', '#2a2a2a')};
                        border-radius: 8px;
                        padding: 16px;
                        margin: 10px 0;
                    }}
                """)
                term_layout = QVBoxLayout(term_card)
                term_name = QLabel(f"今日节气：{solar_term.get('term', '')}")
                term_name.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
                term_name.setStyleSheet("color: #333;")
                term_layout.addWidget(term_name)
                term_poem = QLabel(f"「{solar_term.get('poem', '')}」")
                term_poem.setStyleSheet("color: #555; font-style: italic;")
                term_layout.addWidget(term_poem)
                term_dao = QLabel(f"相关大道：{solar_term.get('dao', '')}")
                term_dao.setStyleSheet("color: #666; font-size: 12px;")
                term_layout.addWidget(term_dao)
                layout.addWidget(term_card)

            if festival:
                fest_card = QFrame()
                fest_card.setStyleSheet(f"""
                    QFrame {{
                        background-color: {festival.get('color', '#2a2a2a')};
                        border-radius: 8px;
                        padding: 16px;
                        margin: 10px 0;
                    }}
                """)
                fest_layout = QVBoxLayout(fest_card)
                fest_name = QLabel(f"🎊 今日节日：{festival.get('name', '')}")
                fest_name.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
                fest_name.setStyleSheet("color: #333;")
                fest_layout.addWidget(fest_name)
                fest_dao = QLabel(f"相关大道：{festival.get('dao', '')}")
                fest_dao.setStyleSheet("color: #555; font-size: 12px;")
                fest_layout.addWidget(fest_dao)
                layout.addWidget(fest_card)

        # 二十四节气列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout(container)

        from ..digital_life.easter_eggs import SOLAR_TERMS
        for term, data in SOLAR_TERMS.items():
            term_row = QLabel(f"{data.get('date', '')} · {term} · {data.get('dao', '')}")
            term_row.setStyleSheet("color: #888; font-size: 11px; padding: 3px 0;")
            container_layout.addWidget(term_row)

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        return widget

    def _show_fragment_dialog(self):
        """显示碎片对话框"""
        fragments = self.egg_manager.get_fragment_collection() if self.egg_manager else []
        dialog = FragmentCollectionDialog(fragments, self)
        dialog.exec()

    def _show_cipher_dialog(self):
        """显示密文对话框"""
        symbols = self.egg_manager.get_cipher_collection() if self.egg_manager else []
        dialog = CipherCollectionDialog(symbols, self)
        dialog.exec()

    def _refresh(self):
        """刷新面板"""
        if self.egg_manager:
            summary = self.egg_manager.get_egg_discovery_summary()
            self.summary_label.setText(
                f"已发现：{summary['discovered_count']}/{summary['total_possible']} 个彩蛋"
            )
