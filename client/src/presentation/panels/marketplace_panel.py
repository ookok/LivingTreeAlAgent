"""
生态市场面板 - 对接真实 Marketplace
"""

import os
from pathlib import Path
from typing import Optional, List, Dict

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QGroupBox, QFormLayout, QLineEdit, QComboBox,
    QMessageBox, QSplitter, QTextEdit, QSpinBox,
    QTabWidget, QWidget, QGridLayout, QFrame,
)
from PyQt6.QtGui import QFont, QPixmap


# ── 生态市场主界面 ─────────────────────────────────────────────────

class MarketplacePanel(QWidget):
    """生态市场面板 - 对接真实 Marketplace"""

    product_purchased = pyqtSignal(str)
    product_reviewed = pyqtSignal(str, int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._marketplace = None
        self._products: List[Dict] = []
        self._setup_ui()
        self._init_marketplace()

    def _setup_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 标题
        title = QLabel("🛒 生态市场")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        # 描述
        desc = QLabel("生态市场 - 浏览、购买、评价插件和技能")
        desc.setStyleSheet("font-size: 14px; color: #666;")
        layout.addWidget(desc)

        # 标签页
        tabs = QTabWidget()

        # 标签页1：浏览商品
        browse_tab = QWidget()
        browse_layout = QVBoxLayout(browse_tab)

        # 搜索和过滤
        filter_layout = QHBoxLayout()

        search_label = QLabel("搜索:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入商品名称...")
        self.search_edit.textChanged.connect(self._filter_products)
        filter_layout.addWidget(search_label)
        filter_layout.addWidget(self.search_edit)

        filter_layout.addSpacing(20)

        category_label = QLabel("分类:")
        self.category_combo = QComboBox()
        self.category_combo.addItems(["全部", "插件", "技能", "主题", "其他"])
        self.category_combo.currentTextChanged.connect(self._filter_products)
        filter_layout.addWidget(category_label)
        filter_layout.addWidget(self.category_combo)

        filter_layout.addStretch()

        browse_layout.addLayout(filter_layout)

        # 商品列表
        self.product_list = QListWidget()
        self.product_list.itemClicked.connect(self._on_product_selected)
        browse_layout.addWidget(self.product_list)

        tabs.addTab(browse_tab, "浏览商品")

        # 标签页2：我的购买
        my_tab = QWidget()
        my_layout = QVBoxLayout(my_tab)

        self.my_product_list = QListWidget()
        my_layout.addWidget(self.my_product_list)

        tabs.addTab(my_tab, "我的购买")

        layout.addWidget(tabs)

        # 商品详情
        detail_group = QGroupBox("商品详情")
        detail_layout = QFormLayout(detail_group)

        self.product_name_label = QLabel("-")
        detail_layout.addRow("名称:", self.product_name_label)

        self.product_author_label = QLabel("-")
        detail_layout.addRow("作者:", self.product_author_label)

        self.product_price_label = QLabel("-")
        detail_layout.addRow("价格:", self.product_price_label)

        self.product_rating_label = QLabel("-")
        detail_layout.addRow("评分:", self.product_rating_label)

        layout.addWidget(detail_group)

        # 描述
        desc_group = QGroupBox("描述")
        desc_layout = QVBoxLayout(desc_group)

        self.product_desc_text = QTextEdit()
        self.product_desc_text.setReadOnly(True)
        self.product_desc_text.setMaximumHeight(100)
        desc_layout.addWidget(self.product_desc_text)

        layout.addWidget(desc_group)

        # 按钮
        btn_layout = QHBoxLayout()

        self.purchase_btn = QPushButton("购买")
        self.purchase_btn.clicked.connect(self._purchase_product)
        self.purchase_btn.setEnabled(False)
        btn_layout.addWidget(self.purchase_btn)

        self.review_btn = QPushButton("评价")
        self.review_btn.clicked.connect(self._review_product)
        self.review_btn.setEnabled(False)
        btn_layout.addWidget(self.review_btn)

        btn_layout.addStretch()

        layout.addLayout(btn_layout)

    def _init_marketplace(self):
        """初始化 Marketplace"""
        try:
            from client.src.business.marketplace import Marketplace

            self._marketplace = Marketplace()

            self._load_products()

        except Exception as e:
            QMessageBox.warning(self, "警告", f"Marketplace 初始化失败: {e}")
            self._marketplace = None

    def _load_products(self):
        """加载商品列表（从 Marketplace）"""
        self.product_list.clear()
        self._products = []

        if not self._marketplace:
            return

        try:
            # 调用真实的 Marketplace API
            listings = self._marketplace.list_listings()

            for listing in listings:
                product = {
                    "id": listing.id,
                    "name": listing.name,
                    "author": listing.seller_id,
                    "price": listing.price,
                    "rating": listing.rating,
                    "category": listing.listing_type.value,
                    "desc": listing.description,
                    "purchased": False,  # TODO: 从交易记录判断
                }

                self._products.append(product)

                item = QListWidgetItem(product["name"])
                item.setData(1000, product)  # 存储商品数据
                self.product_list.addItem(item)

            # 加载我的购买
            self._load_my_products()

        except Exception as e:
            QMessageBox.warning(self, "警告", f"加载商品列表失败: {e}")

    def _load_my_products(self):
        """加载我的购买（从 Marketplace）"""
        self.my_product_list.clear()

        if not self._marketplace:
            return

        try:
            # TODO: 从 Marketplace 获取我的购买
            # 目前使用模拟数据
            for product in self._products:
                if product["purchased"]:
                    self.my_product_list.addItem(product["name"])

        except Exception as e:
            QMessageBox.warning(self, "警告", f"加载我的购买失败: {e}")

    def _filter_products(self):
        """过滤商品列表"""
        search_text = self.search_edit.text().lower()
        category = self.category_combo.currentText()

        for i in range(self.product_list.count()):
            item = self.product_list.item(i)
            product = item.data(1000)

            # 检查搜索文本
            match_search = (search_text in product["name"].lower() or
                           search_text in product["desc"].lower())

            # 检查分类
            match_category = (category == "全部") or (product["category"] == category)

            item.setHidden(not (match_search and match_category))

    def _on_product_selected(self, item):
        """商品选中"""
        product = item.data(1000)

        self.product_name_label.setText(product["name"])
        self.product_author_label.setText(product["author"])
        self.product_price_label.setText("免费" if product["price"] == 0 else f"¥{product['price']}")
        self.product_rating_label.setText("⭐" * int(product["rating"]) + f" ({product['rating']})")
        self.product_desc_text.setText(product["desc"])

        # 更新按钮状态
        self.purchase_btn.setEnabled(not product["purchased"])
        self.review_btn.setEnabled(product["purchased"])

    def _purchase_product(self):
        """购买商品"""
        current_item = self.product_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择一个商品")
            return

        product = current_item.data(1000)

        # 确认对话框
        reply = QMessageBox.question(
            self, "确认购买",
            f"确定要购买 {product['name']} 吗？\n价格: {'免费' if product['price'] == 0 else f'¥{product['price']}'}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if not self._marketplace:
                QMessageBox.warning(self, "警告", "Marketplace 未初始化")
                return

            try:
                # 调用真实的 Marketplace API
                # TODO: 获取当前用户 ID
                buyer_id = "current_user"

                transaction = self._marketplace.purchase(
                    listing_id=product["id"],
                    buyer_id=buyer_id,
                )

                # 更新状态
                product["purchased"] = True
                current_item.setData(1000, product)

                self.purchase_btn.setEnabled(False)
                self.review_btn.setEnabled(True)

                self.product_purchased.emit(product["name"])
                QMessageBox.information(self, "成功", f"商品 {product['name']} 购买成功")

                # 刷新我的购买
                self._load_my_products()

            except Exception as e:
                QMessageBox.warning(self, "警告", f"购买失败: {e}")

    def _review_product(self):
        """评价商品"""
        current_item = self.product_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择一个商品")
            return

        product = current_item.data(1000)

        # 模拟评价
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QRadioButton, QDialogButtonBox

        dialog = QDialog(self)
        dialog.setWindowTitle("评价商品")
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel(f"请评价 {product['name']}:"))

        # 评分
        rating_layout = QHBoxLayout()
        self.rating_buttons = []
        for i in range(1, 6):
            btn = QRadioButton("⭐" * i)
            if i == 5:
                btn.setChecked(True)
            self.rating_buttons.append(btn)
            rating_layout.addWidget(btn)

        layout.addLayout(rating_layout)

        # 评论
        self.review_edit = QTextEdit()
        self.review_edit.setPlaceholderText("输入你的评价...")
        self.review_edit.setMaximumHeight(100)
        layout.addWidget(self.review_edit)

        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 获取评分
            rating = 5
            for i, btn in enumerate(self.rating_buttons, 1):
                if btn.isChecked():
                    rating = i
                    break

            # 获取评论
            review = self.review_edit.toPlainText()

            if not self._marketplace:
                QMessageBox.warning(self, "警告", "Marketplace 未初始化")
                return

            try:
                # 调用真实的 Marketplace API
                # TODO: 获取当前用户 ID
                buyer_id = "current_user"

                self._marketplace.review(
                    listing_id=product["id"],
                    buyer_id=buyer_id,
                    rating=rating,
                    comment=review,
                )

                self.product_reviewed.emit(product["name"], rating, review)
                QMessageBox.information(self, "成功", f"评价提交成功！\n评分: {'⭐' * rating}\n评论: {review}")

            except Exception as e:
                QMessageBox.warning(self, "警告", f"评价失败: {e}")
