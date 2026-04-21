"""
首页推荐 Tab
聚合展示：推荐卡片流 + 模块切换 + 设置
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget,
    QFrame, QScrollArea, QMenu,
    QCheckBox, QGroupBox, QDialog, QDialogButtonBox,
    QListWidget, QListWidgetItem
)
from PyQt6.QtGui import QAction

from core.module_manager import get_module_manager, ModuleConfig
from ui.recommendation_panel import RecommendationPanel


class HomePageTab(QWidget):
    """
    首页推荐Tab
    包含推荐内容流和模块管理
    """
    
    # 模块切换信号
    module_changed = pyqtSignal(str)  # 切换到的模块ID
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 模块管理器
        self.module_manager = get_module_manager()
        
        # 面板实例
        self._panels: dict[str, QWidget] = {}
        
        self.setup_ui()
        self.apply_style()
        
        # 默认显示推荐
        self.show_module("recommendation")
    
    def setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 顶部栏：模块切换 + 设置
        header = self._create_header()
        main_layout.addWidget(header)
        
        # 主内容区
        self.content_stack = QStackedWidget()
        self.content_stack.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.content_stack)
    
    def _create_header(self) -> QWidget:
        """创建顶部栏"""
        header = QWidget()
        header.setFixedHeight(56)
        header.setStyleSheet("background: white; border-bottom: 1px solid #e5e7eb;")
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)
        
        # 标题
        title = QLabel("🏠 首页")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f2937;")
        layout.addWidget(title)
        
        layout.addStretch()
        
        # 设置按钮
        settings_btn = QPushButton("⚙️")
        settings_btn.setFixedSize(36, 36)
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.clicked.connect(self._show_settings)
        settings_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: #f3f4f6;
            }
        """)
        layout.addWidget(settings_btn)
        
        return header
    
    def _create_module_content(self, module_id: str) -> QWidget:
        """创建模块内容"""
        if module_id == "recommendation":
            return RecommendationPanel()
        elif module_id == "game_hall":
            return self._create_game_hall_placeholder()
        else:
            return self._create_placeholder(module_id)
    
    def _create_placeholder(self, module_id: str) -> QWidget:
        """创建占位组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_label = QLabel("🚧")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 48px;")
        layout.addWidget(icon_label)
        
        name = self.module_manager.get_module(module_id)
        name_text = name.name if name else module_id
        
        label = QLabel(f"{name_text} 模块开发中...")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 16px; color: #6b7280; margin-top: 12px;")
        layout.addWidget(label)
        
        return widget
    
    def _create_game_hall_placeholder(self) -> QWidget:
        """创建游戏世界占位"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)
        
        # 图标
        icon_label = QLabel("🎮")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 64px;")
        layout.addWidget(icon_label)
        
        # 标题
        title = QLabel("游戏世界")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1f2937;")
        layout.addWidget(title)
        
        # 描述
        desc = QLabel("AI对战棋牌游戏\n斗地主 · 四川麻将")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("font-size: 14px; color: #6b7280;")
        layout.addWidget(desc)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        # 斗地主按钮
        ddz_btn = QPushButton("🃏 斗地主")
        ddz_btn.setFixedSize(120, 40)
        ddz_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ddz_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #2563eb;
            }
        """)
        btn_layout.addWidget(ddz_btn)
        
        # 麻将按钮
        majiang_btn = QPushButton("🀄 四川麻将")
        majiang_btn.setFixedSize(120, 40)
        majiang_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        majiang_btn.setStyleSheet("""
            QPushButton {
                background: #10b981;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #059669;
            }
        """)
        btn_layout.addWidget(majiang_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return widget
    
    def show_module(self, module_id: str):
        """显示指定模块"""
        # 确保模块存在
        if module_id not in self._panels:
            panel = self._create_module_content(module_id)
            self._panels[module_id] = panel
            self.content_stack.addWidget(panel)
        
        # 切换显示
        self.content_stack.setCurrentWidget(self._panels[module_id])
        self.module_changed.emit(module_id)
    
    def get_current_panel(self) -> QWidget:
        """获取当前面板"""
        return self.content_stack.currentWidget()
    
    def apply_style(self):
        """应用样式"""
        self.setStyleSheet("background: #f9fafb;")
    
    def _show_settings(self):
        """显示设置对话框"""
        dialog = ModuleSettingsDialog(self.module_manager, self)
        dialog.module_toggled.connect(self._on_module_toggled)
        dialog.exec()
    
    def _on_module_toggled(self, module_id: str, visible: bool):
        """模块可见性改变"""
        # 通知主窗口更新UI
        pass
    
    def get_config(self) -> dict:
        """获取配置"""
        return {
            "current_module": self.content_stack.currentWidget(),
            "panels": {
                module_id: panel.get_config() if hasattr(panel, 'get_config') else {}
                for module_id, panel in self._panels.items()
            }
        }


class ModuleSettingsDialog(QDialog):
    """
    模块设置对话框
    管理模块的显示/隐藏
    """
    
    module_toggled = pyqtSignal(str, bool)  # module_id, visible
    
    def __init__(self, module_manager, parent=None):
        super().__init__(parent)
        self.module_manager = module_manager
        
        self.setWindowTitle("模块设置")
        self.setMinimumWidth(400)
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # 说明
        info = QLabel("勾选要在首页显示的模块，隐藏的模块将不再有任务活动")
        info.setWordWrap(True)
        info.setStyleSheet("color: #6b7280; font-size: 13px;")
        layout.addWidget(info)
        
        # 模块列表
        group = QGroupBox("首页模块")
        group_layout = QVBoxLayout(group)
        
        self.checkboxes: dict[str, QCheckBox] = {}
        
        for mod in self.module_manager.get_all_modules():
            cb = QCheckBox(f"{mod.icon} {mod.name}")
            cb.setChecked(mod.visible)
            cb.setToolTip(mod.description)
            self.checkboxes[mod.module_id] = cb
            group_layout.addWidget(cb)
        
        layout.addWidget(group)
        
        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _on_save(self):
        """保存设置"""
        for module_id, cb in self.checkboxes.items():
            visible = cb.isChecked()
            if self.module_manager.is_visible(module_id) != visible:
                self.module_manager.set_visible(module_id, visible)
                self.module_toggled.emit(module_id, visible)
        
        self.accept()
