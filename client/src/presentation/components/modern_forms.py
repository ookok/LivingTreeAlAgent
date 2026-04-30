"""现代化表单组件 - 支持复杂表单填写和用户引导"""

from PyQt6.QtWidgets import (
    QWidget, QFrame, QLabel, QLineEdit, QTextEdit,
    QComboBox, QCheckBox, QRadioButton, QDateEdit,
    QTimeEdit, QSpinBox, QDoubleSpinBox, QVBoxLayout,
    QHBoxLayout, QFormLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QFont

class ModernTextField(QWidget):
    """现代化文本输入框"""
    
    text_changed = pyqtSignal(str)
    
    def __init__(self, label_text="", placeholder="", parent=None):
        super().__init__(parent)
        self._init_ui(label_text, placeholder)
    
    def _init_ui(self, label_text, placeholder):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        if label_text:
            self._label = QLabel(label_text)
            self._label.setStyleSheet("""
                QLabel {
                    color: #374151;
                    font-size: 13px;
                    font-weight: 500;
                }
            """)
            layout.addWidget(self._label)
        
        self._line_edit = QLineEdit()
        self._line_edit.setPlaceholderText(placeholder)
        self._line_edit.setStyleSheet("""
            QLineEdit {
                background: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 14px;
                color: #1f2937;
            }
            QLineEdit:focus {
                border-color: #6366f1;
                outline: none;
                box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
            }
            QLineEdit:hover {
                border-color: #9ca3af;
            }
        """)
        self._line_edit.textChanged.connect(self.text_changed)
        layout.addWidget(self._line_edit)
    
    def set_text(self, text):
        self._line_edit.setText(text)
    
    def get_text(self):
        return self._line_edit.text()

class ModernTextArea(QWidget):
    """现代化文本域"""
    
    text_changed = pyqtSignal(str)
    
    def __init__(self, label_text="", placeholder="", parent=None):
        super().__init__(parent)
        self._init_ui(label_text, placeholder)
    
    def _init_ui(self, label_text, placeholder):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        if label_text:
            self._label = QLabel(label_text)
            self._label.setStyleSheet("""
                QLabel {
                    color: #374151;
                    font-size: 13px;
                    font-weight: 500;
                }
            """)
            layout.addWidget(self._label)
        
        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText(placeholder)
        self._text_edit.setStyleSheet("""
            QTextEdit {
                background: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 14px;
                color: #1f2937;
            }
            QTextEdit:focus {
                border-color: #6366f1;
                outline: none;
                box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
            }
        """)
        self._text_edit.textChanged.connect(lambda: self.text_changed.emit(self._text_edit.toPlainText()))
        layout.addWidget(self._text_edit)
    
    def set_text(self, text):
        self._text_edit.setPlainText(text)
    
    def get_text(self):
        return self._text_edit.toPlainText()

class ModernComboBox(QWidget):
    """现代化下拉选择框"""
    
    selection_changed = pyqtSignal(str)
    
    def __init__(self, label_text="", options=[], parent=None):
        super().__init__(parent)
        self._init_ui(label_text, options)
    
    def _init_ui(self, label_text, options):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        if label_text:
            self._label = QLabel(label_text)
            self._label.setStyleSheet("""
                QLabel {
                    color: #374151;
                    font-size: 13px;
                    font-weight: 500;
                }
            """)
            layout.addWidget(self._label)
        
        self._combo = QComboBox()
        self._combo.addItems(options)
        self._combo.setStyleSheet("""
            QComboBox {
                background: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 14px;
                color: #1f2937;
                min-width: 150px;
            }
            QComboBox:focus {
                border-color: #6366f1;
                outline: none;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: url(icons/arrow_down.png);
                width: 16px;
                height: 16px;
            }
        """)
        self._combo.currentTextChanged.connect(self.selection_changed)
        layout.addWidget(self._combo)
    
    def set_options(self, options):
        self._combo.clear()
        self._combo.addItems(options)
    
    def get_selected(self):
        return self._combo.currentText()

class ModernCheckBox(QWidget):
    """现代化复选框"""
    
    state_changed = pyqtSignal(bool)
    
    def __init__(self, label_text="", checked=False, parent=None):
        super().__init__(parent)
        self._init_ui(label_text, checked)
    
    def _init_ui(self, label_text, checked):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        self._check = QCheckBox()
        self._check.setChecked(checked)
        self._check.setStyleSheet("""
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #d1d5db;
                border-radius: 4px;
                background: white;
            }
            QCheckBox::indicator:checked {
                border-color: #6366f1;
                background: #6366f1;
            }
            QCheckBox::indicator:checked::after {
                image: url(icons/check.png);
                width: 10px;
                height: 10px;
            }
        """)
        self._check.stateChanged.connect(lambda state: self.state_changed.emit(state == Qt.CheckState.Checked.value))
        layout.addWidget(self._check)
        
        self._label = QLabel(label_text)
        self._label.setStyleSheet("""
            QLabel {
                color: #374151;
                font-size: 14px;
            }
        """)
        layout.addWidget(self._label)
        layout.addStretch()
    
    def is_checked(self):
        return self._check.isChecked()

class ModernRadioGroup(QWidget):
    """现代化单选按钮组"""
    
    selection_changed = pyqtSignal(str)
    
    def __init__(self, label_text="", options=[], parent=None):
        super().__init__(parent)
        self._init_ui(label_text, options)
    
    def _init_ui(self, label_text, options):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        if label_text:
            self._label = QLabel(label_text)
            self._label.setStyleSheet("""
                QLabel {
                    color: #374151;
                    font-size: 13px;
                    font-weight: 500;
                    margin-bottom: 8px;
                }
            """)
            layout.addWidget(self._label)
        
        self._radios = []
        for option in options:
            radio = QRadioButton(option)
            radio.setStyleSheet("""
                QRadioButton {
                    spacing: 8px;
                    color: #374151;
                    font-size: 14px;
                }
                QRadioButton::indicator {
                    width: 16px;
                    height: 16px;
                    border: 2px solid #d1d5db;
                    border-radius: 50%;
                    background: white;
                }
                QRadioButton::indicator:checked {
                    border-color: #6366f1;
                }
                QRadioButton::indicator:checked::after {
                    width: 8px;
                    height: 8px;
                    background: #6366f1;
                    border-radius: 50%;
                    margin: 3px;
                }
            """)
            radio.toggled.connect(lambda checked, opt=option: checked and self.selection_changed.emit(opt))
            self._radios.append(radio)
            layout.addWidget(radio)
    
    def get_selected(self):
        for radio in self._radios:
            if radio.isChecked():
                return radio.text()
        return None

class ModernForm(QWidget):
    """现代化表单容器"""
    
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self._init_ui(title)
    
    def _init_ui(self, title):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        
        if title:
            self._title = QLabel(title)
            self._title.setStyleSheet("""
                QLabel {
                    color: #111827;
                    font-size: 20px;
                    font-weight: 600;
                }
            """)
            layout.addWidget(self._title)
        
        self._form_layout = QFormLayout()
        self._form_layout.setContentsMargins(0, 0, 0, 0)
        self._form_layout.setSpacing(16)
        layout.addLayout(self._form_layout)
    
    def add_field(self, label, widget):
        """添加表单字段"""
        label_widget = QLabel(label)
        label_widget.setStyleSheet("""
            QLabel {
                color: #374151;
                font-size: 13px;
                font-weight: 500;
            }
        """)
        self._form_layout.addRow(label_widget, widget)
    
    def add_widget(self, widget):
        """添加任意组件"""
        self._form_layout.addRow(widget)