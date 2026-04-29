"""
智能创作与专业审核增强系统 - PyQt6 UI面板
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTextEdit, QPushButton, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QProgressBar,
    QGroupBox, QFormLayout, QSplitter, QListWidget,
    QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
    QScrollArea, QFrame, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QTextCursor

from core.creative_review_system import (
    create_integrated_system, CreativeReviewIntegratedSystem,
    ReviewDomain, ReviewLevel
)


class ReviewThread(QThread):
    """审核线程"""
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int, str)
    error = pyqtSignal(str)
    
    def __init__(self, system, doc_id, level):
        super().__init__()
        self.system = system
        self.doc_id = doc_id
        self.level = level
    
    def run(self):
        try:
            self.progress.emit(30, "正在审核...")
            result = self.system.review_document(self.doc_id, self.level)
            self.progress.emit(100, "审核完成")
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class CreativeReviewPanel(QWidget):
    """智能创作与专业审核面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.system = create_integrated_system()
        self.current_doc_id = None
        self.review_thread = None
        
        self.init_ui()
        self.init_connections()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 标签页
        self.tabs = QTabWidget()
        
        # Tab 1: 创作助手
        self.tabs.addTab(self._create_creation_tab(), "✍️ 智能创作")
        
        # Tab 2: 专业审核
        self.tabs.addTab(self._create_review_tab(), "🔍 专业审核")
        
        # Tab 3: 质量认证
        self.tabs.addTab(self._create_certification_tab(), "🏆 质量认证")
        
        # Tab 4: 知识库
        self.tabs.addTab(self._create_knowledge_tab(), "📚 知识库")
        
        # Tab 5: 协同创作
        self.tabs.addTab(self._create_collaboration_tab(), "👥 协同创作")
        
        # Tab 6: 系统概览
        self.tabs.addTab(self._create_overview_tab(), "📊 系统概览")
        
        layout.addWidget(self.tabs)
    
    def _create_creation_tab(self) -> QWidget:
        """创建创作助手标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 标题输入
        title_group = QGroupBox("文档信息")
        title_layout = QFormLayout()
        
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("输入文档标题...")
        title_layout.addRow("标题:", self.title_input)
        
        self.domain_combo = QComboBox()
        self.domain_combo.addItems(["通用", "环评", "财务", "法律", "技术"])
        title_layout.addRow("领域:", self.domain_combo)
        
        title_group.setLayout(title_layout)
        layout.addWidget(title_group)
        
        # 内容输入
        content_group = QGroupBox("文档内容")
        content_layout = QVBoxLayout()
        
        self.content_input = QTextEdit()
        self.content_input.setPlaceholderText("输入文档内容...")
        self.content_input.setMinimumHeight(200)
        content_layout.addWidget(self.content_input)
        
        content_group.setLayout(content_layout)
        layout.addWidget(content_group)
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        self.analyze_btn = QPushButton("🔍 分析内容")
        self.analyze_btn.clicked.connect(self.analyze_content)
        btn_layout.addWidget(self.analyze_btn)
        
        self.improve_btn = QPushButton("✨ 优化内容")
        self.improve_btn.clicked.connect(self.improve_content)
        btn_layout.addWidget(self.improve_btn)
        
        self.create_btn = QPushButton("📝 创建并审核")
        self.create_btn.clicked.connect(self.create_document)
        btn_layout.addWidget(self.create_btn)
        
        layout.addLayout(btn_layout)
        
        # 分析结果
        self.analysis_result = QTextEdit()
        self.analysis_result.setReadOnly(True)
        self.analysis_result.setMaximumHeight(150)
        layout.addWidget(QLabel("📊 分析结果:"))
        layout.addWidget(self.analysis_result)
        
        return widget
    
    def _create_review_tab(self) -> QWidget:
        """创建专业审核标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 审核控制
        control_group = QGroupBox("审核控制")
        control_layout = QHBoxLayout()
        
        self.doc_id_input = QLineEdit()
        self.doc_id_input.setPlaceholderText("输入文档ID...")
        control_layout.addWidget(QLabel("文档ID:"))
        control_layout.addWidget(self.doc_id_input)
        
        self.review_level_combo = QComboBox()
        self.review_level_combo.addItems([
            "自动预审", "专业深度审核", "综合评估", "最终审核"
        ])
        control_layout.addWidget(QLabel("审核级别:"))
        control_layout.addWidget(self.review_level_combo)
        
        self.start_review_btn = QPushButton("🚀 开始审核")
        self.start_review_btn.clicked.connect(self.start_review)
        control_layout.addWidget(self.start_review_btn)
        
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # 审核进度
        self.review_progress = QProgressBar()
        self.review_progress.setVisible(False)
        layout.addWidget(self.review_progress)
        
        self.review_status = QLabel("")
        layout.addWidget(self.review_status)
        
        # 审核结果
        results_group = QGroupBox("审核结果")
        results_layout = QVBoxLayout()
        
        self.review_result_widget = QTextEdit()
        self.review_result_widget.setReadOnly(True)
        results_layout.addWidget(self.review_result_widget)
        
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        # 问题列表
        issues_group = QGroupBox("问题列表")
        issues_layout = QVBoxLayout()
        
        self.issues_table = QTableWidget()
        self.issues_table.setColumnCount(5)
        self.issues_table.setHorizontalHeaderLabels(["严重程度", "类型", "标题", "描述", "建议"])
        issues_layout.addWidget(self.issues_table)
        
        issues_group.setLayout(issues_layout)
        layout.addWidget(issues_group)
        
        return widget
    
    def _create_certification_tab(self) -> QWidget:
        """创建质量认证标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 认证控制
        cert_control = QGroupBox("质量认证")
        cert_layout = QHBoxLayout()
        
        self.cert_doc_id_input = QLineEdit()
        self.cert_doc_id_input.setPlaceholderText("输入文档ID...")
        cert_layout.addWidget(QLabel("文档ID:"))
        cert_layout.addWidget(self.cert_doc_id_input)
        
        self.certify_btn = QPushButton("🏆 颁发认证")
        self.certify_btn.clicked.connect(self.certify_document)
        cert_layout.addWidget(self.certify_btn)
        
        cert_control.setLayout(cert_layout)
        layout.addWidget(cert_control)
        
        # 认证结果
        cert_result_group = QGroupBox("认证报告")
        cert_result_layout = QVBoxLayout()
        
        self.cert_result_widget = QTextEdit()
        self.cert_result_widget.setReadOnly(True)
        cert_result_layout.addWidget(self.cert_result_widget)
        
        cert_result_group.setLayout(cert_result_layout)
        layout.addWidget(cert_result_group)
        
        # 质量指标
        metrics_group = QGroupBox("质量指标")
        metrics_layout = QGridLayout()
        
        self.metric_widgets = {}
        metrics = ["准确性", "完整性", "一致性", "清晰度", "专业性", "创新性"]
        
        for i, metric in enumerate(metrics):
            metrics_layout.addWidget(QLabel(f"{metric}:"), i // 2, (i % 2) * 2)
            bar = QProgressBar()
            bar.setRange(0, 100)
            self.metric_widgets[metric] = bar
            metrics_layout.addWidget(bar, i // 2, (i % 2) * 2 + 1)
        
        metrics_group.setLayout(metrics_layout)
        layout.addWidget(metrics_group)
        
        return widget
    
    def _create_knowledge_tab(self) -> QWidget:
        """创建知识库标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 搜索
        search_group = QGroupBox("知识搜索")
        search_layout = QHBoxLayout()
        
        self.knowledge_query = QLineEdit()
        self.knowledge_query.setPlaceholderText("搜索知识...")
        search_layout.addWidget(self.knowledge_query)
        
        self.search_knowledge_btn = QPushButton("🔍 搜索")
        self.search_knowledge_btn.clicked.connect(self.search_knowledge)
        search_layout.addWidget(self.search_knowledge_btn)
        
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)
        
        # 知识列表
        knowledge_group = QGroupBox("知识条目")
        knowledge_layout = QVBoxLayout()
        
        self.knowledge_list = QListWidget()
        self.knowledge_list.itemDoubleClicked.connect(self.view_knowledge_item)
        knowledge_layout.addWidget(self.knowledge_list)
        
        knowledge_group.setLayout(knowledge_layout)
        layout.addWidget(knowledge_group)
        
        # 知识详情
        self.knowledge_detail = QTextEdit()
        self.knowledge_detail.setReadOnly(True)
        self.knowledge_detail.setMaximumHeight(150)
        layout.addWidget(QLabel("知识详情:"))
        layout.addWidget(self.knowledge_detail)
        
        return widget
    
    def _create_collaboration_tab(self) -> QWidget:
        """创建协同创作标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 工作空间
        ws_group = QGroupBox("工作空间")
        ws_layout = QHBoxLayout()
        
        self.workspace_name = QLineEdit()
        self.workspace_name.setPlaceholderText("工作空间名称...")
        ws_layout.addWidget(QLabel("名称:"))
        ws_layout.addWidget(self.workspace_name)
        
        self.create_ws_btn = QPushButton("➕ 创建空间")
        self.create_ws_btn.clicked.connect(self.create_workspace)
        ws_layout.addWidget(self.create_ws_btn)
        
        ws_group.setLayout(ws_layout)
        layout.addWidget(ws_group)
        
        # 协作文档
        collab_group = QGroupBox("协作内容")
        collab_layout = QVBoxLayout()
        
        self.collab_content = QTextEdit()
        self.collab_content.setPlaceholderText("协作内容...")
        collab_layout.addWidget(self.collab_content)
        
        collab_btn_layout = QHBoxLayout()
        
        self.save_collab_btn = QPushButton("💾 保存")
        self.save_collab_btn.clicked.connect(self.save_collaboration)
        collab_btn_layout.addWidget(self.save_collab_btn)
        
        self.add_comment_btn = QPushButton("💬 添加评论")
        self.add_comment_btn.clicked.connect(self.add_comment)
        collab_btn_layout.addWidget(self.add_comment_btn)
        
        collab_layout.addLayout(collab_btn_layout)
        collab_group.setLayout(collab_layout)
        layout.addWidget(collab_group)
        
        # 评论列表
        comments_group = QGroupBox("评论")
        comments_layout = QVBoxLayout()
        
        self.comments_list = QListWidget()
        comments_layout.addWidget(self.comments_list)
        
        comments_group.setLayout(comments_layout)
        layout.addWidget(comments_group)
        
        return widget
    
    def _create_overview_tab(self) -> QWidget:
        """创建系统概览标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 统计概览
        stats_group = QGroupBox("系统统计")
        stats_layout = QGridLayout()
        
        self.stats_labels = {}
        stats_items = [
            "总文档数", "总审核数", "总认证数", "平均质量分",
            "活跃工作空间", "知识条目数"
        ]
        
        for i, item in enumerate(stats_items):
            stats_layout.addWidget(QLabel(f"{item}:"), i, 0)
            label = QLabel("0")
            label.setStyleSheet("font-size: 16px; font-weight: bold;")
            self.stats_labels[item] = label
            stats_layout.addWidget(label, i, 1)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新统计")
        refresh_btn.clicked.connect(self.refresh_stats)
        layout.addWidget(refresh_btn)
        
        layout.addStretch()
        
        return widget
    
    def init_connections(self):
        """初始化连接"""
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_stats)
        self.timer.start(30000)  # 每30秒刷新
    
    # ========== 槽函数 ==========
    
    def analyze_content(self):
        """分析内容"""
        content = self.content_input.toPlainText()
        if not content:
            self.analysis_result.setHtml("<b>请输入内容</b>")
            return
        
        analysis = self.system.creative_system.analyze(content, self.domain_combo.currentText())
        
        result_html = f"""
        <b>📊 内容分析结果</b><br>
        <hr>
        <b>基础统计:</b><br>
        - 字数: {analysis.word_count} | 字符: {analysis.char_count}<br>
        - 句子: {analysis.sentence_count} | 段落: {analysis.paragraph_count}<br>
        <b>质量评分:</b> {analysis.quality_score:.1f}/100<br>
        <b>可读性:</b> {analysis.readability_score:.1f}/100<br>
        <b>复杂度:</b> {analysis.complexity}<br>
        <b>关键词:</b> {', '.join(analysis.keywords[:5])}<br>
        """
        
        if analysis.issues:
            result_html += f"<br><b>问题 ({len(analysis.issues)}):</b><br>"
            for issue in analysis.issues[:5]:
                result_html += f"- [{issue['severity']}] {issue['message']}<br>"
        
        self.analysis_result.setHtml(result_html)
    
    def improve_content(self):
        """优化内容"""
        content = self.content_input.toPlainText()
        if not content:
            return
        
        improved = self.system.creative_system.improve(content)
        self.content_input.setPlainText(improved)
        self.analysis_result.setHtml("<b>✅ 内容已优化</b>")
    
    def create_document(self):
        """创建文档"""
        title = self.title_input.text()
        content = self.content_input.toPlainText()
        domain = self.domain_combo.currentText().lower()
        
        if not title or not content:
            self.analysis_result.setHtml("<b>请输入标题和内容</b>")
            return
        
        result = self.system.create_with_assistance(title, content, domain)
        self.current_doc_id = result["doc_id"]
        
        self.doc_id_input.setText(self.current_doc_id)
        self.cert_doc_id_input.setText(self.current_doc_id)
        
        # 显示改进后的内容
        self.content_input.setPlainText(result["improved_content"])
        
        # 显示创建结果
        result_html = f"""
        <b>✅ 文档创建成功</b><br>
        <hr>
        <b>文档ID:</b> {self.current_doc_id}<br>
        <b>改进字数:</b> {len(content)} → {len(result['improved_content'])}<br>
        <b>建议数量:</b> {len(result['suggestions'])}<br>
        """
        
        if result['suggestions']:
            result_html += "<br><b>建议:</b><br>"
            for s in result['suggestions']:
                result_html += f"- {s['type']}: {s['reason']}<br>"
        
        self.analysis_result.setHtml(result_html)
        
        # 自动切换到审核标签
        self.tabs.setCurrentIndex(1)
    
    def start_review(self):
        """开始审核"""
        doc_id = self.doc_id_input.text()
        if not doc_id:
            self.review_status.setText("请输入文档ID")
            return
        
        level_map = {
            0: ReviewLevel.AUTO_PREVIEW,
            1: ReviewLevel.PROFESSIONAL,
            2: ReviewLevel.COMPREHENSIVE,
            3: ReviewLevel.FINAL
        }
        level = level_map.get(self.review_level_combo.currentIndex(), ReviewLevel.AUTO_PREVIEW)
        
        self.review_progress.setVisible(True)
        self.review_progress.setValue(0)
        self.start_review_btn.setEnabled(False)
        
        self.review_thread = ReviewThread(self.system, doc_id, level)
        self.review_thread.progress.connect(self._on_review_progress)
        self.review_thread.finished.connect(self._on_review_finished)
        self.review_thread.error.connect(self._on_review_error)
        self.review_thread.start()
    
    def _on_review_progress(self, value: int, status: str):
        """审核进度更新"""
        self.review_progress.setValue(value)
        self.review_status.setText(status)
    
    def _on_review_finished(self, result: dict):
        """审核完成"""
        self.review_progress.setVisible(False)
        self.start_review_btn.setEnabled(True)
        
        # 显示审核结果
        review_result = result.get("review_result", {})
        opinion = result.get("opinion", {})
        
        result_html = f"""
        <b>🔍 审核结果</b><br>
        <hr>
        <b>审核ID:</b> {review_result.get('result_id', 'N/A')[:20]}...<br>
        <b>综合评分:</b> {review_result.get('overall_score', 0):.1f}/100<br>
        <b>质量等级:</b> {review_result.get('quality_level', 'N/A')}<br>
        <b>状态:</b> {review_result.get('status', 'N/A')}<br>
        <b>处理时间:</b> {result.get('processing_time_ms', 0):.0f}ms<br>
        <br>
        <b>📋 审核意见:</b><br>
        {opinion.get('summary', '')}<br>
        <b>判定:</b> {opinion.get('verdict', '')}<br>
        """
        
        self.review_result_widget.setHtml(result_html)
        
        # 更新问题列表
        issues = result.get("issues", [])
        self.issues_table.setRowCount(len(issues))
        
        for i, issue in enumerate(issues):
            self.issues_table.setItem(i, 0, QTableWidgetItem(issue.get("severity", "")))
            self.issues_table.setItem(i, 1, QTableWidgetItem(issue.get("category", "")))
            self.issues_table.setItem(i, 2, QTableWidgetItem(issue.get("title", "")))
            self.issues_table.setItem(i, 3, QTableWidgetItem(issue.get("description", "")[:50]))
            self.issues_table.setItem(i, 4, QTableWidgetItem(issue.get("suggestion", "")[:50]))
        
        self.issues_table.resizeColumnsToContents()
    
    def _on_review_error(self, error: str):
        """审核错误"""
        self.review_progress.setVisible(False)
        self.start_review_btn.setEnabled(True)
        self.review_status.setText(f"错误: {error}")
    
    def certify_document(self):
        """颁发认证"""
        doc_id = self.cert_doc_id_input.text()
        if not doc_id:
            self.cert_result_widget.setHtml("<b>请输入文档ID</b>")
            return
        
        try:
            cert_result = self.system.certify_quality(doc_id)
            
            # 显示认证结果
            result_html = f"""
            <b>🏆 质量认证报告</b><br>
            <hr>
            <b>认证ID:</b> {cert_result.get('cert_id', 'N/A')[:20]}...<br>
            <b>综合评分:</b> {cert_result.get('overall_score', 0):.1f}/100<br>
            <b>认证级别:</b> {cert_result.get('cert_level', 'N/A')}<br>
            <b>已认证:</b> {'是' if cert_result.get('certified') else '否'}<br>
            """
            
            metrics = cert_result.get('metrics', {})
            result_html += "<br><b>维度评分:</b><br>"
            metric_names = {
                'accuracy': '准确性', 'completeness': '完整性',
                'consistency': '一致性', 'clarity': '清晰度',
                'professionalism': '专业性', 'innovation': '创新性'
            }
            
            for key, name in metric_names.items():
                value = metrics.get(key, 0)
                self.metric_widgets[name].setValue(int(value))
                result_html += f"- {name}: {value:.1f}<br>"
            
            if cert_result.get('strengths'):
                result_html += "<br><b>✅ 优点:</b><br>"
                for s in cert_result['strengths']:
                    result_html += f"- {s}<br>"
            
            if cert_result.get('recommendations'):
                result_html += "<br><b>💡 建议:</b><br>"
                for r in cert_result['recommendations']:
                    result_html += f"- {r}<br>"
            
            self.cert_result_widget.setHtml(result_html)
            
        except Exception as e:
            self.cert_result_widget.setHtml(f"<b>错误:</b> {str(e)}")
    
    def search_knowledge(self):
        """搜索知识"""
        query = self.knowledge_query.text()
        if not query:
            return
        
        results = self.system.search_knowledge(query)
        
        self.knowledge_list.clear()
        for item in results[:20]:
            self.knowledge_list.addItem(item.get("title", "Untitled"))
    
    def view_knowledge_item(self, item):
        """查看知识条目"""
        query = self.knowledge_query.text()
        results = self.system.search_knowledge(query)
        
        index = self.knowledge_list.currentRow()
        if index < len(results):
            entry = results[index]
            detail = f"""
            <b>{entry.get('title', '')}</b><br>
            <hr>
            <b>分类:</b> {entry.get('category', 'N/A')}<br>
            <b>领域:</b> {entry.get('domain', 'N/A')}<br>
            <b>质量:</b> {entry.get('quality_score', 0):.1f}<br>
            <br>
            {entry.get('content', '')[:500]}...
            """
            self.knowledge_detail.setHtml(detail)
    
    def create_workspace(self):
        """创建工作空间"""
        name = self.workspace_name.text()
        if not name:
            return
        
        result = self.system.create_workspace(name, "current_user")
        self.workspace_name.setText(f"Created: {result['workspace_id'][:20]}...")
    
    def save_collaboration(self):
        """保存协作"""
        # 实现保存逻辑
        pass
    
    def add_comment(self):
        """添加评论"""
        # 实现评论逻辑
        pass
    
    def refresh_stats(self):
        """刷新统计"""
        try:
            stats = self.system.get_system_stats()
            
            self.stats_labels["总文档数"].setText(str(stats.get("total_documents", 0)))
            self.stats_labels["总审核数"].setText(str(stats.get("total_reviews", 0)))
            self.stats_labels["总认证数"].setText(str(stats.get("total_certs", 0)))
            
            quality_stats = stats.get("quality_stats", {})
            avg_score = quality_stats.get("avg_score", 0)
            self.stats_labels["平均质量分"].setText(f"{avg_score:.1f}")
            
            collab_stats = stats.get("collaboration_stats", {})
            self.stats_labels["活跃工作空间"].setText(str(collab_stats.get("active_workspaces", 0)))
            
            knowledge_stats = stats.get("knowledge_stats", {})
            self.stats_labels["知识条目数"].setText(str(knowledge_stats.get("total_entries", 0)))
            
        except Exception as e:
            print(f"刷新统计失败: {e}")
