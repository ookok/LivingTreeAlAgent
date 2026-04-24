"""
AgentHub - Hermes 智能体控制面板
集成五大核心模块的统一监控界面

五大支柱：
1. TaskRouter - 多层递归任务分解器
2. PermissionEngine - 动态权限策略引擎
3. SkillClusterer - 技能语义聚类系统
4. SemanticValidator - 语义一致性校验器
5. ResourceMonitor - 自适应资源调度器

使用方式：
    from core.agent_hub import AgentHub
    hub = AgentHub(parent=main_window)
    hub.show()
"""

import json
import time
import threading
from datetime import datetime
from typing import Optional

# 日志系统
from core.logger import get_logger
logger = get_logger("core.agent_hub")

# PyQt6/PyQt5 兼容
try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QPushButton, QTextEdit, QTreeWidget,
        QTreeWidgetItem, QTableWidget, QTableWidgetItem,
        QTabWidget, QGroupBox, QProgressBar, QStatusBar,
        QMessageBox, QDialog, QHeaderView, QSplitter,
        QListWidget, QListWidgetItem, QAbstractItemView,
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
    from PyQt6.QtGui import QFont, QColor, QPalette
    PYQT_VERSION = 6
except ImportError:
    try:
        from PyQt5.QtWidgets import (
            QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
            QLabel, QPushButton, QTextEdit, QTreeWidget,
            QTreeWidgetItem, QTableWidget, QTableWidgetItem,
            QTabWidget, QGroupBox, QProgressBar, QStatusBar,
            QMessageBox, QDialog, QHeaderView, QSplitter,
            QListWidget, QListWidgetItem
        )
        from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
        from PyQt5.QtGui import QFont, QColor, QPalette
        PYQT_VERSION = 5
    except ImportError:
        raise ImportError("需要安装 PyQt6 或 PyQt5: pip install PyQt6")

from core.task_router import TaskRouter, TaskNode, TaskStatus
from core.permission_engine import PermissionEngine, RiskLevel
from core.skill_clusterer import SkillClusterer
from core.semantic_validator import SemanticValidator
from core.resource_monitor import ResourceMonitor, LoadLevel, Alert


class ApprovalDialog(QDialog):
    """权限审批对话框"""

    def __init__(self, request: dict, parent=None):
        super().__init__(parent)
        self.request = request
        self.result = False
        self.remember_choice = False
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("🔐 操作审批请求")
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)

        # 风险提示
        risk = self.request.get("risk_level", "unknown")
        risk_colors = {
            "high": "#FF4444",
            "extreme": "#FF0000",
            "medium": "#FFAA00",
            "low": "#44AA44",
        }
        risk_color = risk_colors.get(risk, "#888888")

        risk_label = QLabel(f'<h2 style="color: {risk_color}">⚠️ {risk.upper()} 风险操作</h2>')
        risk_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(risk_label)

        # 详情
        details = QTextEdit()
        details.setReadOnly(True)
        details.setMaximumHeight(150)
        details.append(f"<b>操作类型:</b> {self.request.get('action', 'N/A')}")
        details.append(f"<b>匹配模式:</b> {', '.join(self.request.get('matched_patterns', []))}")
        details.append(f"<b>置信度:</b> {self.request.get('confidence', 0):.0%}")
        details.append(f"<b>原因:</b> {self.request.get('reason', 'N/A')}")
        layout.addWidget(details)

        # 按钮
        btn_layout = QHBoxLayout()
        self.btn_allow = QPushButton("✅ 允许")
        self.btn_deny = QPushButton("❌ 拒绝")
        self.btn_allow.clicked.connect(self._allow)
        self.btn_deny.clicked.connect(self._deny)
        btn_layout.addWidget(self.btn_allow)
        btn_layout.addWidget(self.btn_deny)
        layout.addLayout(btn_layout)

    def _allow(self):
        self.result = True
        self.accept()

    def _deny(self):
        self.result = False
        self.reject()


