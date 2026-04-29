"""
企业智能协同系统UI面板 (Enterprise Intelligent Collaboration Panel)
================================================================

提供企业模式切换、组织架构管理、团队协作等功能界面
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QPushButton, QLabel, QStackedWidget, QListWidget,
                             QListWidgetItem, QTextEdit, QLineEdit, QComboBox,
                             QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView,
                             QFormLayout, QGroupBox, QSplitter, QCalendarWidget,
                             QProgressBar, QDialog, QDialogButtonBox, QCheckBox,
                             QDateEdit, QTimeEdit, QSlider, QScrollArea, QFrame)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QDate, QTime
from PyQt6.QtGui import QFont, QIcon, QAction, QPainter, QPen, QColor, QBrush, QPalette
from PyQt6.QtChart import QChart, QChartView, QPieSeries, QBarSeries, QBarSet, QLineSeries, QCategoryAxis
from typing import Optional, Callable, List, Dict, Any
from datetime import datetime, timedelta
import uuid


class EnterprisePanel(QWidget):
    """企业智能协同系统面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_enterprise = None
        self.current_user = None
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)

        # 顶部标题栏
        header = self._create_header()
        main_layout.addLayout(header)

        # 主内容区 - 标签页
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_overview_tab(), "📊 总览")
        self.tabs.addTab(self._create_org_tab(), "🏢 组织")
        self.tabs.addTab(self._create_team_tab(), "👥 团队")
        self.tabs.addTab(self._create_collab_tab(), "🤝 协作")
        self.tabs.addTab(self._create_knowledge_tab(), "📚 知识")
        self.tabs.addTab(self._create_ai_tab(), "🤖 AI助手")

        main_layout.addWidget(self.tabs)

    def _create_header(self) -> QHBoxLayout:
        """创建顶部标题栏"""
        header = QHBoxLayout()

        title = QLabel("🏢 企业智能协同系统")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        header.addWidget(title)

        header.addStretch()

        # 企业切换器
        self.enterprise_combo = QComboBox()
        self.enterprise_combo.addItems(["选择企业...", "示例科技有限公司", "创新实验部"])
        header.addWidget(QLabel("当前企业:"))
        header.addWidget(self.enterprise_combo)

        # 用户信息
        user_btn = QPushButton("👤 张经理")
        user_btn.setFlat(True)
        header.addWidget(user_btn)

        return header

    def _create_overview_tab(self) -> QWidget:
        """创建总览标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 企业健康度仪表
        health_group = QGroupBox("🏥 企业健康度")
        health_layout = QHBoxLayout()

        self.health_score = self._create_gauge(85, "综合健康度")
        health_layout.addWidget(self.health_score)

        dimensions = [
            ("财务健康", 90),
            ("运营效率", 82),
            ("组织活力", 88),
            ("创新能力", 75)
        ]

        for name, score in dimensions:
            gauge = self._create_gauge(score, name)
            health_layout.addWidget(gauge)

        health_group.setLayout(health_layout)
        layout.addWidget(health_group)

        # 快捷统计
        stats_group = QGroupBox("📈 关键指标")
        stats_layout = QHBoxLayout()

        self.stat_cards = {}
        stats_data = [
            ("👥 员工总数", "248", "+12本月"),
            ("📁 活跃项目", "36", "8个新增"),
            ("💬 今日消息", "1,284", "↑15%"),
            ("📋 待审批项", "8", "3个紧急"),
            ("🏆 完成率", "94%", "↑3%")
        ]

        for title, value, change in stats_data:
            card = self._create_stat_card(title, value, change)
            self.stat_cards[title] = card
            stats_layout.addWidget(card)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # 最近活动
        activity_group = QGroupBox("🕐 最近活动")
        activity_layout = QVBoxLayout()

        activities = [
            ("李四加入了前端开发团队", "2分钟前"),
            ("王五提交了项目审批申请", "15分钟前"),
            ("「智能路由」项目完成阶段评审", "1小时前"),
            ("张总发布了月度战略公告", "2小时前"),
            ("新员工培训课程已上线", "3小时前")
        ]

        for activity, time in activities:
            activity_layout.addWidget(
                self._create_activity_item(activity, time)
            )

        activity_group.setLayout(activity_layout)
        layout.addWidget(activity_group)

        layout.addStretch()
        return widget

    def _create_org_tab(self) -> QWidget:
        """创建组织架构标签页"""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # 左侧：组织架构树
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)

        left_panel.setFrameStyle(QFrame.Shape.StyledPanel)
        left_layout.addWidget(QLabel("🏛️ 组织架构"))

        self.org_tree = QListWidget()
        org_items = [
            ("🏢 示例科技", [
                ("📊 管理层", ["张总 (CEO)", "李总 (CFO)", "王总 (CTO)"]),
                ("📱 产品研发部", [
                    ("🖥️ 前端团队", ["前端工程师 A", "前端工程师 B"]),
                    ("⚙️ 后端团队", ["后端工程师 A", "后端工程师 B"]),
                ]),
                ("📈 市场运营部", [
                    ("📢 市场团队", ["市场专员 A"]),
                    ("📣 运营团队", ["运营专员 A"]),
                ]),
                ("👔 人力资源部", ["HR 经理", "HR 专员"]),
            ])
        ]

        self._populate_org_tree(self.org_tree, org_items)
        left_layout.addWidget(self.org_tree)

        # 组织操作按钮
        org_btn_layout = QHBoxLayout()
        org_btn_layout.addWidget(QPushButton("🔄 刷新"))
        org_btn_layout.addWidget(QPushButton("➕ 添加部门"))
        org_btn_layout.addWidget(QPushButton("✏️ 编辑"))
        left_layout.addLayout(org_btn_layout)

        # 右侧：组织详情
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_panel.setFrameStyle(QFrame.Shape.StyledPanel)

        right_layout.addWidget(QLabel("📋 部门详情"))

        # 部门信息表单
        dept_form = QFormLayout()
        dept_form.addRow("部门名称:", QLineEdit("产品研发部"))
        dept_form.addRow("部门负责人:", QLineEdit("王总 (CTO)"))
        dept_form.addRow("员工数量:", QLabel("86人"))
        dept_form.addRow("成立时间:", QLabel("2020-01-15"))
        dept_form.addRow("KPI完成率:", QLabel("92%"))

        right_layout.addLayout(dept_form)

        right_layout.addWidget(QLabel("👥 成员列表"))
        member_table = QTableWidget(5, 3)
        member_table.setHorizontalHeaderLabels(["姓名", "职位", "状态"])
        members = [
            ("工程师 A", "高级前端", "🟢 在线"),
            ("工程师 B", "中级前端", "🟡 离开"),
            ("工程师 C", "初级前端", "🟢 在线"),
            ("工程师 D", "高级前端", "🔴 离线"),
            ("工程师 E", "中级前端", "🟢 在线"),
        ]
        for i, (name, role, status) in enumerate(members):
            member_table.setItem(i, 0, QTableWidgetItem(name))
            member_table.setItem(i, 1, QTableWidgetItem(role))
            member_table.setItem(i, 2, QTableWidgetItem(status))
        right_layout.addWidget(member_table)

        layout.addWidget(left_panel, 1)
        layout.addWidget(right_panel, 2)

        return widget

    def _create_team_tab(self) -> QWidget:
        """创建团队管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 团队统计
        stats_layout = QHBoxLayout()

        self.team_stat_cards = {}
        team_stats = [
            ("🚀 活跃项目", "12", "↑3"),
            ("✅ 已完成", "24", "+5本月"),
            ("⏳ 进行中", "8", "3个即将到期"),
            ("📌 待启动", "4", "2个审批中")
        ]

        for title, count, note in team_stats:
            card = self._create_stat_card(title, count, note)
            self.team_stat_cards[title] = card
            stats_layout.addWidget(card)

        layout.addLayout(stats_layout)

        # 项目列表
        self.project_list = QTableWidget(8, 5)
        self.project_list.setHorizontalHeaderLabels(
            ["项目名称", "负责人", "进度", "状态", "截止日期"]
        )

        projects = [
            ("智能路由引擎", "张经理", "████████░░ 80%", "🟢 进行中", "2026-05-01"),
            ("Hermes Desktop", "李工", "██████████ 95%", "🟢 进行中", "2026-04-20"),
            ("企业协同系统", "王总", "██████░░░░ 60%", "🟡 风险", "2026-05-15"),
            ("移动端APP", "赵工", "████░░░░░░ 40%", "🟢 进行中", "2026-06-01"),
            ("数据分析平台", "刘总", "███████░░░ 70%", "🟢 进行中", "2026-05-10"),
            ("AI推理引擎", "陈工", "██░░░░░░░░ 20%", "🟠 延期", "2026-06-15"),
            ("知识图谱", "周工", "██████░░░░ 65%", "🟢 进行中", "2026-05-20"),
            ("安全审计系统", "吴工", "░░░░░░░░░░ 0%", "⚪ 待启动", "2026-07-01"),
        ]

        for i, (name, lead, progress, status, deadline) in enumerate(projects):
            self.project_list.setItem(i, 0, QTableWidgetItem(name))
            self.project_list.setItem(i, 1, QTableWidgetItem(lead))
            self.project_list.setItem(i, 2, QTableWidgetItem(progress))
            self.project_list.setItem(i, 3, QTableWidgetItem(status))
            self.project_list.setItem(i, 4, QTableWidgetItem(deadline))

        self.project_list.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.project_list)

        # 项目操作
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(QPushButton("➕ 新建项目"))
        btn_layout.addWidget(QPushButton("🔍 搜索项目"))
        btn_layout.addWidget(QPushButton("📊 项目分析"))
        btn_layout.addStretch()
        btn_layout.addWidget(QPushButton("🤖 智能组队"))

        layout.addLayout(btn_layout)

        return widget

    def _create_collab_tab(self) -> QWidget:
        """创建协作标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 协作类型选择
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("协作类型:"))

        self.collab_type = QComboBox()
        self.collab_type.addItems([
            "📢 企业公告", "💬 部门讨论", "📁 项目频道", "💡 创意分享"
        ])
        type_layout.addWidget(self.collab_type)
        type_layout.addStretch()

        # 发布内容
        publish_group = QGroupBox("✏️ 发布内容")
        publish_layout = QVBoxLayout()

        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("标题:"))
        title_input = QLineEdit()
        title_input.setPlaceholderText("输入公告标题...")
        title_layout.addWidget(title_input)
        publish_layout.addLayout(title_layout)

        self.publish_content = QTextEdit()
        self.publish_content.setPlaceholderText("输入公告内容...\n\n支持富文本格式")
        self.publish_content.setMaximumHeight(150)
        publish_layout.addWidget(self.publish_content)

        # 发布选项
        options_layout = QHBoxLayout()
        options_layout.addWidget(QLabel("可见范围:"))
        scope_combo = QComboBox()
        scope_combo.addItems(["全公司", "指定部门", "指定团队"])
        options_layout.addWidget(scope_combo)
        options_layout.addWidget(QLabel("优先级:"))
        priority_combo = QComboBox()
        priority_combo.addItems(["📔 普通", "🔔 高", "🚨 紧急"])
        options_layout.addWidget(priority_combo)
        options_layout.addStretch()

        publish_layout.addLayout(options_layout)

        # 发布按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(QPushButton("📎 附件"))
        btn_row.addWidget(QPushButton("⏰ 定时发布"))
        publish_btn = QPushButton("🚀 立即发布")
        publish_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px 16px;")
        btn_row.addWidget(publish_btn)
        publish_layout.addLayout(btn_row)

        publish_group.setLayout(publish_layout)
        layout.addWidget(publish_group)

        # 协作消息流
        feed_group = QGroupBox("📰 最新动态")
        feed_layout = QVBoxLayout()

        feeds = [
            ("张总", "发布了", "月度战略公告", "2小时前", "🏢 全公司"),
            ("李经理", "发起了", "「产品需求」审批", "3小时前", "📋 待审批"),
            ("前端团队", "更新了", "项目进度报告", "5小时前", "💬 部门"),
            ("王工", "分享了", "技术调研报告", "昨天", "💡 创意"),
        ]

        for author, action, content, time, tag in feeds:
            feed_layout.addWidget(
                self._create_feed_item(author, action, content, time, tag)
            )

        feed_group.setLayout(feed_layout)
        layout.addWidget(feed_group)

        return widget

    def _create_knowledge_tab(self) -> QWidget:
        """创建知识库标签页"""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # 左侧：知识分类
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setFrameStyle(QFrame.Shape.StyledPanel)

        left_layout.addWidget(QLabel("📚 知识分类"))

        categories = [
            ("📋 企业制度", 45),
            ("📖 流程规范", 32),
            ("💼 项目文档", 128),
            ("👥 人员知识", 56),
            ("🔧 技术分享", 78),
            ("💡 创意库", 23)
        ]

        self.category_list = QListWidget()
        for name, count in categories:
            item = QListWidgetItem(f"{name} ({count})")
            self.category_list.addItem(item)
        left_layout.addWidget(self.category_list)

        left_layout.addWidget(QPushButton("🔍 搜索知识库"))

        # 右侧：知识内容
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_panel.setFrameStyle(QFrame.Shape.StyledPanel)

        right_layout.addWidget(QLabel("📄 知识条目详情"))

        # 知识图谱可视化
        chart_group = QGroupBox("🕸️ 知识图谱")
        chart_layout = QVBoxLayout()

        # 简单的知识网络可视化
        self.kg_view = QLabel("""
        <svg width="400" height="300">
            <circle cx="200" cy="150" r="30" fill="#4CAF50"/>
            <text x="200" y="155" text-anchor="middle" fill="white">AI</text>

            <circle cx="100" cy="80" r="20" fill="#2196F3"/>
            <text x="100" y="85" text-anchor="middle" fill="white">前端</text>

            <circle cx="300" cy="80" r="20" fill="#2196F3"/>
            <text x="300" y="85" text-anchor="middle" fill="white">后端</text>

            <circle cx="100" cy="220" r="20" fill="#FF9800"/>
            <text x="100" y="225" text-anchor="middle" fill="white">产品</text>

            <circle cx="300" cy="220" r="20" fill="#FF9800"/>
            <text x="300" y="225" text-anchor="middle" fill="white">运营</text>

            <line x1="170" y1="140" x2="120" y2="100" stroke="#999" stroke-width="2"/>
            <line x1="230" y1="140" x2="280" y2="100" stroke="#999" stroke-width="2"/>
            <line x1="170" y1="160" x2="120" y2="200" stroke="#999" stroke-width="2"/>
            <line x1="230" y1="160" x2="280" y2="200" stroke="#999" stroke-width="2"/>
        </svg>
        """)
        self.kg_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chart_layout.addWidget(self.kg_view)

        chart_group.setLayout(chart_layout)
        right_layout.addWidget(chart_group)

        # 专家推荐
        expert_group = QGroupBox("🌟 相关专家")
        expert_layout = QHBoxLayout()

        experts = [
            ("张工", "AI专家", "98%匹配"),
            ("李工", "前端专家", "85%匹配"),
            ("王工", "架构师", "82%匹配"),
        ]

        for name, title, match in experts:
            expert_card = QFrame()
            expert_card.setFrameStyle(QFrame.Shape.StyledPanel)
            expert_layout_inner = QVBoxLayout(expert_card)
            expert_layout_inner.addWidget(QLabel(f"👤 {name}"))
            expert_layout_inner.addWidget(QLabel(title))
            expert_layout_inner.addWidget(QLabel(match))
            expert_layout.addWidget(expert_card)

        expert_group.setLayout(expert_layout)
        right_layout.addWidget(expert_group)

        layout.addWidget(left_panel, 1)
        layout.addWidget(right_panel, 2)

        return widget

    def _create_ai_tab(self) -> QWidget:
        """创建AI助手标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # AI功能选择
        features_layout = QHBoxLayout()

        ai_features = [
            ("🤖 智能组队", self._show_team_formation),
            ("📊 决策分析", self._show_decision_analysis),
            ("🔮 场景模拟", self._show_scenario_simulation),
            ("📈 趋势预测", self._show_trend_prediction),
        ]

        for name, handler in ai_features:
            btn = QPushButton(name)
            btn.clicked.connect(handler)
            features_layout.addWidget(btn)

        layout.addLayout(features_layout)

        # AI交互区
        ai_group = QGroupBox("💬 AI智能助手")
        ai_layout = QVBoxLayout()

        self.ai_chat = QTextEdit()
        self.ai_chat.setReadOnly(True)
        self.ai_chat.setMaximumHeight(200)
        self.ai_chat.append("""
        <div style="background: #E3F2FD; padding: 10px; border-radius: 5px;">
        <b>🤖 AI助手:</b><br>
        您好！我是企业智能助手。我可以帮您：<br>
        • 分析团队协作效率<br>
        • 推荐项目组成员<br>
        • 模拟企业决策场景<br>
        • 预测业务发展趋势<br><br>
        请选择上方功能或直接输入您的问题。
        </div>
        """)
        ai_layout.addWidget(self.ai_chat)

        # AI输入
        input_layout = QHBoxLayout()
        self.ai_input = QLineEdit()
        self.ai_input.setPlaceholderText("输入您的问题...")
        input_layout.addWidget(self.ai_input)

        ask_btn = QPushButton("💬 提问")
        ask_btn.clicked.connect(self._handle_ai_question)
        input_layout.addWidget(ask_btn)

        ai_layout.addLayout(input_layout)

        # AI结果展示
        self.ai_result = QTextEdit()
        self.ai_result.setReadOnly(True)
        ai_layout.addWidget(QLabel("📋 分析结果:"))
        ai_layout.addWidget(self.ai_result)

        ai_group.setLayout(ai_layout)
        layout.addWidget(ai_group)

        layout.addStretch()
        return widget

    # ==================== 辅助方法 ====================

    def _create_gauge(self, value: int, label: str) -> QWidget:
        """创建仪表盘组件"""
        widget = QFrame()
        widget.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(widget)

        gauge = QLabel(f"<span style='font-size: 24px;'>{value}%</span>")
        gauge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(gauge)

        # 简单进度条
        progress = QProgressBar()
        progress.setValue(value)
        progress.setTextVisible(False)
        progress.setMaximumHeight(6)
        layout.addWidget(progress)

        name_label = QLabel(label)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

        return widget

    def _create_stat_card(self, title: str, value: str, note: str) -> QFrame:
        """创建统计卡片"""
        card = QFrame()
        card.setFrameStyle(QFrame.Shape.StyledPanel)
        card_layout = QVBoxLayout(card)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: #666;")
        card_layout.addWidget(title_label)

        value_label = QLabel(f"<span style='font-size: 28px; font-weight: bold;'>{value}</span>")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(value_label)

        note_label = QLabel(note)
        note_label.setStyleSheet("color: #4CAF50;")
        note_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(note_label)

        return card

    def _create_activity_item(self, activity: str, time: str) -> QFrame:
        """创建活动项"""
        item = QFrame()
        item.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(item)

        layout.addWidget(QLabel(f"● {activity}"))
        layout.addStretch()
        layout.addWidget(QLabel(f"<span style='color: #999;'>{time}</span>"))

        return item

    def _create_feed_item(self, author: str, action: str, content: str,
                          time: str, tag: str) -> QFrame:
        """创建动态项"""
        item = QFrame()
        item.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(item)

        avatar = QLabel("👤")
        layout.addWidget(avatar)

        text_layout = QVBoxLayout()
        text_layout.addWidget(QLabel(f"<b>{author}</b> {action} <b>{content}</b>"))
        text_layout.addWidget(QLabel(f"<span style='color: #666;'> {time}</span>"))
        layout.addLayout(text_layout)

        layout.addStretch()

        tag_label = QLabel(tag)
        tag_label.setStyleSheet("background: #E0E0E0; padding: 2px 8px; border-radius: 3px;")
        layout.addWidget(tag_label)

        return item

    def _populate_org_tree(self, tree: QListWidget, items: list, parent=None):
        """填充组织树"""
        for item_data in items:
            if len(item_data) == 2:
                name, children = item_data
                root_item = QListWidgetItem(name)
                root_item.setData(Qt.ItemDataRole.UserRole, {"expanded": False})
                tree.addItem(root_item)

                if parent is None:
                    self._add_org_children(tree, root_item, children)
            else:
                name = item_data[0] if isinstance(item_data[0], str) else item_data[0]
                tree.addItem(name)

    def _add_org_children(self, tree: QListWidget, parent_item: QListWidgetItem, children: list):
        """添加组织树子节点"""
        for child in children:
            if isinstance(child, tuple):
                name, sub_children = child
                child_item = QListWidgetItem(f"  {name}")
                child_item.setData(Qt.ItemDataRole.UserRole, {"parent": parent_item})
                tree.addItem(child_item)

                if isinstance(sub_children, list):
                    self._add_org_children(tree, child_item, sub_children)
            else:
                child_item = QListWidgetItem(f"  {child}")
                child_item.setData(Qt.ItemDataRole.UserRole, {"parent": parent_item})
                tree.addItem(child_item)

    # ==================== AI功能处理 ====================

    def _show_team_formation(self):
        """显示智能组队"""
        self.ai_result.setHtml("""
        <h3>🤖 智能组队建议</h3>
        <p><b>项目：</b>企业数据分析平台</p>
        <p><b>需求技能：</b></p>
        <ul>
            <li>Python数据分析 (2人)</li>
            <li>前端可视化 (1人)</li>
            <li>数据库优化 (1人)</li>
            <li>项目经理 (1人)</li>
        </ul>
        <p><b>推荐团队：</b></p>
        <table border="1" cellpadding="5">
            <tr><th>角色</th><th>推荐人员</th><th>匹配度</th></tr>
            <tr><td>项目经理</td><td>张经理</td><td>95%</td></tr>
            <tr><td>Python开发</td><td>李工、王工</td><td>92%</td></tr>
            <tr><td>前端开发</td><td>赵工</td><td>88%</td></tr>
            <tr><td>数据库</td><td>陈工</td><td>85%</td></tr>
        </table>
        """)

    def _show_decision_analysis(self):
        """显示决策分析"""
        self.ai_result.setHtml("""
        <h3>📊 决策分析报告</h3>
        <p><b>决策：</b>是否上线新的协作功能模块</p>

        <h4>✅ 支持因素：</h4>
        <ul>
            <li>用户调研显示83%需要此功能</li>
            <li>竞争对手已上线类似功能</li>
            <li>预计增加20%用户留存</li>
        </ul>

        <h4>⚠️ 风险因素：</h4>
        <ul>
            <li>开发周期紧张（预计8周）</li>
            <li>需要额外2名开发人员</li>
            <li>可能影响现有功能稳定性</li>
        </ul>

        <h4>💡 建议：</h4>
        <p>建议分阶段上线：先上线核心功能MVP，收集用户反馈后再完善。</p>
        """)

    def _show_scenario_simulation(self):
        """显示场景模拟"""
        self.ai_result.setHtml("""
        <h3>🔮 场景模拟结果</h3>
        <p><b>场景：</b>公司扩张至30%规模后的运营状态</p>

        <h4>📈 预测指标（6个月后）：</h4>
        <table border="1" cellpadding="5">
            <tr><th>指标</th><th>当前</th><th>预测</th><th>变化</th></tr>
            <tr><td>营收</td><td>1000万</td><td>1300万</td><td style="color:green">+30%</td></tr>
            <tr><td>成本</td><td>600万</td><td>780万</td><td style="color:red">+30%</td></tr>
            <tr><td>利润率</td><td>40%</td><td>40%</td><td>持平</td></tr>
            <tr><td>员工满意度</td><td>85%</td><td>78%</td><td style="color:red">-7%</td></tr>
        </table>

        <h4>⚠️ 需关注风险：</h4>
        <ul>
            <li>员工满意度可能下降，需要加强文化建设</li>
            <li>管理复杂度提升，建议增设中层管理岗位</li>
        </ul>
        """)

    def _show_trend_prediction(self):
        """显示趋势预测"""
        self.ai_result.setHtml("""
        <h3>📈 业务趋势预测</h3>

        <h4>🔮 未来3个月预测：</h4>
        <p>基于历史数据和当前增长趋势：</p>

        <ul>
            <li><b>用户增长：</b>预计增长25%（从1万到1.25万）</li>
            <li><b>活跃度：</b>预计提升15%</li>
            <li><b>付费转化：</b>预计从3%提升到3.5%</li>
            <li><b>客户满意度：</b>预计维持在90%以上</li>
        </ul>

        <h4>💡 优化建议：</h4>
        <ul>
            <li>加强用户引导，提升新用户激活率</li>
            <li>优化付费流程，降低转化流失</li>
            <li>增加社区运营，提升用户粘性</li>
        </ul>
        """)

    def _handle_ai_question(self):
        """处理AI问题"""
        question = self.ai_input.text().strip()
        if not question:
            return

        self.ai_chat.append(f"""
        <div style="background: #E8F5E9; padding: 10px; border-radius: 5px; margin-top: 5px;">
        <b>👤 您:</b> {question}
        </div>
        """)

        # 模拟AI响应
        self.ai_chat.append("""
        <div style="background: #E3F2FD; padding: 10px; border-radius: 5px; margin-top: 5px;">
        <b>🤖 AI助手:</b><br>
        正在分析您的问题...
        </div>
        """)

        self.ai_input.clear()


def create_enterprise_panel() -> EnterprisePanel:
    """创建企业面板"""
    return EnterprisePanel()