"""
需求头脑风暴面板
IdeaClarifierPanel - PyQt6 UI for brainstorming workflow

核心设计：
1. HARD-GATE - 禁止在用户批准设计前执行任何实现
2. 一次一问 - 减少认知负担
3. 多选优先 - 提供选项而非开放问题
4. 逐段展示 - 每段获取用户批准
"""

from typing import Optional, Dict, Any, List
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTextEdit, QLineEdit, QListWidget, QListWidgetItem,
    QGroupBox, QScrollArea, QFrame, QRadioButton, QButtonGroup,
    QProgressBar, QComboBox, QCheckBox, QTextBrowser,
    QDialog, QDialogButtonBox, QMessageBox, QSplitter,
    QWizard, QWizardPage
)
from PyQt6.QtSvgWidgets import QSvgWidget

from client.src.business.idea_clarifier import (
    get_idea_clarifier, IdeaClarifier, ClarifySession,
    ClarifyPhase, ClarifyQuestion, QuestionType,
    DesignOption, DesignSection
)


class PhaseIndicator(QWidget):
    """阶段指示器 - 显示当前头脑风暴进度"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        
        self.phases = [
            ("💡", "开始"),
            ("🎯", "目的"),
            ("⚙️", "约束"),
            ("✅", "成功"),
            ("💭", "方案"),
            ("📐", "设计"),
            ("👁️", "审核"),
            ("🎉", "完成")
        ]
        
        self.phase_labels = []
        for icon, name in self.phases:
            label = QLabel(f"{icon}\n{name}")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("""
                QLabel {
                    padding: 5px 10px;
                    border-radius: 5px;
                    background: #f0f0f0;
                    color: #999;
                    font-size: 11px;
                }
                QLabel[phase="active"] {
                    background: #3b82f6;
                    color: white;
                }
                QLabel[phase="completed"] {
                    background: #22c55e;
                    color: white;
                }
            """)
            self.phase_labels.append(label)
            layout.addWidget(label)
        
        layout.addStretch()
    
    def set_phase(self, phase: ClarifyPhase):
        """设置当前阶段"""
        phase_order = [
            ClarifyPhase.CONTEXT,
            ClarifyPhase.PURPOSE,
            ClarifyPhase.CONSTRAINTS,
            ClarifyPhase.SUCCESS_CRITERIA,
            ClarifyPhase.ALTERNATIVES,
            ClarifyPhase.DESIGN,
            ClarifyPhase.REVIEW,
            ClarifyPhase.APPROVED
        ]
        
        try:
            current_idx = phase_order.index(phase)
        except ValueError:
            current_idx = 0
        
        for i, label in enumerate(self.phase_labels):
            if i < current_idx:
                label.setProperty("phase", "completed")
                label.style().unpolish(label)
                label.style().polish(label)
            elif i == current_idx:
                label.setProperty("phase", "active")
                label.style().unpolish(label)
                label.style().polish(label)
            else:
                label.setProperty("phase", "")
                label.style().unpolish(label)
                label.style().polish(label)


class QuestionCard(QWidget):
    """问题卡片 - 显示单个问题"""
    
    answered = pyqtSignal(str, object)  # question_id, answer
    
    def __init__(self, question: ClarifyQuestion, parent=None):
        super().__init__(parent)
        self.question = question
        self._init_ui()
    
    def _init_ui(self):
        self.setStyleSheet("""
            QWidget#question_card {
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 15px;
                margin: 5px;
            }
            QLabel#question_text {
                font-size: 14px;
                font-weight: bold;
                color: #1f2937;
            }
            QLabel#hint_text {
                font-size: 12px;
                color: #6b7280;
                font-style: italic;
            }
        """)
        self.setObjectName("question_card")
        
        layout = QVBoxLayout(self)
        
        # 问题文本
        text_label = QLabel(self.question.text)
        text_label.setObjectName("question_text")
        text_label.setWordWrap(True)
        layout.addWidget(text_label)
        
        # 提示
        if self.question.hint:
            hint_label = QLabel(f"💡 {self.question.hint}")
            hint_label.setObjectName("hint_text")
            layout.addWidget(hint_label)
        
        # 问题类型分支
        if self.question.question_type == QuestionType.MULTIPLE_CHOICE:
            self._create_choice_ui(layout)
        elif self.question.question_type == QuestionType.YES_NO:
            self._create_yesno_ui(layout)
        elif self.question.question_type == QuestionType.SCALE:
            self._create_scale_ui(layout)
        else:
            self._create_open_ui(layout)
    
    def _create_choice_ui(self, layout):
        """多选问题UI"""
        self.button_group = QButtonGroup()
        
        for i, option in enumerate(self.question.options):
            btn = QRadioButton(option)
            btn.setStyleSheet("""
                QRadioButton {
                    padding: 8px;
                    font-size: 13px;
                }
                QRadioButton:hover {
                    background: #f3f4f6;
                }
            """)
            self.button_group.addButton(btn, i)
            layout.addWidget(btn)
    
    def _create_yesno_ui(self, layout):
        """是否问题UI"""
        self.button_group = QButtonGroup()
        
        yes_btn = QRadioButton("✅ 是")
        no_btn = QRadioButton("❌ 否")
        
        self.button_group.addButton(yes_btn, 1)
        self.button_group.addButton(no_btn, 0)
        
        layout.addWidget(yes_btn)
        layout.addWidget(no_btn)
    
    def _create_scale_ui(self, layout):
        """量表问题UI"""
        self.combo = QComboBox()
        self.combo.addItems(self.question.options)
        self.combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                font-size: 13px;
                border: 1px solid #d1d5db;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.combo)
    
    def _create_open_ui(self, layout):
        """开放问题UI"""
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("请输入你的回答...")
        self.text_edit.setMaximumHeight(100)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #d1d5db;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
        """)
        layout.addWidget(self.text_edit)
    
    def get_answer(self) -> Any:
        """获取答案"""
        if hasattr(self, 'button_group'):
            selected = self.button_group.checkedButton()
            if selected:
                idx = self.button_group.id(selected)
                return self.question.options[idx] if self.question.options else idx
        elif hasattr(self, 'combo'):
            return self.combo.currentText()
        elif hasattr(self, 'text_edit'):
            return self.text_edit.toPlainText()
        return None
    
    def set_answered(self, answer: Any):
        """设置已回答的答案"""
        if hasattr(self, 'button_group') and isinstance(answer, str):
            for i, option in enumerate(self.question.options):
                if option == answer:
                    btn = self.button_group.button(i)
                    if btn:
                        btn.setChecked(True)
                    break
        elif hasattr(self, 'combo'):
            idx = self.combo.findText(str(answer))
            if idx >= 0:
                self.combo.setCurrentIndex(idx)
        elif hasattr(self, 'text_edit'):
            self.text_edit.setPlainText(str(answer))


