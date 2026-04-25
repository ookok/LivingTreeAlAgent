"""
意图工作台 - 智能交互界面
用于 PyQt6 AI-IDE，实现自然语言驱动的开发工作流

特性:
- 自然语言输入
- 意图实时分析
- 多模式交互
- 快捷命令
- 上下文感知
"""

from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import time

# PyQt6 imports
try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
        QLabel, QPushButton, QComboBox, QListWidget,
        QListWidgetItem, QFrame, QSplitter, QSizePolicy,
        QToolButton, QMenu, QScrollArea, QGroupBox
    )
    from PyQt6.QtCore import (
        Qt, QTimer, QSize, QPoint, pyqtSignal, QPropertyAnimation,
        QRect, QParallelAnimationGroup
    )
    from PyQt6.QtGui import (
        QFont, QTextCursor, QIcon, QAction, QPalette, QColor,
        QPainter, QPen, QBrush, QLinearGradient
    )
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    print("[IntentWorkspace] PyQt6 not available, using text mode")


# ============== 样式定义 ==============

WORKSPACE_STYLES = """
/* 主容器 */
IntentWorkspace {
    background-color: #1e1e1e;
    border: 1px solid #3e3e42;
    border-radius: 8px;
}

/* 输入区域 */
.IntentInput {
    background-color: #252526;
    border: 1px solid #3e3e42;
    border-radius: 8px;
    padding: 12px;
    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
    font-size: 14px;
    color: #d4d4d4;
}

.IntentInput:focus {
    border: 2px solid #007acc;
}

.IntentInput::placeholder {
    color: #6a6a6a;
}

/* 意图标签 */
.IntentTag {
    background-color: #0e639c;
    color: white;
    border-radius: 4px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: bold;
}

/* 快捷命令按钮 */
.CommandButton {
    background-color: #2d2d2d;
    color: #d4d4d4;
    border: 1px solid #3e3e42;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    min-width: 100px;
}

.CommandButton:hover {
    background-color: #3e3e42;
    border: 1px solid #007acc;
}

.CommandButton:pressed {
    background-color: #007acc;
}

/* 发送按钮 */
.SendButton {
    background-color: #007acc;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 10px 24px;
    font-size: 14px;
    font-weight: bold;
}

.SendButton:hover {
    background-color: #005a9e;
}

.SendButton:pressed {
    background-color: #004578;
}

/* 模式选择器 */
.ModeSelector {
    background-color: #252526;
    border: 1px solid #3e3e42;
    border-radius: 4px;
    padding: 6px;
    color: #d4d4d4;
}

/* 历史记录项 */
.HistoryItem {
    background-color: #252526;
    border: none;
    border-bottom: 1px solid #3e3e42;
    padding: 10px;
    border-radius: 4px;
}

.HistoryItem:selected {
    background-color: #094771;
}

/* 意图分析卡片 */
.IntentCard {
    background-color: #2d2d2d;
    border: 1px solid #3e3e42;
    border-radius: 6px;
    padding: 12px;
    margin: 4px;
}

/* 上下文面板 */
.ContextPanel {
    background-color: #252526;
    border: 1px solid #3e3e42;
    border-radius: 6px;
    padding: 8px;
}

/* 状态栏 */
.StatusBar {
    background-color: #007acc;
    color: white;
    padding: 6px 12px;
    font-size: 12px;
    border-radius: 0 0 8px 8px;
}

/* 标签栏 */
.TagBar {
    background-color: #252526;
    border-bottom: 1px solid #3e3e42;
    padding: 8px;
}

/* 工具栏按钮 */
.ToolButton {
    background-color: transparent;
    border: none;
    border-radius: 4px;
    padding: 6px;
    color: #808080;
}

.ToolButton:hover {
    background-color: #3e3e42;
    color: #d4d4d4;
}
"""


# ============== 意图类型枚举 ==============

