"""
URL智能优化与深度搜索Wiki系统 UI面板
"""

import asyncio
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLineEdit, QPushButton, QTextBrowser, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QGroupBox, QFormLayout, QComboBox,
    QCheckBox, QListWidget, QListWidgetItem, QSplitter,
    QFrame, QScrollArea, QProgressDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QTextCharFormat, QColor


class URLTestWorker(QThread):
    """URL测试工作线程"""
    finished = pyqtSignal(object)
    progress = pyqtSignal(int, str)
    error = pyqtSignal(str)
    
    def __init__(self, url: str):
        super().__init__()
        self.url = url
    
    def run(self):
        try:
            from client.src.business.url_intelligence import get_url_system
            system = get_url_system()
            result = asyncio.run(system.optimize(self.url))
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class WikiGenerateWorker(QThread):
    """Wiki生成工作线程"""
    finished = pyqtSignal(object)
    progress = pyqtSignal(int, str)
    
    def __init__(self, topic: str, use_search: bool = True):
        super().__init__()
        self.topic = topic
        self.use_search = use_search
    
    def run(self):
        try:
            from client.src.business.deep_search_wiki import get_wiki_system
            system = get_wiki_system()
            wiki = asyncio.run(system.generate_async(self.topic, self.use_search))
            self.finished.emit(wiki)
        except Exception as e:
            self.error.emit(str(e))


