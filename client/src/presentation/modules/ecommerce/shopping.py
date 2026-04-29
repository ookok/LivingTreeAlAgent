"""
电商购物窗口 - E-commerce Shopping

支持：
- 商品搜索
- 商品分类浏览
- 购物车管理
- 订单查看
"""

from typing import List, Dict, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QPushButton, QScrollArea,
    QLineEdit, QListWidget, QListWidgetItem,
    QStackedWidget, QDialog, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal

from client.src.presentation.framework.minimal_ui_framework import (
    ColorScheme, Spacing, MinimalCard, UIComponentFactory
)


class ProductCard(QFrame):
    """商品卡片"""
    
    product_selected = pyqtSignal(dict)
    
    def __init__(self, product: Dict, parent=None):
        super().__init__(parent)
        self._product = product
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        self.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
            }
            QFrame:hover {
                border-color: #3B82F6;
                box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
            }
        """)
        
        # 商品图片区域
        image_area = QFrame()
        image_area.setFixedHeight(120)
        image_area.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border-radius: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
            }
        """)
        
        image_label = QLabel(self._product.get("icon", "📦"))
        image_label.setStyleSheet("font-size: 48px;")
        image_layout = QVBoxLayout(image_area)
        image_layout.addWidget(image_label)
        
        layout.addWidget(image_area)
        
        # 商品名称
        name_label = UIComponentFactory.create_label(
            self, self._product["name"], ColorScheme.TEXT_PRIMARY, 13
        )
        name_label.setWordWrap(True)
        layout.addWidget(name_label)
        
        # 价格
        price_label = QLabel(f"¥{self._product['price']}")
        price_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #EF4444;")
        layout.addWidget(price_label)
        
        # 添加购物车按钮
        add_btn = UIComponentFactory.create_button(
            self, "加入购物车", variant="primary", size="sm"
        )
        add_btn.clicked.connect(lambda: self.product_selected.emit(self._product))
        layout.addWidget(add_btn)


