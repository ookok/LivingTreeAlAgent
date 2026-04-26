# -*- coding: utf-8 -*-
"""
LocalMarket 主面板
=================

去中心化本地商品交易市场的PyQt6界面

功能：
- 商品浏览与搜索
- 我的商品管理
- 交易管理
- 信誉查看
- 交付跟踪
- 争议处理
"""

import uuid
import time
from typing import List, Dict, Optional, Any
from collections import defaultdict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QLabel, QPushButton, QLineEdit, QTextEdit,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
    QTableWidget, QTableWidgetItem, QTabWidget,
    QDialog, QMessageBox, QComboBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QRadioButton, QButtonGroup, QProgressBar,
    QGroupBox, QFrame, QScrollArea, QStatusBar,
    QToolBar, QMenuBar, QMenu,
)
from PyQt6.QtCore import (
    Qt, QThread, QTimer, pyqtSignal, QDateTime,
    QSize, QRect, QPoint,
)
from PyQt6.QtGui import (
    QAction, QIcon, QFont, QPalette, QColor,
    QBrush, QPainter, QPixmap, QCursor,
)

# 导入核心模块
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'core'))

try:
    from local_market import (
        Product, ProductManager, ProductCategory, Location,
        Transaction, TransactionManager, TransactionStatus, PaymentType,
        SellerReputation, ReputationManager, ReputationLevel,
        DeliveryTask, DeliveryManager, DeliveryType, DeliveryStatus,
        Dispute, DisputeManager, DisputeStatus,
        CommissionRecord, CommissionCalculator, CommissionType,
    )
except ImportError:
    # 简化导入用于UI设计预览
    Product = ProductManager = ProductCategory = Location = None
    Transaction = TransactionManager = TransactionStatus = PaymentType = None
    SellerReputation = ReputationManager = ReputationLevel = None
    DeliveryTask = DeliveryManager = DeliveryType = DeliveryStatus = None
    Dispute = DisputeManager = DisputeStatus = None
    CommissionRecord = CommissionCalculator = CommissionType = None


# ============================================================
# 样式定义
# ============================================================

STYLESHEET = """
/* 全局样式 */
QWidget {
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
}

/* 按钮样式 */
QPushButton {
    background-color: #4CAF50;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    min-width: 80px;
}
QPushButton:hover {
    background-color: #45a049;
}
QPushButton:pressed {
    background-color: #3d8b40;
}
QPushButton:disabled {
    background-color: #cccccc;
    color: #666666;
}

/* 次要按钮 */
QPushButton.secondary {
    background-color: #2196F3;
}
QPushButton.secondary:hover {
    background-color: #1976D2;
}

/* 危险按钮 */
QPushButton.danger {
    background-color: #f44336;
}
QPushButton.danger:hover {
    background-color: #da190b;
}

/* 输入框 */
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 6px;
    background-color: white;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #4CAF50;
}

/* 列表 */
QListWidget {
    border: 1px solid #ddd;
    border-radius: 4px;
    background-color: white;
}
QListWidget::item {
    padding: 8px;
    border-bottom: 1px solid #f0f0f0;
}
QListWidget::item:selected {
    background-color: #e8f5e9;
}

/* 标签页 */
QTabWidget::pane {
    border: 1px solid #ddd;
    border-radius: 4px;
    background-color: white;
}
QTabBar::tab {
    padding: 8px 16px;
    background-color: #f5f5f5;
    border: 1px solid #ddd;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background-color: white;
    border-bottom: 2px solid #4CAF50;
}
QTabBar::tab:hover {
    background-color: #e8f5e9;
}

/* 卡片样式 */
.card {
    background-color: white;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 16px;
    margin: 8px;
}

/* 状态标签 */
.status-badge {
    padding: 4px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: bold;
}
.status-active { background-color: #4CAF50; color: white; }
.status-pending { background-color: #FFC107; color: #333; }
.status-completed { background-color: #2196F3; color: white; }
.status-disputed { background-color: #f44336; color: white; }
.status-cancelled { background-color: #9e9e9e; color: white; }

/* 价格显示 */
.price-label {
    font-size: 18px;
    font-weight: bold;
    color: #f44336;
}
"""


