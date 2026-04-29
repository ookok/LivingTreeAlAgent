"""
脚本任务授权组件

提供脚本执行前的授权确认功能，确保用户明确同意执行可能有风险的操作。
"""

from typing import Optional, Dict, Any, Callable
from enum import Enum

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QFrame, QCheckBox, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from .minimal_ui_framework import ColorScheme, Spacing, UIComponentFactory


class AuthorizationLevel(Enum):
    """授权级别"""
    LOW = "low"      # 低风险操作（如读取文件）
    MEDIUM = "medium" # 中等风险操作（如写入文件）
    HIGH = "high"    # 高风险操作（如执行系统命令）
    CRITICAL = "critical" # 关键操作（如删除文件、修改系统配置）


class ScriptAuthorizationDialog(QDialog):
    """脚本授权对话框"""
    
    authorized = pyqtSignal(bool)
    
    def __init__(self, parent=None, task_info: Dict[str, Any] = None):
        super().__init__(parent)
        self._task_info = task_info or {}
        self._authorization_granted = False
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        self.setWindowTitle("🔒 脚本执行授权")
        self.setMinimumWidth(480)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(Spacing.MD)
        
        # 风险级别标识
        risk_level = self._get_risk_level()
        risk_widget = self._create_risk_indicator(risk_level)
        layout.addWidget(risk_widget)
        
        # 任务信息卡片
        info_group = QGroupBox("任务详情")
        info_layout = QVBoxLayout(info_group)
        info_layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
        
        # 任务名称
        if "name" in self._task_info:
            name_label = QLabel(f"<b>任务名称:</b> {self._task_info['name']}")
            name_label.setStyleSheet(f"color: {ColorScheme.TEXT_PRIMARY.value};")
            info_layout.addWidget(name_label)
        
        # 任务描述
        if "description" in self._task_info:
            desc_label = QLabel("<b>任务描述:</b>")
            desc_label.setStyleSheet(f"color: {ColorScheme.TEXT_PRIMARY.value};")
            info_layout.addWidget(desc_label)
            
            desc_text = QTextEdit()
            desc_text.setPlainText(self._task_info["description"])
            desc_text.setReadOnly(True)
            desc_text.setMaximumHeight(80)
            desc_text.setStyleSheet("""
                QTextEdit {
                    background-color: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 4px;
                    padding: 8px;
                    font-size: 13px;
                }
            """)
            info_layout.addWidget(desc_text)
        
        # 操作列表
        if "operations" in self._task_info:
            ops_label = QLabel("<b>将执行的操作:</b>")
            ops_label.setStyleSheet(f"color: {ColorScheme.TEXT_PRIMARY.value};")
            info_layout.addWidget(ops_label)
            
            ops_text = QTextEdit()
            ops_text.setPlainText("\n".join([f"- {op}" for op in self._task_info["operations"]]))
            ops_text.setReadOnly(True)
            ops_text.setMaximumHeight(100)
            ops_text.setStyleSheet("""
                QTextEdit {
                    background-color: #fef3c7;
                    border: 1px solid #fbbf24;
                    border-radius: 4px;
                    padding: 8px;
                    font-size: 13px;
                }
            """)
            info_layout.addWidget(ops_text)
        
        layout.addWidget(info_group)
        
        # 风险提示
        warning_frame = QFrame()
        warning_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {'#fef2f2' if risk_level in [AuthorizationLevel.HIGH, AuthorizationLevel.CRITICAL] else '#fffbeb'};
                border: 1px solid {'#fecaca' if risk_level in [AuthorizationLevel.HIGH, AuthorizationLevel.CRITICAL] else '#fde68a'};
                border-radius: 8px;
                padding: {Spacing.MD}px;
            }}
        """)
        warning_layout = QHBoxLayout(warning_frame)
        
        icon_label = QLabel("⚠️" if risk_level == AuthorizationLevel.MEDIUM else "🚨")
        icon_label.setStyleSheet("font-size: 24px;")
        warning_layout.addWidget(icon_label)
        
        warning_text = QLabel(self._get_warning_message(risk_level))
        warning_text.setWordWrap(True)
        warning_text.setStyleSheet(f"font-size: 13px; color: {'#dc2626' if risk_level in [AuthorizationLevel.HIGH, AuthorizationLevel.CRITICAL] else '#d97706'};")
        warning_layout.addWidget(warning_text)
        
        layout.addWidget(warning_frame)
        
        # 不再询问复选框
        self._remember_checkbox = QCheckBox("记住我的选择")
        self._remember_checkbox.setStyleSheet(f"font-size: 12px; color: {ColorScheme.TEXT_SECONDARY.value};")
        layout.addWidget(self._remember_checkbox)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(Spacing.MD)
        
        cancel_btn = UIComponentFactory.create_button(
            self, "取消", variant="secondary", size="md",
            on_click=self._on_cancel
        )
        button_layout.addWidget(cancel_btn)
        
        if risk_level == AuthorizationLevel.CRITICAL:
            confirm_btn = UIComponentFactory.create_button(
                self, "确认执行", variant="error", size="md",
                on_click=self._on_confirm
            )
        else:
            confirm_btn = UIComponentFactory.create_button(
                self, "允许执行", variant="primary", size="md",
                on_click=self._on_confirm
            )
        button_layout.addWidget(confirm_btn)
        
        layout.addLayout(button_layout)
    
    def _get_risk_level(self) -> AuthorizationLevel:
        """获取风险级别"""
        if "risk_level" in self._task_info:
            try:
                return AuthorizationLevel(self._task_info["risk_level"])
            except ValueError:
                pass
        
        # 根据操作类型推断风险级别
        if "operations" in self._task_info:
            for op in self._task_info["operations"]:
                if any(keyword in op.lower() for keyword in ["delete", "remove", "format", "rm -rf"]):
                    return AuthorizationLevel.CRITICAL
                if any(keyword in op.lower() for keyword in ["write", "modify", "overwrite", "install"]):
                    return AuthorizationLevel.HIGH
        
        return AuthorizationLevel.MEDIUM
    
    def _get_warning_message(self, level: AuthorizationLevel) -> str:
        """获取风险警告消息"""
        messages = {
            AuthorizationLevel.LOW: "此操作风险较低，但仍建议您确认后再执行。",
            AuthorizationLevel.MEDIUM: "此操作可能会修改文件或系统设置，请确认您了解其影响。",
            AuthorizationLevel.HIGH: "⚠️ 警告：此操作可能会对系统或数据造成影响，请仔细确认操作内容后再继续。",
            AuthorizationLevel.CRITICAL: "🚨 危险：此操作可能会删除文件或造成不可逆的系统更改！请务必仔细检查操作内容。"
        }
        return messages.get(level, "请确认此操作")
    
    def _create_risk_indicator(self, level: AuthorizationLevel) -> QWidget:
        """创建风险级别指示器"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        level_label = QLabel("风险级别:")
        level_label.setStyleSheet(f"font-size: 12px; color: {ColorScheme.TEXT_SECONDARY.value};")
        layout.addWidget(level_label)
        
        colors = {
            AuthorizationLevel.LOW: "#22C55E",
            AuthorizationLevel.MEDIUM: "#F59E0B",
            AuthorizationLevel.HIGH: "#EF4444",
            AuthorizationLevel.CRITICAL: "#DC2626"
        }
        
        level_text = {
            AuthorizationLevel.LOW: "低",
            AuthorizationLevel.MEDIUM: "中",
            AuthorizationLevel.HIGH: "高",
            AuthorizationLevel.CRITICAL: "关键"
        }
        
        badge = QFrame()
        badge.setFixedSize(60, 24)
        badge.setStyleSheet(f"""
            QFrame {{
                background-color: {colors[level]};
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
            }}
        """)
        
        badge_label = QLabel(level_text[level])
        badge_label.setStyleSheet("color: white; font-size: 12px; font-weight: bold;")
        
        badge_layout = QVBoxLayout(badge)
        badge_layout.addWidget(badge_label)
        
        layout.addWidget(badge)
        
        return widget
    
    def _on_cancel(self):
        """取消授权"""
        self._authorization_granted = False
        self.authorized.emit(False)
        self.close()
    
    def _on_confirm(self):
        """确认授权"""
        self._authorization_granted = True
        
        if self._remember_checkbox.isChecked() and "name" in self._task_info:
            self._save_authorization(self._task_info["name"])
        
        self.authorized.emit(True)
        self.close()
    
    def _save_authorization(self, task_name: str):
        """保存授权记录"""
        # 可以扩展保存到配置文件
        pass
    
    def was_authorized(self) -> bool:
        """是否已授权"""
        return self._authorization_granted


