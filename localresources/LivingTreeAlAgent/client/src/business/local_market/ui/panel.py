"""
去中心化本地商品交易市场 - PyQt6 管理面板

提供商品管理、交易、信誉查看等功能的图形界面
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QTabWidget, QGroupBox,
    QFormLayout, QScrollArea, QFrame, QDialog, QListWidget,
    QListWidgetItem, QProgressBar, QSpinBox, QDoubleSpinBox,
    QCheckBox, QSlider
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon, QColor, QPalette

from ..models import (
    Product, ProductCategory, Trade, TransactionStatus,
    DeliveryType, NodeInfo, ReputationAction
)
from .. import LocalMarketSystem


class LocalMarketPanel(QWidget):
    """本地商品交易市场管理面板"""

    def __init__(self, system: LocalMarketSystem = None):
        super().__init__()

        self.system = system or LocalMarketSystem()
        self.current_tab = "market"

        self._init_ui()
        self._connect_signals()

        # 定时刷新
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._refresh_data)
        self.refresh_timer.start(30000)  # 30秒刷新

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # 顶部标题栏
        header = self._create_header()
        layout.addWidget(header)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_market_tab(), "🛒 市场")
        self.tabs.addTab(self._create_my_products_tab(), "📦 我的商品")
        self.tabs.addTab(self._create_trades_tab(), "🤝 交易")
        self.tabs.addTab(self._create_reputation_tab(), "⭐ 信誉")
        self.tabs.addTab(self._create_settings_tab(), "⚙️ 设置")

        layout.addWidget(self.tabs)

    def _create_header(self) -> QWidget:
        """创建顶部标题栏"""
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    from: #667eea, to: #764ba2);
                border-radius: 8px;
                padding: 10px;
            }
        """)

        layout = QHBoxLayout(header)

        title = QLabel("🛒 去中心化本地商品交易市场")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")

        self.node_id_label = QLabel(f"节点: {self.system.node_id[:8]}")
        self.node_id_label.setStyleSheet("color: white; background: rgba(255,255,255,0.2); padding: 5px 10px; border-radius: 4px;")

        self.status_label = QLabel("⚡ 在线")
        self.status_label.setStyleSheet("color: #4ade80; font-weight: bold;")

        self.peers_label = QLabel("邻居: 0")
        self.peers_label.setStyleSheet("color: white;")

        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(self.node_id_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.peers_label)

        return header

    def _create_market_tab(self) -> QWidget:
        """创建市场标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 搜索栏
        search_bar = self._create_search_bar()
        layout.addWidget(search_bar)

        # 商品列表
        self.product_list = QListWidget()
        self.product_list.itemClicked.connect(self._on_product_clicked)
        layout.addWidget(self.product_list)

        # 商品详情区
        detail_group = QGroupBox("商品详情")
        detail_layout = QFormLayout(detail_group)

        self.detail_title = QLabel("")
        self.detail_price = QLabel("")
        self.detail_seller = QLabel("")
        self.detail_desc = QTextEdit()
        self.detail_desc.setReadOnly(True)

        detail_layout.addRow("标题:", self.detail_title)
        detail_layout.addRow("价格:", self.detail_price)
        detail_layout.addRow("卖家:", self.detail_seller)
        detail_layout.addRow("描述:", self.detail_desc)

        self.buy_btn = QPushButton("🛒 发起交易")
        self.buy_btn.clicked.connect(self._on_buy_clicked)
        detail_layout.addRow("", self.buy_btn)

        layout.addWidget(detail_group)

        return tab

    def _create_my_products_tab(self) -> QWidget:
        """创建我的商品标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 发布商品按钮
        btn_layout = QHBoxLayout()
        publish_btn = QPushButton("📤 发布新商品")
        publish_btn.clicked.connect(self._on_publish_clicked)
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._refresh_products)

        btn_layout.addWidget(publish_btn)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        # 我的商品表格
        self.my_products_table = QTableWidget()
        self.my_products_table.setColumnCount(7)
        self.my_products_table.setHorizontalHeaderLabels([
            "商品ID", "标题", "价格", "分类", "状态", "浏览", "操作"
        ])
        layout.addWidget(self.my_products_table)

        return tab

    def _create_trades_tab(self) -> QWidget:
        """创建交易标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 交易统计
        stats_layout = QHBoxLayout()

        self.active_trades_label = QLabel("进行中: 0")
        self.completed_trades_label = QLabel("已完成: 0")
        self.disputed_trades_label = QLabel("争议中: 0")

        for label in [self.active_trades_label, self.completed_trades_label, self.disputed_trades_label]:
            label.setStyleSheet("background: rgba(255,255,255,0.1); padding: 8px 16px; border-radius: 4px;")
            stats_layout.addWidget(label)

        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # 交易列表
        self.trades_table = QTableWidget()
        self.trades_table.setColumnCount(7)
        self.trades_table.setHorizontalHeaderLabels([
            "交易ID", "商品", "对方", "金额", "状态", "时间", "操作"
        ])
        self.trades_table.itemClicked.connect(self._on_trade_clicked)
        layout.addWidget(self.trades_table)

        return tab

    def _create_reputation_tab(self) -> QWidget:
        """创建信誉标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 我的信誉卡片
        rep_card = QFrame()
        rep_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    from: #f093fb, to: #f5576c);
                border-radius: 12px;
                padding: 20px;
            }
        """)
        rep_layout = QVBoxLayout(rep_card)

        rep_title = QLabel("我的信誉")
        rep_title.setStyleSheet("color: white; font-size: 16px;")

        self.my_rep_score = QLabel("100")
        self.my_rep_score.setStyleSheet("color: white; font-size: 48px; font-weight: bold;")

        self.my_rep_level = QLabel("等级: C")
        self.my_rep_level.setStyleSheet("color: white;")

        self.my_rep_change = QLabel("本月 +0")
        self.my_rep_change.setStyleSheet("color: rgba(255,255,255,0.8);")

        rep_layout.addWidget(rep_title)
        rep_layout.addWidget(self.my_rep_score)
        rep_layout.addWidget(self.my_rep_level)
        rep_layout.addWidget(self.my_rep_change)

        layout.addWidget(rep_card)

        # 信誉历史
        history_label = QLabel("信誉历史")
        history_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(history_label)

        self.rep_history_table = QTableWidget()
        self.rep_history_table.setColumnCount(4)
        self.rep_history_table.setHorizontalHeaderLabels(["时间", "事件", "变化", "原因"])
        layout.addWidget(self.rep_history_table)

        return tab

    def _create_settings_tab(self) -> QWidget:
        """创建设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 节点设置
        settings_group = QGroupBox("节点设置")
        settings_layout = QFormLayout(settings_group)

        self.node_name_input = QLineEdit(self.system.node_info.name)
        self.lat_input = QDoubleSpinBox()
        self.lat_input.setRange(-90, 90)
        self.lat_input.setValue(self.system.node_info.location.latitude if self.system.node_info.location else 0)

        self.lon_input = QDoubleSpinBox()
        self.lon_input.setRange(-180, 180)
        self.lon_input.setValue(self.system.node_info.location.longitude if self.system.node_info.location else 0)

        settings_layout.addRow("节点名称:", self.node_name_input)
        settings_layout.addRow("纬度:", self.lat_input)
        settings_layout.addRow("经度:", self.lon_input)

        layout.addWidget(settings_group)

        # 发现设置
        discovery_group = QGroupBox("发现设置")
        discovery_layout = QFormLayout(discovery_group)

        self.radius_input = QSpinBox()
        self.radius_input.setRange(1, 100)
        self.radius_input.setValue(10)
        self.radius_input.setSuffix(" km")

        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["混合策略", "同心圆", "智能广播", "兴趣匹配"])

        discovery_layout.addRow("搜索半径:", self.radius_input)
        discovery_layout.addRow("发现策略:", self.strategy_combo)

        layout.addWidget(discovery_group)

        # 保存按钮
        save_btn = QPushButton("💾 保存设置")
        save_btn.clicked.connect(self._on_save_settings)
        layout.addWidget(save_btn)

        layout.addStretch()

        return tab

    def _create_search_bar(self) -> QWidget:
        """创建搜索栏"""
        bar = QFrame()
        bar.setStyleSheet("background: rgba(255,255,255,0.1); border-radius: 8px; padding: 8px;")
        layout = QHBoxLayout(bar)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索商品...")
        self.search_input.returnPressed.connect(self._on_search)

        self.category_combo = QComboBox()
        self.category_combo.addItems(["全部分类", "电子产品", "服饰箱包", "家居用品", "食品生鲜", "图书二手", "本地服务", "其他"])

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["距离优先", "价格升序", "价格降序", "信誉优先", "最新优先"])

        search_btn = QPushButton("搜索")
        search_btn.clicked.connect(self._on_search)

        layout.addWidget(self.search_input)
        layout.addWidget(self.category_combo)
        layout.addWidget(self.sort_combo)
        layout.addWidget(search_btn)

        return bar

    def _connect_signals(self):
        """连接信号"""
        pass

    # ========================================================================
    # 事件处理
    # ========================================================================

    def _on_search(self):
        """搜索商品"""
        query = self.search_input.text()
        category_text = self.category_combo.currentText()

        category = None
        if category_text != "全部分类":
            category_map = {
                "电子产品": ProductCategory.ELECTRONICS,
                "服饰箱包": ProductCategory.FASHION,
                "家居用品": ProductCategory.HOME,
                "食品生鲜": ProductCategory.FOOD,
                "图书二手": ProductCategory.BOOKS,
                "本地服务": ProductCategory.SERVICES,
            }
            category = category_map.get(category_text)

        # 异步搜索
        asyncio.create_task(self._search_products(query, category))

    async def _search_products(self, query: str, category: ProductCategory = None):
        """异步搜索商品"""
        try:
            lat = self.lat_input.value() if self.lat_input.value() else None
            lon = self.lon_input.value() if self.lon_input.value() else None

            results = await self.system.discover_products(
                latitude=lat,
                longitude=lon,
                category=category,
                keywords=[query] if query else None,
                radius_km=self.radius_input.value()
            )

            self._update_product_list(results)

        except Exception as e:
            print(f"Search error: {e}")

    def _update_product_list(self, products: List[Dict]):
        """更新商品列表"""
        self.product_list.clear()

        for item in products:
            product_data = item.get("product", {})
            product = Product.from_dict(product_data)

            distance = item.get("distance_km", 0)
            rep = item.get("seller_rep", 0)

            text = f"""
                <div style='padding: 10px;'>
                    <b style='font-size: 14px;'>{product.title}</b>
                    <br/>
                    <span style='color: #f5576c; font-size: 16px;'>¥{product.price:.2f}</span>
                    <span style='color: #666; font-size: 12px;'> | 距离: {distance:.1f}km</span>
                    <span style='color: #ffa500; font-size: 12px;'> | 信誉: ⭐{rep}</span>
                    <br/>
                    <span style='color: #888; font-size: 12px;'>{product.category.value}</span>
                </div>
            """

            list_item = QListWidgetItem(text)
            list_item.setData(Qt.ItemDataRole.UserRole, product)
            self.product_list.addItem(list_item)

    def _on_product_clicked(self, item: QListWidgetItem):
        """商品项点击"""
        product = item.data(Qt.ItemDataRole.UserRole)
        if not product:
            return

        self.detail_title.setText(product.title)
        self.detail_price.setText(f"¥{product.price:.2f}")
        self.detail_seller.setText(f"节点: {product.seller_id[:8]}")
        self.detail_desc.setText(product.description)

    def _on_buy_clicked(self):
        """发起购买"""
        current_item = self.product_list.currentItem()
        if not current_item:
            return

        product = current_item.data(Qt.ItemDataRole.UserRole)
        if not product:
            return

        # 显示交易对话框
        dialog = TradeDialog(product, self.system)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh_data()

    def _on_publish_clicked(self):
        """发布商品"""
        dialog = PublishProductDialog(self.system)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh_products()

    def _on_trade_clicked(self, item: QTableWidgetItem):
        """交易项点击"""
        pass

    def _on_save_settings(self):
        """保存设置"""
        self.system.node_info.name = self.node_name_input.text()

        if self.system.node_info.location:
            self.system.node_info.location.latitude = self.lat_input.value()
            self.system.node_info.location.longitude = self.lon_input.value()

    def _refresh_data(self):
        """刷新数据"""
        self._refresh_products()
        self._refresh_trades()
        self._refresh_reputation()

        # 更新网络状态
        peers = len(self.system.network.get_alive_nodes())
        self.peers_label.setText(f"邻居: {peers}")

    def _refresh_products(self):
        """刷新商品列表"""
        asyncio.create_task(self._load_my_products())

    async def _load_my_products(self):
        """异步加载我的商品"""
        try:
            products = await self.system.get_my_products()
            self._update_my_products_table(products)
        except Exception as e:
            print(f"Load products error: {e}")

    def _update_my_products_table(self, products: List[Product]):
        """更新我的商品表格"""
        self.my_products_table.setRowCount(len(products))

        for row, product in enumerate(products):
            self.my_products_table.setItem(row, 0, QTableWidgetItem(product.product_id[:8]))
            self.my_products_table.setItem(row, 1, QTableWidgetItem(product.title))
            self.my_products_table.setItem(row, 2, QTableWidgetItem(f"¥{product.price:.2f}"))
            self.my_products_table.setItem(row, 3, QTableWidgetItem(product.category.value))
            self.my_products_table.setItem(row, 4, QTableWidgetItem(product.status))

            # 操作按钮
            edit_btn = QPushButton("编辑")
            edit_btn.clicked.connect(lambda _, p=product: self._on_edit_product(p))
            self.my_products_table.setCellWidget(row, 6, edit_btn)

    def _refresh_trades(self):
        """刷新交易列表"""
        trades = self.system.get_my_trades()

        active = sum(1 for t in trades if t.status in [TransactionStatus.INITIATED, TransactionStatus.NEGOTIATING, TransactionStatus.ESCROW])
        completed = sum(1 for t in trades if t.status == TransactionStatus.COMPLETED)
        disputed = sum(1 for t in trades if t.status == TransactionStatus.DISPUTED)

        self.active_trades_label.setText(f"进行中: {active}")
        self.completed_trades_label.setText(f"已完成: {completed}")
        self.disputed_trades_label.setText(f"争议中: {disputed}")

        self.trades_table.setRowCount(len(trades))
        for row, trade in enumerate(trades):
            self.trades_table.setItem(row, 0, QTableWidgetItem(trade.trade_id[:8]))
            self.trades_table.setItem(row, 1, QTableWidgetItem(trade.product_id[:8]))
            counterparty = trade.buyer.node_id if trade.seller.node_id == self.system.node_id else trade.seller.node_id
            self.trades_table.setItem(row, 2, QTableWidgetItem(counterparty[:8]))
            self.trades_table.setItem(row, 3, QTableWidgetItem(f"¥{trade.final_price:.2f}"))
            self.trades_table.setItem(row, 4, QTableWidgetItem(trade.status.value))
            self.trades_table.setItem(row, 5, QTableWidgetItem(trade.initiated_at.strftime("%Y-%m-%d %H:%M")))

    def _refresh_reputation(self):
        """刷新信誉"""
        rep = self.system.get_reputation()
        level = self.system.get_reputation_level()

        self.my_rep_score.setText(str(rep))
        self.my_rep_level.setText(f"等级: {level}")

    def _on_edit_product(self, product: Product):
        """编辑商品"""
        pass


