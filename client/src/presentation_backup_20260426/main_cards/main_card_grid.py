"""
MainCardGrid - 13大功能卡片网格布局器
提供流式网格展示、自适应列数、动态添加/移除卡片
"""
from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QFrame, QGridLayout, QLabel
)

from ui.main_cards.main_card import (
    MODULES_CONFIG,
    MainCard,
    MainCardStatus,
)


class MainCardGrid(QFrame):
    """
    主功能卡片网格管理器

    功能:
    - 流式网格布局 (从左到右, 自动换行)
    - 自适应列数 (根据窗口宽度)
    - 支持动态添加/移除/更新卡片
    - 卡片点击信号传递给外部
    """

    trigger_module = pyqtSignal(str)  # 卡片被点击
    grid_resized = pyqtSignal(int, int)  # 网格行数, 列数

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.cards: List[MainCard] = []
        self._module_map: dict[str, MainCard] = {}
        self._grid_layout: Optional[QGridLayout] = None
        self._container: Optional[QWidget] = None
        self._scroll_area: Optional[QScrollArea] = None

        self.setObjectName("MainCardGrid")
        self._init_grid()

    def _init_grid(self):
        """初始化网格布局容器"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # 创建支持滚动的容器
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        # 内容容器
        self._container = QWidget()
        self._grid_layout = QGridLayout(self._container)
        self._grid_layout.setContentsMargins(12, 12, 12, 12)
        self._grid_layout.setSpacing(16)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self._scroll_area.setWidget(self._container)
        main_layout.addWidget(self._scroll_area)

        # 初始加载 13 个模块
        self.load_all()

    def load_all(self):
        """加载全部 13 个模块"""
        self.clear()
        for module_id, config in MODULES_CONFIG.items():
            status = config.get("status", MainCardStatus.NORMAL)
            self.add_card(module_id, status)

    def add_card(self, module_id: str, status: str = MainCardStatus.NORMAL):
        """
        向网格添加一张卡片

        Args:
            module_id: 模块标识符
            status: 卡片状态 (NORMAL/ACTIVE/LOCKED/DISABLED)
        """
        if module_id not in MODULES_CONFIG:
            return

        card = MainCard(module_id, status)
        card.card_clicked.connect(self.trigger_module)
        self.cards.append(card)
        self._module_map[module_id] = card

        # 计算位置: 在网格中按行/列排列
        row = len(self.cards) // self._calc_columns()
        col = len(self.cards) % self._calc_columns()
        if self._grid_layout:
            self._grid_layout.addWidget(card, row, col)

    def clear(self):
        """清空网格中的所有卡片"""
        for card in self.cards:
            card.setParent(None)
            card.deleteLater()
        self.cards.clear()
        self._module_map.clear()

    def remove_card(self, module_id: str):
        """移除指定模块的卡片"""
        if module_id not in self._module_map:
            return
        card = self._module_map.pop(module_id)
        if module_id in self.cards:
            self.cards.remove(module_id)
        card.setParent(None)
        card.deleteLater()

    def set_card_status(self, module_id: str, status: str):
        """更新指定卡片的显示状态"""
        if module_id not in self._module_map:
            return
        card = self._module_map[module_id]
        card.setStatus(status)
        if module_id in MODULES_CONFIG:
            MODULES_CONFIG[module_id]["status"] = "active" if status == MainCardStatus.ACTIVE else "normal"

    def get_card_status(self, module_id: str) -> str:
        """获取卡片当前状态"""
        if module_id not in self._module_map:
            return MainCardStatus.LOCKED
        return self._module_map[module_id].status

    def enable_card(self, module_id: str):
        """启用卡片 (解锁/激活状态)"""
        self.set_card_status(module_id, MainCardStatus.ACTIVE)

    def disable_card(self, module_id: str):
        """禁用卡片 (锁定状态)"""
        self.set_card_status(module_id, MainCardStatus.LOCKED)

    def get_card(self, module_id: str) -> Optional[MainCard]:
        """获取指定卡片实例"""
        return self._module_map.get(module_id)

    def get_all_cards(self) -> List[MainCard]:
        """获取所有卡片列表"""
        return self.cards

    def _calc_columns(self) -> int:
        """根据可用宽度计算最佳列数"""
        if not self._container:
            return 4
        available_width = self._container.width() - 24
        if available_width <= 0:
            return 1
        cols = max(1, available_width // 260)
        return cols

    def resizeEvent(self, event):
        """窗口大小变化时重新计算布局"""
        super().resizeEvent(event)
        if not self._grid_layout or not self.cards:
            return
        temp_cards = self.cards[:]
        for card in self.cards:
            card.setParent(None)
        self.cards.clear()
        for card in temp_cards:
            self._module_map[card.module_id] = card
            self.cards.append(card)
            row = len(self.cards) // self._calc_columns()
            col = len(self.cards) % self._calc_columns()
            if self._grid_layout:
                self._grid_layout.addWidget(card, row, col)

    @property
    def module_count(self) -> int:
        """网格中的卡片数量"""
        return len(self.cards)

    @property
    def active_modules(self) -> List[str]:
        """获取所有激活状态的模块 ID 列表"""
        return [c.module_id for c in self.cards if c.status == MainCardStatus.ACTIVE]
