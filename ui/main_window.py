"""
主窗口 — 三栏布局 + 底部状态栏
集成：聊天、写作助手Tab、用户认证、配置导入导出
V2.0 新增：MCP管理、Skill市场、任务进度、数字分身、LAN聊天
"""

import logging

logger = logging.getLogger(__name__)

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QLabel, QMessageBox, QStackedWidget, QTabWidget,
    QPushButton, QMenuBar, QMenu,
)
from PyQt6.QtGui import QKeyEvent, QAction, QIcon

from core.config import AppConfig, load_config, save_config
from client.src.business.agent import HermesAgent, AgentCallbacks
from core.ollama_client import OllamaClient
from core.session_db import SessionDB
from client.src.business.system_brain import get_system_brain, SystemBrainConfig
from core.config_manager import get_config_manager
from core.auth_system import get_auth_system
from core.smart_config import get_smart_config
from ui.task_progress import get_task_progress_manager
from core.search_tool import AISearchTool
from ui.a2ui import A2UIManager, A2UIPanel, UILoader, FallbackManager, ProgressManager, ConfigQuickEdit

from ui.session_panel import SessionPanel
from ui.chat_panel import ChatPanel
from ui.workspace_panel import WorkspacePanel
from ui.model_market import ModelMarketPanel
from ui.model_pool_panel import ModelPoolPanel
from ui.settings_dialog import SettingsDialog
from ui.toast_notification import get_toast_manager, toast_success, toast_warning, toast_error
from ui.user_auth_dialog import LoginDialog
from ui.config_export_dialog import ConfigExportDialog
from ui.writing_tab import WritingTab
from ui.task_progress import TaskProgressManager
from ui.research_panel import ResearchPanel
from ui.content_monitor_panel import ContentMonitorPanel
from ui.doc_lifecycle_panel import DocLifecyclePanel
from ui.schedule_panel import SchedulePanel
from ui.persona_skill_panel import PersonaSkillPanel
from ui.p2p_search_proxy_panel import P2PSearchProxyPanel
from core.wiki_compiler.compiler import get_wiki_compiler
from core.wiki_compiler.ui.panel import WikiCompilerPanel
# V2.1: 全源情报中心
from ui.intelligence.intelligence_panel import IntelligencePanel
# V2.2: 去中心化邮箱
# from ui.mailbox.mailbox_panel import MailboxPanel
# V2.3: P2P连接器 (短ID寻址 + 多通道通信)
# from ui.connector.connector_panel import ConnectorPanel
# V2.4: 统一聊天 (Element/Discord/Telegram风格)
# from ui.unified_chat.chat_panel import ChatPanel
# V2.5: 翻译中心 (离线初翻 + 在线精翻)
# from ui.translation.translation_panel import TranslationPanel
# V2.6: 去中心化论坛 (P2P穿透网络 + 智能写作)
# from ui.forum.forum_panel import ForumPanel
# V2.7: 伪域名系统 (去中心化域名 + DNS解析)
# from ui.pseudodomain.domain_panel import DomainPanel
# V2.8: 元宇宙UI (舰桥操作系统 - 时空引力场)
# from ui.metaverse_ui_panel import MetaverseUIPanel

