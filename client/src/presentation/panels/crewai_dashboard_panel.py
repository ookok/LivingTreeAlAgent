"""
CrewAI Dashboard 面板
PyQt6 UI 界面，用于监控和管理 CrewAI 多智能体系统
"""

import logging
from typing import Dict, Any, List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QGridLayout, QMessageBox, QTabWidget,
    QListWidget, QListWidgetItem, QTextEdit, QProgressBar,
    QPushButton, QComboBox, QFormLayout, QSpinBox,
    QDoubleSpinBox, QCheckBox, QLineEdit
)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QColor, QFont

logger = logging.getLogger(__name__)


class CrewAIDashboardPanel(QWidget):
    """
    CrewAI Dashboard 面板
    
    功能：
    1. 智能体列表和状态监控
    2. 任务执行进度
    3. 协作关系可视化
    4. 日志输出窗口
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._crewai_adapter = None
        self._agents = {}
        self._tasks = {}
        self._init_ui()
        self._setup_timer()

    def _init_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 标题
        title = QLabel("🤖 CrewAI Dashboard")
        title.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #333333;
            padding-bottom: 8px;
        """)
        layout.addWidget(title)

        # 创建标签页
        self._tab_widget = QTabWidget()
        layout.addWidget(self._tab_widget)

        # 概览标签页
        self._overview_tab = self._create_overview_tab()
        self._tab_widget.addTab(self._overview_tab, "📊 概览")

        # 智能体标签页
        self._agents_tab = self._create_agents_tab()
        self._tab_widget.addTab(self._agents_tab, "🤖 智能体")

        # 任务标签页
        self._tasks_tab = self._create_tasks_tab()
        self._tab_widget.addTab(self._tasks_tab, "📋 任务")

        # 日志标签页
        self._logs_tab = self._create_logs_tab()
        self._tab_widget.addTab(self._logs_tab, "📝 日志")

        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._refresh_button = QPushButton("🔄 刷新")
        self._refresh_button.clicked.connect(self._refresh)
        button_layout.addWidget(self._refresh_button)

        self._start_button = QPushButton("▶️ 启动")
        self._start_button.clicked.connect(self._start_crew)
        button_layout.addWidget(self._start_button)

        self._stop_button = QPushButton("⏹️ 停止")
        self._stop_button.clicked.connect(self._stop_crew)
        button_layout.addWidget(self._stop_button)

        layout.addLayout(button_layout)

    def _create_overview_tab(self) -> QWidget:
        """创建概览标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # 统计信息
        stats_group = QGroupBox("统计信息")
        stats_layout = QGridLayout(stats_group)

        self._total_agents_label = QLabel("智能体总数: 0")
        stats_layout.addWidget(self._total_agents_label, 0, 0)

        self._active_agents_label = QLabel("活跃智能体: 0")
        stats_layout.addWidget(self._active_agents_label, 0, 1)

        self._total_tasks_label = QLabel("任务总数: 0")
        stats_layout.addWidget(self._total_tasks_label, 1, 0)

        self._running_tasks_label = QLabel("运行中任务: 0")
        stats_layout.addWidget(self._running_tasks_label, 1, 1)

        layout.addWidget(stats_group)

        # CrewAI 状态
        status_group = QGroupBox("CrewAI 状态")
        status_layout = QVBoxLayout(status_group)

        self._status_label = QLabel("状态: 未初始化")
        self._status_label.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(self._status_label)

        self._config_label = QLabel("配置: --")
        status_layout.addWidget(self._config_label)

        layout.addWidget(status_group)

        layout.addStretch()
        return widget

    def _create_agents_tab(self) -> QWidget:
        """创建智能体标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # 智能体列表
        agents_group = QGroupBox("智能体列表")
        agents_layout = QVBoxLayout(agents_group)

        self._agents_list = QListWidget()
        self._agents_list.itemClicked.connect(self._on_agent_selected)
        agents_layout.addWidget(self._agents_list)

        # 智能体详情
        self._agent_details = QTextEdit()
        self._agent_details.setReadOnly(True)
        self._agent_details.setMaximumHeight(200)
        agents_layout.addWidget(self._agent_details)

        layout.addWidget(agents_group)

        return widget

    def _create_tasks_tab(self) -> QWidget:
        """创建任务标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # 任务列表
        tasks_group = QGroupBox("任务列表")
        tasks_layout = QVBoxLayout(tasks_group)

        self._tasks_list = QListWidget()
        self._tasks_list.itemClicked.connect(self._on_task_selected)
        tasks_layout.addWidget(self._tasks_list)

        # 任务进度
        self._task_progress = QProgressBar()
        self._task_progress.setRange(0, 100)
        self._task_progress.setValue(0)
        tasks_layout.addWidget(self._task_progress)

        # 任务详情
        self._task_details = QTextEdit()
        self._task_details.setReadOnly(True)
        self._task_details.setMaximumHeight(200)
        tasks_layout.addWidget(self._task_details)

        layout.addWidget(tasks_group)

        return widget

    def _create_logs_tab(self) -> QWidget:
        """创建日志标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # 日志输出
        logs_group = QGroupBox("日志输出")
        logs_layout = QVBoxLayout(logs_group)

        self._logs_text = QTextEdit()
        self._logs_text.setReadOnly(True)
        self._logs_text.setFont(QFont("Courier", 10))
        logs_layout.addWidget(self._logs_text)

        # 清空按钮
        clear_button = QPushButton("清空日志")
        clear_button.clicked.connect(self._clear_logs)
        logs_layout.addWidget(clear_button)

        layout.addWidget(logs_group)

        return widget

    def _setup_timer(self):
        """设置定时器，定期刷新"""
        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh)
        self._timer.start(5000)  # 每 5 秒刷新一次

        # 立即刷新一次
        self._refresh()

    def _refresh(self):
        """刷新监控数据"""
        try:
            from client.src.business.multi_agent.crewai_adapter import CrewAIAgentAdapter
            
            # 获取或创建 CrewAI Adapter
            if self._crewai_adapter is None:
                try:
                    self._crewai_adapter = CrewAIAgentAdapter(verbose=True)
                    self._log("✅ CrewAI Adapter 初始化成功")
                except Exception as e:
                    self._status_label.setText(f"状态: 初始化失败 - {e}")
                    return
            
            # 更新状态
            self._status_label.setText("状态: 已初始化")
            
            # 更新统计信息
            self._update_stats()
            
            # 更新智能体列表
            self._update_agents_list()
            
            # 更新任务列表
            self._update_tasks_list()
            
        except ImportError as e:
            self._status_label.setText(f"状态: 导入失败 - {e}")
            self._log(f"❌ 导入失败: {e}")
        except Exception as e:
            self._status_label.setText(f"状态: 错误 - {e}")
            self._log(f"❌ 错误: {e}")

    def _update_stats(self):
        """更新统计信息"""
        try:
            # 统计智能体
            total_agents = len(self._agents)
            active_agents = sum(1 for agent in self._agents.values() if agent.get("status") == "active")
            
            self._total_agents_label.setText(f"智能体总数: {total_agents}")
            self._active_agents_label.setText(f"活跃智能体: {active_agents}")
            
            # 统计任务
            total_tasks = len(self._tasks)
            running_tasks = sum(1 for task in self._tasks.values() if task.get("status") == "running")
            
            self._total_tasks_label.setText(f"任务总数: {total_tasks}")
            self._running_tasks_label.setText(f"运行中任务: {running_tasks}")
            
        except Exception as e:
            self._log(f"❌ 更新统计失败: {e}")

    def _update_agents_list(self):
        """更新智能体列表"""
        try:
            self._agents_list.clear()
            
            # 这里应该从 CrewAI Adapter 获取智能体列表
            # 暂时使用模拟数据
            if not self._agents:
                # 模拟数据
                self._agents = {
                    "agent_1": {
                        "name": "研究员",
                        "role": "research",
                        "status": "active",
                        "tasks_completed": 5
                    },
                    "agent_2": {
                        "name": "分析师",
                        "role": "analysis",
                        "status": "idle",
                        "tasks_completed": 3
                    }
                }
            
            for agent_id, agent_data in self._agents.items():
                item = QListWidgetItem()
                item.setText(f"{agent_data['name']} ({agent_data['role']}) - {agent_data['status']}")
                item.setData(Qt.ItemDataRole.UserRole, agent_id)
                self._agents_list.addItem(item)
                
        except Exception as e:
            self._log(f"❌ 更新智能体列表失败: {e}")

    def _update_tasks_list(self):
        """更新任务列表"""
        try:
            self._tasks_list.clear()
            
            # 这里应该从 CrewAI Adapter 获取任务列表
            # 暂时使用模拟数据
            if not self._tasks:
                # 模拟数据
                self._tasks = {
                    "task_1": {
                        "description": "研究市场趋势",
                        "status": "completed",
                        "progress": 100
                    },
                    "task_2": {
                        "description": "分析竞争对手",
                        "status": "running",
                        "progress": 60
                    }
                }
            
            for task_id, task_data in self._tasks.items():
                item = QListWidgetItem()
                item.setText(f"{task_data['description']} - {task_data['status']} ({task_data['progress']}%)")
                item.setData(Qt.ItemDataRole.UserRole, task_id)
                self._tasks_list.addItem(item)
                
        except Exception as e:
            self._log(f"❌ 更新任务列表失败: {e}")

    def _on_agent_selected(self, item: QListWidgetItem):
        """智能体选中事件"""
        try:
            agent_id = item.data(Qt.ItemDataRole.UserRole)
            agent_data = self._agents.get(agent_id)
            
            if agent_data:
                details = f"""
                <b>智能体 ID:</b> {agent_id}<br>
                <b>名称:</b> {agent_data.get('name', '--')}<br>
                <b>角色:</b> {agent_data.get('role', '--')}<br>
                <b>状态:</b> {agent_data.get('status', '--')}<br>
                <b>完成任务:</b> {agent_data.get('tasks_completed', 0)}<br>
                """
                self._agent_details.setHtml(details)
                
        except Exception as e:
            self._log(f"❌ 显示智能体详情失败: {e}")

    def _on_task_selected(self, item: QListWidgetItem):
        """任务选中事件"""
        try:
            task_id = item.data(Qt.ItemDataRole.UserRole)
            task_data = self._tasks.get(task_id)
            
            if task_data:
                details = f"""
                <b>任务 ID:</b> {task_id}<br>
                <b>描述:</b> {task_data.get('description', '--')}<br>
                <b>状态:</b> {task_data.get('status', '--')}<br>
                <b>进度:</b> {task_data.get('progress', 0)}%<br>
                """
                self._task_details.setHtml(details)
                self._task_progress.setValue(task_data.get('progress', 0))
                
        except Exception as e:
            self._log(f"❌ 显示任务详情失败: {e}")

    def _start_crew(self):
        """启动 CrewAI"""
        try:
            self._log("▶️ 启动 CrewAI...")
            # TODO: 实现启动逻辑
            QMessageBox.information(self, "启动", "CrewAI 启动功能待实现")
        except Exception as e:
            self._log(f"❌ 启动失败: {e}")
            QMessageBox.critical(self, "错误", f"启动失败: {e}")

    def _stop_crew(self):
        """停止 CrewAI"""
        try:
            self._log("⏹️ 停止 CrewAI...")
            # TODO: 实现停止逻辑
            QMessageBox.information(self, "停止", "CrewAI 停止功能待实现")
        except Exception as e:
            self._log(f"❌ 停止失败: {e}")
            QMessageBox.critical(self, "错误", f"停止失败: {e}")

    def _clear_logs(self):
        """清空日志"""
        self._logs_text.clear()

    def _log(self, message: str):
        """添加日志"""
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            self._logs_text.append(f"[{timestamp}] {message}")
        except Exception:
            pass

    def closeEvent(self, event):
        """关闭事件"""
        if hasattr(self, '_timer'):
            self._timer.stop()
        super().closeEvent(event)