class AgentHub(QWidget):
    """
    Hermes 智能体控制面板

    集成五大核心模块的统一界面
    """

    COLORS = {
        "task_router": "#3498db",
        "permission": "#e74c3c",
        "skill_clusterer": "#2ecc71",
        "semantic": "#f39c12",
        "resource": "#9b59b6",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent

        self.task_router: Optional[TaskRouter] = None
        self.permission_engine: Optional[PermissionEngine] = None
        self.skill_clusterer: Optional[SkillClusterer] = None
        self.semantic_validator: Optional[SemanticValidator] = None
        self.resource_monitor: Optional[ResourceMonitor] = None

        self._widgets = {}
        self._timers = []

        self._init_modules()
        self._init_ui()

    def _init_modules(self):
        """初始化五大模块"""
        logger.info("=" * 60)
        logger.info("🔧 初始化 AgentHub 五大核心模块...")
        logger.info("=" * 60)

        self.task_router = TaskRouter(max_depth=3, complexity_threshold=0.7)
        logger.info("✓ TaskRouter 已初始化")

        self.permission_engine = PermissionEngine(
            parent_widget=self,
            auto_approve_low=False,
        )
        self.permission_engine.on_alert(self._on_permission_alert)
        logger.info("✓ PermissionEngine 已初始化")

        self.skill_clusterer = SkillClusterer()
        logger.info("✓ SkillClusterer 已初始化")

        self.semantic_validator = SemanticValidator()
        logger.info("✓ SemanticValidator 已初始化")

        self.resource_monitor = ResourceMonitor(interval=3)
        self.resource_monitor.on_alert(self._on_resource_alert)
        self.resource_monitor.on_load_change(self._on_load_change)
        logger.info("✓ ResourceMonitor 已初始化")

        logger.info("=" * 60)
        logger.info("✅ 五大核心模块全部就绪！")
        logger.info("=" * 60)

    def _init_ui(self):
        """初始化界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        title = QLabel('<h2>🧠 Hermes AgentHub - 智能体控制中心</h2>')
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._create_overview_tab(), "📊 总览")
        tabs.addTab(self._create_tasks_tab(), "🔄 任务调度")
        tabs.addTab(self._create_permissions_tab(), "🔐 权限管理")
        tabs.addTab(self._create_skills_tab(), "🛠️ 技能库")
        tabs.addTab(self._create_validator_tab(), "📝 语义校验")
        tabs.addTab(self._create_resource_tab(), "💻 资源监控")

        main_layout.addWidget(tabs)

        self.status_bar = QStatusBar()
        main_layout.addWidget(self.status_bar)

        self._start_timers()

    def _create_overview_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        grid = QGridLayout()

        card1 = self._create_module_card("🔄 TaskRouter", "多层递归任务分解器", "支持 3 层深度递归，复杂度 > 0.7 自动触发", self.COLORS["task_router"])
        self._widgets["task_card"] = card1
        grid.addWidget(card1, 0, 0)

        card2 = self._create_module_card("🔐 PermissionEngine", "动态权限策略引擎", "智能风险评估，弹出审批对话框", self.COLORS["permission"])
        self._widgets["permission_card"] = card2
        grid.addWidget(card2, 0, 1)

        card3 = self._create_module_card("🛠️ SkillClusterer", "技能语义聚类系统", "sentence-transformers + FAISS + DBSCAN", self.COLORS["skill_clusterer"])
        self._widgets["skill_card"] = card3
        grid.addWidget(card3, 1, 0)

        card4 = self._create_module_card("📝 SemanticValidator", "语义一致性校验器", "spaCy 句法分析，避免断章取义", self.COLORS["semantic"])
        self._widgets["validator_card"] = card4
        grid.addWidget(card4, 1, 1)

        card5 = self._create_module_card("💻 ResourceMonitor", "自适应资源调度器", "psutil 实时监控，动态限流", self.COLORS["resource"])
        self._widgets["resource_card"] = card5
        grid.addWidget(card5, 2, 0, 1, 2)

        layout.addLayout(grid)

        btn_layout = QHBoxLayout()
        btn_test_task = QPushButton("🧪 测试任务分解")
        btn_test_task.clicked.connect(self._test_task_router)
        btn_test_perm = QPushButton("🧪 测试权限评估")
        btn_test_perm.clicked.connect(self._test_permission_engine)
        btn_test_skill = QPushButton("🧪 测试技能聚类")
        btn_test_skill.clicked.connect(self._test_skill_clusterer)
        btn_layout.addWidget(btn_test_task)
        btn_layout.addWidget(btn_test_perm)
        btn_layout.addWidget(btn_test_skill)
        layout.addLayout(btn_layout)

        return widget

    def _create_module_card(self, title: str, subtitle: str, description: str, color: str) -> QWidget:
        card = QGroupBox()
        card.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid {color};
                border-radius: 10px;
                margin-top: 10px;
                padding: 10px;
                background: rgba(255,255,255,95);
            }}
            QGroupBox::title {{
                color: {color};
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """)

        layout = QVBoxLayout(card)

        status_layout = QHBoxLayout()
        status_dot = QLabel("⚪")
        status_label = QLabel('<b style="color: #2ecc71">● 运行中</b>')
        status_layout.addWidget(status_dot)
        status_layout.addWidget(status_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)

        desc_label = QLabel(f'<font size=-1>{description}</font>')
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        stats_label = QLabel('<font size=-2 color=gray>就绪</font>')
        layout.addWidget(stats_label)

        return card

    def _create_tasks_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        ctrl_layout = QHBoxLayout()
        btn_add_task = QPushButton("➕ 添加任务")
        btn_add_task.clicked.connect(self._add_demo_task)
        btn_clear_tasks = QPushButton("🗑️ 清空")
        btn_clear_tasks.clicked.connect(self._clear_tasks)
        btn_refresh = QPushButton("🔄 刷新")
        btn_refresh.clicked.connect(self._refresh_tasks)
        ctrl_layout.addWidget(btn_add_task)
        ctrl_layout.addWidget(btn_clear_tasks)
        ctrl_layout.addWidget(btn_refresh)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        self.task_tree = QTreeWidget()
        self.task_tree.setHeaderLabels(["任务ID", "指令", "深度", "复杂度", "状态"])
        self.task_tree.setColumnWidth(0, 80)
        self.task_tree.setColumnWidth(1, 400)
        self.task_tree.setColumnWidth(2, 60)
        self.task_tree.setColumnWidth(3, 80)
        layout.addWidget(self.task_tree)

        log_group = QGroupBox("执行日志")
        log_layout = QVBoxLayout(log_group)
        self.task_log = QTextEdit()
        self.task_log.setReadOnly(True)
        self.task_log.setMaximumHeight(150)
        log_layout.addWidget(self.task_log)
        layout.addWidget(log_group)

        return widget

    def _create_permissions_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        test_layout = QHBoxLayout()
        self.perm_test_input = QTextEdit()
        self.perm_test_input.setPlaceholderText("输入待测试的指令...\n例如：删除文件 C:\\temp\\test.txt")
        self.perm_test_input.setMaximumHeight(80)
        test_layout.addWidget(self.perm_test_input, 3)

        btn_test_perm = QPushButton("🔍 评估风险")
        btn_test_perm.clicked.connect(self._test_permission)
        test_layout.addWidget(btn_test_perm, 1)
        layout.addLayout(test_layout)

        hist_group = QGroupBox("权限历史")
        hist_layout = QVBoxLayout(hist_group)
        self.perm_table = QTableWidget()
        self.perm_table.setColumnCount(5)
        self.perm_table.setHorizontalHeaderLabels(["时间", "操作", "风险等级", "结果", "置信度"])
        self.perm_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.perm_table.setMaximumHeight(200)
        hist_layout.addWidget(self.perm_table)
        layout.addWidget(hist_group)

        stats_group = QGroupBox("统计")
        stats_layout = QGridLayout(stats_group)
        self._widgets["perm_total"] = QLabel("0")
        self._widgets["perm_approved"] = QLabel("0")
        self._widgets["perm_denied"] = QLabel("0")
        self._widgets["perm_auto"] = QLabel("0")
        stats_layout.addWidget(QLabel("总请求:"), 0, 0)
        stats_layout.addWidget(self._widgets["perm_total"], 0, 1)
        stats_layout.addWidget(QLabel("已批准:"), 0, 2)
        stats_layout.addWidget(self._widgets["perm_approved"], 0, 3)
        stats_layout.addWidget(QLabel("已拒绝:"), 0, 4)
        stats_layout.addWidget(self._widgets["perm_denied"], 0, 5)
        stats_layout.addWidget(QLabel("自动批准:"), 1, 0)
        stats_layout.addWidget(self._widgets["perm_auto"], 1, 1)
        layout.addWidget(stats_group)

        return widget

    def _create_skills_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        ctrl_layout = QHBoxLayout()
        btn_add_skill = QPushButton("➕ 添加技能")
        btn_add_skill.clicked.connect(self._add_demo_skill)
        btn_cluster = QPushButton("🔍 执行聚类")
        btn_cluster.clicked.connect(self._run_clustering)
        btn_merge = QPushButton("🔀 生成合并建议")
        btn_merge.clicked.connect(self._generate_merge_suggestions)
        ctrl_layout.addWidget(btn_add_skill)
        ctrl_layout.addWidget(btn_cluster)
        ctrl_layout.addWidget(btn_merge)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        self.skills_list = QListWidget()
        self.skills_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.skills_list)

        suggest_group = QGroupBox("合并建议")
        suggest_layout = QVBoxLayout(suggest_group)
        self.suggestions_text = QTextEdit()
        self.suggestions_text.setReadOnly(True)
        self.suggestions_text.setMaximumHeight(120)
        suggest_layout.addWidget(self.suggestions_text)
        layout.addWidget(suggest_group)

        return widget

    def _create_validator_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        input_layout = QVBoxLayout()
        input_layout.addWidget(QLabel("待校验文本块:"))
        self.validator_input = QTextEdit()
        self.validator_input.setPlaceholderText("输入文本块进行语义校验...\n例如：因为天气冷，所以\n（检测未闭合从句）")
        self.validator_input.setMaximumHeight(100)
        input_layout.addWidget(self.validator_input)

        btn_validate = QPushButton("🔍 校验")
        btn_validate.clicked.connect(self._validate_text)
        input_layout.addWidget(btn_validate)
        layout.addLayout(input_layout)

        result_group = QGroupBox("校验结果")
        result_layout = QVBoxLayout(result_group)
        self.validator_result = QTextEdit()
        self.validator_result.setReadOnly(True)
        result_layout.addWidget(self.validator_result)
        layout.addWidget(result_group)

        stats_layout = QHBoxLayout()
        stats_layout.addWidget(QLabel("有效率:"))
        self._widgets["valid_rate"] = QLabel("N/A")
        stats_layout.addWidget(self._widgets["valid_rate"])
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        return widget

    def _create_resource_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        grid = QGridLayout()

        cpu_group = QGroupBox("🖥️ CPU")
        cpu_layout = QVBoxLayout(cpu_group)
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setRange(0, 100)
        self._widgets["cpu_bar"] = self.cpu_bar
        self.cpu_label = QLabel("0%")
        self._widgets["cpu_label"] = self.cpu_label
        cpu_layout.addWidget(self.cpu_bar)
        cpu_layout.addWidget(self.cpu_label)
        grid.addWidget(cpu_group, 0, 0)

        mem_group = QGroupBox("💾 内存")
        mem_layout = QVBoxLayout(mem_group)
        self.mem_bar = QProgressBar()
        self.mem_bar.setRange(0, 100)
        self._widgets["mem_bar"] = self.mem_bar
        self.mem_label = QLabel("0 GB")
        self._widgets["mem_label"] = self.mem_label
        mem_layout.addWidget(self.mem_bar)
        mem_layout.addWidget(self.mem_label)
        grid.addWidget(mem_group, 0, 1)

        load_group = QGroupBox("📊 系统负载")
        load_layout = QVBoxLayout(load_group)
        self.load_label = QLabel('<h2 style="color: #2ecc71">🟢 空闲</h2>')
        self._widgets["load_label"] = self.load_label
        self.load_detail = QLabel("任务队列: 0/3")
        self._widgets["load_detail"] = self.load_detail
        load_layout.addWidget(self.load_label)
        load_layout.addWidget(self.load_detail)
        grid.addWidget(load_group, 1, 0)

        gpu_group = QGroupBox("🎮 GPU")
        gpu_layout = QVBoxLayout(gpu_group)
        self.gpu_label = QLabel("未检测到")
        self._widgets["gpu_label"] = self.gpu_label
        gpu_layout.addWidget(self.gpu_label)
        grid.addWidget(gpu_group, 1, 1)

        layout.addLayout(grid)

        threshold_group = QGroupBox("告警阈值")
        threshold_layout = QGridLayout(threshold_group)
        threshold_layout.addWidget(QLabel("CPU 警告 (>%):"), 0, 0)
        threshold_layout.addWidget(QLabel("70"), 0, 1)
        threshold_layout.addWidget(QLabel("CPU 危险 (>%):"), 0, 2)
        threshold_layout.addWidget(QLabel("85"), 0, 3)
        threshold_layout.addWidget(QLabel("内存警告 (GB):"), 1, 0)
        threshold_layout.addWidget(QLabel("8"), 1, 1)
        threshold_layout.addWidget(QLabel("内存危险 (GB):"), 1, 2)
        threshold_layout.addWidget(QLabel("16"), 1, 3)
        layout.addWidget(threshold_group)

        return widget

    def _start_timers(self):
        if self.resource_monitor:
            self.resource_monitor.start()

        timer = QTimer(self)
        timer.timeout.connect(self._update_ui)
        timer.start(2000)
        self._timers.append(timer)

    def _update_ui(self):
        if self.resource_monitor:
            status = self.resource_monitor.get_status_dict()

            cpu = status["cpu_percent"]
            self._widgets["cpu_bar"].setValue(int(cpu))
            self._widgets["cpu_label"].setText(f"{cpu:.1f}%")
            if cpu > 85:
                self._widgets["cpu_bar"].setStyleSheet("QProgressBar::chunk { background: #e74c3c; }")
            elif cpu > 70:
                self._widgets["cpu_bar"].setStyleSheet("QProgressBar::chunk { background: #f39c12; }")
            else:
                self._widgets["cpu_bar"].setStyleSheet("QProgressBar::chunk { background: #2ecc71; }")

            mem_mb = status["memory_mb"]
            mem_pct = status["memory_percent"]
            self._widgets["mem_bar"].setValue(int(mem_pct))
            self._widgets["mem_label"].setText(f"{mem_mb / 1024:.1f} GB ({mem_pct:.0f}%)")

            load = status["load_level"]
            load_emoji = status["load_emoji"]
            load_text = {"idle": "空闲", "light": "轻度", "moderate": "中度", "heavy": "重度", "critical": "危险"}.get(load, "")
            load_color = {"idle": "#2ecc71", "light": "#f1c40f", "moderate": "#e67e22", "heavy": "#e74c3c", "critical": "#c0392b"}.get(load, "#888")
            self._widgets["load_label"].setText(f'<h2 style="color: {load_color}">{load_emoji} {load_text}</h2>')
            self._widgets["load_detail"].setText(f"任务队列: {status['queue_info']}")

            if status.get("gpu_percent") is not None:
                gpu_pct = status["gpu_percent"]
                self._widgets["gpu_label"].setText(f"{gpu_pct:.1f}%")
            else:
                self._widgets["gpu_label"].setText("未检测到")

            self.status_bar.showMessage(
                f"💻 CPU: {cpu:.0f}% | 💾 内存: {mem_mb/1024:.1f} GB | "
                f"📊 负载: {load_text} | 🧠 AgentHub 运行中"
            )

        if self.permission_engine:
            stats = self.permission_engine.get_stats()
            self._widgets["perm_total"].setText(str(stats["total_requests"]))
            self._widgets["perm_approved"].setText(str(stats["approved"]))
            self._widgets["perm_denied"].setText(str(stats["denied"]))
            self._widgets["perm_auto"].setText(str(stats["auto_approved"]))

        if self.semantic_validator:
            vstats = self.semantic_validator.get_stats()
            if vstats["total_chunks"] > 0:
                rate = vstats["valid_rate"] * 100
                self._widgets["valid_rate"].setText(f"{rate:.1f}%")

        if self.task_router:
            self._refresh_tasks()

    def _on_permission_alert(self, alert: Alert):
        self.status_bar.showMessage(f"🔐 {alert.message}", 5000)

    def _on_resource_alert(self, alert: Alert):
        self.status_bar.showMessage(f"⚠️ {alert.message}", 5000)
        QMessageBox.warning(self, "资源告警", alert.message)

    def _on_load_change(self, load: LoadLevel):
        load_text = {"idle": "空闲", "light": "轻度", "moderate": "中度", "heavy": "重度", "critical": "危险"}.get(load.value, "")
        self.status_bar.showMessage(f"📊 系统负载变化: {load_text}", 3000)

    def _test_task_router(self):
        if not self.task_router:
            return
        self.task_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 测试任务分解...")
        task_id = self.task_router.add_task(
            prompt="分析《红楼梦》人物关系图谱",
            context={"book": "红楼梦"},
            tools=["read_file", "search_files"],
            priority=2
        )
        self.task_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] 添加任务: {task_id}")
        for event in self.task_router.execute():
            self.task_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {event}")

    def _test_permission_engine(self):
        if not self.permission_engine:
            return
        test_prompts = [
            "删除文件 C:\\temp\\test.txt",
            "读取配置文件 config.yaml",
            "执行 subprocess.run(['ls'])",
            "发送邮件给 ceo@mogoo.com.cn",
        ]
        for prompt in test_prompts:
            result = self.permission_engine.assess(prompt)
            self.task_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] 评估: {prompt[:30]}...")
            self.task_log.append(f"    风险等级: {result['risk_level']} | 置信度: {result['confidence']:.0%}")

    def _test_skill_clusterer(self):
        if not self.skill_clusterer:
            return
        skills = [
            ("extract_financial_data_v1", "从 PDF 提取财务数据"),
            ("extract_financial_data_v2", "提取财务报表数据"),
            ("extract_stock_price", "获取股票价格信息"),
            ("calculate_ratio", "计算财务比率"),
            ("generate_report", "生成分析报告"),
        ]
        for name, desc in skills:
            self.skill_clusterer.register_skill(name, desc)
            self.skills_list.addItem(f"✓ {name}: {desc}")
        self._run_clustering()

    def _add_demo_task(self):
        if not self.task_router:
            return
        task_id = self.task_router.add_task(
            prompt=f"演示任务 {datetime.now().strftime('%H:%M:%S')}",
            tools=["read_file"],
        )
        self._refresh_tasks()

    def _clear_tasks(self):
        if self.task_router:
            self.task_router._tasks.clear()
            self.task_router._task_queue.clear()
        self.task_tree.clear()
        self.task_log.clear()

    def _refresh_tasks(self):
        if not self.task_router or not self.task_tree:
            return
        self.task_tree.clear()
        for task_id, task in self.task_router._tasks.items():
            item = QTreeWidgetItem([
                task_id[:8],
                task.prompt[:50] + ("..." if len(task.prompt) > 50 else ""),
                str(task.depth),
                f"{task.complexity_score:.2f}",
                task.status.value,
            ])
            self.task_tree.addTopLevelItem(item)

    def _test_permission(self):
        if not self.permission_engine:
            return
        text = self.perm_test_input.toPlainText()
        if not text.strip():
            return
        result = self.permission_engine.assess(text)

        row = self.perm_table.rowCount()
        self.perm_table.insertRow(row)
        self.perm_table.setItem(row, 0, QTableWidgetItem(datetime.now().strftime("%H:%M:%S")))
        self.perm_table.setItem(row, 1, QTableWidgetItem(result["action"]))

        risk_item = QTableWidgetItem(result["risk_level"])
        if result["risk_level"] == "high":
            risk_item.setBackground(QColor("#ffcccc"))
        elif result["risk_level"] == "medium":
            risk_item.setBackground(QColor("#fff4cc"))
        self.perm_table.setItem(row, 2, risk_item)

        self.perm_table.setItem(row, 3, QTableWidgetItem("待审批" if result["requires_approval"] else "自动"))
        self.perm_table.setItem(row, 4, QTableWidgetItem(f"{result['confidence']:.0%}"))

        if result["requires_approval"]:
            dialog = ApprovalDialog(result, self)
            if dialog.exec_():
                self.task_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] 用户批准: {text[:40]}")
            else:
                self.task_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] 用户拒绝: {text[:40]}")

    def _add_demo_skill(self):
        if not self.skill_clusterer:
            return
        name = f"skill_{int(time.time())}"
        desc = f"演示技能 {datetime.now().strftime('%H:%M:%S')}"
        self.skill_clusterer.register_skill(name, desc)
        self.skills_list.addItem(f"✓ {name}: {desc}")

    def _run_clustering(self):
        if not self.skill_clusterer:
            return
        self.skill_clusterer.build_index()
        clusters = self.skill_clusterer.clusterize()
        self.skills_list.clear()
        for cluster in clusters:
            self.skills_list.addItem(f"📦 聚类 {cluster.cluster_id}: {len(cluster.skills)} 个技能")
            for skill in cluster.skills:
                self.skills_list.addItem(f"   └─ {skill.name}")

    def _generate_merge_suggestions(self):
        if not self.skill_clusterer:
            return
        suggestions = self.skill_clusterer.get_merge_suggestions()
        self.suggestions_text.clear()
        if not suggestions:
            self.suggestions_text.append("暂无合并建议")
            return
        for s in suggestions:
            self.suggestions_text.append(
                f"📌 {s.skill_pair[0].name} + {s.skill_pair[1].name}\n"
                f"   相似度: {s.similarity:.2%}\n"
                f"   建议名称: {s.suggested_name}\n"
            )

    def _validate_text(self):
        if not self.semantic_validator:
            return
        text = self.validator_input.toPlainText()
        if not text.strip():
            return
        result = self.semantic_validator.validate_chunk(text)
        self.validator_result.clear()
        self.validator_result.append(f"<b>校验结果:</b> {'✅ 有效' if result['is_valid'] else '❌ 无效'}")
        self.validator_result.append(f"<b>置信度:</b> {result['confidence']:.0%}")
        self.validator_result.append(f"<b>问题:</b>")
        if result['issues']:
            for issue in result['issues']:
                self.validator_result.append(f"   - {issue}")
        else:
            self.validator_result.append("   无")
        self.validator_result.append(f"<b>建议:</b> {result['suggestion']}")

    def closeEvent(self, event):
        if self.resource_monitor:
            self.resource_monitor.stop()
        for timer in self._timers:
            timer.stop()
        event.accept()


def show_agent_hub(parent=None):
    """显示 AgentHub 面板"""
    hub = AgentHub(parent=parent)
    hub.setWindowTitle("Hermes AgentHub - 智能体控制中心")
    hub.resize(1000, 700)
    hub.show()
    return hub
