"""
技能抽屉组件 (ToolboxDrawerWidget)

Lobe 风格的右侧技能/工具抽屉
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QGroupBox, QLabel, QCheckBox, QPushButton,
    QFrame, QSwitch, QComboBox, QSpinBox,
    QListWidget, QListWidgetItem, QWidget,
    QGridLayout, QSlider, QProgressBar
)
from PyQt6.QtGui import QFont

from .lobe_models import (
    SkillBinding, SkillCategory, SKILL_PRESETS, SessionType
)


class SkillToggle(QWidget):
    """技能开关组件"""

    # 信号：技能启用/禁用时触发
    toggled = pyqtSignal(bool)

    def __init__(self, binding: SkillBinding, parent=None):
        super().__init__(parent)
        self.binding = binding
        self._setup_ui()

    def _setup_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 技能名称和图标
        header_layout = QHBoxLayout()

        icon_label = QLabel(self.binding.icon)
        icon_label.setFont(QFont("Microsoft YaHei", 14))
        header_layout.addWidget(icon_label)

        name_label = QLabel(self.binding.name)
        name_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Medium))
        header_layout.addWidget(name_label, stretch=1)

        # 开关
        self.switch = QSwitch()
        self.switch.setChecked(self.binding.enabled)
        self.switch.setMaximumWidth(44)
        self.switch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.switch.toggled.connect(self._on_toggled)
        header_layout.addWidget(self.switch)

        layout.addLayout(header_layout)

        # 描述
        desc_label = QLabel(self.binding.description)
        desc_label.setFont(QFont("Microsoft YaHei", 8))
        desc_label.setStyleSheet("color: #888;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background: #e0e0e0;")
        layout.addWidget(line)

    def _on_toggled(self, checked: bool):
        """开关切换"""
        self.binding.enabled = checked
        self.toggled.emit(checked)

        # 视觉反馈
        if checked:
            self.setStyleSheet("""
                SkillToggle {
                    background: #e3f2fd;
                    border-radius: 8px;
                    padding: 4px;
                }
            """)
        else:
            self.setStyleSheet("")

    def isChecked(self) -> bool:
        """是否启用"""
        return self.switch.isChecked()

    def setChecked(self, checked: bool):
        """设置启用状态"""
        self.switch.setChecked(checked)


class ToolboxDrawerWidget(QScrollArea):
    """
    技能抽屉组件

    功能：
    - 按类别展示技能开关
    - 动态绑定后端配置
    - 实时状态反馈
    """

    # 信号
    skill_changed = pyqtSignal(str, bool)  # skill_id, enabled

    def __init__(self, parent=None):
        super().__init__(parent)
        self._skill_widgets: dict[str, SkillToggle] = {}
        self._setup_ui()

    def _setup_ui(self):
        """初始化UI"""
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("""
            QScrollArea {
                border: none;
                background: #fafafa;
            }
        """)

        # 容器
        container = QWidget()
        container.setMinimumWidth(260)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        # 标题
        title = QLabel("🧰 技能超市")
        title.setFont(QFont("Microsoft YaHei", 13, QFont.Weight.Bold))
        layout.addWidget(title)

        # 当前会话信息
        self.session_label = QLabel("当前：电商咨询")
        self.session_label.setFont(QFont("Microsoft YaHei", 9))
        self.session_label.setStyleSheet("color: #666;")
        layout.addWidget(self.session_label)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background: #e0e0e0;")
        layout.addWidget(line)

        # ==================== 搜索与联网 ====================
        search_group = QGroupBox("🔍 搜索与联网")
        search_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 8px;
                padding: 8px;
                background: #fff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)
        search_layout = QVBoxLayout()
        search_layout.setSpacing(8)

        self._add_skill_widgets([
            SKILL_PRESETS.get("agent_reach"),
            SKILL_PRESETS.get("p2p_proxy"),
        ], search_layout)

        search_group.setLayout(search_layout)
        layout.addWidget(search_group)

        # ==================== AI 模型路由 ====================
        ai_group = QGroupBox("🧠 AI 模型路由")
        ai_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 8px;
                padding: 8px;
                background: #fff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)
        ai_layout = QVBoxLayout()
        ai_layout.setSpacing(8)

        self._add_skill_widgets([
            SKILL_PRESETS.get("smollm2_router"),
            SKILL_PRESETS.get("deepseek"),
        ], ai_layout)

        ai_group.setLayout(ai_layout)
        layout.addWidget(ai_group)

        # ==================== 角色技能 ====================
        persona_group = QGroupBox("🎭 角色技能")
        persona_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 8px;
                padding: 8px;
                background: #fff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)
        persona_layout = QVBoxLayout()
        persona_layout.setSpacing(8)

        self._add_skill_widgets([
            SKILL_PRESETS.get("colleague_sales"),
            SKILL_PRESETS.get("colleague_architect"),
            SKILL_PRESETS.get("jobs"),
            SKILL_PRESETS.get("musk"),
            SKILL_PRESETS.get("naval"),
        ], persona_layout)

        persona_group.setLayout(persona_layout)
        layout.addWidget(persona_group)

        # ==================== 记忆与知识 ====================
        memory_group = QGroupBox("🏛️ 记忆与知识")
        memory_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 8px;
                padding: 8px;
                background: #fff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)
        memory_layout = QVBoxLayout()
        memory_layout.setSpacing(8)

        self._add_skill_widgets([
            SKILL_PRESETS.get("memory_palace"),
            SKILL_PRESETS.get("fusion_rag"),
        ], memory_layout)

        memory_group.setLayout(memory_layout)
        layout.addWidget(memory_group)

        # ==================== 工具能力 ====================
        tool_group = QGroupBox("🔧 工具能力")
        tool_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 8px;
                padding: 8px;
                background: #fff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)
        tool_layout = QVBoxLayout()
        tool_layout.setSpacing(8)

        self._add_skill_widgets([
            SKILL_PRESETS.get("persona_skill"),
        ], tool_layout)

        tool_group.setLayout(tool_layout)
        layout.addWidget(tool_group)

        # ==================== 活跃技能列表 ====================
        active_group = QGroupBox("✅ 当前激活")
        active_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 8px;
                padding: 8px;
                background: #fff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)
        active_layout = QVBoxLayout()

        self.active_skills_list = QListWidget()
        self.active_skills_list.setStyleSheet("""
            QListWidget {
                border: none;
                background: transparent;
            }
        """)
        active_layout.addWidget(self.active_skills_list)

        active_group.setLayout(active_layout)
        layout.addWidget(active_group)

        layout.addStretch()

        self.setWidget(container)

    def _add_skill_widgets(self, skills: list, layout):
        """添加技能组件到布局"""
        for skill in skills:
            if skill is None:
                continue
            toggle = SkillToggle(skill)
            toggle.toggled.connect(lambda checked, sid=skill.skill_id: self._on_skill_toggled(sid, checked))
            self._skill_widgets[skill.skill_id] = toggle
            layout.addWidget(toggle)

    def _on_skill_toggled(self, skill_id: str, enabled: bool):
        """技能开关切换"""
        self.skill_changed.emit(skill_id, enabled)
        self._update_active_skills_list()

    def _update_active_skills_list(self):
        """更新活跃技能列表"""
        self.active_skills_list.clear()

        for skill_id, toggle in self._skill_widgets.items():
            if toggle.isChecked():
                binding = toggle.binding
                icon = binding.icon
                name = binding.name
                self.active_skills_list.addItem(f"{icon} {name}")

    def set_session_type(self, session_type: SessionType):
        """设置会话类型，自动启用相关技能"""
        # 根据会话类型预设技能
        preset_skills = {
            SessionType.TRADE: ["colleague_sales", "memory_palace"],
            SessionType.CODE: ["colleague_architect", "smollm2_router"],
            SessionType.SEARCH: ["agent_reach", "p2p_proxy"],
            SessionType.RAG: ["fusion_rag", "memory_palace"],
            SessionType.PERSONA: ["persona_skill"],
            SessionType.CUSTOM: [],
        }

        default_skills = preset_skills.get(session_type, [])

        # 更新会话标签
        session_names = {
            SessionType.TRADE: "电商咨询",
            SessionType.CODE: "代码助手",
            SessionType.SEARCH: "全网搜索",
            SessionType.RAG: "文档库",
            SessionType.PERSONA: "角色对话",
            SessionType.CUSTOM: "自定义",
        }
        self.session_label.setText(f"当前：{session_names.get(session_type, '未知')}")

        # 启用默认技能
        for skill_id in default_skills:
            if skill_id in self._skill_widgets:
                self._skill_widgets[skill_id].setChecked(True)

        self._update_active_skills_list()

    def get_enabled_skills(self) -> list[str]:
        """获取所有启用的技能ID"""
        return [
            skill_id for skill_id, toggle in self._skill_widgets.items()
            if toggle.isChecked()
        ]

    def get_enabled_skill_configs(self) -> dict:
        """获取启用的技能配置"""
        configs = {}
        for skill_id, toggle in self._skill_widgets.items():
            if toggle.isChecked():
                binding = toggle.binding
                configs.update(binding.config_keys)
        return configs

    def enable_skill(self, skill_id: str):
        """启用技能"""
        if skill_id in self._skill_widgets:
            self._skill_widgets[skill_id].setChecked(True)

    def disable_skill(self, skill_id: str):
        """禁用技能"""
        if skill_id in self._skill_widgets:
            self._skill_widgets[skill_id].setChecked(False)

    def is_skill_enabled(self, skill_id: str) -> bool:
        """检查技能是否启用"""
        if skill_id in self._skill_widgets:
            return self._skill_widgets[skill_id].isChecked()
        return False
