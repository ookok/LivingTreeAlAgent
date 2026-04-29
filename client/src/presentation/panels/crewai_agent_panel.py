"""
CrewAI Agent 管理面板
PyQt6 UI 界面，用于创建、配置和管理 CrewAI Agent
"""

import logging
from typing import Dict, Any, List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QGridLayout, QMessageBox, QTabWidget,
    QListWidget, QListWidgetItem, QTextEdit, QProgressBar,
    QPushButton, QComboBox, QFormLayout, QSpinBox,
    QDoubleSpinBox, QCheckBox, QLineEdit, QDialog,
    QDialogButtonBox, QVBoxLayout, QHBoxLayout,
    QMainWindow, QApplication
)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QColor, QFont

logger = logging.getLogger(__name__)


class AgentConfigDialog(QDialog):
    """
    Agent 配置对话框
    用于创建或编辑 CrewAI Agent
    """

    def __init__(self, parent=None, agent_data: Optional[Dict] = None):
        super().__init__(parent)
        self._agent_data = agent_data or {}
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        """构建UI"""
        self.setWindowTitle("配置 Agent")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 表单布局
        form_layout = QFormLayout()
        form_layout.setSpacing(8)

        # 名称
        self._name_edit = QLineEdit()
        form_layout.addRow("名称:", self._name_edit)

        # 角色
        self._role_edit = QLineEdit()
        self._role_edit.setPlaceholderText("例如: 研究员、分析师、作家")
        form_layout.addRow("角色:", self._role_edit)

        # 目标
        self._goal_edit = QLineEdit()
        self._goal_edit.setPlaceholderText("Agent 的主要目标")
        form_layout.addRow("目标:", self._goal_edit)

        # 背景故事
        self._backstory_edit = QTextEdit()
        self._backstory_edit.setMaximumHeight(100)
        self._backstory_edit.setPlaceholderText("Agent 的背景故事")
        form_layout.addRow("背景故事:", self._backstory_edit)

        # 温度
        self._temperature_spin = QDoubleSpinBox()
        self._temperature_spin.setRange(0.0, 1.0)
        self._temperature_spin.setValue(0.7)
        self._temperature_spin.setSingleStep(0.1)
        form_layout.addRow("温度:", self._temperature_spin)

        # 最大迭代次数
        self._max_iter_spin = QSpinBox()
        self._max_iter_spin.setRange(1, 100)
        self._max_iter_spin.setValue(5)
        form_layout.addRow("最大迭代:", self._max_iter_spin)

        # 工具列表（暂时用逗号分隔）
        self._tools_edit = QLineEdit()
        self._tools_edit.setPlaceholderText("工具名称，用逗号分隔")
        form_layout.addRow("工具:", self._tools_edit)

        # 允许委托
        self._allow_delegation_check = QCheckBox("允许委托")
        self._allow_delegation_check.setChecked(True)
        form_layout.addRow("", self._allow_delegation_check)

        # 详细模式
        self._verbose_check = QCheckBox("详细模式")
        self._verbose_check.setChecked(True)
        form_layout.addRow("", self._verbose_check)

        layout.addLayout(form_layout)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._cancel_button = QPushButton("取消")
        self._cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self._cancel_button)

        self._save_button = QPushButton("保存")
        self._save_button.clicked.connect(self.accept)
        self._save_button.setDefault(True)
        button_layout.addWidget(self._save_button)

        layout.addLayout(button_layout)

    def _load_data(self):
        """加载数据（编辑模式）"""
        if self._agent_data:
            self._name_edit.setText(self._agent_data.get("name", ""))
            self._role_edit.setText(self._agent_data.get("role", ""))
            self._goal_edit.setText(self._agent_data.get("goal", ""))
            self._backstory_edit.setText(self._agent_data.get("backstory", ""))
            self._temperature_spin.setValue(self._agent_data.get("temperature", 0.7))
            self._max_iter_spin.setValue(self._agent_data.get("max_iter", 5))
            self._tools_edit.setText(",".join(self._agent_data.get("tools", [])))
            self._allow_delegation_check.setChecked(self._agent_data.get("allow_delegation", True))
            self._verbose_check.setChecked(self._agent_data.get("verbose", True))

    def get_data(self) -> Dict[str, Any]:
        """获取数据"""
        tools_text = self._tools_edit.text().strip()
        tools = [t.strip() for t in tools_text.split(",")] if tools_text else []

        return {
            "name": self._name_edit.text(),
            "role": self._role_edit.text(),
            "goal": self._goal_edit.text(),
            "backstory": self._backstory_edit.toPlainText(),
            "temperature": self._temperature_spin.value(),
            "max_iter": self._max_iter_spin.value(),
            "tools": tools,
            "allow_delegation": self._allow_delegation_check.isChecked(),
            "verbose": self._verbose_check.isChecked()
        }