class TradeDialog(QDialog):
    """交易对话框"""

    def __init__(self, product: Product, system: LocalMarketSystem):
        super().__init__()

        self.product = product
        self.system = system

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("发起交易")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # 商品信息
        info_label = QLabel(f"""
            <b>{self.product.title}</b><br/>
            价格: ¥{self.product.price:.2f}<br/>
            卖家: {self.product.seller_id[:8]}
        """)
        layout.addWidget(info_label)

        # 报价输入
        price_label = QLabel("你的报价:")
        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0, 1000000)
        self.price_input.setValue(self.product.price)
        self.price_input.setPrefix("¥ ")

        price_layout = QHBoxLayout()
        price_layout.addWidget(price_label)
        price_layout.addWidget(self.price_input)

        layout.addLayout(price_layout)

        # 留言
        msg_label = QLabel("留言:")
        self.msg_input = QTextEdit()
        self.msg_input.setPlaceholderText("可选：告诉卖家你想说的话...")

        layout.addWidget(msg_label)
        layout.addWidget(self.msg_input)

        # 按钮
        btn_layout = QHBoxLayout()
        confirm_btn = QPushButton("✅ 发起交易")
        confirm_btn.clicked.connect(self._on_confirm)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(confirm_btn)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    async def _on_confirm(self):
        """确认发起交易"""
        try:
            price = self.price_input.value()
            message = self.msg_input.toPlainText()

            # 发起交易
            trade = await self.system.initiate_trade(
                self.product.product_id,
                buyer_info={"node_id": self.system.node_id, "name": self.system.node_info.name}
            )

            # 如果有报价，发起议价
            if price < self.product.price:
                await self.system.make_offer(trade.trade_id, price, message)

            self.accept()

        except Exception as e:
            print(f"Trade error: {e}")