class OptionCard(QWidget):
    """方案选项卡片"""
    
    selected = pyqtSignal(str)  # option_id
    
    def __init__(self, option: DesignOption, parent=None):
        super().__init__(parent)
        self.option = option
        self._init_ui()
    
    def _init_ui(self):
        # 背景色
        bg_color = "#fef3c7" if self.option.recommended else "#ffffff"
        border_color = "#f59e0b" if self.option.recommended else "#d1d5db"
        
        self.setStyleSheet(f"""
            QWidget#option_card {{
                background: {bg_color};
                border: 2px solid {border_color};
                border-radius: 8px;
                padding: 15px;
                margin: 5px;
            }}
        """)
        self.setObjectName("option_card")
        
        layout = QVBoxLayout(self)
        
        # 标题行
        title_layout = QHBoxLayout()
        
        name_label = QLabel(f"<h3>{self.option.name}</h3>")
        title_layout.addWidget(name_label)
        
        if self.option.recommended:
            rec_label = QLabel("⭐ 推荐")
            rec_label.setStyleSheet("""
                background: #f59e0b;
                color: white;
                padding: 3px 8px;
                border-radius: 10px;
                font-size: 12px;
            """)
            title_layout.addWidget(rec_label)
        
        title_layout.addStretch()
        
        complexity_label = QLabel(f"复杂度: {self.option.complexity}")
        complexity_colors = {"low": "#22c55e", "medium": "#f59e0b", "high": "#ef4444"}
        complexity_label.setStyleSheet(f"""
            color: {complexity_colors.get(self.option.complexity, '#6b7280')};
            font-weight: bold;
        """)
        title_layout.addWidget(complexity_label)
        
        layout.addLayout(title_layout)
        
        # 描述
        desc_label = QLabel(self.option.description)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # 优缺点
        pros_cons_layout = QHBoxLayout()
        
        pros_group = QGroupBox("✅ 优势")
        pros_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #d1d5db;
                border-radius: 4px;
                margin-top: 5px;
            }
        """)
        pros_layout = QVBoxLayout(pros_group)
        for pro in self.option.pros:
            pros_layout.addWidget(QLabel(f"• {pro}"))
        pros_cons_layout.addWidget(pros_group)
        
        cons_group = QGroupBox("⚠️ 劣势")
        cons_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #d1d5db;
                border-radius: 4px;
                margin-top: 5px;
            }
        """)
        cons_layout = QVBoxLayout(cons_group)
        for con in self.option.cons:
            cons_layout.addWidget(QLabel(f"• {con}"))
        pros_cons_layout.addWidget(cons_group)
        
        layout.addLayout(pros_cons_layout)
        
        # 选择按钮
        select_btn = QPushButton("选择此方案")
        select_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #2563eb;
            }
        """)
        select_btn.clicked.connect(lambda: self.selected.emit(self.option.option_id))
        layout.addWidget(select_btn)


class SectionCard(QWidget):
    """设计段落卡片"""
    
    approved = pyqtSignal(str)  # section_id
    content_changed = pyqtSignal(str, str)  # section_id, content
    
    def __init__(self, section: DesignSection, parent=None):
        super().__init__(parent)
        self.section = section
        self._init_ui()
    
    def _init_ui(self):
        border_color = "#22c55e" if self.section.approved else "#e5e7eb"
        
        self.setStyleSheet(f"""
            QWidget#section_card {{
                background: white;
                border: 2px solid {border_color};
                border-radius: 8px;
                padding: 15px;
                margin: 5px;
            }}
        """)
        self.setObjectName("section_card")
        
        layout = QVBoxLayout(self)
        
        # 标题行
        title_layout = QHBoxLayout()
        
        title_label = QLabel(f"<h3>{self.section.title}</h3>")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        self.status_label = QLabel("⏳ 待审核" if not self.section.approved else "✅ 已批准")
        self.status_label.setStyleSheet("""
            padding: 3px 10px;
            border-radius: 10px;
            font-size: 12px;
        """ + ("background: #22c55e; color: white;" if self.section.approved else "background: #fef3c7; color: #92400e;"))
        title_layout.addWidget(self.status_label)
        
        layout.addLayout(title_layout)
        
        # 内容编辑器
        self.content_edit = QTextEdit()
        self.content_edit.setPlainText(self.section.content)
        self.content_edit.setPlaceholderText("在此编辑设计内容...")
        self.content_edit.setMinimumHeight(150)
        self.content_edit.textChanged.connect(self._on_content_changed)
        self.content_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #d1d5db;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Consolas', monospace;
            }
        """)
        layout.addWidget(self.content_edit)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        if not self.section.approved:
            approve_btn = QPushButton("✅ 批准此段")
            approve_btn.setStyleSheet("""
                QPushButton {
                    background: #22c55e;
                    color: white;
                    border: none;
                    padding: 8px 15px;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background: #16a34a;
                }
            """)
            approve_btn.clicked.connect(lambda: self._approve())
            btn_layout.addWidget(approve_btn)
        else:
            edit_btn = QPushButton("✏️ 编辑")
            edit_btn.setStyleSheet("""
                QPushButton {
                    background: #6b7280;
                    color: white;
                    border: none;
                    padding: 8px 15px;
                    border-radius: 5px;
                }
            """)
            edit_btn.clicked.connect(self._enable_edit)
            btn_layout.addWidget(edit_btn)
        
        layout.addLayout(btn_layout)
    
    def _on_content_changed(self):
        """内容改变"""
        self.content_changed.emit(self.section.section_id, self.content_edit.toPlainText())
    
    def _approve(self):
        """批准"""
        self.section.approved = True
        self.approved.emit(self.section.section_id)
    
    def _enable_edit(self):
        """启用编辑"""
        self.section.approved = False
        self.update_status()
    
    def update_status(self):
        """更新状态显示"""
        border_color = "#22c55e" if self.section.approved else "#e5e7eb"
        self.setStyleSheet(f"""
            QWidget#section_card {{
                background: white;
                border: 2px solid {border_color};
                border-radius: 8px;
                padding: 15px;
                margin: 5px;
            }}
        """)
        
        self.status_label.setText("✅ 已批准" if self.section.approved else "⏳ 待审核")
        self.status_label.setStyleSheet("""
            padding: 3px 10px;
            border-radius: 10px;
            font-size: 12px;
        """ + ("background: #22c55e; color: white;" if self.section.approved else "background: #fef3c7; color: #92400e;"))


