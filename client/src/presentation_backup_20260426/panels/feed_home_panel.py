# feed_home_panel.py — 聚合推荐首页 PyQt6 面板
# 瀑布流布局 + 自适应卡片 UI

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QScrollArea, QFrame, QSizePolicy,
    QComboBox, QCheckBox, QSpinBox, QGroupBox, QFormLayout,
    QListWidget, QListWidgetItem, QTextBrowser, QProgressBar,
    QMenu, QApplication,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QThread, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QAction, QCursor, QPixmap, QColor
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
import sys
import traceback
import asyncio


class FeedCard(QFrame):
    """
    单个 Feed 卡片

    样式：
    - 固定宽 300px，高度由内容撑开
    - 圆角 12px + 轻柔阴影
    - 悬停微放大 0.98s 过渡
    """

    # 信号
    clicked = pyqtSignal(str)        # item_id
    rightClicked = pyqtSignal(str)  # item_id
    bookmarked = pyqtSignal(str)    # item_id

    # 媒体加载完成信号
    mediaLoaded = pyqtSignal(str, QPixmap)  # item_id, pixmap

    CARD_WIDTH = 300
    MEDIA_HEIGHT = 120

    def __init__(self, item_data: dict, parent=None):
        super().__init__(parent)
        self.item_data = item_data
        self.item_id = item_data.get("id", "")
        self._pixmap = None
        self._network_manager = None

        self._init_ui()
        self._load_thumbnail()

    def _init_ui(self):
        """初始化 UI"""
        self.setFixedWidth(self.CARD_WIDTH)
        self.setMinimumHeight(100)
        self.setMaximumHeight(400)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # 样式
        self.setStyleSheet("""
            FeedCard {
                background-color: #ffffff;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }
            FeedCard:hover {
                border: 1px solid #4CAF50;
            }
        """)

        # 阴影效果
        from PyQt6.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 30))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

        # 布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. 媒体区
        self.media_label = QLabel()
        self.media_label.setFixedHeight(self.MEDIA_HEIGHT)
        self.media_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.media_label.setStyleSheet("""
            background-color: #f5f5f5;
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
            border-bottom: 1px solid #e0e0e0;
        """)
        layout.addWidget(self.media_label)

        # 2. 内容区
        content_frame = QFrame()
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(12, 10, 12, 10)
        content_layout.setSpacing(6)

        # 标题
        title_label = QLabel()
        title_label.setText(f"<b>{self._escape_html(self.item_data.get('title', ''))}</b>")
        title_label.setWordWrap(True)
        title_label.setMaximumHeight(44)  # 2行
        title_label.setStyleSheet("color: #333; font-size: 14px;")
        content_layout.addWidget(title_label)

        # 摘要
        summary = self.item_data.get("summary", "")
        if len(summary) > 100:
            summary = summary[:100] + "..."
        summary_label = QLabel(self._escape_html(summary))
        summary_label.setWordWrap(True)
        summary_label.setMaximumHeight(60)  # 3行
        summary_label.setStyleSheet("color: #888; font-size: 12px;")
        content_layout.addWidget(summary_label)

        # 元数据
        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(8)

        # 来源标签
        source = self.item_data.get("source", "unknown")
        source_label = QLabel(f"[{source}]")
        source_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
        meta_layout.addWidget(source_label)

        # 时间
        time_str = self.item_data.get("display_time", "")
        if time_str:
            time_label = QLabel(time_str)
            time_label.setStyleSheet("color: #999; font-size: 11px;")
            meta_layout.addWidget(time_label)

        meta_layout.addStretch()

        # 点赞数
        likes = self.item_data.get("likes", 0)
        if likes > 0:
            likes_label = QLabel(f"👍 {likes}")
            likes_label.setStyleSheet("color: #666; font-size: 11px;")
            meta_layout.addWidget(likes_label)

        content_layout.addLayout(meta_layout)

        layout.addWidget(content_frame)

        # 右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _escape_html(self, text: str) -> str:
        """HTML 转义"""
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#39;"))

    def _load_thumbnail(self):
        """懒加载缩略图"""
        thumbnail_url = self.item_data.get("thumbnail_url", "")
        if not thumbnail_url:
            self._show_placeholder()
            return

        # 使用 QNetworkAccessManager 异步加载
        if self._network_manager is None:
            self._network_manager = QNetworkAccessManager()

        request = QNetworkRequest(thumbnail_url)
        request.setHeader(QNetworkRequest.KnownHeaders.CacheLoadControlHeader, 1)  # AlwaysNetwork
        reply = self._network_manager.get(request)
        reply.finished.connect(lambda: self._on_thumbnail_loaded(reply))

    def _on_thumbnail_loaded(self, reply: QNetworkReply):
        """缩略图加载完成"""
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll()
            pixmap = QPixmap()
            pixmap.loadFromData(data)

            if not pixmap.isNull():
                # 缩放到合适大小
                scaled = pixmap.scaled(
                    self.CARD_WIDTH, self.MEDIA_HEIGHT,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.media_label.setPixmap(scaled)
                self._pixmap = scaled

                # 发射信号
                self.mediaLoaded.emit(self.item_id, scaled)
            else:
                self._show_placeholder()
        else:
            self._show_placeholder()

        reply.deleteLater()

    def _show_placeholder(self):
        """显示占位图"""
        self.media_label.setText("🖼️")
        self.media_label.setStyleSheet("""
            background-color: #f0f0f0;
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
            border-bottom: 1px solid #e0e0e0;
            color: #ccc;
            font-size: 32px;
        """)

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu(self)

        open_action = QAction("🔗 打开链接", self)
        open_action.triggered.connect(lambda: self._open_link())
        menu.addAction(open_action)

        bookmark_action = QAction("⭐ 收藏", self)
        bookmark_action.triggered.connect(lambda: self._bookmark())
        menu.addAction(bookmark_action)

        menu.addSeparator()

        hide_action = QAction("🚫 不感兴趣", self)
        hide_action.triggered.connect(lambda: self._hide())
        menu.addAction(hide_action)

        menu.exec(QCursor.pos())

    def _open_link(self):
        """打开链接"""
        import webbrowser
        url = self.item_data.get("url", "")
        if url:
            webbrowser.open(url)
        self.clicked.emit(self.item_id)

    def _bookmark(self):
        """收藏"""
        self.bookmarked.emit(self.item_id)

    def _hide(self):
        """不感兴趣"""
        self.rightClicked.emit(self.item_id)

    # 鼠标事件
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item_id)
        super().mousePressEvent(event)


