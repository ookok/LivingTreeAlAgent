"""
深度搜索模块面板 - 富文本搜索过程展示
基于四层混合检索架构的可视化界面
"""

from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QTimer, QPropertyAnimation, QSize, QEasingCurve, QSizeF
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton,
    QScrollArea, QFrame, QListWidget,
    QListWidgetItem, QProgressBar,
    QToolButton, QSizePolicy,
    QAbstractItemView, QGraphicsOpacityEffect,
    QTextEdit, QSplitter,
)
from PyQt6.QtGui import (
    QFont, QDesktopServices, QCursor, QPixmap, 
    QPainter, QPen, QColor, QTextCursor, QTextCharFormat,
    QTextBlockFormat, QTextBlock, QPalette
)

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    QWebEngineView = None

from .presentation.theme import theme_manager


class SearchPhaseIndicator(QWidget):
    """搜索阶段指示器 - 动态显示当前搜索阶段"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._phases = []
        self._current_index = -1
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            background: transparent;
        """)
        
        layout = QHBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.phase_labels = []
    
    def set_phases(self, phases: list):
        """设置搜索阶段"""
        self._phases = phases
        self._current_index = -1
        
        # 清除旧标签
        layout = self.layout()
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.phase_labels = []
        
        # 创建阶段标签
        for i, phase in enumerate(phases):
            label = QLabel(phase["name"])
            label.setStyleSheet("""
                color: #CCCCCC;
                font-size: 13px;
                padding: 4px 12px;
                background: #F0F0F0;
                border-radius: 12px;
            """)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
            self.phase_labels.append(label)
            
            # 添加箭头（除了最后一个）
            if i < len(phases) - 1:
                arrow = QLabel("→")
                arrow.setStyleSheet("color: #DDDDDD; font-size: 14px;")
                layout.addWidget(arrow)
        
        layout.addStretch()
    
    def set_current_phase(self, index: int, status: str = ""):
        """设置当前阶段"""
        if index < 0 or index >= len(self.phase_labels):
            return
        
        self._current_index = index
        
        # 更新标签样式
        for i, label in enumerate(self.phase_labels):
            if i < index:
                # 已完成
                label.setStyleSheet("""
                    color: #10B981;
                    font-size: 13px;
                    padding: 4px 12px;
                    background: #E8F5F0;
                    border-radius: 12px;
                """)
                label.setText(f"✓ {self._phases[i]['name']}")
            elif i == index:
                # 当前
                label.setStyleSheet("""
                    color: #FFFFFF;
                    font-size: 13px;
                    padding: 4px 12px;
                    background: #10B981;
                    border-radius: 12px;
                    font-weight: bold;
                """)
                if status:
                    label.setText(f"{self._phases[i]['name']} {status}")
                else:
                    label.setText(f"● {self._phases[i]['name']}")
            else:
                # 未开始
                label.setStyleSheet("""
                    color: #999999;
                    font-size: 13px;
                    padding: 4px 12px;
                    background: #F5F5F5;
                    border-radius: 12px;
                """)