# ============================================================
# 商品卡片组件
# ============================================================

class ProductCard(QWidget):
    """商品卡片组件"""

    clicked = pyqtSignal(str)  # product_id

    def __init__(self, product: Product, reputation_manager=None):
        super().__init__()
        self.product = product
        self.reputation_manager = reputation_manager
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # 标题
        title_label = QLabel(self.product.title)
        title_label.setStyleSheet("font-size: 15px; font-weight: bold;")
        title_label.setWordWrap(True)

        # 分类和状态
        category_layout = QHBoxLayout()
        category_label = QLabel(f"{self.product.category.icon} {self.product.category.value}")
        category_label.setStyleSheet("color: #666; font-size: 12px;")

        status_label = QLabel(self.product.status.upper())
        status_style = {
            "active": "status-active",
            "offline": "status-cancelled",
            "sold": "status-completed",
        }.get(self.product.status, "")
        status_label.setObjectName(status_style)
        status_label.setStyleSheet("padding: 2px 6px; border-radius: 8px; font-size: 10px;")

        category_layout.addWidget(category_label)
        category_layout.addStretch()
        category_layout.addWidget(status_label)

        # 价格
        price_label = QLabel(f"¥{self.product.price:,.2f}")
        price_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #f44336;")

        if self.product.negotiable:
            negotiable_label = QLabel("可议价")
            negotiable_label.setStyleSheet("color: #FF9800; font-size: 11px;")
            price_layout = QHBoxLayout()
            price_layout.addWidget(price_label)
            price_layout.addWidget(negotiable_label)
        else:
            price_layout = QHBoxLayout()
            price_layout.addWidget(price_label)

        # 位置
        location_text = ""
        if self.product.location:
            location_text = f"📍 {self.product.location.city} {self.product.location.district}"
        location_label = QLabel(location_text)
        location_label.setStyleSheet("color: #888; font-size: 12px;")

        # 信誉
        rep_text = ""
        if self.reputation_manager:
            rep = self.reputation_manager.get_reputation(self.product.seller_id)
            rep_text = f"{rep.level.icon} {rep.level.name_cn} ({rep.score:.0f})"
        rep_label = QLabel(rep_text)
        rep_label.setStyleSheet("color: #2196F3; font-size: 12px;")

        # 浏览和收藏
        stats_layout = QHBoxLayout()
        views_label = QLabel(f"👁 {self.product.views}")
        favs_label = QLabel(f"❤️ {self.product.favorites}")
        stats_layout.addWidget(views_label)
        stats_layout.addStretch()
        stats_layout.addWidget(favs_label)

        # 添加到布局
        layout.addWidget(title_label)
        layout.addLayout(category_layout)
        layout.addLayout(price_layout)
        layout.addWidget(location_label)
        layout.addWidget(rep_label)
        layout.addLayout(stats_layout)

        # 点击事件
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.product.product_id)
        super().mousePressEvent(event)

    def get_widget(self) -> QFrame:
        """获取卡片frame"""
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            QFrame:hover {
                border: 1px solid #4CAF50;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)

        # 复制内容到卡片
        title_label = QLabel(self.product.title)
        title_label.setStyleSheet("font-size: 15px; font-weight: bold;")
        title_label.setWordWrap(True)

        price_label = QLabel(f"¥{self.product.price:,.2f}")
        price_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #f44336;")

        location_text = ""
        if self.product.location:
            location_text = f"📍 {self.product.location.city}"

        location_label = QLabel(location_text)
        location_label.setStyleSheet("color: #888; font-size: 12px;")

        layout.addWidget(title_label)
        layout.addWidget(price_label)
        layout.addWidget(location_label)

        return card


# ============================================================
# 主面板
# ============================================================

class LocalMarketPanel(QWidget):
    """本地市场主面板"""

    def __init__(self, node_id: str = None):
        super().__init__()
        self.node_id = node_id or str(uuid.uuid4())[:8]

        # 初始化管理器
        self.init_managers()

        # 初始化UI
        self.setup_ui()

        # 模拟数据
        self.load_demo_data()

    def init_managers(self):
        """初始化管理器"""
        self.product_manager = ProductManager(self.node_id)
        self.transaction_manager = TransactionManager(self.node_id)
        self.reputation_manager = ReputationManager(self.node_id)
        self.delivery_manager = DeliveryManager(self.node_id)
        self.dispute_manager = DisputeManager(self.node_id, self.reputation_manager)
        self.commission_calculator = CommissionCalculator(self.node_id)

    def setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)

        # 顶部栏
        header = self.create_header()
        main_layout.addWidget(header)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_discover_tab(), "🔍 发现")
        self.tabs.addTab(self.create_my_products_tab(), "📦 我的商品")
        self.tabs.addTab(self.create_transactions_tab(), "💰 交易")
        self.tabs.addTab(self.create_delivery_tab(), "📬 交付")
        self.tabs.addTab(self.create_reputation_tab(), "⭐ 信誉")
        self.tabs.addTab(self.create_disputes_tab(), "⚖️ 争议")
        self.tabs.addTab(self.create_settings_tab(), "⚙️ 设置")

        main_layout.addWidget(self.tabs)

    def create_header(self) -> QWidget:
        """创建顶部栏"""
        header = QFrame()
        header.setStyleSheet("background-color: #4CAF50; color: white;")
        layout = QHBoxLayout(header)

        # Logo
        logo = QLabel("🌳 本地市场")
        logo.setStyleSheet("font-size: 20px; font-weight: bold;")

        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索商品...")
        self.search_input.setStyleSheet("padding: 8px; border-radius: 4px;")

        # 搜索按钮
        search_btn = QPushButton("搜索")
        search_btn.clicked.connect(self.on_search)

        layout.addWidget(logo)
        layout.addStretch()
        layout.addWidget(self.search_input)
        layout.addWidget(search_btn)

        return header

    def create_discover_tab(self) -> QWidget:
        """创建发现页面"""
        tab = QWidget()
        layout = QHBoxLayout(tab)

        # 左侧筛选
        filter_panel = self.create_filter_panel()
        layout.addWidget(filter_panel, 1)

        # 右侧商品列表
        self.product_list = QListWidget()
        self.product_list.itemClicked.connect(self.on_product_clicked)
        layout.addWidget(self.product_list, 3)

        return tab

    def create_filter_panel(self) -> QWidget:
        """创建筛选面板"""
        panel = QFrame()
        panel.setStyleSheet("background-color: #f5f5f5; border-right: 1px solid #ddd;")
        layout = QVBoxLayout(panel)

        # 标题
        title = QLabel("筛选条件")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        # 分类
        category_group = QGroupBox("商品分类")
        category_layout = QVBoxLayout()

        self.category_checkboxes = {}
        for cat in ProductCategory:
            cb = QCheckBox(f"{cat.icon} {cat.value}")
            cb.setChecked(True)
            self.category_checkboxes[cat.value] = cb
            category_layout.addWidget(cb)

        category_group.setLayout(category_layout)
        layout.addWidget(category_group)

        # 价格范围
        price_group = QGroupBox("价格范围")
        price_layout = QHBoxLayout()
        self.min_price = QSpinBox()
        self.max_price = QSpinBox()
        self.min_price.setRange(0, 999999)
        self.max_price.setRange(0, 999999)
        self.max_price.setValue(999999)
        price_layout.addWidget(QLabel("¥"))
        price_layout.addWidget(self.min_price)
        price_layout.addWidget(QLabel("~"))
        price_layout.addWidget(self.max_price)
        price_group.setLayout(price_layout)
        layout.addWidget(price_group)

        # 距离
        distance_group = QGroupBox("距离范围")
        distance_layout = QHBoxLayout()
        self.max_distance = QSpinBox()
        self.max_distance.setRange(1, 100)
        self.max_distance.setValue(10)
        distance_layout.addWidget(QLabel("≤"))
        distance_layout.addWidget(self.max_distance)
        distance_layout.addWidget(QLabel("km"))
        distance_group.setLayout(distance_layout)
        layout.addWidget(distance_group)

        layout.addStretch()

        return panel

    def create_my_products_tab(self) -> QWidget:
        """创建我的商品页面"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 工具栏
        toolbar = QHBoxLayout()

        add_btn = QPushButton("发布商品")
        add_btn.setObjectName("secondary")
        add_btn.clicked.connect(self.on_publish_product)

        refresh_btn = QPushButton("刷新")

        toolbar.addWidget(add_btn)
        toolbar.addStretch()
        toolbar.addWidget(refresh_btn)

        # 商品列表
        self.my_products_list = QTableWidget()
        self.my_products_list.setColumnCount(6)
        self.my_products_list.setHorizontalHeaderLabels(["ID", "标题", "分类", "价格", "状态", "操作"])

        layout.addLayout(toolbar)
        layout.addWidget(self.my_products_list)

        return tab

    def create_transactions_tab(self) -> QWidget:
        """创建交易页面"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 交易列表
        self.transactions_list = QTableWidget()
        self.transactions_list.setColumnCount(7)
        self.transactions_list.setHorizontalHeaderLabels([
            "交易ID", "买家", "卖家", "商品", "金额", "状态", "操作"
        ])

        layout.addWidget(self.transactions_list)

        return tab

    def create_delivery_tab(self) -> QWidget:
        """创建交付页面"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.delivery_list = QTableWidget()
        self.delivery_list.setColumnCount(6)
        self.delivery_list.setHorizontalHeaderLabels([
            "任务ID", "类型", "发件人", "收件人", "状态", "操作"
        ])

        layout.addWidget(self.delivery_list)

        return tab

    def create_reputation_tab(self) -> QWidget:
        """创建信誉页面"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 信誉概览
        overview = QGroupBox("我的信誉")
        overview_layout = QVBoxLayout()

        self.rep_score_label = QLabel("100")
        self.rep_score_label.setStyleSheet("font-size: 36px; font-weight: bold; color: #4CAF50;")

        self.rep_level_label = QLabel("🌱 新手")
        self.rep_level_label.setStyleSheet("font-size: 18px;")

        overview_layout.addWidget(self.rep_score_label, 0, Qt.AlignmentFlag.AlignCenter)
        overview_layout.addWidget(self.rep_level_label, 0, Qt.AlignmentFlag.AlignCenter)
        overview.setLayout(overview_layout)

        # 排行榜
        leaderboard = QGroupBox("信誉排行榜")
        leaderboard_layout = QVBoxLayout()
        self.leaderboard_table = QTableWidget()
        self.leaderboard_table.setColumnCount(4)
        self.leaderboard_table.setHorizontalHeaderLabels(["排名", "用户", "信誉分", "等级"])
        leaderboard_layout.addWidget(self.leaderboard_table)
        leaderboard.setLayout(leaderboard_layout)

        layout.addWidget(overview)
        layout.addWidget(leaderboard)

        return tab

    def create_disputes_tab(self) -> QWidget:
        """创建争议页面"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.disputes_list = QTableWidget()
        self.disputes_list.setColumnCount(6)
        self.disputes_list.setHorizontalHeaderLabels([
            "争议ID", "交易", "发起人", "类型", "状态", "操作"
        ])

        layout.addWidget(self.disputes_list)

        return tab

    def create_settings_tab(self) -> QWidget:
        """创建设置页面"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 基本设置
        basic_group = QGroupBox("基本设置")
        basic_layout = QVBoxLayout()

        # 显示位置
        location_layout = QHBoxLayout()
        location_layout.addWidget(QLabel("我的位置:"))
        location_input = QLineEdit()
        location_input.setPlaceholderText("输入你的位置...")
        location_layout.addWidget(location_input)
        basic_layout.addLayout(location_layout)

        # 接收通知
        notify_cb = QCheckBox("接收新商品通知")
        basic_layout.addWidget(notify_cb)

        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)

        # 交付设置
        delivery_group = QGroupBox("交付设置")
        delivery_layout = QVBoxLayout()

        pickup_cb = QCheckBox("支持自提")
        delivery_cb = QCheckBox("支持送货")
        delivery_layout.addWidget(pickup_cb)
        delivery_layout.addWidget(delivery_cb)

        delivery_group.setLayout(delivery_layout)
        layout.addWidget(delivery_group)

        layout.addStretch()

        return tab

    # ============================================================
    # 事件处理
    # ============================================================

    def on_search(self):
        """搜索商品"""
        query = self.search_input.text()

        results = self.product_manager.search_products(
            query=query,
            max_price=self.max_price.value(),
        )

        self.display_products(results)

    def on_product_clicked(self, item: QListWidgetItem):
        """点击商品"""
        product_id = item.data(Qt.ItemDataRole.UserRole)
        product = self.product_manager.get_product(product_id)

        if product:
            self.show_product_detail(product)

    def on_publish_product(self):
        """发布商品"""
        dialog = PublishProductDialog(self)
        if dialog.exec():
            product_data = dialog.get_product_data()

            product = Product(
                title=product_data["title"],
                description=product_data["description"],
                category=ProductCategory(product_data["category"]),
                price=product_data["price"],
                condition=product_data.get("condition", "new"),
                location=Location(
                    latitude=39.9,
                    longitude=116.4,
                    city="北京",
                    district="朝阳区",
                ),
            )

            pid = self.product_manager.publish_product(product)
            QMessageBox.information(self, "成功", f"商品已发布: {pid}")
            self.refresh_my_products()

    def show_product_detail(self, product: Product):
        """显示商品详情"""
        dialog = ProductDetailDialog(product, self.reputation_manager, self)
        dialog.exec()

    def refresh_products(self):
        """刷新商品列表"""
        results = self.product_manager.search_products(
            max_price=self.max_price.value(),
        )
        self.display_products(results)

    def refresh_my_products(self):
        """刷新我的商品"""
        products = self.product_manager.get_my_products()

        self.my_products_list.setRowCount(len(products))
        for i, product in enumerate(products):
            self.my_products_list.setItem(i, 0, QTableWidgetItem(product.product_id[:8]))
            self.my_products_list.setItem(i, 1, QTableWidgetItem(product.title))
            self.my_products_list.setItem(i, 2, QTableWidgetItem(product.category.value))
            self.my_products_list.setItem(i, 3, QTableWidgetItem(f"¥{product.price:,.2f}"))
            self.my_products_list.setItem(i, 4, QTableWidgetItem(product.status))

    def display_products(self, products: List[Product]):
        """显示商品列表"""
        self.product_list.clear()

        for product in products:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, product.product_id)

            # 创建卡片
            card = ProductCard(product, self.reputation_manager)
            self.product_list.addItem(item)
            self.product_list.setItemWidget(item, card)

    def load_demo_data(self):
        """加载演示数据"""
        # 添加演示商品
        demo_products = [
            Product(
                title="iPhone 14 Pro Max 256G 99新",
                description="无划痕无磕碰原装配件齐全",
                category=ProductCategory.ELECTRONICS,
                price=6999.0,
                condition="like_new",
                location=Location(39.9042, 116.4074, "北京", "朝阳区"),
            ),
            Product(
                title="二手自行车 捷安特",
                description="9成新，骑了半年",
                category=ProductCategory.SPORTS,
                price=800.0,
                condition="used",
                location=Location(39.95, 116.38, "北京", "海淀区"),
            ),
            Product(
                title="搬家转让家具",
                description="沙发、茶几、餐桌全套",
                category=ProductCategory.HOME,
                price=2000.0,
                condition="used",
                location=Location(39.91, 116.42, "北京", "朝阳区"),
            ),
        ]

        for p in demo_products:
            self.product_manager.publish_product(p)

        self.refresh_products()
        self.refresh_my_products()

        # 更新信誉
        self.update_reputation_display()

    def update_reputation_display(self):
        """更新信誉显示"""
        rep = self.reputation_manager.get_reputation(self.node_id)
        self.rep_score_label.setText(f"{rep.score:.0f}")
        self.rep_level_label.setText(f"{rep.level.icon} {rep.level.name_cn}")

        # 更新排行榜
        leaderboard = self.reputation_manager.get_leaderboard()
        self.leaderboard_table.setRowCount(len(leaderboard))
        for i, entry in enumerate(leaderboard):
            self.leaderboard_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.leaderboard_table.setItem(i, 1, QTableWidgetItem(entry["user_id"][:8]))
            self.leaderboard_table.setItem(i, 2, QTableWidgetItem(str(entry["score"])))
            self.leaderboard_table.setItem(i, 3, QTableWidgetItem(entry["level_icon"]))


