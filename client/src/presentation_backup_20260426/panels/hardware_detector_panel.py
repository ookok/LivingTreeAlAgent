"""
AI算力仪表盘面板 (Hardware Detector Panel)
==========================================

集成 ai-detector 前端工具，提供本地硬件检测与AI模型匹配功能。

功能特性:
- CPU/RAM/GPU 自动检测
- 21+ 主流AI模型兼容性评估
- tokens/sec 性能预估
- 结果通过 PyQt WebChannel 传回 Python

依赖:
    PyQt6.QtWebEngineWidgets (可选, 无GPU时降级)
    PyQt6.QtCore
    PyQt6.QtWidgets

作者: Hermes Desktop Team
"""

import json
import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Callable

from PyQt6.QtCore import (
    QObject, pyqtSignal, pyqtSlot, QUrl, QSize, Qt,
    QTimer, QThread
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTextEdit, QGroupBox, QScrollArea,
    QProgressBar, QComboBox, QCheckBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QSpacerItem, QSizePolicy, QSpinBox
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile, QWebEnginePage,
    QWebChannel
)

# =============================================================================
# 数据模型
# =============================================================================

class HardwareProfile:
    """硬件配置画像"""

    def __init__(
        self,
        cpu_cores: int = 0,
        cpu_threads: int = 0,
        cpu_model: str = "Unknown",
        cpu_arch: str = "Unknown",
        ram_total_gb: float = 0.0,
        ram_available_gb: float = 0.0,
        ram_type: str = "Unknown",
        gpu_renderer: str = "Unknown",
        gpu_vram_gb: float = 0.0,
        gpu_vendor: str = "Unknown",
        has_webgl: bool = False,
        has_gpu: bool = False,
        timestamp: Optional[str] = None
    ):
        self.cpu_cores = cpu_cores
        self.cpu_threads = cpu_threads
        self.cpu_model = cpu_model
        self.cpu_arch = cpu_arch
        self.ram_total_gb = ram_total_gb
        self.ram_available_gb = ram_available_gb
        self.ram_type = ram_type
        self.gpu_renderer = gpu_renderer
        self.gpu_vram_gb = gpu_vram_gb
        self.gpu_vendor = gpu_vendor
        self.has_webgl = has_webgl
        self.has_gpu = has_gpu
        self.timestamp = timestamp or datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu_cores": self.cpu_cores,
            "cpu_threads": self.cpu_threads,
            "cpu_model": self.cpu_model,
            "cpu_arch": self.cpu_arch,
            "ram_total_gb": self.ram_total_gb,
            "ram_available_gb": self.ram_available_gb,
            "ram_type": self.ram_type,
            "gpu_renderer": self.gpu_renderer,
            "gpu_vram_gb": self.gpu_vram_gb,
            "gpu_vendor": self.gpu_vendor,
            "has_webgl": self.has_webgl,
            "has_gpu": self.has_gpu,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HardwareProfile":
        return cls(**{k: v for k, v in data.items() if k in cls.__init__.__code__.co_varnames})

    def get_hash(self) -> str:
        """生成硬件配置哈希指纹"""
        key_data = f"{self.cpu_model}:{self.ram_total_gb}:{self.gpu_renderer}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]

    def can_run_model(self, model_name: str, vram_required: float) -> bool:
        """检查是否能运行指定模型"""
        if vram_required <= 0:
            return True  # API模型

        if not self.has_gpu:
            # CPU模式,仅支持小模型
            return vram_required <= 6 and self.ram_total_gb >= 8

        return self.gpu_vram_gb >= vram_required and self.ram_total_gb >= 8

    def estimate_speed(self, model_name: str, vram_required: float) -> int:
        """估算运行速度 (tokens/sec)"""
        if vram_required <= 0:
            return 999  # API无限速

        if not self.has_gpu:
            if vram_required <= 6:
                return self.cpu_cores * 2
            elif vram_required <= 13:
                return self.cpu_cores
            return 1

        if self.gpu_vram_gb < vram_required:
            return 2

        # GPU加速估算
        if vram_required <= 6:
            return 40 + int((self.gpu_vram_gb - vram_required) * 5)
        elif vram_required <= 12:
            return 30 + int((self.gpu_vram_gb - vram_required) * 3)
        elif vram_required <= 24:
            return 20 + int((self.gpu_vram_gb - vram_required) * 2)
        return 10


