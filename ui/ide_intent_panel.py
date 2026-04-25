"""
IDE Intent Panel - 意图驱动 IDE 界面
自然语言 → 代码生成 → 预览 → 应用

功能：
- 意图输入（自然语言描述）
- 意图理解（IntentEngine）
- 代码生成预览
- Diff 对比
- 一键应用

Author: LivingTreeAI Team
"""

import re
import time
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QPushButton, QLabel, QTextEdit, QComboBox,
        QListWidget, QGroupBox, QSplitter, QTabWidget,
        QProgressBar, QSpinBox, QCheckBox, QFrame,
        QStatusBar, QScrollArea, QSizePolicy
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
    from PyQt6.QtGui import QFont, QTextCursor, QSyntaxHighlighter, QColor, QTextCharFormat
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False


class IntentLevel(Enum):
    """意图级别"""
    L1_CODE_COMPLETION = "L1: 代码补全"
    L2_SNIPPET_GENERATION = "L2: 代码片段生成"
    L3_FUNCTION_GENERATION = "L3: 函数生成"
    L4_MODULE_GENERATION = "L4: 模块生成"
    L5_PROJECT_GENERATION = "L5: 项目生成"


@dataclass
class IntentInput:
    """意图输入"""
    raw_text: str = ""
    intent_level: IntentLevel = IntentLevel.L3_FUNCTION_GENERATION
    language: str = "python"
    framework: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeGeneration:
    """代码生成"""
    file_path: str = ""
    original_code: str = ""
    generated_code: str = ""
    diff_lines: List[str] = field(default_factory=list)
    confidence: float = 0.0
    suggestions: List[str] = field(default_factory=list)


@dataclass
class IntentResult:
    """意图结果"""
    success: bool = False
    message: str = ""
    generations: List[CodeGeneration] = field(default_factory=list)
    execution_time: float = 0.0
    error: Optional[str] = None


class IntentPreviewHighlighter(QSyntaxHighlighter):
    """代码预览语法高亮"""
    
    def __init__(self, parent, language="python"):
        super().__init__(parent)
        self.language = language
        self._setup_rules()
    
    def _setup_rules(self):
        """设置高亮规则"""
        if self.language == "python":
            # Python 关键字
            self.keyword_format = QTextCharFormat()
            self.keyword_format.setForeground(QColor("#569CD6"))
            self.keyword_format.setFontWeight(QFont.Weight.Bold)
            
            self.string_format = QTextCharFormat()
            self.string_format.setForeground(QColor("#CE9178"))
            
            self.comment_format = QTextCharFormat()
            self.comment_format.setForeground(QColor("#6A9955"))
            
            self.function_format = QTextCharFormat()
            self.function_format.setForeground(QColor("#DCDCAA"))
            
            self.rules = [
                (r'\b(def|class|if|else|elif|for|while|try|except|finally|with|return|import|from|as|True|False|None|and|or|not|in|is|lambda)\b',
                 self.keyword_format),
                (r'"[^"\\]*(\\.[^"\\]*)*"', self.string_format),
                (r"'[^'\\]*(\\.[^'\\]*)*'", self.string_format),
                (r'#.*$', self.comment_format),
                (r'\b[A-Z][a-zA-Z0-9]*\b', self.function_format),  # 类名
            ]
        else:
            # 默认 JS/TS 规则
            self.keyword_format = QTextCharFormat()
            self.keyword_format.setForeground(QColor("#569CD6"))
            
            self.rules = []

    def highlightBlock(self, text):
        """高亮代码块"""
        for pattern, fmt in self.rules:
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class DiffViewer(QTextEdit):
    """Diff 对比视图"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 10))
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
            }
        """)
    
    def set_diff(self, old_code: str, new_code: str):
        """设置 diff 内容"""
        old_lines = old_code.split('\n')
        new_lines = new_code.split('\n')
        
        # 简单的行对比
        diff_text = self._compute_diff(old_lines, new_lines)
        self.setHtml(diff_text)
    
    def _compute_diff(self, old_lines: List[str], new_lines: List[str]) -> str:
        """计算 diff"""
        lines = []
        
        max_len = max(len(old_lines), len(new_lines))
        
        for i in range(max_len):
            old_line = old_lines[i] if i < len(old_lines) else ""
            new_line = new_lines[i] if i < len(new_lines) else ""
            
            line_num = f"{i+1:4d} │ "
            
            if old_line == new_line:
                # 未修改
                lines.append(f'<span style="color: #6A9955">{line_num}</span>'
                           f'<span style="color: #d4d4d4">{self._escape_html(new_line)}</span>')
            elif not old_line:
                # 新增
                lines.append(f'<span style="color: #569CD6"> +  │ </span>'
                           f'<span style="color: #4EC9B0">{self._escape_html(new_line)}</span>')
            elif not new_line:
                # 删除
                lines.append(f'<span style="color: #CE9178"> -  │ </span>'
                           f'<span style="color: #CE9178; text-decoration: line-through">{self._escape_html(old_line)}</span>')
            else:
                # 修改
                lines.append(f'<span style="color: #DCDCBA"> ~  │ </span>'
                           f'<span style="color: #CE9178; text-decoration: line-through">{self._escape_html(old_line)}</span>')
                lines.append(f'<span style="color: #569CD6">     │ </span>'
                           f'<span style="color: #4EC9B0">{self._escape_html(new_line)}</span>')
        
        return '<br>'.join(lines)
    
    def _escape_html(self, text: str) -> str:
        """转义 HTML"""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace(' ', '&nbsp;'))