class WaterfallLayout:
    """
    瀑布流布局管理器

    将卡片分配到多列，自动计算位置
    """

    def __init__(self, column_count: int = 3, spacing: int = 12):
        self.column_count = column_count
        self.spacing = spacing
        self.columns = [[] for _ in range(column_count)]  # 每列的卡片

    def add_card(self, card: FeedCard, height: int):
        """添加卡片到最短的列"""
        # 找到最短的列
        min_col = 0
        min_height = self._get_column_height(0)
        for i in range(1, self.column_count):
            h = self._get_column_height(i)
            if h < min_height:
                min_height = h
                min_col = i

        self.columns[min_col].append((card, height))

    def _get_column_height(self, col: int) -> int:
        return sum(h + self.spacing for _, h in self.columns[col])

    def get_positions(self) -> list:
        """获取所有卡片的位置 (card, x, y)"""
        positions = []

        col_heights = [0] * self.column_count

        for col_idx, column in enumerate(self.columns):
            x = col_idx * (FeedCard.CARD_WIDTH + self.spacing)

            for card, height in column:
                y = col_heights[col_idx]
                positions.append((card, x, y))
                col_heights[col_idx] += height + self.spacing

        return positions

    def clear(self):
        """清空"""
        self.columns = [[] for _ in range(self.column_count)]


