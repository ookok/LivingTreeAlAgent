"""
游戏中心窗口 - Game Center

支持多种游戏类型：
- 文字冒险
- 策略游戏
- 益智游戏
- 角色扮演
"""

from typing import List, Dict, Optional
from enum import Enum

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QPushButton, QScrollArea,
    QListWidget, QListWidgetItem, QStackedWidget,
    QTextEdit, QProgressBar, QDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from client.src.presentation.framework.minimal_ui_framework import (
    ColorScheme, Spacing, MinimalCard, UIComponentFactory
)


class GameType(Enum):
    """游戏类型"""
    ADVENTURE = "adventure"
    STRATEGY = "strategy"
    PUZZLE = "puzzle"
    RPG = "rpg"


class GameCard(QFrame):
    """游戏卡片"""
    
    game_selected = pyqtSignal(dict)
    
    def __init__(self, game_info: Dict, parent=None):
        super().__init__(parent)
        self._game_info = game_info
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        self.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
            }
            QFrame:hover {
                border-color: #3B82F6;
                box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
            }
        """)
        
        # 游戏图标
        icon_label = QLabel(self._game_info.get("icon", "🎮"))
        icon_label.setStyleSheet("font-size: 40px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        
        # 游戏名称
        name_label = UIComponentFactory.create_label(
            self, self._game_info["name"], ColorScheme.TEXT_PRIMARY, 14
        )
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        layout.addWidget(name_label)
        
        # 游戏类型标签
        type_label = UIComponentFactory.create_label(
            self, f"{self._game_info.get('type', '')}", ColorScheme.TEXT_SECONDARY, 11
        )
        type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(type_label)
        
        # 评分
        rating_label = QLabel(f"⭐ {self._game_info.get('rating', 0)}/5")
        rating_label.setStyleSheet("font-size: 12px; color: #F59E0B;")
        rating_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(rating_label)
    
    def mousePressEvent(self, event):
        self.game_selected.emit(self._game_info)


class AdventureGame(QWidget):
    """文字冒险游戏"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._story = []
        self._current_index = 0
        self._setup_ui()
        self._load_story()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # 故事文本
        self.story_text = QTextEdit()
        self.story_text.setReadOnly(True)
        self.story_text.setStyleSheet("""
            QTextEdit {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 16px;
                font-size: 14px;
                line-height: 1.6;
            }
        """)
        layout.addWidget(self.story_text, 1)
        
        # 选项按钮
        self.options_layout = QVBoxLayout()
        self.options_layout.setSpacing(8)
        layout.addLayout(self.options_layout)
    
    def _load_story(self):
        """加载故事数据"""
        self._story = [
            {
                "text": "你醒来发现自己身处一个神秘的森林中。四周漆黑一片，只有远处有微弱的光芒。你决定：",
                "options": ["朝着光芒前进", "先探索周围环境", "尝试呼救"]
            },
            {
                "text": "你朝着光芒走去，发现了一座古老的城堡。城堡的大门半开着，里面传来奇怪的声音。",
                "options": ["进入城堡", "在门口观察", "寻找其他入口"]
            },
            {
                "text": "城堡内部装饰华丽但布满灰尘。你看到一幅画像，画中人竟然和你长得一模一样！",
                "options": ["仔细观察画像", "继续深入城堡", "逃离这里"]
            }
        ]
        self._show_current_story()
    
    def _show_current_story(self):
        """显示当前故事"""
        if self._current_index < len(self._story):
            story = self._story[self._current_index]
            self.story_text.setPlainText(story["text"])
            
            # 清除旧选项
            while self.options_layout.count() > 0:
                item = self.options_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            # 添加新选项
            for i, option in enumerate(story["options"]):
                btn = UIComponentFactory.create_button(
                    self, f"{i + 1}. {option}", variant="secondary", size="md"
                )
                btn.clicked.connect(lambda checked, idx=i: self._select_option(idx))
                self.options_layout.addWidget(btn)
        else:
            self.story_text.setPlainText("🎉 恭喜你完成了冒险！")
    
    def _select_option(self, option_index):
        """选择选项"""
        self._current_index += 1
        self._show_current_story()


