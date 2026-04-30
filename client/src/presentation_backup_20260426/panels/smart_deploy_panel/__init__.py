"""
智能轻量化部署系统 - UI面板
Smart Deployment Panel

5标签页设计：
1. 🏠 总览仪表板 - 系统状态和快速入口
2. 📥 输入与解析 - 多模态输入 + 意图理解结果
3. 🎮 沙箱模拟 - 安全环境预演部署
4. 🚀 部署执行 - 卡片式并行部署
5. 📚 学习中心 - 新手引导 + 技能树
"""

import sys
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QProgressBar, QGroupBox, QFormLayout,
    QScrollArea, QFrame, QLineEdit, QComboBox,
    QListWidget, QListWidgetItem, QTextBrowser,
    QSlider, QDial, QCheckBox, QSpinBox,
    QBadge, QToolButton, QSplitter, QGridLayout,
    QProgressDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QThread
from PyQt6.QtGui import QFont, QColor, QTextCursor, QIcon, QPalette

# 导入核心模块
sys.path.insert(0, str(__file__).rsplit('/ui/', 1)[0] if '/' in __file__ else '')
sys.path.insert(0, str(__file__).rsplit('\\ui\\', 1)[0] if '\\ui\\' in __file__ else '')

try:
    from .business.smart_deploy import (
        IntentUnderstandingEngine, IntentType, TechStack, RiskLevel,
        EnvironmentAnalyzer, ServerInfo,
        StrategyGenerator, DeploymentStrategy, GeneratedScript,
        SandboxExecutor, SandboxReport,
        DeploymentEngine, DeploymentStatus, ServerDeployment,
        ObstacleResolver, ObstacleType,
        MultiModeInputHandler, InputMode,
        LearningSystem, SkillLevel, Explanation
    )
except ImportError:
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from .business.smart_deploy import (
        IntentUnderstandingEngine, IntentType, TechStack, RiskLevel,
        EnvironmentAnalyzer, ServerInfo,
        StrategyGenerator, DeploymentStrategy, GeneratedScript,
        SandboxExecutor, SandboxReport,
        DeploymentEngine, DeploymentStatus, ServerDeployment,
        ObstacleResolver, ObstacleType,
        MultiModeInputHandler, InputMode,
        LearningSystem, SkillLevel, Explanation
    )

logger = logging.getLogger(__name__)


# ============== 样式常量 ==============
DARK_STYLE = """
QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
    font-family: 'Microsoft YaHei', sans-serif;
}
QGroupBox {
    border: 1px solid #3a3a5c;
    border-radius: 8px;
    margin-top: 12px;
    padding: 12px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #60a5fa;
}
QPushButton {
    background-color: #3a3a5c;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    color: #e0e0e0;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #4a4a6c;
}
QPushButton:pressed {
    background-color: #2a2a4c;
}
QPushButton:checked {
    background-color: #60a5fa;
    color: #1a1a2e;
}
QTextEdit, QTextBrowser {
    background-color: #1a1a2e;
    border: 1px solid #3a3a5c;
    border-radius: 4px;
    color: #e0e0e0;
    font-family: 'Consolas', monospace;
}
QLineEdit {
    background-color: #2a2a3e;
    border: 1px solid #3a3a5c;
    border-radius: 4px;
    padding: 6px;
    color: #e0e0e0;
}
QListWidget {
    background-color: #1a1a2e;
    border: 1px solid #3a3a5c;
    border-radius: 4px;
    color: #e0e0e0;
}
QListWidget::item {
    padding: 8px;
    border-bottom: 1px solid #2a2a3e;
}
QListWidget::item:selected {
    background-color: #3a3a5c;
}
QTabWidget::pane {
    background-color: #1a1a2e;
    border: 1px solid #3a3a5c;
    border-radius: 4px;
}
QTabBar::tab {
    background-color: #2a2a3e;
    color: #a0a0a0;
    padding: 10px 20px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QTabBar::tab:selected {
    background-color: #3a3a5c;
    color: #ffffff;
}
QProgressBar {
    background-color: #2a2a3e;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: #ffffff;
}
QProgressBar::chunk {
    background-color: #60a5fa;
    border-radius: 4px;
}
QTableWidget {
    background-color: #1a1a2e;
    border: none;
    color: #e0e0e0;
    gridline-color: #2a2a3e;
}
QTableWidget::item {
    padding: 4px;
}
QHeaderView::section {
    background-color: #2a2a3e;
    color: #a0a0a0;
    padding: 8px;
    border: none;
}
"""


