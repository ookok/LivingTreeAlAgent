"""
元宇宙UI面板 - Metaverse UI Panel
舰桥操作系统PyQt6集成面板
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget
from PyQt6.QtGui import QKeyEvent

from core.metaverse_ui import (
    BridgeConsole,
    TradeDeck,
    OracleCoreWidget,
    CommArrayWidget,
    NavigationSphere,
    get_sound_engine,
)


class MetaverseUIPanel(QWidget):
    """
    元宇宙UI面板
    提供全屏舰桥模式和独立面板模式
    """
    
    exit_requested = pyqtSignal()  # 退出请求
    navigation_requested = pyqtSignal(str)  # 导航请求
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signals()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 顶部栏 (退出按钮)
        header = QWidget()
        header.setFixedHeight(40)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 5, 10, 5)
        
        header_layout.addStretch()
        
        exit_btn = QPushButton("✕ 退出舰桥")
        exit_btn.setObjectName("HoloButtonDanger")
        exit_btn.clicked.connect(self._exit_bridge)
        header_layout.addWidget(exit_btn)
        
        layout.addWidget(header)
        
        # 主内容: 舰桥控制台
        self.bridge_console = BridgeConsole()
        self.bridge_console.navigate_requested.connect(self._on_navigate)
        self.bridge_console.settings_requested.connect(self._on_settings)
        self.bridge_console.escape_pressed.connect(self._exit_bridge)
        
        layout.addWidget(self.bridge_console, 1)
    
    def _connect_signals(self):
        """连接信号"""
        pass
    
    def _on_navigate(self, target: str):
        """导航"""
        self.navigation_requested.emit(target)
        
        # 播放音效
        get_sound_engine().play_sound("navigate")
    
    def _on_settings(self):
        """设置"""
        # 发送设置信号
        pass
    
    def _exit_bridge(self):
        """退出舰桥模式"""
        get_sound_engine().play_sound("disengage")
        self.exit_requested.emit()
    
    def keyPressEvent(self, event: QKeyEvent):
        """键盘事件"""
        if event.key() == Qt.Key.Key_Escape:
            self._exit_bridge()
        elif event.key() == Qt.Key.Key_F11:
            # 切换全屏
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        
        super().keyPressEvent(event)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # 公共API
    # ═══════════════════════════════════════════════════════════════════════════
    
    def enter_fullscreen(self):
        """进入全屏"""
        get_sound_engine().play_sound("engage")
        self.showFullScreen()
        self.bridge_console.enter_fullscreen()
    
    def set_node_id(self, node_id: str):
        """设置节点ID"""
        self.bridge_console.set_node_id(node_id)
    
    def set_pending_signals(self, count: int):
        """设置潜在交易信号"""
        self.bridge_console.set_pending_signals(count)
    
    def show_trade_notification(self, title: str, message: str):
        """显示交易通知"""
        self.bridge_console.show_trade_notification(title, message)


# ═══════════════════════════════════════════════════════════════════════════════
# 快速测试
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # 应用样式
    from core.metaverse_ui import get_bridge_stylesheet
    app.setStyleSheet(get_bridge_stylesheet())
    
    panel = MetaverseUIPanel()
    panel.resize(1200, 800)
    panel.show()
    
    sys.exit(app.exec())