class PublishProductDialog(QDialog):
    """发布商品对话框"""

    def __init__(self, system: LocalMarketSystem):
        super().__init__()

        self.system = system

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("发布新商品")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)

        # 标题
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("标题:"))
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("商品标题")
        title_layout.addWidget(self.title_input)
        layout.addLayout(title_layout)

        # 价格
        price_layout = QHBoxLayout()
        price_layout.addWidget(QLabel("价格:"))
        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0, 1000000)
        self.price_input.setPrefix("¥ ")
        price_layout.addWidget(self.price_input)
        price_layout.addStretch()
        layout.addLayout(price_layout)

        # 分类
        cat_layout = QHBoxLayout()
        cat_layout.addWidget(QLabel("分类:"))
        self.category_combo = QComboBox()
        self.category_combo.addItems([
            "其他", "电子产品", "服饰箱包", "家居用品",
            "食品生鲜", "图书二手", "本地服务"
        ])
        cat_layout.addWidget(self.category_combo)
        cat_layout.addStretch()
        layout.addLayout(cat_layout)

        # 描述
        desc_label = QLabel("描述:")
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("详细描述商品...")
        layout.addWidget(desc_label)
        layout.addWidget(self.desc_input)

        # 交付方式
        delivery_layout = QHBoxLayout()
        delivery_layout.addWidget(QLabel("交付方式:"))
        self.delivery_combo = QComboBox()
        self.delivery_combo.addItems(["买家自提", "节点配送", "安全交付点"])
        delivery_layout.addWidget(self.delivery_combo)
        delivery_layout.addStretch()
        layout.addLayout(delivery_layout)

        # 按钮
        btn_layout = QHBoxLayout()
        confirm_btn = QPushButton("📤 发布")
        confirm_btn.clicked.connect(self._on_confirm)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(confirm_btn)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    async def _on_confirm(self):
        """确认发布"""
        try:
            title = self.title_input.text()
            price = self.price_input.value()
            category_text = self.category_combo.currentText()

            category_map = {
                "电子产品": ProductCategory.ELECTRONICS,
                "服饰箱包": ProductCategory.FASHION,
                "家居用品": ProductCategory.HOME,
                "食品生鲜": ProductCategory.FOOD,
                "图书二手": ProductCategory.BOOKS,
                "本地服务": ProductCategory.SERVICES,
            }
            category = category_map.get(category_text, ProductCategory.OTHER)

            delivery_text = self.delivery_combo.currentText()
            delivery_map = {
                "买家自提": DeliveryType.PICKUP,
                "节点配送": DeliveryType.NODE_DELIVERY,
                "安全交付点": DeliveryType.SAFEPOINT,
            }
            delivery = delivery_map.get(delivery_text, DeliveryType.PICKUP)

            await self.system.publish_product(
                title=title,
                description=self.desc_input.toPlainText(),
                price=price,
                category=category,
                delivery_type=delivery
            )

            self.accept()

        except Exception as e:
            print(f"Publish error: {e}")


# ========================================================================
# 便捷函数
# ========================================================================

def handle_market_command(command: str) -> str:
    """处理自然语言命令"""
    command = command.lower()

    if "发布" in command or "上架" in command:
        return "请使用发布商品功能填写商品信息"

    elif "搜索" in command or "找" in command:
        return "正在搜索附近商品..."

    elif "交易" in command or "购买" in command:
        return "请选择要购买的商品"

    elif "信誉" in command or "信誉分" in command:
        system = get_local_market_system()
        rep = system.get_reputation()
        level = system.get_reputation_level()
        return f"当前信誉: {rep} | 等级: {level}"

    return "未知命令，请尝试：发布商品、搜索商品、查看信誉"