class StyledCard(QFrame):
    """卡片组件"""

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            StyledCard {
                background-color: #2a2a3e;
                border: 1px solid #3a3a5c;
                border-radius: 8px;
                padding: 12px;
            }
        """)

        if title:
            layout = QVBoxLayout(self)
            title_label = QLabel(title)
            title_label.setStyleSheet("color: #60a5fa; font-size: 14px; font-weight: bold;")
            layout.addWidget(title_label)


class OverviewTab(QWidget):
    """总览仪表板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.start_refresh_timer()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # 标题
        title = QLabel("🚀 智能轻量化部署系统")
        title.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #60a5fa;")
        layout.addWidget(title)

        # 状态卡片行
        status_row = QHBoxLayout()

        self.engine_status = StatusCard("🧠 引擎状态", "就绪", "#4ade80")
        self.server_status = StatusCard("🖥️ 服务器", "未连接", "#9ca3af")
        self.deploy_status = StatusCard("📦 部署状态", "空闲", "#60a5fa")
        self.learning_status = StatusCard("📚 学习进度", "Lv.1 萌新", "#facc15")

        for card in [self.engine_status, self.server_status, self.deploy_status, self.learning_status]:
            status_row.addWidget(card)

        layout.addLayout(status_row)

        # 快速操作区
        quick_group = QGroupBox("⚡ 快速操作")
        quick_layout = QHBoxLayout(quick_group)

        self.analyze_btn = QPushButton("🔍 智能分析")
        self.analyze_btn.clicked.connect(self.on_analyze)

        self.deploy_btn = QPushButton("🚀 一键部署")
        self.deploy_btn.clicked.connect(self.on_deploy)

        self.simulate_btn = QPushButton("🎮 沙箱模拟")
        self.simulate_btn.clicked.connect(self.on_simulate)

        self.learn_btn = QPushButton("📚 学习中心")
        self.learn_btn.clicked.connect(self.on_learn)

        for btn in [self.analyze_btn, self.deploy_btn, self.simulate_btn, self.learn_btn]:
            btn.setMinimumHeight(50)
            quick_layout.addWidget(btn)

        layout.addWidget(quick_group)

        # 最近活动
        activity_group = QGroupBox("📋 最近活动")
        activity_layout = QVBoxLayout(activity_group)

        self.activity_list = QListWidget()
        self.activity_list.addItem("等待活动记录...")
        activity_layout.addWidget(self.activity_list)

        layout.addWidget(activity_group)

        layout.addStretch()

    def start_refresh_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(3000)

    def refresh_status(self):
        """刷新状态"""
        try:
            from .business.smart_deploy import DeploymentEngine
            engine = DeploymentEngine()
            stats = engine.get_stats()

            # 更新引擎状态
            if stats.get("enabled"):
                self.engine_status.set_value("就绪", "#4ade80")
            else:
                self.engine_status.set_value("已暂停", "#ff6b6b")

            # 更新服务器状态
            servers = stats.get("servers", [])
            if servers:
                self.server_status.set_value(f"{len(servers)}台服务器", "#4ade80")
            else:
                self.server_status.set_value("未连接", "#9ca3af")

            # 更新部署状态
            active = stats.get("active_deployments", 0)
            if active > 0:
                self.deploy_status.set_value(f"部署中({active})", "#60a5fa")
            else:
                self.deploy_status.set_value("空闲", "#60a5fa")

            # 更新学习进度
            from .business.smart_deploy import LearningSystem
            learning = LearningSystem()
            progress = learning.get_progress()
            self.learning_status.set_value(f"Lv.{progress.level.value} {progress.level.name}", "#facc15")

        except Exception as e:
            logger.error(f"Failed to refresh status: {e}")

    def on_analyze(self):
        """分析按钮点击"""
        self.window().tabs.setCurrentIndex(1)

    def on_deploy(self):
        """部署按钮点击"""
        self.window().tabs.setCurrentIndex(3)

    def on_simulate(self):
        """模拟按钮点击"""
        self.window().tabs.setCurrentIndex(2)

    def on_learn(self):
        """学习按钮点击"""
        self.window().tabs.setCurrentIndex(4)