class SourceStatusPanel(QWidget):
    """数据源状态面板 - 显示各来源可用性"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._sources = {}
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            background: #FFFFFF;
            border: 1px solid #E8E8E8;
            border-radius: 8px;
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        
        # 标题
        title = QLabel("📊 数据源状态")
        title.setStyleSheet("""
            color: #333333;
            font-size: 13px;
            font-weight: bold;
        """)
        layout.addWidget(title)
        
        # 状态列表
        self.status_layout = QVBoxLayout()
        self.status_layout.setSpacing(6)
        layout.addLayout(self.status_layout)
    
    def set_sources(self, sources: list):
        """设置数据源状态"""
        self._sources = {s["name"]: s for s in sources}
        
        # 清除旧状态
        while self.status_layout.count():
            item = self.status_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 创建状态行
        for source in sources:
            row = self._create_source_row(source)
            self.status_layout.addWidget(row)
    
    def _create_source_row(self, source: dict) -> QWidget:
        """创建数据源状态行"""
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        
        # 状态图标
        status = source.get("status", "pending")
        if status == "available":
            icon = "🟢"
            icon_color = "#10B981"
        elif status == "searching":
            icon = "🟡"
            icon_color = "#F59E0B"
        elif status == "unavailable":
            icon = "🔴"
            icon_color = "#EF4444"
        else:
            icon = "⚪"
            icon_color = "#CCCCCC"
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"color: {icon_color}; font-size: 12px;")
        row_layout.addWidget(icon_label)
        
        # 名称
        name_label = QLabel(source.get("name", ""))
        name_label.setStyleSheet("color: #333333; font-size: 12px;")
        row_layout.addWidget(name_label, 1)
        
        # 状态文字
        status_label = QLabel(source.get("status_text", ""))
        status_label.setStyleSheet(f"color: {icon_color}; font-size: 11px;")
        row_layout.addWidget(status_label)
        
        return row
    
    def update_source_status(self, name: str, status: str, status_text: str = ""):
        """更新单个数据源状态"""
        if name in self._sources:
            self._sources[name]["status"] = status
            self._sources[name]["status_text"] = status_text
            # 重新渲染（简化处理：整体更新）
            self.set_sources(list(self._sources.values()))


class RichTextResultView(QTextEdit):
    """富文本结果视图 - 显示搜索结果"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self._setup_style()
    
    def _setup_style(self):
        self.setStyleSheet("""
            QTextEdit {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 12px;
                padding: 16px;
                color: #333333;
            }
        """)
        # 禁用滚动条样式问题
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    
    def append_header(self, text: str, level: int = 1):
        """添加标题"""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        char_format = QTextCharFormat()
        block_format = QTextBlockFormat()
        
        if level == 1:
            char_format.setFontPointSize(18)
            char_format.setFontWeight(QFont.Weight.Bold)
            char_format.setForeground(QColor("#1F2937"))
            block_format.setTopMargin(16)
            block_format.setBottomMargin(8)
        elif level == 2:
            char_format.setFontPointSize(15)
            char_format.setFontWeight(QFont.Weight.Bold)
            char_format.setForeground(QColor("#374151"))
            block_format.setTopMargin(12)
            block_format.setBottomMargin(6)
        else:
            char_format.setFontPointSize(13)
            char_format.setFontWeight(QFont.Weight.Bold)
            char_format.setForeground(QColor("#4B5563"))
            block_format.setTopMargin(8)
            block_format.setBottomMargin(4)
        
        cursor.setCharFormat(char_format)
        cursor.setBlockFormat(block_format)
        cursor.insertText(text)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
    
    def append_text(self, text: str, color: str = "#374151", bold: bool = False, italic: bool = False):
        """添加文本"""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        char_format = QTextCharFormat()
        char_format.setFontPointSize(13)
        char_format.setForeground(QColor(color))
        if bold:
            char_format.setFontWeight(QFont.Weight.Bold)
        if italic:
            char_format.setFontItalic(True)
        
        block_format = QTextBlockFormat()
        block_format.setTopMargin(4)
        block_format.setBottomMargin(4)
        
        cursor.setCharFormat(char_format)
        cursor.setBlockFormat(block_format)
        cursor.insertText(text)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
    
    def append_link(self, text: str, url: str, color: str = "#10B981"):
        """添加链接"""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        char_format = QTextCharFormat()
        char_format.setFontPointSize(13)
        char_format.setForeground(QColor(color))
        char_format.setFontUnderline(True)
        
        block_format = QTextBlockFormat()
        block_format.setTopMargin(4)
        block_format.setBottomMargin(8)
        
        cursor.setCharFormat(char_format)
        cursor.setBlockFormat(block_format)
        
        # 插入带链接的文本
        cursor.insertText(text)
        
        # 尝试设置链接（QTextEdit有限支持）
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
    
    def append_source_item(self, index: int, title: str, source: str, url: str, score: float = None):
        """添加来源项"""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # 序号
        num_format = QTextCharFormat()
        num_format.setFontPointSize(13)
        num_format.setFontWeight(QFont.Weight.Bold)
        num_format.setForeground(QColor("#10B981"))
        
        block_format = QTextBlockFormat()
        block_format.setTopMargin(8)
        block_format.setLeftMargin(0)
        
        cursor.setCharFormat(num_format)
        cursor.setBlockFormat(block_format)
        cursor.insertText(f"[{index}] ")
        
        # 标题
        title_format = QTextCharFormat()
        title_format.setFontPointSize(13)
        title_format.setFontWeight(QFont.Weight.Bold)
        title_format.setForeground(QColor("#1F2937"))
        cursor.setCharFormat(title_format)
        cursor.insertText(title)
        
        # 来源和分数
        meta_text = f" — {source}"
        if score is not None:
            meta_text += f" (置信度: {score:.0%})"
        
        meta_format = QTextCharFormat()
        meta_format.setFontPointSize(12)
        meta_format.setForeground(QColor("#6B7280"))
        cursor.setCharFormat(meta_format)
        cursor.insertText(meta_text)
        
        # 换行
        cursor.insertText("\n")
        
        # URL
        url_format = QTextCharFormat()
        url_format.setFontPointSize(11)
        url_format.setForeground(QColor("#10B981"))
        cursor.setCharFormat(url_format)
        cursor.insertText(f"    🔗 {url}\n")
        
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
    
    def append_divider(self):
        """添加分隔线"""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        block_format = QTextBlockFormat()
        block_format.setTopMargin(12)
        block_format.setBottomMargin(12)
        
        cursor.setBlockFormat(block_format)
        cursor.insertHtml("<hr style='border: none; border-top: 1px dashed #E5E7EB; margin: 12px 0;'>")
        self.setTextCursor(cursor)
    
    def append_related_tags(self, tags: list):
        """添加相关标签"""
        if not tags:
            return
        
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # 标签区域标题
        title_format = QTextCharFormat()
        title_format.setFontPointSize(12)
        title_format.setForeground(QColor("#9CA3AF"))
        block_format = QTextBlockFormat()
        block_format.setTopMargin(12)
        cursor.setCharFormat(title_format)
        cursor.setBlockFormat(block_format)
        cursor.insertText("相关搜索：")
        
        # 标签
        for tag in tags[:6]:
            tag_format = QTextCharFormat()
            tag_format.setFontPointSize(12)
            tag_format.setForeground(QColor("#10B981"))
            tag_format.setBackground(QColor("#ECFDF5"))
            cursor.setCharFormat(tag_format)
            cursor.insertText(f" {tag} ")
        
        cursor.insertText("\n")
        self.setTextCursor(cursor)


