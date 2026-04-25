"""
Karpathy Skills PyQt6 UI Panel
工程师行为准则配置与监控面板
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QTextEdit, QCheckBox,
    QGroupBox, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QSpinBox, QDoubleSpinBox, QComboBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from client.src.business.karpathy_skills import (
    AmbiguityDetector,
    AgentPromptBuilder,
    AgentType,
    get_detector,
    get_builder,
)


class KarpathyRulesPanel(QWidget):
    """
    Karpathy Skills 主面板
    包含规则配置、歧义检测历史、Agent Prompt 预览
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.detector = get_detector()
        self.builder = get_builder()

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("Karpathy Skills - 工程师行为准则")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Tab 控件
        tabs = QTabWidget()

        # Tab 1: 规则概览
        tabs.addTab(self._create_rules_tab(), "规则概览")

        # Tab 2: 歧义检测
        tabs.addTab(self._create_ambiguity_tab(), "歧义检测")

        # Tab 3: Agent Prompt
        tabs.addTab(self._create_prompt_tab(), "Prompt 预览")

        # Tab 4: 配置
        tabs.addTab(self._create_config_tab(), "配置")

        layout.addWidget(tabs)

    def _create_rules_tab(self) -> QWidget:
        """创建规则概览 Tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 五项准则
        rules_text = """
<h2>工程师行为准则（源于 Andrej Karpathy）</h2>

<h3>1. 不隐藏困惑（No Hiding Confusion）</h3>
<p>若需求/代码有歧义，必须列出所有可能解读并追问确认。
禁止自行选择一种解读后沉默执行。</p>

<h3>2. 极简实现（Minimal Implementation）</h3>
<p>写完代码后自问："资深工程师会觉得这过度设计吗？"
若是，删减至仅满足需求的最少代码。</p>

<h3>3. 最小接触（Minimal Touch）</h3>
<p>编辑旧代码时，只修改与任务直接相关的部分。
不顺手"清理"无关注释、格式、变量命名。</p>

<h3>4. 目标驱动（Goal-Driven）</h3>
<p>多步任务先输出≤3步的计划，并定义可验证的成功标准。
循环执行直到所有成功标准满足。</p>