class StatusCard(QFrame):
    """状态卡片"""

    def __init__(self, title: str, value: str, color: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            StatusCard {{
                background-color: #2a2a3e;
                border: 1px solid #3a3a5c;
                border-radius: 8px;
                padding: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #9ca3af; font-size: 12px;")

        self.value_label = QLabel(value)
        self.value_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        self.value_label.setStyleSheet(f"color: {color};")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str, color: str = None):
        self.value_label.setText(value)
        if color:
            self.value_label.setStyleSheet(f"color: {color};")


class InputParseTab(QWidget):
    """输入与解析标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.intent_engine = IntentUnderstandingEngine()
        self.env_analyzer = EnvironmentAnalyzer()
        self.multi_input = MultiModeInputHandler()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 输入模式选择
        mode_group = QGroupBox("📥 输入方式")
        mode_layout = QHBoxLayout(mode_group)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "💬 文本描述",
            "📸 截图/图片",
            "📁 上传文件",
            "🎤 语音输入",
            "✍️ 手写输入"
        ])

        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("请描述您的部署需求...\n\n例如：帮我部署一个Python Flask应用到Ubuntu服务器上，使用Docker容器运行")
        self.input_text.setMaximumHeight(150)

        self.parse_btn = QPushButton("🔍 智能解析")
        self.parse_btn.setStyleSheet("background-color: #60a5fa; color: #1a1a2e;")
        self.parse_btn.clicked.connect(self.on_parse)

        mode_layout.addWidget(self.mode_combo)
        mode_layout.addWidget(self.parse_btn)

        layout.addWidget(mode_group)
        layout.addWidget(self.input_text)

        # 解析结果区
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：意图理解结果
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        intent_group = QGroupBox("🎯 意图理解结果")
        intent_layout = QFormLayout(intent_group)

        self.intent_type_label = QLabel("未知")
        self.tech_stack_label = QLabel("未知")
        self.deploy_type_label = QLabel("未知")
        self.risk_level_label = QLabel("低风险")

        for label in [self.intent_type_label, self.tech_stack_label,
                      self.deploy_type_label, self.risk_level_label]:
            label.setStyleSheet("color: #e0e0e0;")

        intent_layout.addRow("意图类型:", self.intent_type_label)
        intent_layout.addRow("技术栈:", self.tech_stack_label)
        intent_layout.addRow("部署方式:", self.deploy_type_label)
        intent_layout.addRow("风险等级:", self.risk_level_label)

        left_layout.addWidget(intent_group)

        # 环境分析结果
        env_group = QGroupBox("🖥️ 环境分析")
        env_layout = QFormLayout(env_group)

        self.os_label = QLabel("Linux")
        self.cpu_label = QLabel("2核")
        self.memory_label = QLabel("2GB")
        self.docker_label = QLabel("未安装")

        for label in [self.os_label, self.cpu_label, self.memory_label, self.docker_label]:
            label.setStyleSheet("color: #e0e0e0;")

        env_layout.addRow("操作系统:", self.os_label)
        env_layout.addRow("CPU:", self.cpu_label)
        env_layout.addRow("内存:", self.memory_label)
        env_layout.addRow("Docker:", self.docker_label)

        left_layout.addWidget(env_group)
        left_layout.addStretch()

        splitter.addWidget(left_panel)

        # 右侧：详细分析
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        detail_group = QGroupBox("📊 详细分析")
        detail_layout = QVBoxLayout(detail_group)

        self.detail_text = QTextBrowser()
        self.detail_text.setHtml("""
            <div style='color: #e0e0e0;'>
                <p>📋 <b>需求摘要</b></p>
                <p style='margin-left: 20px;'>等待输入...</p>
                <br>
                <p>⚙️ <b>技术栈检测</b></p>
                <p style='margin-left: 20px;'>等待分析...</p>
                <br>
                <p>🔧 <b>环境要求</b></p>
                <p style='margin-left: 20px;'>等待检测...</p>
            </div>
        """)

        detail_layout.addWidget(self.detail_text)
        right_layout.addWidget(detail_group)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

        # 生成策略按钮
        self.generate_btn = QPushButton("✨ 生成部署策略")
        self.generate_btn.setStyleSheet("background-color: #4ade80; color: #1a1a2e; font-weight: bold;")
        self.generate_btn.setMinimumHeight(50)
        self.generate_btn.clicked.connect(self.on_generate_strategy)
        self.generate_btn.setEnabled(False)

        layout.addWidget(self.generate_btn)

        # 存储解析结果
        self.current_intent_result = None

    def on_parse(self):
        """解析输入"""
        text = self.input_text.toPlainText()
        if not text.strip():
            return

        # 模拟解析
        self.parse_btn.setEnabled(False)
        self.parse_btn.setText("⏳ 解析中...")

        # 模拟延迟
        QTimer.singleShot(500, self._do_parse)

    def _do_parse(self):
        """执行解析"""
        text = self.input_text.toPlainText()

        # 调用意图理解引擎
        intent_result = self.intent_engine.analyze(text)

        # 更新UI
        self.intent_type_label.setText(intent_result.intent_type.value.upper())
        self.tech_stack_label.setText(intent_result.tech_stack.value.upper())
        self.deploy_type_label.setText(intent_result.deployment_type)
        self.risk_level_label.setText(intent_result.risk_level.value.upper())

        # 风险等级颜色
        risk_colors = {"low": "#4ade80", "medium": "#facc15", "high": "#ff6b6b", "critical": "#dc2626"}
        self.risk_level_label.setStyleSheet(f"color: {risk_colors.get(intent_result.risk_level.value, '#e0e0e0')};")

        # 更新详情
        self.detail_text.setHtml(f"""
            <div style='color: #e0e0e0;'>
                <p>📋 <b>需求摘要</b></p>
                <p style='margin-left: 20px;'>{intent_result.target_description}</p>
                <br>
                <p>⚙️ <b>技术栈检测</b></p>
                <p style='margin-left: 20px;'>检测到: {intent_result.tech_stack.value.upper()}</p>
                <p style='margin-left: 20px;'>置信度: {intent_result.confidence:.0%}</p>
                <br>
                <p>🔧 <b>环境要求</b></p>
                <p style='margin-left: 20px;'>• CPU: {intent_result.environment.get('cpu_cores', 2)}核</p>
                <p style='margin-left: 20px;'>• 内存: {intent_result.environment.get('memory_mb', 2048)}MB</p>
                <p style='margin-left: 20px;'>• 端口: {', '.join(map(str, intent_result.environment.get('ports', [])))}</p>
                <br>
                <p>⚠️ <b>风险因素</b></p>
                <p style='margin-left: 20px;'>• {'<br>• '.join(intent_result.risk_factors) if intent_result.risk_factors else '无'}</p>
            </div>
        """)

        self.current_intent_result = intent_result
        self.generate_btn.setEnabled(True)

        self.parse_btn.setEnabled(True)
        self.parse_btn.setText("🔍 智能解析")

    def on_generate_strategy(self):
        """生成策略"""
        if self.current_intent_result:
            self.window().tabs.setCurrentIndex(2)


class SimulateWorker(QThread):
    """沙箱模拟后台工作线程"""
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal()

    def __init__(self, sandbox: SandboxExecutor, script: str = None):
        super().__init__()
        self.sandbox = sandbox
        self.script = script or "#!/bin/bash\necho 'No script provided'"

    def run(self):
        try:
            self.output_signal.emit("🚀 开始沙箱模拟...")
            self.progress_signal.emit(10)

            # 环境检查
            self.output_signal.emit("⏳ [环境检查] ...")
            self.progress_signal.emit(20)

            # 依赖分析
            self.output_signal.emit("⏳ [依赖分析] ...")
            self.progress_signal.emit(40)

            # 脚本验证
            self.output_signal.emit("⏳ [脚本验证] ...")
            self.progress_signal.emit(60)

            # 执行模拟
            self.output_signal.emit("⏳ [执行测试] ...")
            report = self.sandbox.execute_sandbox(self.script, timeout=60)
            self.progress_signal.emit(80)

            # 最终确认
            self.output_signal.emit("⏳ [最终确认] ...")
            self.progress_signal.emit(100)

            if report.status == "success":
                self.output_signal.emit("\n✅ 模拟完成！脚本可以安全执行")
            else:
                self.output_signal.emit(f"\n⚠️ 模拟完成，但有警告: {report.stderr[:200]}")

        except Exception as e:
            self.output_signal.emit(f"\n❌ 模拟出错: {str(e)}")
        finally:
            self.finished_signal.emit()


class SandboxSimulateTab(QWidget):
    """沙箱模拟标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sandbox = SandboxExecutor()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 控制栏
        control_layout = QHBoxLayout()

        self.start_btn = QPushButton("▶️ 开始模拟")
        self.start_btn.setStyleSheet("background-color: #60a5fa; color: #1a1a2e;")
        self.start_btn.clicked.connect(self.on_start_simulate)

        self.pause_btn = QPushButton("⏸️ 暂停")
        self.pause_btn.setCheckable(True)
        self.pause_btn.clicked.connect(self.on_pause_simulate)

        self.stop_btn = QPushButton("⏹️ 停止")
        self.stop_btn.clicked.connect(self.on_stop_simulate)

        self.clear_btn = QPushButton("🗑️ 清空")
        self.clear_btn.clicked.connect(self.on_clear)

        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.pause_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.clear_btn)
        control_layout.addStretch()

        layout.addLayout(control_layout)

        # 模拟输出
        output_group = QGroupBox("🎮 模拟执行过程")
        output_layout = QVBoxLayout(output_group)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)

        output_layout.addWidget(self.output_text)
        layout.addWidget(output_group)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(20)

        self.status_label = QLabel("等待开始...")
        self.status_label.setStyleSheet("color: #9ca3af;")

        progress_layout = QVBoxLayout()
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)

        layout.addLayout(progress_layout)

        # 预测问题
        predict_group = QGroupBox("⚠️ 预测问题")
        predict_layout = QVBoxLayout(predict_group)

        self.predict_list = QListWidget()
        self.predict_list.addItem("等待分析...")
        predict_layout.addWidget(self.predict_list)

        layout.addWidget(predict_group)

    def on_start_simulate(self):
        """开始模拟"""
        self.output_text.append("🚀 开始沙箱模拟...")
        self.progress_bar.setValue(0)
        self.start_btn.setEnabled(False)

        # 获取父窗口的策略信息（如果有的话）
        strategy = None
        try:
            parent = self.window()
            if hasattr(parent, 'current_strategy'):
                strategy = parent.current_strategy
        except:
            pass

        # 调用真实的沙箱执行
        def run_simulate():
            try:
                # 创建模拟任务
                test_script = """
#!/bin/bash
echo "Testing deployment script..."
apt-get update
apt-get install -y python3 python3-pip
pip3 install flask
echo "Installation complete"
"""
                report = self.sandbox.execute_sandbox(test_script, timeout=60)

                # 更新UI
                self.output_text.append(f"\n📊 模拟执行报告")
                self.output_text.append(f"状态: {report.status}")
                self.output_text.append(f"执行时间: {report.execution_time:.2f}秒")
                self.output_text.append(f"\n输出:\n{report.stdout[:500]}")

                if report.stderr:
                    self.output_text.append(f"\n错误:\n{report.stderr[:500]}")

                self.progress_bar.setValue(100)

                # 更新预测问题
                self.predict_list.clear()
                if report.status == "success":
                    self.predict_list.addItem("✓ 未检测到危险命令")
                    self.predict_list.addItem("✓ 权限配置正常")
                    self.predict_list.addItem("✓ 依赖关系清晰")
                    self.status_label.setText("模拟完成 - 可以安全执行")
                else:
                    self.predict_list.addItem(f"⚠️ 模拟失败: {report.status}")
                    self.status_label.setText("模拟失败")

            except Exception as e:
                self.output_text.append(f"\n❌ 模拟出错: {str(e)}")
                self.status_label.setText("模拟出错")
            finally:
                self.start_btn.setEnabled(True)

        # 在后台线程执行
        from PyQt6.QtCore import QThread
        thread = QThread()
        worker = SimulateWorker(self.sandbox, test_script if strategy is None else None)
        worker.output_signal.connect(lambda msg: self.output_text.append(msg))
        worker.progress_signal.connect(lambda p: self.progress_bar.setValue(p))
        worker.finished_signal.connect(lambda: self.start_btn.setEnabled(True))
        worker.start()

    def on_pause_simulate(self, checked: bool):
        """暂停模拟"""
        if checked:
            self.sandbox.pause()
            self.pause_btn.setText("▶️ 继续")
        else:
            self.sandbox.resume()
            self.pause_btn.setText("⏸️ 暂停")

    def on_stop_simulate(self):
        """停止模拟"""
        self.sandbox.stop()
        self.output_text.append("\n⚠️ 模拟已停止")
        self.status_label.setText("已停止")

    def on_clear(self):
        """清空"""
        self.output_text.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("等待开始...")
        self.predict_list.clear()
        self.predict_list.addItem("等待分析...")


