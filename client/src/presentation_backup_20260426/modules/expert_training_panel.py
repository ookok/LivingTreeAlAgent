"""
专家训练模块面板
"""

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton,
    QTextEdit, QScrollArea, QFrame,
    QComboBox, QProgressBar,
    QRadioButton, QButtonGroup,
    QListWidget, QListWidgetItem,
)
from PyQt6.QtGui import QFont


class ExpertTrainingPanel(QWidget):
    """专家训练面板"""
    
    train_requested = pyqtSignal(str, str)  # expert_id, mode
    adopt_answer = pyqtSignal(str)  # question_id
    correct_answer = pyqtSignal(str, str)  # question_id, corrected_answer
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_mode = "qa"
        self._current_expert = None
        self._experts = []  # {id, name, accuracy, trained, total}
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            ExpertTrainingPanel {
                background: #0D0D0D;
            }
            QLabel {
                color: #FFFFFF;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton {
                background: #252525;
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                padding: 8px 16px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #333333;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # 标题
        title = QLabel("🎓 专家训练")
        title.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #00D4AA;
        """)
        layout.addWidget(title)
        
        # 训练模式选择
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(12)
        
        mode_label = QLabel("训练模式:")
        mode_label.setStyleSheet("color: #A0A0A0;")
        mode_layout.addWidget(mode_label)
        
        self.mode_group = QButtonGroup()
        
        modes = [
            ("📝 问答模式", "qa"),
            ("💬 对话模式", "chat"),
            ("📊 评估模式", "eval"),
        ]
        
        for name, mode_id in modes:
            btn = QRadioButton(name)
            btn.setChecked(mode_id == "qa")
            btn.clicked.connect(lambda c, m=mode_id: self._on_mode_change(m))
            self.mode_group.addButton(btn)
            mode_layout.addWidget(btn)
        
        mode_layout.addStretch()
        layout.addLayout(mode_layout)
        
        # 专家选择
        expert_layout = QHBoxLayout()
        
        expert_label = QLabel("当前专家:")
        expert_label.setStyleSheet("color: #A0A0A0;")
        expert_layout.addWidget(expert_label)
        
        self.expert_combo = QComboBox()
        self.expert_combo.setMinimumWidth(200)
        self.expert_combo.setStyleSheet("""
            QComboBox {
                background: #1A1A1A;
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 8px 12px;
                color: #FFFFFF;
            }
        """)
        self.expert_combo.currentIndexChanged.connect(self._on_expert_change)
        expert_layout.addWidget(self.expert_combo)
        
        expert_layout.addStretch()
        
        new_expert_btn = QPushButton("➕ 新建专家")
        new_expert_btn.setStyleSheet("""
            QPushButton {
                background: #7C3AED;
                color: #FFFFFF;
            }
            QPushButton:hover {
                background: #8B5CF6;
            }
        """)
        new_expert_btn.clicked.connect(self._on_new_expert)
        expert_layout.addWidget(new_expert_btn)
        
        layout.addLayout(expert_layout)
        
        # 训练区域
        training_area = QFrame()
        training_area.setStyleSheet("""
            QFrame {
                background: #1A1A1A;
                border-radius: 12px;
            }
        """)
        training_layout = QVBoxLayout(training_area)
        training_layout.setContentsMargins(20, 20, 20, 20)
        training_layout.setSpacing(20)
        
        # 问题卡片
        self.question_card = QFrame()
        self.question_card.setStyleSheet("""
            QFrame {
                background: #252525;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        q_layout = QVBoxLayout(self.question_card)
        q_layout.setSpacing(12)
        
        q_header = QLabel("❓ 用户问题")
        q_header.setStyleSheet("color: #00D4AA; font-weight: bold;")
        q_layout.addWidget(q_header)
        
        self.question_text = QLabel("选择一个专家开始训练...")
        self.question_text.setStyleSheet("""
            color: #FFFFFF;
            font-size: 15px;
            line-height: 1.6;
        """)
        self.question_text.setWordWrap(True)
        q_layout.addWidget(self.question_text)
        
        training_layout.addWidget(self.question_card)
        
        # 专家回答
        self.expert_card = QFrame()
        self.expert_card.setStyleSheet("""
            QFrame {
                background: #252525;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        e_layout = QVBoxLayout(self.expert_card)
        e_layout.setSpacing(12)
        
        e_header = QLabel("🎓 专家回答")
        e_header.setStyleSheet("color: #7C3AED; font-weight: bold;")
        e_layout.addWidget(e_header)
        
        self.expert_text = QLabel("")
        self.expert_text.setStyleSheet("""
            color: #A0A0A0;
            font-size: 14px;
            line-height: 1.6;
        """)
        self.expert_text.setWordWrap(True)
        e_layout.addWidget(self.expert_text)
        
        training_layout.addWidget(self.expert_card)
        
        # 你的回答（待修正）
        self.user_card = QFrame()
        self.user_card.setStyleSheet("""
            QFrame {
                background: #252525;
                border: 1px dashed #666666;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        u_layout = QVBoxLayout(self.user_card)
        u_layout.setSpacing(12)
        
        u_header = QLabel("✏️ 你的回答 (待修正)")
        u_header.setStyleSheet("color: #FFD700; font-weight: bold;")
        u_layout.addWidget(u_header)
        
        self.user_text = QLabel("")
        self.user_text.setStyleSheet("""
            color: #A0A0A0;
            font-size: 14px;
            line-height: 1.6;
        """)
        self.user_text.setWordWrap(True)
        u_layout.addWidget(self.user_text)
        
        training_layout.addWidget(self.user_card)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        adopt_btn = QPushButton("✓ 采纳")
        adopt_btn.setStyleSheet("""
            QPushButton {
                background: #00D4AA;
                color: #0D0D0D;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #00E8BB;
            }
        """)
        adopt_btn.clicked.connect(self._on_adopt)
        btn_layout.addWidget(adopt_btn)
        
        correct_btn = QPushButton("✏️ 修正")
        correct_btn.setStyleSheet("""
            QPushButton {
                background: #FFD700;
                color: #0D0D0D;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #FFE44D;
            }
        """)
        correct_btn.clicked.connect(self._on_correct)
        btn_layout.addWidget(correct_btn)
        
        skip_btn = QPushButton("⏭️ 跳过")
        skip_btn.clicked.connect(self._on_skip)
        btn_layout.addWidget(skip_btn)
        
        btn_layout.addStretch()
        
        training_layout.addLayout(btn_layout)
        layout.addWidget(training_area, 1)
        
        # 进度条
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(8)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(80)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #252525;
                border: none;
                border-radius: 6px;
                height: 12px;
                text-align: center;
                color: #FFFFFF;
            }
            QProgressBar::chunk {
                background: #00D4AA;
                border-radius: 6px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(24)
        
        self.accuracy_label = QLabel("准确率: 92.5%")
        self.accuracy_label.setStyleSheet("color: #00D4AA; font-size: 14px;")
        stats_layout.addWidget(self.accuracy_label)
        
        self.trained_label = QLabel("已训练: 156/200")
        self.trained_label.setStyleSheet("color: #A0A0A0; font-size: 14px;")
        stats_layout.addWidget(self.trained_label)
        
        stats_layout.addStretch()
        progress_layout.addLayout(stats_layout)
        
        layout.addLayout(progress_layout)
    
    def _on_mode_change(self, mode: str):
        self._current_mode = mode
    
    def _on_expert_change(self, index: int):
        if index >= 0 and index < len(self._experts):
            self._current_expert = self._experts[index]
    
    def _on_new_expert(self):
        pass  # TODO: 新建专家
    
    def _on_adopt(self):
        pass  # TODO: 采纳回答
    
    def _on_correct(self):
        pass  # TODO: 修正回答
    
    def _on_skip(self):
        pass  # TODO: 跳过
    
    def set_experts(self, experts: list):
        """设置专家列表"""
        self._experts = experts
        self.expert_combo.clear()
        for expert in experts:
            self.expert_combo.addItem(f"{expert['name']} ({expert['accuracy']}%)")
    
    def show_training_item(self, question: str, expert_answer: str, user_answer: str):
        """显示训练项"""
        self.question_text.setText(question)
        self.expert_text.setText(expert_answer)
        self.user_text.setText(user_answer)
    
    def update_progress(self, trained: int, total: int, accuracy: float):
        """更新进度"""
        progress = int(trained / total * 100) if total > 0 else 0
        self.progress_bar.setValue(progress)
        self.accuracy_label.setText(f"准确率: {accuracy:.1f}%")
        self.trained_label.setText(f"已训练: {trained}/{total}")


__all__ = ["ExpertTrainingPanel"]