# 需求头脑风暴 (借鉴 obra/superpowers 设计思路)
# from ui.idea_clarifier_panel import IdeaClarifierPanel
# 政府开放资料查询 (借鉴 gov_openapi_agent 设计思路)
# from ui.gov_data_panel import GovDataPanel
# 公司印章生成器 (借鉴 company-stamp 设计思路)
# from ui.stamp_panel import StampPanel
# 中继链 - 分布式积分账本 (无币无挖矿类区块链)
# from ui.relay_chain_panel import RelayChainPanel
# V3.0: 根系同步 (Root Sync - Syncthing 风格去中心化文件同步)
# from ui.root_sync_panel import RootSyncPanel
# V3.1: GitHub Store (桌面代码仓库 - 发现安装 GitHub Release 桌面应用)
# from ui.github_store_panel import GitHubStorePanel
# V3.2: Database Browser (桌面数据库管理 - onetcli 风格多数据库管理)
# from ui.database_browser_panel import DatabaseBrowserPanel
# V3.3: Preview Panel (Office 文档实时预览与编辑 - AionUi 风格)
# from ui.preview_panel import PreviewPanel
# V2.0: MCP Market 面板
# from ui.mcp_market_panel import MCPMarketPanel
# V2.0: Skill Market 面板
# from ui.skill_market_panel import SkillMarketPanel
# V2.0: Digital Avatar 面板
# from ui.avatar_panel import AvatarPanel
# 环保模型商店面板 (P2P模型分发 + API Key自动配置)
# from ui.model_store_panel import ModelStorePanel
# 🔐 IdentityPanel - 身份驱动的数据主权 UI
# from ui.identity_panel import IdentityPanel
# 📚 私有法规库检索面板 (Chroma/Milvus + all-MiniLM-L6-v2)
# from ui.regulation_search_panel import RegulationSearchPanel
# 🏛️ 社区共建者权益中心 (积分->权益转换 + 税务合规 + 基金透明)
# from ui.community_rights_panel import CommunityRightsPanel
# 🤖 AI脚本生成器 (自然语言→可执行脚本 + 沙箱执行 + 脚本市场)
# from ui.ai_script_panel import AIScriptPanel
# 🌐 P2P 去中心化更新系统面板
# from ui.decentralized_update_panel import DecentralizedUpdatePanel
# V2.0: LAN Chat 面板
# from ui.lan_chat_panel import LANChatPanel
# V2.0: Smart IDE 面板
# from ui.smart_ide_panel import SmartIDEPanel
# V2.0: Game Room 面板
# from ui.game_room_panel import GameRoomPanel
# 🎮 融合游戏系统 (暗黑地牢 + 狼人杀 + 密室逃脱)
# from ui.dungeon_werewolf_escape_panel import FusionGamePanel
# 🎭 虚拟形象与社交广场系统
# from ui.virtual_avatar_social_panel import VirtualAvatarSocialPanel
# 🃏 斗地主游戏系统
# from ui.dou_di_zhu_panel import DouDiZhuPanel
# 🌐 P2P网络自举协议
# from ui.p2p_bootstrap_panel import P2PBootstrapPanel
# 🌌 通用数字永生系统 - Phoenix Protocol
# from ui.phoenix_protocol_panel import PhoenixProtocolPanel
# 🎛️ 通用硬件智能集成系统 - Hardware Mind
# from ui.hardware_mind_panel import HardwareMindPanel
# 🐍 Python智能日志分析系统 - Python Mind
# from ui.python_mind_panel import PythonMindPanel
# 🧹 智能临时文件清理系统 - Smart Cleanup
# from ui.smart_cleanup_panel import SmartCleanupPanel
# 🤖 AI驱动式界面自检与优化系统 - UI Self-Check
# from ui.ui_self_check_panel import UISelfCheckPanel
# 🔐 智能授权与实名认证系统 - Activation License
# from ui.activation_license_panel import ActivationLicensePanel
# V2.0: Knowledge Blockchain 面板
# from ui.knowledge_blockchain_panel import KnowledgeBlockchainPanel
# L4 执行层监控面板
# from ui.l4_executor_panel import L4ExecutorPanel
# SmolLM2 L0 快反大脑面板
# from ui.smolllm2_panel import SmolLM2Panel
# 智能提示系统面板
# from ui.intelligent_hints_panel import IntelligentHintsPanel
# 思维审核与自我进化面板
# from ui.thought_audit_panel import ThoughtAuditPanel
# 聚合推荐首页面板
# from ui.feed_home_panel import FeedHomePanel
# 认知框架协作者面板
# from ui.cognitive_framework_panel import CognitiveFrameworkPanel
# 消息模式面板
# from ui.message_pattern_panel import MessagePatternPanel
# 聚合推荐面板
# from ui.aggregator_panel import AggregatorPanel
# 归档工具面板
# from ui.archive_tool_panel import ArchiveToolPanel
# 云盘面板
# from ui.cloud_disk_panel import CloudDiskPanel
# 提佣系统面板
# from ui.commission_panel import CommissionPanel
# 专业审核增强面板
# from ui.creative_review_panel import CreativeReviewPanel
# 决策支持面板
# from ui.decision_panel import DecisionSupportPanel
# 增强任务面板
# from ui.enhanced_task_panel import EnhancedTaskPanel
# Karpathy规则面板
# from ui.karpathy_panel import KarpathyRulesPanel
# 轻量级UI面板
# from ui.lightweight_ui_panel import LightweightUIPanel
# Markdown转Doc面板
# from ui.md_to_doc_panel import MarkdownToDocPanel
# P2P广播面板
# from ui.p2p_broadcast_panel import P2PBroadcastPanel
# 用户画像面板
# from ui.profile_panel import ProfilePanel
# 模型提供商面板
# from ui.provider_panel import ProviderPanel
# 智能推荐面板
# from ui.recommendation_panel import RecommendationPanel
# 中继面板
# from ui.relay_panel import RelayPanel
# 安全诊断面板
# from ui.security_diagnostic_panel import SecurityDiagnosticPanel
# 智能助手面板
# from ui.smart_assistant_panel import SmartAssistantPanel
# 智能写作面板
# from ui.smart_writing_panel import SmartWritingPanel
# 社交电商面板
# from ui.social_commerce_panel import SocialCommercePanel
# 状态面板
# from ui.status_panel import StatusPanel
# Toonflow短剧面板
# from ui.toonflow_panel import ToonflowPanel
# URL智能优化面板
# from ui.url_intelligence_panel import URLIntelligencePanel
# 写作助手面板
# from ui.writing_assistant_panel import WritingAssistantPanel


