"""
移动端屏幕组件
==============

Kivy 移动端界面组件

包含:
- ChatScreen: 聊天屏幕
- SkillsScreen: 技能市场屏幕
- SettingsScreen: 设置屏幕
- BottomNav: 底部导航
- GestureNav: 手势导航
"""

import time
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.properties import StringProperty, ListProperty
from kivy.metrics import dp, sp
from kivy.clock import Clock


# ==================== 颜色常量 ====================

class Colors:
    """颜色定义"""
    PRIMARY = "#007acc"
    PRIMARY_DARK = "#005a9e"
    SECONDARY = "#3794ff"
    BACKGROUND = "#1e1e1e"
    SURFACE = "#252526"
    SURFACE_LIGHT = "#2d2d2e"
    TEXT_PRIMARY = "#d4d4d4"
    TEXT_SECONDARY = "#858585"
    SUCCESS = "#4CAF50"
    WARNING = "#ff9800"
    ERROR = "#f44336"
    BORDER = "#3c3c3c"


# ==================== 聊天屏幕 ====================

class ChatScreen(Screen):
    """聊天屏幕"""

    session_id = StringProperty("")
    messages = ListProperty([])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._setup_ui()

    def _setup_ui(self):
        """设置 UI"""
        layout = BoxLayout(orientation="vertical", spacing=0)

        # 顶部栏
        header = BoxLayout(
            size_hint_y=None,
            height=dp(56),
            padding=[dp(16), dp(8)],
            spacing=dp(12)
        )
        header.add_widget(Label(
            text="[b]Hermes[/b]",
            markup=True,
            font_size=sp(18),
            color=Colors.TEXT_PRIMARY
        ))
        header.add_widget(Label(size_hint_x=1))  # 弹性空间
        layout.add_widget(header)

        # 消息列表
        self.message_list = ScrollView(
            size_hint_y=1,
            do_scroll_y=True
        )
        self.message_container = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(8),
            padding=dp(16)
        )
        self.message_list.add_widget(self.message_container)
        layout.add_widget(self.message_list)

        # 输入区域
        input_area = BoxLayout(
            size_hint_y=None,
            height=dp(56),
            padding=[dp(12), dp(8)],
            spacing=dp(8)
        )
        self.message_input = TextInput(
            hint_text="输入消息...",
            multiline=False,
            size_hint_x=1,
            font_size=sp(14),
            background_color=Colors.SURFACE_LIGHT,
            foreground_color=Colors.TEXT_PRIMARY,
            cursor_color=Colors.PRIMARY,
            padding=[dp(12), dp(12)]
        )
        self.message_input.bind(on_text_validate=self._on_send)
        input_area.add_widget(self.message_input)

        send_btn = Button(
            text="发送",
            size_hint_x=None,
            width=dp(64),
            background_color=Colors.PRIMARY,
            color=Colors.TEXT_PRIMARY,
            on_press=lambda x: self._on_send()
        )
        input_area.add_widget(send_btn)
        layout.add_widget(input_area)

        self.add_widget(layout)

    def _on_send(self):
        """发送消息"""
        text = self.message_input.text.strip()
        if not text:
            return

        self.message_input.text = ""
        self.add_message("user", text)

        # 模拟 AI 响应
        Clock.schedule_once(lambda dt: self.add_message("assistant", "思考中..."), 0)

    def add_message(self, role: str, content: str):
        """添加消息"""
        msg_layout = BoxLayout(
            size_hint_y=None,
            size_hint_x=0.8,
            pos_hint={"x": 0.1 if role == "assistant" else 0.1},
            padding=[dp(12), dp(8)],
            spacing=dp(8)
        )

        # 头像
        avatar = Label(
            text="H" if role == "assistant" else "U",
            size_hint_x=None,
            width=dp(32),
            markup=True,
            font_size=sp(14),
            color=Colors.BACKGROUND
        )
        msg_layout.add_widget(avatar)

        # 消息内容
        msg_label = Label(
            text=content,
            size_hint_x=1,
            text_size=(None, None),
            markup=True,
            font_size=sp(14),
            color=Colors.TEXT_PRIMARY,
            halign="left",
            valign="top"
        )
        msg_layout.add_widget(msg_label)

        self.message_container.add_widget(msg_layout)
        self.message_container.height += dp(48)

        # 滚动到底部
        Clock.schedule_once(lambda dt: setattr(
            self.message_list, "scroll_y", 0
        ), 0)


# ==================== 技能市场屏幕 ====================

