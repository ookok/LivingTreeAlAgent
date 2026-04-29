"""
LLM Wiki 管理面板
=================

提供 LLM 文档的解析、KnowledgeGraph 集成、图谱推理等功能的 UI 界面。

功能：
1. 文档解析（Phase 1）：Markdown、PDF、代码
2. KnowledgeGraph 集成（Phase 2/2+）：章节结构导入、分块顺序保留
3. 高级功能（Phase 3）：跨文档引用、实体链接、图谱推理
4. 查询与推理：路径查找、子图提取、相关概念查询

作者: LivingTreeAI Team
日期: 2026-04-29
版本: 1.0.0
"""

import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QMessageBox, QSplitter, QTextEdit, QTabWidget,
    QComboBox, QProgressBar, QTextBrowser,
    QFileDialog, QGroupBox, QFormLayout,
    QLineEdit, QSpinBox, QCheckBox, QPlainTextEdit
)
from PyQt6.QtGui import QFont, QTextCursor


# ── LLM Wiki 面板主界面 ─────────────────────────────────────────────────────
class LLMWikiPanel(QWidget):
    """
    LLM Wiki 管理面板
    
    功能标签页：
    1. 文档解析（Phase 1）
    2. KnowledgeGraph 集成（Phase 2/2+）
    3. 高级功能（Phase 3）
    4. 图谱推理
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 数据
        self._current_chunks: List[Any] = []  # DocumentChunk list
        self._current_graph: Optional[Any] = None  # KnowledgeGraph
        self._current_file: Optional[str] = None
        
        # UI 组件
        self.file_list: Optional[QListWidget] = None
        self.chunk_list: Optional[QListWidget] = None
        self.graph_info: Optional[QTextBrowser] = None
        self.log_output: Optional[QTextBrowser] = None
        
        self._init_ui()
        self._init_connections()
    
    # ── 初始化 ─────────────────────────────────────────────────────────────
    
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # 标题
        title = QLabel("📚 LLM Wiki 知识库")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)
        
        desc = QLabel("LLM 文档解析 · KnowledgeGraph 集成 · 图谱推理")
        desc.setStyleSheet("font-size: 14px; color: #666;")
        layout.addWidget(desc)
        
        # 工具栏
        toolbar = self._create_toolbar()
        layout.addLayout(toolbar)
        
        # 主内容区（分割器）
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：文件列表 + 分块列表
        left_widget = self._create_left_panel()
        splitter.addWidget(left_widget)
        
        # 右侧：标签页（图谱信息、推理、日志）
        right_widget = self._create_right_panel()
        splitter.addWidget(right_widget)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)
    
    def _create_toolbar(self) -> QHBoxLayout:
        """创建工具栏"""
        toolbar = QHBoxLayout()
        
        # 打开文件
        self.open_file_btn = QPushButton("📂 打开文件")
        self.open_file_btn.clicked.connect(self._open_file)
        toolbar.addWidget(self.open_file_btn)
        
        # 打开目录
        self.open_dir_btn = QPushButton("📁 打开目录")
        self.open_dir_btn.clicked.connect(self._open_directory)
        toolbar.addWidget(self.open_dir_btn)
        
        toolbar.addStretch()
        
        # 解析按钮
        self.parse_btn = QPushButton("🔍 解析文档")
        self.parse_btn.clicked.connect(self._parse_document)
        self.parse_btn.setEnabled(False)
        toolbar.addWidget(self.parse_btn)
        
        # 集成到图谱按钮
        self.integrate_btn = QPushButton("🔗 集成到图谱")
        self.integrate_btn.clicked.connect(self._integrate_to_graph)
        self.integrate_btn.setEnabled(False)
        toolbar.addWidget(self.integrate_btn)
        
        return toolbar
    
    def _create_left_panel(self) -> QWidget:
        """创建左侧面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 文件列表
        file_group = QGroupBox("📂 已加载文件")
        file_layout = QVBoxLayout(file_group)
        
        self.file_list = QListWidget()
        self.file_list.itemClicked.connect(self._on_file_selected)
        file_layout.addWidget(self.file_list)
        
        layout.addWidget(file_group)
        
        # 分块列表
        chunk_group = QGroupBox("📄 文档分块")
        chunk_layout = QVBoxLayout(chunk_group)
        
        self.chunk_list = QListWidget()
        self.chunk_list.itemClicked.connect(self._on_chunk_selected)
        chunk_layout.addWidget(self.chunk_list)
        
        layout.addWidget(chunk_group)
        
        return widget
    
    def _create_right_panel(self) -> QWidget:
        """创建右侧面板（标签页）"""
        tabs = QTabWidget()
        
        # Tab 1: 图谱信息
        graph_tab = self._create_graph_tab()
        tabs.addTab(graph_tab, "🔗 图谱信息")
        
        # Tab 2: 图谱推理
        reason_tab = self._create_reason_tab()
        tabs.addTab(reason_tab, "🧠 图谱推理")
        
        # Tab 3: 日志
        log_tab = self._create_log_tab()
        tabs.addTab(log_tab, "📋 日志")
        
        return tabs
    
    def _create_graph_tab(self) -> QWidget:
        """创建图谱信息标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 图谱统计信息
        stats_group = QGroupBox("📊 图谱统计")
        stats_layout = QFormLayout(stats_group)
        
        self.stats_nodes = QLabel("0")
        stats_layout.addRow("节点数:", self.stats_nodes)
        
        self.stats_relations = QLabel("0")
        stats_layout.addRow("关系数:", self.stats_relations)
        
        self.stats_chunk_order = QLabel("0")
        stats_layout.addRow("分块顺序长度:", self.stats_chunk_order)
        
        self.stats_rel_types = QTextBrowser()
        self.stats_rel_types.setMaximumHeight(100)
        stats_layout.addRow("关系类型:", self.stats_rel_types)
        
        layout.addWidget(stats_group)
        
        # 查询接口
        query_group = QGroupBox("🔍 查询")
        query_layout = QVBoxLayout(query_group)
        
        # 按索引获取分块
        index_layout = QHBoxLayout()
        index_layout.addWidget(QLabel("索引:"))
        self.query_index_spin = QSpinBox()
        self.query_index_spin.setMinimum(0)
        self.query_index_spin.setMaximum(999)
        index_layout.addWidget(self.query_index_spin)
        self.query_index_btn = QPushButton("查询")
        self.query_index_btn.clicked.connect(self._query_chunk_by_index)
        index_layout.addWidget(self.query_index_btn)
        index_layout.addStretch()
        query_layout.addLayout(index_layout)
        
        # 查询结果显示
        self.query_result = QTextBrowser()
        self.query_result.setMaximumHeight(150)
        query_layout.addWidget(self.query_result)
        
        layout.addWidget(query_group)
        
        layout.addStretch()
        return widget
    
    def _create_reason_tab(self) -> QWidget:
        """创建图谱推理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 路径查找
        path_group = QGroupBox("🗺️ 路径查找")
        path_layout = QVBoxLayout(path_group)
        
        self.path_start = QLineEdit()
        self.path_start.setPlaceholderText("起始节点 ID")
        path_layout.addWidget(QLabel("起始节点:"))
        path_layout.addWidget(self.path_start)
        
        self.path_end = QLineEdit()
        self.path_end.setPlaceholderText("目标节点 ID")
        path_layout.addWidget(QLabel("目标节点:"))
        path_layout.addWidget(self.path_end)
        
        self.path_btn = QPushButton("查找路径")
        self.path_btn.clicked.connect(self._find_path)
        path_layout.addWidget(self.path_btn)
        
        self.path_result = QTextBrowser()
        path_layout.addWidget(self.path_result)
        
        layout.addWidget(path_group)
        
        # 推理问答
        reason_group = QGroupBox("💡 推理问答")
        reason_layout = QVBoxLayout(reason_group)
        
        self.reason_query = QPlainTextEdit()
        self.reason_query.setPlaceholderText("输入查询问题...")
        self.reason_query.setMaximumHeight(80)
        reason_layout.addWidget(self.reason_query)
        
        self.reason_btn = QPushButton("推理")
        self.reason_btn.clicked.connect(self._reason_over_graph)
        reason_layout.addWidget(self.reason_btn)
        
        self.reason_result = QTextBrowser()
        reason_layout.addWidget(self.reason_result)
        
        layout.addWidget(reason_group)
        
        return widget
    
    def _create_log_tab(self) -> QWidget:
        """创建日志标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.log_output = QTextBrowser()
        self.log_output.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
        layout.addWidget(self.log_output)
        
        # 清空按钮
        clear_btn = QPushButton("清空日志")
        clear_btn.clicked.connect(lambda: self.log_output.clear())
        layout.addWidget(clear_btn)
        
        return widget
    
    # ── 信号连接 ────────────────────────────────────────────────────────────
    
    def _init_connections(self):
        """初始化信号连接"""
        pass  # 已在 _create_toolbar 中连接
    
    # ── 槽函数 ──────────────────────────────────────────────────────────────
    
    def _open_file(self):
        """打开单个文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 LLM 文档",
            "",
            "Markdown Files (*.md *.markdown);;Python Files (*.py);;All Files (*)"
        )
        
        if file_path:
            self._current_file = file_path
            self.parse_btn.setEnabled(True)
            self._log(f"已选择文件: {file_path}")
            
            # 添加到文件列表
            self.file_list.addItem(file_path)
    
    def _open_directory(self):
        """打开目录（批量处理）"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择文档目录",
            ""
        )
        
        if dir_path:
            self._current_file = dir_path
            self.parse_btn.setEnabled(True)
            self._log(f"已选择目录: {dir_path}")
            
            # 添加到文件列表
            self.file_list.addItem(f"[DIR] {dir_path}")
    
    def _parse_document(self):
        """解析文档"""
        if not self._current_file:
            QMessageBox.warning(self, "警告", "请先选择文件或目录")
            return
        
        try:
            self._log(f"开始解析: {self._current_file}")
            
            # 导入 LLM Wiki 模块
            from client.src.business.llm_wiki import LLMDocumentParser, load_and_integrate_markdown_v3
            
            # 判断是文件还是目录
            if os.path.isfile(self._current_file):
                # 单个文件
                parser = LLMDocumentParser()
                
                if self._current_file.endswith('.md'):
                    self._current_chunks = parser.parse_markdown(self._current_file)
                elif self._current_file.endswith('.py'):
                    with open(self._current_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    self._current_chunks = parser.parse_python_file(self._current_file, content)
                else:
                    QMessageBox.warning(self, "警告", f"不支持的文件类型: {self._current_file}")
                    return
                
            elif os.path.isdir(self._current_file):
                # 目录：批量处理
                self._current_chunks = []
                parser = LLMDocumentParser()
                
                for root, dirs, files in os.walk(self._current_file):
                    for file in files:
                        if file.endswith('.md'):
                            file_path = os.path.join(root, file)
                            chunks = parser.parse_markdown(file_path)
                            self._current_chunks.extend(chunks)
                            self._log(f"  已解析: {file_path} ({len(chunks)} 个块)")
                
                self._log(f"目录解析完成: 共 {len(self._current_chunks)} 个块")
            
            # 更新分块列表
            self._update_chunk_list()
            
            # 启用集成按钮
            if self._current_chunks:
                self.integrate_btn.setEnabled(True)
            
            self._log(f"✅ 解析完成: {len(self._current_chunks)} 个块")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"解析失败: {str(e)}")
            self._log(f"❌ 解析失败: {str(e)}")
    
    def _integrate_to_graph(self):
        """集成到 KnowledgeGraph"""
        if not self._current_chunks:
            QMessageBox.warning(self, "警告", "请先解析文档")
            return
        
        try:
            self._log(f"开始集成到 KnowledgeGraph（Phase 3）...")
            
            # 导入并调用 V3 版本
            from client.src.business.llm_wiki import integrate_llm_wiki_to_graph_v3
            
            self._current_graph = integrate_llm_wiki_to_graph_v3(
                self._current_chunks,
                domain="llm_wiki_ui",
                enable_cache=True
            )
            
            # 更新图谱信息
            self._update_graph_info()
            
            self._log(f"✅ 集成完成: {len(self._current_graph.nodes)} 个节点, {len(self._current_graph.relations)} 个关系")
            
            QMessageBox.information(self, "成功", f"集成完成！\n节点数: {len(self._current_graph.nodes)}\n关系数: {len(self._current_graph.relations)}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"集成失败: {str(e)}")
            self._log(f"❌ 集成失败: {str(e)}")
    
    def _update_chunk_list(self):
        """更新分块列表"""
        self.chunk_list.clear()
        
        for i, chunk in enumerate(self._current_chunks):
            item_text = f"[{i}] {chunk.chunk_type}: {chunk.title or '(无标题)'}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, i)  # 存储索引
            self.chunk_list.addItem(item)
    
    def _update_graph_info(self):
        """更新图谱信息"""
        if not self._current_graph:
            return
        
        # 统计信息
        stats = self._current_graph.get_statistics()
        
        self.stats_nodes.setText(str(stats.get('node_count', 0)))
        self.stats_relations.setText(str(stats.get('relation_count', 0)))
        
        # 如果可用，显示更详细的统计
        if hasattr(self._current_graph, 'get_statistics'):
            try:
                detailed_stats = self._current_graph.get_statistics()
                self.stats_chunk_order.setText(str(detailed_stats.get('chunk_order_length', 0)))
                
                # 关系类型
                rel_types = detailed_stats.get('relation_types', {})
                rel_text = "\n".join([f"  - {k}: {v}" for k, v in rel_types.items()])
                self.stats_rel_types.setText(rel_text)
            except:
                pass
    
    def _query_chunk_by_index(self):
        """按索引查询分块"""
        if not self._current_graph:
            QMessageBox.warning(self, "警告", "请先集成到图谱")
            return
        
        index = self.query_index_spin.value()
        
        try:
            from client.src.business.llm_wiki import LLMWikiKnowledgeGraphIntegratorV3
            
            # 创建临时集成器来获取查询接口
            integrator = LLMWikiKnowledgeGraphIntegratorV3(domain="temp")
            integrator.graph = self._current_graph
            
            node = integrator.get_chunk_by_index(index)
            
            if node:
                result_text = f"节点 ID: {node.node_id}\n"
                result_text += f"标题: {node.title}\n"
                result_text += f"类型: {node.node_type}\n"
                result_text += f"内容: {node.content[:200]}...\n"
                self.query_result.setText(result_text)
            else:
                self.query_result.setText(f"未找到索引 {index} 对应的节点")
                
        except Exception as e:
            self.query_result.setText(f"查询失败: {str(e)}")
    
    def _find_path(self):
        """查找路径"""
        if not self._current_graph:
            QMessageBox.warning(self, "警告", "请先集成到图谱")
            return
        
        start_id = self.path_start.text().strip()
        end_id = self.path_end.text().strip()
        
        if not start_id or not end_id:
            QMessageBox.warning(self, "警告", "请输入起始节点和目标节点 ID")
            return
        
        try:
            from client.src.business.llm_wiki import LLMWikiKnowledgeGraphIntegratorV3
            
            integrator = LLMWikiKnowledgeGraphIntegratorV3(domain="temp")
            integrator.graph = self._current_graph
            
            path = integrator.find_path(start_id, end_id)
            
            if path:
                path_text = f"找到路径（长度 {len(path)}）:\n"
                for i, node_id in enumerate(path):
                    node = self._current_graph.nodes.get(node_id)
                    title = node.title if node else node_id
                    path_text += f"  {i+1}. {title} ({node_id[:8]}...)\n"
                self.path_result.setText(path_text)
            else:
                self.path_result.setText("未找到路径（节点可能不连通）")
                
        except Exception as e:
            self.path_result.setText(f"路径查找失败: {str(e)}")
    
    def _reason_over_graph(self):
        """图谱推理"""
        if not self._current_graph:
            QMessageBox.warning(self, "警告", "请先集成到图谱")
            return
        
        query = self.reason_query.toPlainText().strip()
        
        if not query:
            QMessageBox.warning(self, "警告", "请输入查询问题")
            return
        
        try:
            from client.src.business.llm_wiki import LLMWikiKnowledgeGraphIntegratorV3
            
            integrator = LLMWikiKnowledgeGraphIntegratorV3(domain="temp")
            integrator.graph = self._current_graph
            
            result = integrator.reason_over_graph(query)
            
            result_text = f"答案: {result.get('answer', '无')}\n"
            result_text += f"置信度: {result.get('confidence', 0):.2f}\n\n"
            
            matched = result.get('matched_concepts', [])
            if matched:
                result_text += f"匹配概念: {', '.join(matched)}\n"
            
            evidence = result.get('evidence', [])
            if evidence:
                result_text += f"\n证据（前 {len(evidence)} 条）:\n"
                for ev in evidence[:3]:
                    result_text += f"  - {ev.get('concept', 'N/A')}: {ev.get('subgraph_nodes', 0)} 个节点\n"
            
            self.reason_result.setText(result_text)
            
        except Exception as e:
            self.reason_result.setText(f"推理失败: {str(e)}")
    
    def _on_file_selected(self, item: QListWidgetItem):
        """文件选中事件"""
        file_path = item.text()
        self._log(f"选中文件: {file_path}")
    
    def _on_chunk_selected(self, item: QListWidgetItem):
        """分块选中事件"""
        index = item.data(Qt.ItemDataRole.UserRole)
        if index is not None and index < len(self._current_chunks):
            chunk = self._current_chunks[index]
            self._log(f"选中分块 #{index}: {chunk.title or '(无标题)'}")
            self._log(f"  类型: {chunk.chunk_type}, 长度: {len(chunk.content)} 字符")
    
    def _log(self, message: str):
        """添加日志"""
        if self.log_output:
            self.log_output.append(message)
            # 滚动到底部
            cursor = self.log_output.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.log_output.setTextCursor(cursor)


# ── 导出 ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # 独立测试
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    panel = LLMWikiPanel()
    panel.setWindowTitle("LLM Wiki 管理面板测试")
    panel.resize(1200, 800)
    panel.show()
    
    sys.exit(app.exec())
