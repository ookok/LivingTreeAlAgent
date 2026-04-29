"""
定时任务管理面板
Schedule Management Panel

功能：
- 自然语言创建定时任务
- 查看和管理现有任务
- 支持创建/查询/删除操作
"""

import sys
from typing import Optional, List, Dict, Any
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QListWidget, QListWidgetItem,
    QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QScrollArea,
    QFrame, QSizePolicy, QMessageBox, QToolTip
)
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon, QAction

# 导入定时任务核心模块
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])
from core.smart_fallback.schedule_nlp import NLPScheduleParser, ParsedSchedule, CommandType
from core.smart_fallback.schedule_command import ScheduleCommandExecutor


class ScheduleCard(QFrame):
    """定时任务卡片"""

    delete_requested = pyqtSignal(str)  # 请求删除任务
    edit_requested = pyqtSignal(str)   # 请求编辑任务

    def __init__(self, task_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.task_data = task_data
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setLineWidth(1)

        # 根据状态设置颜色
        status = self.task_data.get("status", "ACTIVE")
        if status == "ACTIVE":
            self.setStyleSheet("""
                ScheduleCard {
                    background-color: #f8fff8;
                    border: 1px solid #4caf50;
                    border-radius: 8px;
                    padding: 10px;
                }
            """)
        else:
            self.setStyleSheet("""
                ScheduleCard {
                    background-color: #fff8f8;
                    border: 1px solid #f44336;
                    border-radius: 8px;
                    padding: 10px;
                }
            """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 标题行
        header_layout = QHBoxLayout()

        status_icon = "🟢" if status == "ACTIVE" else "🔴"
        title = self.task_data.get("name", "未命名任务")
        title_label = QLabel(f"{status_icon} {title}")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        header_layout.addWidget(title_label)
        header_layout.addStretch()

        # ID标签
        task_id = self.task_data.get("id", "")
        id_label = QLabel(f"ID: {task_id}")
        id_label.setStyleSheet("color: #666; font-size: 11px;")
        header_layout.addWidget(id_label)

        layout.addLayout(header_layout)

        # 调度信息
        schedule_type = self.task_data.get("schedule_type", "")
        if schedule_type == "once":
            scheduled_at = self.task_data.get("scheduled_at", "")
            if scheduled_at:
                try:
                    dt = datetime.fromisoformat(scheduled_at)
                    schedule_text = f"⏰ {dt.strftime('%Y-%m-%d %H:%M')}"
                except:
                    schedule_text = f"⏰ {scheduled_at}"
        else:
            rrule = self.task_data.get("rrule", "")
            executor = ScheduleCommandExecutor()
            schedule_text = f"🔄 {executor._describe_rrule(rrule)}"

        schedule_label = QLabel(schedule_text)
        schedule_label.setStyleSheet("color: #333; font-size: 12px;")
        layout.addWidget(schedule_label)

        # 描述
        prompt = self.task_data.get("prompt", "")
        if prompt:
            prompt_label = QLabel(f"📝 {prompt}")
            prompt_label.setStyleSheet("color: #555; font-size: 12px;")
            prompt_label.setWordWrap(True)
            layout.addWidget(prompt_label)

        # 执行时间信息
        next_run = self.task_data.get("next_run", "")
        last_run = self.task_data.get("last_run", "")
        if next_run:
            next_label = QLabel(f"📅 下次: {next_run}")
            next_label.setStyleSheet("color: #1976d2; font-size: 11px;")
            layout.addWidget(next_label)
        if last_run:
            last_label = QLabel(f"✓ 上次: {last_run}")
            last_label.setStyleSheet("color: #666; font-size: 11px;")
            layout.addWidget(last_label)

        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        delete_btn = QPushButton("🗑️ 删除")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffebee;
                border: 1px solid #f44336;
                border-radius: 4px;
                padding: 4px 12px;
                color: #c62828;
            }
            QPushButton:hover {
                background-color: #ffcdd2;
            }
        """)
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(task_id))
        btn_layout.addWidget(delete_btn)

        layout.addLayout(btn_layout)


class SchedulePanel(QWidget):
    """
    定时任务管理面板

    支持自然语言输入来创建、查询、删除定时任务
    """

    # 信号
    task_created = pyqtSignal(str)  # 任务创建信号
    task_deleted = pyqtSignal(str)   # 任务删除信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parser = NLPScheduleParser()
        self.executor = ScheduleCommandExecutor()
        self._setup_ui()
        self._refresh_tasks()

    def _setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 标题
        title_layout = QHBoxLayout()
        title = QLabel("⏰ 定时任务管理")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1976d2;")
        title_layout.addWidget(title)
        title_layout.addStretch()

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #e3f2fd;
                border: 1px solid #1976d2;
                border-radius: 4px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #bbdefb;
            }
        """)
        refresh_btn.clicked.connect(self._refresh_tasks)
        title_layout.addWidget(refresh_btn)

        main_layout.addLayout(title_layout)

        # 创建任务区域
        create_group = QGroupBox("✨ 自然语言创建任务")
        create_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #4caf50;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #faffff;
            }
        """)

        create_layout = QVBoxLayout(create_group)

        # 输入区域
        input_layout = QHBoxLayout()

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("例如：每天早上9点提醒我开会、明天下午3点做报告、每周一早上9点部门周会...")
        self.input_box.setStyleSheet("""
            QLineEdit {
                border: 2px solid #ddd;
                border-radius: 6px;
                padding: 10px;
                font-size: 14px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #4caf50;
            }
        """)
        self.input_box.returnPressed.connect(self._on_submit)
        input_layout.addWidget(self.input_box, 4)

        # 提交按钮
        self.submit_btn = QPushButton("🚀 创建")
        self.submit_btn.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.submit_btn.clicked.connect(self._on_submit)
        input_layout.addWidget(self.submit_btn, 1)

        create_layout.addLayout(input_layout)

        # 快捷指令提示
        tips_layout = QHBoxLayout()
        tips_label = QLabel("💡 快捷指令：")
        tips_label.setStyleSheet("color: #666; font-size: 12px;")

        tips = [
            ("每天X点", "每天早上9点提醒我"),
            ("每周X", "每周一早上9点开会"),
            ("明天下午", "明天下午3点做报告"),
            ("每隔", "每隔30分钟提醒喝水"),
        ]

        for tip_text, tip_example in tips:
            btn = QPushButton(tip_text)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #e8f5e9;
                    border: 1px solid #81c784;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 11px;
                    color: #2e7d32;
                }
                QPushButton:hover {
                    background-color: #c8e6c9;
                }
            """)
            btn.clicked.connect(lambda checked, t=tip_example: self._fill_example(t))
            tips_layout.addWidget(btn)

        tips_layout.addStretch()
        create_layout.addLayout(tips_layout)

        main_layout.addWidget(create_group)

        # 查询/管理区域
        manage_group = QGroupBox("📋 定时任务列表")
        manage_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #1976d2;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
        """)

        manage_layout = QVBoxLayout(manage_group)

        # 查询栏
        query_layout = QHBoxLayout()

        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("输入查询条件，如：查看所有任务、查看进行中的任务...")
        self.query_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #ddd;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #1976d2;
            }
        """)
        self.query_input.returnPressed.connect(self._on_query)
        query_layout.addWidget(self.query_input, 3)

        query_btn = QPushButton("🔍 查询")
        query_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
        """)
        query_btn.clicked.connect(self._on_query)
        query_layout.addWidget(query_btn, 1)

        manage_layout.addLayout(query_layout)

        # 任务列表（滚动区域）
        self.task_container = QScrollArea()
        self.task_container.setWidgetResizable(True)
        self.task_container.setStyleSheet("""
            QScrollArea {
                border: 1px solid #ddd;
                border-radius: 6px;
                background-color: white;
            }
        """)
        self.task_list_widget = QWidget()
        self.task_list_layout = QVBoxLayout(self.task_list_widget)
        self.task_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.task_list_layout.setSpacing(8)
        self.task_container.setWidget(self.task_list_widget)

        manage_layout.addWidget(self.task_container, 1)

        # 无任务提示
        self.empty_label = QLabel("📭 暂无定时任务\n\n您可以使用自然语言创建第一个定时任务")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("""
            color: #999;
            font-size: 14px;
            padding: 40px;
        """)
        manage_layout.addWidget(self.empty_label)

        main_layout.addWidget(manage_group, 1)

        # 状态栏
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #666; font-size: 12px;")
        main_layout.addWidget(self.status_label)

    def _fill_example(self, text: str):
        """填充示例文本"""
        self.input_box.setText(text)
        self.input_box.setFocus()

    def _on_submit(self):
        """提交创建任务"""
        text = self.input_box.text().strip()
        if not text:
            return

        self.submit_btn.setEnabled(False)
        self.status_label.setText("⏳ 正在解析和创建任务...")

        # 解析命令
        parsed = self.parser.parse(text)

        if parsed.command == CommandType.UNKNOWN:
            self.status_label.setText("❌ 无法理解您的意图")
            self.submit_btn.setEnabled(True)
            QMessageBox.warning(
                self,
                "无法理解",
                parsed.error_message or "请尝试更明确的表达，如：\n• 每天早上9点提醒我开会\n• 明天下午3点做报告\n• 每周一早上9点部门周会"
            )
            return

        if parsed.command not in [CommandType.CREATE]:
            self.status_label.setText("ℹ️ 请使用创建命令，如：'每天早上9点提醒我开会'")
            self.submit_btn.setEnabled(True)
            return

        # 执行创建
        result = self.executor.execute(text)

        if result.get("success"):
            task_id = result.get("task_id", "")
            self.status_label.setText(f"✅ 任务创建成功！ID: {task_id}")
            self.input_box.clear()

            # 显示成功消息
            QMessageBox.information(
                self,
                "创建成功",
                result.get("message", "定时任务已创建！")
            )

            # 刷新列表
            self._refresh_tasks()
        else:
            error = result.get("error", "未知错误")
            self.status_label.setText(f"❌ 创建失败: {error}")
            QMessageBox.critical(self, "创建失败", error)

        self.submit_btn.setEnabled(True)

    def _on_query(self):
        """查询任务"""
        text = self.query_input.text().strip()

        self.status_label.setText("🔍 正在查询...")

        if text:
            result = self.executor.execute(text)
        else:
            # 默认查询所有
            result = self.executor.execute("查看我的定时任务")

        if result.get("success"):
            self._display_tasks(result.get("tasks", []))
            self.status_label.setText(f"📋 共 {len(result.get('tasks', []))} 个任务")
        else:
            self.status_label.setText(f"❌ 查询失败: {result.get('error', '未知错误')}")

    def _refresh_tasks(self):
        """刷新任务列表"""
        result = self.executor.execute("查看我的定时任务")

        if result.get("success"):
            tasks = result.get("tasks", [])
            self._display_tasks(tasks)
            self.status_label.setText(f"📋 共 {len(tasks)} 个定时任务")
        else:
            self.status_label.setText(f"❌ 刷新失败")

    def _display_tasks(self, tasks: List[Dict[str, Any]]):
        """显示任务列表"""
        # 清除现有卡片
        while self.task_list_layout.count():
            item = self.task_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not tasks:
            self.empty_label.show()
            return

        self.empty_label.hide()

        for task_data in tasks:
            card = ScheduleCard(task_data)
            card.delete_requested.connect(self._on_delete_task)
            self.task_list_layout.addWidget(card)

    def _on_delete_task(self, task_id: str):
        """删除任务"""
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除任务 {task_id} 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            result = self.executor.execute(f"删除任务 {task_id}")

            if result.get("success"):
                self.status_label.setText(f"🗑️ 任务已删除")
                self._refresh_tasks()
            else:
                QMessageBox.critical(self, "删除失败", result.get("error", "未知错误"))

    def handle_natural_language(self, text: str) -> str:
        """
        处理自然语言输入（供外部调用）

        Args:
            text: 自然语言输入

        Returns:
            执行结果消息
        """
        # 解析命令
        parsed = self.parser.parse(text)

        if parsed.command == CommandType.UNKNOWN:
            return f"❌ {parsed.error_message or '无法理解您的意图'}"

        # 执行命令
        result = self.executor.execute(text)

        if result.get("success"):
            return result.get("message", "✅ 操作成功！")
        else:
            return f"❌ {result.get('error', '操作失败')}"


# 便捷函数：直接处理自然语言
def handle_schedule_command(text: str) -> str:
    """
    处理自然语言定时任务命令

    Examples:
        >>> result = handle_schedule_command("每天早上9点提醒我开会")
        >>> print(result)  # "✅ 定时任务创建成功！..."

        >>> result = handle_schedule_command("查看我的定时任务")
        >>> print(result)  # "📋 共找到 3 个定时任务：..."
    """
    executor = ScheduleCommandExecutor()
    result = executor.execute(text)

    if result.get("success"):
        return result.get("message", "✅ 操作成功！")
    else:
        return f"❌ {result.get('error', '操作失败')}"


if __name__ == "__main__":
    # 测试
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    window = SchedulePanel()
    window.setWindowTitle("定时任务管理测试")
    window.resize(800, 600)
    window.show()

    sys.exit(app.exec())