class SkillsScreen(Screen):
    """技能市场屏幕"""

    categories = ListProperty(["全部", "写作", "编程", "设计", "数据分析"])
    skills = ListProperty([])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._setup_ui()

    def _setup_ui(self):
        """设置 UI"""
        layout = BoxLayout(orientation="vertical", spacing=0)

        # 标题
        header = BoxLayout(
            size_hint_y=None,
            height=dp(56),
            padding=[dp(16), dp(8)]
        )
        header.add_widget(Label(
            text="[b]技能市场[/b]",
            markup=True,
            font_size=sp(18),
            color=Colors.TEXT_PRIMARY
        ))
        layout.add_widget(header)

        # 分类标签
        category_scroll = ScrollView(
            size_hint_y=None,
            height=dp(44),
            do_scroll_x=True,
            do_scroll_y=False
        )
        category_layout = BoxLayout(
            size_hint_x=None,
            spacing=dp(8),
            padding=[dp(16), dp(8)]
        )
        category_layout.width = sum(dp(80) for _ in self.categories) + dp(16)

        for cat in self.categories:
            btn = Button(
                text=cat,
                size_hint_x=None,
                width=dp(80),
                background_color=Colors.PRIMARY if cat == "全部" else Colors.SURFACE_LIGHT,
                color=Colors.TEXT_PRIMARY,
                on_press=lambda x, c=cat: self._on_category_select(c)
            )
            category_layout.add_widget(btn)

        category_scroll.add_widget(category_layout)
        layout.add_widget(category_scroll)

        # 技能网格
        self.skills_grid = ScrollView(size_hint_y=1)
        self.skills_container = GridLayout(
            cols=2,
            size_hint_y=None,
            spacing=dp(12),
            padding=dp(16)
        )
        self.skills_container.bind(minimum_height=self.skills_container.setter("height"))
        self.skills_grid.add_widget(self.skills_container)
        layout.add_widget(self.skills_grid)

        self.add_widget(layout)

    def _on_category_select(self, category: str):
        """选择分类"""
        pass

    def load_skills(self, skills: list):
        """加载技能"""
        self.skills = skills
        self.skills_container.clear_widgets()

        for skill in skills:
            card = self._create_skill_card(skill)
            self.skills_container.add_widget(card)

    def _create_skill_card(self, skill: dict) -> BoxLayout:
        """创建技能卡片"""
        card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(120),
            padding=dp(12),
            spacing=dp(8),
            background_color=Colors.SURFACE_LIGHT,
            radius=[dp(8)]
        )

        # 图标
        icon = Label(
            text=skill.get("icon", "🔧"),
            font_size=sp(24),
            size_hint_y=0.4
        )
        card.add_widget(icon)

        # 名称
        name = Label(
            text=skill.get("name", ""),
            font_size=sp(14),
            color=Colors.TEXT_PRIMARY,
            size_hint_y=0.3
        )
        card.add_widget(name)

        # 描述
        desc = Label(
            text=skill.get("description", "")[:30] + "...",
            font_size=sp(10),
            color=Colors.TEXT_SECONDARY,
            size_hint_y=0.3
        )
        card.add_widget(desc)

        return card


# ==================== 设置屏幕 ====================

class SettingsScreen(Screen):
    """设置屏幕"""

    settings = ListProperty([])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._setup_ui()

    def _setup_ui(self):
        """设置 UI"""
        layout = BoxLayout(orientation="vertical", spacing=0)

        # 标题
        header = BoxLayout(
            size_hint_y=None,
            height=dp(56),
            padding=[dp(16), dp(8)]
        )
        header.add_widget(Label(
            text="[b]设置[/b]",
            markup=True,
            font_size=sp(18),
            color=Colors.TEXT_PRIMARY
        ))
        layout.add_widget(header)

        # 设置列表
        scroll = ScrollView(size_hint_y=1)
        self.settings_container = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(1),
            padding=[0, dp(8)]
        )
        self.settings_container.bind(minimum_height=self.settings_container.setter("height"))
        scroll.add_widget(self.settings_container)
        layout.add_widget(scroll)

        self.add_widget(layout)

    def load_settings(self, settings: list):
        """加载设置"""
        self.settings = settings
        self.settings_container.clear_widgets()

        for section, items in settings:
            # 分组标题
            section_label = Label(
                text=section,
                size_hint_y=None,
                height=dp(32),
                font_size=sp(12),
                color=Colors.TEXT_SECONDARY,
                padding=[dp(16), dp(4)]
            )
            self.settings_container.add_widget(section_label)

            for item in items:
                row = self._create_setting_row(item)
                self.settings_container.add_widget(row)

    def _create_setting_row(self, item: dict) -> BoxLayout:
        """创建设置行"""
        row = BoxLayout(
            size_hint_y=None,
            height=dp(48),
            padding=[dp(16), dp(8)],
            background_color=Colors.SURFACE_LIGHT
        )

        # 图标
        icon = Label(
            text=item.get("icon", "⚙"),
            font_size=sp(16),
            size_hint_x=None,
            width=dp(32),
            color=Colors.TEXT_SECONDARY
        )
        row.add_widget(icon)

        # 标签
        label = Label(
            text=item.get("label", ""),
            font_size=sp(14),
            color=Colors.TEXT_PRIMARY,
            size_hint_x=1
        )
        row.add_widget(label)

        # 值/开关
        if item.get("type") == "switch":
            switch = Button(
                text="OFF" if not item.get("value") else "ON",
                size_hint_x=None,
                width=dp(60),
                background_color=Colors.ERROR if not item.get("value") else Colors.SUCCESS,
                on_press=lambda x, i=item: self._on_switch_toggle(i)
            )
            row.add_widget(switch)
        else:
            value = Label(
                text=str(item.get("value", "")),
                font_size=sp(12),
                color=Colors.TEXT_SECONDARY,
                size_hint_x=None,
                width=dp(80)
            )
            row.add_widget(value)

        return row

    def _on_switch_toggle(self, item: dict):
        """开关切换"""
        pass