class GameCenterWindow(QWidget):
    """游戏中心主窗口"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._games = self._load_games()
        self._setup_ui()
    
    def _load_games(self) -> List[Dict]:
        """加载游戏列表"""
        return [
            {"id": 1, "name": "神秘森林", "type": "冒险", "icon": "🌲", "rating": 4.8},
            {"id": 2, "name": "策略大师", "type": "策略", "icon": "⚔️", "rating": 4.5},
            {"id": 3, "name": "数独挑战", "type": "益智", "icon": "🧩", "rating": 4.7},
            {"id": 4, "name": "魔法学院", "type": "RPG", "icon": "🏰", "rating": 4.9},
            {"id": 5, "name": "迷宫探险", "type": "冒险", "icon": "🗺️", "rating": 4.3},
            {"id": 6, "name": "卡牌对决", "type": "策略", "icon": "🃏", "rating": 4.6},
        ]
    
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
        
        title_label = UIComponentFactory.create_label(
            title_bar, "🎮 游戏中心", ColorScheme.TEXT_PRIMARY, 16
        )
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        layout.addWidget(title_bar)
        
        # 主内容区
        main_content = QWidget()
        main_layout = QHBoxLayout(main_content)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)
        
        # 游戏列表
        games_list = QWidget()
        games_layout = QVBoxLayout(games_list)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
            }
        """)
        
        games_grid = QWidget()
        grid_layout = QGridLayout(games_grid)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(12)
        
        for i, game in enumerate(self._games):
            card = GameCard(game)
            card.game_selected.connect(self._on_game_selected)
            card.setFixedSize(150, 180)
            grid_layout.addWidget(card, i // 3, i % 3)
        
        scroll_area.setWidget(games_grid)
        games_layout.addWidget(scroll_area)
        
        main_layout.addWidget(games_list, 1)
        
        # 游戏详情/游戏界面
        self.game_area = QStackedWidget()
        self.game_area.setFixedWidth(400)
        self.game_area.setStyleSheet("""
            QStackedWidget {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
            }
        """)
        
        # 默认欢迎界面
        welcome_page = QWidget()
        welcome_layout = QVBoxLayout(welcome_page)
        welcome_layout.setContentsMargins(32, 32, 32, 32)
        welcome_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        welcome_icon = QLabel("🎮")
        welcome_icon.setStyleSheet("font-size: 64px;")
        welcome_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.addWidget(welcome_icon)
        
        welcome_text = UIComponentFactory.create_label(
            welcome_page, "选择一个游戏开始冒险", ColorScheme.TEXT_SECONDARY, 14
        )
        welcome_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.addWidget(welcome_text)
        
        self.game_area.addWidget(welcome_page)
        
        main_layout.addWidget(self.game_area)
        
        layout.addWidget(main_content, 1)
    
    def _on_game_selected(self, game_info: Dict):
        """游戏选中处理"""
        # 如果是冒险游戏，打开冒险游戏界面
        if game_info["type"] == "冒险":
            game_widget = AdventureGame()
            self.game_area.addWidget(game_widget)
            self.game_area.setCurrentWidget(game_widget)
        else:
            # 其他游戏类型显示占位界面
            placeholder = QWidget()
            layout = QVBoxLayout(placeholder)
            layout.setContentsMargins(32, 32, 32, 32)
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            icon = QLabel(game_info.get("icon", "🎮"))
            icon.setStyleSheet("font-size: 48px;")
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(icon)
            
            text = UIComponentFactory.create_label(
                placeholder, f"{game_info['name']} 开发中...", ColorScheme.TEXT_SECONDARY, 14
            )
            text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(text)
            
            self.game_area.addWidget(placeholder)
            self.game_area.setCurrentWidget(placeholder)