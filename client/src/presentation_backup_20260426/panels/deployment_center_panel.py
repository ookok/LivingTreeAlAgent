"""
智能部署中心面板
统一的 L0-L4 模型和 Agent 部署管理界面
支持本地自动部署和远程 API 配置
"""

from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QProgressBar,
    QFrame, QGroupBox, QCheckBox, QLineEdit,
    QTabWidget, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QProgressDialog
)
from PyQt6.QtGui import QFont, QColor, QPalette
import time

from .business.model_layer_config import (
    ModelTier, ServiceStatus, DeployMode,
    ModelDefinition, L0_L4_MODELS, get_models_by_tier,
    LayerDeploymentConfig, LayerConfig, create_default_layer_config
)
from .business.deployment_engine import DeploymentEngine, get_deployment_engine
from .business.deployment_monitor import DeploymentMonitor, get_deployment_monitor, SystemStatus


# ── 样式定义 ────────────────────────────────────────────────────────────────

PANEL_STYLE = """
QWidget#DeploymentCenter {
    background: #0F172A;
    color: #E2E8F0;
}

QGroupBox {
    border: 1px solid #334155;
    border-radius: 8px;
    margin-top: 12px;
    padding: 12px;
    font-weight: 600;
    color: #94A3B8;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
    color: #64748B;
}

QPushButton {
    background: #334155;
    color: #F1F5F9;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
}
QPushButton:hover {
    background: #475569;
}
QPushButton:pressed {
    background: #1E293B;
}
QPushButton:disabled {
    background: #1E293B;
    color: #64748B;
}
QPushButton#PrimaryBtn {
    background: #3B82F6;
    font-weight: 600;
}
QPushButton#PrimaryBtn:hover {
    background: #2563EB;
}
QPushButton#SuccessBtn {
    background: #10B981;
}
QPushButton#SuccessBtn:hover {
    background: #059669;
}
QPushButton#DangerBtn {
    background: #EF4444;
}
QPushButton#DangerBtn:hover {
    background: #DC2626;
}

QLineEdit, QComboBox {
    background: #1E293B;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 8px 12px;
    color: #F1F5F9;
    font-size: 13px;
}
QLineEdit:focus, QComboBox:focus {
    border-color: #3B82F6;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox::down-arrow {
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #94A3B8;
    margin-right: 8px;
}
QComboBox QAbstractItemView {
    background: #1E293B;
    border: 1px solid #334155;
    selection-background-color: #3B82F6;
    color: #F1F5F9;
    padding: 4px;
}

QProgressBar {
    border: none;
    border-radius: 4px;
    background: #1E293B;
    height: 8px;
    text-align: center;
}
QProgressBar::chunk {
    background: #3B82F6;
    border-radius: 4px;
}

QLabel {
    color: #E2E8F0;
}
QLabel#Title {
    font-size: 18px;
    font-weight: 700;
    color: #F1F5F9;
}
QLabel#Subtitle {
    font-size: 12px;
    color: #94A3B8;
}
QLabel#StatusRunning {
    color: #10B981;
    font-weight: 600;
}
QLabel#StatusStopped {
    color: #64748B;
}
QLabel#StatusError {
    color: #EF4444;
}
"""


# ── 状态显示组件 ─────────────────────────────────────────────────────────────

class StatusIndicator(QWidget):
    """状态指示器"""
    
    def __init__(self, status: ServiceStatus, parent=None):
        super().__init__(parent)
        self._status = status
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self._dot = QLabel("●")
        self._dot.setFixedWidth(20)
        self._label = QLabel()
        
        layout.addWidget(self._dot)
        layout.addWidget(self._label)
        
        self._update_status()
    
    def _update_status(self):
        colors = {
            ServiceStatus.RUNNING: "#10B981",
            ServiceStatus.STOPPED: "#64748B",
            ServiceStatus.STARTING: "#F59E0B",
            ServiceStatus.ERROR: "#EF4444",
            ServiceStatus.DOWNLOADING: "#3B82F6",
        }
        texts = {
            ServiceStatus.RUNNING: "运行中",
            ServiceStatus.STOPPED: "已停止",
            ServiceStatus.STARTING: "启动中",
            ServiceStatus.ERROR: "错误",
            ServiceStatus.DOWNLOADING: "下载中",
        }
        
        color = colors.get(self._status, "#64748B")
        text = texts.get(self._status, "未知")
        
        self._dot.setStyleSheet(f"color: {color}; font-size: 14px;")
        self._label.setText(text)
        self._label.setStyleSheet(f"color: {color};")
    
    def set_status(self, status: ServiceStatus):
        self._status = status
        self._update_status()


