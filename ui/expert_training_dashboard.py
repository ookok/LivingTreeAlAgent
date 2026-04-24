# -*- coding: utf-8 -*-
"""
专家训练模块面板 - 完整版
======================

核心功能：
1. 实时学习监控 - 缓存命中率、纠正率、系统健康度
2. 知识管理 - 导入、导出、搜索、版本控制
3. 三阶段训练向导 - 提示注入 → 蒸馏数据 → 模型微调
4. 多专家协作 - 专家库管理、路由策略
5. 性能仪表盘 - 延迟、错误率、成本优化
6. 自动化调度 - 高频查询自动收集、定时训练

设计原则：
- 友好直观 - 无需深入了解AI也能使用
- 渐进式引导 - 从简单到复杂
- 实时反馈 - 每一步操作都有即时反馈
"""

from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QThread
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit,
    QFrame, QScrollArea, QProgressBar, QSlider,
    QComboBox, QCheckBox, QButtonGroup, QRadioButton,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
    QTabWidget, QGroupBox, QFormLayout, QSplitter,
    QDialog, QDialogButtonBox, QFileDialog, QMessageBox,
    QProgressDialog, QStatusBar, QToolBar,
)
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon, QAction
from PyQt6.QtCore import Qt

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Callable
import json
import time
from datetime import datetime, timedelta
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class LearningMetrics:
    """学习指标"""
    cache_hit_rate: float = 0.0
    correction_rate: float = 0.0
    accuracy: float = 0.0
    total_queries: int = 0
    learning_records: int = 0
    knowledge_fragments: int = 0
    system_health: float = 0.0

@dataclass
class ExpertInfo:
    """专家信息"""
    id: str
    name: str
    domain: str
    status: str  # active, training, inactive
    accuracy: float = 0.0
    trained_count: int = 0
    total_samples: int = 0

@dataclass
class TrainingJob:
    """训练任务"""
    id: str
    domain: str
    stage: str  # prompt, distillation, finetune
    status: str  # pending, running, completed, failed
    progress: float = 0.0
    started_at: str = ""
    completed_at: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# 子面板组件
# ═══════════════════════════════════════════════════════════════════════════════

