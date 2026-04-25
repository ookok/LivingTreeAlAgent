"""
首页聚合推荐面板
轻量级推荐系统 UI
"""

import asyncio
import webbrowser
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem,
    QScrollArea, QFrame, QSizePolicy,
    QMenu, QApplication
)
from PyQt6.QtGui import QIcon, QAction

from core.recommendation import (
    get_profile_manager,
    get_recall_engine,
    get_ranking_engine,
    adapt_items,
    UnifiedItem
)
from core.recommendation.user_profile import UserProfileManager
from client.src.presentation.panels.recommendation_card import RecommendationCard, EmptyRecommendationCard


class RecommendationWorker(QThread):
    """推荐内容加载线程"""
    
    finished = pyqtSignal(list)  # 加载完成信号
    error = pyqtSignal(str)       # 错误信号
    progress = pyqtSignal(str)    # 进度信号
    
    def __init__(self, recall_engine, ranking_engine, profile_manager):
        super().__init__()
        self.recall_engine = recall_engine
        self.ranking_engine = ranking_engine
        self.profile_manager = profile_manager
    
    def run(self):
        """执行推荐加载"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 获取用户画像
            self.progress.emit("获取用户画像...")
            profile = self.profile_manager.get_profile()
            
            # 召回
            self.progress.emit("召回内容...")
            raw_items = loop.run_until_complete(
                self.recall_engine.recall_all(profile, limit_per_source=15)
            )
            
            # 排序
            self.progress.emit("智能排序...")
            ranked_items = self.ranking_engine.rank(raw_items, profile, top_k=10)
            
            # 转换
            self.progress.emit("整理结果...")
            unified_items = adapt_items(ranked_items)
            
            loop.close()
            
            self.finished.emit(unified_items)
            
        except Exception as e:
            self.error.emit(str(e))


class RecommendationPanel(QFrame):
    """
    推荐面板
    展示个性化推荐内容卡片流
    """
    
    # 配置改变信号
    visibility_changed = pyqtSignal(bool)  # 可见性改变
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化推荐系统
        self.profile_manager = get_profile_manager()
        self.recall_engine = get_recall_engine(self.profile_manager)
        self.ranking_engine = get_ranking_engine()
        
        # 状态
        self._worker: Optional[RecommendationWorker] = None
        self._items: list[UnifiedItem] = []
        
        self.setup_ui()
        self.apply_style()
        
        # 启动首次加载
        self.refresh()
    
    def setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 标题栏
        header = QWidget()
        header.setFixedHeight(50)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)
        
        title = QLabel("🏠 首页推荐")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1f2937;")
        header_layout.addWidget(title)
        
        # 刷新按钮
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.setFixedSize(80, 32)
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #2563eb;
            }
            QPushButton:disabled {
                background: #93c5fd;
            }
        """)
        header_layout.addWidget(self.refresh_btn)
        
        # 加载状态
        self.status_label = QLabel()
        self.status_label.setStyleSheet("font-size: 12px; color: #6b7280;")
        header_layout.addWidget(self.status_label)
        
        main_layout.addWidget(header)
        
        # 分隔线
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background: #e5e7eb;")
        divider.setFixedHeight(1)
        main_layout.addWidget(divider)
        
        # 推荐列表（滚动区域）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: #f9fafb;
            }
            QScrollBar:vertical {
                width: 6px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #d1d5db;
                border-radius: 3px;
            }
        """)
        
        # 列表容器
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(12, 12, 12, 12)
        self.list_layout.setSpacing(8)
        self.list_layout.addStretch()
        
        scroll.setWidget(self.list_container)
        main_layout.addWidget(scroll)
        
        # 右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def apply_style(self):
        """应用样式"""
        self.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 0;
            }
        """)
        self.setMinimumWidth(320)
        self.setMaximumWidth(400)
    
    def refresh(self):
        """刷新推荐内容"""
        if self._worker and self._worker.isRunning():
            return
        
        # 禁用刷新按钮
        self.refresh_btn.setDisabled(True)
        self.status_label.setText("加载中...")
        
        # 清空列表
        self._clear_list()
        
        # 显示加载状态
        self._show_loading()
        
        # 启动工作线程
        self._worker = RecommendationWorker(
            self.recall_engine,
            self.ranking_engine,
            self.profile_manager
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()
    
    def _clear_list(self):
        """清空列表"""
        # 移除所有卡片（除了最后一个stretch）
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def _show_loading(self):
        """显示加载状态"""
        loading = QLabel("⏳ 正在加载推荐内容...")
        loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading.setStyleSheet("""
            padding: 40px;
            font-size: 14px;
            color: #6b7280;
        """)
        self.list_layout.insertWidget(0, loading)
    
    def _on_progress(self, msg: str):
        """进度更新"""
        self.status_label.setText(msg)
    
    def _on_loaded(self, items: list[UnifiedItem]):
        """加载完成"""
        self._items = items
        self._clear_list()
        
        if not items:
            # 显示空状态
            empty_card = EmptyRecommendationCard(
                "暂无推荐，去聊天生成用户画像吧！"
            )
            empty_card.clicked.connect(self._on_empty_clicked)
            self.list_layout.insertWidget(0, empty_card)
            self.status_label.setText("暂无推荐")
        else:
            # 显示推荐卡片
            for item in items:
                card = RecommendationCard({
                    "id": item.id,
                    "type": item.type,
                    "title": item.title,
                    "description": item.description,
                    "url": item.url,
                    "icon": item.icon,
                    "source": item.source,
                    "publish_time": item.publish_time,
                    "tags": item.tags,
                })
                card.clicked.connect(self._on_card_clicked)
                self.list_layout.insertWidget(self.list_layout.count() - 1, card)
            
            self.status_label.setText(f"已加载 {len(items)} 条推荐")
        
        self.refresh_btn.setDisabled(False)
    
    def _on_error(self, error: str):
        """加载错误"""
        self._clear_list()
        
        error_card = EmptyRecommendationCard(f"加载失败: {error}")
        self.list_layout.insertWidget(0, error_card)
        
        self.refresh_btn.setDisabled(False)
        self.status_label.setText("加载失败")
    
    def _on_card_clicked(self, item_id: str, item_type: str, url: str):
        """卡片点击"""
        # 记录行为
        self.profile_manager.record_behavior(item_id, item_type, "click")
        
        # 打开链接
        if url:
            webbrowser.open(url)
    
    def _on_empty_clicked(self):
        """空状态点击"""
        # 提示用户去聊天
        self.status_label.setText("💡 去聊天探索更多内容吧！")
    
    def show_context_menu(self, pos):
        """右键菜单"""
        menu = QMenu(self)
        
        # 刷新
        refresh_action = QAction("🔄 刷新推荐", self)
        refresh_action.triggered.connect(self.refresh)
        menu.addAction(refresh_action)
        
        menu.addSeparator()
        
        # 兴趣管理
        interests_action = QAction("⚙️ 管理兴趣标签", self)
        interests_action.triggered.connect(self._show_interest_manager)
        menu.addAction(interests_action)
        
        # 清空画像
        clear_action = QAction("🗑️ 重置用户画像", self)
        clear_action.triggered.connect(self._clear_profile)
        menu.addAction(clear_action)
        
        menu.exec(self.mapToGlobal(pos))
    
    def _show_interest_manager(self):
        """显示兴趣管理器"""
        profile = self.profile_manager.get_profile()
        interests = profile.get_top_interests(10)
        
        from PyQt6.QtWidgets import QInputDialog
        tags, ok = QInputDialog.getMultiLineText(
            self,
            "管理兴趣标签",
            "当前兴趣标签（每行一个）：",
            "\n".join(interests) if interests else ""
        )
        
        if ok:
            # 解析标签
            new_tags = [t.strip() for t in tags.split("\n") if t.strip()]
            self.profile_manager.update_from_tags(new_tags)
            self.refresh()
    
    def _clear_profile(self):
        """清空用户画像"""
        from PyQt6.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(
            self,
            "确认重置",
            "确定要重置用户画像吗？这将清除所有兴趣记录。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            profile = self.profile_manager.get_profile()
            profile.click_history.clear()
            profile.view_history.clear()
            profile.interests.clear()
            profile.total_clicks = 0
            profile.total_views = 0
            profile.is_cold_start = True
            self.profile_manager.save()
            self.refresh()
    
    def update_interests(self, tags: list[str]):
        """从外部更新兴趣标签"""
        self.profile_manager.update_from_tags(tags)
    
    def get_config(self) -> dict:
        """获取面板配置"""
        return {
            "enabled": self.isVisible(),
            "items": [
                {
                    "id": item.id,
                    "type": item.type,
                    "title": item.title,
                }
                for item in self._items[:5]  # 只保存前5条
            ]
        }
    
    def set_config(self, config: dict):
        """设置面板配置"""
        if "enabled" in config:
            self.setVisible(config["enabled"])
