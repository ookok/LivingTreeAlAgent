"""
主窗口 — 三栏布局 + 底部状态栏 + 无弹窗 UI
=========================================
集成：聊天、写作助手Tab、用户认证、配置导入导出
V2.0 新增：MCP管理、Skill市场、任务进度、数字分身、LAN聊天

🌿 生命之树无弹窗设计:
- 林冠警报带 (CanopyAlertBand): 顶部全局提醒
- 根系询问台 (RootInquiryDeck): 右侧边栏确认
- 沃土状态栏 (SoilStatusRail): 底部进度/状态
- 晨露提示卡 (DewdropHintCard): 上下文提示
"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QLabel, QStackedWidget, QTabWidget,
    QPushButton, QMessageBox,
)
from PyQt6.QtGui import QKeyEvent, QAction, QIcon

# 基础设施层导入（工程化路径）
from client.src.infrastructure.config.config import AppConfig, load_config, save_config
from client.src.infrastructure.model.ollama_client import OllamaClient
from client.src.infrastructure.database.connection import SessionDB
from client.src.infrastructure.network.relay_client import RelayClient
from client.src.infrastructure.network.lan_discovery import LANDiscovery

# 业务层导入
from client.src.business.assembler.assembler_panel import AssemblerPanel
from client.src.business.metaverse.metaverse_panel import MetaversePanel
from client.src.business.home.home_panel import HomePanel

# 表现层组件
from client.src.presentation.theme import DARK_QSS
from client.src.presentation.components import (
    LivingTreeUI,
    CanopyAlertBand,
    RootInquiryDeck,
    SoilStatusRail,
    DewdropHintCard,
)


class MainWindow(QWidget):
    """
    主窗口

    布局：左侧会话面板 + 中央聊天/写作切换 + 右侧工作区/模型池
    顶部：林冠警报带（全局提醒）
    右侧：根系询问台（确认询问）
    底部：沃土状态栏（进度/状态）

    V2.0 新增：MCP管理、Skill市场、任务进度、数字分身、LAN聊天
    """

    switch_to_writing = pyqtSignal(str)  # 传入生成内容

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.current_session_id: str | None = None
        self._agent = None
        self._streaming = False

        # V2.0 功能模块
        self._smart_config = None
        self._task_progress_manager = None
        self._search_tool = None
        self._research_panel = None

        # 🌿 生命之树 UI 管理器
        self._ltui: LivingTreeUI = None

        self._build_ui()
        self._init_living_tree_ui()
        self._init_agent()
        self._init_system_brain()
        self._init_smart_config()
        self._init_task_progress()
        self._init_search()
        self._init_sessions()
        self._init_auth()
        self._setup_menu()

        self.setWindowTitle("Hermes Desktop v2.0 🌿")
        self.resize(config.window_width, config.window_height)

    # ── UI ─────────────────────────────────────────────────────

    def _build_ui(self):
        self.setMinimumSize(900, 600)

        # 主布局（垂直：内容 + 状态栏）
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 林冠警报带将在这里插入（在root布局的index 0）

        # 水平布局（主内容区）
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter = splitter

        # 左侧：会话面板
        self.session_panel = self._create_session_panel()
        splitter.addWidget(self.session_panel)

        # 中央：Tab 切换
        self.center_tabs = QTabWidget()
        self.center_tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.center_tabs.setDocumentMode(True)

        # 聊天页面
        self.chat_panel = self._create_chat_panel()
        self.chat_panel.send_requested.connect(self._on_send_message)
        self.chat_panel.stop_requested.connect(self._on_stop)
        self.chat_panel.switch_to_writing.connect(self._enter_writing_mode)
        self.center_tabs.addTab(self.chat_panel, "💬 聊天")

        # 写作助手页面
        self.writing_tab = self._create_writing_tab()
        self.writing_tab.status_changed.connect(self._on_status_changed)
        self.center_tabs.addTab(self.writing_tab, "✍️ 写作助手")

        # V2.0: 研究搜索页面
        self.research_tab = self._create_research_panel()
        self.center_tabs.addTab(self.research_tab, "🔍 研究助手")

        # V2.0: 首页聚合
        self.home_tab = HomePanel()
        self.center_tabs.addTab(self.home_tab, "🏠 首页")

        # V2.0: 嫁接园（装配园）
        self.assembler_tab = AssemblerPanel()
        self.center_tabs.addTab(self.assembler_tab, "🌱 嫁接园")

        # V2.8: 元宇宙UI (舰桥)
        self.metaverse_tab = MetaversePanel()
        self.center_tabs.addTab(self.metaverse_tab, "🚀 舰桥")

        splitter.addWidget(self.center_tabs)

        # 右侧：工作区
        self.right_stack = QStackedWidget()
        self.workspace_panel = self._create_workspace_panel()
        self.right_stack.addWidget(self.workspace_panel)

        # 模型池面板
        self.model_pool_panel = self._create_model_pool_panel()
        self.model_pool_panel.model_selected.connect(self._switch_model)
        self.right_stack.addWidget(self.model_pool_panel)

        splitter.addWidget(self.right_stack)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([self.config.left_panel_width, 800, self.config.right_panel_width])

        content_layout.addWidget(splitter)
        root.addLayout(content_layout)

        # 沃土状态栏将在这里添加（在root布局的末尾）

        # 默认
        self.center_tabs.setCurrentIndex(0)
        self.right_stack.setCurrentIndex(0)

        # 应用主题
        self.setStyleSheet(DARK_QSS)

    def _create_session_panel(self):
        """创建会话面板（子类可覆盖）"""
        from client.src.presentation.widgets.session_panel import SessionPanel
        panel = SessionPanel()
        panel.new_chat_requested.connect(self._new_chat)
        panel.session_selected.connect(self._load_session)
        panel.session_deleted.connect(self._delete_session)
        panel.settings_requested.connect(self._show_settings)
        return panel

    def _create_chat_panel(self):
        """创建聊天面板"""
        from client.src.presentation.panels.chat_panel import ChatPanel
        return ChatPanel()

    def _create_writing_tab(self):
        """创建写作标签页"""
        from client.src.presentation.panels.writing_tab import WritingTab
        return WritingTab(self, self._agent)

    def _create_research_panel(self):
        """创建研究面板"""
        from client.src.presentation.panels.research_panel import ResearchPanel
        panel = ResearchPanel()
        self._research_panel = panel
        return panel

    def _create_workspace_panel(self):
        """创建工作区面板"""
        from client.src.presentation.widgets.workspace_panel import WorkspacePanel
        return WorkspacePanel()

    def _create_model_pool_panel(self):
        """创建模型池面板"""
        from client.src.presentation.panels.model_pool_panel import ModelPoolPanel
        return ModelPoolPanel(self)

    def _init_living_tree_ui(self):
        """初始化生命之树 UI 组件"""
        self._ltui = LivingTreeUI(self)

        # 林冠警报带信号
        self._ltui.alert.action_clicked.connect(self._on_alert_action)
        self._ltui.alert.dismissed.connect(self._on_alert_dismiss)

        # 根系询问台信号
        self._ltui.inquiry.confirmed.connect(self._on_inquiry_confirmed)
        self._ltui.inquiry.cancelled.connect(self._on_inquiry_cancelled)

        # 沃土状态栏信号
        self._ltui.status.cancelled.connect(self._on_status_cancelled)

    # ── 🌿 林冠警报带 (Canopy Alert Band) ─────────────────────────

    def show_alert(
        self,
        message: str,
        level: str = "info",
        actions: list = None,
        auto_hide_ms: int = 0
    ):
        """
        显示全局提醒（林冠警报带）

        Args:
            message: 提醒消息
            level: info/warning/error/success
            actions: [(文本, 回调), ...]
            auto_hide_ms: 自动隐藏时间
        """
        self._ltui.alert.show_alert(message, level, actions, auto_hide_ms)

    def _on_alert_action(self, action_id: str):
        """警报动作被点击"""
        pass  # 子类可覆盖

    def _on_alert_dismiss(self):
        """警报被关闭"""
        pass  # 子类可覆盖

    # ── 🌿 根系询问台 (Root Inquiry Deck) ───────────────────────

    def ask(
        self,
        title: str = "根系询问",
        description: str = "请确认您的选择：",
        options: list = None,
        on_confirm=None,
        on_cancel=None
    ):
        """
        显示询问（根系询问台）

        Args:
            title: 标题
            description: 描述
            options: [(id, 文本, 回调), ...]
            on_confirm: 确认回调 (choice_id)
            on_cancel: 取消回调
        """
        self._ltui.inquiry.ask(title, description, options=options, on_confirm=on_confirm, on_cancel=on_cancel)

    def ask_conflict_resolve(self, tool_new: str, tool_old: str, options: list, on_confirm=None):
        """显示冲突解决询问"""
        self._ltui.inquiry.ask_conflict_resolve(tool_new, tool_old, options, on_confirm)

    def ask_delete(self, item_name: str, on_confirm=None):
        """显示删除确认"""
        self._ltui.ask_delete(item_name, on_confirm)

    def ask_risk(self, action: str, risk_level: str = "medium", on_confirm=None):
        """显示风险确认"""
        self._ltui.ask_risk(action, risk_level, on_confirm)

    def _on_inquiry_confirmed(self, choice_id: str, choice_text: str):
        """询问确认"""
        pass  # 子类可覆盖

    def _on_inquiry_cancelled(self):
        """询问取消"""
        pass  # 子类可覆盖

    # ── 🌿 沃土状态栏 (Soil Status Rail) ─────────────────────────

    def show_progress(self, message: str, progress: int = -1):
        """显示进度状态"""
        self._ltui.status.show_progress(message, progress)

    def update_progress(self, progress: int, message: str = None):
        """更新进度"""
        self._ltui.status.update_progress(progress, message)

    def show_success_status(self, message: str, auto_hide_ms: int = 3000):
        """显示成功状态"""
        self._ltui.status.show_success(message, auto_hide_ms)

    def show_error_status(self, message: str, auto_hide_ms: int = 5000):
        """显示错误状态"""
        self._ltui.status.show_error(message, auto_hide_ms)

    def show_info_status(self, message: str, auto_hide_ms: int = 3000):
        """显示信息状态"""
        self._ltui.status.show_info(message, auto_hide_ms)

    def clear_status(self):
        """清除状态栏"""
        self._ltui.status.clear()

    def _on_status_cancelled(self):
        """状态栏取消"""
        pass  # 子类可覆盖

    # ── 🌿 晨露提示卡 (Dewdrop Hint Card) ─────────────────────────

    def show_hint_below(self, target: QWidget, message: str, level: str = "info"):
        """在控件下方显示提示"""
        DewdropHintCard.show_below(target, message, level)

    def show_hint_right(self, target: QWidget, message: str, level: str = "info"):
        """在控件右侧显示提示"""
        DewdropHintCard.show_right_of(target, message, level)

    def dismiss_all_hints(self):
        """关闭所有提示卡"""
        DewdropHintCard.dismiss_all()

    # ── 便捷方法（替换 QMessageBox）────────────────────────────────

    def show_info(self, message: str, title: str = "提示"):
        """显示信息提示（替换 QMessageBox.information）"""
        self.show_alert(f"💡 {title}: {message}", level="info", auto_hide_ms=3000)

    def show_warning(self, message: str, title: str = "警告", actions: list = None):
        """显示警告提示（替换 QMessageBox.warning）"""
        if actions is None:
            actions = [("知道了", None)]
        self.show_alert(f"⚠️ {title}: {message}", level="warning", actions=actions)

    def show_error(self, message: str, title: str = "错误", actions: list = None):
        """显示错误提示（替换 QMessageBox.critical）"""
        if actions is None:
            actions = [("关闭", None)]
        self.show_alert(f"❌ {title}: {message}", level="error", actions=actions, auto_hide_ms=5000)

    def confirm(self, message: str, on_confirm, on_cancel=None, title: str = "确认"):
        """显示确认对话框（替换 QMessageBox.question）"""
        self.ask(
            title=title,
            description=message,
            options=[
                ("confirm", "确认", on_confirm),
                ("cancel", "取消", on_cancel)
            ]
        )

    def confirm_delete(self, item_name: str, on_confirm):
        """显示删除确认（替换 QMessageBox 关于删除的确认）"""
        self.ask_delete(item_name, on_confirm)

    # ── 菜单 ─────────────────────────────────────────────────────

    def _setup_menu(self):
        """设置菜单栏"""
        pass

    # ── Toast 通知 ───────────────────────────────────────────────

    def _toggle_toast(self, checked: bool):
        """切换通知"""
        # 通知现在由沃土状态栏处理
        pass

    def _show_toast(self, message: str, toast_type: str = "info"):
        """显示通知"""
        level_map = {
            "success": "success",
            "warning": "warning",
            "error": "error",
            "info": "info"
        }
        self.show_alert(message, level=level_map.get(toast_type, "info"), auto_hide_ms=3000)

    # ── 系统大脑 ─────────────────────────────────────────────────

    def _init_system_brain(self):
        """初始化系统大脑"""
        def on_status(msg: str, progress: float):
            self.statusBar().showMessage(f"系统大脑: {msg}")
            if progress >= 0:
                self._ltui.status.show_progress(msg, int(progress * 100))

        try:
            from client.src.infrastructure.model.system_brain import get_system_brain, SystemBrainConfig

            config = SystemBrainConfig(
                model_name="qwen2.5:0.5b",
                api_base=self.config.ollama.base_url
            )
            self.system_brain = get_system_brain(config, status_callback=on_status)

            import threading
            def init():
                ready = self.system_brain.check_and_prepare()
                QTimer.singleShot(0, lambda: self._update_brain_status(ready))

            threading.Thread(target=init, daemon=True).start()
        except Exception as e:
            self._show_toast(f"系统大脑初始化失败: {e}", "warning")

    def _update_brain_status(self, ready: bool):
        """更新系统大脑状态"""
        if ready:
            self._show_toast("系统大脑已就绪", "success")
        else:
            self._show_toast("系统大脑未就绪，请确保Ollama正在运行", "warning")

    # ── 智能配置 ─────────────────────────────────────────────────

    def _init_smart_config(self):
        """初始化智能配置系统"""
        try:
            self._smart_config = get_smart_config(
                use_brain=True,
                brain=self.system_brain if hasattr(self, 'system_brain') else None
            )

            import threading
            def init():
                env = self._smart_config.detect_environment()
                suggestions = self._smart_config.analyze_and_suggest()
                QTimer.singleShot(0, lambda: self._update_smart_config_status(env, suggestions))

            threading.Thread(target=init, daemon=True).start()
        except Exception as e:
            self._show_toast(f"智能配置初始化失败: {e}", "warning")

    def _update_smart_config_status(self, env, suggestions):
        """更新智能配置状态"""
        self._show_toast("智能配置已就绪", "success")

    # ── 任务进度 ─────────────────────────────────────────────────

    def _init_task_progress(self):
        """初始化任务进度管理器"""
        self._task_progress_manager = get_task_progress_manager(self)

    # ── AI 搜索 ─────────────────────────────────────────────────

    def _init_search(self):
        """初始化 AI 搜索工具"""
        from client.src.infrastructure.network.search_tool import AISearchTool

        serper_key = ""
        brave_key = ""

        self._search_tool = AISearchTool(
            serper_key=serper_key,
            brave_key=brave_key,
            cache_ttl=60,
        )

        if hasattr(self, 'research_tab'):
            self.research_tab.set_search_tool(self._search_tool)

        if self.ollama_client and self.ollama_client.ping():
            self._search_tool.set_llm_client(
                self.ollama_client,
                model=self.config.ollama.default_model or "qwen2.5:7b"
            )

    # ── Agent ─────────────────────────────────────────────────

    def _init_agent(self):
        self.ollama_client = OllamaClient(self.config.ollama)
        self._update_status()
        QTimer.singleShot(3000, self._update_status)

    def _update_status(self):
        online = self.ollama_client.ping()
        if online:
            v = self.ollama_client.version()
            m = self.config.ollama.default_model or "未选模型"
            status_text = f"Ollama {v} — {m}"
            indicator = "🟢"
        else:
            status_text = "⚠ Ollama 未运行 — 请启动 ollama serve"
            indicator = "🔴"

        # 更新沃土状态栏
        self._ltui.status.show_info(status_text)

    # ── 会话 ─────────────────────────────────────────────────

    def _init_sessions(self):
        db = SessionDB()
        for s in db.list_sessions(limit=50):
            self.session_panel.add_session(s.id, s.title)

    def _new_chat(self):
        self.chat_panel.clear_messages()
        db = SessionDB()
        sid = db.create_session()
        self.current_session_id = sid
        self.session_panel.add_session(sid, "新会话", select=True)
        self._recreate_agent()

    def _load_session(self, session_id: str):
        if self._streaming:
            # 替换 QMessageBox.warning
            self.show_warning("请等待", "请等待当前响应结束后再切换会话")
            return
        self.current_session_id = session_id
        db = SessionDB()
        s = db.get_session(session_id)
        if s:
            self.chat_panel.set_title(s.title)
            self._load_session_messages(session_id)

    def _load_session_messages(self, session_id: str):
        db = SessionDB()
        msgs = db.get_messages(session_id)
        self.chat_panel.clear_messages()
        for m in msgs:
            if m.role == "user":
                self.chat_panel.add_user_message(m.content)
            elif m.role == "assistant":
                self.chat_panel.begin_assistant_message()
                self.chat_panel.append_token(m.content)

    def _delete_session(self, session_id: str):
        db = SessionDB()
        db.delete_session(session_id)
        self.session_panel.remove_session(session_id)
        if self.current_session_id == session_id:
            self._new_chat()

    def _recreate_agent(self):
        from client.src.business.agent import HermesAgent, AgentCallbacks

        if self._agent:
            self._agent.close()
        cbs = AgentCallbacks(
            stream_delta=self._on_stream_delta,
            thinking=self._on_thinking,
            tool_start=self._on_tool_start,
            tool_result=self._on_tool_result,
        )
        self._agent = HermesAgent(
            config=self.config,
            session_id=self.current_session_id,
            callbacks=cbs,
        )

        if hasattr(self, 'writing_tab'):
            self.writing_tab.set_agent(self._agent)

    # ── 消息 ─────────────────────────────────────────────────

    def _on_send_message(self, text: str):
        if not self.current_session_id:
            self._new_chat()

        if not self._agent:
            self._recreate_agent()

        if not self.ollama_client.ping():
            self.chat_panel.add_error_message(
                "Ollama 未运行！请在终端运行: ollama serve\n"
                "或到设置中检查 Ollama 连接地址"
            )
            return

        self._streaming = True
        self.chat_panel.set_running(True)
        self.chat_panel.add_user_message(text)

        self._ltui.status.show_progress("AI 思考中...", -1)

        import threading

        def run():
            try:
                self.chat_panel.begin_assistant_message()
                for chunk in self._agent.send_message(text):
                    if chunk.error:
                        QTimer.singleShot(0, lambda: self.chat_panel.add_error_message(f"错误: {chunk.error}"))
                        break
            except Exception as e:
                QTimer.singleShot(0, lambda: self.chat_panel.add_error_message(f"异常: {str(e)}"))
            finally:
                QTimer.singleShot(0, lambda: self.chat_panel.set_running(False))
                QTimer.singleShot(0, lambda: self._ltui.status.clear())
                self._streaming = False

        threading.Thread(target=run, daemon=True).start()

    def _on_stop(self):
        if self._agent:
            self._agent.interrupt()
        self._streaming = False
        self.chat_panel.set_running(False)
        self._ltui.status.clear()

    # ── 回调 ─────────────────────────────────────────────────

    def _on_stream_delta(self, delta: str):
        QTimer.singleShot(0, lambda: self.chat_panel.append_token(delta))

    def _on_thinking(self, delta: str):
        pass

    def _on_tool_start(self, name: str, args_str: str):
        QTimer.singleShot(0, lambda: self.chat_panel.add_tool_block(name, args_str))

    def _on_tool_result(self, name: str, result: str, success: bool):
        QTimer.singleShot(0, lambda: self.chat_panel.finish_tool_block(name, result, success))

    # ── 状态变化 ─────────────────────────────────────────────────

    def _on_status_changed(self, msg: str):
        """写作 Tab 状态变化"""
        self._ltui.status.show_info(msg)

    # ── 写作模式切换 ─────────────────────────────────────────────

    def _enter_writing_mode(self, content: str = ""):
        """进入写作模式"""
        self.center_tabs.setCurrentIndex(1)
        if content and hasattr(self, 'writing_tab'):
            self.writing_tab._editor.setPlainText(content)

    def _enter_chat_mode(self):
        """返回聊天模式"""
        self.center_tabs.setCurrentIndex(0)

    # ── 设置对话框 ────────────────────────────────────────────────

    def _show_settings(self):
        """显示设置对话框（替换为面板）"""
        # 切换到设置标签页，而不是弹窗
        settings_tab_index = self._find_or_create_settings_tab()
        if settings_tab_index >= 0:
            self.center_tabs.setCurrentIndex(settings_tab_index)

    def _find_or_create_settings_tab(self) -> int:
        """查找或创建设置标签页"""
        for i in range(self.center_tabs.count()):
            if self.center_tabs.tabText(i) == "⚙️ 设置":
                return i
        return -1

    # ── 模型切换 ─────────────────────────────────────────────────

    def _switch_model(self, model_name: str):
        """切换模型"""
        self.config.ollama.default_model = model_name
        self._update_status()
        self._show_toast(f"已切换到模型: {model_name}", "success")