class IntentType(Enum):
    """意图类型"""
    CODE_GENERATION = "code_generation"      # 代码生成
    CODE_REVIEW = "code_review"              # 代码审查
    DEBUGGING = "debugging"                  # 调试
    REFACTORING = "refactoring"              # 重构
    DOCUMENTATION = "documentation"          # 文档生成
    TESTING = "testing"                      # 测试
    EXPLANATION = "explanation"              # 解释说明
    SEARCH = "search"                        # 搜索
    ANALYSIS = "analysis"                    # 分析
    CONVERSATION = "conversation"           # 对话


# ============== 工作模式枚举 ==============

class WorkMode(Enum):
    """工作模式"""
    AUTO = "auto"           # 自动模式
    CODE = "code"           # 代码模式
    REVIEW = "review"       # 审查模式
    DEBUG = "debug"         # 调试模式
    DOC = "doc"             # 文档模式
    RESEARCH = "research"    # 研究模式


# ============== 数据结构 ==============

@dataclass
class IntentResult:
    """意图分析结果"""
    original_text: str
    intent_type: IntentType
    confidence: float
    entities: List[Dict[str, Any]] = field(default_factory=list)
    suggested_actions: List[str] = field(default_factory=list)
    context_hints: List[str] = field(default_factory=list)
    language: str = "python"
    framework: str = ""
    components: List[str] = field(default_factory=list)


@dataclass
class HistoryItem:
    """历史记录项"""
    id: str
    text: str
    intent_type: IntentType
    timestamp: float
    result_summary: str = ""


# ============== 意图分析器 ==============