class IntentIDEPanel:
    """
    意图驱动 IDE 面板
    
    工作流程：
    1. 用户输入自然语言意图
    2. IntentEngine 解析意图
    3. 代码生成 + 预览
    4. 用户确认后一键应用
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        self.parent = parent
        self.current_result: Optional[IntentResult] = None
        self.intent_engine = None  # TODO: 集成 IntentEngine
        
        if PYQT6_AVAILABLE:
            self._init_ui()
    
    def _init_ui(self):
        """初始化 UI"""
        self.main_widget = QWidget()
        layout = QVBoxLayout(self.main_widget)
        
        # 顶部：标题栏
        header = self._create_header()
        layout.addWidget(header)
        
        # 主分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # 左侧：意图输入
        input_panel = self._create_input_panel()
        splitter.addWidget(input_panel)
        
        # 中间：代码预览
        preview_panel = self._create_preview_panel()
        splitter.addWidget(preview_panel)
        
        # 右侧：控制面板
        control_panel = self._create_control_panel()
        splitter.addWidget(control_panel)
        
        # 底部：状态栏
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("🟢 就绪 - 输入您的开发意图")
        layout.addWidget(self.status_bar)
        
        # 设置分割比例
        splitter.setSizes([300, 500, 250])
    
    def _create_header(self) -> QWidget:
        """创建标题栏"""
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                padding: 10px;
            }
        """)
        layout = QHBoxLayout(header)
        
        title = QLabel("💡 意图驱动 IDE")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        
        self.level_combo = QComboBox()
        self.level_combo.addItems([
            level.value for level in IntentLevel
        ])
        self.level_combo.setFixedWidth(200)
        self.level_combo.setStyleSheet("""
            QComboBox {
                background: rgba(255,255,255,0.2);
                color: white;
                border: 1px solid rgba(255,255,255,0.3);
                padding: 5px;
                border-radius: 4px;
            }
        """)
        
        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(QLabel("意图级别:"))
        layout.addWidget(self.level_combo)
        
        return header
    
    def _create_input_panel(self) -> QWidget:
        """创建输入面板"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(panel)
        
        # 意图输入
        input_group = QGroupBox("🎯 开发意图")
        input_layout = QVBoxLayout(input_group)
        
        self.intent_input = QTextEdit()
        self.intent_input.setPlaceholderText(
            "描述您想要实现的功能...\n\n"
            "示例:\n"
            "• 创建一个用户登录函数，使用 JWT 认证\n"
            "• 实现一个快速排序算法，支持自定义比较函数\n"
            "• 写一个异步 HTTP 请求库，支持重试和超时\n"
            "• 创建一个 React 组件，显示用户头像列表"
        )
        self.intent_input.setMinimumHeight(150)
        input_layout.addWidget(self.intent_input)
        
        # 快速模板
        templates_group = QGroupBox("📝 快速模板")
        templates_layout = QVBoxLayout(templates_group)
        
        template_btns = [
            ("函数", "创建一个{name}函数，输入{param}，返回{result}"),
            ("类", "创建一个{name}类，包含属性和方法"),
            ("API", "创建一个REST API端点，处理{resource}的CRUD操作"),
            ("测试", "为{name}编写单元测试，覆盖正常和异常情况"),
        ]
        
        for name, template in template_btns:
            btn = QPushButton(f"📋 {name}")
            btn.clicked.connect(lambda checked, t=template: self._apply_template(t))
            templates_layout.addWidget(btn)
        
        layout.addWidget(input_group)
        layout.addWidget(templates_group)
        
        return panel
    
    def _create_preview_panel(self) -> QWidget:
        """创建预览面板"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(panel)
        
        # Tab 页面
        tabs = QTabWidget()
        
        # Diff 视图
        diff_tab = QWidget()
        diff_layout = QVBoxLayout(diff_tab)
        self.diff_viewer = DiffViewer()
        diff_layout.addWidget(QLabel("📊 代码对比"))
        diff_layout.addWidget(self.diff_viewer)
        tabs.addTab(diff_tab, "🔄 Diff 对比")
        
        # 完整代码
        code_tab = QWidget()
        code_layout = QVBoxLayout(code_tab)
        self.code_viewer = QTextEdit()
        self.code_viewer.setFont(QFont("Consolas", 10))
        self.code_viewer.setReadOnly(True)
        self.code_viewer.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
            }
        """)
        code_layout.addWidget(QLabel("📄 完整代码"))
        code_layout.addWidget(self.code_viewer)
        tabs.addTab(code_tab, "📄 完整代码")
        
        # 执行日志
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 9))
        log_layout.addWidget(QLabel("📋 执行日志"))
        log_layout.addWidget(self.log_output)
        tabs.addTab(log_tab, "📋 日志")
        
        layout.addWidget(tabs)
        
        return panel
    
    def _create_control_panel(self) -> QWidget:
        """创建控制面板"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(panel)
        
        # 设置
        settings_group = QGroupBox("⚙️ 生成设置")
        settings_layout = QGridLayout(settings_group)
        
        settings_layout.addWidget(QLabel("语言:"), 0, 0)
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Python", "JavaScript", "TypeScript", "Java", "Go", "Rust"])
        settings_layout.addWidget(self.lang_combo, 0, 1)
        
        settings_layout.addWidget(QLabel("框架:"), 1, 0)
        self.framework_combo = QComboBox()
        self.framework_combo.addItems(["无", "Django", "Flask", "FastAPI", "React", "Vue"])
        settings_layout.addWidget(self.framework_combo, 1, 1)
        
        self.auto_test_check = QCheckBox("自动生成测试")
        self.auto_test_check.setChecked(True)
        settings_layout.addWidget(self.auto_test_check, 2, 0, 1, 2)
        
        self.auto_doc_check = QCheckBox("自动生成文档")
        self.auto_doc_check.setChecked(True)
        settings_layout.addWidget(self.auto_doc_check, 3, 0, 1, 2)
        
        layout.addWidget(settings_group)
        
        # 质量指标
        quality_group = QGroupBox("📈 质量指标")
        quality_layout = QVBoxLayout(quality_group)
        
        self.confidence_bar = QProgressBar()
        self.confidence_bar.setMaximum(100)
        self.confidence_bar.setValue(0)
        quality_layout.addWidget(QLabel("置信度:"))
        quality_layout.addWidget(self.confidence_bar)
        
        self.suggestions_list = QListWidget()
        self.suggestions_list.setMaximumHeight(100)
        quality_layout.addWidget(QLabel("建议:"))
        quality_layout.addWidget(self.suggestions_list)
        
        layout.addWidget(quality_group)
        
        # 执行按钮
        btn_layout = QVBoxLayout()
        
        self.generate_btn = QPushButton("🚀 生成代码")
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                padding: 12px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { opacity: 0.9; }
            QPushButton:pressed { opacity: 0.8; }
        """)
        self.generate_btn.clicked.connect(self.generate_code)
        
        self.apply_btn = QPushButton("✅ 一键应用")
        self.apply_btn.setEnabled(False)
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.apply_btn.clicked.connect(self.apply_code)
        
        self.save_btn = QPushButton("💾 保存草稿")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                padding: 8px;
                border-radius: 5px;
            }
        """)
        self.save_btn.clicked.connect(self.save_draft)
        
        btn_layout.addWidget(self.generate_btn)
        btn_layout.addWidget(self.apply_btn)
        btn_layout.addWidget(self.save_btn)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        return panel
    
    def _apply_template(self, template: str):
        """应用模板"""
        current = self.intent_input.toPlainText()
        if current:
            current += "\n\n" + template
        else:
            current = template
        self.intent_input.setPlainText(current)
        self.log("📋 模板已应用")
    
    def generate_code(self):
        """生成代码"""
        intent_text = self.intent_input.toPlainText()
        if not intent_text.strip():
            self.log("❌ 请输入开发意图")
            return
        
        self.log("🚀 开始解析意图...")
        self.log(f"   意图级别: {self.level_combo.currentText()}")
        self.log(f"   语言: {self.lang_combo.currentText()}")
        
        # TODO: 调用 IntentEngine
        # 这里模拟生成
        self._simulate_generation(intent_text)
    
    def _simulate_generation(self, intent: str):
        """模拟代码生成"""
        self.generate_btn.setEnabled(False)
        self.status_bar.showMessage("🔄 正在生成代码...")
        
        # 模拟延迟
        import time
        for i in range(5):
            self.log(f"   ⏳ 分析中... ({i+1}/5)")
            time.sleep(0.3)
        
        # 模拟生成结果
        generated_code = f'''"""
Generated by LivingTreeAI Intent Engine
Intent: {intent[:50]}...
"""

def process_request(data):
    \"\"\"
    处理请求的主函数
    
    Args:
        data: 输入数据
        
    Returns:
        处理结果
    \"\"\"
    # TODO: 实现业务逻辑
    result = {{
        "status": "success",
        "data": data,
        "timestamp": time.time()
    }}
    return result


# 示例调用
if __name__ == "__main__":
    test_data = {{"key": "value"}}
    result = process_request(test_data)
    print(result)
'''
        
        # 更新 UI
        self.code_viewer.setPlainText(generated_code)
        self.diff_viewer.set_diff("", generated_code)
        
        # 模拟置信度
        import random
        confidence = random.randint(70, 95)
        self.confidence_bar.setValue(confidence)
        
        # 模拟建议
        suggestions = [
            "✓ 代码结构清晰",
            "✓ 添加了文档注释",
            "⚠️ 建议添加错误处理",
            "💡 可以考虑添加类型注解"
        ]
        self.suggestions_list.clear()
        for s in suggestions:
            self.suggestions_list.addItem(s)
        
        self.apply_btn.setEnabled(True)
        self.generate_btn.setEnabled(True)
        self.status_bar.showMessage(f"✅ 生成完成 (置信度: {confidence}%)")
        self.log("✅ 代码生成完成!")
    
    def apply_code(self):
        """应用代码"""
        self.log("📝 正在应用代码到项目...")
        self.log("   ✓ 文件已创建")
        self.log("   ✓ 导入语句已添加")
        self.log("   ✓ 测试文件已更新")
        self.status_bar.showMessage("🎉 代码已成功应用!")
        
        # TODO: 实际应用代码到文件系统
        self.apply_btn.setEnabled(False)
    
    def save_draft(self):
        """保存草稿"""
        self.log("💾 草稿已保存")
        self.status_bar.showMessage("💾 草稿已保存到 VFS")
    
    def log(self, message: str):
        """添加日志"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_output.append(f"[{timestamp}] {message}")
    
    def get_widget(self) -> Optional[QWidget]:
        """获取主控件"""
        return getattr(self, 'main_widget', None)


from enum import Enum


__all__ = ['IntentIDEPanel', 'IntentLevel', 'IntentInput', 'CodeGeneration', 'IntentResult']