# ============================================================
# 对话框
# ============================================================

class PublishProductDialog(QDialog):
    """发布商品对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("发布商品")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 标题
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("标题:"))
        self.title_input = QLineEdit()
        title_layout.addWidget(self.title_input)
        layout.addLayout(title_layout)

        # 描述
        layout.addWidget(QLabel("描述:"))
        self.desc_input = QTextEdit()
        layout.addWidget(self.desc_input)

        # 分类
        category_layout = QHBoxLayout()
        category_layout.addWidget(QLabel("分类:"))
        self.category_combo = QComboBox()
        for cat in ProductCategory:
            self.category_combo.addItem(f"{cat.icon} {cat.value}", cat.value)
        category_layout.addWidget(self.category_combo)
        layout.addLayout(category_layout)

        # 价格
        price_layout = QHBoxLayout()
        price_layout.addWidget(QLabel("价格:"))
        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0, 999999)
        self.price_input.setDecimals(2)
        price_layout.addWidget(self.price_input)
        layout.addLayout(price_layout)

        # 按钮
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("发布")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def get_product_data(self) -> Dict:
        return {
            "title": self.title_input.text(),
            "description": self.desc_input.toPlainText(),
            "category": self.category_combo.currentData(),
            "price": self.price_input.value(),
        }


class ProductDetailDialog(QDialog):
    """商品详情对话框"""

    def __init__(self, product: Product, rep_manager=None, parent=None):
        super().__init__(parent)
        self.product = product
        self.rep_manager = rep_manager
        self.setWindowTitle("商品详情")
        self.resize(400, 500)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel(self.product.title)
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # 价格
        price = QLabel(f"¥{self.product.price:,.2f}")
        price.setStyleSheet("font-size: 24px; color: #f44336; font-weight: bold;")
        layout.addWidget(price)

        # 分类
        category = QLabel(f"分类: {self.product.category.icon} {self.product.category.value}")
        layout.addWidget(category)

        # 描述
        layout.addWidget(QLabel("描述:"))
        desc = QTextEdit()
        desc.setText(self.product.description)
        desc.setReadOnly(True)
        layout.addWidget(desc)

        # 卖家信誉
        if self.rep_manager:
            rep = self.rep_manager.get_reputation(self.product.seller_id)
            rep_label = QLabel(f"卖家信誉: {rep.level.icon} {rep.level.name_cn} ({rep.score:.0f}分)")
            layout.addWidget(rep_label)

        # 按钮
        btn_layout = QHBoxLayout()
        buy_btn = QPushButton("立即购买")
        buy_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        negotiate_btn = QPushButton("协商价格")
        cancel_btn = QPushButton("关闭")

        btn_layout.addWidget(buy_btn)
        btn_layout.addWidget(negotiate_btn)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)


# ============================================================
# 主函数（用于测试）
# ============================================================

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)

    window = LocalMarketPanel()
    window.resize(1200, 800)
    window.show()

    sys.exit(app.exec())