class IntentAnalyzer:
    """
    意图分析器
    
    使用规则 + 小模型进行快速意图识别
    """
    
    # 意图关键词映射
    INTENT_PATTERNS = {
        IntentType.CODE_GENERATION: [
            '创建', '生成', '写', '实现', '编写', '开发',
            'create', 'generate', 'write', 'implement', 'code'
        ],
        IntentType.CODE_REVIEW: [
            '审查', 'review', '检查', '优化', '改进',
            'review', 'optimize', 'improve'
        ],
        IntentType.DEBUGGING: [
            'debug', '调试', '修复', '错误', 'bug', '异常',
            'fix', 'error', 'exception', 'crash'
        ],
        IntentType.REFACTORING: [
            '重构', 'refactor', '重写', '优化代码', '整理'
        ],
        IntentType.DOCUMENTATION: [
            '文档', '注释', '说明', 'doc', 'comment', 'readme',
            'api', '文档化'
        ],
        IntentType.TESTING: [
            '测试', 'test', '单元测试', 'unit test', '测试用例'
        ],
        IntentType.EXPLANATION: [
            '解释', '说明', 'explain', 'understand', '什么是',
            'how does', 'why'
        ],
        IntentType.SEARCH: [
            '搜索', '查找', 'search', 'find', 'look for',
            '在哪里', '怎么实现'
        ],
        IntentType.ANALYSIS: [
            '分析', 'analyze', '分析', '对比', 'compare',
            '性能', '评估'
        ],
    }
    
    # 语言检测
    LANGUAGE_PATTERNS = {
        'python': ['python', 'python', 'django', 'flask', 'fastapi'],
        'javascript': ['javascript', 'js', 'node', 'react', 'vue', 'angular'],
        'typescript': ['typescript', 'ts'],
        'java': ['java', 'spring', 'maven'],
        'c++': ['c++', 'cpp', 'c++', 'qt'],
        'go': ['go', 'golang'],
        'rust': ['rust'],
        'sql': ['sql', 'mysql', 'postgresql', '数据库'],
    }
    
    def __init__(self):
        self._cache: Dict[str, IntentResult] = {}
        self._max_cache_size = 100
    
    def analyze(self, text: str) -> IntentResult:
        """
        分析意图
        
        Args:
            text: 输入文本
            
        Returns:
            IntentResult: 意图分析结果
        """
        # 清理文本
        text = text.strip()
        
        # 检查缓存
        if text in self._cache:
            return self._cache[text]
        
        # 分析
        result = self._do_analyze(text)
        
        # 缓存
        if len(self._cache) >= self._max_cache_size:
            # 删除最老的
            oldest = min(self._cache.keys(), 
                        key=lambda k: self._cache[k].timestamp if hasattr(self._cache[k], 'timestamp') else 0)
            del self._cache[oldest]
        
        self._cache[text] = result
        return result
    
    def _do_analyze(self, text: str) -> IntentResult:
        """执行实际的分析"""
        # 检测意图类型
        intent_type, confidence = self._detect_intent(text)
        
        # 检测语言
        language = self._detect_language(text)
        
        # 检测框架
        framework = self._detect_framework(text, language)
        
        # 提取实体
        entities = self._extract_entities(text)
        
        # 生成建议动作
        suggested_actions = self._generate_suggestions(intent_type, language)
        
        # 生成上下文提示
        context_hints = self._generate_context_hints(intent_type, text)
        
        return IntentResult(
            original_text=text,
            intent_type=intent_type,
            confidence=confidence,
            entities=entities,
            suggested_actions=suggested_actions,
            context_hints=context_hints,
            language=language,
            framework=framework
        )
    
    def _detect_intent(self, text: str) -> tuple[IntentType, float]:
        """检测意图类型"""
        text_lower = text.lower()
        scores = {}
        
        for intent_type, keywords in self.INTENT_PATTERNS.items():
            score = 0
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    score += 1
            if score > 0:
                scores[intent_type] = score / len(keywords)
        
        if not scores:
            return IntentType.CONVERSATION, 0.5
        
        # 返回最高分
        best_intent = max(scores, key=scores.get)
        max_score = scores[best_intent]
        
        # 归一化置信度
        confidence = min(0.95, 0.5 + max_score * 0.3)
        
        return best_intent, confidence
    
    def _detect_language(self, text: str) -> str:
        """检测编程语言"""
        text_lower = text.lower()
        
        for lang, keywords in self.LANGUAGE_PATTERNS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return lang
        
        return "python"  # 默认
    
    def _detect_framework(self, text: str, language: str) -> str:
        """检测框架"""
        text_lower = text.lower()
        
        framework_map = {
            'python': ['django', 'flask', 'fastapi', 'pyqt', 'pandas', 'numpy'],
            'javascript': ['react', 'vue', 'angular', 'nextjs', 'express'],
            'java': ['spring', 'springboot', 'mybatis'],
        }
        
        if language in framework_map:
            for fw in framework_map[language]:
                if fw in text_lower:
                    return fw
        
        return ""
    
    def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """提取实体"""
        entities = []
        
        # 提取文件路径
        import re
        file_paths = re.findall(r'[\w/]+\.[\w]+', text)
        for path in file_paths[:5]:
            entities.append({
                'type': 'file',
                'value': path,
                'confidence': 0.8
            })
        
        # 提取类名 (PascalCase)
        classes = re.findall(r'\b[A-Z][a-zA-Z0-9]*Class\b', text)
        for cls in classes[:5]:
            entities.append({
                'type': 'class',
                'value': cls,
                'confidence': 0.7
            })
        
        # 提取函数名 (snake_case 或 camelCase)
        functions = re.findall(r'\b[a-z_]+\([^\)]*\)|[a-z][a-zA-Z0-9]+\([^\)]*\)', text)
        for func in functions[:5]:
            entities.append({
                'type': 'function',
                'value': func,
                'confidence': 0.6
            })
        
        return entities
    
    def _generate_suggestions(self, intent_type: IntentType, language: str) -> List[str]:
        """生成建议动作"""
        suggestions = {
            IntentType.CODE_GENERATION: [
                f"生成 {language} 代码",
                "查看代码预览",
                "应用到项目"
            ],
            IntentType.CODE_REVIEW: [
                "进行全面审查",
                "只检查性能",
                "生成审查报告"
            ],
            IntentType.DEBUGGING: [
                "分析错误原因",
                "提供修复方案",
                "解释堆栈跟踪"
            ],
            IntentType.REFACTORING: [
                "分析重构机会",
                "生成重构方案",
                "预览变更"
            ],
            IntentType.DOCUMENTATION: [
                "生成文档",
                "添加注释",
                "创建 README"
            ],
            IntentType.TESTING: [
                "生成测试用例",
                "运行现有测试",
                "查看覆盖率"
            ],
            IntentType.EXPLANATION: [
                "详细解释",
                "简化说明",
                "提供示例"
            ],
            IntentType.SEARCH: [
                "搜索知识库",
                "搜索网络",
                "查看历史"
            ],
            IntentType.ANALYSIS: [
                "详细分析",
                "生成报告",
                "可视化结果"
            ],
            IntentType.CONVERSATION: [
                "继续对话",
                "切换到代码模式",
                "获取帮助"
            ]
        }
        
        return suggestions.get(intent_type, [])
    
    def _generate_context_hints(self, intent_type: IntentType, text: str) -> List[str]:
        """生成上下文提示"""
        hints = []
        
        # 基于意图类型
        if intent_type == IntentType.CODE_GENERATION:
            hints.append("💡 提供更多细节可以获得更准确的代码")
        
        if intent_type == IntentType.DEBUGGING:
            hints.append("🐛 可以粘贴错误信息或堆栈跟踪")
        
        if intent_type == IntentType.CODE_REVIEW:
            hints.append("📋 选择代码片段进行审查")
        
        # 检查是否有上下文
        if len(text) < 20:
            hints.append("📝 请描述更详细的需求")
        
        # 检查是否指定了文件
        if '.py' in text or '.js' in text:
            hints.append("📁 将分析指定文件的上下文")
        
        return hints


