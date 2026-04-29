"""
自适应引导面板 - Adaptive Guide Panel

提供可视化的引导界面：

1. 仪表盘视图 - 展示系统状态
2. 待配置列表 - 优先处理高优配置
3. 引导流程视图 - 分步引导
4. 帮助卡片 - 上下文帮助

使用示例：
    panel = AdaptiveGuidePanel()
    panel.show()
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QListWidget, QListWidgetItem, QStackedWidget, QProgressBar,
    QCard, QTextEdit, QLineEdit, QComboBox, QGroupBox,
    QScrollArea, QFrame, QBadge, QToolButton
)
from PyQt6.QtGui import QFont, QIcon, QAction

logger = logging.getLogger(__name__)


class GuideStepWidget(QWidget):
    """引导步骤组件"""
    
    def __init__(self, step: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.step = step
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # 步骤标题
        title_label = QLabel(f"步骤 {self.step.get('step_id', '')}: {self.step.get('title', '')}")
        title_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        layout.addWidget(title_label)
        
        # 描述
        desc_label = QLabel(self.step.get('description', ''))
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666;")
        layout.addWidget(desc_label)
        
        # 状态
        status = self.step.get('status', 'pending')
        if status == 'completed':
            self.setStyleSheet("background: #e8f5e9; border-radius: 5px;")
        elif status == 'in_progress':
            self.setStyleSheet("background: #fff3e0; border-radius: 5px;")
    
    def update_status(self, status: str):
        """更新状态"""
        self.step['status'] = status
        if status == 'completed':
            self.setStyleSheet("background: #e8f5e9; border-radius: 5px;")
        elif status == 'in_progress':
            self.setStyleSheet("background: #fff3e0; border-radius: 5px;")
        elif status == 'failed':
            self.setStyleSheet("background: #ffebee; border-radius: 5px;")


class HelpCardWidget(QWidget):
    """帮助卡片组件"""
    
    clicked = pyqtSignal(str)  # feature_id
    
    def __init__(self, card: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.card = card
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        
        # 标题
        title_label = QLabel(self.card.get('title', ''))
        title_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        layout.addWidget(title_label)
        
        # 内容
        content = self.card.get('content', '')
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        layout.addWidget(content_label)
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        primary_action = self.card.get('primary_action')
        if primary_action:
            primary_btn = QPushButton(primary_action.get('title', '配置'))
            primary_btn.clicked.connect(lambda: self.clicked.emit(self.card.get('feature_id', '')))
            primary_btn.setStyleSheet("""
                QPushButton {
                    background: #4CAF50;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background: #45a049;
                }
            """)
            btn_layout.addWidget(primary_btn)
        
        secondary_actions = self.card.get('secondary_actions', [])
        if secondary_actions:
            for action in secondary_actions[:2]:
                btn = QPushButton(action.get('title', '')[:15])
                btn.clicked.connect(lambda checked, a=action: self.handle_action(a))
                btn_layout.addWidget(btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 时间估算
        time_estimate = self.card.get('time_estimate', '')
        if time_estimate:
            time_label = QLabel(f"⏱️ {time_estimate}")
            time_label.setStyleSheet("color: #888; font-size: 12px;")
            layout.addWidget(time_label)
        
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin: 5px;
            }
        """)
    
    def handle_action(self, action: Dict[str, Any]):
        """处理动作"""
        action_type = action.get('type', '')
        action_url = action.get('url', '')
        
        if action_type == 'guide':
            self.clicked.emit(action_url.replace('guide:', ''))
        elif action_type == 'switch':
            self.clicked.emit(f"switch:{action_url}")
        elif action_type == 'external':
            import webbrowser
            webbrowser.open(action_url)