class IntentDisplayWidget(QWidget):
    """意图显示组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            background: #F0FDF4;
            border: 1px solid #BBF7D0;
            border-radius: 8px;
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        
        # 图标
        self.icon_label = QLabel("🎯")
        self.icon_label.setStyleSheet("font-size: 16px;")
        layout.addWidget(self.icon_label)
        
        # 意图信息
        self.info_layout = QVBoxLayout()
        self.info_layout.setSpacing(2)
        
        self.type_label = QLabel()
        self.type_label.setStyleSheet("color: #166534; font-size: 13px; font-weight: bold;")
        self.info_layout.addWidget(self.type_label)
        
        self.desc_label = QLabel()
        self.desc_label.setStyleSheet("color: #15803D; font-size: 11px;")
        self.info_layout.addWidget(self.desc_label)
        
        layout.addLayout(self.info_layout, 1)
        
        # 置信度
        self.confidence_label = QLabel()
        self.confidence_label.setStyleSheet("""
            color: #FFFFFF;
            background: #10B981;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        """)
        layout.addWidget(self.confidence_label)
    
    def set_intent(self, intent_type: str, confidence: float, features: dict = None):
        """设置意图信息"""
        intent_names = {
            "factual": "📚 事实查询",
            "conversational": "💬 对话类",
            "procedural": "⚙️ 流程操作",
            "creative": "🎨 创意类",
            "hybrid": "🔀 混合查询"
        }
        
        intent_descs = {
            "factual": "从知识库检索相关信息",
            "conversational": "结合会话上下文理解",
            "procedural": "查找操作步骤或指南",
            "creative": "需要生成创意内容",
            "hybrid": "多类型复合查询"
        }
        
        self.type_label.setText(intent_names.get(intent_type, intent_type))
        self.desc_label.setText(intent_descs.get(intent_type, ""))
        self.confidence_label.setText(f"{confidence:.0%}")
    
    def clear(self):
        """清空显示"""
        self.type_label.setText("🎯 准备中...")
        self.desc_label.setText("")
        self.confidence_label.setText("")


