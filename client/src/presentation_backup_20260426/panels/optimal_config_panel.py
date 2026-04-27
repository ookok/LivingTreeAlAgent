# -*- coding: utf-8 -*-
"""
Optimal Config Panel - 可视化配置面板
=====================================

提供直观的配置界面，支持:
1. Depth 滑块调节
2. 实时配置预览
3. 配置持久化

Author: LivingTreeAI Team
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any, Callable

# PyQt6 导入
try:
    from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSettings
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QSlider, QSpinBox, QDoubleSpinBox, QCheckBox,
        QPushButton, QGroupBox, QFormLayout, QTextEdit,
        QComboBox, QTabWidget
    )
    from PyQt6.QtGui import QFont, QColor, QPalette
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    # 降级为 mock
    class QWidget:
        def __init__(self, *args, **kwargs): pass
    class pyqtSignal:
        def __init__(self, *args): pass

logger = logging.getLogger(__name__)


# ── 配置信号 ────────────────────────────────────────────────────────────────


class ConfigSignals:
    """配置信号"""
    config_changed = pyqtSignal(dict)  # 配置改变信号
    depth_changed = pyqtSignal(int)    # depth 改变信号
    apply_clicked = pyqtSignal(dict)   # 应用按钮点击信号


# ── 配置面板 ───────────────────────────────────────────────────────────────


class OptimalConfigPanel(QWidget if PYQT6_AVAILABLE else object):
    """
    Optimal Config 可视化配置面板

    功能：
    1. Depth 滑块调节 (1-10)
    2. 实时配置预览
    3. 配置持久化 (QSettings)
    4. 预设配置选择

    使用示例：
    ```python
    from client.src.presentation.panels.optimal_config_panel import OptimalConfigPanel

    panel = OptimalConfigPanel()
    panel.config_changed.connect(lambda cfg: print(f"Config: {cfg}"))
    panel.show()
    ```
    """

    # 信号
    config_changed = pyqtSignal(dict)
    depth_changed = pyqtSignal(int)
    apply_clicked = pyqtSignal(dict)

    # 配置默认值
    DEFAULT_CONFIG = {
        'depth': 5,
        'timeout': 57.0,
        'max_retries': 3,
        'context_limit': 8192,
        'max_tokens': 4096,
        'temperature': 0.7,
        'use_reasoning': True,
        'use_execution': False,
        'use_verification': False,
    }

    # 预设配置
    PRESETS = {
        '快速模式': {'depth': 2, 'timeout': 30.0, 'max_retries': 1},
        '平衡模式': {'depth': 5, 'timeout': 60.0, 'max_retries': 3},
        '深度模式': {'depth': 8, 'timeout': 180.0, 'max_retries': 5},
        '专家模式': {'depth': 10, 'timeout': 300.0, 'max_retries': 7},
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 配置
        self._config = self.DEFAULT_CONFIG.copy()
        self._signals = ConfigSignals()
        
        # 持久化
        self._settings = QSettings("LivingTreeAI", "OptimalConfig") if PYQT6_AVAILABLE else None
        
        # 初始化 UI
        if PYQT6_AVAILABLE:
            self._init_ui()
            self._load_config()
        else:
            self._mock_ui()

    def _init_ui(self):
        """初始化 UI"""
        self.setWindowTitle("Optimal Config 配置面板")
        self.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # 1. 预设选择
        preset_group = self._create_preset_group()
        layout.addWidget(preset_group)
        
        # 2. Tab 页面
        tab_widget = QTabWidget()
        
        # Tab 1: 基础配置
        tab_widget.addTab(self._create_basic_tab(), "基础配置")
        
        # Tab 2: 高级配置
        tab_widget.addTab(self._create_advanced_tab(), "高级配置")
        
        # Tab 3: 实时预览
        tab_widget.addTab(self._create_preview_tab(), "配置预览")
        
        layout.addWidget(tab_widget)
        
        # 3. 按钮
        button_layout = self._create_button_layout()
        layout.addLayout(button_layout)

    def _create_preset_group(self) -> QWidget:
        """创建预设选择组"""
        group = QGroupBox("快速预设")
        layout = QVBoxLayout(group)
        
        # 预设按钮
        btn_layout = QHBoxLayout()
        for name in self.PRESETS.keys():
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, n=name: self._apply_preset(n))
            btn.setMinimumHeight(40)
            btn_layout.addWidget(btn)
        
        layout.addLayout(btn_layout)
        return group

    def _create_basic_tab(self) -> QWidget:
        """创建基础配置 Tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        form = QFormLayout()
        
        # Depth 滑块
        depth_layout = QHBoxLayout()
        self._depth_slider = QSlider(Qt.Orientation.Horizontal)
        self._depth_slider.setRange(1, 10)
        self._depth_slider.setValue(5)
        self._depth_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._depth_slider.setTickInterval(1)
        self._depth_slider.valueChanged.connect(self._on_depth_changed)
        
        self._depth_label = QLabel("5")
        self._depth_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        
        depth_layout.addWidget(self._depth_slider)
        depth_layout.addWidget(self._depth_label)
        
        form.addRow("深度 (Depth):", depth_layout)
        
        # 复杂度标签
        self._complexity_label = QLabel("中等复杂度")
        self._complexity_label.setStyleSheet("color: #3B82F6;")
        form.addRow("", self._complexity_label)
        
        # Timeout
        self._timeout_spin = QDoubleSpinBox()
        self._timeout_spin.setRange(10, 600)
        self._timeout_spin.setValue(60)
        self._timeout_spin.setSuffix(" 秒")
        self._timeout_spin.valueChanged.connect(self._on_timeout_changed)
        form.addRow("超时时间:", self._timeout_spin)
        
        # Max Retries
        self._retries_spin = QSpinBox()
        self._retries_spin.setRange(0, 10)
        self._retries_spin.setValue(3)
        self._retries_spin.valueChanged.connect(self._on_retries_changed)
        form.addRow("最大重试:", self._retries_spin)
        
        # Context Limit
        self._context_spin = QSpinBox()
        self._context_spin.setRange(1024, 65536)
        self._context_spin.setValue(8192)
        self._context_spin.setSingleStep(1024)
        self._context_spin.valueChanged.connect(self._on_context_changed)
        form.addRow("上下文限制:", self._context_spin)
        
        layout.addLayout(form)
        layout.addStretch()
        return widget

    def _create_advanced_tab(self) -> QWidget:
        """创建高级配置 Tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        form = QFormLayout()
        
        # Max Tokens
        self._tokens_spin = QSpinBox()
        self._tokens_spin.setRange(256, 32768)
        self._tokens_spin.setValue(4096)
        self._tokens_spin.setSingleStep(256)
        self._tokens_spin.valueChanged.connect(self._on_tokens_changed)
        form.addRow("最大 Token:", self._tokens_spin)
        
        # Temperature
        self._temp_spin = QDoubleSpinBox()
        self._temp_spin.setRange(0.0, 2.0)
        self._temp_spin.setValue(0.7)
        self._temp_spin.setSingleStep(0.1)
        self._temp_spin.valueChanged.connect(self._on_temp_changed)
        form.addRow("Temperature:", self._temp_spin)
        
        # 开关选项
        self._reasoning_check = QCheckBox("启用推理")
        self._reasoning_check.setChecked(True)
        self._reasoning_check.toggled.connect(self._on_reasoning_changed)
        form.addRow("", self._reasoning_check)
        
        self._execution_check = QCheckBox("启用代码执行")
        self._execution_check.toggled.connect(self._on_execution_changed)
        form.addRow("", self._execution_check)
        
        self._verification_check = QCheckBox("启用结果验证")
        self._verification_check.toggled.connect(self._on_verification_changed)
        form.addRow("", self._verification_check)
        
        layout.addLayout(form)
        layout.addStretch()
        return widget

    def _create_preview_tab(self) -> QWidget:
        """创建配置预览 Tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 预览文本
        self._preview_text = QTextEdit()
        self._preview_text.setReadOnly(True)
        self._preview_text.setFont(QFont("Consolas", 10))
        layout.addWidget(self._preview_text)
        
        # 更新预览
        self._update_preview()
        
        return widget

    def _create_button_layout(self) -> QHBoxLayout:
        """创建按钮布局"""
        layout = QHBoxLayout()
        
        # 保存按钮
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save_config)
        layout.addWidget(save_btn)
        
        # 重置按钮
        reset_btn = QPushButton("重置")
        reset_btn.clicked.connect(self._reset_config)
        layout.addWidget(reset_btn)
        
        # 应用按钮
        apply_btn = QPushButton("应用")
        apply_btn.setDefault(True)
        apply_btn.clicked.connect(self._apply_config)
        layout.addWidget(apply_btn)
        
        return layout

    # ── 事件处理 ────────────────────────────────────────────────────────────

    def _on_depth_changed(self, value: int):
        """Depth 滑块改变"""
        self._depth_label.setText(str(value))
        self._config['depth'] = value
        
        # 更新复杂度标签
        if value <= 2:
            self._complexity_label.setText("极简")
            self._complexity_label.setStyleSheet("color: #22C55E;")
        elif value <= 4:
            self._complexity_label.setText("简单")
            self._complexity_label.setStyleSheet("color: #84CC16;")
        elif value <= 6:
            self._complexity_label.setText("中等复杂度")
            self._complexity_label.setStyleSheet("color: #3B82F6;")
        elif value <= 8:
            self._complexity_label.setText("复杂")
            self._complexity_label.setStyleSheet("color: #F59E0B;")
        else:
            self._complexity_label.setText("极复杂")
            self._complexity_label.setStyleSheet("color: #EF4444;")
        
        self._update_preview()
        self.depth_changed.emit(value)
        self.config_changed.emit(self._config.copy())

    def _on_timeout_changed(self, value: float):
        self._config['timeout'] = value
        self._update_preview()
        self.config_changed.emit(self._config.copy())

    def _on_retries_changed(self, value: int):
        self._config['max_retries'] = value
        self._update_preview()
        self.config_changed.emit(self._config.copy())

    def _on_context_changed(self, value: int):
        self._config['context_limit'] = value
        self._update_preview()
        self.config_changed.emit(self._config.copy())

    def _on_tokens_changed(self, value: int):
        self._config['max_tokens'] = value
        self._update_preview()

    def _on_temp_changed(self, value: float):
        self._config['temperature'] = value
        self._update_preview()

    def _on_reasoning_changed(self, checked: bool):
        self._config['use_reasoning'] = checked
        self.config_changed.emit(self._config.copy())

    def _on_execution_changed(self, checked: bool):
        self._config['use_execution'] = checked
        self.config_changed.emit(self._config.copy())

    def _on_verification_changed(self, checked: bool):
        self._config['use_verification'] = checked
        self.config_changed.emit(self._config.copy())

    def _apply_preset(self, name: str):
        """应用预设"""
        if name in self.PRESETS:
            preset = self.PRESETS[name]
            self._config.update(preset)
            self._sync_ui()
            self._update_preview()
            self.config_changed.emit(self._config.copy())
            logger.info(f"Applied preset: {name}")

    def _update_preview(self):
        """更新配置预览"""
        preview = f"""
╔══════════════════════════════════════════════════════════════╗
║                  Optimal Config 实时预览                     ║
╠══════════════════════════════════════════════════════════════╣
║  Depth:          {self._config['depth']:>2}                                        ║
║  Timeout:         {self._config['timeout']:>6.1f} 秒                               ║
║  Max Retries:     {self._config['max_retries']:>2}                                        ║
║  Context Limit:   {self._config['context_limit']:>6} tokens                         ║
║  Max Tokens:      {self._config['max_tokens']:>6} tokens                         ║
║  Temperature:     {self._config['temperature']:.1f}                                        ║
╠══════════════════════════════════════════════════════════════╣
║  Features:                                                 ║
║    Reasoning:      {'✓' if self._config['use_reasoning'] else '✗'}                                        ║
║    Execution:      {'✓' if self._config['use_execution'] else '✗'}                                        ║
║    Verification:   {'✓' if self._config['use_verification'] else '✗'}                                        ║
╚══════════════════════════════════════════════════════════════╝
"""
        if hasattr(self, '_preview_text'):
            self._preview_text.setPlainText(preview)

    def _save_config(self):
        """保存配置"""
        if self._settings:
            for key, value in self._config.items():
                self._settings.setValue(key, value)
            self._settings.sync()
            logger.info("Config saved")
        self.config_changed.emit(self._config.copy())

    def _load_config(self):
        """加载配置"""
        if self._settings:
            for key in self._config.keys():
                value = self._settings.value(key)
                if value is not None:
                    # 类型转换
                    if isinstance(self._config[key], bool):
                        self._config[key] = value.lower() == 'true' if isinstance(value, str) else bool(value)
                    elif isinstance(self._config[key], int):
                        self._config[key] = int(value)
                    elif isinstance(self._config[key], float):
                        self._config[key] = float(value)
                    else:
                        self._config[key] = value
            self._sync_ui()
            self._update_preview()
            logger.info("Config loaded")

    def _reset_config(self):
        """重置配置"""
        self._config = self.DEFAULT_CONFIG.copy()
        self._sync_ui()
        self._update_preview()
        logger.info("Config reset")

    def _apply_config(self):
        """应用配置"""
        self.apply_clicked.emit(self._config.copy())
        logger.info("Config applied")

    def _sync_ui(self):
        """同步 UI"""
        if not PYQT6_AVAILABLE:
            return
        
        self._depth_slider.setValue(self._config['depth'])
        self._timeout_spin.setValue(self._config['timeout'])
        self._retries_spin.setValue(self._config['max_retries'])
        self._context_spin.setValue(self._config['context_limit'])
        self._tokens_spin.setValue(self._config['max_tokens'])
        self._temp_spin.setValue(self._config['temperature'])
        self._reasoning_check.setChecked(self._config['use_reasoning'])
        self._execution_check.setChecked(self._config['use_execution'])
        self._verification_check.setChecked(self._config['use_verification'])

    def _mock_ui(self):
        """Mock UI (无 PyQt6)"""
        logger.warning("PyQt6 not available, using mock UI")

    # ── 公开接口 ─────────────────────────────────────────────────────────────

    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return self._config.copy()

    def set_config(self, config: Dict[str, Any]):
        """设置配置"""
        self._config.update(config)
        self._sync_ui()
        self._update_preview()
        self.config_changed.emit(self._config.copy())


