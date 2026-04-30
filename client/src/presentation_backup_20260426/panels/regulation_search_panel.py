"""
私有法规库检索面板
Private Regulation Search Panel

提供法规检索的 PyQt6 UI 界面

Author: Hermes Desktop Team
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLineEdit, QPushButton, QLabel, QTextEdit,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QComboBox, QSpinBox, QProgressBar, QTabWidget,
    QGroupBox, QFrame, QScrollArea, QSplitter,
    QApplication, QStyledItemDelegate, QStyleOptionViewItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QPalette, QAction

import os
import json
from typing import List, Optional, Dict, Any
from datetime import datetime


class RegulationSearchWorker(QThread):
    """法规检索工作线程"""

    results_ready = pyqtSignal(list)
    progress_update = pyqtSignal(int, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, db, query: str, top_k: int, filters: Dict):
        super().__init__()
        self.db = db
        self.query = query
        self.top_k = top_k
        self.filters = filters

    def run(self):
        try:
            self.progress_update.emit(10, "正在编码查询...")

            results = self.db.search(
                query=self.query,
                top_k=self.top_k,
                category=self.filters.get("category"),
                department=self.filters.get("department"),
                status=self.filters.get("status", "有效")
            )

            self.progress_update.emit(100, "检索完成")
            self.results_ready.emit(results)

        except Exception as e:
            self.error_occurred.emit(str(e))


class RegulationSearchPanel(QWidget):
    """私有法规库检索面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = None
        self.current_results = []
        self.worker = None

        self.init_ui()
        self.init_database()

    def init_ui(self):
        """初始化 UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # ===== 标题栏 =====
        title_layout = QHBoxLayout()
        title_label = QLabel("📚 私有法规库")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        # 数据库类型标签
        self.db_type_label = QLabel("ChromaDB + all-MiniLM-L6-v2")
        self.db_type_label.setStyleSheet("color: #666; font-size: 11px;")
        title_layout.addWidget(self.db_type_label)

        main_layout.addLayout(title_layout)

        # ===== 搜索区域 =====
        search_group = QGroupBox("🔍 法规检索")
        search_layout = QVBoxLayout()

        # 搜索框布局
        search_input_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入关键词，如：股东权益保护、数据安全、劳动者权益...")
        self.search_input.setMinimumHeight(36)
        self.search_input.returnPressed.connect(self.do_search)
        search_input_layout.addWidget(self.search_input, 1)

        self.search_btn = QPushButton(" 搜索 ")
        self.search_btn.setMinimumHeight(36)
        self.search_btn.setDefault(True)
        self.search_btn.clicked.connect(self.do_search)
        search_input_layout.addWidget(self.search_btn)

        search_layout.addLayout(search_input_layout)

        # 过滤条件
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("类别:"))
        self.category_combo = QComboBox()
        self.category_combo.addItems(["全部", "法律法规", "行政法规", "部门规章", "规范性文件", "司法解释"])
        self.category_combo.setMinimumWidth(120)
        filter_layout.addWidget(self.category_combo)

        filter_layout.addWidget(QLabel("部门:"))
        self.department_combo = QComboBox()
        self.department_combo.addItems(["全部", "全国人民代表大会", "全国人民代表大会常务委员会", "国务院", "最高人民法院"])
        self.department_combo.setMinimumWidth(150)
        filter_layout.addWidget(self.department_combo)

        filter_layout.addWidget(QLabel("状态:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["有效", "全部", "废止", "修改"])
        self.status_combo.setMinimumWidth(80)
        filter_layout.addWidget(self.status_combo)

        filter_layout.addWidget(QLabel("数量:"))
        self.top_k_spin = QSpinBox()
        self.top_k_spin.setMinimum(1)
        self.top_k_spin.setMaximum(50)
        self.top_k_spin.setValue(10)
        self.top_k_spin.setMinimumWidth(60)
        filter_layout.addWidget(self.top_k_spin)

        filter_layout.addStretch()

        search_layout.addLayout(filter_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        search_layout.addWidget(self.progress_bar)

        search_group.setLayout(search_layout)
        main_layout.addWidget(search_group)

        # ===== 主内容区域 =====
        content_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：结果列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        result_label = QLabel("📋 检索结果")
        result_label.setStyleSheet("font-weight: bold; padding: 5px;")
        left_layout.addWidget(result_label)

        self.result_list = QListWidget()
        self.result_list.itemClicked.connect(self.on_result_clicked)
        left_layout.addWidget(self.result_list)

        content_splitter.addWidget(left_widget)
        content_splitter.setSizes([300, 600])

        # 右侧：详情面板
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        detail_label = QLabel("📄 法规详情")
        detail_label.setStyleSheet("font-weight: bold; padding: 5px;")
        right_layout.addWidget(detail_label)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setPlaceholderText("点击左侧结果查看详情...")
        right_layout.addWidget(self.detail_text)

        content_splitter.addWidget(right_widget)

        main_layout.addWidget(content_splitter, 1)

        # ===== 状态栏 =====
        status_layout = QHBoxLayout()

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #666; font-size: 11px;")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.stats_label = QLabel("法规: 0 | 分块: 0 | 检索: 0")
        self.stats_label.setStyleSheet("color: #666; font-size: 11px;")
        status_layout.addWidget(self.stats_label)

        main_layout.addLayout(status_layout)

    def init_database(self):
        """初始化数据库"""
        try:
            from .business.regulation_vector_db import create_regulation_db, RegulationLaw

            # 尝试加载已存在的数据库
            db_path = "./data/regulations"
            if os.path.exists(db_path):
                self.db = create_regulation_db(
                    db_type="chroma",
                    embedding_model="all-MiniLM-L6-v2",
                    persist_directory=db_path
                )
                self.update_statistics()
            else:
                self.db = None

            if self.db:
                self.db_type_label.setText(
                    f"{self.db.db_config.db_type.value.upper()} + {self.db.embedding_model.get_model_name()}"
                )
                self.status_label.setText("数据库已加载")

        except ImportError as e:
            self.status_label.setText(f"缺少依赖: {e}")
        except Exception as e:
            self.status_label.setText(f"数据库加载失败: {e}")

    def update_statistics(self):
        """更新统计信息"""
        if self.db:
            stats = self.db.get_statistics()
            self.stats_label.setText(
                f"法规: {stats['total_laws']} | "
                f"分块: {stats['total_chunks']} | "
                f"检索: {stats['total_searches']}"
            )

    def do_search(self):
        """执行搜索"""
        if self.db is None:
            self.status_label.setText("数据库未初始化")
            return

        query = self.search_input.text().strip()
        if not query:
            self.status_label.setText("请输入搜索关键词")
            return

        if self.worker and self.worker.isRunning():
            self.status_label.setText("检索中，请稍候...")
            return

        # 构建过滤条件
        filters = {}
        if self.category_combo.currentText() != "全部":
            filters["category"] = self.category_combo.currentText()
        if self.department_combo.currentText() != "全部":
            filters["department"] = self.department_combo.currentText()
        if self.status_combo.currentText() != "全部":
            filters["status"] = self.status_combo.currentText()

        # 禁用搜索按钮
        self.search_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("检索中...")

        # 启动工作线程
        self.worker = RegulationSearchWorker(
            self.db, query, self.top_k_spin.value(), filters
        )
        self.worker.results_ready.connect(self.on_search_complete)
        self.worker.progress_update.connect(self.on_progress_update)
        self.worker.error_occurred.connect(self.on_search_error)
        self.worker.start()

    def on_search_complete(self, results: List):
        """搜索完成"""
        self.current_results = results
        self.result_list.clear()

        if not results:
            self.result_list.addItem("未找到相关法规")
            self.status_label.setText("未找到匹配结果")
            return

        for result in results:
            # 创建列表项
            score_color = self.get_score_color(result.score)
            item_text = (
                f"<b>{result.law.title}</b> "
                f"<span style='color: {score_color}'>({result.score:.2f})</span><br/>"
                f"<span style='color: #666; font-size: 11px;'>{result.law.category} | "
                f"{result.law.department}</span>"
            )
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, result)
            self.result_list.addItem(item)

        self.status_label.setText(f"找到 {len(results)} 条相关法规")
        self.update_statistics()

        # 恢复搜索按钮
        self.search_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

    def get_score_color(self, score: float) -> str:
        """根据分数返回颜色"""
        if score >= 0.8:
            return "#e74c3c"  # 红色 - 高度相关
        elif score >= 0.6:
            return "#f39c12"  # 橙色 - 中度相关
        elif score >= 0.4:
            return "#3498db"  # 蓝色 - 一般相关
        else:
            return "#95a5a6"  # 灰色 - 弱相关

    def on_result_clicked(self, item: QListWidgetItem):
        """结果项被点击"""
        result = item.data(Qt.ItemDataRole.UserRole)
        if result is None:
            return

        # 构造详情文本
        detail_html = f"""
        <h2 style='color: #2c3e50; margin-bottom: 10px;'>{result.law.title}</h2>

        <p style='color: #7f8c8d; margin: 5px 0;'>
            <b>法规ID:</b> {result.law.law_id}<br/>
            <b>类别:</b> {result.law.category}<br/>
            <b>发布部门:</b> {result.law.department}<br/>
            <b>发布日期:</b> {result.law.issue_date}<br/>
            <b>生效日期:</b> {result.law.effective_date}<br/>
            <b>状态:</b> <span style='color: #27ae60;'>{result.law.status}</span>
        </p>

        <hr style='border: 1px solid #ecf0f1;'/>

        <p style='color: #2c3e50;'>
            <b>关键词:</b> {', '.join(result.law.keywords) if result.law.keywords else '无'}
        </p>

        <hr style='border: 1px solid #ecf0f1;'/>

        <h3 style='color: #34495e;'>法规内容:</h3>
        <div style='background: #f8f9fa; padding: 15px; border-radius: 5px;'>
            {result.highlight}
        </div>

        <p style='margin-top: 15px; color: #95a5a6; font-size: 11px;'>
            <b>相似度:</b> {result.score:.4f} | <b>排名:</b> #{result.rank}
        </p>
        """

        self.detail_text.setHtml(detail_html)

    def on_progress_update(self, value: int, message: str):
        """进度更新"""
        self.progress_bar.setValue(value)
        self.status_label.setText(message)

    def on_search_error(self, error: str):
        """搜索错误"""
        self.status_label.setText(f"检索失败: {error}")
        self.search_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

    def add_regulation(self, law_data: Dict):
        """添加法规（供外部调用）"""
        if self.db is None:
            self.status_label.setText("数据库未初始化")
            return False

        try:
            from .business.regulation_vector_db import RegulationLaw

            law = RegulationLaw.from_dict(law_data)
            success = self.db.add_law(law)

            if success:
                self.status_label.setText(f"已添加法规: {law.title}")
                self.update_statistics()
            else:
                self.status_label.setText("添加法规失败")

            return success

        except Exception as e:
            self.status_label.setText(f"添加失败: {e}")
            return False

    def export_results(self, filepath: str):
        """导出检索结果"""
        try:
            data = []
            for result in self.current_results:
                data.append({
                    "law": result.law.to_dict(),
                    "score": result.score,
                    "highlight": result.highlight,
                    "rank": result.rank
                })

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.status_label.setText(f"已导出 {len(data)} 条结果")
            return True

        except Exception as e:
            self.status_label.setText(f"导出失败: {e}")
            return False

    def get_widget(self) -> QWidget:
        """获取面板组件"""
        return self