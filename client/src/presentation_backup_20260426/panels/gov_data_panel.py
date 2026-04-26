"""
政府开放资料查询面板 - GovDataPanel

提供自然语言界面查询政府各部会开放资料：
- 环保署空气品质、水质、废弃物等
- 交通部公车、高铁、台铁等
- 经济部水利署水库、河川等
- 气象局天气预报、地震等

参考 gov_openapi_agent 设计，通过 OpenAPI 规范动态加载
"""

from typing import Optional, List, Dict
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QLineEdit, QListWidget,
    QListWidgetItem, QFrame, QScrollArea, QTabWidget,
    QGroupBox, QComboBox, QSpinBox, QCheckBox,
    QProgressBar, QTextBrowser, QCompleter,
    QSplitter, QFormLayout, QDialog, QDialogButtonBox,
    QMessageBox
)
from PyQt6.QtGui import QFont, QPalette, QColor


class QueryWorker(QThread):
    """查询工作线程"""
    finished = pyqtSignal(list)  # 查询结果列表
    error = pyqtSignal(str)      # 错误信息
    progress = pyqtSignal(str)   # 进度信息

    def __init__(self, gov_query, query_text: str):
        super().__init__()
        self.gov_query = gov_query
        self.query_text = query_text

    def run(self):
        try:
            self.progress.emit("正在分析查询意图...")
            results = self.gov_query.query_by_natural_language(self.query_text)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class PlatformCard(QFrame):
    """平台信息卡片"""

    def __init__(self, platform_info: Dict, parent=None):
        super().__init__(parent)
        self.platform_info = platform_info
        self._build_ui()

    def _build_ui(self):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background: #2a2a3e;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                padding: 12px;
                margin: 4px;
            }
            QFrame:hover {
                border: 1px solid #5a5a8e;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # 平台名称
        name = QLabel(f"🏛️ {self.platform_info.get('name', '')}")
        name.setStyleSheet("color: #a0a0ff; font-size: 14px; font-weight: bold;")
        layout.addWidget(name)

        # 英文名
        name_en = QLabel(self.platform_info.get('name_en', ''))
        name_en.setStyleSheet("color: #707090; font-size: 11px;")
        layout.addWidget(name_en)

        # 端点数量
        count = self.platform_info.get('endpoint_count', 0)
        count_lbl = QLabel(f"📊 {count} 个资料集")
        count_lbl.setStyleSheet("color: #9090b0; font-size: 12px;")
        layout.addWidget(count_lbl)

        # 启用状态
        if self.platform_info.get('enabled'):
            status = QLabel("🟢 已启用")
            status.setStyleSheet("color: #4ade80; font-size: 11px;")
        else:
            status = QLabel("⚪ 已停用")
            status.setStyleSheet("color: #6b7280; font-size: 11px;")
        layout.addWidget(status)


class EndpointItem(QFrame):
    """端点列表项"""

    def __init__(self, endpoint_info: Dict, parent=None):
        super().__init__(parent)
        self.endpoint_info = endpoint_info
        self._build_ui()

    def _build_ui(self):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background: #252538;
                border-radius: 6px;
                padding: 8px;
                margin: 2px;
            }
            QFrame:hover {
                background: #2a2a45;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)

        # 端点名称
        name = QLabel(f"📡 {self.endpoint_info.get('name', '')}")
        name.setStyleSheet("color: #e0e0ff; font-size: 13px;")
        layout.addWidget(name)

        # 平台来源
        platform = QLabel(f"   来源: {self.endpoint_info.get('platform', '')}")
        platform.setStyleSheet("color: #8080a0; font-size: 11px;")
        layout.addWidget(platform)

        # 描述
        desc = self.endpoint_info.get('description', '')
        if desc:
            desc_lbl = QLabel(f"   {desc}")
            desc_lbl.setStyleSheet("color: #606080; font-size: 11px;")
            desc_lbl.setWordWrap(True)
            layout.addWidget(desc_lbl)


class GovDataPanel(QWidget):
    """
    政府开放资料查询面板

    功能：
    1. 自然语言查询输入
    2. 快速查询按钮
    3. 平台浏览
    4. 端点浏览
    5. 查询历史
    6. 结果展示
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._gov_query = None
        self._query_worker: Optional[QueryWorker] = None
        self._query_history: List[str] = []
        self.quick_buttons: List[QPushButton] = []  # 快速查询按钮列表

        # 快速查询配置
        self.cn_queries = [
            ("📊 GDP数据", "中国GDP"),
            ("📈 CPI指数", "中国CPI"),
            ("👥 人口数据", "中国人口"),
            ("💰 贸易数据", "中国贸易顺差"),
            ("🏭 工业产值", "中国工业增加值"),
        ]
        self.tw_queries = [
            ("🌬️ 空气品质", "空气品质"),
            ("💧 水库蓄水", "水库蓄水率"),
            ("🚌 公车动态", "公车动态"),
            ("🌤️ 天气预报", "天气预报"),
            ("🌧️ 雨量资料", "雨量观测"),
        ]
        self.global_queries = [
            ("📊 世界GDP", "世界GDP"),
            ("👥 世界人口", "世界人口"),
            ("🇺🇸 美国数据", "美国数据"),
        ]

        self._build_ui()
        self._load_platforms()

    def _build_ui(self):
        """构建UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === 标题栏 ===
        header = QWidget()
        header.setStyleSheet("background: #1a1a2e; border-bottom: 1px solid #2a2a4e;")
        header.setFixedHeight(56)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 0, 16, 0)

        title = QLabel("🏛️ 政府开放资料查询")
        title.setStyleSheet("color: #a0a0ff; font-size: 16px; font-weight: bold;")
        h_layout.addWidget(title)

        h_layout.addStretch()

        # API Key 设置按钮
        self.config_btn = QPushButton("⚙️")
        self.config_btn.setFixedSize(36, 36)
        self.config_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #4a4a6e;
                border-radius: 6px;
                color: #8080a0;
            }
            QPushButton:hover {
                background: #2a2a4e;
            }
        """)
        self.config_btn.clicked.connect(self._show_config_dialog)
        h_layout.addWidget(self.config_btn)

        main_layout.addWidget(header)

        # === 主内容区 ===
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(16)

        # 左侧：查询区
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(12)

        # 查询输入框
        query_group = QGroupBox("🔍 自然语言查询")
        query_group.setStyleSheet("""
            QGroupBox {
                color: #a0a0ff;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                font-size: 13px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        query_layout = QVBoxLayout(query_group)

        # 地区选择 + 输入框 同一行
        search_row = QHBoxLayout()
        search_row.setSpacing(10)

        # 地区选择下拉框
        self.region_combo = QComboBox()
        self.region_combo.setStyleSheet("""
            QComboBox {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 6px;
                padding: 8px 12px;
                color: #e0e0ff;
                font-size: 13px;
                min-width: 120px;
            }
            QComboBox:hover {
                border: 1px solid #5a5a9e;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #8080a0;
            }
        """)
        self.region_combo.addItem("🌍 全球", "global")
        self.region_combo.addItem("🇨🇳 中国大陆", "cn")
        self.region_combo.addItem("🇹🇼 台湾", "tw")
        self.region_combo.addItem("🇭🇰 香港", "hk")
        self.region_combo.addItem("🇲🇴 澳门", "mo")
        self.region_combo.addItem("🇺🇸 美国", "us")
        self.region_combo.addItem("🇪🇺 欧盟", "eu")
        self.region_combo.currentIndexChanged.connect(self._on_region_changed)
        search_row.addWidget(self.region_combo)

        # 输入框
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("例如：中国GDP、台北空气品质、香港天气...")
        self.query_input.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 6px;
                padding: 10px 14px;
                color: #e0e0ff;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #5a5a9e;
            }
            QLineEdit::placeholder {
                color: #606080;
            }
        """)
        self.query_input.returnPressed.connect(self._do_query)
        search_row.addWidget(self.query_input, 1)

        query_layout.addLayout(search_row)

        # 快速查询按钮 - 根据地区动态显示
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(8)

        # 大陆快速查询
        self.cn_queries = [
            ("📊 GDP数据", "中国GDP"),
            ("📈 CPI指数", "中国CPI"),
            ("👥 人口数据", "中国人口"),
            ("💰 贸易数据", "中国贸易顺差"),
            ("🏭 工业产值", "中国工业增加值"),
        ]

        # 台湾快速查询
        self.tw_queries = [
            ("🌬️ 空气品质", "空气品质"),
            ("💧 水库蓄水", "水库蓄水率"),
            ("🚌 公车动态", "公车动态"),
            ("🌤️ 天气预报", "天气预报"),
            ("🌧️ 雨量资料", "雨量观测"),
        ]

        # 全球快速查询
        self.global_queries = [
            ("📊 世界GDP", "世界GDP"),
            ("👥 世界人口", "世界人口"),
            ("🇺🇸 美国数据", "美国数据"),
        ]

        self.quick_buttons = []
        self._update_quick_buttons("global")

        quick_layout.addStretch()
        query_layout.addLayout(quick_layout)
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(8)

        quick_queries = [
            ("🌬️ 空气品质", "空气品质"),
            ("💧 水库蓄水", "水库蓄水率"),
            ("🚌 公车动态", "公车动态"),
            ("🌤️ 天气预报", "天气预报"),
            ("🌧️ 雨量资料", "雨量观测"),
        ]

        for label, query in quick_queries:
            btn = QPushButton(label)
            btn.setStyleSheet("""
                QPushButton {
                    background: #2a2a4e;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 10px;
                    color: #9090c0;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background: #3a3a6e;
                    color: #b0b0e0;
                }
            """)
            btn.clicked.connect(lambda checked, q=query: self.query_input.setText(q))
            quick_layout.addWidget(btn)

        quick_layout.addStretch()
        query_layout.addLayout(quick_layout)

        # 查询按钮
        btn_layout = QHBoxLayout()
        self.query_btn = QPushButton("🔍 查询")
        self.query_btn.setStyleSheet("""
            QPushButton {
                background: #4a4aff;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                color: white;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #5a5aff;
            }
            QPushButton:disabled {
                background: #3a3a6e;
                color: #606080;
            }
        """)
        self.query_btn.clicked.connect(self._do_query)
        btn_layout.addWidget(self.query_btn)

        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setVisible(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: #ff4a4a;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                color: white;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #ff5a5a;
            }
        """)
        self.stop_btn.clicked.connect(self._stop_query)
        btn_layout.addWidget(self.stop_btn)

        btn_layout.addStretch()
        query_layout.addLayout(btn_layout)

        left_layout.addWidget(query_group)

        # 结果区域
        result_group = QGroupBox("📋 查询结果")
        result_group.setStyleSheet("""
            QGroupBox {
                color: #a0a0ff;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                font-size: 13px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        result_layout = QVBoxLayout(result_group)

        self.result_area = QTextBrowser()
        self.result_area.setPlaceholderText("查询结果将显示在这里...\n\n支持查询示例：\n• 台中今天的空气品质\n• 台北公车动态\n• 全台水库蓄水率\n• 明天天气预报\n• 最近地震资讯")
        self.result_area.setStyleSheet("""
            QTextBrowser {
                background: #1e1e32;
                border: 1px solid #2a2a4e;
                border-radius: 6px;
                padding: 12px;
                color: #d0d0f0;
                font-size: 13px;
            }
        """)
        result_layout.addWidget(self.result_area, 1)

        left_layout.addWidget(result_group, 1)

        content_layout.addWidget(left_panel, 1)

        # 右侧：平台和端点浏览
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(12)

        # 平台列表
        platform_group = QGroupBox("🏛️ 可用平台")
        platform_group.setStyleSheet("""
            QGroupBox {
                color: #a0a0ff;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                font-size: 13px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        platform_layout = QVBoxLayout(platform_group)
        self.platform_list = QListWidget()
        self.platform_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
            }
            QListWidget::item {
                padding: 4px;
            }
        """)
        self.platform_list.itemClicked.connect(self._on_platform_selected)
        platform_layout.addWidget(self.platform_list)

        right_layout.addWidget(platform_group, 1)

        # 端点列表
        endpoint_group = QGroupBox("📡 资料集")
        endpoint_group.setStyleSheet("""
            QGroupBox {
                color: #a0a0ff;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                font-size: 13px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        endpoint_layout = QVBoxLayout(endpoint_group)
        self.endpoint_list = QListWidget()
        self.endpoint_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
            }
            QListWidget::item {
                padding: 4px;
            }
        """)
        self.endpoint_list.itemDoubleClicked.connect(self._on_endpoint_double_clicked)
        endpoint_layout.addWidget(self.endpoint_list)

        right_layout.addWidget(endpoint_group, 1)

        content_layout.addWidget(right_panel, 0)

        main_layout.addWidget(content, 1)

        # === 状态栏 ===
        self.status_bar = QLabel("就绪")
        self.status_bar.setStyleSheet("""
            QLabel {
                background: #1a1a2e;
                color: #707090;
                padding: 6px 16px;
                font-size: 11px;
            }
        """)
        main_layout.addWidget(self.status_bar)

    def _init_gov_query(self):
        """延迟初始化GovDataQuery"""
        if self._gov_query is None:
            try:
                from client.src.business.gov_data_query import get_gov_data_query
                self._gov_query = get_gov_data_query()
            except ImportError:
                self._gov_query = None

    def _on_region_changed(self, index: int):
        """地区选择改变"""
        region = self.region_combo.currentData()
        self._update_quick_buttons(region)
        self._load_platforms(region)
        self._update_status_by_region(region)

    def _update_quick_buttons(self, region: str):
        """更新快速查询按钮"""
        # 清除现有按钮
        for btn in self.quick_buttons:
            btn.deleteLater()
        self.quick_buttons.clear()

        # 找到 quick_layout
        query_group = self.query_input.parentWidget().parentWidget()
        layout = query_group.layout()

        # 查找 quick_layout
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item.layout() and item.layout() != self.query_input.parentWidget().layout():
                quick_layout = item.layout()
                while quick_layout.count():
                    child = quick_layout.takeAt(0)
                    if child.widget() and child.widget() not in self.quick_buttons:
                        child.widget().deleteLater()

                # 添加新按钮
                if region == "cn":
                    queries = self.cn_queries
                elif region == "tw":
                    queries = self.tw_queries
                else:
                    queries = self.global_queries

                for label, query_text in queries:
                    btn = QPushButton(label)
                    btn.setStyleSheet("""
                        QPushButton {
                            background: #2a2a4e;
                            border: none;
                            border-radius: 4px;
                            padding: 6px 10px;
                            color: #9090c0;
                            font-size: 11px;
                        }
                        QPushButton:hover {
                            background: #3a3a6e;
                            color: #b0b0e0;
                        }
                    """)
                    btn.clicked.connect(lambda checked, q=query_text: self.query_input.setText(q))
                    quick_layout.insertWidget(quick_layout.count() - 1, btn)
                    self.quick_buttons.append(btn)
                break

    def _update_status_by_region(self, region: str):
        """根据地区更新状态栏"""
        region_names = {
            "cn": "🇨🇳 中国大陆 - 国家统计局/各省市政府数据平台",
            "tw": "🇹🇼 台湾 - 环保署/交通部/水利署/气象局",
            "hk": "🇭🇰 香港 - 政府资料一线通",
            "mo": "🇲🇴 澳门 - 统计暨普查局",
            "us": "🇺🇸 美国 - data.gov",
            "eu": "🇪🇺 欧盟 - open data",
            "global": "🌍 全球 - 世界银行/联合国数据"
        }
        self.status_bar.setText(region_names.get(region, "就绪"))

    def _load_platforms(self, region: str = None):
        """加载平台列表"""
        self._init_gov_query()
        self.platform_list.clear()

        if not self._gov_query:
            # 显示演示数据
            demo_platforms = [
                {"id": "moenv", "name": "环保署环境资料开放平台", "name_en": "MOENV Open Data", "enabled": True, "endpoint_count": 4},
                {"id": "tdx", "name": "交通部运输资料流通服务平台", "name_en": "TDX Transport Data", "enabled": False, "endpoint_count": 4},
                {"id": "wra", "name": "经济部水利署水利资料开放平台", "name_en": "WRA Water Resources", "enabled": True, "endpoint_count": 3},
                {"id": "cwa", "name": "气象局资料开放平台", "name_en": "CWA Weather", "enabled": False, "endpoint_count": 3},
            ]
            platforms = demo_platforms
        else:
            platforms = self._gov_query.list_platforms(region=region)

        for p in platforms:
            item = QListWidgetItem()
            card = PlatformCard(p)
            card.setFixedWidth(200)
            item.setSizeHint(card.sizeHint())
            self.platform_list.addItem(item)
            self.platform_list.setItemWidget(item, card)

    def _on_platform_selected(self, item):
        """平台选择"""
        index = self.platform_list.row(item)
        platforms = self._gov_query.list_platforms() if self._gov_query else []

        if index < len(platforms):
            platform_id = platforms[index]["id"]
            self._load_endpoints(platform_id)

    def _load_endpoints(self, platform_id: str = None):
        """加载端点列表"""
        self._init_gov_query()
        self.endpoint_list.clear()

        if not self._gov_query:
            return

        endpoints = self._gov_query.list_endpoints(platform_id)

        for ep in endpoints:
            item = QListWidgetItem()
            card = EndpointItem(ep)
            card.setFixedWidth(280)
            item.setSizeHint(card.sizeHint())
            self.endpoint_list.addItem(item)
            self.endpoint_list.setItemWidget(item, card)

    def _on_endpoint_double_clicked(self, item):
        """端点双击查询"""
        index = self.endpoint_list.row(item)
        endpoints = self._gov_query.list_endpoints() if self._gov_query else []

        if index < len(endpoints):
            ep = endpoints[index]
            # 直接查询
            self.query_input.setText(ep["name"])
            self._do_query()

    def _do_query(self):
        """执行查询"""
        query_text = self.query_input.text().strip()
        if not query_text:
            return

        self._init_gov_query()

        # 添加到历史
        if query_text not in self._query_history:
            self._query_history.append(query_text)
            if len(self._query_history) > 20:
                self._query_history.pop(0)

        # 更新UI状态
        self.query_btn.setVisible(False)
        self.stop_btn.setVisible(True)
        self.result_area.clear()
        self.result_area.append(f"🔄 正在查询：「{query_text}」\n")

        # 启动查询线程
        if self._gov_query:
            self._query_worker = QueryWorker(self._gov_query, query_text)
            self._query_worker.progress.connect(self._on_query_progress)
            self._query_worker.finished.connect(self._on_query_finished)
            self._query_worker.error.connect(self._on_query_error)
            self._query_worker.start()
        else:
            self._show_demo_result(query_text)

    def _stop_query(self):
        """停止查询"""
        if self._query_worker and self._query_worker.isRunning():
            self._query_worker.terminate()
            self._query_worker.wait()

        self.query_btn.setVisible(True)
        self.stop_btn.setVisible(False)
        self.status_bar.setText("查询已停止")

    def _on_query_progress(self, msg: str):
        """查询进度更新"""
        self.result_area.append(msg)
        self.status_bar.setText(msg)

    def _on_query_finished(self, results: List):
        """查询完成"""
        self.query_btn.setVisible(True)
        self.stop_btn.setVisible(False)

        if not results:
            self.result_area.append("\n⚠️ 未找到相关资料，请尝试其他关键词。")
            self.status_bar.setText("未找到资料")
            return

        # 格式化结果
        output = []
        for result in results:
            formatted = self._gov_query.format_result_natural(result)
            output.append(formatted)
            output.append("\n" + "=" * 50 + "\n")

        self.result_area.append("\n".join(output))
        self.status_bar.setText(f"查询完成，找到 {len(results)} 个结果")

    def _on_query_error(self, error: str):
        """查询错误"""
        self.query_btn.setVisible(True)
        self.stop_btn.setVisible(False)
        self.result_area.append(f"\n❌ 查询失败：{error}")
        self.status_bar.setText(f"错误: {error}")

    def _show_demo_result(self, query: str):
        """显示演示结果"""
        self.query_btn.setVisible(True)
        self.stop_btn.setVisible(False)

        query_lower = query.lower()

        if "空气" in query or "空品" in query or "pm2" in query_lower:
            result = """🌬️ **空气品质资讯**

📍 台中市
   AQI: 72 (普通 🟡)
   PM2.5: 28 μg/m³

📍 台北市
   AQI: 58 (普通 🟡)
   PM2.5: 18 μg/m³

📍 高雄市
   AQI: 85 (对敏感族群不健康 🟠)
   PM2.5: 42 μg/m³

---
💡 这是演示资料。如需实时资料，请在设置中配置环保署 API Key。"""
        elif "水库" in query or "蓄水" in query:
            result = """💧 **全台水库蓄水状况**

📍 曾文水库
   蓄水率: 78.5%
   有效容量: 45,000 立方公尺

📍 石门水库
   蓄水率: 62.3%
   有效容量: 18,500 立方公尺

📍 翡翠水库
   蓄水率: 91.2%
   有效容量: 28,000 立方公尺

---
💡 这是演示资料。如需实时资料，请配置水利署资料介接。"""
        elif "公车" in query or "公交" in query:
            result = """🚌 **公车动态资讯**

🚌 路线: 300路区间车
   站牌: 台北车站
   预计到站: 5 分钟

🚌 路线: 5路
   站牌: 台北车站
   预计到站: 12 分钟

---
💡 这是演示资料。如需实时资料，请配置交通部 TDX API。"""
        elif "天气" in query:
            result = """🌤️ **天气预报**

📍 台北市
   温度: 24~30°C
   降雨机率: 30%
   天气: 多云午后雷阵雨

📍 台中市
   温度: 26~34°C
   降雨机率: 20%
   天气: 晴朗

---
💡 这是演示资料。如需实时资料，请配置气象局 API。"""
        else:
            result = f"""📊 **查询结果**

您查询的「{query}」找到以下资料：

• 环保署环境资料
• 交通部运输资料
• 水利署水文资料
• 气象局气象资料

---
💡 这是演示资料。请在设置中配置相应的 API Key 以获取实时资料。"""

        self.result_area.append(result)
        self.status_bar.setText("演示模式 - 请配置 API Key 获取真实资料")

    def _show_config_dialog(self):
        """显示配置对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("⚙️ API 配置")
        dialog.setFixedSize(500, 400)
        dialog.setStyleSheet("""
            QDialog {
                background: #1a1a2e;
            }
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 标题
        title = QLabel("政府开放资料 API 配置")
        title.setStyleSheet("color: #a0a0ff; font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # 说明
        desc = QLabel(
            "请设置各部会开放资料的 API 凭证。\n"
            "API Key 将保存在环境变量中，不会外泄。"
        )
        desc.setStyleSheet("color: #808090; font-size: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # 表单
        form = QFormLayout()
        form.setSpacing(12)

        self.api_keys = {}

        platforms = [
            ("环保署 (MOENV)", "MOENV_API_KEY", "从 https://data.moenv.gov.tw.tw/api-term 获取"),
            ("气象局 (CWA)", "CWA_API_KEY", "从 https://opendata.cwa.gov.tw/api-key 获取"),
            ("交通部 TDX", "TDX_CLIENT_ID", "从 https://tdx.transportdata.tw/register 获取"),
        ]

        for name, env_var, hint in platforms:
            group = QVBoxLayout()

            key_input = QLineEdit()
            key_input.setPlaceholderText(f"输入 {env_var}")
            key_input.setEchoMode(QLineEdit.EchoMode.Password)
            key_input.setStyleSheet("""
                QLineEdit {
                    background: #252538;
                    border: 1px solid #3a3a5e;
                    border-radius: 4px;
                    padding: 8px 12px;
                    color: #e0e0ff;
                }
            """)
            self.api_keys[env_var] = key_input

            hint_lbl = QLabel(hint)
            hint_lbl.setStyleSheet("color: #606080; font-size: 10px;")

            group.addWidget(key_input)
            group.addWidget(hint_lbl)

            group_widget = QWidget()
            group_widget.setLayout(group)
            form.addRow(name, group_widget)

        layout.addLayout(form)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_btn = QPushButton("💾 保存")
        save_btn.setStyleSheet("""
            QPushButton {
                background: #4a4aff;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                color: white;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #5a5aff;
            }
        """)
        save_btn.clicked.connect(lambda: self._save_config(dialog))
        btn_layout.addWidget(save_btn)

        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet("""
            QPushButton {
                background: #3a3a5e;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                color: #a0a0c0;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #4a4a7e;
            }
        """)
        close_btn.clicked.connect(dialog.close)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        dialog.exec()

    def _save_config(self, dialog: QDialog):
        """保存配置"""
        import os

        for env_var, input_widget in self.api_keys.items():
            value = input_widget.text().strip()
            if value:
                os.environ[env_var] = value

        QMessageBox.information(
            self,
            "配置已保存",
            "API Key 已保存到环境变量。\n请重启应用以使配置生效。",
            QMessageBox.StandardButton.Ok
        )
        dialog.close()