# -*- coding: utf-8 -*-
"""
🎮 挂机积分与等级粘性增强系统 UI 面板
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QGroupBox, QLineEdit, QProgressBar, QFrame,
                             QGridLayout, QScrollArea, QBadge)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QPainter, QLinearGradient, QBrush


class IdleGradePanel(QWidget):
    """挂机积分与等级系统面板"""

    TAB_LABELS = [
        ("🏠", "我的主页"),
        ("⏳", "挂机收益"),
        ("🎮", "小游戏"),
        ("🏆", "成就"),
        ("📋", "挑战"),
        ("📊", "排行榜"),
        ("🎁", "每日奖励"),
        ("🐱", "我的宠物")
    ]

    def __init__(self, system=None, parent=None):
        super().__init__(parent)
        self.system = system
        self.current_user = "user_default"
        self.init_ui()

        # 刷新定时器
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(30000)

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 标题栏
        header = self._create_header()
        layout.addWidget(header)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        tabs = [
            self._create_home_tab(),
            self._create_idle_tab(),
            self._create_games_tab(),
            self._create_achievement_tab(),
            self._create_challenge_tab(),
            self._create_leaderboard_tab(),
            self._create_daily_reward_tab(),
            self._create_pet_tab()
        ]

        for i, (emoji, title) in enumerate(self.TAB_LABELS):
            self.tabs.addTab(tabs[i], f"{emoji} {title}")

        layout.addWidget(self.tabs)

    def _create_header(self) -> QWidget:
        """创建标题栏"""
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 8px;
                padding: 15px;
            }
        """)

        layout = QHBoxLayout(header)

        # 等级徽章
        self.badge_label = QLabel("🐣")
        self.badge_label.setStyleSheet("font-size: 40px;")
        layout.addWidget(self.badge_label)

        # 用户信息
        info_layout = QVBoxLayout()
        self.level_label = QLabel("萌新 Lv.1")
        self.level_label.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")

        self.credits_label = QLabel("积分: 0")
        self.credits_label.setStyleSheet("color: #FFD700; font-size: 16px;")

        info_layout.addWidget(self.level_label)
        info_layout.addWidget(self.credits_label)
        layout.addLayout(info_layout)

        layout.addStretch()

        # 每日签到按钮
        self.signin_btn = QPushButton("🎁 每日签到")
        self.signin_btn.setStyleSheet("""
            QPushButton {
                background: #F59E0B;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #D97706;
            }
        """)
        self.signin_btn.clicked.connect(self.on_signin)
        layout.addWidget(self.signin_btn)

        return header

    def _create_home_tab(self) -> QWidget:
        """我的主页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 等级进度卡片
        level_card = self._create_level_card()
        layout.addWidget(level_card)

        # 快速入口
        quick_layout = QGridLayout()

        quick_items = [
            ("⏳", "挂机收益", "10/分"),
            ("🎮", "小游戏", "4个"),
            ("🏆", "成就", "5个"),
            ("📊", "排行榜", "第88名"),
            ("🎁", "签到", "+100"),
            ("🐱", "宠物", "Lv.3")
        ]

        for i, (emoji, name, value) in enumerate(quick_items):
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background: #f8fafc;
                    border-radius: 8px;
                    padding: 15px;
                }
            """)
            card_layout = QVBoxLayout(card)
            card_layout.addWidget(QLabel(emoji))
            card_layout.addWidget(QLabel(name))
            val_label = QLabel(value)
            val_label.setStyleSheet("color: #667eea; font-weight: bold;")
            card_layout.addWidget(val_label)

            quick_layout.addWidget(card, i // 3, i % 3)

        layout.addLayout(quick_layout)

        return widget

    def _create_level_card(self) -> QFrame:
        """等级卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #11998e, stop:1 #38ef7d);
                border-radius: 12px;
                padding: 20px;
            }
        """)

        layout = QVBoxLayout(card)

        # 等级信息
        top_layout = QHBoxLayout()

        self.level_badge = QLabel("🐣 Lv.1")
        self.level_badge.setStyleSheet("color: white; font-size: 28px; font-weight: bold;")
        top_layout.addWidget(self.level_badge)

        top_layout.addStretch()

        self.level_name = QLabel("萌新")
        self.level_name.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 18px;")
        top_layout.addWidget(self.level_name)

        layout.addLayout(top_layout)

        # 进度条
        self.level_progress = QProgressBar()
        self.level_progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid white;
                border-radius: 5px;
                height: 20px;
                text-align: center;
                background: rgba(255,255,255,0.3);
            }
            QProgressBar::chunk {
                background: white;
                border-radius: 3px;
            }
        """)
        self.level_progress.setValue(35)
        layout.addWidget(self.level_progress)

        # 下一级信息
        next_layout = QHBoxLayout()
        next_layout.addWidget(QLabel("距离下一级还需:"))
        self.next_credits = QLabel("1,000 积分")
        self.next_credits.setStyleSheet("color: #FFD700; font-weight: bold;")
        next_layout.addWidget(self.next_credits)
        next_layout.addStretch()

        self.next_level_name = QLabel("见习")
        self.next_level_name.setStyleSheet("color: white;")
        next_layout.addWidget(self.next_level_name)

        layout.addLayout(next_layout)

        return card

    def _create_idle_tab(self) -> QWidget:
        """挂机收益"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 今日收益概览
        overview_card = QFrame()
        overview_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #f093fb, stop:1 #f5576c);
                border-radius: 12px;
                padding: 20px;
            }
        """)

        overview_layout = QHBoxLayout(overview_card)

        overview_items = [
            ("今日收益", "2,580"),
            ("挂机上限", "3,000"),
            ("剩余额度", "420")
        ]

        for title, value in overview_items:
            item_layout = QVBoxLayout()
            item_layout.addWidget(QLabel(title))
            val_label = QLabel(value)
            val_label.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
            item_layout.addWidget(val_label)
            overview_layout.addLayout(item_layout)

        overview_layout.addStretch()

        layout.addWidget(overview_card)

        # 收益明细
        detail_group = QGroupBox("📊 收益明细")
        detail_layout = QVBoxLayout()

        details = [
            ("在线时长", "120分钟", "+60"),
            ("网络贡献", "中继节点", "+30"),
            ("设备能力", "高配设备", "+25"),
            ("社交参与", "5个好友", "+15"),
            ("资产财富", "10000积分", "+10")
        ]

        for item, value, reward in details:
            row = QHBoxLayout()
            row.addWidget(QLabel(item))
            row.addWidget(QLabel(value))
            reward_label = QLabel(reward)
            reward_label.setStyleSheet("color: #4ade80; font-weight: bold;")
            row.addWidget(reward_label)
            detail_layout.addLayout(row)

        detail_group.setLayout(detail_layout)
        layout.addWidget(detail_group)

        # 活跃加成器
        multiplier_group = QGroupBox("⚡ 活跃加成器")
        multiplier_layout = QHBoxLayout()

        multipliers = [
            ("🎉 活动加成", "1.2x"),
            ("💎 VIP加成", "1.5x"),
            ("🤖 设备加成", "1.1x")
        ]

        for name, mult in multipliers:
            chip = QLabel(f"{name} {mult}")
            chip.setStyleSheet("""
                QLabel {
                    background: #fef3c7;
                    padding: 8px 12px;
                    border-radius: 15px;
                    color: #92400e;
                }
            """)
            multiplier_layout.addWidget(chip)

        multiplier_layout.addStretch()
        multiplier_group.setLayout(multiplier_layout)
        layout.addWidget(multiplier_group)

        return widget

    def _create_games_tab(self) -> QWidget:
        """小游戏"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 小游戏列表
        games_group = QGroupBox("🎮 我的小游戏")
        games_layout = QVBoxLayout()

        games = [
            ("⛏️", "数据挖矿", "Lv.3", "今日收益: 156", True),
            ("🌾", "节点耕作", "Lv.5", "今日收益: 320", True),
            ("🤖", "AI训练场", "Lv.2", "今日收益: 89", False),
            ("📚", "知识收割", "Lv.1", "今日收益: 45", True)
        ]

        for emoji, name, level,收益, active in games:
            game_card = QFrame()
            game_card.setStyleSheet("""
                QFrame {
                    background: #f8fafc;
                    border-radius: 8px;
                    padding: 12px;
                }
            """)

            game_layout = QHBoxLayout(game_card)

            game_layout.addWidget(QLabel(emoji))
            game_layout.addWidget(QLabel(name))

            lvl_label = QLabel(level)
            lvl_label.setStyleSheet("background: #667eea; color: white; padding: 2px 8px; border-radius: 10px;")
            game_layout.addWidget(lvl_label)

            game_layout.addWidget(QLabel(收益))

            if active:
                status = QLabel("● 运行中")
                status.setStyleSheet("color: #4ade80;")
            else:
                status = QLabel("○ 已暂停")
                status.setStyleSheet("color: #9ca3af;")

            game_layout.addWidget(status)

            upgrade_btn = QPushButton("升级")
            upgrade_btn.setFixedWidth(60)
            game_layout.addWidget(upgrade_btn)

            games_layout.addWidget(game_card)

        games_group.setLayout(games_layout)
        layout.addWidget(games_group)

        return widget

    def _create_achievement_tab(self) -> QWidget:
        """成就"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 成就概览
        overview = QHBoxLayout()

        overview.addWidget(QLabel("🏆 已解锁成就"))
        overview.addWidget(QLabel("8/15"))
        overview.addStretch()

        layout.addLayout(overview)

        # 成就列表
        achievements_group = QGroupBox("🎖️ 成就列表")
        achievements_layout = QVBoxLayout()

        achievements = [
            ("🚀", "快速学习者", "7天内达到熟练等级", True, "1000"),
            ("⏳", "挂机大师", "连续挂机30天", False, "5000"),
            ("🌐", "网络支柱", "节点在线超1000小时", True, "10000"),
            ("💰", "积分大亨", "拥有100万积分", False, "50000"),
            ("👑", "等级传奇", "达到传奇等级", False, "100000"),
            ("🦋", "社交蝴蝶", "拥有超过50个好友", True, "2000")
        ]

        for emoji, name, desc, unlocked, reward in achievements:
            achieve_card = QFrame()
            if unlocked:
                achieve_card.setStyleSheet("""
                    QFrame {
                        background: #fef3c7;
                        border-radius: 8px;
                        padding: 10px;
                    }
                """)
            else:
                achieve_card.setStyleSheet("""
                    QFrame {
                        background: #f3f4f6;
                        border-radius: 8px;
                        padding: 10px;
                        opacity: 0.6;
                    }
                """)

            achieve_layout = QHBoxLayout(achieve_card)

            badge = QLabel(emoji)
            badge.setStyleSheet("font-size: 24px;")
            achieve_layout.addWidget(badge)

            info_layout = QVBoxLayout()
            name_label = QLabel(name)
            name_label.setStyleSheet("font-weight: bold;")
            info_layout.addWidget(name_label)
            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: #6b7280; font-size: 12px;")
            info_layout.addWidget(desc_label)
            achieve_layout.addLayout(info_layout)

            achieve_layout.addStretch()

            reward_label = QLabel(f"+{reward}")
            reward_label.setStyleSheet("color: #667eea; font-weight: bold;")
            achieve_layout.addWidget(reward_label)

            achievements_layout.addWidget(achieve_card)

        achievements_group.setLayout(achievements_layout)
        layout.addWidget(achievements_group)

        return widget

    def _create_challenge_tab(self) -> QWidget:
        """挑战"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 每周挑战
        challenge_group = QGroupBox("📋 进行中的挑战")
        challenge_layout = QVBoxLayout()

        challenges = [
            {
                "name": "每周挑战",
                "progress": 65,
                "tasks": [("赚取5000积分", "3200/5000"), ("完成10笔交易", "6/10")]
            },
            {
                "name": "社交挑战",
                "progress": 40,
                "tasks": [("添加10个好友", "4/10"), ("加入3个群组", "1/3")]
            }
        ]

        for challenge in challenges:
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                    padding: 15px;
                }
            """)
            card_layout = QVBoxLayout(card)

            # 标题和进度
            header_layout = QHBoxLayout()
            header_layout.addWidget(QLabel(challenge["name"]))

            progress = QProgressBar()
            progress.setValue(challenge["progress"])
            progress.setTextVisible(True)
            header_layout.addWidget(progress)

            card_layout.addLayout(header_layout)

            # 任务列表
            for task_name, task_progress in challenge["tasks"]:
                task_layout = QHBoxLayout()
                task_layout.addWidget(QLabel(f"○ {task_name}"))
                task_layout.addWidget(QLabel(task_progress))
                task_layout.addStretch()
                card_layout.addLayout(task_layout)

            layout.addWidget(card)

        challenge_group.setLayout(challenge_layout)
        layout.addWidget(challenge_group)

        return widget

    def _create_leaderboard_tab(self) -> QWidget:
        """排行榜"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 切换标签
        tabs_layout = QHBoxLayout()

        for scope in ["全球", "好友", "本周"]:
            btn = QPushButton(scope)
            btn.setCheckable(True)
            if scope == "全球":
                btn.setChecked(True)
            tabs_layout.addWidget(btn)

        tabs_layout.addStretch()
        layout.addLayout(tabs_layout)

        # 排行榜
        leaderboard_group = QGroupBox("📊 排行榜")
        leaderboard_layout = QVBoxLayout()

        leaders = [
            ("🥇", "AI大师", "Lv.8", "1,250,000"),
            ("🥈", "数据侠", "Lv.7", "980,000"),
            ("🥉", "代码狂", "Lv.7", "875,000"),
            ("#4", "算法师", "Lv.6", "756,000"),
            ("#5", "网络王", "Lv.6", "698,000"),
            ("#6", "创意家", "Lv.5", "520,000"),
            ("#7", "你", "Lv.3", "25,000"),
        ]

        for rank, name, level, credits in leaders:
            row = QFrame()
            if "你" in name:
                row.setStyleSheet("background: #eef2ff; border-radius: 5px; padding: 8px;")
            else:
                row.setStyleSheet("padding: 8px;")

            row_layout = QHBoxLayout(row)

            rank_label = QLabel(rank)
            rank_label.setStyleSheet("font-size: 16px; min-width: 30px;")
            row_layout.addWidget(rank_label)

            name_label = QLabel(name)
            name_label.setStyleSheet("font-weight: bold; min-width: 80px;")
            row_layout.addWidget(name_label)

            level_label = QLabel(level)
            level_label.setStyleSheet("color: #667eea;")
            row_layout.addWidget(level_label)

            row_layout.addStretch()

            credits_label = QLabel(credits)
            credits_label.setStyleSheet("color: #F59E0B; font-weight: bold;")
            row_layout.addWidget(credits_label)

            leaderboard_layout.addWidget(row)

        leaderboard_group.setLayout(leaderboard_layout)
        layout.addWidget(leaderboard_group)

        return widget

    def _create_daily_reward_tab(self) -> QWidget:
        """每日奖励"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 签到卡片
        signin_card = QFrame()
        signin_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #F59E0B, stop:1 #F97316);
                border-radius: 12px;
                padding: 25px;
            }
        """)

        signin_layout = QVBoxLayout(signin_card)

        signin_layout.addWidget(QLabel("🎁 每日签到"))
        signin_layout.addWidget(QLabel("连续签到 7 天"))

        # 签到日历
        calendar_layout = QHBoxLayout()
        days = ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5", "Day 6", "Day 7"]
        for i, day in enumerate(days):
            day_widget = QVBoxLayout()
            if i < 3:
                check = QLabel("✓")
                check.setStyleSheet("color: #4ade80; font-size: 20px;")
            elif i == 3:
                check = QLabel("★")
                check.setStyleSheet("color: #FFD700; font-size: 20px;")
            else:
                check = QLabel("○")
                check.setStyleSheet("color: white; font-size: 20px;")

            day_widget.addWidget(check)
            day_widget.addWidget(QLabel(day))
            calendar_layout.addLayout(day_widget)

        signin_layout.addLayout(calendar_layout)

        signin_btn = QPushButton("🎁 立即签到领取 100 积分")
        signin_btn.setStyleSheet("""
            QPushButton {
                background: white;
                color: #F59E0B;
                border: none;
                padding: 12px 24px;
                border-radius: 25px;
                font-weight: bold;
                font-size: 16px;
            }
        """)
        signin_layout.addWidget(signin_btn)

        layout.addWidget(signin_card)

        # 奖励日程
        reward_group = QGroupBox("📅 连续签到奖励")
        reward_layout = QVBoxLayout()

        milestones = [
            ("Day 1", "🎁", "100", True),
            ("Day 3", "🎁🎁", "300", True),
            ("Day 7", "🏆", "1000", False),
            ("Day 14", "🏆🏆", "2500", False),
            ("Day 30", "👑", "10000", False)
        ]

        for day, badge, reward, unlocked in milestones:
            row = QHBoxLayout()
            if unlocked:
                row.addWidget(QLabel(f"✓ {day}"))
            else:
                row.addWidget(QLabel(f"○ {day}"))

            row.addWidget(QLabel(badge))
            row.addWidget(QLabel(f"+{reward}"))
            row.addStretch()
            reward_layout.addLayout(row)

        reward_group.setLayout(reward_layout)
        layout.addWidget(reward_group)

        return widget

    def _create_pet_tab(self) -> QWidget:
        """我的宠物"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 宠物卡片
        pet_card = QFrame()
        pet_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #a18cd1, stop:1 #fbc2eb);
                border-radius: 12px;
                padding: 20px;
            }
        """)

        pet_layout = QVBoxLayout(pet_card)

        # 宠物信息
        top_layout = QHBoxLayout()

        pet_emoji = QLabel("🐱")
        pet_emoji.setStyleSheet("font-size: 60px;")
        top_layout.addWidget(pet_emoji)

        info_layout = QVBoxLayout()
        name_label = QLabel("小可爱")
        name_label.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        info_layout.addWidget(name_label)

        level_label = QLabel("Lv.3  电子猫")
        level_label.setStyleSheet("color: rgba(255,255,255,0.9);")
        info_layout.addWidget(level_label)

        top_layout.addLayout(info_layout)
        top_layout.addStretch()

        pet_layout.addLayout(top_layout)

        # 属性
        stats_layout = QHBoxLayout()

        stats = [
            ("⏱️ 收集速度", "1.3x"),
            ("💫 挂机加成", "1.1x"),
            ("🎯 技能", "自动收集")
        ]

        for label, value in stats:
            stat_layout = QVBoxLayout()
            stat_layout.addWidget(QLabel(label))
            val_label = QLabel(value)
            val_label.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
            stat_layout.addWidget(val_label)
            stats_layout.addLayout(stat_layout)

        pet_layout.addLayout(stats_layout)

        # 收集按钮
        collect_btn = QPushButton("🐱 让宠物收集积分")
        collect_btn.setStyleSheet("""
            QPushButton {
                background: white;
                color: #a18cd1;
                border: none;
                padding: 10px 20px;
                border-radius: 20px;
                font-weight: bold;
            }
        """)
        pet_layout.addWidget(collect_btn)

        layout.addWidget(pet_card)

        # 宠物升级
        upgrade_group = QGroupBox("⬆️ 宠物升级")
        upgrade_layout = QVBoxLayout()

        upgrade_info = QLabel("升级到 Lv.4 需要: 500 积分")
        upgrade_layout.addWidget(upgrade_info)

        upgrade_btn = QPushButton("升级宠物")
        upgrade_layout.addWidget(upgrade_btn)

        upgrade_group.setLayout(upgrade_layout)
        layout.addWidget(upgrade_group)

        return widget

    def on_signin(self):
        """签到"""
        print("执行签到...")

    def refresh_data(self):
        """刷新数据"""
        print("刷新面板数据...")