class ShoppingCart(QDialog):
    """购物车对话框"""
    
    def __init__(self, items: List[Dict], parent=None):
        super().__init__(parent)
        self._items = items
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle("🛒 购物车")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # 购物车列表
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        items_widget = QWidget()
        items_layout = QVBoxLayout(items_widget)
        
        total_price = 0
        for item in self._items:
            item_frame = QFrame()
            item_frame.setStyleSheet("""
                QFrame {
                    background-color: #FFFFFF;
                    border-bottom: 1px solid #E5E7EB;
                    padding: 12px;
                }
            """)
            
            item_layout_h = QHBoxLayout(item_frame)
            
            icon_label = QLabel(item.get("icon", "📦"))
            icon_label.setStyleSheet("font-size: 32px;")
            item_layout_h.addWidget(icon_label)
            
            info_widget = QWidget()
            info_layout = QVBoxLayout(info_widget)
            
            name_label = UIComponentFactory.create_label(
                info_widget, item["name"], ColorScheme.TEXT_PRIMARY, 14
            )
            info_layout.addWidget(name_label)
            
            price_label = QLabel(f"¥{item['price']}")
            price_label.setStyleSheet("font-size: 14px; color: #EF4444;")
            info_layout.addWidget(price_label)
            
            item_layout_h.addWidget(info_widget)
            item_layout_h.addStretch()
            
            quantity_label = QLabel(f"x{item.get('quantity', 1)}")
            quantity_label.setStyleSheet("font-size: 14px; color: #6B7280;")
            item_layout_h.addWidget(quantity_label)
            
            items_layout.addWidget(item_frame)
            
            total_price += item["price"] * item.get("quantity", 1)
        
        scroll_area.setWidget(items_widget)
        layout.addWidget(scroll_area, 1)
        
        # 底部结算
        bottom_frame = QFrame()
        bottom_frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-top: 1px solid #E5E7EB;
                padding: 16px;
            }
        """)
        
        bottom_layout = QHBoxLayout(bottom_frame)
        
        total_label = QLabel(f"合计: ¥{total_price}")
        total_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #EF4444;")
        bottom_layout.addWidget(total_label)
        bottom_layout.addStretch()
        
        checkout_btn = UIComponentFactory.create_button(
            bottom_frame, "结算", variant="primary", size="md"
        )
        bottom_layout.addWidget(checkout_btn)
        
        layout.addWidget(bottom_frame)


class ShoppingWindow(QWidget):
    """电商购物主窗口"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._products = self._load_products()
        self._cart = []
        self._setup_ui()
    
    def _load_products(self) -> List[Dict]:
        """加载商品列表"""
        return [
            {"id": 1, "name": "智能手表 Pro", "price": 1299, "icon": "⌚", "category": "电子产品"},
            {"id": 2, "name": "无线耳机", "price": 599, "icon": "🎧", "category": "电子产品"},
            {"id": 3, "name": "机械键盘", "price": 459, "icon": "⌨️", "category": "电子产品"},
            {"id": 4, "name": "蓝牙音箱", "price": 299, "icon": "🔊", "category": "电子产品"},
            {"id": 5, "name": "便携充电宝", "price": 199, "icon": "🔋", "category": "电子产品"},
            {"id": 6, "name": "电子书阅读器", "price": 899, "icon": "📚", "category": "电子产品"},
        ]
    
    def _setup_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #FAFAFA;
                font-family: 'Segoe UI', 'PingFang SC', sans-serif;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题栏
        title_bar = QFrame()
        title_bar.setFixedHeight(56)
        title_bar.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-bottom: 1px solid #E5E7EB;
            }
        """)
        
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 16, 0)
        
        title_label = UIComponentFactory.create_label(
            title_bar, "🛒 电商购物", ColorScheme.TEXT_PRIMARY, 16
        )
        title_layout.addWidget(title_label)
        
        # 搜索框
        search_input = QLineEdit()
        search_input.setPlaceholderText("搜索商品...")
        search_input.setStyleSheet("""
            QLineEdit {
                background-color: #F3F4F6;
                border: none;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
            }
        """)
        search_input.setFixedWidth(200)
        title_layout.addWidget(search_input)
        
        title_layout.addStretch()
        
        # 购物车按钮
        cart_btn = QPushButton(f"🛒 ({len(self._cart)})")
        cart_btn.setStyleSheet("""
            QPushButton {
                background-color: #EF4444;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 6px 16px;
                font-size: 13px;
            }
        """)
        cart_btn.clicked.connect(self._open_cart)
        title_layout.addWidget(cart_btn)
        
        layout.addWidget(title_bar)
        
        # 主内容区
        main_content = QWidget()
        main_layout = QHBoxLayout(main_content)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)
        
        # 分类导航
        categories = ["全部", "电子产品", "服装", "食品", "家居"]
        category_widget = QWidget()
        category_layout = QVBoxLayout(category_widget)
        
        for category in categories:
            btn = UIComponentFactory.create_button(
                category_widget, category, variant="secondary", size="sm"
            )
            category_layout.addWidget(btn)
        
        main_layout.addWidget(category_widget)
        
        # 商品列表
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        products_grid = QWidget()
        grid_layout = QGridLayout(products_grid)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(12)
        
        for i, product in enumerate(self._products):
            card = ProductCard(product)
            card.product_selected.connect(self._add_to_cart)
            card.setFixedSize(200, 220)
            grid_layout.addWidget(card, i // 4, i % 4)
        
        scroll_area.setWidget(products_grid)
        main_layout.addWidget(scroll_area, 1)
        
        layout.addWidget(main_content, 1)
    
    def _add_to_cart(self, product: Dict):
        """添加到购物车"""
        self._cart.append(product)
        
        # 更新购物车按钮
        for btn in self.findChildren(QPushButton):
            if btn.text().startswith("🛒"):
                btn.setText(f"🛒 ({len(self._cart)})")
                break
    
    def _open_cart(self):
        """打开购物车"""
        if self._cart:
            dialog = ShoppingCart(self._cart, self)
            dialog.exec()
        else:
            QDialog().exec()


# 全局购物窗口实例
_shopping_window = None

def get_shopping_window() -> ShoppingWindow:
    """获取购物窗口实例"""
    global _shopping_window
    if _shopping_window is None:
        _shopping_window = ShoppingWindow()
    return _shopping_window