class SearchProcessWidget(QWidget):
    """搜索过程组件 - 搜索时的动态展示"""
    
    searching_progress = pyqtSignal(int, str)  # phase_index, status
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_query = ""
        self._phases = []
        self._current_phase = -1
        self._findings = []
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            background: #FFFFFF;
            border: 1px solid #E8E8E8;
            border-radius: 12px;
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)
        
        # 顶部：查询和意图
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        # 查询标签
        self.query_label = QLabel()
        self.query_label.setStyleSheet("""
            color: #1F2937;
            font-size: 16px;
            font-weight: bold;
            background: #F3F4F6;
            padding: 8px 16px;
            border-radius: 8px;
        """)
        header_layout.addWidget(self.query_label, 1)
        
        # 意图显示
        self.intent_widget = IntentDisplayWidget()
        self.intent_widget.hide()
        header_layout.addWidget(self.intent_widget)
        
        layout.addLayout(header_layout)
        
        # 阶段指示器
        self.phase_indicator = SearchPhaseIndicator()
        layout.addWidget(self.phase_indicator)
        
        # 中间区域：左侧发现列表 + 右侧数据源状态
        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(12)
        
        # 发现列表
        findings_widget = QWidget()
        findings_widget.setStyleSheet("""
            background: #F9FAFB;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
        """)
        findings_layout = QVBoxLayout(findings_widget)
        findings_layout.setContentsMargins(12, 10, 12, 10)
        findings_layout.setSpacing(8)
        
        findings_header = QLabel("📡 实时发现")
        findings_header.setStyleSheet("color: #374151; font-size: 13px; font-weight: bold;")
        findings_layout.addWidget(findings_header)
        
        self.findings_list = QTextEdit()
        self.findings_list.setReadOnly(True)
        self.findings_list.setStyleSheet("""
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 6px;
            padding: 8px;
            color: #4B5563;
            font-size: 12px;
        """)
        self.findings_list.setMaximumHeight(140)
        findings_layout.addWidget(self.findings_list)
        
        middle_layout.addWidget(findings_widget, 1)
        
        # 数据源状态
        self.source_panel = SourceStatusPanel()
        self.source_panel.setMaximumWidth(200)
        middle_layout.addWidget(self.source_panel)
        
        layout.addLayout(middle_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #E5E7EB;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background: #10B981;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # 状态文字
        self.status_label = QLabel("正在分析查询...")
        self.status_label.setStyleSheet("color: #6B7280; font-size: 12px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
    
    def start_search(self, query: str, intent_info: dict = None):
        """开始搜索"""
        self._current_query = query
        self._findings = []
        
        # 显示查询
        self.query_label.setText(f'"{query}"')
        
        # 设置意图
        if intent_info:
            self.intent_widget.show()
            self.intent_widget.set_intent(
                intent_info.get("primary", "factual"),
                intent_info.get("confidence", 0.8)
            )
        else:
            self.intent_widget.hide()
        
        # 设置阶段
        self._phases = [
            {"name": "理解意图", "duration": 500},
            {"name": "精确缓存", "duration": 50},
            {"name": "会话检索", "duration": 100},
            {"name": "知识库", "duration": 800},
            {"name": "网络搜索", "duration": 1500},
            {"name": "融合结果", "duration": 300},
        ]
        self.phase_indicator.set_phases(self._phases)
        
        # 清空发现列表
        self.findings_list.clear()
        
        # 清空数据源
        sources = [
            {"name": "精确缓存", "status": "pending", "status_text": "等待中"},
            {"name": "会话缓存", "status": "pending", "status_text": "等待中"},
            {"name": "知识库", "status": "pending", "status_text": "等待中"},
            {"name": "搜索引擎", "status": "pending", "status_text": "等待中"},
            {"name": "LLM增强", "status": "pending", "status_text": "等待中"},
        ]
        self.source_panel.set_sources(sources)
        
        # 开始阶段动画
        self._animate_phases()
    
    def _animate_phases(self):
        """阶段动画"""
        self._current_phase = 0
        self._update_phase_animation()
    
    def _update_phase_animation(self):
        """更新阶段动画"""
        if self._current_phase >= len(self._phases):
            # 完成
            self.status_label.setText("✨ 搜索完成，正在生成结果...")
            self.progress_bar.setValue(100)
            return
        
        phase = self._phases[self._current_phase]
        
        # 更新阶段指示器
        self.phase_indicator.set_current_phase(self._current_phase, "...")
        
        # 更新进度条
        progress = int((self._current_phase / len(self._phases)) * 100)
        self.progress_bar.setValue(progress)
        
        # 添加发现
        self._add_finding(f"正在{phase['name']}...")
        
        # 更新数据源状态
        source_map = {
            0: "精确缓存",
            1: "会话缓存",
            2: "知识库",
            3: "搜索引擎",
            4: "LLM增强",
            5: None
        }
        source_name = source_map.get(self._current_phase)
        if source_name:
            self.source_panel.update_source_status(source_name, "searching", "检索中...")
        
        # 继续下一阶段
        delay = phase["duration"]
        self._current_phase += 1
        
        # 模拟发现
        if self._current_phase == 4:  # 网络搜索阶段
            self._add_finding("🔍 正在搜索网络资源...")
            QTimer.singleShot(500, lambda: self._add_finding("📊 已发现 12 条相关结果"))
            QTimer.singleShot(1000, lambda: self._add_finding("📊 已发现 28 条相关结果"))
        
        QTimer.singleShot(delay, self._update_phase_animation)
    
    def _add_finding(self, text: str):
        """添加发现"""
        current = self.findings_list.toPlainText()
        if current:
            self.findings_list.setPlainText(f"{current}\n{text}")
        else:
            self.findings_list.setPlainText(text)
    
    def set_progress(self, phase_index: int, status: str):
        """设置进度（供外部调用）"""
        self.phase_indicator.set_current_phase(phase_index, status)
        self._add_finding(status)
        
        # 更新进度条
        progress = int((phase_index / len(self._phases)) * 100)
        self.progress_bar.setValue(progress)
        
        # 更新状态
        self.status_label.setText(status)


class DeepSearchPanel(QWidget):
    """
    深度搜索面板 - 富文本搜索过程展示
    
    特点：
    1. 搜索时显示动态搜索过程（意图理解→知识库→网络→聚合）
    2. 搜索后以富文本形式展示结果，不显示卡片
    3. 结果包含：意图分类、融合答案、来源列表、置信度
    """
    
    search_requested = pyqtSignal(str, dict)
    open_in_browser = pyqtSignal(str)
    open_preview = pyqtSignal(str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._results = []
        self._current_page = 1
        self._page_size = 10
        self._is_searching = False
        self._current_query = ""
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            DeepSearchPanel {
                background: #F8FAFC;
            }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(16)
        
        # 1. 搜索区域
        self._setup_search_area(main_layout)
        
        # 2. 内容区域（搜索过程 / 结果）
        content_splitter = QSplitter(Qt.Orientation.Vertical)
        content_splitter.setHandleWidth(1)
        content_splitter.setStyleSheet("""
            QSplitter::handle {
                background: transparent;
            }
        """)
        
        # 搜索过程面板（默认隐藏）
        self.process_widget = SearchProcessWidget()
        self.process_widget.hide()
        content_splitter.addWidget(self.process_widget)
        
        # 结果展示区域
        self.result_view = RichTextResultView()
        self._show_empty_state()
        content_splitter.addWidget(self.result_view)
        
        # 设置分割比例
        content_splitter.setStretchFactor(0, 0)  # 过程面板默认折叠
        content_splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(content_splitter, 1)
        
        # 3. 底部：统计信息和分页
        self._setup_footer(main_layout)
    
    def _setup_search_area(self, layout: QVBoxLayout):
        """搜索区域"""
        search_layout = QHBoxLayout()
        search_layout.setSpacing(12)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入搜索内容，例如：五一去哪玩")
        self.search_input.setMinimumHeight(48)
        self.search_input.setStyleSheet(theme_manager.get_widget_styles()["input"])
        self.search_input.returnPressed.connect(self._on_search)
        search_layout.addWidget(self.search_input, 1)
        
        self.search_btn = QPushButton("🔍 深度搜索")
        self.search_btn.setFixedSize(120, 48)
        self.search_btn.setStyleSheet(theme_manager.get_widget_styles()["button_primary"])
        self.search_btn.clicked.connect(self._on_search)
        search_layout.addWidget(self.search_btn)
        
        layout.addLayout(search_layout)
        
        # 提示文字
        hint = QLabel("💡 提示：深度搜索会智能理解您的意图，同时检索知识库和网络资源")
        hint.setStyleSheet("color: #9CA3AF; font-size: 12px; padding: 4px 0;")
        layout.addWidget(hint)
    
    def _setup_footer(self, layout: QVBoxLayout):
        """底部区域"""
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(12)
        
        # 统计信息
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #6B7280; font-size: 12px;")
        footer_layout.addWidget(self.stats_label, 1)
        
        # 分页按钮
        self.prev_btn = QPushButton("◀ 上一页")
        self.prev_btn.setStyleSheet(theme_manager.get_widget_styles()["button_secondary"])
        self.prev_btn.clicked.connect(self._on_prev_page)
        self.prev_btn.hide()
        footer_layout.addWidget(self.prev_btn)
        
        self.next_btn = QPushButton("下一页 ▶")
        self.next_btn.setStyleSheet(theme_manager.get_widget_styles()["button_secondary"])
        self.next_btn.clicked.connect(self._on_next_page)
        self.next_btn.hide()
        footer_layout.addWidget(self.next_btn)
        
        layout.addLayout(footer_layout)
    
    def _connect_signals(self):
        """连接信号"""
        theme_manager.theme_changed.connect(self._on_theme_changed)
    
    def _on_theme_changed(self, theme_name: str):
        """主题切换"""
        self.search_input.setStyleSheet(theme_manager.get_widget_styles()["input"])
        self.search_btn.setStyleSheet(theme_manager.get_widget_styles()["button_primary"])
        self.prev_btn.setStyleSheet(theme_manager.get_widget_styles()["button_secondary"])
        self.next_btn.setStyleSheet(theme_manager.get_widget_styles()["button_secondary"])
    
    def _on_search(self):
        """执行搜索"""
        query = self.search_input.text().strip()
        if not query or self._is_searching:
            return
        
        self._is_searching = True
        self._current_query = query
        self._current_page = 1
        self._results = []
        
        # 更新按钮状态
        self.search_btn.setEnabled(False)
        self.search_btn.setText("搜索中...")
        
        # 显示搜索过程面板
        self.process_widget.show()
        self.result_view.hide()
        
        # 启动搜索过程动画
        self.process_widget.start_search(query, {
            "primary": "factual",
            "confidence": 0.85
        })
        
        # 发送搜索请求
        self.search_requested.emit(query, {
            "page": self._current_page,
            "page_size": self._page_size
        })
    
    def _on_prev_page(self):
        """上一页"""
        if self._current_page > 1:
            self._current_page -= 1
            self._do_pagination()
    
    def _on_next_page(self):
        """下一页"""
        total_pages = (len(self._results) + self._page_size - 1) // self._page_size
        if self._current_page < total_pages:
            self._current_page += 1
            self._do_pagination()
    
    def _do_pagination(self):
        """执行分页"""
        # 重新显示当前页结果
        self._render_results()
    
    def _show_empty_state(self):
        """显示空状态"""
        self.result_view.clear()
        self.result_view.append_header("📚 深度搜索", 1)
        self.result_view.append_text(
            "\n欢迎使用深度搜索！\n\n"
            "输入您想了解的内容，系统将智能理解您的意图，"
            "同时检索知识库和网络资源，为您提供全面的答案。\n\n"
            "💡 示例查询：\n"
            "   • \"五一去哪玩\"\n"
            "   • \"Python异步编程详解\"\n"
            "   • \"如何配置SSH免密登录\"\n"
        )
        self.result_view.append_divider()
        self.result_view.append_text("🛠️ 技术栈支持：精确缓存 | 会话上下文 | 知识库检索 | 网络搜索 | LLM增强", 
                                      color="#9CA3AF")
    
    def on_search_progress(self, phase: int, status: str):
        """搜索进度回调"""
        self.process_widget.set_progress(phase, status)
    
    def show_results(self, data: dict, complete: bool = True):
        """显示搜索结果"""
        if complete:
            self._is_searching = False
            self.search_btn.setEnabled(True)
            self.search_btn.setText("🔍 深度搜索")
            self.process_widget.hide()
            self.result_view.show()
        
        # 解析结果数据
        answer = data.get("answer", "")
        sources = data.get("sources", [])
        intent = data.get("intent", {})
        confidence = data.get("confidence", 0)
        related = data.get("related", [])
        stats = data.get("stats", {})
        
        # 存储结果
        self._results = sources
        self._total_results = len(sources)
        
        # 渲染富文本结果
        self._render_rich_results(answer, sources, intent, confidence, related, stats)
        
        # 更新统计
        self._update_stats(stats)
    
    def _render_rich_results(self, answer: str, sources: list, intent: dict, 
                           confidence: float, related: list, stats: dict):
        """渲染富文本结果"""
        self.result_view.clear()
        
        # 1. 查询标题
        self.result_view.append_header(f'"{self._current_query}"', 1)
        
        # 2. 意图和置信度
        intent_type = intent.get("primary", "factual")
        intent_names = {
            "factual": "📚 事实查询",
            "conversational": "💬 对话类",
            "procedural": "⚙️ 流程操作",
            "creative": "🎨 创意类",
            "hybrid": "🔀 混合查询"
        }
        self.result_view.append_text(
            f"识别为 {intent_names.get(intent_type, intent_type)}，"
            f"置信度 {confidence:.0%}",
            color="#6B7280"
        )
        
        self.result_view.append_divider()
        
        # 3. 融合答案
        if answer:
            self.result_view.append_header("📋 综合答案", 2)
            self.result_view.append_text(answer, color="#1F2937")
            self.result_view.append_divider()
        
        # 4. 来源列表
        if sources:
            self.result_view.append_header(f"📚 参考来源 ({len(sources)} 条)", 2)
            
            for i, source in enumerate(sources, 1):
                title = source.get("title", source.get("content", "")[:50])
                source_name = source.get("source", source.get("api_name", "未知来源"))
                url = source.get("url", "")
                score = source.get("score", source.get("fused_score", None))
                
                self.result_view.append_source_item(i, title, source_name, url, score)
        
        # 5. 相关搜索
        if related:
            self.result_view.append_divider()
            self.result_view.append_related_tags(related)
    
    def _update_stats(self, stats: dict):
        """更新统计信息"""
        total = stats.get("total_results", self._total_results)
        cached = stats.get("cached", False)
        
        stats_text = f"找到 {total} 个结果"
        if cached:
            stats_text += " (缓存)"
        
        # 来源分布
        tier_dist = stats.get("tier_distribution", {})
        if tier_dist:
            tier_names = {
                "TIER_1_CN_HIGH": "国内高速",
                "TIER_2_CN_VERTICAL": "垂直专业",
                "TIER_3_GLOBAL": "全球免费",
                "TIER_4_FALLBACK": "本地备用"
            }
            sources_used = stats.get("sources_used", [])
            if sources_used:
                stats_text += f" | 来源: {', '.join(sources_used[:3])}"
        
        self.stats_label.setText(stats_text)
        
        # 更新分页按钮
        total_pages = max(1, (total + self._page_size - 1) // self._page_size)
        self.prev_btn.setVisible(total_pages > 1)
        self.next_btn.setVisible(total_pages > 1)
        self.prev_btn.setEnabled(self._current_page > 1)
        self.next_btn.setEnabled(self._current_page < total_pages)
        
        if total_pages > 1:
            self.stats_label.setText(
                f"{stats_text} | 第 {self._current_page} / {total_pages} 页"
            )
    
    def set_searching(self, searching: bool):
        """设置搜索状态"""
        self._is_searching = searching
        self.search_btn.setEnabled(not searching)
        self.search_btn.setText("搜索中..." if searching else "🔍 深度搜索")


# ==================== 模拟数据生成 ====================

def generate_travel_search_result(query: str = "五一去哪玩") -> dict:
    """生成旅行搜索模拟结果"""
    return {
        "query": query,
        "intent": {
            "primary": "factual",
            "confidence": 0.92,
            "features": {
                "has_question_word": True,
                "has_knowledge_word": True,
                "complexity_score": 0.6
            }
        },
        "confidence": 0.92,
        "answer": """根据2024年最新数据，五一假期推荐以下目的地：

🌸 **短途周边游（3天以内）**
- **婺源篁岭**：油菜花盛开，梯田花海美不胜收
- **杭州西湖**：春季西湖，烟雨朦胧，适合休闲漫步
- **成都周边**：青城山、都江堰，巴蜀文化之旅

🏔️ **长途热门目的地（4-5天）**
- **云南大理**：苍山洱海，风花雪月，适合慢节奏
- **厦门鼓浪屿**：海岛风情，文艺小清新
- **张家界国家森林公园**：奇峰怪石，大自然的鬼斧神工

📌 **出行建议**：
1. 提前15天预订机票酒店，避开涨价高峰
2. 关注天气预报，备好雨具和防晒
3. 人流密集景点建议错峰出行
4. 自驾注意路况和停车问题""",
        "sources": [
            {
                "title": "2024年五一假期旅游目的地推荐",
                "source": "马蜂窝",
                "url": "https://www.mafengwo.cn/search/s.html?q=五一旅游",
                "score": 0.95
            },
            {
                "title": "婺源篁岭 - 春季赏花攻略",
                "source": "携程旅行",
                "url": "https://you.ctrip.com/sight/wuyuan/12345.html",
                "score": 0.88
            },
            {
                "title": "五一假期热门景点排行榜",
                "source": "小红书",
                "url": "https://www.xiaohongshu.com/search result",
                "score": 0.82
            },
            {
                "title": "云南大理旅游完全指南",
                "source": "穷游网",
                "url": "https://www.qyer.com/china/dali/",
                "score": 0.90
            },
            {
                "title": "张家界国家森林公园游览攻略",
                "source": "马蜂窝",
                "url": "https://www.mafengwo.cn/mdd/",
                "score": 0.85
            }
        ],
        "related": [
            "五一假期攻略", "自驾游路线", "民宿推荐", 
            "旅游保险", "景点门票优惠", "行李清单"
        ],
        "stats": {
            "total_results": 128,
            "cached": False,
            "tier_distribution": {
                "TIER_1_CN_HIGH": 5,
                "TIER_2_CN_VERTICAL": 3
            },
            "sources_used": ["baidu", "mafengwo", "ctrip"],
            "avg_quality_score": 8.5,
            "avg_relevance_score": 9.1
        }
    }


def generate_tech_search_result(query: str = "Python异步编程") -> dict:
    """生成技术搜索模拟结果"""
    return {
        "query": query,
        "intent": {
            "primary": "procedural",
            "confidence": 0.88,
            "features": {
                "has_code_word": True,
                "has_technical_terms": True,
                "complexity_score": 0.7
            }
        },
        "confidence": 0.88,
        "answer": """Python异步编程详解：

📖 **核心概念**
异步编程是一种并发编程模式，允许在等待I/O操作（如网络请求、文件读写）时执行其他任务，从而提高程序效率。

🔧 **主要实现方式**

1. **async/await 语法（Python 3.5+）**
```python
import asyncio

async def fetch_data(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
```

2. **asyncio 模块**
- `asyncio.run()`: 运行异步协程
- `asyncio.gather()`: 并发执行多个任务
- `asyncio.create_task()`: 创建任务

3. **第三方库**
- `aiohttp`: 异步HTTP客户端
- `aioredis`: 异步Redis客户端
- `FastAPI`: 现代异步Web框架

⚡ **适用场景**
- 高并发网络请求
- 实时聊天应用
- 流式数据处理
- Web服务器开发""",
        "sources": [
            {
                "title": "Python官方文档 - asyncio",
                "source": "Python.org",
                "url": "https://docs.python.org/3/library/asyncio.html",
                "score": 0.98
            },
            {
                "title": "FastAPI 异步框架教程",
                "source": "FastAPI",
                "url": "https://fastapi.tiangolo.com/zh/tutorial/",
                "score": 0.92
            },
            {
                "title": "Python asyncio深度解析",
                "source": "Stack Overflow",
                "url": "https://stackoverflow.com/questions/tagged/python-asyncio",
                "score": 0.85
            },
            {
                "title": "aiohttp 官方文档",
                "source": "aiohttp",
                "url": "https://docs.aiohttp.org/",
                "score": 0.88
            }
        ],
        "related": [
            "asyncio教程", "aiohttp使用", "FastAPI教程",
            "异步vs同步", "事件循环原理", "协程详解"
        ],
        "stats": {
            "total_results": 89,
            "cached": True,
            "tier_distribution": {
                "TIER_2_CN_VERTICAL": 4
            },
            "sources_used": ["stackoverflow", "github", "python-doc"],
            "avg_quality_score": 9.2,
            "avg_relevance_score": 9.5
        }
    }


__all__ = [
    "DeepSearchPanel",
    "RichTextResultView",
    "SearchProcessWidget",
    "IntentDisplayWidget",
    "generate_travel_search_result",
    "generate_tech_search_result"
]