class CrewAIAgentPanel(QWidget):
    """
    CrewAI Agent 管理面板
    
    功能：
    1. Agent 列表
    2. 创建/编辑/删除 Agent
    3. 配置 Agent 角色、目标、工具
    4. 测试 Agent
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._crewai_adapter = None
        self._agents = {}
        self._init_ui()
        self._setup_timer()

    def _init_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 标题
        title = QLabel("🤖 CrewAI Agent 管理")
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

        # Agent 列表标签页
        self._list_tab = self._create_list_tab()
        self._tab_widget.addTab(self._list_tab, "📋 Agent 列表")

        # 创建/编辑 Agent 标签页
        self._edit_tab = self._create_edit_tab()
        self._tab_widget.addTab(self._edit_tab, "✏️ 创建/编辑")

        # 测试 Agent 标签页
        self._test_tab = self._create_test_tab()
        self._tab_widget.addTab(self._test_tab, "🧪 测试")

        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._refresh_button = QPushButton("🔄 刷新")
        self._refresh_button.clicked.connect(self._refresh)
        button_layout.addWidget(self._refresh_button)

        layout.addLayout(button_layout)

    def _create_list_tab(self) -> QWidget:
        """创建 Agent 列表标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # Agent 列表
        agents_group = QGroupBox("Agent 列表")
        agents_layout = QVBoxLayout(agents_group)

        self._agents_list = QListWidget()
        self._agents_list.itemClicked.connect(self._on_agent_selected)
        agents_layout.addWidget(self._agents_list)

        # 操作按钮
        button_layout = QHBoxLayout()

        self._edit_button = QPushButton("✏️ 编辑")
        self._edit_button.clicked.connect(self._edit_agent)
        button_layout.addWidget(self._edit_button)

        self._delete_button = QPushButton("🗑️ 删除")
        self._delete_button.clicked.connect(self._delete_agent)
        button_layout.addWidget(self._delete_button)

        button_layout.addStretch()
        agents_layout.addLayout(button_layout)

        layout.addWidget(agents_group)

        # Agent 详情
        details_group = QGroupBox("Agent 详情")
        details_layout = QVBoxLayout(details_group)

        self._agent_details = QTextEdit()
        self._agent_details.setReadOnly(True)
        self._agent_details.setMaximumHeight(200)
        details_layout.addWidget(self._agent_details)

        layout.addWidget(details_group)

        return widget

    def _create_edit_tab(self) -> QWidget:
        """创建/编辑 Agent 标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # 表单布局
        form_layout = QFormLayout()
        form_layout.setSpacing(8)

        # 名称
        self._name_edit = QLineEdit()
        form_layout.addRow("名称:", self._name_edit)

        # 角色
        self._role_edit = QLineEdit()
        self._role_edit.setPlaceholderText("例如: 研究员、分析师、作家")
        form_layout.addRow("角色:", self._role_edit)

        # 目标
        self._goal_edit = QLineEdit()
        self._goal_edit.setPlaceholderText("Agent 的主要目标")
        form_layout.addRow("目标:", self._goal_edit)

        # 背景故事
        self._backstory_edit = QTextEdit()
        self._backstory_edit.setMaximumHeight(100)
        self._backstory_edit.setPlaceholderText("Agent 的背景故事")
        form_layout.addRow("背景故事:", self._backstory_edit)

        # 温度
        self._temperature_spin = QDoubleSpinBox()
        self._temperature_spin.setRange(0.0, 1.0)
        self._temperature_spin.setValue(0.7)
        self._temperature_spin.setSingleStep(0.1)
        form_layout.addRow("温度:", self._temperature_spin)

        # 最大迭代次数
        self._max_iter_spin = QSpinBox()
        self._max_iter_spin.setRange(1, 100)
        self._max_iter_spin.setValue(5)
        form_layout.addRow("最大迭代:", self._max_iter_spin)

        # 工具列表（暂时用逗号分隔）
        self._tools_edit = QLineEdit()
        self._tools_edit.setPlaceholderText("工具名称，用逗号分隔")
        form_layout.addRow("工具:", self._tools_edit)

        # 允许委托
        self._allow_delegation_check = QCheckBox("允许委托")
        self._allow_delegation_check.setChecked(True)
        form_layout.addRow("", self._allow_delegation_check)

        # 详细模式
        self._verbose_check = QCheckBox("详细模式")
        self._verbose_check.setChecked(True)
        form_layout.addRow("", self._verbose_check)

        layout.addLayout(form_layout)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._clear_button = QPushButton("清空")
        self._clear_button.clicked.connect(self._clear_form)
        button_layout.addWidget(self._clear_button)

        self._save_button = QPushButton("保存")
        self._save_button.clicked.connect(self._save_agent)
        button_layout.addWidget(self._save_button)

        layout.addLayout(button_layout)

        return widget

    def _create_test_tab(self) -> QWidget:
        """创建测试 Agent 标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # Agent 选择
        select_group = QGroupBox("选择 Agent")
        select_layout = QFormLayout(select_group)

        self._test_agent_combo = QComboBox()
        select_layout.addRow("Agent:", self._test_agent_combo)

        layout.addWidget(select_group)

        # 测试输入
        input_group = QGroupBox("测试输入")
        input_layout = QVBoxLayout(input_group)

        self._test_input = QTextEdit()
        self._test_input.setPlaceholderText("输入测试提示...")
        self._test_input.setMaximumHeight(100)
        input_layout.addWidget(self._test_input)

        self._test_button = QPushButton("▶️ 运行测试")
        self._test_button.clicked.connect(self._run_test)
        input_layout.addWidget(self._test_button)

        layout.addWidget(input_group)

        # 测试结果
        result_group = QGroupBox("测试结果")
        result_layout = QVBoxLayout(result_group)

        self._test_output = QTextEdit()
        self._test_output.setReadOnly(True)
        result_layout.addWidget(self._test_output)

        layout.addWidget(result_group)

        return widget

    def _setup_timer(self):
        """设置定时器，定期刷新"""
        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh)
        self._timer.start(5000)  # 每 5 秒刷新一次

        # 立即刷新一次
        self._refresh()

    def _refresh(self):
        """刷新数据"""
        try:
            from client.src.business.multi_agent.crewai_adapter import CrewAIAgentAdapter
            
            # 获取或创建 CrewAI Adapter
            if self._crewai_adapter is None:
                try:
                    self._crewai_adapter = CrewAIAgentAdapter(verbose=True)
                    self._log("✅ CrewAI Adapter 初始化成功")
                except Exception as e:
                    self._log(f"❌ CrewAI Adapter 初始化失败: {e}")
                    return
            
            # 更新 Agent 列表
            self._update_agents_list()
            
            # 更新测试 Agent 下拉框
            self._update_test_agent_combo()
            
        except ImportError as e:
            self._log(f"❌ 导入失败: {e}")
        except Exception as e:
            self._log(f"❌ 错误: {e}")

    def _update_agents_list(self):
        """更新 Agent 列表"""
        try:
            self._agents_list.clear()
            
            # 这里应该从 CrewAI Adapter 获取 Agent 列表
            # 暂时使用模拟数据
            if not self._agents:
                # 模拟数据
                self._agents = {
                    "agent_1": {
                        "name": "研究员",
                        "role": "research",
                        "goal": "收集和分析市场数据",
                        "backstory": "你是一位经验丰富的研究员...",
                        "temperature": 0.7,
                        "max_iter": 5,
                        "tools": ["web_search", "data_analysis"],
                        "allow_delegation": True,
                        "verbose": True
                    },
                    "agent_2": {
                        "name": "分析师",
                        "role": "analysis",
                        "goal": "分析数据并生成报告",
                        "backstory": "你是一位专业的数据分析师...",
                        "temperature": 0.5,
                        "max_iter": 3,
                        "tools": ["data_visualization", "report_generation"],
                        "allow_delegation": False,
                        "verbose": True
                    }
                }
            
            for agent_id, agent_data in self._agents.items():
                item = QListWidgetItem()
                item.setText(f"{agent_data['name']} ({agent_data['role']})")
                item.setData(Qt.ItemDataRole.UserRole, agent_id)
                self._agents_list.addItem(item)
                
        except Exception as e:
            self._log(f"❌ 更新 Agent 列表失败: {e}")

    def _update_test_agent_combo(self):
        """更新测试 Agent 下拉框"""
        try:
            self._test_agent_combo.clear()
            
            for agent_id, agent_data in self._agents.items():
                self._test_agent_combo.addItem(agent_data['name'], agent_id)
                
        except Exception as e:
            self._log(f"❌ 更新测试 Agent 下拉框失败: {e}")

    def _on_agent_selected(self, item: QListWidgetItem):
        """Agent 选中事件"""
        try:
            agent_id = item.data(Qt.ItemDataRole.UserRole)
            agent_data = self._agents.get(agent_id)
            
            if agent_data:
                details = f"""
                <b>Agent ID:</b> {agent_id}<br>
                <b>名称:</b> {agent_data.get('name', '--')}<br>
                <b>角色:</b> {agent_data.get('role', '--')}<br>
                <b>目标:</b> {agent_data.get('goal', '--')}<br>
                <b>温度:</b> {agent_data.get('temperature', 0.7)}<br>
                <b>最大迭代:</b> {agent_data.get('max_iter', 5)}<br>
                <b>工具:</b> {', '.join(agent_data.get('tools', []))}<br>
                <b>允许委托:</b> {agent_data.get('allow_delegation', True)}<br>
                <b>详细模式:</b> {agent_data.get('verbose', True)}<br>
                """
                self._agent_details.setHtml(details)
                
        except Exception as e:
            self._log(f"❌ 显示 Agent 详情失败: {e}")

    def _edit_agent(self):
        """编辑 Agent"""
        try:
            current_item = self._agents_list.currentItem()
            if not current_item:
                QMessageBox.warning(self, "警告", "请先选择一个 Agent")
                return
            
            agent_id = current_item.data(Qt.ItemDataRole.UserRole)
            agent_data = self._agents.get(agent_id)
            
            if agent_data:
                # 打开配置对话框
                dialog = AgentConfigDialog(self, agent_data)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    # 更新 Agent 数据
                    new_data = dialog.get_data()
                    self._agents[agent_id] = new_data
                    self._log(f"✅ Agent '{new_data['name']}' 更新成功")
                    self._refresh()
                    
        except Exception as e:
            self._log(f"❌ 编辑 Agent 失败: {e}")
            QMessageBox.critical(self, "错误", f"编辑 Agent 失败: {e}")

    def _delete_agent(self):
        """删除 Agent"""
        try:
            current_item = self._agents_list.currentItem()
            if not current_item:
                QMessageBox.warning(self, "警告", "请先选择一个 Agent")
                return
            
            agent_id = current_item.data(Qt.ItemDataRole.UserRole)
            agent_data = self._agents.get(agent_id)
            
            if agent_data:
                # 确认删除
                reply = QMessageBox.question(
                    self, "确认删除",
                    f"确定要删除 Agent '{agent_data['name']}' 吗？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    del self._agents[agent_id]
                    self._log(f"✅ Agent '{agent_data['name']}' 删除成功")
                    self._refresh()
                    
        except Exception as e:
            self._log(f"❌ 删除 Agent 失败: {e}")
            QMessageBox.critical(self, "错误", f"删除 Agent 失败: {e}")

    def _clear_form(self):
        """清空表单"""
        self._name_edit.clear()
        self._role_edit.clear()
        self._goal_edit.clear()
        self._backstory_edit.clear()
        self._temperature_spin.setValue(0.7)
        self._max_iter_spin.setValue(5)
        self._tools_edit.clear()
        self._allow_delegation_check.setChecked(True)
        self._verbose_check.setChecked(True)

    def _save_agent(self):
        """保存 Agent"""
        try:
            # 获取表单数据
            name = self._name_edit.text().strip()
            if not name:
                QMessageBox.warning(self, "警告", "请输入 Agent 名称")
                return
            
            role = self._role_edit.text().strip()
            goal = self._goal_edit.text().strip()
            backstory = self._backstory_edit.toPlainText().strip()
            
            tools_text = self._tools_edit.text().strip()
            tools = [t.strip() for t in tools_text.split(",")] if tools_text else []
            
            agent_data = {
                "name": name,
                "role": role,
                "goal": goal,
                "backstory": backstory,
                "temperature": self._temperature_spin.value(),
                "max_iter": self._max_iter_spin.value(),
                "tools": tools,
                "allow_delegation": self._allow_delegation_check.isChecked(),
                "verbose": self._verbose_check.isChecked()
            }
            
            # 保存到 Agent 列表
            agent_id = f"agent_{len(self._agents) + 1}"
            self._agents[agent_id] = agent_data
            
            self._log(f"✅ Agent '{name}' 保存成功")
            self._clear_form()
            self._refresh()
            
        except Exception as e:
            self._log(f"❌ 保存 Agent 失败: {e}")
            QMessageBox.critical(self, "错误", f"保存 Agent 失败: {e}")

    def _run_test(self):
        """运行测试"""
        try:
            # 获取选中的 Agent
            agent_index = self._test_agent_combo.currentIndex()
            if agent_index < 0:
                QMessageBox.warning(self, "警告", "请先选择一个 Agent")
                return
            
            agent_id = self._test_agent_combo.itemData(agent_index)
            agent_data = self._agents.get(agent_id)
            
            if not agent_data:
                QMessageBox.warning(self, "警告", "Agent 数据不存在")
                return
            
            # 获取测试输入
            test_input = self._test_input.toPlainText().strip()
            if not test_input:
                QMessageBox.warning(self, "警告", "请输入测试提示")
                return
            
            # 这里应该调用 CrewAI Adapter 执行 Agent
            # 暂时使用模拟输出
            self._test_output.append(f"🧪 测试 Agent: {agent_data['name']}")
            self._test_output.append(f"📝 输入: {test_input}")
            self._test_output.append(f"✅ 输出: 这是模拟输出...")
            self._test_output.append("")
            
            self._log(f"✅ Agent '{agent_data['name']}' 测试完成")
            
        except Exception as e:
            self._log(f"❌ 测试失败: {e}")
            self._test_output.append(f"❌ 测试失败: {e}")
            QMessageBox.critical(self, "错误", f"测试失败: {e}")

    def _log(self, message: str):
        """添加日志"""
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] CrewAIAgentPanel: {message}")
        except Exception:
            pass

    def closeEvent(self, event):
        """关闭事件"""
        if hasattr(self, '_timer'):
            self._timer.stop()
        super().closeEvent(event)
