"""
MainPage - 主界面页面板
集成 13 大功能卡片系统作为首页展示
对应需求：深度搜索、知识库、专家训练、智能IDE、分布式IM、
项目生成、企业管理、游戏世界、数字分身、虚拟云盘、下一代商城、
邮箱、内部平台
"""
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget,
    QLineEdit, QFrame, QGridLayout,
)

from ui.main_cards.main_card import (
    MODULES_CONFIG,
    MainCard,
    MainCardStatus,
)


class MainPage(QWidget):
    """
    主界面页面板

    功能:
    1. 展示 13 大核心功能卡片
    2. 管理卡片状态 (激活/锁定/禁用)
    3. 将卡片点击事件传递到外部
    4. 提供搜索过滤功能
    5. 模块切换和导航
    """

    # 信号定义
    module_requested = pyqtSignal(str)  # 用户请求打开某模块
    module_opened = pyqtSignal(str)     # 模块被打开的信号
    module_closed = pyqtSignal(str)     # 模块被关闭的信号
    status_changed = pyqtSignal(str, str)  # 模块状态变化 (module_id, new_status)
    grid_loaded = pyqtSignal(int)       # 网格加载完成 (卡片数量)

    HEADER_HEIGHT = 72
    CARD_MIN_WIDTH = 230
    CARD_GAP = 20

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._panels: dict[str, QWidget] = {}
        self._active_cards: dict[str, MainCard] = {}
        self._init_ui()
        self._load_main_grid()

    def _init_ui(self):
        """初始化 UI 根布局"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setStyleSheet("background-color: #f5f6fa;")

        # 顶部栏
        self.header = self._create_header()
        main_layout.addWidget(self.header)

        # 主内容区 (堆叠 widget)
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack, 1)

    def _create_header(self) -> QFrame:
        """创建顶部标题栏"""
        header_frame = QFrame()
        header_frame.setObjectName("MainPageHeader")
        header_frame.setFixedHeight(self.HEADER_HEIGHT)
        header_frame.setStyleSheet("""
            QFrame#MainPageHeader {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0f172a, stop:1 #1e293b);
            }
        """)

        layout = QHBoxLayout(header_frame)
        layout.setContentsMargins(24, 12, 24, 12)

        # 左侧应用标题
        app_icon = QLabel("🌳")
        app_icon.setFixedSize(36, 36)
        app_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_icon.setStyleSheet("font-size: 28px;")
        layout.addWidget(app_icon)

        app_title = QLabel("LivingTree AI Agent")
        app_title.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: white;
            padding: 0 8px;
        """)
        layout.addWidget(app_title)

        # 弹性空间
        layout.addStretch()

        # 搜索框
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("🔍 搜索功能模块...")
        self.search_field.setFixedSize(320, 38)
        self.search_field.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.12);
                border: 1px solid rgba(255, 255, 255, 0.25);
                border-radius: 10px;
                padding: 0 16px;
                color: white;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid rgba(255, 255, 255, 0.6);
                background: rgba(255, 255, 255, 0.18);
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.5);
            }
        """)
        self.search_field.textChanged.connect(self._filter_cards)
        layout.addWidget(self.search_field)

        layout.addSpacing(16)

        # 设置按钮
        settings_btn = QPushButton("⚙️")
        settings_btn.setFixedSize(40, 40)
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 10px;
                color: white;
                font-size: 18px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.3);
            }
        """)
        settings_btn.clicked.connect(self._show_settings)
        layout.addWidget(settings_btn)

        return header_frame

    def _load_main_grid(self):
        """加载主卡片网格"""
        grid_frame = GridFrame()
        grid_frame.load_all()
        grid_frame.trigger_module.connect(self._on_card_clicked)

        self.content_stack.addWidget(grid_frame)
        self.content_stack.setCurrentIndex(0)
        self._active_grid = grid_frame
        self._active_cards = {c.module_id: c for c in grid_frame.cards}

        # 通知网格加载完成
        self.grid_loaded.emit(len(grid_frame.cards))

    def _on_card_clicked(self, module_id: str):
        """处理卡片点击事件"""
        self.module_requested.emit(module_id)
        card = self._active_cards.get(module_id)
        if not card:
            return

        if card.status == MainCardStatus.LOCKED:
            self._show_locked_dialog(module_id)
        elif card.status in (MainCardStatus.NORMAL, MainCardStatus.ACTIVE):
            self._open_module(module_id)

    def _open_module(self, module_id: str):
        """打开对应模块面板"""
        self.module_opened.emit(module_id)
        card = self._active_cards.get(module_id)
        if card:
            card.setStatus(MainCardStatus.ACTIVE)

        # TODO: 动态加载对应 Panel
        # 例如: from ui.knowledge_base_panel import KnowledgeBasePanel
        #       panel = KnowledgeBasePanel()
        #       self.content_stack.addWidget(panel)
        #       self.content_stack.setCurrentWidget(panel)
        print(f"[MainPage] Opening module: {module_id}")

    def _show_locked_dialog(self, module_id: str):
        """显示锁定模块的提示对话框"""
        print(f"[MainPage] Module '{module_id}' is locked")
        # TODO: 实现 QMessageBox 或自定义 Dialog

    def _show_settings(self):
        """显示设置面板"""
        print("[MainPage] Opening settings...")
        # TODO: 实现设置面板

    def _filter_cards(self, text: str):
        """搜索过滤卡片"""
        if not text:
            for card in self._active_cards.values():
                card.setVisible(True)
            return

        text_lower = text.lower()
        for card in self._active_cards.values():
            config = MODULES_CONFIG.get(card.module_id, {})
            match = (
                card.module_id in text_lower
                or config.get("name", "").lower() in text_lower
                or config.get("desc", "").lower() in text_lower
            ) or text_lower in config.get("icon", "")
            card.setVisible(match)

    def update_module_status(self, module_id: str, status: str):
        """更新模块状态"""
        card = self._active_cards.get(module_id)
        if card:
            card.setStatus(status)
        self.status_changed.emit(module_id, status)
        if module_id in MODULES_CONFIG:
            MODULES_CONFIG[module_id]["status"] = status

    def get_module_status(self, module_id: str) -> str:
        """获取模块状态"""
        card = self._active_cards.get(module_id)
        return card.status if card else MainCardStatus.LOCKED

    def set_module_enabled(self, module_id: str, enabled: bool):
        """设置模块可用/禁用"""
        status = MainCardStatus.ACTIVE if enabled else MainCardStatus.LOCKED
        self.update_module_status(module_id, status)

    def show_module_panel(self, module_id: str, panel_widget: QWidget):
        """手动切换到指定模块面板"""
        self._panels[module_id] = panel_widget
        self.content_stack.addWidget(panel_widget)
        self.content_stack.setCurrentWidget(panel_widget)
        self.module_opened.emit(module_id)


class GridFrame(QFrame):
    """卡片网格容器"""
    trigger_module = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards: list[MainCard] = []
        self._layout: Optional[QGridLayout] = None
        self.setStyleSheet("background: transparent;")
        
        self._init_layout()
        self._populate()

    def _init_layout(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(0)

        container = QWidget()
        self._layout = QGridLayout(container)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(20)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(container)
        self._container = container

    def _populate(self):
        for module_id, config in MODULES_CONFIG.items():
            self.add_card(module_id, config.get("status", MainCardStatus.NORMAL))

    def add_card(self, module_id: str, status: str = MainCardStatus.NORMAL):
        card = MainCard(module_id, status)
        card.card_clicked.connect(self.trigger_module)
        self.cards.append(card)
        
        row = len(self.cards) // 4
        col = len(self.cards) % 4
        if self._layout:
            self._layout.addWidget(card, row, col)

    def load_all(self):
        for module_id in MODULES_CONFIG:
            self.add_card(module_id, MODULES_CONFIG[module_id].get("status", MainCardStatus.NORMAL))

    def clear(self):
        for card in self.cards:
            card.setParent(None)
            card.deleteLater()
        self.cards.clear()