# ==================== 底部导航 ====================

class BottomNav(BoxLayout):
    """底部导航栏"""

    current = StringProperty("chat")
    items = ListProperty(["chat", "skills", "settings"])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._setup_ui()

    def _setup_ui(self):
        """设置 UI"""
        self.size_hint_y = None
        self.height = dp(56)
        self.padding = [dp(8), dp(8)]
        self.spacing = dp(8)
        self.background_color = Colors.SURFACE

        self._update_nav()

    def _update_nav(self):
        """更新导航"""
        self.clear_widgets()

        icons = {
            "chat": "💬",
            "skills": "🛠",
            "settings": "⚙"
        }

        labels = {
            "chat": "聊天",
            "skills": "技能",
            "settings": "设置"
        }

        for item in self.items:
            btn = Button(
                text=f"{icons[item]}\n{labels[item]}",
                markup=True,
                font_size=sp(10),
                background_color=Colors.PRIMARY if self.current == item else Colors.SURFACE_LIGHT,
                color=Colors.TEXT_PRIMARY if self.current == item else Colors.TEXT_SECONDARY,
                on_press=lambda x, i=item: self._on_nav_select(i)
            )
            self.add_widget(btn)

    def _on_nav_select(self, item: str):
        """选择导航项"""
        self.current = item
        self._update_nav()

        # 通知屏幕管理器
        if self.parent and hasattr(self.parent, "switch_to"):
            self.parent.switch_to(item)


# ==================== 手势导航 ====================

class GestureNav:
    """
    手势导航

    支持:
    - 滑动手势切换屏幕
    - 双击返回
    - 长按显示菜单
    """

    def __init__(self, screen_manager: ScreenManager):
        self.sm = screen_manager
        self._touch_start = None
        self._touch_start_time = 0
        self._min_swipe_distance = dp(50)
        self._max_swipe_time = 0.5

    def on_touch_down(self, touch):
        """触摸开始"""
        self._touch_start = touch.pos
        self._touch_start_time = time.time()

    def on_touch_up(self, touch):
        """触摸结束"""
        if self._touch_start is None:
            return

        dx = touch.pos[0] - self._touch_start[0]
        dy = touch.pos[1] - self._touch_start[1]
        dt = time.time() - self._touch_start_time

        # 检查是否为滑动手势
        if dt < self._max_swipe_time:
            if abs(dx) > self._min_swipe_distance:
                # 水平滑动
                if dx > 0:
                    self._go_next()
                else:
                    self._go_previous()

        self._touch_start = None

    def _go_next(self):
        """下一个屏幕"""
        screens = self.sm.screen_names
        current = self.sm.current
        if current in screens:
            idx = screens.index(current)
            if idx < len(screens) - 1:
                self.sm.current = screens[idx + 1]

    def _go_previous(self):
        """上一个屏幕"""
        screens = self.sm.screen_names
        current = self.sm.current
        if current in screens:
            idx = screens.index(current)
            if idx > 0:
                self.sm.current = screens[idx - 1]


# ==================== 移动端主屏幕管理器 ====================

class MobileScreenManager(ScreenManager):
    """移动端屏幕管理器"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.transition = SlideTransition(duration=0.3)

        # 添加屏幕
        self.add_widget(ChatScreen(name="chat"))
        self.add_widget(SkillsScreen(name="skills"))
        self.add_widget(SettingsScreen(name="settings"))

        self.current = "chat"

    def switch_to(self, screen_name: str):
        """切换到指定屏幕"""
        if screen_name in self.screen_names:
            self.current = screen_name

    def go_chat(self):
        """切换到聊天"""
        self.current = "chat"

    def go_skills(self):
        """切换到技能"""
        self.current = "skills"

    def go_settings(self):
        """切换到设置"""
        self.current = "settings"