class AdaptiveGuidePanel(QWidget):
    """
    自适应引导面板
    
    主面板组件，集成所有引导功能
    """
    
    # 信号
    guide_started = pyqtSignal(str)  # feature_id
    guide_completed = pyqtSignal(str)  # flow_id
    config_updated = pyqtSignal(dict)  # config
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 导入管理器
        try:
            from core.adaptive_guide import get_guide_manager, get_context_help
            self._manager = get_guide_manager()
            self._help = get_context_help()
        except ImportError as e:
            logger.warning("Adaptive guide manager not available: %s", e)
            self._manager = None
            self._help = None
        
        self._current_guide_flow = None
        self._init_ui()
        
        # 定时刷新
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_dashboard)
        self._refresh_timer.start(30000)  # 30秒刷新
    
    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        
        # 顶部标题栏
        header = self._create_header()
        main_layout.addWidget(header)
        
        # 标签页
        self._tabs = QTabWidget()
        
        # 仪表盘标签
        self._dashboard_tab = self._create_dashboard_tab()
        self._tabs.addTab(self._dashboard_tab, "📊 仪表盘")
        
        # 待配置标签
        self._pending_tab = self._create_pending_tab()
        self._tabs.addTab(self._pending_tab, "📋 待配置")
        
        # 引导标签
        self._guide_tab = self._create_guide_tab()
        self._tabs.addTab(self._guide_tab, "🚀 引导")
        
        # 帮助标签
        self._help_tab = self._create_help_tab()
        self._tabs.addTab(self._help_tab, "❓ 帮助")
        
        main_layout.addWidget(self._tabs)
    
    def _create_header(self) -> QWidget:
        """创建标题栏"""
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #667eea, stop:1 #764ba2);
                padding: 15px;
                border-radius: 0;
            }
        """)
        
        layout = QHBoxLayout(header)
        
        # 标题
        title = QLabel("🎯 自适应引导系统")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        layout.addWidget(title)
        
        layout.addStretch()
        
        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.2);
                color: white;
                border: 1px solid rgba(255,255,255,0.3);
                padding: 5px 15px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.3);
            }
        """)
        refresh_btn.clicked.connect(self._refresh_dashboard)
        layout.addWidget(refresh_btn)
        
        return header
    
    def _create_dashboard_tab(self) -> QWidget:
        """创建仪表盘标签"""
        widget = QScrollArea()
        widget.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        
        # 统计卡片
        stats_layout = QHBoxLayout()
        
        self._total_features_card = self._create_stat_card("总功能", "0", "📦")
        self._configured_card = self._create_stat_card("已配置", "0", "✅")
        self._pending_card = self._create_stat_card("待配置", "0", "⏳")
        self._active_impl_card = self._create_stat_card("当前方案", "-", "🔧")
        
        stats_layout.addWidget(self._total_features_card)
        stats_layout.addWidget(self._configured_card)
        stats_layout.addWidget(self._pending_card)
        stats_layout.addWidget(self._active_impl_card)
        
        layout.addLayout(stats_layout)
        
        # 用户画像卡片
        profile_card = self._create_profile_card()
        layout.addWidget(profile_card)
        
        # 最近引导
        recent_card = self._create_recent_guides_card()
        layout.addWidget(recent_card)
        
        layout.addStretch()
        widget.setWidget(container)
        
        return widget
    
    def _create_stat_card(self, title: str, value: str, icon: str) -> QWidget:
        """创建统计卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 15px;
                min-width: 120px;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 24px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        
        value_label = QLabel(value)
        value_label.setObjectName("stat_value")
        value_label.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #666;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        return card
    
    def _create_profile_card(self) -> QFrame:
        """创建用户画像卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        
        layout = QVBoxLayout(card)
        
        title = QLabel("👤 用户画像")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        self._profile_label = QLabel("加载中...")
        self._profile_label.setWordWrap(True)
        layout.addWidget(self._profile_label)
        
        return card
    
    def _create_recent_guides_card(self) -> QFrame:
        """创建最近引导卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        
        layout = QVBoxLayout(card)
        
        title = QLabel("📜 最近引导")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        self._recent_guides_list = QListWidget()
        layout.addWidget(self._recent_guides_list)
        
        return card
    
    def _create_pending_tab(self) -> QWidget:
        """创建待配置标签"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 说明
        info_label = QLabel("以下功能需要配置才能使用高级特性。点击开始引导配置。")
        info_label.setStyleSheet("color: #666; padding: 10px;")
        layout.addWidget(info_label)
        
        # 待配置列表
        self._pending_list = QListWidget()
        self._pending_list.itemClicked.connect(self._on_pending_item_clicked)
        layout.addWidget(self._pending_list)
        
        return widget
    
    def _create_guide_tab(self) -> QWidget:
        """创建引导标签"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 当前引导流程
        self._guide_steps_stack = QStackedWidget()
        layout.addWidget(self._guide_steps_stack)
        
        # 空状态
        self._guide_empty_state = QLabel("""
            <div style='text-align: center; padding: 50px;'>
                <div style='font-size: 48px;'>🚀</div>
                <div style='font-size: 18px; margin: 20px 0;'>选择一个待配置功能开始引导</div>
                <div style='color: #888;'>系统会一步步指导您完成配置</div>
            </div>
        """)
        self._guide_steps_stack.addWidget(self._guide_empty_state)
        
        # 引导步骤面板（稍后添加）
        self._guide_steps_panel = None
        self._guide_steps_stack.addWidget(QWidget())  # placeholder
        
        return widget
    
    def _create_help_tab(self) -> QWidget:
        """创建帮助标签"""
        widget = QScrollArea()
        widget.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        
        self._help_cards_container = QVBoxLayout()
        layout.addLayout(self._help_cards_container)
        
        layout.addStretch()
        widget.setWidget(container)
        
        return widget
    
    def _refresh_dashboard(self):
        """刷新仪表盘"""
        if self._manager is None:
            return
        
        try:
            dashboard = self._manager.get_dashboard_data()
            
            # 更新统计
            self._update_stat_value(self._total_features_card, str(dashboard.total_features))
            self._update_stat_value(self._configured_card, str(dashboard.configured_features))
            self._update_stat_value(self._pending_card, str(len(dashboard.pending_configurations)))
            
            # 更新用户画像
            profile = dashboard.user_profile
            profile_text = f"技术等级: {profile.get('tech_level', 'unknown')}\n"
            profile_text += f"使用模式: {profile.get('usage_pattern', 'unknown')}\n"
            profile_text += f"偏好引导: {', '.join(profile.get('preferred_guide_types', []))}"
            self._profile_label.setText(profile_text)
            
            # 更新待配置列表
            self._update_pending_list()
            
            # 更新帮助卡片
            self._update_help_cards()
            
            # 更新最近引导
            self._update_recent_guides()
            
        except Exception as e:
            logger.error("Failed to refresh dashboard: %s", e)
    
    def _update_stat_value(self, card: QWidget, value: str):
        """更新统计卡片值"""
        for child in card.children():
            if isinstance(child, QLabel) and child.objectName() == "stat_value":
                child.setText(value)
                break
    
    def _update_pending_list(self):
        """更新待配置列表"""
        self._pending_list.clear()
        
        if self._manager is None:
            return
        
        pending = self._manager.get_pending_configurations()
        
        for item_data in pending:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, item_data)
            
            # 创建列表项widget
            item_widget = QFrame()
            item_widget.setStyleSheet("""
                QFrame {
                    background: white;
                    border: 1px solid #e0e0e0;
                    border-radius: 5px;
                    padding: 10px;
                }
            """)
            
            layout = QVBoxLayout(item_widget)
            
            title = QLabel(f"📦 {item_data.get('feature_id', '')}")
            title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
            layout.addWidget(title)
            
            info = QLabel(f"当前方案: {item_data.get('implementation', '')} | 级别: {item_data.get('level', '')}")
            info.setStyleSheet("color: #666;")
            layout.addWidget(info)
            
            time_est = item_data.get('time_estimate', '')
            if time_est:
                time_label = QLabel(f"⏱️ {time_est}")
                time_label.setStyleSheet("color: #888; font-size: 12px;")
                layout.addWidget(time_label)
            
            self._pending_list.addItem(item)
            self._pending_list.setItemWidget(item, item_widget)
    
    def _update_help_cards(self):
        """更新帮助卡片"""
        # 清除现有卡片
        while self._help_cards_container.count():
            item = self._help_cards_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if self._manager is None:
            return
        
        # 添加卡片
        pending = self._manager.get_pending_configurations()
        
        for item_data in pending[:5]:  # 最多显示5个
            card_data = {
                'feature_id': item_data.get('feature_id', ''),
                'title': f"需要配置: {item_data.get('feature_id', '')}",
                'content': f"配置后可使用 {item_data.get('implementation', '')}",
                'time_estimate': item_data.get('time_estimate', ''),
                'primary_action': {'title': '🚀 开始引导', 'url': f"guide:{item_data.get('feature_id', '')}"},
                'secondary_actions': [
                    {'title': '💡 使用免费方案', 'url': f"switch:{item_data.get('feature_id', '')}"},
                ],
            }
            
            card = HelpCardWidget(card_data)
            card.clicked.connect(self._on_help_card_clicked)
            self._help_cards_container.addWidget(card)
    
    def _update_recent_guides(self):
        """更新最近引导"""
        self._recent_guides_list.clear()
        
        if self._manager is None:
            return
        
        recent = self._manager.get_recent_guides(limit=5)
        
        for guide in recent:
            status = "✅" if guide.get('completed') else "⏳"
            text = f"{status} {guide.get('feature_id', '')} - {guide.get('started_at', '')[:10]}"
            self._recent_guides_list.addItem(text)
    
    def _on_pending_item_clicked(self, item: QListWidgetItem):
        """待配置项点击"""
        item_data = item.data(Qt.ItemDataRole.UserRole)
        feature_id = item_data.get('feature_id', '')
        
        if feature_id:
            self.start_guide(feature_id)
    
    def _on_help_card_clicked(self, feature_id: str):
        """帮助卡片点击"""
        if feature_id.startswith('switch:'):
            # 切换到免费方案
            actual_id = feature_id.replace('switch:', '')
            self._switch_to_free_implementation(actual_id)
        else:
            # 开始引导
            self.start_guide(feature_id)
    
    def _switch_to_free_implementation(self, feature_id: str):
        """切换到免费实现"""
        if self._manager is None:
            return
        
        # 暂时标记为完成（实际实现中应该真正切换）
        logger.info("Switching %s to free implementation", feature_id)
        
        # 刷新显示
        self._refresh_dashboard()
    
    def start_guide(self, feature_id: str):
        """开始引导"""
        if self._manager is None:
            return
        
        # 创建引导流程
        flow = self._manager.start_guide(feature_id)
        
        if flow is None:
            logger.warning("No guide available for feature: %s", feature_id)
            return
        
        self._current_guide_flow = flow
        
        # 切换到引导标签
        self._tabs.setCurrentIndex(2)
        
        # 显示引导内容
        self._show_guide_flow(flow)
        
        # 发送信号
        self.guide_started.emit(feature_id)
    
    def _show_guide_flow(self, flow):
        """显示引导流程"""
        # 创建引导面板
        guide_panel = QWidget()
        layout = QVBoxLayout(guide_panel)
        
        # 标题
        title = QLabel(f"🚀 {flow.name}")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # 描述
        desc = QLabel(flow.description)
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # 进度条
        progress = QProgressBar()
        progress.setValue(0)
        layout.addWidget(progress)
        
        # 步骤列表
        steps_layout = QVBoxLayout()
        
        for step in flow.steps:
            step_widget = GuideStepWidget({
                'step_id': str(flow.steps.index(step) + 1),
                'title': step.title,
                'description': step.description,
                'status': step.status.value if hasattr(step.status, 'value') else 'pending',
            })
            steps_layout.addWidget(step_widget)
        
        layout.addLayout(steps_layout)
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        if flow.current_step_index > 0:
            prev_btn = QPushButton("⬅️ 上一步")
            prev_btn.clicked.connect(self._prev_guide_step)
            btn_layout.addWidget(prev_btn)
        
        skip_btn = QPushButton("跳过")
        skip_btn.clicked.connect(self._skip_guide_step)
        btn_layout.addWidget(skip_btn)
        
        next_btn = QPushButton("下一步 ➡️")
        next_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
            }
        """)
        next_btn.clicked.connect(self._next_guide_step)
        btn_layout.addWidget(next_btn)
        
        layout.addLayout(btn_layout)
        
        # 如果有当前步骤，替换占位符
        if self._guide_steps_panel is not None:
            self._guide_steps_stack.removeWidget(self._guide_steps_panel)
            self._guide_steps_panel.deleteLater()
        
        self._guide_steps_panel = guide_panel
        self._guide_steps_stack.addWidget(guide_panel)
        self._guide_steps_stack.setCurrentWidget(guide_panel)
    
    def _next_guide_step(self):
        """下一步"""
        if self._current_guide_flow is None:
            return
        
        current = self._current_guide_flow.get_current_step()
        if current:
            current.status = "completed"
        
        # 如果还有下一步
        next_step = self._current_guide_flow.get_next_step()
        if next_step:
            self._current_guide_flow.current_step_index += 1
            self._refresh_dashboard()
        else:
            # 完成
            self._complete_guide()
    
    def _prev_guide_step(self):
        """上一步"""
        if self._current_guide_flow is None:
            return
        
        if self._current_guide_flow.current_step_index > 0:
            self._current_guide_flow.current_step_index -= 1
            self._refresh_dashboard()
    
    def _skip_guide_step(self):
        """跳过步骤"""
        if self._current_guide_flow is None:
            return
        
        # 尝试下一步
        next_step = self._current_guide_flow.get_next_step()
        if next_step:
            self._current_guide_flow.current_step_index += 1
            self._refresh_dashboard()
        else:
            # 完成
            self._complete_guide()
    
    def _complete_guide(self):
        """完成引导"""
        if self._current_guide_flow is None:
            return
        
        flow_id = self._current_guide_flow.flow_id
        self._manager.complete_guide(flow_id)
        
        self._current_guide_flow = None
        
        # 切换回仪表盘
        self._tabs.setCurrentIndex(0)
        self._refresh_dashboard()
        
        # 发送信号
        self.guide_completed.emit(flow_id)
    
    def update_config(self, config: Dict[str, Any]):
        """更新配置"""
        if self._manager:
            self._manager.update_config(config)
            self._refresh_dashboard()
            self.config_updated.emit(config)