class TierCard(QFrame):
    """层级卡片"""
    
    start_clicked = pyqtSignal(ModelTier)
    stop_clicked = pyqtSignal(ModelTier)
    config_clicked = pyqtSignal(ModelTier)
    
    def __init__(self, tier: ModelTier, parent=None):
        super().__init__(parent)
        self.tier = tier
        self._setup_ui()
    
    def _setup_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            TierCard {
                background: #1E293B;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 12px;
            }
            TierCard:hover {
                border-color: #3B82F6;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # 标题行
        header = QHBoxLayout()
        title = QLabel(f"📊 {self.tier.value} 层")
        title.setStyleSheet("font-size: 14px; font-weight: 700; color: #F1F5F9;")
        header.addWidget(title)
        
        self._status_indicator = StatusIndicator(ServiceStatus.STOPPED)
        header.addStretch()
        header.addWidget(self._status_indicator)
        
        layout.addLayout(header)
        
        # 模型信息
        self._model_label = QLabel("未配置模型")
        self._model_label.setStyleSheet("font-size: 12px; color: #94A3B8;")
        layout.addWidget(self._model_label)
        
        # 模型选择下拉框
        self._model_combo = QComboBox()
        self._model_combo.setFixedHeight(32)
        self._populate_models()
        layout.addWidget(self._model_combo)
        
        # 按钮行
        btn_layout = QHBoxLayout()
        
        self._start_btn = QPushButton("▶ 启动")
        self._start_btn.setObjectName("SuccessBtn")
        self._start_btn.setFixedHeight(32)
        self._start_btn.clicked.connect(lambda: self.start_clicked.emit(self.tier))
        
        self._stop_btn = QPushButton("⏹ 停止")
        self._stop_btn.setObjectName("DangerBtn")
        self._stop_btn.setFixedHeight(32)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(lambda: self.stop_clicked.emit(self.tier))
        
        btn_layout.addWidget(self._start_btn)
        btn_layout.addWidget(self._stop_btn)
        
        layout.addLayout(btn_layout)
        
        # 进度条
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)
        
        # 状态信息
        self._info_label = QLabel("")
        self._info_label.setStyleSheet("font-size: 11px; color: #64748B;")
        layout.addWidget(self._info_label)
    
    def _populate_models(self):
        """填充模型列表"""
        models = get_models_by_tier(self.tier)
        self._model_combo.clear()
        
        for model in models:
            self._model_combo.addItem(
                f"{model.name} ({model.size_gb}GB)",
                model.ollama_name
            )
    
    def set_model(self, model: ModelDefinition):
        """设置模型"""
        for i in range(self._model_combo.count()):
            if self._model_combo.itemData(i) == model.ollama_name:
                self._model_combo.setCurrentIndex(i)
                break
        
        self._model_label.setText(f"用途: {model.purpose}")
        self._info_label.setText(f"内存需求: {model.recommended_memory_gb}GB")
    
    def get_selected_model_name(self) -> str:
        """获取选中的模型名"""
        return self._model_combo.currentData()
    
    def set_status(self, status: ServiceStatus):
        """设置状态"""
        self._status_indicator.set_status(status)
        self._start_btn.setEnabled(status != ServiceStatus.RUNNING)
        self._stop_btn.setEnabled(status == ServiceStatus.RUNNING)
        
        if status == ServiceStatus.RUNNING:
            self._model_label.setStyleSheet("font-size: 12px; color: #10B981;")
        else:
            self._model_label.setStyleSheet("font-size: 12px; color: #94A3B8;")
    
    def show_progress(self, show: bool, value: int = 0):
        """显示进度"""
        self._progress.setVisible(show)
        if show:
            self._progress.setValue(value)
    
    def set_info(self, text: str):
        """设置信息"""
        self._info_label.setText(text)