<h3>5. 主动权衡（Explicit Trade-offs）</h3>
<p>在关键决策点展示权衡："方案A快但耦合，方案B慢但解耦"。
让用户了解决策利弊后再执行。</p>
"""

        rules_label = QLabel(rules_text)
        rules_label.setWordWrap(True)
        rules_label.setTextFormat(Qt.TextFormat.RichText)

        scroll = QScrollArea()
        scroll.setWidget(rules_label)
        scroll.setWidgetResizable(True)

        layout.addWidget(scroll)

        return widget

    def _create_ambiguity_tab(self) -> QWidget:
        """创建歧义检测 Tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 测试区域
        test_group = QGroupBox("歧义检测测试")
        test_layout = QVBoxLayout(test_group)

        test_input_layout = QHBoxLayout()
        test_input_layout.addWidget(QLabel("输入测试文本："))

        self.test_input = QTextEdit()
        self.test_input.setPlaceholderText("输入一段可能有歧义的需求文本...")
        self.test_input.setMaximumHeight(80)
        test_input_layout.addWidget(self.test_input)

        test_layout.addLayout(test_input_layout)

        btn_layout = QHBoxLayout()
        self.detect_btn = QPushButton("检测歧义")
        self.detect_btn.clicked.connect(self._on_detect_ambiguity)
        btn_layout.addWidget(self.detect_btn)

        self.clear_btn = QPushButton("清空历史")
        self.clear_btn.clicked.connect(self._on_clear_history)
        btn_layout.addWidget(self.clear_btn)

        test_layout.addLayout(btn_layout)

        layout.addWidget(test_group)

        # 结果显示
        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        layout.addWidget(self.result_area, 1)

        return widget

    def _on_detect_ambiguity(self):
        """执行歧义检测"""
        text = self.test_input.toPlainText()
        if not text.strip():
            self.result_area.setPlainText("请输入测试文本")
            return

        signals = self.detector.detect(text)

        if not signals:
            self.result_area.setPlainText("未检测到明显歧义 ✓")
        else:
            result = f"检测到 {len(signals)} 处潜在歧义：\n\n"
            for i, sig in enumerate(signals, 1):
                result += f"【{i}】类型: {sig.ambiguity_type}, 置信度: {sig.confidence:.0%}\n"
                result += f"    解读: {' / '.join(sig.possible_interpretations[:2])}\n\n"

            self.result_area.setPlainText(result)

    def _on_clear_history(self):
        """清空历史"""
        self.detector._history.clear()
        self.result_area.setPlainText("历史已清空")

    def _create_prompt_tab(self) -> QWidget:
        """创建 Prompt 预览 Tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Agent 类型选择
        select_layout = QHBoxLayout()
        select_layout.addWidget(QLabel("Agent 类型："))

        self.agent_combo = QComboBox()
        self.agent_combo.addItems([
            ("code_architect", "代码架构师"),
            ("debug_specialist", "调试专家"),
            ("code_generator", "代码生成器"),
            ("refactor_agent", "重构专家"),
            ("review_agent", "审查专家"),
            ("general", "通用助手"),
        ])
        select_layout.addWidget(self.agent_combo)

        self.refresh_btn = QPushButton("刷新预览")
        self.refresh_btn.clicked.connect(self._on_refresh_prompt)
        select_layout.addWidget(self.refresh_btn)

        layout.addLayout(select_layout)

        # Prompt 显示
        self.prompt_area = QTextEdit()
        self.prompt_area.setReadOnly(True)
        layout.addWidget(self.prompt_area, 1)

        # 初始化显示
        self._on_refresh_prompt()

        return widget

    def _on_refresh_prompt(self):
        """刷新 Prompt 预览"""
        agent_type = self.agent_combo.currentData()
        prompt = self.builder.build(agent_type=agent_type, include_karpathy=True)
        self.prompt_area.setPlainText(prompt)

    def _create_config_tab(self) -> QWidget:
        """创建配置 Tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 歧义检测配置
        detect_group = QGroupBox("歧义检测配置")
        detect_layout = QVBoxLayout(detect_group)

        self.enable_detect = QCheckBox("启用自动歧义检测")
        self.enable_detect.setChecked(True)
        detect_layout.addWidget(self.enable_detect)

        conf_layout = QHBoxLayout()
        conf_layout.addWidget(QLabel("置信度阈值："))
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.1, 1.0)
        self.confidence_spin.setSingleStep(0.1)
        self.confidence_spin.setValue(0.5)
        conf_layout.addWidget(self.confidence_spin)
        conf_layout.addStretch()
        detect_layout.addLayout(conf_layout)

        layout.addWidget(detect_group)

        # 代码复杂度检查
        complexity_group = QGroupBox("代码复杂度检查")
        complexity_layout = QVBoxLayout(complexity_group)

        self.enable_complexity = QCheckBox("启用过度设计检测")
        self.enable_complexity.setChecked(True)
        complexity_layout.addWidget(self.enable_complexity)

        line_layout = QHBoxLayout()
        line_layout.addWidget(QLabel("最大函数数："))
        self.max_funcs = QSpinBox()
        self.max_funcs.setRange(1, 50)
        self.max_funcs.setValue(5)
        line_layout.addWidget(self.max_funcs)
        line_layout.addStretch()
        complexity_layout.addLayout(line_layout)

        layout.addWidget(complexity_group)

        # 按钮
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存配置")
        save_btn.clicked.connect(self._on_save_config)
        btn_layout.addWidget(save_btn)

        reset_btn = QPushButton("重置")
        reset_btn.clicked.connect(self._on_reset_config)
        btn_layout.addWidget(reset_btn)

        layout.addLayout(btn_layout)

        layout.addStretch()

        return widget

    def _on_save_config(self):
        """保存配置"""
        # TODO: 保存到配置文件
        self.result_area.setPlainText("配置已保存（功能待实现）")

    def _on_reset_config(self):
        """重置配置"""
        self.enable_detect.setChecked(True)
        self.confidence_spin.setValue(0.5)
        self.enable_complexity.setChecked(True)
        self.max_funcs.setValue(5)


# 辅助函数：创建 Agent 类型下拉框
def create_agent_combo() -> QComboBox:
    """创建 Agent 类型选择下拉框"""
    combo = QComboBox()
    combo.addItems([
        ("code_architect", "代码架构师"),
        ("debug_specialist", "调试专家"),
        ("code_generator", "代码生成器"),
        ("refactor_agent", "重构专家"),
        ("review_agent", "审查专家"),
        ("general", "通用助手"),
    ])
    return combo