# ============== 意图工作台主组件 ==============

class IntentWorkspace(QWidget if PYQT6_AVAILABLE else object):
    """
    意图工作台主组件
    
    提供自然语言驱动的开发工作流界面
    """
    
    # 信号定义
    intent_analyzed = pyqtSignal(dict)          # 意图分析完成
    action_triggered = pyqtSignal(str, dict)     # 动作触发 (action, params)
    text_submitted = pyqtSignal(str)             # 文本提交
    mode_changed = pyqtSignal(str)               # 模式切换
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 创建意图分析器
        self._analyzer = IntentAnalyzer()
        
        # 状态
        self._current_intent: Optional[IntentResult] = None
        self._history: List[HistoryItem] = []
        self._max_history = 50
        
        # 快捷命令
        self._shortcuts = {
            '生成代码': self._on_generate_code,
            '审查代码': self._on_review_code,
            '调试': self._on_debug,
            '写测试': self._on_write_test,
            '生成文档': self._on_generate_doc,
            '解释': self._on_explain,
        }
        
        self._setup_ui()
        self._setup_shortcuts()
    
    def _setup_ui(self):
        """设置 UI"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 顶部工具栏
        toolbar = self._create_toolbar()
        main_layout.addWidget(toolbar)
        
        # 模式标签栏
        mode_bar = self._create_mode_bar()
        main_layout.addWidget(mode_bar)
        
        # 主内容区 - 分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧 - 意图输入和历史
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)
        
        # 中间 - 意图分析结果
        center_panel = self._create_center_panel()
        splitter.addWidget(center_panel)
        
        # 右侧 - 上下文
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)
        
        # 设置分割比例
        splitter.setStretchFactor(0, 3)  # 左侧 30%
        splitter.setStretchFactor(1, 4)  # 中间 40%
        splitter.setStretchFactor(2, 3)  # 右侧 30%
        
        main_layout.addWidget(splitter, 1)
        
        # 底部状态栏
        status_bar = self._create_status_bar()
        main_layout.addWidget(status_bar)
        
        # 应用样式
        self.setStyleSheet(WORKSPACE_STYLES)
    
    def _create_toolbar(self) -> QWidget:
        """创建工具栏"""
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(5, 5, 5, 5)
        
        # 标题
        title = QLabel("🎯 意图工作台")
        title.setStyleSheet("""
            QLabel {
                color: #d4d4d4;
                font-size: 16px;
                font-weight: bold;
                padding: 5px;
            }
        """)
        toolbar_layout.addWidget(title)
        
        toolbar_layout.addStretch()
        
        # 快捷命令按钮
        for label in ['📝 新对话', '📚 历史', '⚙️ 设置']:
            btn = QPushButton(label)
            btn.setObjectName("ToolButton")
            btn.setMaximumWidth(100)
            btn.clicked.connect(lambda checked, l=label: self._on_tool_click(l))
            toolbar_layout.addWidget(btn)
        
        return toolbar
    
    def _create_mode_bar(self) -> QWidget:
        """创建模式标签栏"""
        mode_bar = QWidget()
        mode_bar.setObjectName("TagBar")
        mode_bar_layout = QHBoxLayout(mode_bar)
        mode_bar_layout.setContentsMargins(10, 5, 10, 5)
        mode_bar_layout.setSpacing(10)
        
        # 模式按钮
        modes = [
            ("auto", "🚀 自动", True),
            ("code", "💻 代码", False),
            ("review", "🔍 审查", False),
            ("debug", "🐛 调试", False),
            ("doc", "📄 文档", False),
            ("research", "🔬 研究", False),
        ]
        
        self._mode_buttons = {}
        for mode_id, label, is_checked in modes:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(is_checked)
            btn.setObjectName("ModeButton")
            btn.clicked.connect(lambda checked, m=mode_id: self._on_mode_changed(m))
            self._mode_buttons[mode_id] = btn
            mode_bar_layout.addWidget(btn)
        
        mode_bar_layout.addStretch()
        
        return mode_bar
    
    def _create_left_panel(self) -> QWidget:
        """创建左侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # 意图输入
        input_label = QLabel("💬 输入您的需求")
        input_label.setStyleSheet("color: #d4d4d4; font-size: 13px; font-weight: bold;")
        layout.addWidget(input_label)
        
        self._input_edit = QTextEdit()
        self._input_edit.setObjectName("IntentInput")
        self._input_edit.setPlaceholderText(
            "例如：创建一个用户登录页面，包含邮箱和密码验证\n"
            "或者：解释这段代码的作用\n"
            "或者：帮我调试这个错误..."
        )
        self._input_edit.setMinimumHeight(150)
        self._input_edit.textChanged.connect(self._on_input_changed)
        layout.addWidget(self._input_edit)
        
        # 发送按钮行
        button_layout = QHBoxLayout()
        
        # 快捷命令下拉
        self._shortcut_combo = QComboBox()
        self._shortcut_combo.setObjectName("ModeSelector")
        self._shortcut_combo.addItem("选择快捷命令...")
        for cmd in self._shortcuts.keys():
            self._shortcut_combo.addItem(cmd)
        self._shortcut_combo.currentTextChanged.connect(self._on_shortcut_selected)
        button_layout.addWidget(self._shortcut_combo)
        
        button_layout.addStretch()
        
        # 发送按钮
        self._send_btn = QPushButton("🚀 发送")
        self._send_btn.setObjectName("SendButton")
        self._send_btn.clicked.connect(self._on_submit)
        button_layout.addWidget(self._send_btn)
        
        layout.addLayout(button_layout)
        
        # 历史记录
        history_label = QLabel("📜 历史记录")
        history_label.setStyleSheet("color: #d4d4d4; font-size: 13px; font-weight: bold;")
        layout.addWidget(history_label)
        
        self._history_list = QListWidget()
        self._history_list.setObjectName("HistoryList")
        self._history_list.itemClicked.connect(self._on_history_click)
        layout.addWidget(self._history_list, 1)
        
        return panel
    
    def _create_center_panel(self) -> QWidget:
        """创建中间面板（意图分析结果）"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # 意图分析标题
        title = QLabel("🧠 意图分析")
        title.setStyleSheet("color: #d4d4d4; font-size: 14px; font-weight: bold;")
        layout.addWidget(title)
        
        # 意图类型标签
        self._intent_tag = QLabel("等待输入...")
        self._intent_tag.setObjectName("IntentTag")
        self._intent_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._intent_tag.setMaximumWidth(200)
        layout.addWidget(self._intent_tag)
        
        # 置信度
        self._confidence_label = QLabel("置信度: -")
        self._confidence_label.setStyleSheet("color: #808080; font-size: 12px;")
        layout.addWidget(self._confidence_label)
        
        # 建议动作
        actions_label = QLabel("⚡ 建议动作")
        actions_label.setStyleSheet("color: #d4d4d4; font-size: 13px;")
        layout.addWidget(actions_label)
        
        self._actions_widget = QWidget()
        self._actions_layout = QVBoxLayout(self._actions_widget)
        self._actions_layout.setContentsMargins(0, 5, 0, 5)
        self._actions_layout.setSpacing(5)
        layout.addWidget(self._actions_widget)
        
        # 上下文提示
        hints_label = QLabel("💡 提示")
        hints_label.setStyleSheet("color: #d4d4d4; font-size: 13px;")
        layout.addWidget(hints_label)
        
        self._hints_text = QLabel("输入需求后这里会显示提示...")
        self._hints_text.setStyleSheet("color: #808080; font-size: 12px;")
        self._hints_text.setWordWrap(True)
        layout.addWidget(self._hints_text)
        
        layout.addStretch()
        
        return panel
    
    def _create_right_panel(self) -> QWidget:
        """创建右侧面板（上下文）"""
        panel = QWidget()
        panel.setObjectName("ContextPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # 标题
        title = QLabel("📋 当前上下文")
        title.setStyleSheet("color: #d4d4d4; font-size: 14px; font-weight: bold;")
        layout.addWidget(title)
        
        # 语言
        lang_group = QGroupBox("编程语言")
        lang_layout = QVBoxLayout(lang_group)
        self._lang_label = QLabel("自动检测中...")
        self._lang_label.setStyleSheet("color: #d4d4d4; font-size: 12px;")
        lang_layout.addWidget(self._lang_label)
        layout.addWidget(lang_group)
        
        # 框架
        fw_group = QGroupBox("框架/库")
        fw_layout = QVBoxLayout(fw_group)
        self._fw_label = QLabel("-")
        self._fw_label.setStyleSheet("color: #d4d4d4; font-size: 12px;")
        fw_layout.addWidget(self._fw_label)
        layout.addWidget(fw_group)
        
        # 检测到的实体
        entities_group = QGroupBox("检测到的实体")
        entities_layout = QVBoxLayout(entities_group)
        self._entities_list = QListWidget()
        entities_layout.addWidget(self._entities_list)
        layout.addWidget(entities_group, 1)
        
        return panel
    
    def _create_status_bar(self) -> QWidget:
        """创建状态栏"""
        status_bar = QWidget()
        status_bar.setObjectName("StatusBar")
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(10, 5, 10, 5)
        
        self._status_label = QLabel("🚀 就绪")
        self._status_label.setStyleSheet("color: white; font-size: 12px;")
        status_layout.addWidget(self._status_label)
        
        status_layout.addStretch()
        
        # 模式指示
        self._mode_indicator = QLabel("自动模式")
        self._mode_indicator.setStyleSheet("color: white; font-size: 12px;")
        status_layout.addWidget(self._mode_indicator)
        
        return status_bar
    
    def _setup_shortcuts(self):
        """设置快捷键"""
        from PyQt6.QtGui import QShortcut, QKeySequence
        from PyQt6.QtCore import Qt
        
        # Ctrl+Enter 发送
        shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        shortcut.activated.connect(self._on_submit)
        
        # Ctrl+L 清除
        shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        shortcut.activated.connect(self._on_clear)
    
    # ========== 事件处理 ==========
    
    def _on_input_changed(self):
        """输入文本变化"""
        text = self._input_edit.toPlainText()
        
        if len(text) < 3:
            return
        
        # 防抖：延迟分析
        QTimer.singleShot(300, lambda: self._analyze_intent(text))
    
    def _analyze_intent(self, text: str):
        """分析意图"""
        # 再次检查文本是否一致
        if self._input_edit.toPlainText() != text:
            return
        
        # 更新状态
        self._status_label.setText("🔍 分析中...")
        
        # 执行分析
        result = self._analyzer.analyze(text)
        self._current_intent = result
        
        # 更新 UI
        self._update_intent_display(result)
        
        # 发送信号
        self.intent_analyzed.emit({
            'intent_type': result.intent_type.value,
            'confidence': result.confidence,
            'language': result.language,
            'entities': result.entities
        })
        
        self._status_label.setText("✅ 分析完成")
    
    def _update_intent_display(self, result: IntentResult):
        """更新意图显示"""
        # 意图标签
        intent_names = {
            IntentType.CODE_GENERATION: "💻 代码生成",
            IntentType.CODE_REVIEW: "🔍 代码审查",
            IntentType.DEBUGGING: "🐛 调试",
            IntentType.REFACTORING: "🔧 重构",
            IntentType.DOCUMENTATION: "📄 文档",
            IntentType.TESTING: "🧪 测试",
            IntentType.EXPLANATION: "📖 解释",
            IntentType.SEARCH: "🔎 搜索",
            IntentType.ANALYSIS: "📊 分析",
            IntentType.CONVERSATION: "💬 对话",
        }
        
        self._intent_tag.setText(intent_names.get(result.intent_type, "❓ 未知"))
        
        # 置信度
        conf_text = f"置信度: {result.confidence:.0%}"
        self._confidence_label.setText(conf_text)
        
        # 语言
        self._lang_label.setText(result.language.upper() if result.language else "未检测")
        
        # 框架
        self._fw_label.setText(result.framework if result.framework else "-")
        
        # 实体列表
        self._entities_list.clear()
        for entity in result.entities:
            self._entities_list.addItem(f"[{entity['type']}] {entity['value']}")
        
        # 清空建议动作
        while self._actions_layout.count():
            child = self._actions_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # 添加建议动作
        for action in result.suggested_actions:
            btn = QPushButton(action)
            btn.setObjectName("CommandButton")
            btn.clicked.connect(lambda checked, a=action: self._on_action_click(a))
            self._actions_layout.addWidget(btn)
        
        # 提示
        if result.context_hints:
            self._hints_text.setText("\n".join(result.context_hints))
        else:
            self._hints_text.setText("没有额外提示")
    
    def _on_submit(self):
        """提交文本"""
        text = self._input_edit.toPlainText().strip()
        
        if not text:
            return
        
        # 发送信号
        self.text_submitted.emit(text)
        
        # 添加到历史
        self._add_to_history(text)
        
        # 更新状态
        self._status_label.setText("⏳ 等待响应...")
    
    def _on_action_click(self, action: str):
        """动作按钮点击"""
        self.action_triggered.emit(action, {
            'intent': self._current_intent.__dict__ if self._current_intent else {},
            'text': self._input_edit.toPlainText()
        })
    
    def _on_tool_click(self, label: str):
        """工具栏按钮点击"""
        if "新对话" in label:
            self._on_clear()
        elif "历史" in label:
            pass  # 切换到历史面板
        elif "设置" in label:
            pass  # 打开设置
    
    def _on_mode_changed(self, mode: str):
        """模式切换"""
        # 更新按钮状态
        for mode_id, btn in self._mode_buttons.items():
            btn.setChecked(mode_id == mode)
        
        # 更新指示器
        mode_names = {
            'auto': '自动模式',
            'code': '代码模式',
            'review': '审查模式',
            'debug': '调试模式',
            'doc': '文档模式',
            'research': '研究模式'
        }
        
        self._mode_indicator.setText(mode_names.get(mode, mode))
        self.mode_changed.emit(mode)
    
    def _on_shortcut_selected(self, text: str):
        """快捷命令选择"""
        if text in self._shortcuts:
            handler = self._shortcuts[text]
            handler()
    
    def _on_history_click(self, item: QListWidgetItem):
        """历史记录点击"""
        index = self._history_list.row(item)
        if 0 <= index < len(self._history):
            history = self._history[index]
            self._input_edit.setPlainText(history.text)
            self._analyze_intent(history.text)
    
    def _add_to_history(self, text: str):
        """添加到历史"""
        if self._current_intent:
            item = HistoryItem(
                id=str(int(time.time())),
                text=text,
                intent_type=self._current_intent.intent_type,
                timestamp=time.time(),
                result_summary=self._current_intent.intent_type.value
            )
            
            self._history.insert(0, item)
            
            # 限制历史数量
            if len(self._history) > self._max_history:
                self._history.pop()
            
            # 更新历史列表
            self._history_list.insertItem(0, f"[{item.intent_type.value}] {text[:50]}...")
    
    def _on_clear(self):
        """清除输入"""
        self._input_edit.clear()
        self._current_intent = None
        self._intent_tag.setText("等待输入...")
        self._confidence_label.setText("置信度: -")
        self._lang_label.setText("自动检测中...")
        self._fw_label.setText("-")
        self._entities_list.clear()
        self._hints_text.setText("输入需求后这里会显示提示...")
        self._status_label.setText("🚀 就绪")
    
    # ========== 快捷命令处理器 ==========
    
    def _on_generate_code(self):
        """生成代码"""
        self._input_edit.setPlainText("生成代码：")
        self._mode_buttons['code'].setChecked(True)
    
    def _on_review_code(self):
        """审查代码"""
        self._input_edit.setPlainText("审查代码：")
        self._mode_buttons['review'].setChecked(True)
    
    def _on_debug(self):
        """调试"""
        self._input_edit.setPlainText("调试：")
        self._mode_buttons['debug'].setChecked(True)
    
    def _on_write_test(self):
        """写测试"""
        self._input_edit.setPlainText("写测试：")
        self._mode_buttons['code'].setChecked(True)
    
    def _on_generate_doc(self):
        """生成文档"""
        self._input_edit.setPlainText("生成文档：")
        self._mode_buttons['doc'].setChecked(True)
    
    def _on_explain(self):
        """解释"""
        self._input_edit.setPlainText("解释：")
    
    # ========== 公共 API ==========
    
    def set_placeholder(self, text: str):
        """设置占位符文本"""
        self._input_edit.setPlaceholderText(text)
    
    def get_current_intent(self) -> Optional[IntentResult]:
        """获取当前意图"""
        return self._current_intent
    
    def get_input_text(self) -> str:
        """获取输入文本"""
        return self._input_edit.toPlainText()
    
    def set_status(self, message: str):
        """设置状态"""
        self._status_label.setText(message)


# ============== 单元测试 ==============

if __name__ == "__main__" and PYQT6_AVAILABLE:
    import sys
    
    app = QApplication(sys.argv)
    
    # 创建意图工作台
    workspace = IntentWorkspace()
    workspace.resize(1200, 800)
    
    # 连接信号
    workspace.text_submitted.connect(lambda t: print(f"Submitted: {t}"))
    workspace.intent_analyzed.connect(lambda r: print(f"Intent: {r}"))
    
    workspace.show()
    sys.exit(app.exec())