# ── Mock 版本 (无 PyQt6) ──────────────────────────────────────────────────


class OptimalConfigPanelMock:
    """Mock 版本"""
    
    def __init__(self):
        self._config = OptimalConfigPanel.DEFAULT_CONFIG.copy()
    
    def get_config(self) -> Dict[str, Any]:
        return self._config.copy()
    
    def set_config(self, config: Dict[str, Any]):
        self._config.update(config)
    
    def show(self):
        print("OptimalConfigPanel (Mock Mode)")
        print(f"Config: {self._config}")


# ── 工厂函数 ───────────────────────────────────────────────────────────────


def create_config_panel() -> QWidget:
    """创建配置面板"""
    if PYQT6_AVAILABLE:
        return OptimalConfigPanel()
    return OptimalConfigPanelMock()


# ── 测试入口 ───────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import sys
    
    if PYQT6_AVAILABLE:
        from PyQt6.QtWidgets import QApplication
        
        app = QApplication(sys.argv)
        
        panel = OptimalConfigPanel()
        panel.config_changed.connect(lambda cfg: print(f"Config changed: {cfg}"))
        panel.apply_clicked.connect(lambda cfg: print(f"Applied: {cfg}"))
        panel.show()
        
        sys.exit(app.exec())
    else:
        print("PyQt6 not available, testing mock...")
        panel = create_config_panel()
        panel.show()
        
        # 模拟配置改变
        panel.set_config({'depth': 8, 'timeout': 180.0})
        print(f"New config: {panel.get_config()}")