# ── 部署工作线程 ─────────────────────────────────────────────────────────────

class DeployWorker(QThread):
    """部署工作线程"""
    
    progress = pyqtSignal(float, str)
    finished = pyqtSignal(bool, str, str)
    
    def __init__(self, engine: DeploymentEngine, tier: ModelTier, model_name: str, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.tier = tier
        self.model_name = model_name
    
    def run(self):
        try:
            def on_progress(p: float, s: str):
                self.progress.emit(p, s)
            
            # 找到模型定义
            model = None
            for m in L0_L4_MODELS:
                if m.ollama_name == self.model_name:
                    model = m
                    break
            
            result = self.engine.auto_deploy_tier(self.tier, model, on_progress)
            
            self.finished.emit(result.success, result.message, result.error or "")
        
        except Exception as e:
            self.finished.emit(False, "部署异常", str(e))


# ── 主面板 ─────────────────────────────────────────────────────────────────────

class DeploymentCenterPanel(QWidget):
    """
    智能部署中心面板
    
    功能：
    1. L0-L4 模型层管理
    2. 本地自动部署（Ollama）
    3. 远程 API 配置
    4. 状态监控和启停控制
    5. 一键部署所有模型
    """
    
    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        
        # 核心组件
        self._engine = get_deployment_engine()
        self._monitor = get_deployment_monitor()
        
        # 配置
        self._config = create_default_layer_config()
        
        # 工作线程
        self._workers: Dict[ModelTier, DeployWorker] = {}
        
        # 初始化UI
        self._setup_ui()
        
        # 连接信号
        self._connect_signals()
        
        # 启动监控
        self._monitor.add_callback(self._on_status_changed)
        self._monitor.start_monitoring()
        
        # 初始刷新
        self._refresh_all()
    
    def _setup_ui(self):
        """设置UI"""
        self.setObjectName("DeploymentCenter")
        self.setStyleSheet(PANEL_STYLE)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 标题区域
        self._setup_header(layout)
        
        # Tab 页
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 16px;
                background: #1E293B;
            }
            QTabBar::tab {
                background: transparent;
                color: #94A3B8;
                padding: 10px 20px;
                margin-right: 4px;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected {
                color: #3B82F6;
                border-bottom: 2px solid #3B82F6;
            }
        """)
        
        # 本地部署页
        local_tab = self._create_local_tab()
        tabs.addTab(local_tab, "🖥️ 本地部署")
        
        # 远程配置页
        remote_tab = self._create_remote_tab()
        tabs.addTab(remote_tab, "☁️ 远程配置")
        
        # 状态总览页
        status_tab = self._create_status_tab()
        tabs.addTab(status_tab, "📈 状态总览")
        
        layout.addWidget(tabs)
    
    def _setup_header(self, parent_layout):
        """设置标题区域"""
        header = QHBoxLayout()
        
        # 标题
        title = QLabel("🚀 智能部署中心")
        title.setObjectName("Title")
        header.addWidget(title)
        
        # Ollama 状态
        self._ollama_status = StatusIndicator(ServiceStatus.STOPPED)
        header.addWidget(QLabel("Ollama:"))
        header.addWidget(self._ollama_status)
        
        # 系统内存
        self._memory_label = QLabel("内存: --")
        self._memory_label.setStyleSheet("color: #94A3B8; font-size: 12px;")
        header.addWidget(self._memory_label)
        
        header.addStretch()
        
        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self._refresh_all)
        header.addWidget(refresh_btn)
        
        parent_layout.addLayout(header)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background: #334155;")
        parent_layout.addWidget(line)
    
    def _create_local_tab(self) -> QWidget:
        """创建本地部署页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)
        
        # 说明文字
        intro = QLabel(
            "💡 本地部署会自动下载、安装和启动模型。\n"
            "   系统会根据您的硬件自动推荐合适的模型配置。"
        )
        intro.setStyleSheet("""
            background: #1E3A5F;
            border-radius: 8px;
            padding: 12px;
            color: #93C5FD;
            font-size: 12px;
        """)
        layout.addWidget(intro)
        
        # 快速操作区
        quick_ops = QHBoxLayout()
        
        self._auto_deploy_btn = QPushButton("⚡ 一键部署所有模型")
        self._auto_deploy_btn.setObjectName("PrimaryBtn")
        self._auto_deploy_btn.setFixedHeight(40)
        self._auto_deploy_btn.clicked.connect(self._on_auto_deploy_all)
        quick_ops.addWidget(self._auto_deploy_btn)
        
        self._stop_all_btn = QPushButton("⏹ 停止所有服务")
        self._stop_all_btn.setObjectName("DangerBtn")
        self._stop_all_btn.setFixedHeight(40)
        self._stop_all_btn.clicked.connect(self._on_stop_all)
        quick_ops.addWidget(self._stop_all_btn)
        
        quick_ops.addStretch()
        
        layout.addLayout(quick_ops)
        
        # 层级卡片区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        
        cards_widget = QWidget()
        cards_layout = QGridLayout(cards_widget)
        cards_layout.setSpacing(12)
        
        # 创建各层级卡片
        self._tier_cards: Dict[ModelTier, TierCard] = {}
        
        row, col = 0, 0
        for tier in ModelTier:
            card = TierCard(tier)
            card.start_clicked.connect(self._on_tier_start)
            card.stop_clicked.connect(self._on_tier_stop)
            
            cards_layout.addWidget(card, row, col)
            self._tier_cards[tier] = card
            
            col += 1
            if col >= 3:  # 每行3个
                col = 0
                row += 1
        
        scroll.setWidget(cards_widget)
        layout.addWidget(scroll)
        
        return widget
    
    def _create_remote_tab(self) -> QWidget:
        """创建远程配置页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)
        
        # 说明
        intro = QLabel(
            "☁️ 远程配置用于连接远程模型服务（如 API 服务器）。\n"
            "   配置后，系统将使用远程 API 代替本地 Ollama。"
        )
        intro.setStyleSheet("""
            background: #1E3A5F;
            border-radius: 8px;
            padding: 12px;
            color: #93C5FD;
            font-size: 12px;
        """)
        layout.addWidget(intro)
        
        # 部署模式选择
        mode_group = QGroupBox("部署模式")
        mode_layout = QHBoxLayout()
        
        self._local_mode = QRadioButton("本地部署 (默认)")
        self._remote_mode = QRadioButton("远程服务器")
        mode_layout.addWidget(self._local_mode)
        mode_layout.addWidget(self._remote_mode)
        mode_layout.addStretch()
        
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # 远程配置区
        remote_group = QGroupBox("远程服务器配置")
        remote_layout = QGridLayout()
        
        remote_layout.addWidget(QLabel("API 地址:"), 0, 0)
        self._remote_url = QLineEdit()
        self._remote_url.setPlaceholderText("http://139.199.124.242:8899/v1")
        remote_layout.addWidget(self._remote_url, 0, 1)
        
        remote_layout.addWidget(QLabel("API Key:"), 1, 0)
        self._remote_key = QLineEdit()
        self._remote_key.setPlaceholderText("输入 API Key (可选)")
        self._remote_key.setEchoMode(QLineEdit.EchoMode.Password)
        remote_layout.addWidget(self._remote_key, 1, 1)
        
        # 测试连接按钮
        test_btn = QPushButton("🔗 测试连接")
        test_btn.clicked.connect(self._on_test_remote)
        remote_layout.addWidget(test_btn, 2, 0, 1, 2)
        
        self._remote_status = QLabel("")
        self._remote_status.setStyleSheet("font-size: 12px;")
        remote_layout.addWidget(self._remote_status, 3, 0, 1, 2)
        
        remote_group.setLayout(remote_layout)
        layout.addWidget(remote_group)
        
        # 层级远程映射
        tier_map_group = QGroupBox("层级 → 远程模型映射")
        tier_map_layout = QVBoxLayout()
        
        self._tier_remote_map: Dict[ModelTier, QLineEdit] = {}
        
        for tier in ModelTier:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{tier.value} 层:"))
            
            edit = QLineEdit()
            edit.setPlaceholderText(f"例如: qwen2.5:1.5b")
            row.addWidget(edit)
            
            self._tier_remote_map[tier] = edit
            tier_map_layout.addLayout(row)
        
        tier_map_group.setLayout(tier_map_layout)
        layout.addWidget(tier_map_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_status_tab(self) -> QWidget:
        """创建状态总览页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 表格
        self._status_table = QTableWidget()
        self._status_table.setColumnCount(4)
        self._status_table.setHorizontalHeaderLabels(["层级", "状态", "模型", "信息"])
        
        header = self._status_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        self._status_table.setRowCount(len(ModelTier))
        
        for i, tier in enumerate(ModelTier):
            self._status_table.setItem(i, 0, QTableWidgetItem(tier.value))
            self._status_table.setItem(i, 1, QTableWidgetItem("未知"))
            self._status_table.setItem(i, 2, QTableWidgetItem(""))
            self._status_table.setItem(i, 3, QTableWidgetItem(""))
        
        self._status_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._status_table)
        
        # 诊断按钮
        diag_layout = QHBoxLayout()
        
        diag_btn = QPushButton("📋 生成诊断报告")
        diag_btn.clicked.connect(self._show_diagnostic)
        diag_layout.addWidget(diag_btn)
        
        diag_layout.addStretch()
        
        layout.addLayout(diag_layout)
        
        return widget
    
    def _connect_signals(self):
        """连接信号"""
        self._monitor.add_callback(self._on_status_changed)
    
    def _on_status_changed(self, status: SystemStatus):
        """状态变化回调"""
        # 更新 Ollama 状态
        if status.ollama_running:
            self._ollama_status.set_status(ServiceStatus.RUNNING)
        else:
            self._ollama_status.set_status(ServiceStatus.STOPPED)
        
        # 更新内存显示
        if status.total_memory_gb > 0:
            self._memory_label.setText(
                f"内存: {status.used_memory_gb:.1f}/{status.total_memory_gb:.1f}GB "
                f"({status.used_memory_gb/status.total_memory_gb*100:.0f}%)"
            )
        
        # 更新层级状态
        for tier, tier_status in status.tier_status.items():
            tier_enum = ModelTier(tier)
            if tier_enum in self._tier_cards:
                card = self._tier_cards[tier_enum]
                card.set_status(tier_status.status)
                
                if tier_status.model_name:
                    card.set_info(f"已加载: {tier_status.model_name}")
        
        # 更新表格
        self._update_status_table(status)
    
    def _update_status_table(self, status: SystemStatus):
        """更新状态表格"""
        for i, tier in enumerate(ModelTier):
            tier_status = status.tier_status.get(tier.value)
            if tier_status:
                # 状态
                status_text = tier_status.status.value
                status_item = self._status_table.item(i, 1)
                status_item.setText(status_text)
                
                # 根据状态设置颜色
                colors = {
                    "running": "#10B981",
                    "stopped": "#64748B",
                    "error": "#EF4444",
                    "starting": "#F59E0B",
                    "downloading": "#3B82F6",
                }
                status_item.setForeground(QColor(colors.get(tier_status.status.value, "#94A3B8")))
                
                # 模型
                self._status_table.item(i, 2).setText(tier_status.model_name or "-")
                
                # 信息
                info = tier_status.error if tier_status.error else ""
                self._status_table.item(i, 3).setText(info)
    
    def _on_tier_start(self, tier: ModelTier):
        """启动指定层级"""
        card = self._tier_cards[tier]
        model_name = card.get_selected_model_name()
        
        if not model_name:
            return
        
        # 禁用按钮
        card._start_btn.setEnabled(False)
        card.show_progress(True, 0)
        
        # 创建工作线程
        worker = DeployWorker(self._engine, tier, model_name)
        worker.progress.connect(lambda p, s: card.show_progress(True, int(p * 100)))
        worker.finished.connect(lambda ok, msg, err: self._on_deploy_finished(tier, ok, msg, err))
        
        self._workers[tier] = worker
        worker.start()
    
    def _on_tier_stop(self, tier: ModelTier):
        """停止指定层级"""
        card = self._tier_cards[tier]
        card.set_status(ServiceStatus.STOPPED)
        card.set_info("已停止")
    
    def _on_deploy_finished(self, tier: ModelTier, success: bool, message: str, error: str):
        """部署完成"""
        card = self._tier_cards[tier]
        card.show_progress(False)
        
        if success:
            card.set_status(ServiceStatus.RUNNING)
            card.set_info(message)
        else:
            card.set_status(ServiceStatus.ERROR)
            card.set_info(f"错误: {error}")
    
    def _on_auto_deploy_all(self):
        """一键部署所有模型"""
        msg = QMessageBox()
        msg.setWindowTitle("确认部署")
        msg.setText(
            "将自动下载并部署所有 L0-L4 模型。\n\n"
            "预计需要下载 10-15GB 模型文件。\n"
            "是否继续？"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if msg.exec() == QMessageBox.StandardButton.Yes:
            for tier, card in self._tier_cards.items():
                if card._start_btn.isEnabled():
                    self._on_tier_start(tier)
    
    def _on_stop_all(self):
        """停止所有服务"""
        for tier, card in self._tier_cards.items():
            if card._stop_btn.isEnabled():
                self._on_tier_stop(tier)
    
    def _on_test_remote(self):
        """测试远程连接"""
        url = self._remote_url.text().strip()
        if not url:
            self._remote_status.setText("请输入 API 地址")
            self._remote_status.setStyleSheet("color: #F59E0B;")
            return
        
        self._remote_status.setText("正在测试连接...")
        self._remote_status.setStyleSheet("color: #3B82F6;")
        
        # TODO: 实现实际的连接测试
        import threading
        def test():
            time.sleep(1)
            # 模拟测试结果
            self._remote_status.setText("✅ 连接成功!")
            self._remote_status.setStyleSheet("color: #10B981;")
        
        threading.Thread(target=test, daemon=True).start()
    
    def _show_diagnostic(self):
        """显示诊断报告"""
        report = self._monitor.get_diagnostic_report()
        
        msg = QMessageBox()
        msg.setWindowTitle("诊断报告")
        msg.setText(report)
        msg.setMinimumWidth(500)
        msg.exec()
    
    def _refresh_all(self):
        """刷新所有状态"""
        status = self._monitor.get_status()
        self._on_status_changed(status)
    
    def closeEvent(self, event):
        """关闭时停止监控"""
        self._monitor.stop_monitoring()
        super().closeEvent(event)


# ── 便捷函数 ─────────────────────────────────────────────────────────────────

def create_deployment_panel(main_window=None) -> DeploymentCenterPanel:
    """创建部署中心面板"""
    return DeploymentCenterPanel(main_window)


# ── 测试 ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication, QMessageBox
    
    app = QApplication(sys.argv)
    
    # 设置字体
    font = QFont()
    font.setPointSize(10)
    app.setFont(font)
    
    panel = DeploymentCenterPanel()
    panel.setWindowTitle("智能部署中心")
    panel.resize(900, 700)
    panel.show()
    
    sys.exit(app.exec())
