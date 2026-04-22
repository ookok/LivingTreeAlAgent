"""
主界面功能卡片系统 - 核心卡片组件 (MainCard)
对应 13 大核心业务模块：
深度搜索、知识库、专家训练、智能IDE、分布式IM、项目生成、
企业管理、游戏世界、数字分身、虚拟云盘、下一代商城、邮箱、内部平台
"""

import logging
from typing import Optional, Callable

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QWidget, QApplication, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QFrame, QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QColor, QFont, QPalette

logger = logging.getLogger(__name__)

# ===== 全局配置：13 大核心模块 =========

MODULES_CONFIG = {
    "deep_search": {
        "icon": "🔍",
        "name": "深度搜索",
        "color": "#3b82f6",      # 蓝色
        "desc": "多源检索/语义分析/实时追踪",
        "status": "active"
    },
    "knowledge_base": {
        "icon": "🧠",
        "name": "知识库",
        "color": "#8b5cf6",      # 紫色
        "desc": "向量检索/RAG/私有化知识库构建",
        "status": "active"
    },
    "expert_training": {
        "icon": "🎓",
        "name": "专家训练",
        "color": "#10b981",      # 绿色
        "desc": "SFT微调/提示词库/技能链",
        "status": "normal"
    },
    "smart_ide": {
        "icon": "🛠️",
        "name": "智能IDE",
        "color": "#f59e0b",      # 橙色
        "desc": "代码生成/调试/集成开发环境",
        "status": "active"
    },
    "distributed_im": {
        "icon": "💬",
        "name": "分布式IM",
        "color": "#ec4899",      # 粉色
        "desc": "端到端加密/P2P通信/虚拟会议",
        "status": "active"
    },
    "project_generation": {
        "icon": "🧱",
        "name": "项目生成",
        "color": "#06b6d4",      # 青色
        "desc": "需求文档转代码/全栈自动生成",
        "status": "normal"
    },
    "enterprise_mgmt": {
        "icon": "🏢",
        "name": "企业管理",
        "color": "#6366f1",      # 靛蓝
        "desc": "组织协同/权限中心/数据流转",
        "status": "normal"
    },
    "game_world": {
        "icon": "🎮",
        "name": "游戏世界",
        "color": "#ef4444",      # 红色
        "desc": "沉浸式体验/数字资产经济与交互",
        "status": "active"
    },
    "digital_avatar": {
        "icon": "🤖",
        "name": "数字分身",
        "color": "#84cc16",      # 黄绿
        "desc": "克隆/虚拟形象/自动化交互代理",
        "status": "active"
    },
    "virtual_cloud": {
        "icon": "☁️",
        "name": "虚拟云盘",
        "color": "#38bdf8",      # 天空蓝
        "desc": "P2P加密存储/文件实时同步",
        "status": "normal"
    },
    "mall": {
        "icon": "🛒",
        "name": "下一代商城",
        "color": "#f43f5e",      # 玫红
        "desc": "积分支付/区块链确权/生态交易",
        "status": "normal"
    },
    "email": {
        "icon": "✉️",
        "name": "邮箱",
        "color": "#94a3b8",      # 蓝灰
        "desc": "智能收件箱/自动分类/加密通信",
        "status": "normal"
    },
    "internal_platform": {
        "icon": "🌐",
        "name": "内部平台",
        "color": "#2dd4bf",      # 绿松石
        "desc": "企业门户/应用分发/权限中心",
        "status": "normal"
    },
}


class MainCardStatus:
    """卡片状态枚举"""
    NORMAL = "normal"
    ACTIVE = "active"
    LOCKED = "locked"
    DISABLED = "disabled"


class MainCardIcon:
    """预设图标映射"""
    DEEP_SEARCH = "🔍"
    KNOWLEDGE = "🧠"
    EXPERT = "🎓"
    IDE = "🛠️"
    IM = "💬"
    PROJECT = "🧱"
    ENTERPRISE = "🏢"
    GAME = "🎮"
    AVATAR = "🤖"
    CLOUD = "☁️"
    MALL = "🛒"
    EMAIL = "✉️"
    PLATFORM = "🌐"


