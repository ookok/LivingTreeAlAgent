# -*- coding: utf-8 -*-
"""
Smart IDE Dashboard - PyQt6 智能IDE仪表盘
==========================================

功能：
- 智能IDE与游戏系统 UI
- 代码编辑器核心
- AI编程助手
- 调试系统
- 记忆增强编辑器
- 协同编辑
- 功能发现引擎
- 游戏化学习

Author: Hermes Desktop Team
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QListWidget,
    QListWidgetItem, QComboBox, QTabWidget, QGroupBox,
    QScrollArea, QFrame, QProgressBar, QTableWidget,
    QTableWidgetItem, QHeaderView, QStatusBar, QMenuBar, QMenu,
    QToolButton, QStackedWidget, QFormLayout, QSpinBox,
    QCheckBox, QMessageBox, QSplitter, QFileDialog,
    QInputDialog, QDialog, QPlainTextEdit, QProgressDialog,
    QApplication, QSizePolicy, QSpacerItem, QScrollBar,
    QDateTimeEdit, QSlider, QDial, QLCDNumber
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, pyqtSlot, QTimer, QRegularExpression, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QRect
from PyQt6.QtGui import QFont, QIcon, QAction, QColor, QPalette, QPainter, QPen, QSyntaxHighlighter, QTextCharFormat, QRegularExpressionValidator, QBrush, QLinearGradient

import asyncio
import json
import time
import os
import subprocess
from datetime import datetime
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from concurrent.futures import ThreadPoolExecutor

from client.src.business.smart_ide_game import (
    SmartIDEGameSystem, CodeEditorCore, AICodingAssistant,
    MemoryEnhancedEditor, CollabEditor, DebuggerManager,
    LanguageType, TaskType, AIRecommendation,
    CodePosition, CompletionItem, Diagnostic, Symbol,
    IDESettings, GameSettings, UserPreferences
)
from client.src.business.github_project_manager import GitHubProjectManager, get_github_project_manager


# ==================== 初始化相关 ====================

class InitializationState(Enum):
    """初始化状态"""
    IDLE = "idle"
    LOADING_CONFIG = "loading_config"
    INITIALIZING_STORAGE = "initializing_storage"
    STARTING_AI = "starting_ai"
    LOADING_PROJECTS = "loading_projects"
    LOADING_SNIPPETS = "loading_snippets"
    INITIALIZING_COLLAB = "initializing_collab"
    READY = "ready"
    ERROR = "error"


@dataclass
class InitializationResult:
    """初始化结果"""
    success: bool
    state: InitializationState
    message: str
    duration_ms: float
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class SystemMetrics:
    """系统指标"""
    files_count: int = 0
    ai_tasks_count: int = 0
    breakpoints_count: int = 0
    memory_items_count: int = 0
    snippets_count: int = 0
    collab_sessions: int = 0
    uptime_seconds: float = 0.0


# ==================== 功能发现引擎 ====================

@dataclass
class FeatureDiscovery:
    """功能发现项"""
    id: str
    name: str
    description: str
    icon: str
    category: str
    priority: int  # 1-5, 5最高
    is_new: bool = False
    usage_count: int = 0
    last_used: Optional[datetime] = None
    tutorial_url: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'category': self.category,
            'priority': self.priority,
            'is_new': self.is_new,
            'usage_count': self.usage_count,
            'last_used': self.last_used.isoformat() if self.last_used else None
        }


class FeatureDiscoveryEngine:
    """功能发现引擎"""

    # 内置功能发现项
    BUILTIN_FEATURES = [
        FeatureDiscovery(
            id='realtime_analysis',
            name='实时代码分析',
            description='实时分析代码质量，发现潜在问题',
            icon='🔍',
            category='coding',
            priority=5,
            is_new=True
        ),
        FeatureDiscovery(
            id='smart_completion',
            name='智能代码补全',
            description='AI驱动的代码补全和建议',
            icon='✨',
            category='coding',
            priority=5,
            is_new=True
        ),
        FeatureDiscovery(
            id='auto_fix',
            name='一键错误修复',
            description='自动修复常见代码错误',
            icon='🔧',
            category='coding',
            priority=4
        ),
        FeatureDiscovery(
            id='snippet_manager',
            name='代码片段管理',
            description='管理、搜索、分类代码片段',
            icon='📚',
            category='productivity',
            priority=4
        ),
        FeatureDiscovery(
            id='project_template',
            name='项目模板库',
            description='快速创建项目模板',
            icon='🚀',
            category='productivity',
            priority=3
        ),
        FeatureDiscovery(
            id='auto_doc',
            name='自动文档生成',
            description='根据代码自动生成API文档',
            icon='📖',
            category='documentation',
            priority=3
        ),
        FeatureDiscovery(
            id='test_generator',
            name='测试用例生成',
            description='自动生成单元测试',
            icon='🧪',
            category='testing',
            priority=3
        ),
        FeatureDiscovery(
            id='performance_dashboard',
            name='性能分析仪表盘',
            description='可视化性能瓶颈分析',
            icon='⚡',
            category='performance',
            priority=2
        ),
        FeatureDiscovery(
            id='refactor_assistant',
            name='重构助手',
            description='智能重构建议和预览',
            icon='🔄',
            category='refactoring',
            priority=2
        ),
        FeatureDiscovery(
            id='dependency_graph',
            name='依赖分析图',
            description='可视化依赖关系图',
            icon='🕸️',
            category='analysis',
            priority=2
        ),
        FeatureDiscovery(
            id='collab_editing',
            name='协同编辑',
            description='多人实时协作编辑',
            icon='👥',
            category='collaboration',
            priority=3
        ),
        FeatureDiscovery(
            id='code_review',
            name='代码审查',
            description='AI驱动的代码审查',
            icon='👀',
            category='review',
            priority=2
        ),
        FeatureDiscovery(
            id='gamified_learning',
            name='游戏化学习',
            description='通过游戏学习编程',
            icon='🎮',
            category='learning',
            priority=2
        ),
        FeatureDiscovery(
            id='pair_programming',
            name='配对编程',
            description='AI实时配对编程',
            icon='🤝',
            category='collaboration',
            priority=1
        ),
        FeatureDiscovery(
            id='cross_media',
            name='跨媒体创作',
            description='代码与PPT/文档联动',
            icon='🎨',
            category='creative',
            priority=1
        ),
    ]

    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or os.path.expanduser("~/.hermes-desktop/feature_discovery")
        os.makedirs(self.storage_path, exist_ok=True)
        self.features_file = os.path.join(self.storage_path, "features_usage.json")
        self.features: Dict[str, FeatureDiscovery] = {}
        self._load_features()

    def _load_features(self):
        """加载功能使用数据"""
        # 初始化内置功能
        for feature in self.BUILTIN_FEATURES:
            self.features[feature.id] = feature

        # 加载使用数据
        if os.path.exists(self.features_file):
            try:
                with open(self.features_file, 'r', encoding='utf-8') as f:
                    usage_data = json.load(f)
                    for feature_id, data in usage_data.items():
                        if feature_id in self.features:
                            self.features[feature_id].usage_count = data.get('usage_count', 0)
                            if data.get('last_used'):
                                self.features[feature_id].last_used = datetime.fromisoformat(data['last_used'])
            except Exception:
                pass

    def _save_features(self):
        """保存功能使用数据"""
        try:
            usage_data = {fid: f.to_dict() for fid, f in self.features.items()}
            with open(self.features_file, 'w', encoding='utf-8') as f:
                json.dump(usage_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_all_features(self) -> List[FeatureDiscovery]:
        """获取所有功能"""
        return list(self.features.values())

    def get_features_by_category(self, category: str) -> List[FeatureDiscovery]:
        """按类别获取功能"""
        return [f for f in self.features.values() if f.category == category]

    def get_new_features(self) -> List[FeatureDiscovery]:
        """获取新功能"""
        return [f for f in self.features.values() if f.is_new]

    def get_recommended_features(self, limit: int = 5) -> List[FeatureDiscovery]:
        """获取推荐功能"""
        features = sorted(
            self.features.values(),
            key=lambda f: (f.priority, f.usage_count),
            reverse=True
        )
        return features[:limit]

    def record_feature_usage(self, feature_id: str):
        """记录功能使用"""
        if feature_id in self.features:
            self.features[feature_id].usage_count += 1
            self.features[feature_id].last_used = datetime.now()
            self._save_features()

    def discover_features(self, user_context: Dict) -> List[FeatureDiscovery]:
        """根据用户上下文发现功能"""
        discovered = []

        # 基于用户行为推荐功能
        for feature in self.features.values():
            if feature.usage_count == 0:  # 从未使用
                # 根据上下文推荐
                if user_context.get('coding_time', 0) > 3600 and feature.category == 'coding':
                    discovered.append(feature)
                elif user_context.get('needs_testing', False) and feature.category == 'testing':
                    discovered.append(feature)
                elif user_context.get('needs_docs', False) and feature.category == 'documentation':
                    discovered.append(feature)

        # 按优先级排序
        discovered.sort(key=lambda f: f.priority, reverse=True)
        return discovered[:5]


# ==================== 指标卡片组件 ====================

class MetricCard(QFrame):
    """指标卡片"""

    clicked = pyqtSignal(str)  # 发送指标ID

    def __init__(self, metric_id: str, title: str, value: str, icon: str, color: str = "#1890ff", parent=None):
        super().__init__(parent)
        self.metric_id = metric_id
        self.title = title
        self.value = value
        self.icon = icon
        self.color = color
        self._setup_ui()

    def _setup_ui(self):
        self.setMinimumHeight(100)
        self.setMinimumWidth(150)
        self.setStyleSheet(f"""
            MetricCard {{
                background-color: white;
                border-radius: 8px;
                border: 1px solid #e0e0e0;
            }}
            MetricCard:hover {{
                border: 2px solid {self.color};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # 图标和标题
        header_layout = QHBoxLayout()
        icon_label = QLabel(self.icon)
        icon_label.setFont(QFont("Segoe UI Emoji", 20))
        header_layout.addWidget(icon_label)

        title_label = QLabel(self.title)
        title_label.setFont(QFont("Microsoft YaHei", 10))
        title_label.setStyleSheet("color: #666;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # 数值
        value_label = QLabel(self.value)
        value_label.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        value_label.setStyleSheet(f"color: {self.color};")
        layout.addWidget(value_label)

        # 点击事件
        self.mousePressEvent = lambda e: self.clicked.emit(self.metric_id)


# ==================== 功能发现卡片 ====================

class FeatureDiscoveryCard(QFrame):
    """功能发现卡片"""

    activated = pyqtSignal(str)  # 发送功能ID
    discovered = pyqtSignal(str)  # 发现功能信号

    def __init__(self, feature: FeatureDiscovery, parent=None):
        super().__init__(parent)
        self.feature = feature
        self._setup_ui()
        self._update_style()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # 头部
        header_layout = QHBoxLayout()

        # 图标
        icon_label = QLabel(self.feature.icon)
        icon_label.setFont(QFont("Segoe UI Emoji", 24))
        header_layout.addWidget(icon_label)

        # 标题
        title_layout = QVBoxLayout()
        title_label = QLabel(self.feature.name)
        title_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        title_layout.addWidget(title_label)

        # 优先级标签
        priority_label = QLabel("⭐" * self.feature.priority)
        priority_label.setFont(QFont("Segoe UI Emoji", 8))
        priority_label.setStyleSheet("color: #faad14;")
        title_layout.addWidget(priority_label)

        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        # 新功能标签
        if self.feature.is_new:
            new_label = QLabel("✨ 新功能")
            new_label.setFont(QFont("Microsoft YaHei", 8))
            new_label.setStyleSheet("""
                background-color: #ff4d4f;
                color: white;
                border-radius: 4px;
                padding: 2px 6px;
            """)
            header_layout.addWidget(new_label)

        layout.addLayout(header_layout)

        # 描述
        desc_label = QLabel(self.feature.description)
        desc_label.setFont(QFont("Microsoft YaHei", 9))
        desc_label.setStyleSheet("color: #666;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # 使用次数
        usage_label = QLabel(f"使用 {self.feature.usage_count} 次")
        usage_label.setFont(QFont("Microsoft YaHei", 8))
        usage_label.setStyleSheet("color: #999;")
        layout.addWidget(usage_label)

        layout.addStretch()

        # 操作按钮
        btn_layout = QHBoxLayout()

        discover_btn = QPushButton("🔍 发现")
        discover_btn.setFont(QFont("Microsoft YaHei", 9))
        discover_btn.setStyleSheet("""
            QPushButton {
                background-color: #1890ff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #40a9ff;
            }
        """)
        discover_btn.clicked.connect(lambda: self.discovered.emit(self.feature.id))
        btn_layout.addWidget(discover_btn)

        use_btn = QPushButton("🚀 使用")
        use_btn.setFont(QFont("Microsoft YaHei", 9))
        use_btn.setStyleSheet("""
            QPushButton {
                background-color: #52c41a;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #73d13d;
            }
        """)
        use_btn.clicked.connect(lambda: self.activated.emit(self.feature.id))
        btn_layout.addWidget(use_btn)

        layout.addLayout(btn_layout)

    def _update_style(self):
        self.setMinimumSize(200, 180)
        self.setMaximumSize(250, 220)


# ==================== AI任务卡片 ====================

class AITaskCard(QFrame):
    """AI任务卡片"""

    def __init__(self, task_type: str, prompt: str, status: str, result: str = "", parent=None):
        super().__init__(parent)
        self.task_type = task_type
        self.prompt = prompt
        self.status = status
        self.result = result
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            AITaskCard {
                background-color: white;
                border-radius: 6px;
                border: 1px solid #e0e0e0;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # 头部
        header_layout = QHBoxLayout()

        # 任务类型图标
        icons = {
            'code_generation': '🔮',
            'error_diagnosis': '🐛',
            'performance_optimization': '⚡',
            'documentation': '📖',
            'test_generation': '🧪',
            'refactoring': '🔄'
        }
        icon_label = QLabel(icons.get(self.task_type, '🤖'))
        icon_label.setFont(QFont("Segoe UI Emoji", 20))
        header_layout.addWidget(icon_label)

        # 任务类型
        type_label = QLabel(self.task_type.replace('_', ' ').title())
        type_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        header_layout.addWidget(type_label)

        header_layout.addStretch()

        # 状态标签
        status_colors = {
            'pending': '#faad14',
            'running': '#1890ff',
            'completed': '#52c41a',
            'failed': '#ff4d4f'
        }
        status_label = QLabel(self.status.upper())
        status_label.setFont(QFont("Microsoft YaHei", 8))
        status_label.setStyleSheet(f"""
            background-color: {status_colors.get(self.status, '#999')};
            color: white;
            border-radius: 4px;
            padding: 2px 8px;
        """)
        header_layout.addWidget(status_label)

        layout.addLayout(header_layout)

        # 提示词
        prompt_label = QLabel(f"📝 {self.prompt[:100]}...")
        prompt_label.setFont(QFont("Microsoft YaHei", 9))
        prompt_label.setStyleSheet("color: #666;")
        prompt_label.setWordWrap(True)
        layout.addWidget(prompt_label)

        # 结果（如果有）
        if self.result:
            result_label = QLabel(f"✅ {self.result[:200]}...")
            result_label.setFont(QFont("Consolas", 9))
            result_label.setStyleSheet("color: #52c41a; background-color: #f6ffed; padding: 4px; border-radius: 4px;")
            result_label.setWordWrap(True)
            layout.addWidget(result_label)


# ==================== 代码片段卡片 ====================

class SnippetCard(QFrame):
    """代码片段卡片"""

    apply_signal = pyqtSignal(str)  # 触发词信号
    edit_signal = pyqtSignal(str)  # 编辑信号
    delete_signal = pyqtSignal(str)  # 删除信号

    def __init__(self, snippet_id: str, title: str, code: str, language: str, usage_count: int = 0, parent=None):
        super().__init__(parent)
        self.snippet_id = snippet_id
        self.title = title
        self.code = code
        self.language = language
        self.usage_count = usage_count
        self._setup_ui()

    def _setup_ui(self):
        self.setMinimumHeight(120)
        self.setStyleSheet("""
            SnippetCard {
                background-color: white;
                border-radius: 6px;
                border: 1px solid #e0e0e0;
            }
            SnippetCard:hover {
                border-color: #1890ff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # 头部
        header_layout = QHBoxLayout()

        # 标题
        title_label = QLabel(f"📎 {self.title}")
        title_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        header_layout.addWidget(title_label)

        # 语言标签
        lang_label = QLabel(self.language)
        lang_label.setFont(QFont("Consolas", 8))
        lang_label.setStyleSheet("""
            background-color: #f0f0f0;
            color: #666;
            border-radius: 4px;
            padding: 2px 6px;
        """)
        header_layout.addWidget(lang_label)

        header_layout.addStretch()

        # 使用次数
        count_label = QLabel(f"使用 {self.usage_count} 次")
        count_label.setFont(QFont("Microsoft YaHei", 8))
        count_label.setStyleSheet("color: #999;")
        header_layout.addWidget(count_label)

        layout.addLayout(header_layout)

        # 代码预览
        code_preview = QLabel(self.code[:150] + "..." if len(self.code) > 150 else self.code)
        code_preview.setFont(QFont("Consolas", 9))
        code_preview.setStyleSheet("color: #333; background-color: #f5f5f5; padding: 4px; border-radius: 4px;")
        code_preview.setWordWrap(True)
        layout.addWidget(code_preview)

        # 操作按钮
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✨ 插入")
        apply_btn.setFont(QFont("Microsoft YaHei", 9))
        apply_btn.clicked.connect(lambda: self.apply_signal.emit(self.snippet_id))
        btn_layout.addWidget(apply_btn)

        edit_btn = QPushButton("✏️ 编辑")
        edit_btn.setFont(QFont("Microsoft YaHei", 9))
        edit_btn.clicked.connect(lambda: self.edit_signal.emit(self.snippet_id))
        btn_layout.addWidget(edit_btn)

        delete_btn = QPushButton("🗑️ 删除")
        delete_btn.setFont(QFont("Microsoft YaHei", 9))
        delete_btn.clicked.connect(lambda: self.delete_signal.emit(self.snippet_id))
        btn_layout.addWidget(delete_btn)

        layout.addLayout(btn_layout)


# ==================== 初始化进度对话框 ====================

class InitializationProgressDialog(QDialog):
    """初始化进度对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🚀 正在启动智能IDE...")
        self.setModal(True)
        self.setFixedSize(400, 200)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 标题
        title_label = QLabel("🚀 智能IDE仪表盘")
        title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        # 状态标签
        self.status_label = QLabel("准备初始化...")
        self.status_label.setFont(QFont("Microsoft YaHei", 10))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # 详情列表
        self.details_list = QListWidget()
        self.details_list.setFont(QFont("Microsoft YaHei", 9))
        layout.addWidget(self.details_list, 1)

        # 取消按钮
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        layout.addWidget(self.cancel_btn)

    def update_progress(self, value: int, status: str, detail: str = ""):
        """更新进度"""
        self.progress_bar.setValue(value)
        self.status_label.setText(status)
        if detail:
            self.details_list.addItem(f"✅ {detail}")
            self.details_list.scrollToBottom()

    def set_ready(self):
        """设置就绪"""
        self.status_label.setText("✨ 初始化完成！")
        self.progress_bar.setValue(100)
        self.cancel_btn.setText("开始使用")


# ==================== Smart IDE Dashboard 主面板 ====================

class SmartIDEDashboard(QWidget):
    """
    智能IDE仪表盘主面板

    功能：
    - 智能IDE与游戏系统 UI
    - 代码编辑器核心
    - AI编程助手
    - 调试系统
    - 记忆增强编辑器
    - 协同编辑
    - 功能发现引擎
    - 游戏化学习
    """

    # 信号定义
    feature_activated = pyqtSignal(str)  # 功能激活信号
    initialization_complete = pyqtSignal()  # 初始化完成信号
    metrics_updated = pyqtSignal(dict)  # 指标更新信号

    def __init__(self, parent=None):
        super().__init__(parent)

        # 系统组件
        self.storage_path = os.path.expanduser("~/.hermes-desktop/smart_ide_dashboard")
        self.ide_system: Optional[SmartIDEGameSystem] = None
        self.feature_engine: Optional[FeatureDiscoveryEngine] = None
        self.github_manager = get_github_project_manager()

        # 初始化状态
        self.initialization_state = InitializationState.IDLE
        self.init_start_time: Optional[datetime] = None

        # 系统指标
        self.metrics = SystemMetrics()

        # 协程事件循环
        self._loop = None
        self._executor = ThreadPoolExecutor(max_workers=4)

        # 初始化UI
        self._setup_ui()

        # 显示初始化进度
        QTimer.singleShot(100, self._show_initialization)

    # ==================== 初始化逻辑 ====================

    async def _initialize_async(self) -> InitializationResult:
        """异步初始化系统"""
        self.init_start_time = datetime.now()
        results = []

        # 创建进度对话框
        progress_dialog = InitializationProgressDialog(self)
        progress_dialog.show()

        try:
            # 阶段1: 加载配置
            self.initialization_state = InitializationState.LOADING_CONFIG
            progress_dialog.update_progress(10, "加载用户配置...", "")
            config_result = await self._load_user_config()
            results.append(config_result)
            progress_dialog.update_progress(20, "配置加载完成", config_result.message)

            # 阶段2: 初始化存储
            self.initialization_state = InitializationState.INITIALIZING_STORAGE
            progress_dialog.update_progress(30, "初始化存储系统...", "")
            storage_result = await self._initialize_storage()
            results.append(storage_result)
            progress_dialog.update_progress(40, "存储系统就绪", storage_result.message)

            # 阶段3: 启动AI助手
            self.initialization_state = InitializationState.STARTING_AI
            progress_dialog.update_progress(50, "启动AI助手...", "")
            ai_result = await self._start_ai_assistant()
            results.append(ai_result)
            progress_dialog.update_progress(60, "AI助手就绪", ai_result.message)

            # 阶段4: 加载项目
            self.initialization_state = InitializationState.LOADING_PROJECTS
            progress_dialog.update_progress(70, "加载最近项目...", "")
            project_result = await self._load_recent_projects()
            results.append(project_result)
            progress_dialog.update_progress(80, "项目加载完成", project_result.message)

            # 阶段5: 加载代码片段
            self.initialization_state = InitializationState.LOADING_SNIPPETS
            progress_dialog.update_progress(90, "加载代码片段库...", "")
            snippet_result = await self._load_code_snippets()
            results.append(snippet_result)
            progress_dialog.update_progress(95, "片段库就绪", snippet_result.message)

            # 阶段6: 初始化协同编辑
            self.initialization_state = InitializationState.INITIALIZING_COLLAB
            progress_dialog.update_progress(98, "初始化协同编辑...", "")
            collab_result = await self._initialize_collaboration()
            results.append(collab_result)

            # 初始化完成
            self.initialization_state = InitializationState.READY
            progress_dialog.update_progress(100, "✨ 初始化完成！", "")
            progress_dialog.set_ready()

            # 等待用户点击
            await asyncio.sleep(0.5)
            progress_dialog.accept()

            # 发送初始化完成信号
            self.initialization_complete.emit()

            # 返回汇总结果
            duration = (datetime.now() - self.init_start_time).total_seconds() * 1000
            return InitializationResult(
                success=True,
                state=InitializationState.READY,
                message=f"初始化完成，耗时 {duration:.0f}ms",
                duration_ms=duration,
                details={r.state.value: r.message for r in results}
            )

        except Exception as e:
            self.initialization_state = InitializationState.ERROR
            progress_dialog.update_progress(0, "❌ 初始化失败", str(e))

            return InitializationResult(
                success=False,
                state=InitializationState.ERROR,
                message=f"初始化失败: {str(e)}",
                duration_ms=0
            )

    def _show_initialization(self):
        """显示初始化"""
        # 创建新的事件循环
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        # 在后台线程运行初始化
        def run_init():
            future = asyncio.ensure_future(self._initialize_async())
            self._loop.run_until_complete(future)

        threading.Thread(target=run_init, daemon=True).start()

    async def _load_user_config(self) -> InitializationResult:
        """加载用户配置"""
        start = time.time()
        try:
            # 模拟加载配置
            await asyncio.sleep(0.1)

            # 创建IDE设置
            self.ide_settings = IDESettings()

            return InitializationResult(
                success=True,
                state=InitializationState.LOADING_CONFIG,
                message="用户配置加载成功",
                duration_ms=(time.time() - start) * 1000
            )
        except Exception as e:
            return InitializationResult(
                success=False,
                state=InitializationState.LOADING_CONFIG,
                message=f"配置加载失败: {str(e)}",
                duration_ms=(time.time() - start) * 1000
            )

    async def _initialize_storage(self) -> InitializationResult:
        """初始化存储系统"""
        start = time.time()
        try:
            # 创建存储目录
            os.makedirs(self.storage_path, exist_ok=True)

            # 初始化功能发现引擎
            self.feature_engine = FeatureDiscoveryEngine(self.storage_path)

            return InitializationResult(
                success=True,
                state=InitializationState.INITIALIZING_STORAGE,
                message="存储系统初始化成功",
                duration_ms=(time.time() - start) * 1000,
                details={"storage_path": self.storage_path}
            )
        except Exception as e:
            return InitializationResult(
                success=False,
                state=InitializationState.INITIALIZING_STORAGE,
                message=f"存储初始化失败: {str(e)}",
                duration_ms=(time.time() - start) * 1000
            )

    async def _start_ai_assistant(self) -> InitializationResult:
        """启动AI助手"""
        start = time.time()
        try:
            # 创建IDE系统
            self.ide_system = SmartIDEGameSystem(self.storage_path)

            # 启动系统
            await self.ide_system.start()

            return InitializationResult(
                success=True,
                state=InitializationState.STARTING_AI,
                message="AI助手启动成功",
                duration_ms=(time.time() - start) * 1000,
                details={
                    "ai_capabilities": self.ide_system.ai_assistant.get_assistant_stats()
                }
            )
        except Exception as e:
            return InitializationResult(
                success=False,
                state=InitializationState.STARTING_AI,
                message=f"AI助手启动失败: {str(e)}",
                duration_ms=(time.time() - start) * 1000
            )

    async def _load_recent_projects(self) -> InitializationResult:
        """加载最近项目"""
        start = time.time()
        try:
            # 获取最近项目
            recent_projects = self.ide_settings.recent_projects if hasattr(self, 'ide_settings') else []

            # 更新指标
            self.metrics.files_count = len(recent_projects)

            return InitializationResult(
                success=True,
                state=InitializationState.LOADING_PROJECTS,
                message=f"加载了 {len(recent_projects)} 个最近项目",
                duration_ms=(time.time() - start) * 1000
            )
        except Exception as e:
            return InitializationResult(
                success=False,
                state=InitializationState.LOADING_PROJECTS,
                message=f"项目加载失败: {str(e)}",
                duration_ms=(time.time() - start) * 1000
            )

    async def _load_code_snippets(self) -> InitializationResult:
        """加载代码片段"""
        start = time.time()
        try:
            # 从记忆编辑器获取片段
            if self.ide_system and hasattr(self.ide_system, 'memory_editor'):
                snippets = self.ide_system.memory_editor.get_all_snippets()
                self.metrics.snippets_count = len(snippets)
            else:
                self.metrics.snippets_count = 0

            return InitializationResult(
                success=True,
                state=InitializationState.LOADING_SNIPPETS,
                message=f"加载了 {self.metrics.snippets_count} 个代码片段",
                duration_ms=(time.time() - start) * 1000
            )
        except Exception as e:
            return InitializationResult(
                success=False,
                state=InitializationState.LOADING_SNIPPETS,
                message=f"片段加载失败: {str(e)}",
                duration_ms=(time.time() - start) * 1000
            )

    async def _initialize_collaboration(self) -> InitializationResult:
        """初始化协同编辑"""
        start = time.time()
        try:
            # 初始化协同编辑器
            if self.ide_system and hasattr(self.ide_system, 'collab_editor'):
                await self.ide_system.collab_editor.start()
                self.metrics.collab_sessions = 0

            return InitializationResult(
                success=True,
                state=InitializationState.INITIALIZING_COLLAB,
                message="协同编辑初始化成功",
                duration_ms=(time.time() - start) * 1000
            )
        except Exception as e:
            return InitializationResult(
                success=False,
                state=InitializationState.INITIALIZING_COLLAB,
                message=f"协同初始化失败: {str(e)}",
                duration_ms=(time.time() - start) * 1000
            )

    # ==================== UI设置 ====================

    def _setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 创建选项卡
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)

        # 添加选项卡
        self.tabs.addTab(self._create_overview_tab(), "📊 总览")
        self.tabs.addTab(self._create_editor_tab(), "✏️ 编辑器")
        self.tabs.addTab(self._create_debug_tab(), "🐛 调试")
        self.tabs.addTab(self._create_ai_tab(), "🤖 AI助手")
        self.tabs.addTab(self._create_snippets_tab(), "📚 片段")
        self.tabs.addTab(self._create_collab_tab(), "👥 协同")
        self.tabs.addTab(self._create_learning_tab(), "🎮 学习")
        self.tabs.addTab(self._create_settings_tab(), "⚙️ 设置")

        main_layout.addWidget(self.tabs)

        # 底部状态栏
        self._setup_status_bar(main_layout)

    def _create_overview_tab(self) -> QWidget:
        """创建总览选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # 标题
        title_label = QLabel("🚀 智能IDE仪表盘")
        title_label.setFont(QFont("Microsoft YaHei", 24, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # 系统指标卡片
        metrics_group = QGroupBox("📊 系统概览")
        metrics_layout = QGridLayout(metrics_group)
        metrics_layout.setSpacing(16)

        self.metric_files = MetricCard("files", "文件", "0", "📄", "#1890ff")
        self.metric_ai = MetricCard("ai_tasks", "AI任务", "0", "🤖", "#52c41a")
        self.metric_debug = MetricCard("breakpoints", "断点", "0", "🐛", "#faad14")
        self.metric_memory = MetricCard("memory", "记忆", "0", "💾", "#722ed1")

        metrics_layout.addWidget(self.metric_files, 0, 0)
        metrics_layout.addWidget(self.metric_ai, 0, 1)
        metrics_layout.addWidget(self.metric_debug, 0, 2)
        metrics_layout.addWidget(self.metric_memory, 0, 3)

        layout.addWidget(metrics_group)

        # 功能发现区域
        discovery_group = QGroupBox("🎯 发现新功能")
        discovery_layout = QVBoxLayout(discovery_group)

        # 功能网格
        self.feature_scroll = QScrollArea()
        self.feature_scroll.setWidgetResizable(True)
        self.feature_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        feature_widget = QWidget()
        self.feature_layout = QGridLayout(feature_widget)
        self.feature_layout.setSpacing(12)

        # 加载功能发现卡片
        self._load_feature_cards()

        self.feature_scroll.setWidget(feature_widget)
        discovery_layout.addWidget(self.feature_scroll)

        layout.addWidget(discovery_group, 1)

        # 快捷操作
        quick_actions_group = QGroupBox("⚡ 快捷操作")
        quick_actions_layout = QHBoxLayout(quick_actions_group)

        new_file_btn = QPushButton("📄 新建文件")
        new_file_btn.setFont(QFont("Microsoft YaHei", 10))
        new_file_btn.clicked.connect(self._on_new_file)
        quick_actions_layout.addWidget(new_file_btn)

        open_file_btn = QPushButton("📂 打开文件")
        open_file_btn.setFont(QFont("Microsoft YaHei", 10))
        open_file_btn.clicked.connect(self._on_open_file)
        quick_actions_layout.addWidget(open_file_btn)

        ai_chat_btn = QPushButton("💬 AI对话")
        ai_chat_btn.setFont(QFont("Microsoft YaHei", 10))
        ai_chat_btn.clicked.connect(lambda: self.tabs.setCurrentIndex(3))
        quick_actions_layout.addWidget(ai_chat_btn)

        refresh_btn = QPushButton("🔄 刷新指标")
        refresh_btn.setFont(QFont("Microsoft YaHei", 10))
        refresh_btn.clicked.connect(self._refresh_metrics)
        quick_actions_layout.addWidget(refresh_btn)

        quick_actions_layout.addStretch()

        layout.addWidget(quick_actions_group)

        return widget

    def _create_editor_tab(self) -> QWidget:
        """创建编辑器选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 工具栏
        toolbar = QFrame()
        toolbar.setStyleSheet("background-color: #f5f5f5; border-radius: 6px;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 8, 10, 8)
        toolbar_layout.setSpacing(10)

        new_btn = QPushButton("📄 新建")
        new_btn.clicked.connect(self._on_new_file)
        toolbar_layout.addWidget(new_btn)

        open_btn = QPushButton("📂 打开")
        open_btn.clicked.connect(self._on_open_file)
        toolbar_layout.addWidget(open_btn)

        save_btn = QPushButton("💾 保存")
        save_btn.clicked.connect(self._on_save_file)
        toolbar_layout.addWidget(save_btn)

        toolbar_layout.addSpacing(20)

        # 语言选择
        lang_label = QLabel("语言:")
        toolbar_layout.addWidget(lang_label)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems([
            "python", "javascript", "typescript", "java", "cpp", "c",
            "go", "rust", "ruby", "php", "swift", "html", "css"
        ])
        self.lang_combo.setCurrentText("python")
        toolbar_layout.addWidget(self.lang_combo)

        toolbar_layout.addStretch()

        format_btn = QPushButton("🎨 格式化")
        format_btn.clicked.connect(self._on_format_code)
        toolbar_layout.addWidget(format_btn)

        layout.addWidget(toolbar)

        # 编辑器区域
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 文件浏览器
        file_panel = QFrame()
        file_panel.setMaximumWidth(200)
        file_panel.setStyleSheet("background-color: #fafafa; border-right: 1px solid #e0e0e0;")
        file_layout = QVBoxLayout(file_panel)
        file_layout.setContentsMargins(8, 8, 8, 8)

        file_title = QLabel("📁 文件")
        file_title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        file_layout.addWidget(file_title)

        self.file_list = QListWidget()
        self.file_list.addItem("untitled.py")
        file_layout.addWidget(self.file_list)

        splitter.addWidget(file_panel)

        # 代码编辑器
        self.code_editor = QPlainTextEdit()
        self.code_editor.setFont(QFont("Consolas", 11))
        self.code_editor.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
                padding: 8px;
            }
        """)
        splitter.addWidget(self.code_editor)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, 1)

        # 状态栏
        status_frame = QFrame()
        status_frame.setStyleSheet("background-color: #f5f5f5; border-top: 1px solid #e0e0e0;")
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(10, 4, 10, 4)

        self.editor_status = QLabel("就绪")
        self.editor_status.setFont(QFont("Microsoft YaHei", 9))
        status_layout.addWidget(self.editor_status)

        status_layout.addStretch()

        self.cursor_pos = QLabel("行: 1, 列: 1")
        self.cursor_pos.setFont(QFont("Consolas", 9))
        status_layout.addWidget(self.cursor_pos)

        layout.addWidget(status_frame)

        return widget

    def _create_debug_tab(self) -> QWidget:
        """创建调试选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 标题
        title_label = QLabel("🐛 调试中心")
        title_label.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # 调试工具栏
        debug_toolbar = QFrame()
        debug_toolbar.setStyleSheet("background-color: #fff; border-radius: 8px; border: 1px solid #e0e0e0;")
        debug_toolbar_layout = QHBoxLayout(debug_toolbar)
        debug_toolbar_layout.setContentsMargins(12, 8, 12, 8)
        debug_toolbar_layout.setSpacing(12)

        start_debug_btn = QPushButton("▶️ 开始调试")
        start_debug_btn.setStyleSheet("background-color: #52c41a; color: white; border: none; padding: 8px 16px; border-radius: 4px;")
        debug_toolbar_layout.addWidget(start_debug_btn)

        stop_debug_btn = QPushButton("⏹️ 停止")
        stop_debug_btn.setStyleSheet("background-color: #ff4d4f; color: white; border: none; padding: 8px 16px; border-radius: 4px;")
        debug_toolbar_layout.addWidget(stop_debug_btn)

        step_over_btn = QPushButton("⏭️ 单步跳过")
        step_over_btn.setStyleSheet("background-color: #1890ff; color: white; border: none; padding: 8px 16px; border-radius: 4px;")
        debug_toolbar_layout.addWidget(step_over_btn)

        step_in_btn = QPushButton("⤵️ 单步进入")
        step_in_btn.setStyleSheet("background-color: #1890ff; color: white; border: none; padding: 8px 16px; border-radius: 4px;")
        debug_toolbar_layout.addWidget(step_in_btn)

        step_out_btn = QPushButton("⤴️ 单步跳出")
        step_out_btn.setStyleSheet("background-color: #1890ff; color: white; border: none; padding: 8px 16px; border-radius: 4px;")
        debug_toolbar_layout.addWidget(step_out_btn)

        debug_toolbar_layout.addStretch()

        layout.addWidget(debug_toolbar)

        # 断点和变量面板
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 断点面板
        breakpoint_panel = QFrame()
        breakpoint_panel.setStyleSheet("background-color: #fff; border-radius: 8px; border: 1px solid #e0e0e0;")
        bp_layout = QVBoxLayout(breakpoint_panel)

        bp_title = QLabel("📍 断点")
        bp_title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        bp_layout.addWidget(bp_title)

        self.breakpoint_list = QListWidget()
        bp_layout.addWidget(self.breakpoint_list)

        add_bp_btn = QPushButton("➕ 添加断点")
        add_bp_btn.clicked.connect(self._on_add_breakpoint)
        bp_layout.addWidget(add_bp_btn)

        splitter.addWidget(breakpoint_panel)

        # 变量监视面板
        watch_panel = QFrame()
        watch_panel.setStyleSheet("background-color: #fff; border-radius: 8px; border: 1px solid #e0e0e0;")
        watch_layout = QVBoxLayout(watch_panel)

        watch_title = QLabel("👁️ 变量监视")
        watch_title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        watch_layout.addWidget(watch_title)

        self.watch_list = QListWidget()
        watch_layout.addWidget(self.watch_list)

        add_watch_btn = QPushButton("➕ 添加监视")
        add_watch_btn.clicked.connect(self._on_add_watch)
        watch_layout.addWidget(add_watch_btn)

        splitter.addWidget(watch_panel)

        # 调用栈面板
        stack_panel = QFrame()
        stack_panel.setStyleSheet("background-color: #fff; border-radius: 8px; border: 1px solid #e0e0e0;")
        stack_layout = QVBoxLayout(stack_panel)

        stack_title = QLabel("📚 调用栈")
        stack_title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        stack_layout.addWidget(stack_title)

        self.stack_list = QListWidget()
        stack_layout.addWidget(self.stack_list)

        splitter.addWidget(stack_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)

        layout.addWidget(splitter, 1)

        # 控制台输出
        console_group = QGroupBox("🖥️ 控制台")
        console_layout = QVBoxLayout(console_group)

        self.console_output = QPlainTextEdit()
        self.console_output.setFont(QFont("Consolas", 10))
        self.console_output.setReadOnly(True)
        self.console_output.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        console_layout.addWidget(self.console_output)

        layout.addWidget(console_group)

        return widget

    def _create_ai_tab(self) -> QWidget:
        """创建AI助手选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 标题
        title_label = QLabel("🤖 AI 编程助手")
        title_label.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # AI任务输入
        input_group = QGroupBox("💬 输入任务")
        input_layout = QVBoxLayout(input_group)

        self.ai_input = QPlainTextEdit()
        self.ai_input.setPlaceholderText("描述你想要做什么... 例如：帮我写一个快速排序算法")
        self.ai_input.setMinimumHeight(80)
        self.ai_input.setFont(QFont("Microsoft YaHei", 11))
        input_layout.addWidget(self.ai_input)

        # 任务类型选择
        task_layout = QHBoxLayout()
        task_label = QLabel("任务类型:")
        task_layout.addWidget(task_label)

        self.task_type_combo = QComboBox()
        self.task_type_combo.addItems([
            "🔮 代码生成",
            "✨ 代码补全",
            "🐛 错误诊断",
            "⚡ 性能分析",
            "📖 文档生成",
            "🧪 测试生成",
            "🔄 重构建议"
        ])
        task_layout.addWidget(self.task_type_combo)

        task_layout.addStretch()

        generate_btn = QPushButton("🚀 执行")
        generate_btn.setFont(QFont("Microsoft YaHei", 11))
        generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #1890ff;
                color: white;
                border: none;
                padding: 10px 24px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #40a9ff;
            }
        """)
        generate_btn.clicked.connect(self._on_execute_ai_task)
        task_layout.addWidget(generate_btn)

        input_layout.addLayout(task_layout)
        layout.addWidget(input_group)

        # AI能力快捷按钮
        capabilities_group = QGroupBox("⚡ 快速操作")
        capabilities_layout = QHBoxLayout(capabilities_group)

        self.ai_buttons = {}
        capabilities = [
            ("generate", "🔮 生成代码", self._on_quick_generate),
            ("diagnose", "🐛 诊断错误", self._on_quick_diagnose),
            ("document", "📖 生成文档", self._on_quick_document),
            ("test", "🧪 生成测试", self._on_quick_test),
            ("optimize", "⚡ 性能分析", self._on_quick_optimize),
            ("refactor", "🔄 重构建议", self._on_quick_refactor)
        ]

        for cap_id, cap_text, cap_handler in capabilities:
            btn = QPushButton(cap_text)
            btn.setFont(QFont("Microsoft YaHei", 10))
            btn.clicked.connect(cap_handler)
            capabilities_layout.addWidget(btn)
            self.ai_buttons[cap_id] = btn

        capabilities_layout.addStretch()
        layout.addWidget(capabilities_group)

        # 结果展示
        result_group = QGroupBox("📋 执行结果")
        result_layout = QVBoxLayout(result_group)

        self.ai_result = QPlainTextEdit()
        self.ai_result.setFont(QFont("Consolas", 11))
        self.ai_result.setReadOnly(True)
        self.ai_result.setStyleSheet("background-color: #f6ffed;")
        result_layout.addWidget(self.ai_result)

        layout.addWidget(result_group, 1)

        # 历史记录
        history_group = QGroupBox("📜 历史记录")
        history_layout = QVBoxLayout(history_group)

        self.ai_history = QListWidget()
        history_layout.addWidget(self.ai_history)

        clear_history_btn = QPushButton("🗑️ 清除历史")
        clear_history_btn.clicked.connect(self.ai_history.clear)
        history_layout.addWidget(clear_history_btn)

        layout.addWidget(history_group)

        return widget

    def _create_snippets_tab(self) -> QWidget:
        """创建代码片段选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 标题
        title_label = QLabel("📚 代码片段库")
        title_label.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # 操作工具栏
        toolbar = QFrame()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(12)

        self.snippet_search = QLineEdit()
        self.snippet_search.setPlaceholderText("🔍 搜索代码片段...")
        self.snippet_search.textChanged.connect(self._on_snippet_search)
        self.snippet_search.setMinimumWidth(300)
        toolbar_layout.addWidget(self.snippet_search)

        # 分类筛选
        self.category_combo = QComboBox()
        self.category_combo.addItems(["全部", "算法", "数据结构", "API调用", "工具类", "模板"])
        self.category_combo.currentTextChanged.connect(self._on_category_changed)
        toolbar_layout.addWidget(self.category_combo)

        toolbar_layout.addStretch()

        new_snippet_btn = QPushButton("➕ 新建片段")
        new_snippet_btn.setStyleSheet("background-color: #52c41a; color: white; border: none; padding: 8px 16px; border-radius: 4px;")
        new_snippet_btn.clicked.connect(self._on_new_snippet)
        toolbar_layout.addWidget(new_snippet_btn)

        import_btn = QPushButton("📥 导入")
        import_btn.clicked.connect(self._on_import_snippets)
        toolbar_layout.addWidget(import_btn)

        export_btn = QPushButton("📤 导出")
        export_btn.clicked.connect(self._on_export_snippets)
        toolbar_layout.addWidget(export_btn)

        layout.addWidget(toolbar)

        # 片段列表
        self.snippets_scroll = QScrollArea()
        self.snippets_scroll.setWidgetResizable(True)
        self.snippets_scroll.setStyleSheet("border: none;")

        self.snippets_container = QWidget()
        self.snippets_grid = QGridLayout(self.snippets_container)
        self.snippets_grid.setSpacing(12)

        self.snippets_scroll.setWidget(self.snippets_container)
        layout.addWidget(self.snippets_scroll, 1)

        # 加载片段
        self._load_snippet_cards()

        return widget

    def _create_collab_tab(self) -> QWidget:
        """创建协同选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 标题
        title_label = QLabel("👥 协同编辑")
        title_label.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # 协同操作
        collab_actions = QFrame()
        collab_actions.setStyleSheet("background-color: #fff; border-radius: 8px; border: 1px solid #e0e0e0; padding: 16px;")
        actions_layout = QVBoxLayout(collab_actions)

        # 创建/加入房间
        room_layout = QHBoxLayout()

        create_room_btn = QPushButton("🏠 创建房间")
        create_room_btn.setStyleSheet("background-color: #1890ff; color: white; border: none; padding: 10px 20px; border-radius: 6px;")
        create_room_btn.clicked.connect(self._on_create_room)
        room_layout.addWidget(create_room_btn)

        join_room_btn = QPushButton("🚪 加入房间")
        join_room_btn.setStyleSheet("background-color: #52c41a; color: white; border: none; padding: 10px 20px; border-radius: 6px;")
        join_room_btn.clicked.connect(self._on_join_room)
        room_layout.addWidget(join_room_btn)

        room_layout.addStretch()

        actions_layout.addLayout(room_layout)

        # 房间ID输入
        room_id_layout = QHBoxLayout()
        room_id_layout.addWidget(QLabel("房间ID:"))
        self.room_id_input = QLineEdit()
        self.room_id_input.setPlaceholderText("输入房间ID或邀请链接...")
        room_id_layout.addWidget(self.room_id_input)
        actions_layout.addLayout(room_id_layout)

        layout.addWidget(collab_actions)

        # 在线用户
        users_group = QGroupBox("🌐 在线用户")
        users_layout = QVBoxLayout(users_group)

        self.online_users = QListWidget()
        self.online_users.addItem("👤 你 (当前用户)")
        users_layout.addWidget(self.online_users)

        layout.addWidget(users_group)

        # 分享链接
        share_group = QGroupBox("🔗 分享链接")
        share_layout = QVBoxLayout(share_group)

        self.share_link = QLineEdit()
        self.share_link.setReadOnly(True)
        self.share_link.setPlaceholderText("生成分享链接后显示在这里...")
        share_layout.addWidget(self.share_link)

        generate_link_btn = QPushButton("🔄 生成链接")
        generate_link_btn.clicked.connect(self._on_generate_share_link)
        share_layout.addWidget(generate_link_btn)

        layout.addWidget(share_group)

        return widget

    def _create_learning_tab(self) -> QWidget:
        """创建学习选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 标题
        title_label = QLabel("🎮 游戏化学习")
        title_label.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # 学习进度
        progress_group = QGroupBox("📈 学习进度")
        progress_layout = QHBoxLayout(progress_group)

        self.learning_progress = QProgressBar()
        self.learning_progress.setRange(0, 100)
        self.learning_progress.setValue(35)
        self.learning_progress.setTextVisible(True)
        progress_layout.addWidget(self.learning_progress)

        progress_label = QLabel("35%")
        progress_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        progress_layout.addWidget(progress_label)

        layout.addWidget(progress_group)

        # 挑战任务
        challenges_group = QGroupBox("🏆 挑战任务")
        challenges_layout = QVBoxLayout(challenges_group)

        challenges = [
            ("算法挑战", "完成10道算法题", "🧩", 7, 10),
            ("代码优化", "优化5段代码性能", "⚡", 3, 5),
            ("文档达人", "生成20份文档", "📖", 12, 20),
            ("测试专家", "编写100个测试用例", "🧪", 45, 100)
        ]

        for title, desc, icon, current, total in challenges:
            challenge_layout = QHBoxLayout()

            icon_label = QLabel(icon)
            icon_label.setFont(QFont("Segoe UI Emoji", 24))
            challenge_layout.addWidget(icon_label)

            info_layout = QVBoxLayout()
            title_label = QLabel(title)
            title_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
            info_layout.addWidget(title_label)

            desc_label = QLabel(desc)
            desc_label.setFont(QFont("Microsoft YaHei", 9))
            desc_label.setStyleSheet("color: #666;")
            info_layout.addWidget(desc_label)

            challenge_layout.addLayout(info_layout)

            progress = QProgressBar()
            progress.setRange(0, total)
            progress.setValue(current)
            progress.setTextVisible(False)
            progress.setMaximumWidth(150)
            challenge_layout.addWidget(progress)

            count_label = QLabel(f"{current}/{total}")
            count_label.setFont(QFont("Microsoft YaHei", 10))
            challenge_layout.addWidget(count_label)

            challenge_layout.addStretch()

            challenges_layout.addLayout(challenge_layout)

        layout.addWidget(challenges_group, 1)

        # 成就
        achievements_group = QGroupBox("🏅 成就")
        achievements_layout = QHBoxLayout(achievements_group)

        achievements = [
            ("初学者", "完成第一个任务", "🌱", True),
            ("代码生成器", "生成100次代码", "🔮", True),
            ("调试高手", "修复50个错误", "🐛", False),
            ("性能优化师", "优化10段代码", "⚡", False)
        ]

        for title, desc, icon, unlocked in achievements:
            achievement_frame = QFrame()
            achievement_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {'#fffbe6' if unlocked else '#f5f5f5'};
                    border-radius: 8px;
                    border: 1px solid {'#faad14' if unlocked else '#e0e0e0'};
                    padding: 12px;
                }}
            """)
            ach_layout = QVBoxLayout(achievement_frame)
            ach_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            icon_label = QLabel(icon)
            icon_label.setFont(QFont("Segoe UI Emoji", 32))
            ach_layout.addWidget(icon_label)

            title_label = QLabel(title)
            title_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
            ach_layout.addWidget(title_label)

            desc_label = QLabel(desc)
            desc_label.setFont(QFont("Microsoft YaHei", 8))
            desc_label.setStyleSheet("color: #666;")
            desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ach_layout.addWidget(desc_label)

            achievements_layout.addWidget(achievement_frame)

        layout.addWidget(achievements_group)

        return widget

    def _create_settings_tab(self) -> QWidget:
        """创建设置选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 标题
        title_label = QLabel("⚙️ 设置")
        title_label.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # 设置内容
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)

        settings_container = QWidget()
        settings_layout = QVBoxLayout(settings_container)
        settings_layout.setSpacing(16)

        # 编辑器设置
        editor_group = QGroupBox("✏️ 编辑器设置")
        editor_layout = QFormLayout(editor_group)

        font_size = QSpinBox()
        font_size.setRange(8, 24)
        font_size.setValue(11)
        editor_layout.addRow("字体大小:", font_size)

        tab_size = QSpinBox()
        tab_size.setRange(2, 8)
        tab_size.setValue(4)
        editor_layout.addRow("制表符宽度:", tab_size)

        auto_save = QCheckBox("启用自动保存")
        auto_save.setChecked(True)
        editor_layout.addRow("", auto_save)

        format_on_save = QCheckBox("保存时格式化")
        format_on_save.setChecked(True)
        editor_layout.addRow("", format_on_save)

        settings_layout.addWidget(editor_group)

        # AI设置
        ai_group = QGroupBox("🤖 AI设置")
        ai_layout = QFormLayout(ai_group)

        ai_model = QComboBox()
        ai_model.addItems(["qwen2.5:1.5b (快速)", "qwen3.5:4b (平衡)", "qwen3.5:9b (深度)"])
        ai_layout.addRow("AI模型:", ai_model)

        creativity = QSlider(Qt.Orientation.Horizontal)
        creativity.setRange(0, 100)
        creativity.setValue(70)
        ai_layout.addRow("创造力:", creativity)

        max_tokens = QSpinBox()
        max_tokens.setRange(256, 8192)
        max_tokens.setSingleStep(256)
        max_tokens.setValue(2048)
        ai_layout.addRow("最大Token:", max_tokens)

        settings_layout.addWidget(ai_group)

        # 主题设置
        theme_group = QGroupBox("🎨 主题设置")
        theme_layout = QFormLayout(theme_group)

        theme = QComboBox()
        theme.addItems(["深色主题", "浅色主题", "跟随系统"])
        theme_layout.addRow("主题:", theme)

        settings_layout.addWidget(theme_group)

        settings_layout.addStretch()

        settings_scroll.setWidget(settings_container)
        layout.addWidget(settings_scroll, 1)

        # 保存按钮
        save_btn = QPushButton("💾 保存设置")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #1890ff;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #40a9ff;
            }
        """)
        save_btn.clicked.connect(self._on_save_settings)
        layout.addWidget(save_btn)

        return widget

    def _setup_status_bar(self, parent_layout: QVBoxLayout):
        """设置状态栏"""
        status_bar = QFrame()
        status_bar.setStyleSheet("background-color: #f5f5f5; border-top: 1px solid #e0e0e0;")
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(12, 4, 12, 4)

        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet("color: #52c41a; font-size: 12px;")
        status_layout.addWidget(self.status_indicator)

        self.status_text = QLabel("就绪")
        self.status_text.setFont(QFont("Microsoft YaHei", 9))
        status_layout.addWidget(self.status_text)

        status_layout.addStretch()

        self.uptime_label = QLabel("运行时间: 00:00:00")
        self.uptime_label.setFont(QFont("Microsoft YaHei", 9))
        status_layout.addWidget(self.uptime_label)

        # 启动运行时间计时器
        self._start_time = datetime.now()
        self._uptime_timer = QTimer()
        self._uptime_timer.timeout.connect(self._update_uptime)
        self._uptime_timer.start(1000)

        parent_layout.addWidget(status_bar)

    # ==================== 功能加载 ====================

    def _load_feature_cards(self):
        """加载功能发现卡片"""
        if not self.feature_engine:
            return

        features = self.feature_engine.get_all_features()

        # 按优先级排序
        features.sort(key=lambda f: f.priority, reverse=True)

        # 创建卡片网格
        for i, feature in enumerate(features[:12]):  # 最多显示12个
            card = FeatureDiscoveryCard(feature)
            card.activated.connect(self._on_feature_activated)
            card.discovered.connect(self._on_feature_discovered)

            row = i // 4
            col = i % 4
            self.feature_layout.addWidget(card, row, col)

    def _load_snippet_cards(self):
        """加载代码片段卡片"""
        # 示例代码片段
        snippets = [
            ("for_loop", "Python For循环", "for i in range(10):\n    print(i)", "python", 128),
            ("api_call", "API调用模板", "import requests\nresponse = requests.get(url)", "python", 256),
            ("class_def", "类定义模板", "class MyClass:\n    def __init__(self):\n        pass", "python", 64),
            ("react_component", "React组件", "function Component() {\n  return <div></div>;\n}", "javascript", 89)
        ]

        for i, (sid, title, code, lang, count) in enumerate(snippets):
            card = SnippetCard(sid, title, code, lang, count)
            card.apply_signal.connect(self._on_apply_snippet)
            card.edit_signal.connect(self._on_edit_snippet)
            card.delete_signal.connect(self._on_delete_snippet)

            row = i // 2
            col = i % 2
            self.snippets_grid.addWidget(card, row, col)

    # ==================== 事件处理 ====================

    def _on_feature_activated(self, feature_id: str):
        """功能激活"""
        if self.feature_engine:
            self.feature_engine.record_feature_usage(feature_id)

        self.feature_activated.emit(feature_id)

        # 显示提示
        QMessageBox.information(
            self,
            "✨ 功能已激活",
            f"功能 {feature_id} 已激活并准备使用！"
        )

    def _on_feature_discovered(self, feature_id: str):
        """功能发现"""
        if self.feature_engine:
            feature = self.feature_engine.features.get(feature_id)
            if feature:
                QMessageBox.information(
                    self,
                    f"🔍 发现: {feature.name}",
                    feature.description
                )

    def _on_new_file(self):
        """新建文件"""
        self.code_editor.clear()
        self.editor_status.setText("新建文件")

    def _on_open_file(self):
        """打开文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "打开文件", "~", "All Files (*.*)"
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.code_editor.setPlainText(content)
                self.editor_status.setText(f"已打开: {os.path.basename(path)}")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"无法打开文件: {e}")

    def _on_save_file(self):
        """保存文件"""
        path, _ = QFileDialog.getSaveFileName(
            self, "保存文件", "~", "All Files (*.*)"
        )
        if path:
            try:
                content = self.code_editor.toPlainText()
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.editor_status.setText(f"已保存: {os.path.basename(path)}")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"无法保存文件: {e}")

    def _on_format_code(self):
        """格式化代码"""
        self.editor_status.setText("格式化代码...")

    def _refresh_metrics(self):
        """刷新指标"""
        # 更新指标显示
        if hasattr(self, 'metric_files'):
            self.metric_files.value = str(self.metrics.files_count)
        if hasattr(self, 'metric_ai'):
            self.metric_ai.value = str(self.metrics.ai_tasks_count)
        if hasattr(self, 'metric_debug'):
            self.metric_debug.value = str(self.metrics.breakpoints_count)
        if hasattr(self, 'metric_memory'):
            self.metric_memory.value = str(self.metrics.memory_items_count)

        self.metrics_updated.emit(asdict(self.metrics))

    def _on_execute_ai_task(self):
        """执行AI任务"""
        prompt = self.ai_input.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "警告", "请输入任务描述！")
            return

        task_type_map = {
            "🔮 代码生成": "code_generation",
            "✨ 代码补全": "code_completion",
            "🐛 错误诊断": "error_diagnosis",
            "⚡ 性能分析": "performance_optimization",
            "📖 文档生成": "documentation",
            "🧪 测试生成": "test_generation",
            "🔄 重构建议": "refactoring"
        }

        task_type = self.task_type_combo.currentText()
        task_id = task_type_map.get(task_type, "code_generation")

        # 添加到历史
        self.ai_history.addItem(f"{task_type}: {prompt[:50]}...")

        # 显示结果（模拟）
        self.ai_result.setPlainText(f"正在执行任务: {task_type}\n\n{prompt}\n\n[模拟结果] 代码生成中...")

        self.metrics.ai_tasks_count += 1
        self._refresh_metrics()

    def _on_quick_generate(self):
        """快速生成代码"""
        self.task_type_combo.setCurrentText("🔮 代码生成")
        self.tabs.setCurrentIndex(3)

    def _on_quick_diagnose(self):
        """快速诊断错误"""
        self.task_type_combo.setCurrentText("🐛 错误诊断")
        self.tabs.setCurrentIndex(3)

    def _on_quick_document(self):
        """快速生成文档"""
        self.task_type_combo.setCurrentText("📖 文档生成")
        self.tabs.setCurrentIndex(3)

    def _on_quick_test(self):
        """快速生成测试"""
        self.task_type_combo.setCurrentText("🧪 测试生成")
        self.tabs.setCurrentIndex(3)

    def _on_quick_optimize(self):
        """快速性能分析"""
        self.task_type_combo.setCurrentText("⚡ 性能分析")
        self.tabs.setCurrentIndex(3)

    def _on_quick_refactor(self):
        """快速重构建议"""
        self.task_type_combo.setCurrentText("🔄 重构建议")
        self.tabs.setCurrentIndex(3)

    def _on_snippet_search(self, text: str):
        """搜索代码片段"""
        # 筛选片段
        pass

    def _on_category_changed(self, category: str):
        """分类变更"""
        pass

    def _on_new_snippet(self):
        """新建代码片段"""
        QMessageBox.information(self, "提示", "新建代码片段功能开发中...")

    def _on_import_snippets(self):
        """导入代码片段"""
        path, _ = QFileDialog.getOpenFileName(
            self, "导入片段", "~", "JSON Files (*.json)"
        )
        if path:
            QMessageBox.information(self, "提示", f"从 {path} 导入片段")

    def _on_export_snippets(self):
        """导出代码片段"""
        path, _ = QFileDialog.getSaveFileName(
            self, "导出片段", "~", "JSON Files (*.json)"
        )
        if path:
            QMessageBox.information(self, "提示", f"导出到 {path}")

    def _on_apply_snippet(self, snippet_id: str):
        """应用代码片段"""
        self.code_editor.insertPlainText(f"// 应用片段: {snippet_id}")
        self.tabs.setCurrentIndex(1)  # 切换到编辑器

    def _on_edit_snippet(self, snippet_id: str):
        """编辑代码片段"""
        QMessageBox.information(self, "提示", f"编辑片段: {snippet_id}")

    def _on_delete_snippet(self, snippet_id: str):
        """删除代码片段"""
        reply = QMessageBox.question(
            self, "确认", f"确定删除片段 {snippet_id}？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(self, "提示", f"片段 {snippet_id} 已删除")

    def _on_add_breakpoint(self):
        """添加断点"""
        line, ok = QInputDialog.getInt(self, "添加断点", "行号:", 1, 1, 9999)
        if ok:
            self.breakpoint_list.addItem(f"📍 第 {line} 行")

    def _on_add_watch(self):
        """添加监视"""
        expr, ok = QInputDialog.getText(self, "添加监视", "表达式:")
        if ok and expr:
            self.watch_list.addItem(f"👁️ {expr}")

    def _on_create_room(self):
        """创建房间"""
        QMessageBox.information(self, "提示", "创建房间功能开发中...")

    def _on_join_room(self):
        """加入房间"""
        room_id = self.room_id_input.text().strip()
        if not room_id:
            QMessageBox.warning(self, "警告", "请输入房间ID！")
            return
        QMessageBox.information(self, "提示", f"加入房间: {room_id}")

    def _on_generate_share_link(self):
        """生成分享链接"""
        self.share_link.setText("https://smartide.app/collab/abc123")

    def _on_save_settings(self):
        """保存设置"""
        QMessageBox.information(self, "成功", "设置已保存！")

    def _update_uptime(self):
        """更新运行时间"""
        delta = datetime.now() - self._start_time
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        seconds = int(delta.total_seconds() % 60)
        self.uptime_label.setText(f"运行时间: {hours:02d}:{minutes:02d}:{seconds:02d}")


# ==================== 导出 ====================

__all__ = [
    'SmartIDEDashboard',
    'InitializationState',
    'InitializationResult',
    'SystemMetrics',
    'FeatureDiscovery',
    'FeatureDiscoveryEngine',
    'MetricCard',
    'FeatureDiscoveryCard',
    'AITaskCard',
    'SnippetCard'
]
