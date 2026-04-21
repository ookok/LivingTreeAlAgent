"""
舰桥指挥台主界面 - Bridge Console
元宇宙UI核心组件，整合全息星图、战术屏、系统面板、导航球
"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QPointF, QRectF
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QPushButton, QStackedWidget,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QSplitter, QSizePolicy, QSpacerItem, QScrollArea
)
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QLinearGradient, QFont, QTransform
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, pyqtProperty
import math
import random

from .bridge_styles import (
    HolographicColors, HolographicFonts, get_bridge_stylesheet,
    create_holo_card_style, HolographicPainter
)
from .holographic_star_map import HolographicStarMap
from .trade_deck import TradeDeck
from .oracle_core import OracleCore, OracleCoreWidget
from .comm_array import CommArray, CommArrayWidget
from .navigation_sphere import NavigationSphere
from .sound_engine import SoundEngine, get_sound_engine


# ═══════════════════════════════════════════════════════════════════════════════
# 舰桥指挥台组件
# ═══════════════════════════════════════════════════════════════════════════════

class BridgeConsole(QWidget):
    """
    舰桥指挥台 - 主界面
    
    布局:
    ┌─────────────────────────────────────────────────────────────┐
    │  [系统状态栏]  赫耳墨斯引擎在线 | 节点:8848 | 信号强度 ████░  │
    ├───────────────┬─────────────────────────┬─────────────────┤
    │               │                         │                 │
    │   战术全息屏   │      全息星图            │   系统面板       │
    │   (左屏)      │      (中央)             │   (右屏)        │
    │               │                         │                 │
    │  - 聊天       │   时空引力场可视化        │  - AI状态       │
    │  - 论坛       │   节点=星光              │  - 网络状态      │
    │  - 商品       │   交易意向=引力线        │  - 补丁系统      │
    │               │                         │  - 进化日志      │
    │               │                         │                 │
    ├───────────────┴─────────────────────────┴─────────────────┤
    │   [先知核心 AI助手]           [导航球]          [通讯阵]     │
    └─────────────────────────────────────────────────────────────┘
    """

    # 信号定义
    navigate_requested = pyqtSignal(str)  # 导航请求 (trade_deck/forum/mailbox/etc)
    ai_action_requested = pyqtSignal(str)  # AI操作请求
    settings_requested = pyqtSignal()  # 设置请求
    escape_pressed = pyqtSignal()  # ESC键退出舰桥模式

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 状态
        self._sound_engine = get_sound_engine()
        self._current_node = "node_8848"
        self._nodes_connected = []
        self._pending_signals = 3  # 潜在交易信号数
        
        # 初始化UI
        self._init_ui()
        self._init_animations()
        
        # 启动引导语
        QTimer.singleShot(500, self._play_welcome)
    
    def _init_ui(self):
        """初始化UI"""
        self.setStyleSheet(get_bridge_stylesheet())
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # ═══════════════════════════════════════════════════════════════
        # 1. 系统状态栏 (顶部)
        # ═══════════════════════════════════════════════════════════════
        self._create_status_bar(main_layout)
        
        # ═══════════════════════════════════════════════════════════════
        # 2. 中央区域 (三栏布局)
        # ═══════════════════════════════════════════════════════════════
        center_widget = QWidget()
        center_layout = QHBoxLayout(center_widget)
        center_layout.setContentsMargins(8, 8, 8, 8)
        center_layout.setSpacing(8)
        
        # 左屏: 战术全息屏
        self.tactical_panel = self._create_tactical_panel()
        center_layout.addWidget(self.tactical_panel, 1)
        
        # 中央: 全息星图
        self.star_map = HolographicStarMap()
        center_layout.addWidget(self.star_map, 2)
        
        # 右屏: 系统面板
        self.system_panel = self._create_system_panel()
        center_layout.addWidget(self.system_panel, 1)
        
        main_layout.addWidget(center_widget, 1)
        
        # ═══════════════════════════════════════════════════════════════
        # 3. 底部区域
        # ═══════════════════════════════════════════════════════════════
        self._create_bottom_bar(main_layout)
        
        # 启动引导动画
        self._animate_loading()
    
    def _create_status_bar(self, parent_layout):
        """创建顶部状态栏"""
        status_bar = QFrame()
        status_bar.setObjectName("BridgePanel")
        status_bar.setFixedHeight(50)
        status_bar_layout = QHBoxLayout(status_bar)
        status_bar_layout.setContentsMargins(16, 8, 16, 8)
        
        # 左侧: AI状态
        self.ai_status_label = QLabel("🤖 赫耳墨斯引擎")
        self.ai_status_label.setObjectName("HoloLabel")
        self.ai_status_label.setStyleSheet(f"color: {HolographicColors.HOLO_GREEN}; font-weight: bold;")
        status_bar_layout.addWidget(self.ai_status_label)
        
        status_bar_layout.addSpacing(20)
        
        # 节点ID
        self.node_label = QLabel(f"▸ 节点: {self._current_node}")
        self.node_label.setObjectName("HUDLabel")
        status_bar_layout.addWidget(self.node_label)
        
        status_bar_layout.addStretch()
        
        # 中央: 欢迎语
        self.welcome_label = QLabel("欢迎回来，指挥官")
        self.welcome_label.setObjectName("HoloLabelTitle")
        self.welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_bar_layout.addWidget(self.welcome_label, 1)
        
        status_bar_layout.addStretch()
        
        # 信号强度
        signal_layout = QHBoxLayout()
        signal_label = QLabel("📡 信号强度")
        signal_label.setObjectName("HoloLabelDim")
        signal_layout.addWidget(signal_label)
        
        self.signal_bars = QLabel("████░")
        self.signal_bars.setStyleSheet(f"color: {HolographicColors.HOLO_GREEN}; font-family: monospace;")
        signal_layout.addWidget(self.signal_bars)
        
        status_bar_layout.addLayout(signal_layout)
        
        status_bar_layout.addSpacing(20)
        
        # 时间
        self.time_label = QLabel("--:--:--")
        self.time_label.setObjectName("HUDLabel")
        self.time_label.setFont(HolographicFonts.mono_font(11))
        status_bar_layout.addWidget(self.time_label)
        
        # 定时更新时钟
        self._clock_timer = QTimer()
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()
        
        parent_layout.addWidget(status_bar)
    
    def _create_tactical_panel(self):
        """创建左屏战术面板"""
        panel = QFrame()
        panel.setObjectName("BridgePanel")
        panel.setMinimumWidth(200)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # 标题
        title = QLabel("◈ 战术全息屏")
        title.setObjectName("HoloLabelTitle")
        title.setStyleSheet(f"color: {HolographicColors.HOLO_PRIMARY};")
        layout.addWidget(title)
        
        # 分隔线
        divider = QFrame()
        divider.setObjectName("HDivider")
        divider.setFixedHeight(2)
        layout.addWidget(divider)
        
        # 功能按钮列表
        self.tactical_buttons = []
        
        buttons = [
            ("💬", "交易舱", "trade_deck"),
            ("🏛️", "通讯阵", "comm_array"),
            ("🔮", "先知核心", "oracle_core"),
            ("📊", "情报中心", "intelligence"),
            ("🛒", "商品市场", "market"),
        ]
        
        for icon, name, target in buttons:
            btn = QPushButton(f"{icon} {name}")
            btn.setObjectName("HoloButtonSecondary")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, t=target: self.navigate_requested.emit(t))
            layout.addWidget(btn)
            self.tactical_buttons.append(btn)
        
        layout.addStretch()
        
        # 快速操作
        quick_title = QLabel("◈ 快捷操作")
        quick_title.setObjectName("HoloLabel")
        quick_title.setStyleSheet(f"color: {HolographicColors.HOLO_SECONDARY};")
        layout.addWidget(quick_title)
        
        # 图片上传按钮 (物质重组器)
        self.upload_btn = QPushButton("📸 物质重组器")
        self.upload_btn.setObjectName("HoloButton")
        self.upload_btn.clicked.connect(self._on_upload_clicked)
        layout.addWidget(self.upload_btn)
        
        # 扫描按钮
        scan_btn = QPushButton("🔍 扫描引力场")
        scan_btn.setObjectName("HoloButtonSecondary")
        scan_btn.clicked.connect(self._on_scan_clicked)
        layout.addWidget(scan_btn)
        
        return panel
    
    def _create_system_panel(self):
        """创建右屏系统面板"""
        panel = QFrame()
        panel.setObjectName("BridgePanel")
        panel.setMinimumWidth(220)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # 标题
        title = QLabel("◈ 系统面板")
        title.setObjectName("HoloLabelTitle")
        title.setStyleSheet(f"color: {HolographicColors.HOLO_PRIMARY};")
        layout.addWidget(title)
        
        # 分隔线
        divider = QFrame()
        divider.setObjectName("HDivider")
        divider.setFixedHeight(2)
        layout.addWidget(divider)
        
        # AI状态区域
        ai_frame = QFrame()
        ai_frame.setObjectName("HoloCard")
        ai_layout = QVBoxLayout(ai_frame)
        ai_layout.setContentsMargins(8, 8, 8, 8)
        
        ai_header = QLabel("🤖 AI 领航员")
        ai_header.setStyleSheet(f"color: {HolographicColors.HOLO_PURPLE}; font-weight: bold;")
        ai_layout.addWidget(ai_header)
        
        self.ai_status_text = QLabel("状态: 在线")
        self.ai_status_text.setObjectName("HoloLabelDim")
        ai_layout.addWidget(self.ai_status_text)
        
        self.ai_suggestion = QLabel("\"检测到 3 个潜在交易信号\"")
        self.ai_suggestion.setStyleSheet(f"color: {HolographicColors.HOLO_GREEN}; font-style: italic;")
        ai_layout.addWidget(self.ai_suggestion)
        
        layout.addWidget(ai_frame)
        
        # 网络状态
        net_frame = QFrame()
        net_frame.setObjectName("HoloCard")
        net_layout = QVBoxLayout(net_frame)
        net_layout.setContentsMargins(8, 8, 8, 8)
        
        net_header = QLabel("🌐 网络状态")
        net_header.setStyleSheet(f"color: {HolographicColors.HOLO_SECONDARY}; font-weight: bold;")
        net_layout.addWidget(net_header)
        
        self.net_status = QLabel("• P2P链路: 5 个活跃节点")
        self.net_status.setObjectName("HoloLabelDim")
        net_layout.addWidget(self.net_status)
        
        self.net_latency = QLabel("• 平均延迟: 23ms")
        self.net_latency.setObjectName("HoloLabelDim")
        net_layout.addWidget(self.net_latency)
        
        layout.addWidget(net_frame)
        
        # 补丁系统
        patch_frame = QFrame()
        patch_frame.setObjectName("HoloCard")
        patch_layout = QVBoxLayout(patch_frame)
        patch_layout.setContentsMargins(8, 8, 8, 8)
        
        patch_header = QLabel("🔧 舰船改装台")
        patch_header.setStyleSheet(f"color: {HolographicColors.HOLO_ORANGE}; font-weight: bold;")
        patch_layout.addWidget(patch_header)
        
        self.patch_count = QLabel("已装载: 12 模块")
        self.patch_count.setObjectName("HoloLabelDim")
        patch_layout.addWidget(self.patch_count)
        
        self.patch_available = QLabel("待安装: 2 蓝图")
        self.patch_available.setStyleSheet(f"color: {HolographicColors.HOLO_ORANGE};")
        patch_layout.addWidget(self.patch_available)
        
        layout.addWidget(patch_frame)
        
        # 进化日志
        evolution_frame = QFrame()
        evolution_frame.setObjectName("HoloCard")
        evolution_layout = QVBoxLayout(evolution_frame)
        evolution_layout.setContentsMargins(8, 8, 8, 8)
        
        evo_header = QLabel("🧬 进化日志")
        evo_header.setStyleSheet(f"color: {HolographicColors.HOLO_GREEN}; font-weight: bold;")
        evolution_layout.addWidget(evo_header)
        
        self.evo_text = QLabel("神经树节点: 1,284")
        self.evo_text.setObjectName("HoloLabelDim")
        evolution_layout.addWidget(self.evo_text)
        
        self.evo_level = QLabel("理解深度: Lv.7")
        self.evo_level.setStyleSheet(f"color: {HolographicColors.HOLO_GREEN};")
        evolution_layout.addWidget(self.evo_level)
        
        layout.addWidget(evolution_frame)
        
        layout.addStretch()
        
        # 设置按钮
        settings_btn = QPushButton("⚙️ 系统设置")
        settings_btn.setObjectName("HoloButtonSecondary")
        settings_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(settings_btn)
        
        return panel
    
    def _create_bottom_bar(self, parent_layout):
        """创建底部区域"""
        bottom_bar = QFrame()
        bottom_bar.setObjectName("BridgePanel")
        bottom_bar.setFixedHeight(120)
        bottom_bar_layout = QHBoxLayout(bottom_bar)
        bottom_bar_layout.setContentsMargins(16, 8, 16, 8)
        
        # 先知核心 (AI助手)
        self.oracle_widget = OracleCoreWidget()
        self.oracle_widget.action_requested.connect(self._on_oracle_action)
        bottom_bar_layout.addWidget(self.oracle_widget, 2)
        
        # 导航球
        bottom_bar_layout.addSpacing(20)
        self.nav_sphere = NavigationSphere()
        self.nav_sphere.navigation_requested.connect(self._on_nav_request)
        bottom_bar_layout.addWidget(self.nav_sphere, 1)
        
        # 通讯阵
        bottom_bar_layout.addSpacing(20)
        self.comm_widget = CommArrayWidget()
        self.comm_widget.message_selected.connect(self._on_message_selected)
        bottom_bar_layout.addWidget(self.comm_widget, 2)
        
        parent_layout.addWidget(bottom_bar)
    
    def _init_animations(self):
        """初始化动画"""
        # 信号脉冲动画
        self._pulse_timer = QTimer()
        self._pulse_timer.timeout.connect(self._pulse_signal)
        self._pulse_timer.start(2000)
    
    def _update_clock(self):
        """更新时钟"""
        from datetime import datetime
        now = datetime.now()
        self.time_label.setText(now.strftime("%H:%M:%S"))
    
    def _animate_loading(self):
        """加载动画"""
        # 脉冲信号计数动画
        self._signal_count = 0
        self._signal_max = 3
        
        def update_signal():
            if self._signal_count < self._signal_max:
                self._signal_count += 1
                dots = "█" * self._signal_count + "░" * (self._signal_max - self._signal_count)
                self.signal_bars.setText(dots)
        
        self._loading_timer = QTimer()
        self._loading_timer.timeout.connect(update_signal)
        self._loading_timer.start(300)
        QTimer.singleShot(1000, self._loading_timer.stop)
    
    def _pulse_signal(self):
        """脉冲信号效果"""
        # 随机更新潜在交易信号数
        if random.random() > 0.7:
            self._pending_signals = max(1, self._pending_signals + random.randint(-1, 1))
            self.ai_suggestion.setText(f"\"检测到 {self._pending_signals} 个潜在交易信号\"")
    
    def _play_welcome(self):
        """播放欢迎语"""
        self._sound_engine.play_sound("boot")
        self._sound_engine.play_voice("欢迎回来指挥官时空引力场稳定")
    
    def _on_upload_clicked(self):
        """图片上传点击"""
        self._sound_engine.play_sound("scan")
        self.navigate_requested.emit("upload")
    
    def _on_scan_clicked(self):
        """扫描引力场"""
        self._sound_engine.play_sound("scan")
        self.star_map.refresh_nodes()
    
    def _on_nav_request(self, target: str):
        """导航请求"""
        self._sound_engine.play_sound("navigate")
        self.navigate_requested.emit(target)
    
    def _on_oracle_action(self, action: str):
        """先知核心操作"""
        self.ai_action_requested.emit(action)
    
    def _on_message_selected(self, msg_type: str):
        """消息选择"""
        self.navigate_requested.emit(f"mail_{msg_type}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # 公共API
    # ═══════════════════════════════════════════════════════════════════════════
    
    def set_node_id(self, node_id: str):
        """设置节点ID"""
        self._current_node = node_id
        self.node_label.setText(f"▸ 节点: {node_id}")
        self.star_map.set_node_id(node_id)
    
    def set_pending_signals(self, count: int):
        """设置潜在交易信号数"""
        self._pending_signals = count
        self.ai_suggestion.setText(f"\"检测到 {count} 个潜在交易信号\"")
    
    def update_network_status(self, nodes: int, latency: float):
        """更新网络状态"""
        self.net_status.setText(f"• P2P链路: {nodes} 个活跃节点")
        self.net_latency.setText(f"• 平均延迟: {latency:.0f}ms")
        
        if latency < 50:
            color = HolographicColors.HOLO_GREEN
        elif latency < 100:
            color = HolographicColors.HOLO_ORANGE
        else:
            color = HolographicColors.HOLO_RED
        self.net_latency.setStyleSheet(f"color: {color};")
    
    def update_patch_status(self, loaded: int, available: int):
        """更新补丁状态"""
        self.patch_count.setText(f"已装载: {loaded} 模块")
        self.patch_available.setText(f"待安装: {available} 蓝图")
    
    def show_trade_notification(self, title: str, message: str):
        """显示交易通知"""
        self._sound_engine.play_sound("alert")
        self.welcome_label.setText(f"📡 {title}")
        QTimer.singleShot(3000, lambda: self.welcome_label.setText("欢迎回来，指挥官"))
    
    def enter_fullscreen(self):
        """进入全屏模式"""
        self._sound_engine.play_sound("engage")
    
    def exit_fullscreen(self):
        """退出全屏模式"""
        self._sound_engine.play_sound("disengage")
        self.escape_pressed.emit()
    
    def keyPressEvent(self, event):
        """键盘事件"""
        if event.key() == Qt.Key.Key_Escape:
            self.exit_fullscreen()
        elif event.key() == Qt.Key.Key_F11:
            self.enter_fullscreen()


# ═══════════════════════════════════════════════════════════════════════════════
# 舰桥控制台管理器
# ═══════════════════════════════════════════════════════════════════════════════

_bridge_console_instance = None

def get_bridge_console() -> BridgeConsole:
    """获取舰桥控制台单例"""
    global _bridge_console_instance
    if _bridge_console_instance is None:
        _bridge_console_instance = BridgeConsole()
    return _bridge_console_instance


def create_bridge_console() -> BridgeConsole:
    """创建新的舰桥控制台"""
    global _bridge_console_instance
    _bridge_console_instance = BridgeConsole()
    return _bridge_console_instance