class MainCard(QFrame):
    """
    主功能卡片——对应 13 大核心业务

    信号:
        card_clicked(module_id: str) - 卡片被点击
    """

    card_clicked = pyqtSignal(str)

    def __init__(
        self,
        module_id: str,
        status: str = MainCardStatus.NORMAL,
        callback: Optional[Callable[[str], None]] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.module_id = module_id
        self.status = status
        self.m_config = MODULES_CONFIG.get(module_id, {
            "icon": "📦",
            "name": module_id,
            "color": "#d1d5db",
            "desc": "模块开发中..."
        })
        self.callback = callback

        # 尺寸设置
        self.setObjectName("MainCard")
        self.setMinimumSize(230, 150)
        self.setMaximumSize(260, 160)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # 阴影效果
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(20)
        self.shadow.setColor(QColor(0, 0, 0, 80))
        self.shadow.setOffset(0, 4)
        self.setGraphicsEffect(self.shadow)

        # 构建 UI
        self._build_ui()
        self._update_style()

    def _build_ui(self):
        """构建卡片内部布局"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 卡片内容框架
        content_frame = QFrame(self)
        content_frame.setObjectName("MainCardFrame")
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)

        # 第一部分：图标 + 标题
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        # 图标
        icon_label = QLabel(self.m_config.get("icon", "📦"))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_color = self.m_config.get("color", "#e5e7eb")
        icon_label.setStyleSheet(f"""
            font-size: 28px;
            background: {icon_color}20;
            border-radius: 16px;
            padding: 4px;
        """)
        icon_label.setFixedSize(48, 48)
        header_layout.addWidget(icon_label)

        # 标题组
        title_group = QVBoxLayout()
        title_label = QLabel(self.m_config.get("name", ""))
        title_label.setObjectName("CardTitle")
        title_label.setStyleSheet("""
            font-size: 15px;
            font-weight: bold;
            color: #1f2937;
            border: none;
        """)
        title_group.addWidget(title_label)

        # 状态标签
        status_text = "活跃" if self.status == MainCardStatus.ACTIVE else "就绪"
        if self.status == MainCardStatus.LOCKED:
            status_text = "锁定"
        elif self.status == MainCardStatus.DISABLED:
            status_text = "禁用"

        status_label = QLabel(status_text)
        status_label.setObjectName("CardStatus")
        status_label.setStyleSheet(f"""
            font-size: 10px;
            color: #6b7280;
            background: #f3f4f6;
            border-radius: 4px;
            padding: 2px 6px;
        """)
        title_group.addWidget(status_label)
        title_group.addStretch()
        header_layout.addLayout(title_group)

        header_layout.addStretch()
        content_layout.addLayout(header_layout)

        # 描述文字
        desc_label = QLabel(self.m_config.get("desc", ""))
        desc_label.setObjectName("CardDesc")
        desc_label.setStyleSheet("font-size: 11px; color: #6b7280;")
        desc_label.setWordWrap(True)
        desc_label.setMaximumWidth(200)
        content_layout.addWidget(desc_label)

        # 操作按钮行
        if self.status in (MainCardStatus.NORMAL, MainCardStatus.ACTIVE):
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()

            btn = QPushButton("打开")
            btn.setObjectName("CardActionBtn")
            btn.setFixedSize(56, 28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton#CardActionBtn {{
                    background: {icon_color};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: bold;
                }}
                QPushButton#CardActionBtn:hover {{
                    background: {icon_color}cc;
                }}
            """)
            btn.clicked.connect(lambda: self._on_click())
            btn_layout.addWidget(btn)
            content_layout.addLayout(btn_layout)

        content_layout.addStretch()
        main_layout.addWidget(content_frame)

    def _update_style(self):
        """根据状态更新样式"""
        base_color = self.m_config.get("color", "#e5e7eb")

        if self.status == MainCardStatus.LOCKED:
            style = f"""
                QFrame#MainCard {{
                    background: #f3f4f6;
                    border: 1px dashed #d1d5db;
                    border-radius: 12px;
                }}
                QFrame#MainCardFrame {{
                    background: white;
                    border: 1px solid #e5e7eb;
                    border-radius: 8px;
                }}
                QFrame#MainCardFrame:hover {{
                    background: white;
                }}
            """

        elif self.status == MainCardStatus.ACTIVE:
            style = f"""
                QFrame#MainCard {{
                    background: {base_color}15;
                    border: 2px solid {base_color};
                    border-radius: 12px;
                }}
                QFrame#MainCardFrame {{
                    background: white;
                    border: 1px solid {base_color};
                    border-radius: 8px;
                }}
            """

        else:  # NORMAL / DISABLED
            style = f"""
                QFrame#MainCard {{
                    background: transparent;
                    border: 1px solid #e5e7eb;
                    border-radius: 12px;
                }}
                QFrame#MainCard:hover {{
                    background: {base_color}15;
                    border: 1px solid {base_color};
                    border-radius: 12px;
                }}
                QFrame#MainCardFrame {{
                    background: white;
                    border: 1px solid #e5e7eb;
                    border-radius: 8px;
                }}
            """

        self.setStyleSheet(style)

    def setStatus(self, status: str):
        """设置卡片状态"""
        self.status = status
        self._update_style()
        # 更新状态标签文字
        for child in self.findChildren(QLabel):
            if child.objectName() == "CardStatus":
                if status == MainCardStatus.ACTIVE:
                    child.setText("活跃")
                elif status == MainCardStatus.LOCKED:
                    child.setText("锁定")
                elif status == MainCardStatus.DISABLED:
                    child.setText("禁用")
                else:
                    child.setText("就绪")
                break

    def _on_click(self):
        """内部点击处理，发射信号"""
        self.card_clicked.emit(self.module_id)
        if self.callback:
            self.callback(self.module_id)

    def mousePressEvent(self, event):
        """鼠标按下处理"""
        if self.status in (MainCardStatus.NORMAL, MainCardStatus.ACTIVE):
            self.card_clicked.emit(self.module_id)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        """鼠标进入：加深阴影"""
        if self.status in (MainCardStatus.NORMAL, MainCardStatus.ACTIVE):
            c = QColor(self.m_config.get("color", "#3b82f6"), 150)
            self.shadow.setColor(c)
            self.shadow.setBlurRadius(25)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开：恢复阴影"""
        self.shadow.setColor(QColor(0, 0, 0, 80))
        self.shadow.setBlurRadius(20)
        super().leaveEvent(event)


class MainCardGrid(QWidget):
    """
    主界面功能卡片网格管理器

    功能：
    - 动态布局 13 张功能卡片
    - 自动适配窗口大小
    - 卡片点击信号传递给外部
    """

    trigger_module = pyqtSignal(str)  # 卡片被点击

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.cards = []
        self._modules = list(MODULES_CONFIG.keys())
        self._init_grid()

    def _init_grid(self):
        """初始化网格布局"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(16)

        # 使用 QScrollArea 支持滚动
        from PyQt6.QtWidgets import QScrollArea
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget()
        self.grid_layout = QVBoxLayout(scroll_content)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_layout.setSpacing(16)

        # 设置流式布局 (从左到右，自动换行)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll.setWidget(scroll_content)
        main_layout.addWidget(self.scroll)

        # 填充所有模块
        for mid in self._modules:
            self.add_card(mid)

    def add_card(self, module_id: str, status: str = MainCardStatus.NORMAL):
        """添加单张卡片到网格"""
        if module_id not in MODULES_CONFIG:
            logger.warning(f"Unknown module_id: {module_id}")
            return

        card = MainCard(module_id, status)
        card.card_clicked.connect(self._on_card_clicked)
        self.cards.append(card)
        self.grid_layout.addWidget(card)

    def clear(self):
        """清空所有卡片"""
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
        self.cards.clear()

    def load_all(self):
        """加载全部 13 个模块"""
        self.clear()
        for mid, config in MODULES_CONFIG.items():
            status = config.get("status", MainCardStatus.NORMAL)
            self.add_card(mid, status)

    def set_card_status(self, module_id: str, status: str):
        """更新指定卡片的显示状态"""
        for card in self.cards:
            if card.module_id == module_id:
                card.setStatus(status)
                break

    def get_card_status(self, module_id: str) -> str:
        """获取卡片当前状态"""
        for card in self.cards:
            if card.module_id == module_id:
                return card.status
        return MainCardStatus.LOCKED

    def enable_card(self, module_id: str):
        """启用卡片（解锁）"""
        self.set_card_status(module_id, MainCardStatus.ACTIVE)
        # 更新配置
        if module_id in MODULES_CONFIG:
            MODULES_CONFIG[module_id]["status"] = "active"

    def disable_card(self, module_id: str):
        """禁用卡片（锁定）"""
        self.set_card_status(module_id, MainCardStatus.LOCKED)
        if module_id in MODULES_CONFIG:
            MODULES_CONFIG[module_id]["status"] = "normal"

    def _on_card_clicked(self, module_id: str):
        """卡片点击事件转发"""
        self.trigger_module.emit(module_id)
        logger.info(f"MainCard clicked: {module_id}")


# ====== 测试入口 ======

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel

    app = QApplication(sys.argv)

    class TestWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("🌳 LivingTree AI Agent - 13 Core Functions")
            self.setMinimumSize(1000, 700)

            central = QWidget()
            self.setCentralWidget(central)
            layout = QVBoxLayout(central)
            layout.setContentsMargins(0, 0, 0, 0)

            # 标题
            title = QLabel("🌳 LivingTree AI Agent - 13 Core Functions")
            title.setObjectName("PageTitle")
            title.setStyleSheet("""
                font-size: 22px;
                font-weight: bold;
                color: #111827;
                padding: 16px;
            """)
            layout.addWidget(title)

            # 卡片网格
            self.grid = MainCardGrid()
            self.grid.load_all()
            self.grid.trigger_module.connect(self._on_module_open)
            layout.addWidget(self.grid)

        def _on_module_open(self, module_id: str):
            print(f"Opening module: {module_id}")

    win = TestWindow()
    win.show()
    sys.exit(app.exec())