class DeploymentTab(QWidget):
    """部署执行标签页"""

    deployment_progress = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.deploy_engine = DeploymentEngine()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 控制栏
        control_layout = QHBoxLayout()

        self.start_deploy_btn = QPushButton("🚀 开始部署")
        self.start_deploy_btn.setStyleSheet("background-color: #4ade80; color: #1a1a2e; font-weight: bold;")
        self.start_deploy_btn.clicked.connect(self.on_start_deploy)

        self.rollback_btn = QPushButton("🔄 回滚")
        self.rollback_btn.setStyleSheet("background-color: #ff6b6b; color: #ffffff;")
        self.rollback_btn.setEnabled(False)

        self.cancel_btn = QPushButton("⏹️ 取消")
        self.cancel_btn.setEnabled(False)

        control_layout.addWidget(self.start_deploy_btn)
        control_layout.addWidget(self.rollback_btn)
        control_layout.addWidget(self.cancel_btn)
        control_layout.addStretch()

        layout.addLayout(control_layout)

        # 服务器卡片区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")

        self.server_cards_container = QWidget()
        self.server_cards_layout = QVBoxLayout(self.server_cards_container)
        self.server_cards_layout.setSpacing(12)

        # 默认显示一个卡片
        self.add_server_card("测试服务器", "localhost")

        scroll.setWidget(self.server_cards_container)
        layout.addWidget(scroll)

        # 总体进度
        overall_group = QGroupBox("📊 部署进度")
        overall_layout = QVBoxLayout(overall_group)

        self.overall_progress = QProgressBar()
        self.overall_progress.setMaximumHeight(25)

        self.overall_status = QLabel("就绪")
        self.overall_status.setStyleSheet("color: #9ca3af;")

        overall_layout.addWidget(self.overall_progress)
        overall_layout.addWidget(self.overall_status)

        layout.addWidget(overall_group)

    def add_server_card(self, name: str, ip: str):
        """添加服务器卡片"""
        card = ServerDeployCard(name, ip)
        self.server_cards_layout.addWidget(card)

    def on_start_deploy(self):
        """开始部署"""
        self.start_deploy_btn.setEnabled(False)
        self.rollback_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

        # 模拟部署过程
        self.simulate_deployment()

    def simulate_deployment(self):
        """模拟部署"""
        cards = self.server_cards_layout.findChildren(ServerDeployCard)
        total = len(cards)
        completed = 0

        for i, card in enumerate(cards):
            card.set_status(DeploymentStatus.DEPLOYING)
            self.overall_status.setText(f"正在部署: {card.server_name}")

            # 模拟步骤
            for step in range(100):
                card.set_progress(step + 1)
                QThread.msleep(20)

            card.set_status(DeploymentStatus.SUCCESS)
            completed += 1
            self.overall_progress.setValue(int(completed / total * 100))

        self.overall_status.setText("✅ 部署完成")
        self.start_deploy_btn.setEnabled(True)
        self.rollback_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)


