# -*- coding: utf-8 -*-
"""
Persona Skill 面板 - PyQt6 角色智库 UI
=====================================

功能：
- 角色浏览与搜索
- 角色分类筛选
- 角色激活/停用
- 快捷咨询
- 多轮对话
- 角色蒸馏

Author: Hermes Desktop Team
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QListWidget,
    QListWidgetItem, QComboBox, QTabWidget, QGroupBox,
    QScrollArea, QFrame, QProgressBar,
    QListView, QStyledItemDelegate, QStyleOptionViewItem
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPalette, QColor, QAction

import asyncio
from datetime import datetime
from typing import Optional, Dict, List

from .business.persona_skill import (
    PersonaEngine, PersonaRegistry, PersonaSkill,
    PersonaCategory, PersonaTier
)


# ==================== 角色卡片组件 ====================

class PersonaCard(QFrame):
    """角色卡片组件"""

    activated = pyqtSignal(str)  # 激活信号
    consulted = pyqtSignal(str)  # 咨询信号

    def __init__(self, persona: PersonaSkill, parent=None):
        super().__init__(parent)
        self.persona = persona
        self._setup_ui()
        self._update_style()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 头部：图标 + 名称
        header = QHBoxLayout()
        self.icon_label = QLabel(self.persona.icon)
        self.icon_label.setFont(QFont("Segoe UI Emoji", 24))
        
        name_layout = QVBoxLayout()
        self.name_label = QLabel(self.persona.name)
        self.name_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        
        self.tier_label = QLabel(f"[{self.persona.tier.value}]")
        self.tier_label.setFont(QFont("Microsoft YaHei", 8))
        self.tier_label.setStyleSheet("color: #888;")
        
        name_layout.addWidget(self.name_label)
        name_layout.addWidget(self.tier_label)
        
        header.addWidget(self.icon_label)
        header.addLayout(name_layout)
        header.addStretch()
        
        # Star 徽章
        if self.persona.star > 0:
            self.star_label = QLabel(f"★ {self.persona.star:,}")
            self.star_label.setStyleSheet("color: #f5a623; font-size: 10px;")
            header.addWidget(self.star_label)

        layout.addLayout(header)

        # 描述
        self.desc_label = QLabel(self.persona.description)
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.desc_label)

        # 标签
        tags_layout = QHBoxLayout()
        for tag in self.persona.tags[:3]:
            tag_btn = QLabel(f"#{tag}")
            tag_btn.setStyleSheet("""
                background-color: #e8f4fd;
                color: #1890ff;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
            """)
            tags_layout.addWidget(tag_btn)
        tags_layout.addStretch()
        layout.addLayout(tags_layout)

        # 按钮
        btn_layout = QHBoxLayout()
        self.activate_btn = QPushButton("激活")
        self.activate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.activate_btn.clicked.connect(lambda: self.activated.emit(self.persona.id))
        
        self.consult_btn = QPushButton("咨询")
        self.consult_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.consult_btn.clicked.connect(lambda: self.consulted.emit(self.persona.id))
        
        btn_layout.addWidget(self.activate_btn)
        btn_layout.addWidget(self.consult_btn)
        layout.addLayout(btn_layout)

        # 使用统计
        stats_layout = QHBoxLayout()
        stats_layout.addStretch()
        if self.persona.usage_count > 0:
            usage_label = QLabel(f"使用 {self.persona.usage_count} 次")
            usage_label.setStyleSheet("color: #999; font-size: 9px;")
            stats_layout.addWidget(usage_label)
        layout.addLayout(stats_layout)

    def _update_style(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setLineWidth(1)
        self.setStyleSheet("""
            PersonaCard {
                background-color: white;
                border: 1px solid #e8e8e8;
                border-radius: 8px;
            }
            PersonaCard:hover {
                border-color: #1890ff;
                background-color: #fafafa;
            }
        """)

    def set_activated(self, is_active: bool):
        """设置激活状态"""
        if is_active:
            self.setStyleSheet("""
                PersonaCard {
                    background-color: #e6f7ff;
                    border: 2px solid #1890ff;
                    border-radius: 8px;
                }
            """)
            self.activate_btn.setText("已激活")
            self.activate_btn.setEnabled(False)
        else:
            self._update_style()
            self.activate_btn.setText("激活")
            self.activate_btn.setEnabled(True)


# ==================== 角色智库面板 ====================

class PersonaSkillPanel(QWidget):
    """
    角色智库主面板

    功能：
    - 角色超市：浏览、搜索、筛选
    - 快捷咨询：输入问题，选择角色，一键咨询
    - 多轮对话：与角色进行连续对话
    - 角色推荐：根据问题自动推荐合适角色
    """

    def __init__(self, engine: Optional[PersonaEngine] = None, parent=None):
        super().__init__(parent)
        self.engine = engine or PersonaEngine()
        self.registry = self.engine.registry
        
        self._current_session_id: Optional[str] = None
        self._chat_history: List[Dict] = []
        
        self._setup_ui()
        self._load_personas()
        self._connect_signals()

    def _setup_ui(self):
        """初始化UI"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ===== 左侧：角色列表 =====
        left_widget = QWidget()
        left_widget.setMaximumWidth(320)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(12, 12, 12, 12)

        # 标题
        title = QLabel("🧙 角色智库")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        left_layout.addWidget(title)

        # 搜索
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索角色...")
        self.search_input.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_input)
        left_layout.addLayout(search_layout)

        # 分类筛选
        filter_layout = QHBoxLayout()
        self.category_combo = QComboBox()
        self.category_combo.addItems(["全部", "销售", "技术", "决策", "管理", "创意", "娱乐"])
        self.category_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(QLabel("类别:"))
        filter_layout.addWidget(self.category_combo)
        left_layout.addLayout(filter_layout)

        # 角色列表（可滚动）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.persona_container = QWidget()
        self.persona_grid = QVBoxLayout(self.persona_container)
        self.persona_grid.setSpacing(12)
        
        scroll.setWidget(self.persona_container)
        left_layout.addWidget(scroll)

        # ===== 中间：对话区域 =====
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(12, 12, 12, 12)

        # 角色状态
        status_layout = QHBoxLayout()
        self.status_icon = QLabel("🤖")
        self.status_icon.setFont(QFont("Segoe UI Emoji", 20))
        self.status_name = QLabel("未选择角色")
        self.status_name.setFont(QFont("Microsoft YaHei", 10))
        status_layout.addWidget(self.status_icon)
        status_layout.addWidget(self.status_name)
        status_layout.addStretch()
        self.switch_btn = QPushButton("切换角色")
        self.switch_btn.setEnabled(False)
        status_layout.addWidget(self.switch_btn)
        center_layout.addLayout(status_layout)

        # 对话历史
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: #fafafa;
                border: 1px solid #e8e8e8;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        center_layout.addWidget(self.chat_display)

        # 推荐提示
        self.recommend_label = QLabel("")
        self.recommend_label.setStyleSheet("""
            background-color: #fff7e6;
            border: 1px solid #ffd591;
            border-radius: 4px;
            padding: 8px;
            font-size: 11px;
            color: #d46b08;
        """)
        center_layout.addWidget(self.recommend_label)

        # 输入区
        input_layout = QVBoxLayout()
        
        self.question_input = QTextEdit()
        self.question_input.setPlaceholderText("输入你的问题...")
        self.question_input.setMaximumHeight(80)
        input_layout.addWidget(self.question_input)

        btn_row = QHBoxLayout()
        self.ask_btn = QPushButton("💬 提问")
        self.ask_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ask_btn.setStyleSheet("""
            QPushButton {
                background-color: #1890ff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #40a9ff;
            }
            QPushButton:disabled {
                background-color: #d9d9d9;
            }
        """)
        
        self.clear_btn = QPushButton("清空")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        btn_row.addWidget(self.ask_btn)
        btn_row.addWidget(self.clear_btn)
        input_layout.addLayout(btn_row)
        
        center_layout.addLayout(input_layout)

        # ===== 右侧：角色详情 =====
        right_widget = QWidget()
        right_widget.setMaximumWidth(280)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(12, 12, 12, 12)

        detail_title = QLabel("📋 角色详情")
        detail_title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        right_layout.addWidget(detail_title)

        self.detail_area = QScrollArea()
        self.detail_area.setWidgetResizable(True)
        self.detail_widget = QWidget()
        self.detail_layout = QVBoxLayout(self.detail_widget)
        self.detail_area.setWidget(self.detail_widget)
        right_layout.addWidget(self.detail_area)

        # 加载默认提示
        default_label = QLabel("选择角色查看详情")
        default_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        default_label.setStyleSheet("color: #999; padding: 40px;")
        self.detail_layout.addWidget(default_label)

        # 组装
        main_layout.addWidget(left_widget)
        main_layout.addWidget(center_widget)
        main_layout.addWidget(right_widget)

        # 设置比例
        main_layout.setStretch(0, 2)  # 左侧
        main_layout.setStretch(1, 3)  # 中间
        main_layout.setStretch(2, 2)  # 右侧

    def _connect_signals(self):
        """连接信号"""
        self.ask_btn.clicked.connect(self._on_ask)
        self.clear_btn.clicked.connect(self._on_clear)
        self.switch_btn.clicked.connect(self._on_switch_persona)

    def _load_personas(self):
        """加载角色列表"""
        # 清空现有
        while self.persona_grid.count():
            item = self.persona_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 获取所有角色
        personas = self.registry.list_all()
        
        for persona in personas:
            card = PersonaCard(persona)
            card.activated.connect(self._on_persona_activated)
            card.consulted.connect(self._on_persona_consulted)
            self.persona_grid.addWidget(card)

    def _on_search(self, text: str):
        """搜索角色"""
        for i in range(self.persona_grid.count()):
            widget = self.persona_grid.itemAt(i).widget()
            if isinstance(widget, PersonaCard):
                visible = not text or (
                    text.lower() in widget.persona.name.lower() or
                    text.lower() in widget.persona.description.lower()
                )
                widget.setVisible(visible)

    def _on_filter_changed(self, index: int):
        """分类筛选"""
        category_map = {
            0: None,  # 全部
            1: PersonaCategory.SALES,
            2: PersonaCategory.TECHNICAL,
            3: PersonaCategory.DECISION,
            4: PersonaCategory.MANAGEMENT,
            5: PersonaCategory.CREATIVE,
            6: PersonaCategory.ENTERTAINMENT,
        }
        selected = category_map.get(index)
        
        for i in range(self.persona_grid.count()):
            widget = self.persona_grid.itemAt(i).widget()
            if isinstance(widget, PersonaCard):
                visible = not selected or widget.persona.category == selected
                widget.setVisible(visible)

    def _on_persona_activated(self, persona_id: str):
        """角色激活"""
        self.registry.activate(persona_id)
        self.engine.switch_persona(persona_id)
        
        # 更新卡片状态
        for i in range(self.persona_grid.count()):
            widget = self.persona_grid.itemAt(i).widget()
            if isinstance(widget, PersonaCard):
                widget.set_activated(widget.persona.id == persona_id)
        
        # 更新状态栏
        persona = self.registry.get(persona_id)
        if persona:
            self.status_icon.setText(persona.icon)
            self.status_name.setText(persona.name)
            self.switch_btn.setEnabled(True)
        
        self._append_system_msg(f"已激活角色: {persona.name if persona else persona_id}")

    def _on_persona_consulted(self, persona_id: str):
        """快捷咨询"""
        self._on_persona_activated(persona_id)
        self.question_input.setFocus()

    def _on_ask(self):
        """提问"""
        question = self.question_input.toPlainText().strip()
        if not question:
            return
        
        # 检查是否选择了角色
        active = self.registry.get_active()
        if not active:
            self._append_system_msg("请先选择一个角色！")
            return
        
        # 添加用户消息
        self._append_user_msg(question)
        self.question_input.clear()
        
        # 禁用按钮
        self.ask_btn.setEnabled(False)
        self.ask_btn.setText("思考中...")
        
        # 异步调用
        asyncio.create_task(self._do_ask(question))

    async def _do_ask(self, question: str):
        """执行提问"""
        try:
            result = await self.engine.invoke(
                task=question,
                session_id=self._current_session_id
            )
            
            if result.success:
                self._append_ai_msg(result.response, result.persona_name)
            else:
                self._append_system_msg(f"调用失败: {result.error}")
        
        finally:
            # 恢复按钮
            self.ask_btn.setEnabled(True)
            self.ask_btn.setText("💬 提问")

    def _on_clear(self):
        """清空对话"""
        self.chat_display.clear()
        self._chat_history.clear()
        self._current_session_id = self.registry.create_session()

    def _on_switch_persona(self):
        """切换角色"""
        # 简化为重新创建会话
        self._current_session_id = self.registry.create_session()
        self._append_system_msg("已创建新对话会话")

    def _append_user_msg(self, text: str):
        """添加用户消息"""
        self._chat_history.append({"role": "user", "content": text})
        self.chat_display.append(f"""
            <div style='text-align: right; margin: 8px 0;'>
                <span style='background-color: #1890ff; color: white; 
                           padding: 8px 12px; border-radius: 12px 12px 0 12px;
                           display: inline-block; max-width: 80%;'>
                    {text}
                </span>
            </div>
        """)
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )

    def _append_ai_msg(self, text: str, persona_name: str):
        """添加AI消息"""
        self._chat_history.append({"role": "assistant", "content": text})
        self.chat_display.append(f"""
            <div style='text-align: left; margin: 8px 0;'>
                <span style='color: #666; font-size: 10px; display: block; margin-bottom: 4px;'>
                    {persona_name}
                </span>
                <span style='background-color: #f1f1f1; color: #333;
                           padding: 8px 12px; border-radius: 12px 12px 12px 0;
                           display: inline-block; max-width: 80%;'>
                    {text.replace(chr(10), '<br>')}
                </span>
            </div>
        """)
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )

    def _append_system_msg(self, text: str):
        """添加系统消息"""
        self.chat_display.append(f"""
            <div style='text-align: center; margin: 8px 0;'>
                <span style='color: #999; font-size: 11px;'>
                    {text}
                </span>
            </div>
        """)

    def show_persona_detail(self, persona: PersonaSkill):
        """显示角色详情"""
        # 清空现有
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 名称和图标
        header = QHBoxLayout()
        icon = QLabel(persona.icon)
        icon.setFont(QFont("Segoe UI Emoji", 32))
        name_label = QLabel(persona.name)
        name_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        header.addWidget(icon)
        header.addWidget(name_label)
        header.addStretch()
        self.detail_layout.addLayout(header)

        # 描述
        desc = QLabel(persona.description)
        desc.setWordWrap(True)
        self.detail_layout.addWidget(desc)

        # 信息组
        info_group = QGroupBox("基本信息")
        info_layout = QVBoxLayout()
        info_layout.addWidget(QLabel(f"类别: {persona.category.value}"))
        info_layout.addWidget(QLabel(f"等级: {persona.tier.value}"))
        info_layout.addWidget(QLabel(f"Star: {persona.star:,}"))
        info_layout.addWidget(QLabel(f"使用次数: {persona.usage_count}"))
        if persona.author:
            info_layout.addWidget(QLabel(f"作者: {persona.author}"))
        info_group.setLayout(info_layout)
        self.detail_layout.addWidget(info_group)

        # 标签
        tags_group = QGroupBox("标签")
        tags_layout = QHBoxLayout()
        for tag in persona.tags:
            tag_label = QLabel(f"#{tag}")
            tag_label.setStyleSheet("background-color: #e8f4fd; color: #1890ff; "
                                    "border-radius: 4px; padding: 4px 8px;")
            tags_layout.addWidget(tag_label)
        tags_layout.addStretch()
        tags_group.setLayout(tags_layout)
        self.detail_layout.addWidget(tags_group)

        # 系统提示词预览
        prompt_group = QGroupBox("系统提示词")
        prompt_layout = QVBoxLayout()
        prompt_preview = QTextEdit()
        prompt_preview.setReadOnly(True)
        prompt_preview.setMaximumHeight(150)
        prompt_preview.setText(persona.system_prompt[:500] + ("..." if len(persona.system_prompt) > 500 else ""))
        prompt_layout.addWidget(prompt_preview)
        prompt_group.setLayout(prompt_layout)
        self.detail_layout.addWidget(prompt_group)

        # 触发词
        if persona.triggers:
            trigger_group = QGroupBox("触发关键词")
            trigger_layout = QVBoxLayout()
            for trigger in persona.triggers[:3]:
                kw_label = QLabel(", ".join(trigger.keywords))
                kw_label.setStyleSheet("color: #666;")
                trigger_layout.addWidget(kw_label)
            trigger_group.setLayout(trigger_layout)
            self.detail_layout.addWidget(trigger_group)

        self.detail_layout.addStretch()


# ==================== 面板工厂 ====================

def create_persona_skill_panel(parent=None) -> PersonaSkillPanel:
    """创建角色智库面板"""
    return PersonaSkillPanel(parent=parent)
