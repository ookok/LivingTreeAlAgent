"""
配置快捷修改

在所有调用配置的 UI 中提供快捷的修改配置的功能
"""

import logging
from typing import Dict, Optional, Any, Callable
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QSpinBox, QCheckBox, QPushButton, QDialog
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)


class ConfigQuickEdit(QDialog):
    """
    配置快捷修改对话框
    """
    
    def __init__(self, config_name: str, current_value: Any, config_type: str, options: Optional[list] = None, parent=None):
        """
        初始化配置快捷修改对话框
        
        Args:
            config_name: 配置名称
            current_value: 当前值
            config_type: 配置类型（string, int, bool, select）
            options: 选项列表（当类型为 select 时使用）
            parent: 父窗口
        """
        super().__init__(parent)
        self.setWindowTitle(f"修改配置: {config_name}")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setFixedSize(400, 200)
        
        self.config_name = config_name
        self.current_value = current_value
        self.config_type = config_type
        self.options = options
        self.result = None
        
        self._build_ui()
    
    def _build_ui(self):
        """
        构建 UI
        """
        layout = QVBoxLayout(self)
        
        # 配置名称
        name_label = QLabel(f"配置: {self.config_name}")
        name_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(name_label)
        
        # 当前值
        current_label = QLabel(f"当前值: {self.current_value}")
        current_label.setStyleSheet("color: #666;")
        layout.addWidget(current_label)
        
        # 输入控件
        input_layout = QHBoxLayout()
        layout.addLayout(input_layout)
        
        label = QLabel("新值:")
        input_layout.addWidget(label)
        
        if self.config_type == "string":
            self._input = QLineEdit(str(self.current_value))
        elif self.config_type == "int":
            self._input = QSpinBox()
            self._input.setValue(int(self.current_value))
            self._input.setRange(-999999, 999999)
        elif self.config_type == "bool":
            self._input = QCheckBox()
            self._input.setChecked(bool(self.current_value))
        elif self.config_type == "select" and self.options:
            self._input = QComboBox()
            self._input.addItems(self.options)
            if str(self.current_value) in self.options:
                self._input.setCurrentText(str(self.current_value))
        else:
            self._input = QLineEdit(str(self.current_value))
        
        input_layout.addWidget(self._input)
        
        # 按钮
        button_layout = QHBoxLayout()
        layout.addLayout(button_layout)
        
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        ok_button = QPushButton("确定")
        ok_button.clicked.connect(self._on_ok)
        button_layout.addWidget(ok_button)
    
    def _on_ok(self):
        """
        确定按钮点击
        """
        if self.config_type == "string":
            self.result = self._input.text()
        elif self.config_type == "int":
            self.result = self._input.value()
        elif self.config_type == "bool":
            self.result = self._input.isChecked()
        elif self.config_type == "select":
            self.result = self._input.currentText()
        else:
            self.result = self._input.text()
        
        self.accept()
    
    def get_result(self) -> Any:
        """
        获取修改结果
        
        Returns:
            Any: 修改后的值
        """
        return self.result


class ConfigQuickEditManager:
    """
    配置快捷修改管理器
    """
    
    def __init__(self):
        self._config_callbacks: Dict[str, Callable] = {}
    
    def register_config_callback(self, config_name: str, callback: Callable):
        """
        注册配置回调
        
        Args:
            config_name: 配置名称
            callback: 回调函数，用于保存配置
        """
        self._config_callbacks[config_name] = callback
    
    def edit_config(self, config_name: str, current_value: Any, config_type: str = "string", options: Optional[list] = None, parent=None) -> Optional[Any]:
        """
        编辑配置
        
        Args:
            config_name: 配置名称
            current_value: 当前值
            config_type: 配置类型
            options: 选项列表
            parent: 父窗口
            
        Returns:
            Optional[Any]: 修改后的值
        """
        dialog = ConfigQuickEdit(config_name, current_value, config_type, options, parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_value = dialog.get_result()
            
            # 调用回调保存配置
            if config_name in self._config_callbacks:
                try:
                    self._config_callbacks[config_name](new_value)
                    logger.info(f"Config {config_name} updated to {new_value}")
                except Exception as e:
                    logger.error(f"Failed to update config {config_name}: {e}")
            
            return new_value
        return None
    
    def create_config_label(self, config_name: str, current_value: Any, config_type: str = "string", options: Optional[list] = None, parent=None) -> QWidget:
        """
        创建配置标签，点击可以修改
        
        Args:
            config_name: 配置名称
            current_value: 当前值
            config_type: 配置类型
            options: 选项列表
            parent: 父窗口
            
        Returns:
            QWidget: 配置标签组件
        """
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        label = QLabel(f"{config_name}: {current_value}")
        label.setStyleSheet("cursor: pointer; color: #3B82F6;")
        label.mousePressEvent = lambda event: self.edit_config(
            config_name, current_value, config_type, options, parent
        )
        layout.addWidget(label)
        
        return widget