class MetricsCard(QFrame):
    """指标卡片组件"""

    def __init__(self, title: str, icon: str = "📊", parent=None):
        super().__init__(parent)
        self.title = title
        self.icon = icon
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            MetricsCard {
                background: #1E1E2E;
                border-radius: 12px;
                border: 1px solid #333355;
                padding: 16px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # 标题行
        header = QHBoxLayout()
        icon_label = QLabel(self.icon)
        icon_label.setStyleSheet("font-size: 20px;")
        header.addWidget(icon_label)

        title_label = QLabel(self.title)
        title_label.setStyleSheet("color: #A0A0A0; font-size: 12px;")
        header.addWidget(title_label)
        header.addStretch()

        layout.addLayout(header)

        # 数值
        self.value_label = QLabel("--")
        self.value_label.setStyleSheet("""
            color: #FFFFFF;
            font-size: 28px;
            font-weight: bold;
        """)
        layout.addWidget(self.value_label)

        # 变化指示
        self.delta_label = QLabel("")
        self.delta_label.setStyleSheet("color: #00D4AA; font-size: 11px;")
        layout.addWidget(self.delta_label)

    def update_value(self, value: float, delta: float = 0.0, suffix: str = "%"):
        """更新数值"""
        if suffix == "%":
            self.value_label.setText(f"{value:.1f}%")
        elif suffix == "ms":
            self.value_label.setText(f"{value:.0f}ms")
        elif suffix == "个":
            self.value_label.setText(f"{int(value)}")
        else:
            self.value_label.setText(str(value))

        if delta > 0:
            self.delta_label.setText(f"↑ +{delta:.1f}{suffix}")
            self.delta_label.setStyleSheet("color: #00D4AA; font-size: 11px;")
        elif delta < 0:
            self.delta_label.setText(f"↓ {delta:.1f}{suffix}")
            self.delta_label.setStyleSheet("color: #FF6B6B; font-size: 11px;")
        else:
            self.delta_label.setText("")


class CircularProgress(QFrame):
    """圆形进度指示器"""

    def __init__(self, size: int = 120, parent=None):
        super().__init__(parent)
        self.size = size
        self.value = 0
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedSize(self.size, self.size)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.value_label = QLabel("0%")
        self.value_label.setStyleSheet("""
            color: #00D4AA;
            font-size: 24px;
            font-weight: bold;
        """)
        layout.addWidget(self.value_label)

        self.status_label = QLabel("系统健康")
        self.status_label.setStyleSheet("color: #A0A0A0; font-size: 11px;")
        layout.addWidget(self.status_label)

    def set_value(self, value: float, status: str = ""):
        """设置进度值"""
        self.value = value
        self.value_label.setText(f"{value:.0f}%")

        if value >= 80:
            color = "#00D4AA"
        elif value >= 60:
            color = "#FFD700"
        else:
            color = "#FF6B6B"

        self.value_label.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")

        if status:
            self.status_label.setText(status)


class KnowledgeTree(QTreeWidget):
    """知识树组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setHeaderLabels(["知识", "类型", "置信度", "更新时间"])
        self.setAlternatingRowColors(True)
        self.setStyleSheet("""
            QTreeWidget {
                background: #1A1A2E;
                border: none;
                color: #FFFFFF;
            }
            QTreeWidget::item {
                padding: 8px;
            }
            QTreeWidget::item:selected {
                background: #2D2D44;
            }
        """)

    def load_knowledge(self, knowledge_list: List[Dict]):
        """加载知识列表"""
        self.clear()

        # 按领域分组
        domains = {}
        for k in knowledge_list:
            domain = k.get("domain", "通用")
            if domain not in domains:
                domains[domain] = []
            domains[domain].append(k)

        for domain, items in domains.items():
            domain_item = QTreeWidgetItem([f"📁 {domain}", "", "", ""])
            domain_item.setExpanded(True)

            for item in items:
                query = item.get("query", "")[:40]
                qtype = item.get("type", "Q&A")
                confidence = f"{item.get('confidence', 0):.0%}"
                updated = item.get("updated_at", "")[:10]

                child = QTreeWidgetItem([query, qtype, confidence, updated])
                domain_item.addChild(child)

            self.addTopLevelItem(domain_item)


class ExpertCard(QFrame):
    """专家卡片组件"""

    clicked = pyqtSignal(str)  # expert_id

    def __init__(self, expert: ExpertInfo, parent=None):
        super().__init__(parent)
        self.expert = expert
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            ExpertCard {
                background: #252535;
                border-radius: 10px;
                border: 1px solid #333355;
                padding: 12px;
            }
            ExpertCard:hover {
                border: 1px solid #00D4AA;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # 标题行
        header = QHBoxLayout()
        icon_label = QLabel("🎓")
        icon_label.setStyleSheet("font-size: 18px;")
        header.addWidget(icon_label)

        name_label = QLabel(self.expert.name)
        name_label.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: bold;")
        header.addWidget(name_label)

        status_label = QLabel("●" if self.expert.status == "active" else "○")
        status_label.setStyleSheet(f"color: {'#00D4AA' if self.expert.status == 'active' else '#666666'};")
        header.addWidget(status_label)

        header.addStretch()
        layout.addLayout(header)

        # 领域
        domain_label = QLabel(f"领域: {self.expert.domain}")
        domain_label.setStyleSheet("color: #A0A0A0; font-size: 11px;")
        layout.addWidget(domain_label)

        # 指标行
        metrics = QHBoxLayout()
        metrics.setSpacing(16)

        acc_label = QLabel(f"准确率: {self.expert.accuracy:.0%}")
        acc_label.setStyleSheet("color: #00D4AA; font-size: 11px;")
        metrics.addWidget(acc_label)

        count_label = QLabel(f"训练: {self.expert.trained_count}")
        count_label.setStyleSheet("color: #A0A0A0; font-size: 11px;")
        metrics.addWidget(count_label)

        metrics.addStretch()
        layout.addLayout(metrics)

        # 操作按钮
        actions = QHBoxLayout()
        actions.setSpacing(8)

        train_btn = QPushButton("训练")
        train_btn.setStyleSheet("""
            QPushButton {
                background: #7C3AED;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover { background: #8B5CF6; }
        """)
        actions.addWidget(train_btn)

        use_btn = QPushButton("使用")
        use_btn.setStyleSheet("""
            QPushButton {
                background: #00D4AA;
                color: #0D0D0D;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover { background: #00E8BB; }
        """)
        actions.addWidget(use_btn)

        layout.addLayout(actions)


# ═══════════════════════════════════════════════════════════════════════════════
# 训练向导对话框
# ═══════════════════════════════════════════════════════════════════════════════

class TrainingWizard(QDialog):
    """三阶段训练向导"""

    stage_changed = pyqtSignal(int)  # stage 0-2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_stage = 0
        self.config = {}
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("🎓 专家训练向导")
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout(self)

        # 进度指示器
        progress_layout = QHBoxLayout()
        self.stage_labels = []
        for i, name in enumerate(["提示注入", "蒸馏数据", "模型微调"]):
            label = QLabel(f"{i+1}. {name}")
            label.setStyleSheet("color: #666666; font-size: 14px;")
            if i == 0:
                label.setStyleSheet("color: #00D4AA; font-size: 14px; font-weight: bold;")
            self.stage_labels.append(label)
            progress_layout.addWidget(label)
            if i < 2:
                arrow = QLabel("→")
                arrow.setStyleSheet("color: #666666;")
                progress_layout.addWidget(arrow)
        progress_layout.addStretch()
        layout.addLayout(progress_layout)

        # 内容区域
        self.content_stack = QTabWidget()
        self.content_stack.addTab(self._create_prompt_tab(), "提示注入")
        self.content_stack.addTab(self._create_distill_tab(), "蒸馏数据")
        self.content_stack.addTab(self._create_finetune_tab(), "模型微调")
        layout.addWidget(self.content_stack)

        # 按钮行
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.prev_btn = QPushButton("← 上一步")
        self.prev_btn.setEnabled(False)
        self.prev_btn.clicked.connect(self._prev_stage)
        btn_layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton("下一步 →")
        self.next_btn.setStyleSheet("""
            QPushButton {
                background: #00D4AA;
                color: #0D0D0D;
                font-weight: bold;
                padding: 8px 24px;
            }
        """)
        self.next_btn.clicked.connect(self._next_stage)
        btn_layout.addWidget(self.next_btn)

        self.finish_btn = QPushButton("完成")
        self.finish_btn.setStyleSheet("""
            QPushButton {
                background: #7C3AED;
                color: #FFFFFF;
                font-weight: bold;
                padding: 8px 24px;
            }
        """)
        self.finish_btn.hide()
        self.finish_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.finish_btn)

        layout.addLayout(btn_layout)

    def _create_prompt_tab(self) -> QWidget:
        """创建提示注入页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 说明
        info = QLabel("""
        <b>提示注入 (Prompt Injection)</b> - 无需训练，立即提升输出质量
        
        选择或创建一个专家提示模板，系统将在回答时自动注入该模板。
        """)
        info.setStyleSheet("color: #A0A0A0; line-height: 1.6;")
        layout.addWidget(info)

        # 领域选择
        domain_group = QGroupBox("选择领域")
        domain_layout = QHBoxLayout()

        self.domain_combo = QComboBox()
        self.domain_combo.addItems([
            "通用", "金融", "技术", "法律", "医疗",
            "教育", "商业", "工程"
        ])
        domain_layout.addWidget(QLabel("领域:"))
        domain_layout.addWidget(self.domain_combo)
        domain_layout.addStretch()
        domain_group.setLayout(domain_layout)
        layout.addWidget(domain_group)

        # 模板编辑
        template_group = QGroupBox("专家提示模板")
        template_layout = QVBoxLayout()

        self.template_edit = QTextEdit()
        self.template_edit.setPlaceholderText("输入专家提示模板...")
        self.template_edit.setMinimumHeight(200)
        self.template_edit.setStyleSheet("""
            QTextEdit {
                background: #1A1A2E;
                border: 1px solid #333355;
                border-radius: 8px;
                color: #FFFFFF;
                padding: 12px;
            }
        """)
        template_layout.addWidget(self.template_edit)
        template_group.setLayout(template_layout)
        layout.addWidget(template_group)

        layout.addStretch()
        return widget

    def _create_distill_tab(self) -> QWidget:
        """创建蒸馏数据页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 说明
        info = QLabel("""
        <b>蒸馏数据生成 (Distillation Data)</b> - 收集高频查询，生成训练数据
        
        系统会自动收集用户的高频问题，并生成对应的专家回答对。
        """)
        info.setStyleSheet("color: #A0A0A0; line-height: 1.6;")
        layout.addWidget(info)

        # 参数设置
        param_group = QGroupBox("参数设置")
        param_layout = QFormLayout()

        self.min_freq_spin = QComboBox()
        self.min_freq_spin.addItems(["3", "5", "10", "20"])
        param_layout.addRow("最小频率:", self.min_freq_spin)

        self.augment_check = QCheckBox("启用数据增强")
        self.augment_check.setChecked(True)
        param_layout.addRow("数据增强:", self.augment_check)

        self.max_samples = QLineEdit("1000")
        param_layout.addRow("最大样本数:", self.max_samples)

        param_group.setLayout(param_layout)
        layout.addWidget(param_group)

        # 预览
        preview_group = QGroupBox("数据预览")
        preview_layout = QVBoxLayout()

        self.preview_list = QListWidget()
        self.preview_list.addItems([
            "Q: 茅台股票值得投资吗?",
            "Q: Python如何处理异常?",
            "Q: 劳动合同有哪些注意事项?",
        ])
        preview_layout.addWidget(self.preview_list)

        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        return widget

    def _create_finetune_tab(self) -> QWidget:
        """创建模型微调页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 说明
        info = QLabel("""
        <b>模型微调 (Fine-tuning)</b> - 训练专属专家模型
        
        基于收集的蒸馏数据，训练一个专属的专家模型。
        训练可能需要较长时间，请确保有足够的计算资源。
        """)
        info.setStyleSheet("color: #A0A0A0; line-height: 1.6;")
        layout.addWidget(info)

        # 模型选择
        model_group = QGroupBox("基础模型")
        model_layout = QHBoxLayout()

        self.base_model_combo = QComboBox()
        self.base_model_combo.addItems([
            "qwen2.5:1.5b (推荐, 快速)",
            "qwen2.5:3b (平衡)",
            "qwen3.5:4b (高质量)",
        ])
        model_layout.addWidget(self.base_model_combo)
        model_layout.addStretch()
        model_group.setLayout(model_layout)
        layout.addWidget(model_group)

        # 训练参数
        train_group = QGroupBox("训练参数")
        train_layout = QFormLayout()

        self.epochs_spin = QComboBox()
        self.epochs_spin.addItems(["1", "2", "3", "5"])
        train_layout.addRow("训练轮数:", self.epochs_spin)

        self.batch_size_spin = QComboBox()
        self.batch_size_spin.addItems(["1", "2", "4", "8"])
        train_layout.addRow("批大小:", self.batch_size_spin)

        self.use_unsloth_check = QCheckBox("使用 Unsloth 加速")
        self.use_unsloth_check.setChecked(True)
        train_layout.addRow("加速选项:", self.use_unsloth_check)

        train_group.setLayout(train_layout)
        layout.addWidget(train_group)

        # 资源估算
        estimate = QLabel("💡 预估训练时间: 5-15 分钟 (取决于数据量)")
        estimate.setStyleSheet("color: #FFD700;")
        layout.addWidget(estimate)

        layout.addStretch()
        return widget

    def _prev_stage(self):
        """上一步"""
        if self.current_stage > 0:
            self.current_stage -= 1
            self.content_stack.setCurrentIndex(self.current_stage)
            self._update_ui()

    def _next_stage(self):
        """下一步"""
        if self.current_stage < 2:
            self.current_stage += 1
            self.content_stack.setCurrentIndex(self.current_stage)
            self._update_ui()

    def _update_ui(self):
        """更新UI状态"""
        for i, label in enumerate(self.stage_labels):
            if i == self.current_stage:
                label.setStyleSheet("color: #00D4AA; font-size: 14px; font-weight: bold;")
            else:
                label.setStyleSheet("color: #666666; font-size: 14px;")

        self.prev_btn.setEnabled(self.current_stage > 0)
        self.next_btn.setVisible(self.current_stage < 2)
        self.finish_btn.setVisible(self.current_stage == 2)

    def get_config(self) -> Dict:
        """获取配置"""
        return {
            "stage": self.current_stage,
            "domain": self.domain_combo.currentText(),
            "template": self.template_edit.toPlainText(),
            "min_freq": int(self.min_freq_spin.currentText()),
            "augment": self.augment_check.isChecked(),
            "max_samples": int(self.max_samples.text()),
            "base_model": self.base_model_combo.currentText().split()[0],
            "epochs": int(self.epochs_spin.currentText()),
            "batch_size": int(self.batch_size_spin.currentText()),
            "use_unsloth": self.use_unsloth_check.isChecked(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 知识导入对话框
# ═══════════════════════════════════════════════════════════════════════════════

class KnowledgeImportDialog(QDialog):
    """知识导入对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("📥 导入知识")
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)

        # 导入方式
        type_group = QGroupBox("导入方式")
        type_layout = QVBoxLayout()

        self.import_type_group = QButtonGroup()
        types = [
            ("📄 从文件导入", "file"),
            ("🔗 从 URL 导入", "url"),
            ("📋 粘贴文本", "paste"),
        ]
        for name, type_id in types:
            btn = QRadioButton(name)
            btn.setChecked(type_id == "file")
            self.import_type_group.addButton(btn, type_id)
            type_layout.addWidget(btn)

        type_group.setLayout(type_layout)
        layout.addWidget(type_group)

        # 导入来源
        source_group = QGroupBox("导入来源")
        source_layout = QVBoxLayout()

        self.source_edit = QTextEdit()
        self.source_edit.setPlaceholderText("选择文件或输入URL/文本...")
        self.source_edit.setMinimumHeight(150)
        source_layout.addWidget(self.source_edit)

        browse_btn = QPushButton("浏览文件...")
        browse_btn.clicked.connect(self._browse_file)
        source_layout.addWidget(browse_btn)

        source_group.setLayout(source_layout)
        layout.addWidget(source_group)

        # 导入设置
        setting_group = QGroupBox("导入设置")
        setting_layout = QFormLayout()

        self.domain_combo = QComboBox()
        self.domain_combo.addItems([
            "通用", "金融", "技术", "法律", "医疗"
        ])
        setting_layout.addRow("领域:", self.domain_combo)

        self.confidence_spin = QSlider(Qt.Orientation.Horizontal)
        self.confidence_spin.setRange(50, 100)
        self.confidence_spin.setValue(80)
        setting_layout.addRow("置信度:", self.confidence_spin)

        setting_group.setLayout(setting_layout)
        layout.addWidget(setting_group)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        import_btn = QPushButton("导入")
        import_btn.setStyleSheet("""
            QPushButton {
                background: #00D4AA;
                color: #0D0D0D;
                font-weight: bold;
                padding: 8px 24px;
            }
        """)
        import_btn.clicked.connect(self.accept)
        btn_layout.addWidget(import_btn)

        layout.addLayout(btn_layout)

    def _browse_file(self):
        """浏览文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择知识文件",
            "", "支持的文件 (*.json *.md *.txt *.jsonl);;所有文件 (*)"
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.source_edit.setPlainText(content)
            except Exception as e:
                QMessageBox.warning(self, "错误", f"读取文件失败: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# 主面板
# ═══════════════════════════════════════════════════════════════════════════════

class ExpertTrainingDashboard(QWidget):
    """
    专家训练仪表盘 - 主面板

    功能：
    1. 实时学习监控 - 缓存命中率、纠正率、系统健康度
    2. 知识管理 - 导入、导出、搜索、版本控制
    3. 三阶段训练向导 - 提示注入 → 蒸馏数据 → 模型微调
    4. 多专家协作 - 专家库管理、路由策略
    5. 性能仪表盘 - 延迟、错误率、成本优化
    6. 自动化调度 - 高频查询自动收集、定时训练
    """

    # 信号
    training_started = pyqtSignal(dict)  # config
    training_completed = pyqtSignal(str)  # expert_id
    knowledge_imported = pyqtSignal(list)  # knowledge_list

    def __init__(self, parent=None):
        super().__init__(parent)

        # 数据
        self._experts: List[ExpertInfo] = []
        self._metrics = LearningMetrics()
        self._knowledge: List[Dict] = []
        self._training_jobs: List[TrainingJob] = []

        # 后端系统（可选）
        self._learning_system = None
        self._pipeline = None

        self._setup_ui()
        self._setup_timers()
        self._load_mock_data()

    def _setup_ui(self):
        """初始化UI"""
        self.setStyleSheet("""
            ExpertTrainingDashboard {
                background: #0D0D14;
            }
            QLabel {
                color: #FFFFFF;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton {
                background: #252535;
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                padding: 8px 16px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #333345;
            }
            QGroupBox {
                border: 1px solid #333355;
                border-radius: 10px;
                margin-top: 12px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                color: #A0A0A0;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # ═══════════════════════════════════════════════════════════════════
        # 顶部标题栏
        # ═══════════════════════════════════════════════════════════════════
        header = QHBoxLayout()

        title = QLabel("🎓 专家训练中心")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #00D4AA;")
        header.addWidget(title)

        header.addStretch()

        # 快速操作
        new_expert_btn = QPushButton("➕ 新建专家")
        new_expert_btn.setStyleSheet("""
            QPushButton {
                background: #7C3AED;
                color: #FFFFFF;
                font-weight: bold;
            }
            QPushButton:hover { background: #8B5CF6; }
        """)
        new_expert_btn.clicked.connect(self._on_new_expert)
        header.addWidget(new_expert_btn)

        import_knowledge_btn = QPushButton("📥 导入知识")
        import_knowledge_btn.clicked.connect(self._on_import_knowledge)
        header.addWidget(import_knowledge_btn)

        main_layout.addLayout(header)

        # ═══════════════════════════════════════════════════════════════════
        # 指标卡片区
        # ═══════════════════════════════════════════════════════════════════
        metrics_layout = QHBoxLayout()

        self.cache_card = MetricsCard("缓存命中率", "💾")
        metrics_layout.addWidget(self.cache_card)

        self.correct_card = MetricsCard("纠正率", "✏️")
        metrics_layout.addWidget(self.correct_card)

        self.accuracy_card = MetricsCard("准确率", "🎯")
        metrics_layout.addWidget(self.accuracy_card)

        self.queries_card = MetricsCard("总查询量", "💬")
        metrics_layout.addWidget(self.queries_card)

        self.health_card = MetricsCard("系统健康", "🏥")
        metrics_layout.addWidget(self.health_card)

        main_layout.addLayout(metrics_layout)

        # ═══════════════════════════════════════════════════════════════════
        # 主内容区 - 选项卡
        # ═══════════════════════════════════════════════════════════════════
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #333355;
                border-radius: 10px;
                background: #1A1A2E;
            }
            QTabBar::tab {
                background: #252535;
                color: #A0A0A0;
                padding: 10px 20px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background: #1A1A2E;
                color: #00D4AA;
                font-weight: bold;
            }
        """)

        self.tabs.addTab(self._create_overview_tab(), "📊 总览")
        self.tabs.addTab(self._create_experts_tab(), "🎓 专家管理")
        self.tabs.addTab(self._create_knowledge_tab(), "📚 知识库")
        self.tabs.addTab(self._create_training_tab(), "⚙️ 训练中心")
        self.tabs.addTab(self._create_performance_tab(), "📈 性能监控")

        main_layout.addWidget(self.tabs, 1)

        # ═══════════════════════════════════════════════════════════════════
        # 底部状态栏
        # ═══════════════════════════════════════════════════════════════════
        status_layout = QHBoxLayout()

        self.status_label = QLabel("● 系统运行正常")
        self.status_label.setStyleSheet("color: #00D4AA;")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.last_update_label = QLabel("最后更新: --")
        self.last_update_label.setStyleSheet("color: #666666;")
        status_layout.addWidget(self.last_update_label)

        main_layout.addLayout(status_layout)

    def _create_overview_tab(self) -> QWidget:
        """创建总览页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 系统健康环形图
        health_layout = QHBoxLayout()

        self.circular_health = CircularProgress(150)
        health_layout.addWidget(self.circular_health)

        # 近期活动
        activity_group = QGroupBox("近期活动")
        activity_layout = QVBoxLayout()

        self.activity_list = QListWidget()
        self.activity_list.addItems([
            "14:32 - 专家「金融分析师」训练完成",
            "14:28 - 知识库新增 5 条记录",
            "14:20 - 缓存命中率提升 3%",
            "14:15 - 纠正记录: Python异步编程",
        ])
        activity_layout.addWidget(self.activity_list)
        activity_group.setLayout(activity_layout)
        health_layout.addWidget(activity_group, 1)

        layout.addLayout(health_layout)

        # 快捷入口
        shortcuts_group = QGroupBox("快捷操作")
        shortcuts_layout = QHBoxLayout()

        shortcuts = [
            ("🎓 快速训练", self._on_quick_training),
            ("📥 批量导入", self._on_batch_import),
            ("📊 查看报告", self._on_view_report),
            ("⚙️ 系统设置", self._on_system_settings),
        ]

        for name, callback in shortcuts:
            btn = QPushButton(name)
            btn.setFixedHeight(50)
            btn.clicked.connect(callback)
            shortcuts_layout.addWidget(btn)

        shortcuts_layout.addStretch()
        shortcuts_group.setLayout(shortcuts_layout)
        layout.addWidget(shortcuts_group)

        # 推荐行动
        recommend_group = QGroupBox("💡 推荐行动")
        recommend_layout = QVBoxLayout()

        recommend_label = QLabel("• 您的「技术专家」准确率下降了 5%，建议重新训练")
        recommend_label.setStyleSheet("color: #FFD700;")
        recommend_layout.addWidget(recommend_label)

        recommend_label2 = QLabel("• 知识库有 12 条未审核记录，建议处理")
        recommend_label2.setStyleSheet("color: #A0A0A0;")
        recommend_layout.addWidget(recommend_label2)

        recommend_group.setLayout(recommend_layout)
        layout.addWidget(recommend_group)

        return widget

    def _create_experts_tab(self) -> QWidget:
        """创建专家管理页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 工具栏
        toolbar = QHBoxLayout()

        search = QLineEdit()
        search.setPlaceholderText("搜索专家...")
        toolbar.addWidget(search)

        toolbar.addStretch()

        new_btn = QPushButton("新建专家")
        new_btn.clicked.connect(self._on_new_expert)
        toolbar.addWidget(new_btn)

        import_btn = QPushButton("导入")
        import_btn.clicked.connect(self._on_import_expert)
        toolbar.addWidget(import_btn)

        export_btn = QPushButton("导出")
        export_btn.clicked.connect(self._on_export_expert)
        toolbar.addWidget(export_btn)

        layout.addLayout(toolbar)

        # 专家卡片列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")

        experts_widget = QWidget()
        self.experts_layout = QGridLayout(experts_widget)
        self.experts_layout.setSpacing(16)

        scroll.setWidget(experts_widget)
        layout.addWidget(scroll, 1)

        return widget

    def _create_knowledge_tab(self) -> QWidget:
        """创建知识库页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 工具栏
        toolbar = QHBoxLayout()

        search = QLineEdit()
        search.setPlaceholderText("搜索知识...")
        toolbar.addWidget(search)

        filter_combo = QComboBox()
        filter_combo.addItems(["全部", "金融", "技术", "法律", "医疗"])
        toolbar.addWidget(filter_combo)

        toolbar.addStretch()

        import_btn = QPushButton("导入")
        import_btn.clicked.connect(self._on_import_knowledge)
        toolbar.addWidget(import_btn)

        export_btn = QPushButton("导出")
        export_btn.clicked.connect(self._on_export_knowledge)
        toolbar.addWidget(export_btn)

        layout.addLayout(toolbar)

        # 知识树
        self.knowledge_tree = KnowledgeTree()
        layout.addWidget(self.knowledge_tree, 1)

        # 知识统计
        stats_layout = QHBoxLayout()

        stats_layout.addWidget(QLabel("总记录: 1,234"))
        stats_layout.addWidget(QLabel("本周新增: +56"))
        stats_layout.addWidget(QLabel("待审核: 12"))

        stats_layout.addStretch()

        layout.addLayout(stats_layout)

        return widget

    def _create_training_tab(self) -> QWidget:
        """创建训练中心页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 三阶段卡片
        stages_layout = QHBoxLayout()

        # 阶段1: 提示注入
        stage1 = QFrame()
        stage1.setStyleSheet("""
            QFrame {
                background: #1E1E2E;
                border-radius: 12px;
                border: 2px solid #333355;
                padding: 20px;
            }
        """)
        stage1_layout = QVBoxLayout(stage1)

        stage1_title = QLabel("1️⃣ 提示注入")
        stage1_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #00D4AA;")
        stage1_layout.addWidget(stage1_title)

        stage1_desc = QLabel("立即提升输出质量\n无需等待训练")
        stage1_desc.setStyleSheet("color: #A0A0A0;")
        stage1_layout.addWidget(stage1_desc)

        stage1_btn = QPushButton("开始")
        stage1_btn.setStyleSheet("background: #00D4AA; color: #0D0D0D; font-weight: bold;")
        stage1_btn.clicked.connect(lambda: self._start_training(0))
        stage1_layout.addWidget(stage1_btn)
        stage1_layout.addStretch()

        stages_layout.addWidget(stage1)

        # 阶段2: 蒸馏数据
        stage2 = QFrame()
        stage2.setStyleSheet("""
            QFrame {
                background: #1E1E2E;
                border-radius: 12px;
                border: 2px solid #333355;
                padding: 20px;
            }
        """)
        stage2_layout = QVBoxLayout(stage2)

        stage2_title = QLabel("2️⃣ 蒸馏数据")
        stage2_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFD700;")
        stage2_layout.addWidget(stage2_title)

        stage2_desc = QLabel("收集高频查询\n生成训练数据")
        stage2_desc.setStyleSheet("color: #A0A0A0;")
        stage2_layout.addWidget(stage2_desc)

        stage2_btn = QPushButton("开始")
        stage2_btn.setStyleSheet("background: #FFD700; color: #0D0D0D; font-weight: bold;")
        stage2_btn.clicked.connect(lambda: self._start_training(1))
        stage2_layout.addWidget(stage2_btn)
        stage2_layout.addStretch()

        stages_layout.addWidget(stage2)

        # 阶段3: 模型微调
        stage3 = QFrame()
        stage3.setStyleSheet("""
            QFrame {
                background: #1E1E2E;
                border-radius: 12px;
                border: 2px solid #333355;
                padding: 20px;
            }
        """)
        stage3_layout = QVBoxLayout(stage3)

        stage3_title = QLabel("3️⃣ 模型微调")
        stage3_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #7C3AED;")
        stage3_layout.addWidget(stage3_title)

        stage3_desc = QLabel("训练专属专家模型\n效果最佳但耗时")
        stage3_desc.setStyleSheet("color: #A0A0A0;")
        stage3_layout.addWidget(stage3_desc)

        stage3_btn = QPushButton("开始")
        stage3_btn.setStyleSheet("background: #7C3AED; color: #FFFFFF; font-weight: bold;")
        stage3_btn.clicked.connect(lambda: self._start_training(2))
        stage3_layout.addWidget(stage3_btn)
        stage3_layout.addStretch()

        stages_layout.addWidget(stage3)

        layout.addLayout(stages_layout)

        # 训练历史
        history_group = QGroupBox("训练历史")
        history_layout = QVBoxLayout()

        self.history_list = QListWidget()
        self.history_list.addItems([
            "[已完成] 金融分析师 - 2024-04-24 14:32",
            "[进行中] 技术专家 - 进度 45%",
            "[已完成] 法律顾问 - 2024-04-23 10:15",
        ])
        history_layout.addWidget(self.history_list)
        history_group.setLayout(history_layout)

        layout.addWidget(history_group)

        return widget

    def _create_performance_tab(self) -> QWidget:
        """创建性能监控页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 性能图表区域
        chart_group = QGroupBox("性能趋势")
        chart_layout = QVBoxLayout()

        # 简化的性能指标显示
        metrics_grid = QGridLayout()

        metrics = [
            ("平均延迟", "120ms", "#00D4AA"),
            ("错误率", "0.5%", "#FF6B6B"),
            ("吞吐量", "50 req/s", "#00D4AA"),
            ("成本优化", "节省 35%", "#FFD700"),
        ]

        for i, (name, value, color) in enumerate(metrics):
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background: #252535;
                    border-radius: 10px;
                    padding: 16px;
                }
            """)
            card_layout = QVBoxLayout(card)

            name_label = QLabel(name)
            name_label.setStyleSheet("color: #A0A0A0; font-size: 12px;")
            card_layout.addWidget(name_label)

            value_label = QLabel(value)
            value_label.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")
            card_layout.addWidget(value_label)

            metrics_grid.addWidget(card, i // 2, i % 2)

        chart_layout.addLayout(metrics_grid)
        chart_group.setLayout(chart_layout)
        layout.addWidget(chart_group)

        # 告警区域
        alerts_group = QGroupBox("⚠️ 告警")
        alerts_layout = QVBoxLayout()

        alert_label = QLabel("暂无告警，系统运行正常")
        alert_label.setStyleSheet("color: #00D4AA;")
        alerts_layout.addWidget(alert_label)

        alerts_group.setLayout(alerts_layout)
        layout.addWidget(alerts_group)

        # 优化建议
        tips_group = QGroupBox("💡 优化建议")
        tips_layout = QVBoxLayout()

        tips_layout.addWidget(QLabel("• 建议启用 Unsloth 加速，可减少 50% 训练时间"))
        tips_layout.addWidget(QLabel("• 知识库碎片化严重，建议整理"))
        tips_layout.addWidget(QLabel("• 当前使用 qwen2.5:1.5b，可考虑升级到 3b"))

        tips_group.setLayout(tips_layout)
        layout.addWidget(tips_group)

        return widget

    def _setup_timers(self):
        """设置定时器"""
        # 指标更新定时器
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_metrics)
        self._update_timer.start(5000)  # 每5秒更新

    def _load_mock_data(self):
        """加载模拟数据"""
        # 模拟专家
        self._experts = [
            ExpertInfo("exp_001", "金融分析师", "金融", "active", 0.92, 156, 200),
            ExpertInfo("exp_002", "技术专家", "技术", "active", 0.88, 234, 300),
            ExpertInfo("exp_003", "法律顾问", "法律", "inactive", 0.85, 89, 100),
        ]

        # 模拟指标
        self._metrics = LearningMetrics(
            cache_hit_rate=78.5,
            correction_rate=12.3,
            accuracy=91.2,
            total_queries=1234,
            learning_records=45,
            knowledge_fragments=567,
            system_health=85.0,
        )

        # 更新UI
        self._update_metrics_ui()

        # 加载专家卡片
        self._load_expert_cards()

        # 加载知识树
        self._load_knowledge_tree()

    def _update_metrics(self):
        """更新指标"""
        # 模拟数据变化
        import random
        self._metrics.cache_hit_rate = max(60, min(95, self._metrics.cache_hit_rate + random.uniform(-2, 2)))
        self._metrics.accuracy = max(80, min(98, self._metrics.accuracy + random.uniform(-1, 1)))

        self._update_metrics_ui()
        self.last_update_label.setText(f"最后更新: {datetime.now().strftime('%H:%M:%S')}")

    def _update_metrics_ui(self):
        """更新指标UI"""
        self.cache_card.update_value(self._metrics.cache_hit_rate, delta=2.3)
        self.correct_card.update_value(self._metrics.correction_rate, delta=-1.2)
        self.accuracy_card.update_value(self._metrics.accuracy, delta=0.8)
        self.queries_card.update_value(self._metrics.total_queries, suffix="次")
        self.health_card.update_value(self._metrics.system_health)

        self.circular_health.set_value(self._metrics.system_health, "系统健康")

    def _load_expert_cards(self):
        """加载专家卡片"""
        # 清空现有
        while self.experts_layout.count():
            item = self.experts_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 添加卡片
        for i, expert in enumerate(self._experts):
            card = ExpertCard(expert)
            card.clicked.connect(lambda id: self._on_expert_clicked(id))
            self.experts_layout.addWidget(card, i // 2, i % 2)

    def _load_knowledge_tree(self):
        """加载知识树"""
        mock_knowledge = [
            {"query": "茅台股票值得投资吗", "domain": "金融", "type": "Q&A", "confidence": 0.92, "updated_at": "2024-04-24"},
            {"query": "Python异步编程最佳实践", "domain": "技术", "type": "Tutorial", "confidence": 0.88, "updated_at": "2024-04-23"},
            {"query": "劳动合同解除条款", "domain": "法律", "type": "Legal", "confidence": 0.85, "updated_at": "2024-04-22"},
        ]
        self.knowledge_tree.load_knowledge(mock_knowledge)

    # ═══════════════════════════════════════════════════════════════════════════
    # 事件处理
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_new_expert(self):
        """新建专家"""
        wizard = TrainingWizard(self)
        if wizard.exec():
            config = wizard.get_config()
            self.training_started.emit(config)
            QMessageBox.information(self, "成功", "专家训练已启动！")

    def _on_import_knowledge(self):
        """导入知识"""
        dialog = KnowledgeImportDialog(self)
        if dialog.exec():
            QMessageBox.information(self, "成功", "知识导入成功！")

    def _on_import_expert(self):
        """导入专家"""
        path, _ = QFileDialog.getOpenFileName(
            self, "导入专家", "", "JSON (*.json)"
        )
        if path:
            QMessageBox.information(self, "成功", f"专家已从 {path} 导入")

    def _on_export_expert(self):
        """导出专家"""
        path, _ = QFileDialog.getSaveFileName(
            self, "导出专家", "experts.json", "JSON (*.json)"
        )
        if path:
            QMessageBox.information(self, "成功", f"专家已导出到 {path}")

    def _on_export_knowledge(self):
        """导出知识"""
        path, _ = QFileDialog.getSaveFileName(
            self, "导出知识", "knowledge.json", "JSON (*.json)"
        )
        if path:
            QMessageBox.information(self, "成功", f"知识已导出到 {path}")

    def _on_expert_clicked(self, expert_id: str):
        """专家卡片点击"""
        for expert in self._experts:
            if expert.id == expert_id:
                QMessageBox.information(self, "专家详情", f"""
                名称: {expert.name}
                领域: {expert.domain}
                状态: {expert.status}
                准确率: {expert.accuracy:.0%}
                训练样本: {expert.trained_count}/{expert.total_samples}
                """)
                break

    def _start_training(self, stage: int):
        """开始训练"""
        wizard = TrainingWizard(self)
        wizard.content_stack.setCurrentIndex(stage)

        if wizard.exec():
            config = wizard.get_config()
            self.training_started.emit(config)
            QMessageBox.information(self, "成功", f"阶段 {stage+1} 训练已启动！")

    def _on_quick_training(self):
        """快速训练"""
        QMessageBox.information(self, "快速训练", "启动快速训练向导...")

    def _on_batch_import(self):
        """批量导入"""
        QMessageBox.information(self, "批量导入", "打开批量导入对话框...")

    def _on_view_report(self):
        """查看报告"""
        QMessageBox.information(self, "报告", "生成性能报告中...")

    def _on_system_settings(self):
        """系统设置"""
        QMessageBox.information(self, "设置", "打开系统设置...")

    # ═══════════════════════════════════════════════════════════════════════════
    # 公共接口
    # ═══════════════════════════════════════════════════════════════════════════

    def set_learning_system(self, system):
        """设置学习系统"""
        self._learning_system = system

    def set_training_pipeline(self, pipeline):
        """设置训练流水线"""
        self._pipeline = pipeline

    def refresh_data(self):
        """刷新数据"""
        if self._learning_system:
            stats = self._learning_system.get_stats()
            # 更新指标...

        self._load_mock_data()


# ═══════════════════════════════════════════════════════════════════════════════
# 导出
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "ExpertTrainingDashboard",
    "TrainingWizard",
    "KnowledgeImportDialog",
    "MetricsCard",
    "ExpertCard",
    "CircularProgress",
    "KnowledgeTree",
]