class MainWindow(QWidget):
    """
    主窗口
    布局：左侧会话面板 + 中央聊天/写作切换 + 右侧工作区/模型池
    V2.0 新增：MCP管理、Skill市场、任务进度、数字分身、LAN聊天
    """

    switch_to_writing = pyqtSignal(str)  # 传入生成内容

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.current_session_id: str | None = None
        self._agent: HermesAgent | None = None
        self._streaming = False

        # V2.0 功能模块
        self._smart_config = None
        self._task_progress_manager: TaskProgressManager | None = None
        self._search_tool: AISearchTool | None = None
        self._research_panel: ResearchPanel | None = None

        # A2UI 相关
        self._a2ui_manager = A2UIManager()
        self._ui_loader_manager = UILoader()
        self._fallback_manager = FallbackManager()
        self._progress_manager = ProgressManager()
        self._config_quick_edit_manager = ConfigQuickEdit()

        # 延迟初始化标志
        self._ui_initialized = False

        # 快速构建基础UI
        self._build_core_ui()
        
        # 设置窗口属性
        self.setWindowTitle("Hermes Desktop v2.0")
        self.resize(config.window_width, config.window_height)
        
        # 显示加载界面
        self._show_loading_screen()
        
        # 异步初始化其他组件
        import threading
        threading.Thread(target=self._async_init, daemon=True).start()

    # ── UI ─────────────────────────────────────────────────────

    def _build_core_ui(self):
        """构建核心UI（快速显示）"""
        self.setMinimumSize(900, 600)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 加载屏幕
        self.loading_stack = QStackedWidget()
        root.addWidget(self.loading_stack)

        # 主界面
        self.main_widget = QWidget()
        self.main_layout = QHBoxLayout(self.main_widget)
        self.loading_stack.addWidget(self.main_widget)

        # 构建主界面布局
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)
        self.splitter.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.splitter)

        # 左侧：会话面板（快速加载）
        self.session_panel = SessionPanel()
        self.session_panel.setStyleSheet("""
            QWidget {
                background-color: #1E293B;
                border: none;
            }
            QLabel {
                color: #94A3B8;
            }
        """)
        self.session_panel.new_chat_requested.connect(self._new_chat)
        self.session_panel.session_selected.connect(self._load_session)
        self.session_panel.session_deleted.connect(self._delete_session)
        self.session_panel.settings_requested.connect(self._show_settings)
        self.splitter.addWidget(self.session_panel)

        # 中央：Tab 切换（只加载核心标签）
        self.center_tabs = QTabWidget()
        self.center_tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.center_tabs.setDocumentMode(True)
        self.center_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #0F172A;
            }
            QTabBar::tab {
                background-color: transparent;
                color: #94A3B8;
                padding: 12px 20px;
                margin-right: 4px;
                border-bottom: 2px solid transparent;
                font-size: 14px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                color: #3B82F6;
                border-bottom: 2px solid #3B82F6;
            }
            QTabBar::tab:hover {
                color: #3B82F6;
                background-color: rgba(59, 130, 246, 0.1);
            }
        """)
        
        # 聊天页面（核心）
        self.chat_panel = ChatPanel()
        self.chat_panel.send_requested.connect(self._on_send_message)
        self.chat_panel.stop_requested.connect(self._on_stop)
        self.chat_panel.switch_to_writing.connect(self._enter_writing_mode)
        self.chat_panel.config_hint_requested.connect(self._show_settings)
        self.center_tabs.addTab(self.chat_panel, "💬 聊天")
        
        # 写作助手页面（核心）
        self.writing_tab = WritingTab(self, self._agent)
        self.writing_tab.status_changed.connect(self._on_status_changed)
        self.center_tabs.addTab(self.writing_tab, "✍️ 写作助手")

        # 研究搜索页面（核心）
        self.research_tab = ResearchPanel()
        self.center_tabs.addTab(self.research_tab, "🔍 研究助手")

        # V2.1: 全源情报中心
        self.intelligence_tab = IntelligencePanel()
        self.center_tabs.addTab(self.intelligence_tab, "🕵️ 情报中心")

        self.splitter.addWidget(self.center_tabs)

        # 右侧：工作区 + 模型池（快速加载）
        self.right_stack = QStackedWidget()
        self.workspace_panel = WorkspacePanel()
        self.right_stack.addWidget(self.workspace_panel)
        self.model_pool_panel = ModelPoolPanel(self)
        self.model_pool_panel.model_selected.connect(self._switch_model)
        self.right_stack.addWidget(self.model_pool_panel)
        self.splitter.addWidget(self.right_stack)

        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([self.config.left_panel_width, 800, self.config.right_panel_width])

        # 状态栏
        self.status_bar = QLabel()
        self.status_bar.setObjectName("StatusBar")
        self.status_bar.setStyleSheet("""
            QLabel#StatusBar {
                background:#0F172A;
                border-top:1px solid #334155;
                padding:8px 16px;
                color:#94A3B8;
                font-size:12px;
            }
        """)
        self._status_text = QLabel("初始化中…")
        self._status_indicator = QLabel("⚫")
        self._brain_status = QLabel("🧠")  # 系统大脑状态
        self._task_status = QLabel("")  # 任务进度状态
        self._toast_toggle = QPushButton("🔔")
        self._toast_toggle.setFixedWidth(30)
        self._toast_toggle.setCheckable(True)
        self._toast_toggle.setChecked(True)
        self._toast_toggle.setToolTip("切换通知提示")
        self._toast_toggle.clicked.connect(self._toggle_toast)
        
        status_layout = QHBoxLayout()
        status_layout.addWidget(self._status_text)
        status_layout.addStretch()
        status_layout.addWidget(self._task_status)  # V2.0: 任务进度状态
        status_layout.addWidget(self._brain_status)
        status_layout.addWidget(self._status_indicator)
        status_layout.addWidget(self._toast_toggle)
        self.status_bar.setLayout(status_layout)
        self.main_layout.addWidget(self.status_bar)

        # 默认
        self.center_tabs.setCurrentIndex(0)
        self.right_stack.setCurrentIndex(0)

    def _show_loading_screen(self):
        """显示加载屏幕"""
        from PyQt6.QtWidgets import QVBoxLayout, QLabel
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QFont

        loading_widget = QWidget()
        loading_layout = QVBoxLayout(loading_widget)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("生命之树正在苏醒...")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #3B82F6;")
        loading_layout.addWidget(title)

        subtitle = QLabel("根系正在伸向远方，连接智慧网络...")
        subtitle.setFont(QFont("Arial", 12))
        subtitle.setStyleSheet("color: #94A3B8;")
        loading_layout.addWidget(subtitle)

        self.loading_stack.addWidget(loading_widget)
        self.loading_stack.setCurrentWidget(loading_widget)

    def _async_init(self):
        """异步初始化组件"""
        import time
        start_time = time.time()

        try:
            # 显示主界面
            QTimer.singleShot(200, lambda: self.loading_stack.setCurrentWidget(self.main_widget))

            # 显示初始化进度
            init_steps = [
                "初始化Hermes Agent",
                "加载系统大脑",
                "初始化智能配置",
                "加载任务进度管理器",
                "初始化搜索工具",
                "加载会话数据",
                "初始化认证系统",
                "同步配置",
                "加载A2UI组件",
                "设置菜单栏"
            ]
            
            QTimer.singleShot(300, lambda: self.chat_panel.show_initialization_progress(init_steps))

            # 初始化核心组件
            self._init_agent()
            self._init_system_brain()
            self._init_smart_config()
            self._init_task_progress()
            self._init_search()
            self._init_sessions()
            self._init_auth()
            self._init_config_sync()
            self._init_a2ui()
            self._setup_menu()

            # 延迟加载其他标签页
            QTimer.singleShot(1000, self._load_additional_tabs)

            # 更新状态
            QTimer.singleShot(500, lambda: self._status_text.setText("就绪"))
            QTimer.singleShot(500, lambda: self._status_indicator.setText("🟢"))

        except Exception as e:
            logger.error(f"异步初始化失败: {e}")
            QTimer.singleShot(0, lambda: self.loading_stack.setCurrentWidget(self.main_widget))
            QTimer.singleShot(0, lambda: self._status_text.setText(f"初始化异常: {str(e)}"))
            QTimer.singleShot(0, lambda: self._status_indicator.setText("🔴"))

        logger.info(f"初始化完成，耗时: {time.time() - start_time:.2f}秒")

    def _load_additional_tabs(self):
        """延迟加载其他标签页"""
        try:
            # V2.0: 内容监控页面
            self.content_monitor_tab = ContentMonitorPanel()
            self.center_tabs.addTab(self.content_monitor_tab, "🛡️ 内容监控")

            # V2.0: 文档审核与生命周期管理页面
            self.doc_lifecycle_tab = DocLifecyclePanel()
            self.center_tabs.addTab(self.doc_lifecycle_tab, "📋 文档审核")

            # V2.0: 定时任务管理页面
            self.schedule_tab = SchedulePanel()
            self.center_tabs.addTab(self.schedule_tab, "⏰ 定时任务")

            # V2.0: Wiki 编译器页面 (LLM Wiki 架构)
            self.wiki_compiler_tab = WikiCompilerPanel(get_wiki_compiler())
            self.center_tabs.addTab(self.wiki_compiler_tab, "🧠 Wiki知识库")

            # V2.0: 角色智库 - Persona Skill 面板
            self.persona_skill_tab = PersonaSkillPanel()
            self.center_tabs.addTab(self.persona_skill_tab, "🧙 角色智库")

            # V2.0: P2P 搜索代理网络
            self.p2p_search_proxy_tab = P2PSearchProxyPanel()
            self.center_tabs.addTab(self.p2p_search_proxy_tab, "🌐 P2P搜索代理")

            # V2.0: 去中心化本地商品交易市场
            from core.local_market.ui.panel import LocalMarketPanel
            self.local_market_tab = LocalMarketPanel()
            self.center_tabs.addTab(self.local_market_tab, "🛒 本地市场")

            # V2.0: PageIndex 智能文档索引 (LLM Wiki 架构)
            from core.page_index.ui.panel import PageIndexPanel
            self.page_index_tab = PageIndexPanel()
            self.center_tabs.addTab(self.page_index_tab, "📑 文档索引")

            # V2.1: Evolution Engine Dashboard - 智能IDE自我进化系统
            try:
                from ui.evolution_dashboard import EvolutionDashboard
                self.evolution_dashboard_tab = EvolutionDashboard()
                self.center_tabs.addTab(self.evolution_dashboard_tab, "🧬 进化引擎")
            except Exception as e:
                logger.debug(f"跳过 进化引擎: {e}")

            # 其他面板（按需加载）
            self._load_optional_tabs()

        except Exception as e:
            logger.error(f"加载标签页失败: {e}")

    def _load_optional_tabs(self):
        """加载可选标签页"""
        optional_tabs = [
            # V2.0: CLI-Anything 工具工厂
            ("cli_anything_tab", "ui.cli_anything_panel", "CLIAutoGenPanel", "⚡ 工具工厂"),
            # V2.0: WebRTC 视频通话与直播
            ("webrtc_tab", "ui.webrtc_panel", "WebRTCPanel", "📞 视频通话"),
            # V2.0: 视频播放器
            ("video_player_tab", "ui.video_player_panel", "VideoPlayerPanel", "🎬 视频播放"),
            # V2.0: P2P 去中心化电商
            ("decommerce_tab", "ui.decommerce_panel", "DeCommercePanel", "🛍️ DeCommerce"),
            # V2.8: 元宇宙UI
            ("metaverse_tab", "ui.metaverse_ui_panel", "MetaverseUIPanel", "🚀 舰桥"),
            # 需求头脑风暴
            ("brainstorm_tab", "ui.idea_clarifier_panel", "IdeaClarifierPanel", "🎯 头脑风暴"),
            # 政府开放资料查询
            ("gov_data_tab", "ui.gov_data_panel", "GovDataPanel", "🏛️ 政府资料"),
            # 公司印章生成器
            ("stamp_tab", "ui.stamp_panel", "StampPanel", "🔐 印章生成"),
            # 中继链
            ("relay_chain_tab", "ui.relay_chain_panel", "RelayChainPanel", "⛓️ 中继链"),
            # P2P 去中心化更新系统
            ("update_tab", "ui.decentralized_update_panel", "DecentralizedUpdatePanel", "🌐 P2P更新"),
            # V2.9: 根系装配园
            ("assembler_tab", "ui.assembler_panel", "RootAssemblyGardenPanel", "🌱 嫁接园"),
            # V2.1: AI算力仪表盘
            ("hardware_detector_tab", "ui.hardware_detector_panel", "HardwareDetectorPanel", "🖥️ 算力仪表盘"),
        ]

        for attr_name, module_name, class_name, tab_title in optional_tabs:
            try:
                module = __import__(module_name, fromlist=[class_name])
                panel_class = getattr(module, class_name)
                panel = panel_class()
                setattr(self, attr_name, panel)
                self.center_tabs.addTab(panel, tab_title)
            except Exception as e:
                logger.debug(f"跳过 {tab_title}: {e}")
                setattr(self, attr_name, None)

    def _build_ui(self):
        """兼容旧代码的构建方法"""
        self._build_core_ui()

    def _setup_menu(self):
        """设置菜单栏"""
        # 创建菜单栏（如果需要的话）
        pass
    
    # ── Toast 通知 ───────────────────────────────────────────────────

    def _toggle_toast(self, checked: bool):
        """切换通知"""
        toast_mgr = get_toast_manager(self)
        toast_mgr.enabled = checked
        self._toast_toggle.setText("🔔" if checked else "🔕")
    
    def _show_toast(self, message: str, toast_type: str = "info"):
        """显示通知"""
        toast_mgr = get_toast_manager(self)
        if not toast_mgr.enabled:
            return
        
        from ui.toast_notification import ToastType
        type_map = {
            "success": ToastType.SUCCESS,
            "warning": ToastType.WARNING,
            "error": ToastType.ERROR,
            "info": ToastType.INFO,
        }
        
        toast_mgr.show(message, type_map.get(toast_type, ToastType.INFO))

    # ── 系统大脑 ───────────────────────────────────────────────────

    def _init_system_brain(self):
        """初始化系统大脑"""
        def on_status(msg: str, progress: float):
            self._brain_status.setToolTip(f"系统大脑: {msg}")
            if progress >= 0:
                self.status_bar.setToolTip(f"系统大脑: {msg} ({int(progress*100)}%)")
        
        config = SystemBrainConfig(
            model_name="qwen2.5:0.5b",
            api_base=self.config.ollama.base_url
        )
        
        self.system_brain = get_system_brain(config, status_callback=on_status)
        
        # 异步初始化
        import threading
        def init():
            ready = self.system_brain.check_and_prepare()
            QTimer.singleShot(0, lambda: self._update_brain_status(ready))
        
        threading.Thread(target=init, daemon=True).start()
    
    def _update_brain_status(self, ready: bool):
        """更新系统大脑状态"""
        if ready:
            self._brain_status.setText("🧠")
            self._brain_status.setStyleSheet("color:#22c55e;")
            self._brain_status.setToolTip(f"系统大脑: {self.system_brain.current_model or '已就绪'}")
            self._show_toast("系统大脑已就绪", "success")
        else:
            self._brain_status.setText("🧠⚠")
            self._brain_status.setStyleSheet("color:#f59e0b;")
            self._brain_status.setToolTip("系统大脑未就绪，请确保Ollama正在运行")

    # ── 智能配置 ───────────────────────────────────────────────────

    def _init_smart_config(self):
        """初始化智能配置系统"""
        self._smart_config = get_smart_config(
            use_brain=True,
            brain=self.system_brain if hasattr(self, 'system_brain') else None
        )
        
        # 异步初始化
        import threading
        def init():
            env = self._smart_config.detect_environment()
            suggestions = self._smart_config.analyze_and_suggest()
            QTimer.singleShot(0, lambda: self._update_smart_config_status(env, suggestions))
        
        threading.Thread(target=init, daemon=True).start()
    
    def _update_smart_config_status(self, env, suggestions):
        """更新智能配置状态"""
        profile = self._smart_config.get_profile()
        self._show_toast(
            f"智能配置已就绪 ({profile.name})",
            "info"
        )
        
        # 如果有优化建议，提示用户
        if suggestions:
            self._show_toast(
                f"检测到 {len(suggestions)} 条配置优化建议",
                "info"
            )
    
    # ── 任务进度 ───────────────────────────────────────────────────

    def _init_task_progress(self):
        """初始化任务进度管理器"""
        self._task_progress_manager = get_task_progress_manager(self)
        
        # 注册任务示例（可在需要时调用）
        # 例如：注册下载模型任务
        # self.register_long_task("下载模型", ["下载中", "验证中", "完成"])

    # ── AI 搜索 ───────────────────────────────────────────────────

    def _init_search(self):
        """初始化 AI 搜索工具"""
        # 从配置读取 API Keys（可选）
        serper_key = ""  # self.config.get("search.serper_key", "")
        brave_key = ""   # self.config.get("search.brave_key", "")
        
        # 创建搜索工具
        self._search_tool = AISearchTool(
            serper_key=serper_key,
            brave_key=brave_key,
            cache_ttl=60,  # 缓存 60 分钟
        )
        
        # 绑定到研究面板
        self.research_tab.set_search_tool(self._search_tool)
        
        # 如果有 Ollama 客户端，绑定 LLM 用于 AI 总结
        if self.ollama_client and self.ollama_client.ping():
            self._search_tool.set_llm_client(
                self.ollama_client,
                model=self.config.ollama.default_model or "qwen2.5:7b"
            )
    
    def _update_task_progress(self, task_id: str, progress: float, step: int, total: int):
        """更新任务进度回调"""
        # 可以在这里更新UI元素
        pass
    
    def start_task(self, title: str, steps: list[str] = None, lock_targets: list[str] = None) -> str:
        """
        开始一个需要显示进度的任务
        
        Args:
            title: 任务标题
            steps: 步骤列表
            lock_targets: 需要锁定的UI目标
            
        Returns:
            任务ID
        """
        if not self._task_progress_manager:
            return ""
        
        return self._task_progress_manager.register_task(
            title=title,
            steps=steps,
            lock_targets=lock_targets or [],
            lock_message=f"正在{title}，请稍候...",
            progress_callback=self._update_task_progress,
            complete_callback=lambda: self._show_toast(f"{title}已完成", "success"),
        )
    
    def is_operation_locked(self, target: str = None) -> bool:
        """检查操作是否被锁定"""
        if not self._task_progress_manager:
            return False
        return self._task_progress_manager.is_locked(target)

    def insert_research_to_writing(self):
        """将研究面板内容插入到写作界面"""
        if not self._research_panel:
            return
        
        content = self._research_panel.get_all_content()
        if content:
            # 切换到写作 Tab
            self.center_tabs.setCurrentIndex(1)
            # 插入内容
            if hasattr(self.writing_tab, '_editor'):
                self.writing_tab._editor.insertPlainText("\n\n" + content)
                self._show_toast("研究内容已插入", "success")

    # ── 用户认证 ───────────────────────────────────────────────────

    def _init_auth(self):
        """初始化认证系统"""
        self.auth_dialog = LoginDialog(self)
        self.auth_dialog.login_successful.connect(self._on_user_login)
        self.auth_dialog.logout_signal.connect(self._on_user_logout)
        
        # 检查是否已登录
        if self.auth_dialog.is_logged_in():
            self._on_user_login(self.auth_dialog.get_current_user().id)
    
    def _on_user_login(self, user_id: str):
        """用户登录回调"""
        user = self.auth_dialog.get_current_user()
        if user:
            self._show_toast(f"欢迎回来, {user.username}!", "success")
    
    def _on_user_logout(self):
        """用户登出回调"""
        self._show_toast("已退出登录", "info")

    # ── 配置同步 ───────────────────────────────────────────────

    def _init_config_sync(self):
        """初始化配置同步（启动时自动拉取）"""
        try:
            from core.config_sync import get_sync_manager
            from core.config import load_config as load_local_config, save_config as save_local_config
            import platform

            sync_mgr = get_sync_manager()

            if not sync_mgr.is_logged_in:
                return  # 未登录，不做同步

            # 启动时拉取远程配置（如果有的话）
            remote_configs = sync_mgr.pull_all_configs()
            if not remote_configs:
                return

            # 合并到本地配置
            merged = False
            for key, remote_data in remote_configs.items():
                local_section = getattr(self.config, key, None)
                if local_section and hasattr(local_section, "model_validate"):
                    try:
                        updated = local_section.model_validate(remote_data)
                        setattr(self.config, key, updated)
                        merged = True
                    except Exception:
                        pass

            if merged:
                save_local_config(self.config)
                self._show_toast("配置已从服务器同步", "success")

            # 启动自动同步（每 5 分钟）
            sync_mgr.start_auto_sync(interval=300)

        except Exception:
            pass  # 静默失败，不影响启动

    def _init_a2ui(self):
        """初始化 A2UI 相关组件"""
        # 注册降级处理器
        self._fallback_manager.register_fallback_handler(
            "llm", self._fallback_llm
        )
        self._fallback_manager.register_fallback_handler(
            "api", self._fallback_api
        )
        
        # 注册配置回调
        self._config_quick_edit_manager.register_config_callback(
            "ollama.base_url", self._update_ollama_url
        )
        self._config_quick_edit_manager.register_config_callback(
            "ollama.default_model", self._update_ollama_model
        )
        
        # 初始化全局进度
        self._global_progress = self._progress_manager.create_global_progress(
            "系统启动中", self
        )
        
        # 模拟启动进度
        self._update_startup_progress(0, "初始化系统...")
        QTimer.singleShot(500, lambda: self._update_startup_progress(20, "加载配置..."))
        QTimer.singleShot(1000, lambda: self._update_startup_progress(40, "初始化网络..."))
        QTimer.singleShot(1500, lambda: self._update_startup_progress(60, "加载插件..."))
        QTimer.singleShot(2000, lambda: self._update_startup_progress(80, "初始化 UI..."))
        QTimer.singleShot(2500, lambda: self._update_startup_progress(100, "启动完成"))
        QTimer.singleShot(3000, self._close_startup_progress)
    
    def _fallback_llm(self):
        """LLM 服务降级处理"""
        logger.warning("LLM service unavailable, falling back to local mode")
        self._show_toast("LLM 服务不可用，已切换到本地模式", "warning")
        # 这里可以实现本地模式的逻辑
        return True
    
    def _fallback_api(self):
        """API 服务降级处理"""
        logger.warning("API service unavailable, falling back to offline mode")
        self._show_toast("API 服务不可用，已切换到离线模式", "warning")
        # 这里可以实现离线模式的逻辑
        return True
    
    def _update_ollama_url(self, value):
        """更新 Ollama URL 配置"""
        self.config.ollama.base_url = value
        save_config(self.config)
        self._show_toast(f"Ollama URL 已更新为: {value}", "success")
    
    def _update_ollama_model(self, value):
        """更新 Ollama 模型配置"""
        self.config.ollama.default_model = value
        save_config(self.config)
        self._show_toast(f"默认模型已更新为: {value}", "success")
    
    def _update_startup_progress(self, progress, text):
        """更新启动进度"""
        if hasattr(self, '_global_progress'):
            self._progress_manager.update_global_progress(progress, text)
    
    def _close_startup_progress(self):
        """关闭启动进度"""
        self._progress_manager.close_global_progress()

    # ── Agent ───────────────────────────────────────────────────

    def _init_agent(self):
        self.ollama_client = OllamaClient(self.config.ollama)
        # 检查 Ollama 是否可用
        if not self.ollama_client.ping():
            # 执行降级处理
            self._fallback_manager.fallback("llm", "Ollama 服务不可用")
        self._update_status()
        QTimer.singleShot(3000, self._update_status)

    def _update_status(self):
        online = self.ollama_client.ping()
        if online:
            v = self.ollama_client.version()
            m = self.config.ollama.default_model or "未选模型"
            self._status_text.setText(f"Ollama {v} — {m}")
            self._status_indicator.setText("🟢")
            self._status_indicator.setStyleSheet("color:#22c55e;")
        else:
            self._status_text.setText("⚠ Ollama 未运行 — 请启动 ollama serve")
            self._status_indicator.setText("🔴")
            self._status_indicator.setStyleSheet("color:#ef4444;")
            
        # 检查是否处于降级模式
        if self._fallback_manager.is_fallback_active():
            self._status_text.setText(f"{self._status_text.text()} | 降级模式")
            self._status_indicator.setText("🟡")
            self._status_indicator.setStyleSheet("color:#f59e0b;")

    # ── 会话 ───────────────────────────────────────────────────

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
            QMessageBox.warning(self, "请等待", "请等待当前响应结束后再切换会话")
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
        
        # 更新写作 Tab 的 Agent
        if hasattr(self, 'writing_tab'):
            self.writing_tab.set_agent(self._agent)

    # ── 消息 ───────────────────────────────────────────────────

    def _on_send_message(self, text: str):
        # V2.0: 检查是否被任务锁定
        if self.is_operation_locked("chat"):
            self._show_toast("当前有任务正在执行，请稍后再试", "warning")
            return
        
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
                self._streaming = False

        threading.Thread(target=run, daemon=True).start()

    def _on_stop(self):
        if self._agent:
            self._agent.interrupt()
        self._streaming = False
        self.chat_panel.set_running(False)

    # ── 回调 ───────────────────────────────────────────────────

    def _on_stream_delta(self, delta: str):
        QTimer.singleShot(0, lambda: self.chat_panel.append_token(delta))

    def _on_thinking(self, delta: str):
        pass

    def _on_tool_start(self, name: str, args_str: str):
        QTimer.singleShot(0, lambda: self.chat_panel.add_tool_block(name, args_str))

    def _on_tool_result(self, name: str, result: str, success: bool):
        QTimer.singleShot(0, lambda: self.chat_panel.finish_tool_block(name, result, success))

    # ── 状态变化 ───────────────────────────────────────────────────

    def _on_status_changed(self, msg: str):
        """写作 Tab 状态变化"""
        self.status_bar.setText(msg)

    def _on_design_approved(self, session_id: str):
        """头脑风暴设计批准后"""
        self.status_bar.setText(f"🎉 设计已批准 (会话ID: {session_id[:8]}...)")
        toast_success(self, "设计已批准！", "现在可以开始实现了。")

    def show_brainstorm_panel(self):
        """打开头脑风暴面板（由ChatPanel调用）"""
        if hasattr(self, 'brainstorm_tab') and self.brainstorm_tab:
            # 找到头脑风暴面板的索引并切换
            for i in range(self.center_tabs.count()):
                if self.center_tabs.widget(i) == self.brainstorm_tab:
                    self.center_tabs.setCurrentIndex(i)
                    break

    # ── 写作模式切换 ───────────────────────────────────────────────────

    def _enter_writing_mode(self, content: str = ""):
        """进入写作模式"""
        self.center_tabs.setCurrentIndex(1)  # 切换到写作 Tab
        if content and hasattr(self, 'writing_tab'):
            self.writing_tab._editor.setPlainText(content)
    
    def _enter_chat_mode(self):
        """返回聊天模式"""
        self.center_tabs.setCurrentIndex(0)
    
    # ── 设置对话框 ───────────────────────────────────────────────────

    def _show_settings(self, link_path: str | None = None):
        """
        显示设置对话框

        Args:
            link_path: 可选的 Tab 路径，用于直接导航到指定设置页面
        """
        dialog = SettingsDialog(self, self.config)

        # 如果指定了 link_path，先导航到对应 tab
        if link_path:
            dialog.navigate_to(link_path)

        # 保存后重新加载配置
        if dialog.exec():
            self.config = load_config()
            self._show_toast("设置已保存", "success")

            # 保存后更新 Ollama 配置
            self.ollama_client = OllamaClient(self.config.ollama)
            self._update_status()

            # 自动推送到配置同步服务器（如果已登录）
            try:
                from core.config_sync import get_sync_manager
                sync_mgr = get_sync_manager()
                if sync_mgr.is_logged_in:
                    configs = {}
                    for key in ["ollama", "model_market", "search", "agent", "writing"]:
                        section = getattr(self.config, key, None)
                        if section and hasattr(section, "model_dump"):
                            configs[key] = section.model_dump()
                    sync_mgr.push_all_configs(configs)
            except Exception:
                pass  # 静默失败，不影响主流程