class URLIntelligencePanel(QWidget):
    """URL智能优化与深度搜索Wiki系统面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_result = None
        self.current_wiki = None
        self.workers = []
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 创建标签页
        tabs = QTabWidget()
        tabs.addTab(self._create_url_tab(), "🌐 URL优化")
        tabs.addTab(self._create_wiki_tab(), "📚 深度Wiki")
        tabs.addTab(self._create_mirror_tab(), "🪞 镜像管理")
        tabs.addTab(self._create_stats_tab(), "📊 统计信息")
        
        layout.addWidget(tabs)
    
    def _create_url_tab(self) -> QWidget:
        """创建URL优化标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 输入区域
        input_group = QGroupBox("🔗 URL输入")
        input_layout = QHBoxLayout()
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("输入需要优化的URL，例如: https://github.com/microsoft/vscode")
        self.url_input.returnPressed.connect(self._optimize_url)
        
        self.optimize_btn = QPushButton("🚀 优化")
        self.optimize_btn.clicked.connect(self._optimize_url)
        
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(lambda: self._optimize_url(force_refresh=True))
        
        input_layout.addWidget(QLabel("URL:"))
        input_layout.addWidget(self.url_input, 1)
        input_layout.addWidget(self.optimize_btn)
        input_layout.addWidget(self.refresh_btn)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        # 结果区域
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 优化建议
        self.result_browser = QTextBrowser()
        self.result_browser.setOpenExternalLinks(True)
        self.result_browser.setHtml(self._get_welcome_html())
        splitter.addWidget(self._create_result_widget())
        
        # 镜像列表
        self.mirror_table = QTableWidget()
        self.mirror_table.setColumnCount(5)
        self.mirror_table.setHorizontalHeaderLabels(["名称", "类型", "延迟", "评分", "状态"])
        self.mirror_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.mirror_table.setMinimumWidth(400)
        splitter.addWidget(self.mirror_table)
        
        splitter.setSizes([500, 400])
        layout.addWidget(splitter)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        return widget
    
    def _create_result_widget(self) -> QWidget:
        """创建结果面板"""
        widget = QFrame()
        layout = QVBoxLayout(widget)
        
        title = QLabel("📋 优化结果")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        self.result_browser = QTextBrowser()
        self.result_browser.setOpenExternalLinks(True)
        layout.addWidget(self.result_browser)
        
        return widget
    
    def _create_wiki_tab(self) -> QWidget:
        """创建深度Wiki标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 输入区域
        input_group = QGroupBox("📚 Wiki主题")
        input_layout = QHBoxLayout()
        
        self.wiki_topic_input = QLineEdit()
        self.wiki_topic_input.setPlaceholderText("输入Wiki主题，例如: Python机器学习")
        self.wiki_topic_input.returnPressed.connect(self._generate_wiki)
        
        self.use_search_cb = QCheckBox("联网搜索")
        self.use_search_cb.setChecked(True)
        
        self.generate_btn = QPushButton("📖 生成Wiki")
        self.generate_btn.clicked.connect(self._generate_wiki)
        
        input_layout.addWidget(QLabel("主题:"))
        input_layout.addWidget(self.wiki_topic_input, 1)
        input_layout.addWidget(self.use_search_cb)
        input_layout.addWidget(self.generate_btn)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        # Wiki内容
        self.wiki_browser = QTextBrowser()
        self.wiki_browser.setOpenExternalLinks(True)
        self.wiki_browser.setHtml(self._get_wiki_welcome_html())
        layout.addWidget(self.wiki_browser)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        self.copy_wiki_btn = QPushButton("📋 复制Markdown")
        self.copy_wiki_btn.clicked.connect(self._copy_wiki)
        self.copy_wiki_btn.setEnabled(False)
        
        self.save_wiki_btn = QPushButton("💾 保存")
        self.save_wiki_btn.clicked.connect(self._save_wiki)
        self.save_wiki_btn.setEnabled(False)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.copy_wiki_btn)
        btn_layout.addWidget(self.save_wiki_btn)
        layout.addLayout(btn_layout)
        
        return widget
    
    def _create_mirror_tab(self) -> QWidget:
        """创建镜像管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 镜像统计
        stats_group = QGroupBox("📊 镜像源统计")
        stats_layout = QFormLayout()
        
        self.mirror_stats_label = QLabel("加载中...")
        stats_layout.addRow("状态:", self.mirror_stats_label)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # 镜像分类列表
        self.mirror_list = QListWidget()
        self.mirror_list.itemClicked.connect(self._show_mirror_details)
        layout.addWidget(self.mirror_list)
        
        # 镜像详情
        self.mirror_detail_browser = QTextBrowser()
        layout.addWidget(self.mirror_detail_browser)
        
        # 加载镜像
        self._load_mirrors()
        
        return widget
    
    def _create_stats_tab(self) -> QWidget:
        """创建统计标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # URL优化统计
        url_stats_group = QGroupBox("🔗 URL优化统计")
        url_stats_layout = QFormLayout()
        
        self.url_cache_label = QLabel("0")
        self.url_rules_label = QLabel("0")
        self.url_mirrors_label = QLabel("0")
        
        url_stats_layout.addRow("缓存条目:", self.url_cache_label)
        url_stats_layout.addRow("镜像规则:", self.url_rules_label)
        url_stats_layout.addRow("镜像源:", self.url_mirrors_label)
        
        url_stats_group.setLayout(url_stats_layout)
        layout.addWidget(url_stats_group)
        
        # Wiki统计
        wiki_stats_group = QGroupBox("📚 Wiki统计")
        wiki_stats_layout = QFormLayout()
        
        self.wiki_search_cache_label = QLabel("0")
        
        wiki_stats_layout.addRow("搜索缓存:", self.wiki_search_cache_label)
        
        wiki_stats_group.setLayout(wiki_stats_layout)
        layout.addWidget(wiki_stats_group)
        
        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新统计")
        refresh_btn.clicked.connect(self._refresh_stats)
        layout.addWidget(refresh_btn)
        
        layout.addStretch()
        
        self._refresh_stats()
        
        return widget
    
    def _get_welcome_html(self) -> str:
        """欢迎HTML"""
        return """
        <div style="text-align: center; padding: 50px; color: #666;">
            <h2>🌐 URL智能优化系统</h2>
            <p>输入URL，系统将自动检测并提供最优镜像</p>
            <br>
            <p style="color: #999;">支持的资源类型:</p>
            <ul style="text-align: left; display: inline-block;">
                <li>🔧 GitHub 代码仓库</li>
                <li>📦 npm/PyPI 包管理</li>
                <li>🤗 HuggingFace 模型</li>
                <li>🐳 Docker 镜像</li>
                <li>📄 学术论文 (arXiv)</li>
            </ul>
        </div>
        """
    
    def _get_wiki_welcome_html(self) -> str:
        """Wiki欢迎HTML"""
        return """
        <div style="text-align: center; padding: 50px; color: #666;">
            <h2>📚 深度搜索Wiki系统</h2>
            <p>输入主题，系统将自动生成结构化Wiki页面</p>
            <br>
            <p style="color: #999;">功能特点:</p>
            <ul style="text-align: left; display: inline-block;">
                <li>🔍 多源信息聚合</li>
                <li>📊 来源可信度评估</li>
                <li>📝 结构化内容组织</li>
                <li>🔗 引用标注追溯</li>
            </ul>
        </div>
        """
    
    def _optimize_url(self, force_refresh: bool = False):
        """优化URL"""
        url = self.url_input.text().strip()
        if not url:
            return
        
        # 检查URL格式
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
            self.url_input.setText(url)
        
        self.optimize_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        
        # 创建工作线程
        worker = URLTestWorker(url)
        worker.finished.connect(lambda r: self._on_optimize_complete(r, force_refresh))
        worker.error.connect(self._on_optimize_error)
        worker.start()
        self.workers.append(worker)
    
    def _on_optimize_complete(self, result, force_refresh: bool):
        """优化完成"""
        self.optimize_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.current_result = result
        
        # 更新结果浏览器
        self.result_browser.setHtml(result.to_markdown())
        
        # 更新镜像列表
        self._update_mirror_table(result)
        
        self.optimize_btn.setEnabled(True)
    
    def _on_optimize_error(self, error: str):
        """优化错误"""
        self.optimize_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        self.result_browser.setHtml(f"""
        <div style="color: red; padding: 20px;">
            <h3>❌ 优化失败</h3>
            <p>{error}</p>
        </div>
        """)
    
    def _update_mirror_table(self, result):
        """更新镜像表格"""
        self.mirror_table.setRowCount(0)
        
        mirrors = [result.recommended_mirror] + result.alternative_mirrors if result.recommended_mirror else result.all_mirrors_tested
        
        for i, mirror in enumerate(mirrors):
            if mirror is None:
                continue
            self.mirror_table.insertRow(i)
            
            self.mirror_table.setItem(i, 0, QTableWidgetItem(mirror.name))
            self.mirror_table.setItem(i, 1, QTableWidgetItem(mirror.mirror_type.value))
            
            latency_item = QTableWidgetItem(f"{mirror.latency_ms:.0f}ms")
            latency_item.setForeground(QColor("green") if mirror.latency_ms < 500 else QColor("orange"))
            self.mirror_table.setItem(i, 2, latency_item)
            
            score_item = QTableWidgetItem(f"{mirror.overall_score:.1f}")
            score_item.setForeground(QColor("green") if mirror.overall_score >= 70 else QColor("orange"))
            self.mirror_table.setItem(i, 3, score_item)
            
            status_text = "✅ 可用" if mirror.status.value == "accessible" else "❌ 不可用"
            status_item = QTableWidgetItem(status_text)
            self.mirror_table.setItem(i, 4, status_item)
    
    def _generate_wiki(self):
        """生成Wiki"""
        topic = self.wiki_topic_input.text().strip()
        if not topic:
            return
        
        use_search = self.use_search_cb.isChecked()
        
        self.generate_btn.setEnabled(False)
        self.wiki_browser.setHtml("""
        <div style="text-align: center; padding: 50px; color: #666;">
            <h3>⏳ 正在生成Wiki...</h3>
            <p>请稍候</p>
        </div>
        """)
        
        worker = WikiGenerateWorker(topic, use_search)
        worker.finished.connect(self._on_wiki_complete)
        worker.error.connect(self._on_wiki_error)
        worker.start()
        self.workers.append(worker)
    
    def _on_wiki_complete(self, wiki):
        """Wiki生成完成"""
        self.generate_btn.setEnabled(True)
        self.current_wiki = wiki
        
        # 渲染Wiki
        md = wiki.to_markdown()
        html = self._markdown_to_html(md)
        self.wiki_browser.setHtml(html)
        
        self.copy_wiki_btn.setEnabled(True)
        self.save_wiki_btn.setEnabled(True)
    
    def _on_wiki_error(self, error: str):
        """Wiki生成错误"""
        self.generate_btn.setEnabled(True)
        self.wiki_browser.setHtml(f"""
        <div style="color: red; padding: 20px;">
            <h3>❌ 生成失败</h3>
            <p>{error}</p>
        </div>
        """)
    
    def _markdown_to_html(self, md: str) -> str:
        """简单Markdown转HTML"""
        html = md
        
        # 标题
        for i in range(5, 0, -1):
            html = html.replace("#" * i + " ", f"<h{i}>", 1)
            html = html.replace("\n" + "#" * i + " ", f"</h{i}><h{i}>", 1)
            html = html.replace(f"</h{i}>\n", f"</h{i}>", 1)
        
        # 粗体
        html = html.replace("**", "<strong>", 1)
        html = html.replace("**", "</strong>", 1)
        
        # 链接
        import re
        html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html)
        
        # 列表
        lines = html.split("\n")
        new_lines = []
        in_list = False
        for line in lines:
            if line.strip().startswith("- "):
                if not in_list:
                    new_lines.append("<ul>")
                    in_list = True
                new_lines.append(f"<li>{line.strip()[2:]}</li>")
            else:
                if in_list:
                    new_lines.append("</ul>")
                    in_list = False
                new_lines.append(line)
        if in_list:
            new_lines.append("</ul>")
        html = "\n".join(new_lines)
        
        # 表格
        lines = html.split("\n")
        new_lines = []
        in_table = False
        for line in lines:
            if line.startswith("|"):
                if not in_table:
                    new_lines.append("<table border='1' style='border-collapse: collapse; width: 100%;'>")
                    in_table = True
                cells = [c.strip() for c in line.split("|")[1:-1]]
                if all(c.replace("-", "") == "" for c in cells):
                    continue
                new_lines.append("<tr>" + "".join(f"<td style='padding: 8px;'>{c}</td>" for c in cells) + "</tr>")
            else:
                if in_table:
                    new_lines.append("</table>")
                    in_table = False
                new_lines.append(line)
        if in_table:
            new_lines.append("</table>")
        html = "\n".join(new_lines)
        
        # 引用
        html = html.replace("> ", "<blockquote>")
        html = html.replace("\n>", "\n<blockquote>")
        html = html + "</blockquote>"
        
        # 段落
        html = html.replace("\n\n", "</p><p>")
        html = f"<p>{html}</p>"
        
        # 换行
        html = html.replace("\n", "<br>")
        html = html.replace("<br><table", "</p><table")
        html = html.replace("</table><br>", "</table><p>")
        html = html.replace("<br><h", "</p><h")
        html = html.replace("</h", "</h")
        html = html.replace("<br><ul>", "</p><ul>")
        html = html.replace("</ul><br>", "</ul><p>")
        html = html.replace("<br><blockquote>", "</p><blockquote>")
        
        return f"""
        <html>
        <head>
        <style>
            body {{ font-family: 'Microsoft YaHei', sans-serif; line-height: 1.6; padding: 20px; }}
            h1, h2, h3, h4, h5 {{ color: #333; }}
            a {{ color: #0066cc; }}
            blockquote {{ border-left: 3px solid #ddd; padding-left: 15px; color: #666; margin: 10px 0; }}
            table {{ margin: 10px 0; }}
            code {{ background: #f5f5f5; padding: 2px 5px; border-radius: 3px; }}
        </style>
        </head>
        <body>{html}</body>
        </html>
        """
    
    def _copy_wiki(self):
        """复制Wiki"""
        if self.current_wiki:
            from PyQt6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText(self.current_wiki.to_markdown())
            
            self.copy_wiki_btn.setText("✅ 已复制!")
            QTimer.singleShot(2000, lambda: self.copy_wiki_btn.setText("📋 复制Markdown"))
    
    def _save_wiki(self):
        """保存Wiki"""
        if self.current_wiki:
            import os
            from PyQt6.QtWidgets import QFileDialog
            
            topic = self.wiki_topic_input.text().strip().replace(" ", "_")
            filename, _ = QFileDialog.getSaveFileName(
                self, "保存Wiki", f"{topic}.md", "Markdown文件 (*.md)"
            )
            
            if filename:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(self.current_wiki.to_markdown())
                
                self.save_wiki_btn.setText("✅ 已保存!")
                QTimer.singleShot(2000, lambda: self.save_wiki_btn.setText("💾 保存"))
    
    def _load_mirrors(self):
        """加载镜像列表"""
        from client.src.business.url_intelligence import get_url_system
        
        system = get_url_system()
        stats = system.get_statistics()
        registry_stats = stats["registry_stats"]
        
        self.mirror_stats_label.setText(f"共 {registry_stats['categories']} 个类别，{registry_stats['total_mirrors']} 个镜像源")
        
        # 加载类别
        categories = registry_stats["by_category"]
        self.mirror_list.clear()
        
        for category, count in categories.items():
            item = QListWidgetItem(f"🗂️ {category} ({count}个)")
            item.setData(Qt.ItemDataRole.UserRole, category)
            self.mirror_list.addItem(item)
    
    def _show_mirror_details(self, item):
        """显示镜像详情"""
        category = item.data(Qt.ItemDataRole.UserRole)
        if not category:
            return
        
        from client.src.business.url_intelligence import get_url_system
        system = get_url_system()
        registry = system._optimizer.registry
        
        mirrors = registry.get_mirrors(category)
        
        html = f"<h3>📦 {category} 镜像源</h3><table border='1' cellpadding='5'>"
        html += "<tr><th>名称</th><th>URL</th><th>位置</th><th>类型</th><th>同步频率</th></tr>"
        
        for m in mirrors:
            html += f"<tr><td>{m.name}</td><td><a href='{m.url}'>{m.url}</a></td>"
            html += f"<td>{m.location}</td><td>{m.mirror_type.value}</td>"
            html += f"<td>{m.sync_frequency}</td></tr>"
        
        html += "</table>"
        self.mirror_detail_browser.setHtml(html)
    
    def _refresh_stats(self):
        """刷新统计"""
        from client.src.business.url_intelligence import get_url_system
        from client.src.business.deep_search_wiki import get_wiki_system
        
        # URL优化统计
        url_system = get_url_system()
        url_stats = url_system.get_statistics()
        
        self.url_cache_label.setText(str(url_stats["cache_size"]))
        self.url_rules_label.setText(str(url_stats["registry_stats"]["total_rules"]))
        self.url_mirrors_label.setText(str(url_stats["registry_stats"]["total_mirrors"]))
        
        # Wiki统计
        wiki_system = get_wiki_system()
        wiki_stats = wiki_system.get_statistics()
        
        self.wiki_search_cache_label.setText(str(wiki_stats["search_stats"]["cache_size"]))
    
    def closeEvent(self, event):
        """关闭时清理"""
        for worker in self.workers:
            if worker.isRunning():
                worker.terminate()
        super().closeEvent(event)