class AIDetectionResult:
    """AI检测结果"""

    def __init__(
        self,
        status: str,
        hardware: HardwareProfile,
        recommended_models: List[Dict[str, Any]],
        timestamp: Optional[str] = None
    ):
        self.status = status
        self.hardware = hardware
        self.recommended_models = recommended_models
        self.timestamp = timestamp or datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "hardware": self.hardware.to_dict(),
            "recommended_models": self.recommended_models,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIDetectionResult":
        return cls(
            status=data["status"],
            hardware=HardwareProfile.from_dict(data["hardware"]),
            recommended_models=data.get("recommended_models", []),
            timestamp=data.get("timestamp")
        )

    def get_best_model(self) -> Optional[Dict[str, Any]]:
        """获取最佳推荐模型"""
        for model in self.recommended_models:
            if model.get("recommended"):
                return model
        if self.recommended_models:
            return self.recommended_models[0]
        return None

    def generate_capability_report(self) -> str:
        """生成能力报告(用于商品发布)"""
        best = self.get_best_model()
        hw = self.hardware

        report = f"""硬件认证报告
CPU: {hw.cpu_model} ({hw.cpu_cores}核/{hw.cpu_threads}线程)
内存: {hw.ram_total_gb}GB {hw.ram_type}
GPU: {hw.gpu_renderer}
VRAM: {hw.gpu_vram_gb}GB
推荐模型: {best['modelName'] if best else 'N/A'}
预估速度: {best['speedEstimate'] if best else 'N/A'} tok/s
VRAM需求: {best.get('vramRequired', 0)}GB
"""
        return report


# =============================================================================
# JS-Python 通信桥接
# =============================================================================

class JSBridge(QObject):
    """JavaScript 与 Python 之间的通信桥接"""

    # 信号定义
    detection_started = pyqtSignal()
    detection_completed = pyqtSignal(dict)
    detection_error = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._pending_callbacks: Dict[str, Callable] = {}

    @pyqtSlot(str, result="QString")
    def postResult(self, json_str: str) -> str:
        """接收来自JavaScript的检测结果"""
        try:
            data = json.loads(json_str)
            self.detection_completed.emit(data)
            return json.dumps({"success": True})
        except Exception as e:
            self.detection_error.emit(str(e))
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(result="QString")
    def getStatus(self) -> str:
        """获取当前状态"""
        return json.dumps({"ready": True, "version": "1.0.0"})

    def inject_detection_script(self) -> str:
        """生成注入到WebView的JavaScript代码"""
        return """
(function() {
    const originalComplete = window.aiDetectorComplete;
    window.aiDetectorComplete = function(data) {
        if (originalComplete) originalComplete(data);
        if (window.pybridge) {
            window.pybridge.postResult(JSON.stringify(data));
        }
    };
    window.getDetectionResult = function() {
        return window.aiDetectorResult || null;
    };
    console.log('JS Bridge initialized');
})();
"""


# =============================================================================
# PyQt6 WebEnginePage (带WebChannel支持)
# =============================================================================

class WebEnginePage(QWebEnginePage):
    """自定义WebEnginePage,支持WebChannel通信"""

    def __init__(self, profile: Optional[QWebEngineProfile] = None, parent: Optional[QObject] = None):
        super().__init__(profile, parent)
        self.js_bridge: Optional[JSBridge] = None
        self.channel: Optional[QWebChannel] = None

    def setJsBridge(self, bridge: JSBridge) -> None:
        """设置JS桥接对象"""
        self.js_bridge = bridge
        self.channel = QWebChannel(self)
        self.channel.registerObject("pybridge", bridge)
        self.setWebChannel(self.channel)


# =============================================================================
# 主面板组件
# =============================================================================