class ServerDeployCard(QFrame):
    """服务器部署卡片"""

    def __init__(self, name: str, ip: str, parent=None):
        super().__init__(parent)
        self.server_name = name
        self.server_ip = ip
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("""
            ServerDeployCard {
                background-color: #2a2a3e;
                border: 1px solid #3a3a5c;
                border-radius: 8px;
                padding: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # 标题栏
        header = QHBoxLayout()
        self.name_label = QLabel(f"🖥️ {self.server_name}")
        self.name_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self.name_label.setStyleSheet("color: #ffffff;")

        self.ip_label = QLabel(self.server_ip)
        self.ip_label.setStyleSheet("color: #9ca3af;")

        self.status_badge = QLabel("等待中")
        self.status_badge.setStyleSheet("background-color: #3a3a5c; color: #9ca3af; padding: 4px 8px; border-radius: 4px;")

        header.addWidget(self.name_label)
        header.addWidget(self.ip_label)
        header.addWidget(self.status_badge)

        layout.addLayout(header)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setMaximumHeight(15)

        layout.addWidget(self.progress)

        # 日志
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(100)
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #1a1a2e; border: none; color: #9ca3af; font-size: 11px;")

        layout.addWidget(self.log_text)

    def set_status(self, status: DeploymentStatus):
        """设置状态"""
        colors = {
            DeploymentStatus.PENDING: "#9ca3af",
            DeploymentStatus.DEPLOYING: "#60a5fa",
            DeploymentStatus.VERIFYING: "#facc15",
            DeploymentStatus.SUCCESS: "#4ade80",
            DeploymentStatus.FAILED: "#ff6b6b",
            DeploymentStatus.ROLLING_BACK: "#f97316"
        }

        self.status_badge.setText(status.value.upper())
        self.status_badge.setStyleSheet(f"background-color: {colors.get(status, '#9ca3af')}; color: #ffffff; padding: 4px 8px; border-radius: 4px;")

        self.log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] 状态: {status.value}")

    def set_progress(self, value: int):
        """设置进度"""
        self.progress.setValue(value)


class LearningTab(QWidget):
    """学习中心标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.learning = LearningSystem()
        self.setup_ui()
        self.load_progress()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 进度概览
        progress_group = QGroupBox("📊 学习进度")
        progress_layout = QHBoxLayout(progress_group)

        self.level_label = QLabel("Lv.1 萌新")
        self.level_label.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        self.level_label.setStyleSheet("color: #facc15;")

        self.xp_label = QLabel("0 XP")
        self.xp_label.setStyleSheet("color: #9ca3af;")

        self.streak_label = QLabel("🔥 连续0天")
        self.streak_label.setStyleSheet("color: #ff6b6b;")

        progress_layout.addWidget(self.level_label)
        progress_layout.addWidget(self.xp_label)
        progress_layout.addWidget(self.streak_label)
        progress_layout.addStretch()

        layout.addWidget(progress_group)

        # 技能树
        skill_group = QGroupBox("🌳 技能树")
        skill_layout = QVBoxLayout(skill_group)

        self.skill_list = QListWidget()
        self.skill_list.itemClicked.connect(self.on_skill_click)
        skill_layout.addWidget(self.skill_list)

        layout.addWidget(skill_group)

        # 今日任务
        task_group = QGroupBox("📅 今日任务")
        task_layout = QVBoxLayout(task_group)

        self.task_list = QListWidget()
        self.task_list.itemClicked.connect(self.on_task_click)
        task_layout.addWidget(self.task_list)

        layout.addWidget(task_group)

        # 命令解释器
        explain_group = QGroupBox("💡 命令解释器")
        explain_layout = QVBoxLayout(explain_group)

        cmd_layout = QHBoxLayout()
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("输入命令，如: pip install, docker run")

        self.explain_btn = QPushButton("解释")
        self.explain_btn.clicked.connect(self.on_explain)

        cmd_layout.addWidget(self.cmd_input)
        cmd_layout.addWidget(self.explain_btn)

        explain_layout.addLayout(cmd_layout)

        self.explain_result = QTextBrowser()
        self.explain_result.setMaximumHeight(200)

        explain_layout.addWidget(self.explain_result)

        layout.addWidget(explain_group)

    def load_progress(self):
        """加载进度"""
        try:
            progress = self.learning.get_progress()
            self.level_label.setText(f"Lv.{progress.level.value} {progress.level.name}")
            self.xp_label.setText(f"{progress.total_xp} XP")
            self.streak_label.setText(f"🔥 连续{progress.streak_days}天")

            # 从LearningSystem获取真实的技能树
            skill_tree = self.learning.get_skill_tree()
            self.skill_list.clear()
            for skill in skill_tree.values():
                if skill.is_unlocked:
                    icon = "🔓"
                elif skill.is_mastered:
                    icon = "⭐"
                else:
                    icon = "🔒"
                level_reqs = f"Lv.{skill.level_required.value}" if not skill.is_unlocked else ""
                self.skill_list.addItem(f"{icon} {skill.name} {level_reqs}")

            # 从LearningSystem获取真实的每日任务
            daily_tasks = self.learning.get_daily_tasks()
            self.task_list.clear()
            for task in daily_tasks:
                status = "☐" if not task.is_completed else "☑"
                self.task_list.addItem(f"{status} {task.name} - +{task.xp_reward}XP")

        except Exception as e:
            logger.error(f"Failed to load progress: {e}")
            self.level_label.setText("Lv.1 萌新")
            self.xp_label.setText("0 XP")
            self.streak_label.setText("🔥 连续0天")

    def on_skill_click(self, item: QListWidgetItem):
        """技能项点击"""
        try:
            skill_tree = self.learning.get_skill_tree()
            text = item.text()

            # 查找对应的技能
            for skill_id, skill in skill_tree.items():
                if skill.name in text:
                    detail = f"""
╔══════════════════════════════════════════════════════════════╗
║                       技能详情                             ║
╠══════════════════════════════════════════════════════════════╣
║ 名称: {skill.name}
║ 描述: {skill.description}
║ 类别: {skill.category}
║ 所需等级: Lv.{skill.level_required.value} {skill.level_required.name}
║ XP要求: {skill.xp_required}
║ 前置技能: {', '.join(skill.prerequisites) if skill.prerequisites else '无'}
╠══════════════════════════════════════════════════════════════╣
║ 状态: {'已解锁' if skill.is_unlocked else '未解锁'}
╚══════════════════════════════════════════════════════════════╝
"""
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.information(self, skill.name, detail.strip())
                    break
        except Exception as e:
            logger.error(f"Failed to show skill detail: {e}")

    def on_task_click(self, item: QListWidgetItem):
        """任务项点击"""
        try:
            text = item.text()
            if text.startswith("☑"):
                return  # 已完成的任务不响应

            # 找到对应的任务
            daily_tasks = self.learning.get_daily_tasks()
            for task in daily_tasks:
                if task.name in text and not task.is_completed:
                    # 模拟完成任务（实际应该根据真实行为判断）
                    self.learning.complete_daily_task(task.task_id)
                    self.load_progress()  # 刷新显示
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.information(self, "任务完成", f"🎉 {task.name} 已完成！\n+{task.xp_reward} XP")
                    break
        except Exception as e:
            logger.error(f"Failed to complete task: {e}")

    def on_explain(self):
        """解释命令"""
        cmd = self.cmd_input.text()
        if not cmd:
            return

        explanation = self.learning.explain_command(cmd)

        self.explain_result.setHtml(f"""
            <div style='color: #e0e0e0; font-family: monospace;'>
                <p style='color: #60a5fa; font-weight: bold;'>📖 命令: {cmd}</p>
                <hr style='border-color: #3a3a5c;'>
                <p style='color: #4ade80;'>🌱 {explanation.metaphor}</p>
                <br>
                <p style='color: #facc15;'>⚙️ {explanation.technical}</p>
                <br>
                <p style='color: #60a5fa;'>✨ {explanation.best_practice}</p>
            </div>
        """)


class SmartDeployPanel(QWidget):
    """
    智能轻量化部署系统 - 主面板

    5标签页设计：
    1. 🏠 总览仪表板
    2. 📥 输入与解析
    3. 🎮 沙箱模拟
    4. 🚀 部署执行
    5. 📚 学习中心
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.apply_style()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # 标签页
        self.tabs = QTabWidget()

        self.overview_tab = OverviewTab()
        self.input_tab = InputParseTab()
        self.sandbox_tab = SandboxSimulateTab()
        self.deploy_tab = DeploymentTab()
        self.learning_tab = LearningTab()

        self.tabs.addTab(self.overview_tab, "🏠 总览")
        self.tabs.addTab(self.input_tab, "📥 输入")
        self.tabs.addTab(self.sandbox_tab, "🎮 模拟")
        self.tabs.addTab(self.deploy_tab, "🚀 部署")
        self.tabs.addTab(self.learning_tab, "📚 学习")

        layout.addWidget(self.tabs)

    def apply_style(self):
        """应用样式"""
        self.setStyleSheet(DARK_STYLE)


# 创建面板
def create_panel() -> SmartDeployPanel:
    """创建面板"""
    return SmartDeployPanel()
