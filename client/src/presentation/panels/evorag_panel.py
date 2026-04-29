"""
EvoRAG 管理面板
==============

提供EvoRAG三大核心特性的UI界面：
1. 反馈驱动反向传播
2. 知识图谱自进化
3. 混合优先级检索

作者: LivingTreeAI Team
日期: 2026-04-29
版本: 1.0.0
"""

import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QSplitter,
    QTextEdit, QTabWidget, QComboBox, QProgressBar,
    QTextBrowser, QFileDialog, QGroupBox, QFormLayout,
    QLineEdit, QSpinBox, QCheckBox, QPlainTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtGui import QFont, QTextCursor

from loguru import logger

# 导入EvoRAG组件
from client.src.business.llm_wiki.feedback_manager import (
    FeedbackManager, FeedbackRecord
)
from client.src.business.llm_wiki.kg_self_evolver import (
    KnowledgeGraphSelfEvolver
)
from client.src.business.llm_wiki.hybrid_retriever import (
    HybridRetriever, RetrievalResult
)
from client.src.business.llm_wiki.knowledge_graph_integrator_v4 import (
    LLMWikiKnowledgeGraphIntegratorV4, EvoRAGConfig
)


# ─── EvoRAG 面板主界面 ─────────────────────────────────────────────
class EvoRAGPanel(QWidget):
    """
    EvoRAG 管理面板

    功能标签页：
    1. 反馈管理
    2. 知识图谱自进化
    3. 混合优先级检索
    4. 统计信息
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # 数据
        self._integrator_v4: Optional[LLMWikiKnowledgeGraphIntegratorV4] = None
        self._current_query: Optional[str] = None
        self._current_paths: Optional[List[List[str]]] = None

        # UI组件
        self.feedback_list: Optional[QListWidget] = None
        self.retrieval_result_table: Optional[QTableWidget] = None
        self.stats_text: Optional[QTextBrowser] = None
        self.log_output: Optional[QTextBrowser] = None

        self._init_ui()
        self._init_connections()

        logger.info("[EvoRAGPanel] 初始化完成")

    # ─── 初始化 ─────────────────────────────────────────────────────

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 标题
        title = QLabel("🚀 EvoRAG 管理器")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        desc = QLabel("反馈驱动 · 知识图谱自进化 · 混合优先级检索")
        desc.setStyleSheet("font-size: 14px; color: #666;")
        layout.addWidget(desc)

        # 主内容区（标签页）
        tabs = QTabWidget()

        # 标签页1: 反馈管理
        feedback_tab = self._create_feedback_tab()
        tabs.addTab(feedback_tab, "📝 反馈管理")

        # 标签页2: KG自进化
        evolution_tab = self._create_evolution_tab()
        tabs.addTab(evolution_tab, "🧬 KG自进化")

        # 标签页3: 混合检索
        retrieval_tab = self._create_retrieval_tab()
        tabs.addTab(retrieval_tab, "🔍 混合检索")

        # 标签页4: 统计信息
        stats_tab = self._create_stats_tab()
        tabs.addTab(stats_tab, "📊 统计信息")

        layout.addWidget(tabs)

        # 日志输出
        log_group = QGroupBox("📋 运行日志")
        log_layout = QVBoxLayout(log_group)
        self.log_output = QTextBrowser()
        self.log_output.setMaximumHeight(150)
        log_layout.addWidget(self.log_output)
        layout.addWidget(log_group)

    def _create_feedback_tab(self) -> QWidget:
        """创建反馈管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 反馈输入区
        input_group = QGroupBox("✍️ 添加反馈")
        input_layout = QFormLayout(input_group)

        self.feedback_query = QLineEdit()
        self.feedback_query.setPlaceholderText("输入用户查询...")
        input_layout.addRow("查询:", self.feedback_query)

        self.feedback_response = QPlainTextEdit()
        self.feedback_response.setPlaceholderText("输入生成的响应...")
        self.feedback_response.setMaximumHeight(100)
        input_layout.addRow("响应:", self.feedback_response)

        self.feedback_score = QSpinBox()
        self.feedback_score.setRange(1, 5)
        self.feedback_score.setValue(4)
        input_layout.addRow("分数(1-5):", self.feedback_score)

        self.feedback_type = QComboBox()
        self.feedback_type.addItems(["human", "llm", "automatic"])
        input_layout.addRow("类型:", self.feedback_type)

        add_btn = QPushButton("➕ 添加反馈")
        add_btn.clicked.connect(self._on_add_feedback)
        input_layout.addRow("", add_btn)

        layout.addWidget(input_group)

        # 反馈列表
        list_group = QGroupBox("📝 反馈记录")
        list_layout = QVBoxLayout(list_group)

        self.feedback_list = QListWidget()
        list_layout.addWidget(self.feedback_list)

        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._on_refresh_feedback)
        list_layout.addWidget(refresh_btn)

        layout.addWidget(list_group)

        return widget

    def _create_evolution_tab(self) -> QWidget:
        """创建KG自进化标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 进化控制区
        control_group = QGroupBox("🧬 进化控制")
        control_layout = QHBoxLayout(control_group)

        evolve_btn = QPushButton("🚀 执行KG进化")
        evolve_btn.clicked.connect(self._on_evolve_kg)
        control_layout.addWidget(evolve_btn)

        refresh_btn = QPushButton("🔄 刷新状态")
        refresh_btn.clicked.connect(self._on_refresh_evolution)
        control_layout.addWidget(refresh_btn)

        layout.addWidget(control_group)

        # 进化结果区
        result_group = QGroupBox("📊 进化结果")
        result_layout = QVBoxLayout(result_group)

        self.evolution_result = QTextBrowser()
        result_layout.addWidget(self.evolution_result)

        layout.addWidget(result_group)

        return widget

    def _create_retrieval_tab(self) -> QWidget:
        """创建混合检索标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 查询输入区
        query_group = QGroupBox("🔍 混合检索")
        query_layout = QFormLayout(query_group)

        self.retrieval_query = QLineEdit()
        self.retrieval_query.setPlaceholderText("输入查询...")
        query_layout.addRow("查询:", self.retrieval_query)

        self.retrieval_top_k = QSpinBox()
        self.retrieval_top_k.setRange(1, 50)
        self.retrieval_top_k.setValue(10)
        query_layout.addRow("Top-K:", self.retrieval_top_k)

        search_btn = QPushButton("🔍 检索")
        search_btn.clicked.connect(self._on_hybrid_retrieval)
        query_layout.addRow("", search_btn)

        layout.addWidget(query_group)

        # 检索结果区
        result_group = QGroupBox("📊 检索结果")
        result_layout = QVBoxLayout(result_group)

        self.retrieval_result_table = QTableWidget()
        self.retrieval_result_table.setColumnCount(6)
        self.retrieval_result_table.setHorizontalHeaderLabels([
            "三元组ID", "头实体", "关系", "尾实体",
            "混合优先级", "贡献分数"
        ])
        self.retrieval_result_table.horizontalHeader().setStretchLastSection(True)
        result_layout.addWidget(self.retrieval_result_table)

        layout.addWidget(result_group)

        return widget

    def _create_stats_tab(self) -> QWidget:
        """创建统计信息标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 统计信息区
        stats_group = QGroupBox("📊 EvoRAG统计")
        stats_layout = QVBoxLayout(stats_group)

        self.stats_text = QTextBrowser()
        stats_layout.addWidget(self.stats_text)

        refresh_btn = QPushButton("🔄 刷新统计")
        refresh_btn.clicked.connect(self._on_refresh_stats)
        stats_layout.addWidget(refresh_btn)

        layout.addWidget(stats_group)

        return widget

    def _init_connections(self):
        """初始化信号连接"""
        pass

    # ─── 槽函数 ─────────────────────────────────────────────────────

    def _on_add_feedback(self):
        """添加反馈"""
        if not self._integrator_v4:
            QMessageBox.warning(self, "警告", "请先加载V4集成器")
            return

        query = self.feedback_query.text().strip()
        response = self.feedback_response.toPlainText().strip()
        score = self.feedback_score.value()
        feedback_type = self.feedback_type.currentText()

        if not query or not response:
            QMessageBox.warning(self, "警告", "请填写查询和响应")
            return

        try:
            # 模拟路径（真实场景应从推理过程提取）
            paths = self._current_paths or [["triplet_1", "triplet_2"]]

            # 添加反馈
            record_id = self._integrator_v4.add_feedback(
                query=query,
                response=response,
                paths=paths,
                feedback_score=float(score),
                feedback_type=feedback_type
            )

            self._log(f"✅ 反馈已添加, 记录ID: {record_id}")
            QMessageBox.information(self, "成功", "反馈添加成功！")

            # 清空输入
            self.feedback_query.clear()
            self.feedback_response.clear()

            # 刷新反馈列表
            self._on_refresh_feedback()

        except Exception as e:
            self._log(f"❌ 添加反馈失败: {e}")
            QMessageBox.critical(self, "错误", f"添加反馈失败: {e}")

    def _on_refresh_feedback(self):
        """刷新反馈列表"""
        if not self._integrator_v4 or not self._integrator_v4.feedback_manager:
            return

        self.feedback_list.clear()

        records = self._integrator_v4.feedback_manager.feedback_records

        for record in records[-50:]:  # 显示最近50条
            item_text = f"[{record.timestamp}] 查询: {record.query[:30]}... | 分数: {record.feedback_score}"
            item = QListWidgetItem(item_text)
            self.feedback_list.addItem(item)

        self._log(f"✅ 刷新反馈列表, 记录数: {len(records)}")

    def _on_evolve_kg(self):
        """执行KG进化"""
        if not self._integrator_v4:
            QMessageBox.warning(self, "警告", "请先加载V4集成器")
            return

        try:
            self._log("🚀 开始KG进化...")

            # 执行进化
            evolved_kg = self._integrator_v4.evolve_knowledge_graph()

            # 显示结果
            result_text = f"""
            <h3>✅ KG进化完成</h3>
            <p><b>进化后KG大小:</b> {len(evolved_kg)} 个三元组</p>
            """

            if self._integrator_v4.kg_evolver:
                stats = self._integrator_v4.kg_evolver.get_statistics()
                result_text += f"""
                <p><b>捷径边数:</b> {stats['shortcut_edges_count']}</p>
                <p><b>抑制三元组数:</b> {stats['suppressed_triplets_count']}</p>
                <p><b>恢复候选数:</b> {stats['recovery_candidates_count']}</p>
                """

            self.evolution_result.setHtml(result_text)

            self._log("✅ KG进化完成")

        except Exception as e:
            self._log(f"❌ KG进化失败: {e}")
            QMessageBox.critical(self, "错误", f"KG进化失败: {e}")

    def _on_refresh_evolution(self):
        """刷新进化状态"""
        if not self._integrator_v4:
            return

        result_text = "<h3>KG进化状态</h3>"

        if self._integrator_v4.kg_evolver:
            stats = self._integrator_v4.kg_evolver.get_statistics()
            result_text += f"""
            <p><b>捷径边数:</b> {stats['shortcut_edges_count']}</p>
            <p><b>抑制三元组数:</b> {stats['suppressed_triplets_count']}</p>
            <p><b>恢复候选数:</b> {stats['recovery_candidates_count']}</p>
            <p><b>最大跳数:</b> {stats['max_hops']}</p>
            """

        self.evolution_result.setHtml(result_text)
        self._log("✅ 刷新进化状态")

    def _on_hybrid_retrieval(self):
        """执行混合检索"""
        if not self._integrator_v4:
            QMessageBox.warning(self, "警告", "请先加载V4集成器")
            return

        query = self.retrieval_query.text().strip()
        top_k = self.retrieval_top_k.value()

        if not query:
            QMessageBox.warning(self, "警告", "请输入查询")
            return

        try:
            self._log(f"🔍 开始混合检索: {query}...")

            # 执行检索
            results = self._integrator_v4.hybrid_retrieve(query, top_k=top_k)

            # 显示结果
            self.retrieval_result_table.setRowCount(len(results))

            for i, result in enumerate(results):
                self.retrieval_result_table.setItem(i, 0, QTableWidgetItem(result.triplet_id))
                self.retrieval_result_table.setItem(i, 1, QTableWidgetItem(result.head))
                self.retrieval_result_table.setItem(i, 2, QTableWidgetItem(result.relation))
                self.retrieval_result_table.setItem(i, 3, QTableWidgetItem(result.tail))
                self.retrieval_result_table.setItem(i, 4, QTableWidgetItem(f"{result.hybrid_priority:.3f}"))
                self.retrieval_result_table.setItem(i, 5, QTableWidgetItem(f"{result.contribution_score:.3f}"))

            # 记录当前查询和路径（用于反馈）
            self._current_query = query
            self._current_paths = [[r.triplet_id for r in results[:2]]]

            self._log(f"✅ 混合检索完成, 结果数: {len(results)}")

        except Exception as e:
            self._log(f"❌ 混合检索失败: {e}")
            QMessageBox.critical(self, "错误", f"混合检索失败: {e}")

    def _on_refresh_stats(self):
        """刷新统计信息"""
        if not self._integrator_v4:
            return

        stats = self._integrator_v4.get_evorag_statistics()

        stats_text = "<h3>📊 EvoRAG统计信息</h3>"

        # 基本统计
        stats_text += f"""
        <h4>基本信息</h4>
        <p><b>反馈次数:</b> {stats.get('feedback_count', 0)}</p>
        <p><b>进化次数:</b> {stats.get('evolution_count', 0)}</p>
        <p><b>检索次数:</b> {stats.get('retrieval_count', 0)}</p>
        """

        # 反馈管理器统计
        if 'feedback_manager' in stats:
            fm_stats = stats['feedback_manager']
            stats_text += f"""
            <h4>反馈管理器</h4>
            <p><b>总反馈数:</b> {fm_stats.get('total_feedback', 0)}</p>
            <p><b>总三元组数:</b> {fm_stats.get('total_triplets', 0)}</p>
            <p><b>α参数:</b> {fm_stats.get('alpha', 0):.3f}</p>
            <p><b>平均贡献分数:</b> {fm_stats.get('avg_contribution_score', 0):.3f}</p>
            """

        # KG自进化器统计
        if 'kg_evolver' in stats:
            evolver_stats = stats['kg_evolver']
            stats_text += f"""
            <h4>KG自进化器</h4>
            <p><b>捷径边数:</b> {evolver_stats.get('shortcut_edges_count', 0)}</p>
            <p><b>抑制三元组数:</b> {evolver_stats.get('suppressed_triplets_count', 0)}</p>
            """

        # 混合检索器统计
        if 'hybrid_retriever' in stats:
            retriever_stats = stats['hybrid_retriever']
            stats_text += f"""
            <h4>混合检索器</h4>
            <p><b>Top-N实体数:</b> {retriever_stats.get('top_n_entities', 0)}</p>
            <p><b>Top-M路径数:</b> {retriever_stats.get('top_m_paths', 0)}</p>
            <p><b>α参数:</b> {retriever_stats.get('alpha', 0):.3f}</p>
            """

        self.stats_text.setHtml(stats_text)
        self._log("✅ 刷新统计信息")

    # ─── 公共方法 ─────────────────────────────────────────────────────

    def set_integrator(self, integrator: LLMWikiKnowledgeGraphIntegratorV4):
        """
        设置V4集成器

        Args:
            integrator: V4集成器实例
        """
        self._integrator_v4 = integrator
        self._log(f"✅ V4集成器已设置")
        self._on_refresh_stats()

    def _log(self, message: str):
        """
        输出日志

        Args:
            message: 日志消息
        """
        if self.log_output:
            self.log_output.append(message)
            # 滚动到底部
            cursor = self.log_output.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.log_output.setTextCursor(cursor)


# ─── 延迟加载函数 ─────────────────────────────────────────────────────
def _create_evorag_panel() -> type:
    """
    创建EvoRAG面板的延迟加载函数

    Returns:
        EvoRAGPanel类
    """
    try:
        return EvoRAGPanel
    except Exception as e:
        logger.error(f"[_create_evorag_panel] 导入失败: {e}")
        return None


if __name__ == "__main__":
    # 测试EvoRAG面板
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    panel = EvoRAGPanel()
    panel.show()

    sys.exit(app.exec())