class HardwareDetectorPanel(QWidget):
    """
    AI算力仪表盘面板

    功能:
    - 内嵌 ai-detector HTML 界面
    - 自动/手动触发硬件检测
    - 结果展示与导出
    - 与 DeCommerce 商品系统集成
    """

    # 信号定义
    detection_done = pyqtSignal(dict)  # 检测完成时发出
    capability_changed = pyqtSignal(dict)  # 能力画像更新时发出

    def __init__(
        self,
        static_path: Optional[str] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)

        # 确定静态资源路径
        if static_path is None:
            self._static_path = Path(__file__).parent.parent / "static" / "ai-detector"
        else:
            self._static_path = Path(static_path)

        self._html_path = self._static_path / "index.html"

        # 状态
        self._current_profile: Optional[HardwareProfile] = None
        self._current_result: Optional[AIDetectionResult] = None
        self._is_webengine_available: bool = True

        # 初始化UI
        self._init_ui()

        # 初始化WebEngine
        self._init_webengine()

        # 加载检测器页面
        self._load_detector()

    def _init_ui(self) -> None:
        """初始化UI组件"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 标签页: 图形界面 / 数据视图 / 集成视图
        self._tabs = QTabWidget()
        self._tabs.addTab(self._create_graphic_tab(), "图形界面")
        self._tabs.addTab(self._create_data_tab(), "数据视图")
        self._tabs.addTab(self._create_integration_tab(), "集成视图")

        main_layout.addWidget(self._tabs)

    def _create_graphic_tab(self) -> QWidget:
        """创建图形界面Tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # WebEngineView 容器
        self._web_container = QFrame()
        self._web_container.setFrameStyle(QFrame.Shape.NoFrame)
        web_layout = QVBoxLayout(self._web_container)
        web_layout.setContentsMargins(0, 0, 0, 0)

        # 创建WebView
        self._webview = QWebEngineView()
        self._webview.setMinimumHeight(600)

        # 设置页面
        self._page = WebEnginePage()
        self._webview.setPage(self._page)

        # 创建JS桥接
        self._js_bridge = JSBridge(self)
        self._page.setJsBridge(self._js_bridge)
        self._js_bridge.detection_completed.connect(self._on_detection_completed)
        self._js_bridge.detection_error.connect(self._on_detection_error)

        web_layout.addWidget(self._webview)

        # 备用控件(WebEngine不可用时显示)
        self._fallback_widget = QLabel(
            "WebEngine 不可用，请使用「数据视图」手动输入硬件信息"
        )
        self._fallback_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._fallback_widget.setStyleSheet("padding: 40px; color: #f59e0b;")
        self._fallback_widget.hide()

        layout.addWidget(self._web_container, 1)

        return tab

    def _create_data_tab(self) -> QWidget:
        """创建数据视图Tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 说明标签
        info_label = QLabel(
            "手动输入硬件配置(当WebEngine不可用时使用)"
        )
        info_label.setStyleSheet("padding: 10px; color: #94a3b8;")
        layout.addWidget(info_label)

        # 硬件配置表单
        form_group = QGroupBox("硬件配置")
        form_layout = QVBoxLayout(form_group)

        # CPU配置
        cpu_layout = QHBoxLayout()
        cpu_layout.addWidget(QLabel("CPU型号:"))
        self._cpu_model_input = QTextEdit()
        self._cpu_model_input.setMaximumHeight(30)
        self._cpu_model_input.setPlaceholderText("例如: Intel Core i7-12700K")
        cpu_layout.addWidget(self._cpu_model_input, 1)
        form_layout.addLayout(cpu_layout)

        cpu_cores_layout = QHBoxLayout()
        cpu_cores_layout.addWidget(QLabel("核心数:"))
        self._cpu_cores_input = QSpinBox()
        self._cpu_cores_input.setRange(1, 128)
        self._cpu_cores_input.setValue(8)
        cpu_cores_layout.addWidget(self._cpu_cores_input)
        cpu_cores_layout.addWidget(QLabel("  线程数:"))
        self._cpu_threads_input = QSpinBox()
        self._cpu_threads_input.setRange(1, 256)
        self._cpu_threads_input.setValue(16)
        cpu_cores_layout.addWidget(self._cpu_threads_input)
        cpu_cores_layout.addStretch()
        form_layout.addLayout(cpu_cores_layout)

        # RAM配置
        ram_layout = QHBoxLayout()
        ram_layout.addWidget(QLabel("内存(GB):"))
        self._ram_total_input = QSpinBox()
        self._ram_total_input.setRange(1, 1024)
        self._ram_total_input.setValue(32)
        ram_layout.addWidget(self._ram_total_input)
        ram_layout.addWidget(QLabel("  类型:"))
        self._ram_type_input = QComboBox()
        self._ram_type_input.addItems(["DDR3", "DDR4", "DDR5", "LPDDR4", "LPDDR5", "Unknown"])
        ram_layout.addWidget(self._ram_type_input)
        ram_layout.addStretch()
        form_layout.addLayout(ram_layout)

        # GPU配置
        gpu_layout = QHBoxLayout()
        gpu_layout.addWidget(QLabel("GPU型号:"))
        self._gpu_model_input = QTextEdit()
        self._gpu_model_input.setMaximumHeight(30)
        self._gpu_model_input.setPlaceholderText("例如: NVIDIA GeForce RTX 3080")
        gpu_layout.addWidget(self._gpu_model_input, 1)
        form_layout.addLayout(gpu_layout)

        gpu_vram_layout = QHBoxLayout()
        gpu_vram_layout.addWidget(QLabel("VRAM(GB):"))
        self._gpu_vram_input = QSpinBox()
        self._gpu_vram_input.setRange(0, 128)
        self._gpu_vram_input.setValue(10)
        gpu_vram_layout.addWidget(self._gpu_vram_input)
        gpu_vram_layout.addWidget(QLabel("  有独立GPU:"))
        self._has_gpu_checkbox = QCheckBox()
        self._has_gpu_checkbox.setChecked(True)
        gpu_vram_layout.addWidget(self._has_gpu_checkbox)
        gpu_vram_layout.addStretch()
        form_layout.addLayout(gpu_vram_layout)

        layout.addWidget(form_group)

        # 模型匹配预览
        model_group = QGroupBox("模型匹配预览")
        model_layout = QVBoxLayout(model_group)

        self._model_preview_table = QTableWidget()
        self._model_preview_table.setColumnCount(5)
        self._model_preview_table.setHorizontalHeaderLabels([
            "模型", "参数", "VRAM需求", "兼容性", "预估速度"
        ])
        self._model_preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        model_layout.addWidget(self._model_preview_table)

        layout.addWidget(model_group, 1)

        # 操作按钮
        btn_layout = QHBoxLayout()
        self._save_profile_btn = QPushButton("保存配置")
        self._save_profile_btn.clicked.connect(self._save_profile)
        btn_layout.addWidget(self._save_profile_btn)

        self._export_report_btn = QPushButton("导出报告")
        self._export_report_btn.clicked.connect(self._export_report)
        btn_layout.addWidget(self._export_report_btn)

        self._match_models_btn = QPushButton("重新匹配模型")
        self._match_models_btn.clicked.connect(self._update_model_preview)
        btn_layout.addWidget(self._match_models_btn)

        layout.addLayout(btn_layout)

        return tab

    def _create_integration_tab(self) -> QWidget:
        """创建集成视图Tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 集成说明
        info = QLabel(
            "本地AI算力与DeCommerce去中心化电商系统集成\n"
            "- 卖家发布AI服务时自动附带硬件认证报告\n"
            "- 买家可自查本地算力决定是否购买服务\n"
            "- P2P网络中发现高性能节点"
        )
        info.setStyleSheet("padding: 15px; background: #1e293b; border-radius: 8px;")
        layout.addWidget(info)

        # 能力报告展示
        report_group = QGroupBox("当前能力报告")
        report_layout = QVBoxLayout(report_group)

        self._report_text = QTextEdit()
        self._report_text.setReadOnly(True)
        self._report_text.setMaximumHeight(200)
        self._report_text.setPlaceholderText("运行检测后,报告将显示在这里...")
        report_layout.addWidget(self._report_text)

        layout.addWidget(report_group)

        # DeCommerce集成状态
        deco_group = QGroupBox("DeCommerce 集成状态")
        deco_layout = QVBoxLayout(deco_group)

        self._deco_status = QTableWidget()
        self._deco_status.setColumnCount(3)
        self._deco_status.setHorizontalHeaderLabels(["功能", "状态", "操作"])
        self._deco_status.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._deco_status.setMaximumHeight(150)

        # 填充状态行
        status_items = [
            ("AI服务发布背书", "待检测", "发布时自动添加"),
            ("算力发现集成", "待检测", "P2P广播附带"),
            ("买家决策辅助", "待检测", "本地对比显示"),
            ("佣金系统联动", "已就绪", "复用现有系统"),
        ]

        self._deco_status.setRowCount(len(status_items))
        for i, (feature, status, note) in enumerate(status_items):
            self._deco_status.setItem(i, 0, QTableWidgetItem(feature))
            self._deco_status.setItem(i, 1, QTableWidgetItem(status))
            self._deco_status.setItem(i, 2, QTableWidgetItem(note))

        deco_layout.addWidget(self._deco_status)

        layout.addWidget(deco_group)

        # API导出
        api_group = QGroupBox("API 端点")
        api_layout = QVBoxLayout(api_group)

        api_label = QLabel(
            "Hermes 工具函数:\n"
            "  - get_local_ai_capability() -> 返回当前硬件能力\n"
            "  - get_ai_capability_report() -> 返回格式化报告\n"
            "  - can_run_model(model_name) -> 检查模型兼容性"
        )
        api_label.setStyleSheet("font-family: monospace; padding: 10px;")
        api_layout.addWidget(api_label)

        layout.addWidget(api_group)

        layout.addStretch()

        return tab

    def _init_webengine(self) -> None:
        """初始化WebEngine"""
        try:
            test_view = QWebEngineView()
            test_view.deleteLater()
            self._is_webengine_available = True
        except Exception as e:
            print(f"WebEngine不可用: {e}")
            self._is_webengine_available = False
            if hasattr(self, '_fallback_widget'):
                self._fallback_widget.show()
            if hasattr(self, '_web_container'):
                self._web_container.hide()

    def _load_detector(self) -> None:
        """加载检测器HTML页面"""
        if not self._is_webengine_available:
            return

        if not self._html_path.exists():
            print(f"警告: 检测器HTML不存在 {self._html_path}")
            return

        self._inject_js_bridge()

        url = QUrl.fromLocalFile(str(self._html_path.resolve()))
        self._webview.setUrl(url)

    def _inject_js_bridge(self) -> None:
        """注入JavaScript桥接代码"""
        script = self._js_bridge.inject_detection_script()
        self._page.profile().setScriptPalette(self._page.defaultProfile().scriptPalette())
        self._page.loadFinished.connect(
            lambda ok: self._webview.page().runJavaScript(script) if ok else None
        )

    @pyqtSlot(dict)
    def _on_detection_completed(self, data: dict) -> None:
        """处理检测完成"""
        try:
            self._current_result = AIDetectionResult.from_dict(data)
            self._current_profile = self._current_result.hardware

            self._update_ui_with_result()

            self.detection_done.emit(data)
            self.capability_changed.emit(self._current_profile.to_dict())

            self._update_integration_view()

            self._save_detection_to_db(data)

            print(f"检测完成: {self._current_profile.cpu_model}, "
                  f"推荐模型: {self._current_result.get_best_model()['modelName']}")

        except Exception as e:
            print(f"处理检测结果失败: {e}")

    @pyqtSlot(str)
    def _on_detection_error(self, error: str) -> None:
        """处理检测错误"""
        print(f"检测错误: {error}")

    def _update_ui_with_result(self) -> None:
        """用检测结果更新UI"""
        if not self._current_result:
            return

        hw = self._current_result.hardware

        # 更新数据视图的输入框
        self._cpu_model_input.setText(hw.cpu_model)
        self._cpu_cores_input.setValue(hw.cpu_cores)
        self._cpu_threads_input.setValue(hw.cpu_threads)
        self._ram_total_input.setValue(int(hw.ram_total_gb))
        self._gpu_model_input.setText(hw.gpu_renderer)
        self._gpu_vram_input.setValue(int(hw.gpu_vram_gb))
        self._has_gpu_checkbox.setChecked(hw.has_gpu)

        # 更新报告文本
        self._report_text.setPlainText(
            self._current_result.generate_capability_report()
        )

        # 更新模型预览
        self._update_model_preview()

    def _update_model_preview(self) -> None:
        """更新模型匹配预览表"""
        if not self._current_profile:
            self._current_profile = HardwareProfile(
                cpu_cores=self._cpu_cores_input.value(),
                cpu_threads=self._cpu_threads_input.value(),
                cpu_model=self._cpu_model_input.toPlainText() or "Unknown",
                ram_total_gb=float(self._ram_total_input.value()),
                gpu_renderer=self._gpu_model_input.toPlainText() or "Unknown",
                gpu_vram_gb=float(self._gpu_vram_input.value()),
                has_gpu=self._has_gpu_checkbox.isChecked()
            )

        # 简单的模型匹配
        models = [
            {"name": "Llama-2-7B", "params": "7B", "vram": 6},
            {"name": "Llama-2-13B", "params": "13B", "vram": 12},
            {"name": "Mistral-7B", "params": "7B", "vram": 6},
            {"name": "Qwen-2.5-7B", "params": "7B", "vram": 6},
            {"name": "ChatGLM3-6B", "params": "6B", "vram": 5},
            {"name": "DeepSeek-7B", "params": "7B", "vram": 6},
        ]

        self._model_preview_table.setRowCount(len(models))
        for i, model in enumerate(models):
            can_run = self._current_profile.can_run_model(model["name"], model["vram"])
            speed = self._current_profile.estimate_speed(model["name"], model["vram"])

            compat = "支持" if can_run else "不足"
            speed_str = f"{speed} tok/s" if speed > 0 else "N/A"

            self._model_preview_table.setItem(i, 0, QTableWidgetItem(model["name"]))
            self._model_preview_table.setItem(i, 1, QTableWidgetItem(model["params"]))
            self._model_preview_table.setItem(i, 2, QTableWidgetItem(f"{model['vram']}GB"))
            self._model_preview_table.setItem(i, 3, QTableWidgetItem(compat))
            self._model_preview_table.setItem(i, 4, QTableWidgetItem(speed_str))

    def _update_integration_view(self) -> None:
        """更新集成视图"""
        if not self._current_result:
            return

        status_items = [
            ("AI服务发布背书", "已就绪", "发布时自动添加"),
            ("算力发现集成", "已就绪", "P2P广播附带"),
            ("买家决策辅助", "已就绪", "本地对比显示"),
            ("佣金系统联动", "已就绪", "复用现有系统"),
        ]

        for i, (feature, status, note) in enumerate(status_items):
            item = self._deco_status.item(i, 1)
            if item:
                item.setText(status)

    def _save_profile(self) -> None:
        """保存当前配置到文件"""
        try:
            if not self._current_profile:
                self._current_profile = HardwareProfile(
                    cpu_cores=self._cpu_cores_input.value(),
                    cpu_threads=self._cpu_threads_input.value(),
                    cpu_model=self._cpu_model_input.toPlainText() or "Unknown",
                    cpu_arch="x64",
                    ram_total_gb=float(self._ram_total_input.value()),
                    ram_available_gb=float(self._ram_total_input.value()) * 0.4,
                    ram_type=self._ram_type_input.currentText(),
                    gpu_renderer=self._gpu_model_input.toPlainText() or "Unknown",
                    gpu_vram_gb=float(self._gpu_vram_input.value()),
                    has_gpu=self._has_gpu_checkbox.isChecked()
                )

            config_dir = Path.home() / ".hermes-desktop"
            config_dir.mkdir(parents=True, exist_ok=True)

            profile_file = config_dir / "hardware_profile.json"
            with open(profile_file, 'w', encoding='utf-8') as f:
                json.dump(self._current_profile.to_dict(), f, indent=2, ensure_ascii=False)

            print(f"配置已保存: {profile_file}")

        except Exception as e:
            print(f"保存配置失败: {e}")

    def _export_report(self) -> None:
        """导出能力报告"""
        if not self._current_result:
            print("请先运行检测")
            return

        try:
            report = self._current_result.generate_capability_report()

            download_dir = Path.home() / "Downloads" / "hermes-desktop"
            download_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = download_dir / f"ai_capability_report_{timestamp}.txt"

            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)

            print(f"报告已导出: {report_file}")

        except Exception as e:
            print(f"导出报告失败: {e}")

    def _save_detection_to_db(self, data: dict) -> None:
        """保存检测结果到数据库"""
        try:
            db_path = Path(__file__).parent.parent / "database" / "hermes.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)

            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_capability_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_hash TEXT NOT NULL,
                    cpu_model TEXT,
                    cpu_cores INTEGER,
                    ram_total_gb REAL,
                    gpu_renderer TEXT,
                    gpu_vram_gb REAL,
                    best_model TEXT,
                    best_speed INTEGER,
                    timestamp TEXT NOT NULL,
                    raw_data TEXT
                )
            """)

            recommended = data.get("recommended_models", [])
            best = next((m for m in recommended if m.get("recommended")), None)
            best_model = best.get("modelName", "N/A") if best else "N/A"
            best_speed = best.get("speedEstimate", 0) if best else 0

            hw = data.get("hardware", {})
            profile_hash = hashlib.sha256(
                f"{hw.get('cpuModel', '')}:{hw.get('ramTotalGB', 0)}:{hw.get('gpuRenderer', '')}".encode()
            ).hexdigest()[:16]

            cursor.execute("""
                INSERT INTO ai_capability_history
                (profile_hash, cpu_model, cpu_cores, ram_total_gb, gpu_renderer,
                 gpu_vram_gb, best_model, best_speed, timestamp, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile_hash,
                hw.get("cpuModel", "Unknown"),
                hw.get("cpuCores", 0),
                hw.get("ramTotalGB", 0),
                hw.get("gpuRenderer", "Unknown"),
                hw.get("gpuVRAM", 0),
                best_model,
                best_speed,
                data.get("timestamp", datetime.now().isoformat()),
                json.dumps(data, ensure_ascii=False)
            ))

            conn.commit()
            conn.close()

            print(f"检测历史已保存到数据库")

        except Exception as e:
            print(f"保存检测历史失败: {e}")

    # =========================================================================
    # 公共接口
    # =========================================================================

    def get_current_profile(self) -> Optional[HardwareProfile]:
        """获取当前硬件配置"""
        return self._current_profile

    def get_current_result(self) -> Optional[AIDetectionResult]:
        """获取当前检测结果"""
        return self._current_result

    def run_detection(self) -> None:
        """触发一次检测"""
        if not self._is_webengine_available:
            # 使用手动输入的数据
            self._current_profile = HardwareProfile(
                cpu_cores=self._cpu_cores_input.value(),
                cpu_threads=self._cpu_threads_input.value(),
                cpu_model=self._cpu_model_input.toPlainText() or "Unknown",
                cpu_arch="x64",
                ram_total_gb=float(self._ram_total_input.value()),
                ram_available_gb=float(self._ram_total_input.value()) * 0.4,
                ram_type=self._ram_type_input.currentText(),
                gpu_renderer=self._gpu_model_input.toPlainText() or "Unknown",
                gpu_vram_gb=float(self._gpu_vram_input.value()),
                has_gpu=self._has_gpu_checkbox.isChecked()
            )
            self._update_model_preview()
            return

        # 触发WebView中的检测
        self._webview.page().runJavaScript("startDetection()")

    def load_saved_profile(self) -> bool:
        """加载已保存的配置"""
        try:
            config_file = Path.home() / ".hermes-desktop" / "hardware_profile.json"
            if not config_file.exists():
                return False

            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self._current_profile = HardwareProfile.from_dict(data)
            self._update_ui_with_result()
            return True

        except Exception as e:
            print(f"加载配置失败: {e}")
            return False


# =============================================================================
# 辅助函数
# =============================================================================

def get_hardware_profile_from_file() -> Optional[HardwareProfile]:
    """从文件获取已保存的硬件配置"""
    try:
        config_file = Path.home() / ".hermes-desktop" / "hardware_profile.json"
        if not config_file.exists():
            return None

        with open(config_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return HardwareProfile.from_dict(data)

    except Exception:
        return None


def create_hardware_detector_panel(parent: Optional[QWidget] = None) -> HardwareDetectorPanel:
    """工厂函数: 创建硬件检测面板"""
    return HardwareDetectorPanel(parent=parent)