class IdeaClarifierPanel(QWidget):
    """
    需求头脑风暴面板主界面
    
    工作流程：
    1. 开始新会话 - 输入主题
    2. 逐步回答问题 - 一次一问
    3. 选择方案 - 查看方案权衡
    4. 审核设计 - 逐段批准
    5. 生成规格 - 导出设计文档
    """
    
    # 信号
    design_approved = pyqtSignal(str)  # session_id - 设计批准后触发
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.clarifier = get_idea_clarifier()
        self.current_session: Optional[ClarifySession] = None
        
        self._init_ui()
        self._update_ui()
    
    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        
        # 顶部：标题和新建按钮
        header_layout = QHBoxLayout()
        
        title_label = QLabel("🎯 需求头脑风暴")
        title_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #1f2937;
        """)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        self.new_session_btn = QPushButton("🆕 新建会话")
        self.new_session_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background: #2563eb;
            }
        """)
        self.new_session_btn.clicked.connect(self._on_new_session)
        header_layout.addWidget(self.new_session_btn)
        
        main_layout.addLayout(header_layout)
        
        # 阶段指示器
        self.phase_indicator = PhaseIndicator()
        main_layout.addWidget(self.phase_indicator)
        
        # HARD-GATE 提示
        self.gate_warning = QLabel("🔒 HARD-GATE: 设计批准前不会执行任何实现")
        self.gate_warning.setStyleSheet("""
            background: #fef3c7;
            color: #92400e;
            padding: 10px;
            border-radius: 5px;
            font-weight: bold;
            text-align: center;
        """)
        self.gate_warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.gate_warning)
        
        # 主内容区域
        self.content_area = QScrollArea()
        self.content_area.setWidgetResizable(True)
        self.content_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
        """)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_area.setWidget(self.content_widget)
        
        main_layout.addWidget(self.content_area, 1)
        
        # 底部操作区
        self.action_layout = QHBoxLayout()
        self.action_layout.addStretch()
        main_layout.addLayout(self.action_layout)
    
    def _on_new_session(self):
        """创建新会话"""
        dialog = NewSessionDialog(self)
        if dialog.exec():
            topic = dialog.get_topic()
            if topic:
                self.current_session = self.clarifier.start_session(topic)
                self._update_ui()
    
    def _update_ui(self):
        """更新UI状态"""
        if not self.current_session:
            self._show_welcome()
            return
        
        self.phase_indicator.set_phase(self.current_session.phase)
        
        phase = self.current_session.phase
        
        # 清空内容
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if widget := item.widget():
                widget.deleteLater()
        
        # 清空操作按钮
        while self.action_layout.count():
            item = self.action_layout.takeAt(0)
            if widget := item.widget():
                widget.deleteLater()
        
        if phase in [ClarifyPhase.CONTEXT, ClarifyPhase.PURPOSE, 
                     ClarifyPhase.CONSTRAINTS, ClarifyPhase.SUCCESS_CRITERIA]:
            self._show_question_phase()
        elif phase == ClarifyPhase.ALTERNATIVES:
            self._show_options_phase()
        elif phase == ClarifyPhase.DESIGN:
            self._show_design_phase()
        elif phase == ClarifyPhase.REVIEW:
            self._show_review_phase()
        elif phase == ClarifyPhase.APPROVED:
            self._show_approved_phase()
    
    def _show_welcome(self):
        """显示欢迎页面"""
        welcome_text = QLabel()
        welcome_text.setText("""
            <div style="text-align: center; padding: 50px;">
                <h2>🎯 欢迎使用需求头脑风暴</h2>
                <p style="font-size: 14px; color: #6b7280;">
                    将你的模糊想法转化为清晰的设计规格<br><br>
                    <b>核心原则：</b><br>
                    🔒 HARD-GATE - 设计批准前不执行任何实现<br>
                    💬 一次一问 - 减少认知负担<br>
                    📋 逐段审核 - 每段获取批准<br>
                    💭 方案权衡 - 提供多种选择<br>
                </p>
                <br>
                <p style="color: #9ca3af;">点击右上角「新建会话」开始</p>
            </div>
        """)
        self.content_layout.addWidget(welcome_text)
    
    def _show_question_phase(self):
        """显示问题阶段"""
        # 显示已回答的问题
        answered_label = QLabel("<h3>📝 已回答</h3>")
        self.content_layout.addWidget(answered_label)
        
        for q in self.current_session.questions:
            if q.answered:
                card = QFrame()
                card.setStyleSheet("""
                    QFrame {
                        background: #f0f9ff;
                        border-left: 3px solid #3b82f6;
                        padding: 10px;
                        margin: 5px;
                    }
                """)
                card_layout = QVBoxLayout(card)
                card_layout.addWidget(QLabel(f"<b>Q:</b> {q.text}"))
                card_layout.addWidget(QLabel(f"<b>A:</b> {q.answer}"))
                self.content_layout.addWidget(card)
        
        # 显示当前问题
        current_q = self.clarifier.get_current_question(self.current_session.session_id)
        if current_q:
            self.content_layout.addWidget(QLabel("<h3>❓ 当前问题</h3>"))
            
            self.question_card = QuestionCard(current_q)
            self.content_layout.addWidget(self.question_card)
            
            # 添加回答按钮
            answer_btn = QPushButton("💬 提交回答")
            answer_btn.setStyleSheet("""
                QPushButton {
                    background: #22c55e;
                    color: white;
                    border: none;
                    padding: 12px 25px;
                    border-radius: 5px;
                    font-weight: bold;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background: #16a34a;
                }
            """)
            answer_btn.clicked.connect(self._on_answer_question)
            self.action_layout.addWidget(answer_btn)
        else:
            # 所有问题已回答
            self.content_layout.addWidget(QLabel("<p style='color: green;'>✅ 所有问题已回答，准备进入下一阶段...</p>"))
    
    def _show_options_phase(self):
        """显示方案选择阶段"""
        self.content_layout.addWidget(QLabel("<h2>💭 请选择实现方案</h2>"))
        self.content_layout.addWidget(QLabel("<p style='color: #6b7280;'>基于你的需求，我准备了以下方案供选择：</p>"))
        
        for option in self.current_session.design_options:
            card = OptionCard(option)
            card.selected.connect(self._on_select_option)
            self.content_layout.addWidget(card)
    
    def _show_design_phase(self):
        """显示设计阶段"""
        self.content_layout.addWidget(QLabel("<h2>📐 设计文档</h2>"))
        
        remaining = [s for s in self.current_session.design_sections if not s.approved]
        if remaining:
            self.content_layout.addWidget(QLabel(f"<p>请逐段审核设计（共 {len(remaining)} 段待审核）</p>"))
        else:
            self.content_layout.addWidget(QLabel("<p style='color: green;'>✅ 所有段落已批准</p>"))
        
        for section in self.current_session.design_sections:
            card = SectionCard(section)
            card.approved.connect(self._on_approve_section)
            card.content_changed.connect(self._on_section_content_changed)
            self.content_layout.addWidget(card)
    
    def _show_review_phase(self):
        """显示审核阶段"""
        self.content_layout.addWidget(QLabel("<h2>👁️ 审核设计规格</h2>"))
        
        # 显示完整设计预览
        preview = QTextBrowser()
        preview.setPlainText(self.clarifier.generate_spec_document(self.current_session.session_id) or "")
        preview.setStyleSheet("""
            QTextBrowser {
                border: 1px solid #d1d5db;
                border-radius: 5px;
                padding: 10px;
                font-family: 'Consolas', monospace;
            }
        """)
        self.content_layout.addWidget(preview)
        
        # 审核按钮
        review_btn = QPushButton("✅ 批准设计并生成规格文档")
        review_btn.setStyleSheet("""
            QPushButton {
                background: #22c55e;
                color: white;
                border: none;
                padding: 15px 30px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #16a34a;
            }
        """)
        review_btn.clicked.connect(self._on_approve_design)
        self.action_layout.addWidget(review_btn)
        
        # 返回编辑按钮
        back_btn = QPushButton("← 返回编辑")
        back_btn.clicked.connect(lambda: self._transition_phase(ClarifyPhase.DESIGN))
        self.action_layout.insertWidget(0, back_btn)
    
    def _show_approved_phase(self):
        """显示已批准阶段"""
        self.gate_warning.setText("🎉 DESIGN APPROVED - 可以开始实现了！")
        self.gate_warning.setStyleSheet("""
            background: #dcfce7;
            color: #166534;
            padding: 10px;
            border-radius: 5px;
            font-weight: bold;
            text-align: center;
        """)
        
        self.content_layout.addWidget(QLabel("<h2>🎉 设计已批准！</h2>"))
        
        # 显示生成的规格文档
        doc = self.clarifier.generate_spec_document(self.current_session.session_id)
        if doc:
            self.content_layout.addWidget(QLabel("<h3>📄 设计规格文档</h3>"))
            
            preview = QTextBrowser()
            preview.setPlainText(doc)
            preview.setStyleSheet("""
                QTextBrowser {
                    border: 1px solid #d1d5db;
                    border-radius: 5px;
                    padding: 10px;
                    font-family: 'Consolas', monospace;
                }
            """)
            self.content_layout.addWidget(preview)
            
            # 下载按钮
            download_btn = QPushButton("📥 下载规格文档")
            download_btn.setStyleSheet("""
                QPushButton {
                    background: #3b82f6;
                    color: white;
                    border: none;
                    padding: 12px 25px;
                    border-radius: 5px;
                    font-weight: bold;
                }
            """)
            download_btn.clicked.connect(self._on_download_spec)
            self.action_layout.addWidget(download_btn)
        
        # 触发设计批准信号
        self.design_approved.emit(self.current_session.session_id)
    
    def _on_answer_question(self):
        """提交问题答案"""
        if not self.question_card:
            return
        
        answer = self.question_card.get_answer()
        if not answer or (isinstance(answer, str) and not answer.strip()):
            QMessageBox.warning(self, "提示", "请先回答问题")
            return
        
        result = self.clarifier.answer_question(
            self.current_session.session_id,
            self.question_card.question.question_id,
            answer
        )
        
        self._update_ui()
    
    def _on_select_option(self, option_id: str):
        """选择方案"""
        result = self.clarifier.select_option(self.current_session.session_id, option_id)
        self._update_ui()
    
    def _on_approve_section(self, section_id: str):
        """批准段落"""
        self.clarifier.approve_section(self.current_session.session_id, section_id)
        self._update_ui()
    
    def _on_section_content_changed(self, section_id: str, content: str):
        """段落内容改变"""
        self.clarifier.update_section(self.current_session.session_id, section_id, content)
    
    def _transition_phase(self, phase: ClarifyPhase):
        """手动切换阶段"""
        self.current_session.phase = phase
        self._update_ui()
    
    def _on_approve_design(self):
        """批准设计"""
        self.clarifier.approve_design(self.current_session.session_id)
        self._update_ui()
    
    def _on_download_spec(self):
        """下载规格文档"""
        doc = self.clarifier.generate_spec_document(self.current_session.session_id)
        if doc:
            from PyQt6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getSaveFileName(
                self, "保存规格文档",
                f"{self.current_session.topic}-design.md",
                "Markdown (*.md)"
            )
            if path:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(doc)
                QMessageBox.information(self, "成功", f"规格文档已保存到:\n{path}")


class NewSessionDialog(QDialog):
    """新建会话对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🆕 新建头脑风暴会话")
        self.setMinimumWidth(500)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # 主题输入
        layout.addWidget(QLabel("<b>你想实现什么功能或解决什么问题？</b>"))
        
        self.topic_input = QTextEdit()
        self.topic_input.setPlaceholderText("例如：我想做一个自动备份文件的功能...")
        self.topic_input.setMinimumHeight(100)
        layout.addWidget(self.topic_input)
        
        # 示例提示
        examples_label = QLabel("""
            <p style="color: #6b7280; font-size: 12px;">
                <b>示例主题：</b><br>
                • "我想让软件自动检测更新并提醒用户"<br>
                • "需要一个项目管理看板来跟踪任务进度"<br>
                • "想要一个智能提醒功能，根据我的习惯自动安排日程"
            </p>
        """)
        layout.addWidget(examples_label)
        
        # 按钮
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)
    
    def get_topic(self) -> str:
        """获取主题"""
        return self.topic_input.toPlainText().strip()