class ScriptTaskHandler:
    """脚本任务处理器"""
    
    def __init__(self):
        self._authorized_tasks = set()
    
    def check_authorization(self, task_info: Dict[str, Any], parent=None) -> bool:
        """检查并获取授权"""
        task_name = task_info.get("name", "unknown")
        
        # 检查是否已授权
        if task_name in self._authorized_tasks:
            return True
        
        # 显示授权对话框
        dialog = ScriptAuthorizationDialog(parent, task_info)
        dialog.exec()
        
        if dialog.was_authorized():
            self._authorized_tasks.add(task_name)
            return True
        
        return False
    
    def execute_script(self, task_info: Dict[str, Any], on_complete: Optional[Callable] = None):
        """执行脚本任务（带授权检查）"""
        if not self.check_authorization(task_info):
            if on_complete:
                on_complete(False, "用户拒绝授权")
            return False
        
        # 执行脚本逻辑
        try:
            # 这里应该是实际的脚本执行逻辑
            result = self._execute_task(task_info)
            
            if on_complete:
                on_complete(True, result)
            
            return True
        except Exception as e:
            if on_complete:
                on_complete(False, str(e))
            return False
    
    def _execute_task(self, task_info: Dict[str, Any]) -> str:
        """执行实际任务"""
        return f"任务 '{task_info.get('name')}' 执行成功"


# 全局实例
_script_handler = None

def get_script_handler() -> ScriptTaskHandler:
    """获取全局脚本任务处理器"""
    global _script_handler
    if _script_handler is None:
        _script_handler = ScriptTaskHandler()
    return _script_handler


# 示例使用
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    task_info = {
        "name": "文件清理脚本",
        "description": "清理临时文件目录",
        "operations": [
            "删除 /tmp/*",
            "删除 ~/.cache/*",
            "清理回收站"
        ],
        "risk_level": "critical"
    }
    
    handler = get_script_handler()
    result = handler.check_authorization(task_info)
    print(f"授权结果: {result}")