class FeedHomePanel(QWidget):
    """
    聚合推荐首页面板

    功能：
    - 瀑布流显示 Feed 卡片
    - 懒加载缩略图
    - 右键不感兴趣反馈
    - 兴趣画像展示
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.system = None  # 延迟加载
        self._cards: Dict[str, FeedCard] = {}
        self._瀑布流 = None
        self._scroll_timer = QTimer()

        self._init_ui()
        self._init_network()

    def _ensure_system(self):
        if self.system is None:
            try:
                from .business.feed_aggregator import get_feed_system
                self.system = get_feed_system()
            except ImportError:
                self.system = None

    # ============================================================
    # UI 初始化
    # ============================================================

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 顶部工具栏
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(12, 8, 12, 8)

        title = QLabel("🌿 信息流")
        title.setFont(QFont("Microsoft YaHei", 13, QFont.Weight.Bold))
        toolbar.addWidget(title)

        toolbar.addStretch()

        # 来源过滤
        self.source_filter = QComboBox()
        self.source_filter.addItems(["全部", "微博", "知乎", "Reddit", "GitHub", "新闻"])
        self.source_filter.currentTextChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.source_filter)

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._refresh_feed)
        toolbar.addWidget(refresh_btn)

        # 设置按钮
        settings_btn = QPushButton("⚙️")
        settings_btn.clicked.connect(self._show_settings)
        toolbar.addWidget(settings_btn)

        main_layout.addLayout(toolbar)

        # Feed 瀑布流区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #f5f5f5;
            }
        """)

        # 瀑布流容器
        self.feed_container = QWidget()
        self.feed_layout = QVBoxLayout(self.feed_container)
        self.feed_layout.setContentsMargins(12, 12, 12, 12)
        self.feed_layout.setSpacing(12)

        self.scroll_area.setWidget(self.feed_container)
        main_layout.addWidget(self.scroll_area)

        # 滚动懒加载
        self.scroll_area.vscrollbar().valueChanged.connect(self._on_scroll)

        # 底部状态栏
        status_bar = QHBoxLayout()
        status_bar.setContentsMargins(12, 4, 12, 4)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #888; font-size: 11px;")
        status_bar.addWidget(self.status_label)

        status_bar.addStretch()

        self.interest_btn = QPushButton("🧠 兴趣画像")
        self.interest_btn.clicked.connect(self._show_interest_profile)
        status_bar.addWidget(self.interest_btn)

        main_layout.addLayout(status_bar)

    def _init_network(self):
        """初始化网络管理器"""
        self._network_manager = QNetworkAccessManager()

    # ============================================================
    # 数据刷新
    # ============================================================

    def _refresh_feed(self):
        """刷新内容流"""
        self._ensure_system()
        if self.system is None:
            self.status_label.setText("系统未加载")
            return

        self.status_label.setText("刷新中...")
        QApplication.processEvents()

        # 异步刷新
        try:
            loop = asyncio.get_event_loop()
        except:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            items = loop.run_until_complete(self.system.refresh())
            self._display_items(items)
            self.status_label.setText(f"已加载 {len(items)} 条内容")
        except Exception as e:
            self.status_label.setText(f"刷新失败: {e}")
            traceback.print_exc()

    def _display_items(self, items: list):
        """显示内容列表"""
        # 清空旧卡片
        for card in self._cards.values():
            card.deleteLater()
        self._cards.clear()

        # 清空布局
        while self.feed_layout.count():
            child = self.feed_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # 创建瀑布流行
        self._瀑布流 = WaterfallLayout(column_count=3, spacing=12)

        # 创建卡片
        for item_data in items[:50]:  # 限制50条
            card = FeedCard(item_data)
            card.clicked.connect(self._on_card_clicked)
            card.rightClicked.connect(self._on_card_hidden)
            card.bookmarked.connect(self._on_card_bookmarked)

            self._cards[item_data["id"]] = card

            # 估算高度
            height = FeedCard.MEDIA_HEIGHT + 130  # 内容区约130
            self._瀑布流.add_card(card, height)

        # 布局卡片
        self._layout_cards()

    def _layout_cards(self):
        """布局所有卡片"""
        if not self._瀑布流:
            return

        positions = self._瀑布流.get_positions()

        for card, x, y in positions:
            card.move(x, y)

        # 设置容器大小
        max_height = max(
            sum(h + self._瀑布流.spacing for _, h in col)
            for col in self._瀑布流.columns
        ) if self._瀑布流.columns else 0

        container_width = 3 * (FeedCard.CARD_WIDTH + self._瀑布流.spacing) + 24
        self.feed_container.setFixedSize(container_width, max_height + 24)

    def _on_scroll(self, value: int):
        """滚动加载（预留扩展）"""
        pass

    # ============================================================
    # 交互处理
    # ============================================================

    def _on_card_clicked(self, item_id: str):
        """卡片点击"""
        self._ensure_system()
        if self.system:
            self.system.record_click(item_id)

    def _on_card_hidden(self, item_id: str):
        """卡片隐藏（不感兴趣）"""
        self._ensure_system()
        if self.system:
            self.system.record_hide(item_id)

        # 卡片淡出移除
        card = self._cards.get(item_id)
        if card:
            self._fade_out_card(card)
            del self._cards[item_id]

    def _on_card_bookmarked(self, item_id: str):
        """卡片收藏"""
        self._ensure_system()
        if self.system:
            self.system.record_bookmark(item_id)
        self.status_label.setText("已收藏 ⭐")

    def _fade_out_card(self, card: FeedCard):
        """卡片淡出动画"""
        # 简单淡出 - 使用 setStyleSheet 模拟
        card.setStyleSheet("""
            FeedCard {
                background-color: #ffffff;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
                opacity: 0;
            }
        """)
        QTimer.singleShot(300, card.deleteLater)

    def _on_filter_changed(self, text: str):
        """过滤条件变化"""
        # 可以根据来源过滤
        pass

    # ============================================================
    # 工具窗口
    # ============================================================

    def _show_settings(self):
        """显示设置面板"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QSpinBox, QCheckBox

        dialog = QDialog(self)
        dialog.setWindowTitle("信息流设置")
        layout = QVBoxLayout(dialog)

        form = QFormLayout()

        # 抓取间隔
        interval = QSpinBox()
        interval.setRange(5, 120)
        interval.setSuffix(" 分钟")
        interval.setValue(30)
        form.addRow("抓取间隔:", interval)

        # 显示数量
        visible = QSpinBox()
        visible.setRange(10, 100)
        visible.setValue(50)
        form.addRow("显示数量:", visible)

        # 自动刷新
        auto_refresh = QCheckBox()
        auto_refresh.setChecked(True)
        form.addRow("自动刷新:", auto_refresh)

        layout.addLayout(form)

        # 按钮
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        dialog.exec()

    def _show_interest_profile(self):
        """显示兴趣画像"""
        self._ensure_system()
        if self.system is None:
            return

        profile = self.system.get_interest_profile()

        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel

        dialog = QDialog(self)
        dialog.setWindowTitle("🧠 你的兴趣画像")
        layout = QVBoxLayout(dialog)

        # 统计
        stats = QLabel()
        stats.setText(f"""
            <b>统计</b><br>
            点击次数: {profile.get('total_clicks', 0)}<br>
            浏览次数: {profile.get('total_views', 0)}<br>
            不感兴趣: {profile.get('total_hides', 0)}<br>
        """)
        layout.addWidget(stats)

        # 标签权重
        tags_label = QLabel("<b>热门标签</b>")
        layout.addWidget(tags_label)

        for tag, weight in profile.get("top_tags", [])[:10]:
            weight_pct = int(weight * 100)
            tag_label = QLabel(f"  {tag}: {weight_pct}%")
            layout.addWidget(tag_label)

        dialog.exec()

    # ============================================================
    # 生命周期
    # ============================================================

    def showEvent(self, event):
        super().showEvent(event)
        if not self._cards:
            QTimer.singleShot(100, self._refresh_feed)

    def hideEvent(self, event):
        super().hideEvent(event)
