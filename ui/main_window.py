"""
主窗口 — 三栏布局 + 底部状态栏
集成：聊天、写作助手Tab、用户认证、配置导入导出
V2.0 新增：MCP管理、Skill市场、任务进度、数字分身、LAN聊天
"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QLabel, QMessageBox, QStackedWidget, QTabWidget,
    QPushButton, QMenuBar, QMenu,
)
from PyQt6.QtGui import QKeyEvent, QAction, QIcon

from core.config import AppConfig, load_config, save_config
from core.agent import HermesAgent, AgentCallbacks
from core.ollama_client import OllamaClient
from core.session_db import SessionDB
from core.system_brain import get_system_brain, SystemBrainConfig
from core.config_manager import get_config_manager
from core.auth_system import get_auth_system
from core.smart_config import get_smart_config
from ui.task_progress import get_task_progress_manager
from core.search_tool import AISearchTool

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
from ui.mailbox.mailbox_panel import MailboxPanel
# V2.3: P2P连接器 (短ID寻址 + 多通道通信)
from ui.connector.connector_panel import ConnectorPanel
# V2.4: 统一聊天 (Element/Discord/Telegram风格)
from ui.unified_chat.chat_panel import ChatPanel
# V2.5: 翻译中心 (离线初翻 + 在线精翻)
from ui.translation.translation_panel import TranslationPanel
# V2.6: 去中心化论坛 (P2P穿透网络 + 智能写作)
from ui.forum.forum_panel import ForumPanel
# V2.7: 伪域名系统 (去中心化域名 + DNS解析)
from ui.pseudodomain.domain_panel import DomainPanel
# V2.8: 元宇宙UI (舰桥操作系统 - 时空引力场)
from ui.metaverse_ui_panel import MetaverseUIPanel

# 需求头脑风暴 (借鉴 obra/superpowers 设计思路)
from ui.idea_clarifier_panel import IdeaClarifierPanel
# 政府开放资料查询 (借鉴 gov_openapi_agent 设计思路)
from ui.gov_data_panel import GovDataPanel
# 公司印章生成器 (借鉴 company-stamp 设计思路)
from ui.stamp_panel import StampPanel
# 中继链 - 分布式积分账本 (无币无挖矿类区块链)
from ui.relay_chain_panel import RelayChainPanel
# V3.0: 根系同步 (Root Sync - Syncthing 风格去中心化文件同步)
from ui.root_sync_panel import RootSyncPanel
# V3.1: GitHub Store (桌面代码仓库 - 发现安装 GitHub Release 桌面应用)
from ui.github_store_panel import GitHubStorePanel
# V3.2: Database Browser (桌面数据库管理 - onetcli 风格多数据库管理)
from ui.database_browser_panel import DatabaseBrowserPanel
# V3.3: Preview Panel (Office 文档实时预览与编辑 - AionUi 风格)
from ui.preview_panel import PreviewPanel
# V2.0: MCP Market 面板
from ui.mcp_market_panel import MCPMarketPanel
# V2.0: Skill Market 面板
from ui.skill_market_panel import SkillMarketPanel
# V2.0: Digital Avatar 面板
from ui.avatar_panel import AvatarPanel
# 环保模型商店面板 (P2P模型分发 + API Key自动配置)
from ui.model_store_panel import ModelStorePanel
# 🔐 IdentityPanel - 身份驱动的数据主权 UI
from ui.identity_panel import IdentityPanel
# 📚 私有法规库检索面板 (Chroma/Milvus + all-MiniLM-L6-v2)
from ui.regulation_search_panel import RegulationSearchPanel
# 🏛️ 社区共建者权益中心 (积分->权益转换 + 税务合规 + 基金透明)
from ui.community_rights_panel import CommunityRightsPanel
# 🤖 AI脚本生成器 (自然语言→可执行脚本 + 沙箱执行 + 脚本市场)
from ui.ai_script_panel import AIScriptPanel
# 🌐 P2P 去中心化更新系统面板
from ui.decentralized_update_panel import DecentralizedUpdatePanel
# V2.0: LAN Chat 面板
from ui.lan_chat_panel import LANChatPanel
# V2.0: Smart IDE 面板
from ui.smart_ide_panel import SmartIDEPanel
# V2.0: Game Room 面板
from ui.game_room_panel import GameRoomPanel
# 🎮 融合游戏系统 (暗黑地牢 + 狼人杀 + 密室逃脱)
from ui.dungeon_werewolf_escape_panel import FusionGamePanel
# 🎭 虚拟形象与社交广场系统
from ui.virtual_avatar_social_panel import VirtualAvatarSocialPanel
# 🃏 斗地主游戏系统
from ui.dou_di_zhu_panel import DouDiZhuPanel
# 🌐 P2P网络自举协议
from ui.p2p_bootstrap_panel import P2PBootstrapPanel
# 🌌 通用数字永生系统 - Phoenix Protocol
from ui.phoenix_protocol_panel import PhoenixProtocolPanel
# 🎛️ 通用硬件智能集成系统 - Hardware Mind
from ui.hardware_mind_panel import HardwareMindPanel
# 🐍 Python智能日志分析系统 - Python Mind
from ui.python_mind_panel import PythonMindPanel
# 🧹 智能临时文件清理系统 - Smart Cleanup
from ui.smart_cleanup_panel import SmartCleanupPanel
# 🤖 AI驱动式界面自检与优化系统 - UI Self-Check
from ui.ui_self_check_panel import UISelfCheckPanel
# 🔐 智能授权与实名认证系统 - Activation License
from ui.activation_license_panel import ActivationLicensePanel
# V2.0: Knowledge Blockchain 面板
from ui.knowledge_blockchain_panel import KnowledgeBlockchainPanel
# L4 执行层监控面板
from ui.l4_executor_panel import L4ExecutorPanel
# SmolLM2 L0 快反大脑面板
from ui.smolllm2_panel import SmolLM2Panel
# 智能提示系统面板
from ui.intelligent_hints_panel import IntelligentHintsPanel
# 思维审核与自我进化面板
from ui.thought_audit_panel import ThoughtAuditPanel
# 聚合推荐首页面板
from ui.feed_home_panel import FeedHomePanel
# 认知框架协作者面板
from ui.cognitive_framework_panel import CognitiveFrameworkPanel
# 消息模式面板
from ui.message_pattern_panel import MessagePatternPanel
# 聚合推荐面板
from ui.aggregator_panel import AggregatorPanel
# 归档工具面板
from ui.archive_tool_panel import ArchiveToolPanel
# 云盘面板
from ui.cloud_disk_panel import CloudDiskPanel
# 提佣系统面板
from ui.commission_panel import CommissionPanel
# 专业审核增强面板
from ui.creative_review_panel import CreativeReviewPanel
# 决策支持面板
from ui.decision_panel import DecisionSupportPanel
# 增强任务面板
from ui.enhanced_task_panel import EnhancedTaskPanel
# Karpathy规则面板
from ui.karpathy_panel import KarpathyRulesPanel
# 轻量级UI面板
from ui.lightweight_ui_panel import LightweightUIPanel
# Markdown转Doc面板
from ui.md_to_doc_panel import MarkdownToDocPanel
# P2P广播面板
from ui.p2p_broadcast_panel import P2PBroadcastPanel
# 用户画像面板
from ui.profile_panel import ProfilePanel
# 模型提供商面板
from ui.provider_panel import ProviderPanel
# 智能推荐面板
from ui.recommendation_panel import RecommendationPanel
# 中继面板
from ui.relay_panel import RelayPanel
# 安全诊断面板
from ui.security_diagnostic_panel import SecurityDiagnosticPanel
# 智能助手面板
from ui.smart_assistant_panel import SmartAssistantPanel
# 智能写作面板
from ui.smart_writing_panel import SmartWritingPanel
# 社交电商面板
from ui.social_commerce_panel import SocialCommercePanel
# 状态面板
from ui.status_panel import StatusPanel
# Toonflow短剧面板
from ui.toonflow_panel import ToonflowPanel
# URL智能优化面板
from ui.url_intelligence_panel import URLIntelligencePanel
# 写作助手面板
from ui.writing_assistant_panel import WritingAssistantPanel


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

        self._build_ui()
        self._init_agent()
        self._init_system_brain()
        self._init_smart_config()
        self._init_task_progress()
        self._init_search()
        self._init_sessions()
        self._init_auth()
        self._init_config_sync()
        self._setup_menu()

        self.setWindowTitle("Hermes Desktop v2.0")
        self.resize(config.window_width, config.window_height)

    # ── UI ─────────────────────────────────────────────────────

    def _build_ui(self):
        self.setMinimumSize(900, 600)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：会话面板
        self.session_panel = SessionPanel()
        self.session_panel.new_chat_requested.connect(self._new_chat)
        self.session_panel.session_selected.connect(self._load_session)
        self.session_panel.session_deleted.connect(self._delete_session)
        self.session_panel.settings_requested.connect(self._show_settings)
        self.splitter.addWidget(self.session_panel)

        # 中央：Tab 切换
        self.center_tabs = QTabWidget()
        self.center_tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.center_tabs.setDocumentMode(True)
        
        # 聊天页面
        self.chat_panel = ChatPanel()
        self.chat_panel.send_requested.connect(self._on_send_message)
        self.chat_panel.stop_requested.connect(self._on_stop)
        self.chat_panel.switch_to_writing.connect(self._enter_writing_mode)
        self.chat_panel.config_hint_requested.connect(self._show_settings)
        self.center_tabs.addTab(self.chat_panel, "💬 聊天")
        
        # 写作助手页面
        self.writing_tab = WritingTab(self, self._agent)
        self.writing_tab.status_changed.connect(self._on_status_changed)
        self.center_tabs.addTab(self.writing_tab, "✍️ 写作助手")

        # V2.0: 研究搜索页面
        self.research_tab = ResearchPanel()
        self.center_tabs.addTab(self.research_tab, "🔍 研究助手")

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

        # V2.1: 全源情报中心 (搜索+谣言检测+竞品监控+预警+报告)
        self.intelligence_tab = IntelligencePanel()
        self.center_tabs.addTab(self.intelligence_tab, "🎯 情报中心")

        # V2.2: 去中心化邮箱 (P2P邮件, 无SMTP)
        self.mailbox_tab = MailboxPanel()
        self.center_tabs.addTab(self.mailbox_tab, "📧 去中心化邮箱")

        # V2.3: P2P连接器 (短ID寻址 + 多通道通信)
        self.connector_tab = ConnectorPanel()
        self.center_tabs.addTab(self.connector_tab, "🔗 P2P连接")

        # V2.4: 统一聊天 (Element/Discord/Telegram风格)
        self.chat_tab = ChatPanel()
        self.center_tabs.addTab(self.chat_tab, "💬 统一聊天")

        # V2.5: 翻译中心 (离线初翻 + 在线精翻)
        self.translation_tab = TranslationPanel()
        self.center_tabs.addTab(self.translation_tab, "🔄 翻译中心")

        # V2.6: 去中心化论坛 (P2P穿透网络 + 智能写作)
        self.forum_tab = ForumPanel()
        self.center_tabs.addTab(self.forum_tab, "🏛️ 去中心化论坛")

        # V2.7: 伪域名系统 (去中心化域名 + DNS解析)
        self.domain_tab = DomainPanel()
        self.center_tabs.addTab(self.domain_tab, "🌐 伪域名")

        # V2.0: CLI-Anything 工具工厂
        try:
            from ui.cli_anything_panel import CLIAutoGenPanel
            self.cli_anything_tab = CLIAutoGenPanel()
            self.center_tabs.addTab(self.cli_anything_tab, "⚡ 工具工厂")
        except ImportError:
            self.cli_anything_tab = None

        # V2.0: WebRTC 视频通话与直播
        try:
            from ui.webrtc_panel import WebRTCPanel
            self.webrtc_tab = WebRTCPanel()
            self.center_tabs.addTab(self.webrtc_tab, "📞 视频通话")
        except ImportError as e:
            self.webrtc_tab = None

        # V2.0: 视频播放器 (LibVLC - Screenbox 同款引擎)
        try:
            from ui.video_player_panel import VideoPlayerPanel
            self.video_player_tab = VideoPlayerPanel()
            self.center_tabs.addTab(self.video_player_tab, "🎬 视频播放")
        except ImportError as e:
            self.video_player_tab = None

        # V2.0: P2P 去中心化电商 (DeCommerce)
        try:
            from ui.decommerce_panel import DeCommercePanel
            self.decommerce_tab = DeCommercePanel()
            self.center_tabs.addTab(self.decommerce_tab, "🛍️ DeCommerce")
        except ImportError as e:
            self.decommerce_tab = None

        # V2.0: 去中心化本地商品交易市场
        from core.local_market.ui.panel import LocalMarketPanel
        self.local_market_tab = LocalMarketPanel()
        self.center_tabs.addTab(self.local_market_tab, "🛒 本地市场")

        # V2.8: 元宇宙UI (舰桥操作系统 - 时空引力场)
        try:
            self.metaverse_tab = MetaverseUIPanel()
            self.center_tabs.addTab(self.metaverse_tab, "🚀 舰桥")
        except Exception as e:
            self.metaverse_tab = None

        # 需求头脑风暴 (HARD-GATE: 设计批准前不执行实现)
        try:
            self.brainstorm_tab = IdeaClarifierPanel()
            self.brainstorm_tab.design_approved.connect(self._on_design_approved)
            self.center_tabs.addTab(self.brainstorm_tab, "🎯 头脑风暴")
        except Exception as e:
            logger.error(f"Failed to load IdeaClarifierPanel: {e}")
            self.brainstorm_tab = None

        # 政府开放资料查询 (借鉴 gov_openapi_agent 设计思路)
        try:
            self.gov_data_tab = GovDataPanel()
            self.center_tabs.addTab(self.gov_data_tab, "🏛️ 政府资料")
        except Exception as e:
            logger.error(f"Failed to load GovDataPanel: {e}")
            self.gov_data_tab = None

        # 公司印章生成器 (借鉴 company-stamp 设计思路)
        try:
            self.stamp_tab = StampPanel()
            self.center_tabs.addTab(self.stamp_tab, "🔐 印章生成")
        except Exception as e:
            logger.error(f"Failed to load StampPanel: {e}")
            self.stamp_tab = None

        # 中继链 - 分布式积分账本 (无币无挖矿类区块链)
        try:
            self.relay_chain_tab = RelayChainPanel()
            self.center_tabs.addTab(self.relay_chain_tab, "⛓️ 中继链")
        except Exception as e:
            logger.error(f"Failed to load RelayChainPanel: {e}")
            self.relay_chain_tab = None

        # 🌐 P2P 去中心化更新系统 (抗审查 + 高可用 + 区块链思想)
        try:
            self.update_tab = DecentralizedUpdatePanel()
            self.center_tabs.addTab(self.update_tab, "🌐 P2P更新")
        except Exception as e:
            logger.error(f"Failed to load DecentralizedUpdatePanel: {e}")
            self.update_tab = None

        # V2.9: 根系装配园 (Root Assembly Garden)
        try:
            from ui.assembler_panel import RootAssemblyGardenPanel
            self.assembler_tab = RootAssemblyGardenPanel()
            self.center_tabs.addTab(self.assembler_tab, "🌱 嫁接园")
        except Exception as e:
            self.assembler_tab = None

        # V2.1: AI算力仪表盘 (硬件检测与模型匹配)
        try:
            from ui.hardware_detector_panel import HardwareDetectorPanel
            self.hardware_detector_tab = HardwareDetectorPanel()
            self.center_tabs.addTab(self.hardware_detector_tab, "🖥️ 算力仪表盘")
        except ImportError as e:
            self.hardware_detector_tab = None

        # V2.0: PageIndex 智能文档索引 (LLM Wiki 架构)
        from core.page_index.ui.panel import PageIndexPanel
        self.page_index_tab = PageIndexPanel()
        self.center_tabs.addTab(self.page_index_tab, "📑 文档索引")

        # V3.0: 根系同步 (Root Sync - Syncthing 风格去中心化文件同步)
        try:
            self.root_sync_tab = RootSyncPanel()
            self.center_tabs.addTab(self.root_sync_tab, "🌳 根系同步")
        except Exception as e:
            self.root_sync_tab = None

        # V3.1: GitHub Store (桌面代码仓库)
        try:
            self.github_store_tab = GitHubStorePanel()
            self.center_tabs.addTab(self.github_store_tab, "🛍️ GitHub商店")
        except Exception as e:
            self.github_store_tab = None

        # V3.2: Database Browser (桌面数据库管理)
        try:
            self.database_browser_tab = DatabaseBrowserPanel()
            self.center_tabs.addTab(self.database_browser_tab, "🗄️ 数据库")
        except Exception as e:
            self.database_browser_tab = None

        # V3.3: Preview Panel (Office 文档实时预览与编辑)
        try:
            self.preview_tab = PreviewPanel()
            self.center_tabs.addTab(self.preview_tab, "📄 预览")
        except Exception as e:
            self.preview_tab = None

        # V2.0: MCP Market 面板 (MCP订阅/发布架构 + MCP市场浏览)
        try:
            self.mcp_market_tab = MCPMarketPanel()
            self.center_tabs.addTab(self.mcp_market_tab, "🔌 MCP市场")
        except Exception as e:
            self.mcp_market_tab = None

        # V2.0: Skill Market 面板 (SKILL.md manifest格式 + Skill安装/卸载/更新)
        try:
            self.skill_market_tab = SkillMarketPanel()
            self.center_tabs.addTab(self.skill_market_tab, "🛠️ Skill市场")
        except Exception as e:
            self.skill_market_tab = None

        # V2.0: Digital Avatar 面板 (三层分身模型 + 成长系统 + 主动交互)
        try:
            self.avatar_tab = AvatarPanel()
            self.center_tabs.addTab(self.avatar_tab, "🎭 数字分身")
        except Exception as e:
            self.avatar_tab = None

        # 🏭 环保模型商店 (P2P模型分发 + 中继链网络 + API Key自动配置)
        try:
            self.model_store_tab = ModelStorePanel()
            self.center_tabs.addTab(self.model_store_tab, "🏭 模型商店")
        except Exception as e:
            self.model_store_tab = None

        # 🔐 IdentityPanel - 身份驱动的数据主权 UI
        # (身份管理/设备列表/同步状态/云端备份/私有服务器配置)
        try:
            self.identity_tab = IdentityPanel()
            self.center_tabs.addTab(self.identity_tab, "🔐 身份中心")
        except Exception as e:
            self.identity_tab = None

        # 📚 私有法规库检索面板 (Chroma/Milvus + all-MiniLM-L6-v2)
        # 支持法规语义检索、混合检索、元数据过滤
        try:
            self.regulation_tab = RegulationSearchPanel()
            self.center_tabs.addTab(self.regulation_tab, "📚 法规库")
        except Exception as e:
            self.regulation_tab = None

        # 🏛️ 社区共建者权益中心 (积分->权益转换 + 税务合规 + 基金透明)
        # 核心理念：积分永不兑现现金，收益转化为社区发展基金，去金融化
        try:
            self.community_rights_tab = CommunityRightsPanel()
            self.center_tabs.addTab(self.community_rights_tab, "🏛️ 权益中心")
        except Exception as e:
            self.community_rights_tab = None

        # 🤖 AI脚本生成器 (自然语言→可执行脚本 + 沙箱执行 + 脚本市场)
        # 核心理念：用户用自然语言描述需求，AI生成可执行脚本
        try:
            self.ai_script_tab = AIScriptPanel()
            self.center_tabs.addTab(self.ai_script_tab, "🤖 AI脚本")
        except Exception as e:
            self.ai_script_tab = None

        # V2.0: LAN Chat 面板 (UDP广播发现 + TCP消息传输 + AI自动回复)
        try:
            self.lan_chat_tab = LANChatPanel()
            self.center_tabs.addTab(self.lan_chat_tab, "💬 LAN聊天")
        except Exception as e:
            self.lan_chat_tab = None

        # V2.0: Smart IDE 面板 (代码编辑器 + AI编程助手 + 调试系统)
        try:
            self.smart_ide_tab = SmartIDEPanel()
            self.center_tabs.addTab(self.smart_ide_tab, "💻 智能IDE")
        except Exception as e:
            self.smart_ide_tab = None

        # V2.0: Game Room 面板 (游戏房间 + 玩家匹配 + 录像截图)
        try:
            self.game_room_tab = GameRoomPanel()
            self.center_tabs.addTab(self.game_room_tab, "🎮 游戏大厅")
        except Exception as e:
            self.game_room_tab = None

        # V2.0: Knowledge Blockchain 面板 (知识区块链 + 共识引擎 + 代币经济)
        try:
            self.knowledge_blockchain_tab = KnowledgeBlockchainPanel()
            self.center_tabs.addTab(self.knowledge_blockchain_tab, "⛓️ 知识链")
        except Exception as e:
            self.knowledge_blockchain_tab = None

        # 🎮 融合游戏系统 (暗黑地牢 + 狼人杀 + 密室逃脱)
        try:
            from core.dungeon_werewolf_escape import FusionGameEngine
            self.fusion_game_engine = FusionGameEngine()
            self.fusion_game_tab = FusionGamePanel()
            self.fusion_game_tab.set_game_engine(self.fusion_game_engine)
            self.center_tabs.addTab(self.fusion_game_tab, "🎯 融合游戏")
        except Exception as e:
            self.fusion_game_tab = None
            self.fusion_game_engine = None

        # 🎭 虚拟形象与社交广场系统
        try:
            from core.virtual_avatar_social import VirtualAvatarSocialEngine
            self.avatar_social_engine = VirtualAvatarSocialEngine()
            self.avatar_social_tab = VirtualAvatarSocialPanel()
            self.avatar_social_tab.set_avatar_engine(self.avatar_social_engine)
            self.center_tabs.addTab(self.avatar_social_tab, "🎭 形象广场")
        except Exception as e:
            self.avatar_social_tab = None
            self.avatar_social_engine = None

        # 🃏 斗地主游戏系统
        try:
            from core.dou_di_zhu import DouDiZhuEngine
            self.dou_dizhu_engine = DouDiZhuEngine()
            self.dou_dizhu_tab = DouDiZhuPanel()
            self.dou_dizhu_tab.set_engine(self.dou_dizhu_engine)
            self.center_tabs.addTab(self.dou_dizhu_tab, "🃏 斗地主")
        except Exception as e:
            self.dou_dizhu_tab = None
            self.dou_dizhu_engine = None

        # 🌐 P2P网络自举协议 (感染式网络)
        try:
            from core.p2p_network_bootstrap import P2PNetworkBootstrapEngine
            self.p2p_bootstrap_engine = P2PNetworkBootstrapEngine(
                node_id=f"node_{uuid.uuid4().hex[:8]}",
                node_url=f"ws://localhost:8888/node"
            )
            self.p2p_bootstrap_tab = P2PBootstrapPanel()
            self.p2p_bootstrap_tab.set_engine(self.p2p_bootstrap_engine)
            self.center_tabs.addTab(self.p2p_bootstrap_tab, "🌐 P2P网络")
        except Exception as e:
            self.p2p_bootstrap_tab = None
            self.p2p_bootstrap_engine = None

        # 🌌 通用数字永生系统 - Phoenix Protocol
        # 核心理念："网络可死，基因永生；载体可灭，灵魂不灭"
        try:
            from core.phoenix_protocol import PhoenixProtocolEngine
            self.phoenix_engine = PhoenixProtocolEngine({
                "node_id": f"phoenix_{uuid.uuid4().hex[:8]}"
            })
            self.phoenix_tab = PhoenixProtocolPanel()
            self.phoenix_tab.phoenix_engine = self.phoenix_engine
            self.center_tabs.addTab(self.phoenix_tab, "🌌 数字永生")
        except Exception as e:
            self.phoenix_tab = None
            self.phoenix_engine = None

        # 🎛️ 通用硬件智能集成系统 - Hardware Mind
        # 核心理念："硬件即插件，自动发现、自动学习、自动集成"
        try:
            from core.hardware_mind import HardwareMindEngine
            self.hardware_mind_engine = HardwareMindEngine({
                "node_id": f"hardwaremind_{uuid.uuid4().hex[:8]}"
            })
            self.hardware_mind_tab = HardwareMindPanel()
            self.hardware_mind_tab.set_engine(self.hardware_mind_engine)
            self.center_tabs.addTab(self.hardware_mind_tab, "🎛️ 硬件智能")
        except Exception as e:
            self.hardware_mind_tab = None
            self.hardware_mind_engine = None

        # 🐍 Python智能日志分析系统 - Python Mind
        # 核心理念："从错误中学习，从日志中洞察，自动诊断，智能修复"
        try:
            from core.python_mind import PythonMindEngine
            self.python_mind_engine = PythonMindEngine({
                "node_id": f"pythonmind_{uuid.uuid4().hex[:8]}"
            })
            self.python_mind_tab = PythonMindPanel()
            self.python_mind_tab.set_engine(self.python_mind_engine)
            self.center_tabs.addTab(self.python_mind_tab, "🐍 Python日志")
        except Exception as e:
            self.python_mind_tab = None
            self.python_mind_engine = None

        # 🧹 智能临时文件清理系统 - Smart Cleanup
        # 核心理念："不是简单的删除，而是智能的资产管理"
        try:
            self.smart_cleanup_tab = SmartCleanupPanel()
            self.center_tabs.addTab(self.smart_cleanup_tab, "🧹 智能清理")
        except Exception as e:
            self.smart_cleanup_tab = None

        # L4 执行层监控 (RelayFreeLLM 网关监控)
        try:
            self.l4_executor_tab = L4ExecutorPanel()
            self.center_tabs.addTab(self.l4_executor_tab, "⚡ L4执行层")
        except Exception as e:
            self.l4_executor_tab = None

        # SmolLM2 L0 快反大脑 (意图路由 <1s 响应)
        try:
            self.smolllm2_tab = SmolLM2Panel()
            self.center_tabs.addTab(self.smolllm2_tab, "🧠 SmolLM2")
        except Exception as e:
            self.smolllm2_tab = None

        # 智能提示系统 (全局交互版)
        try:
            self.intelligent_hints_tab = IntelligentHintsPanel()
            self.center_tabs.addTab(self.intelligent_hints_tab, "💡 智能提示")
        except Exception as e:
            self.intelligent_hints_tab = None

        # 思维审核与自我进化
        try:
            self.thought_audit_tab = ThoughtAuditPanel()
            self.center_tabs.addTab(self.thought_audit_tab, "🔬 思维审核")
        except Exception as e:
            self.thought_audit_tab = None

        # 聚合推荐首页
        try:
            self.feed_home_tab = FeedHomePanel()
            self.center_tabs.addTab(self.feed_home_tab, "🏠 推荐首页")
        except Exception as e:
            self.feed_home_tab = None

        # 认知框架协作者
        try:
            self.cognitive_framework_tab = CognitiveFrameworkPanel()
            self.center_tabs.addTab(self.cognitive_framework_tab, "🧩 认知框架")
        except Exception as e:
            self.cognitive_framework_tab = None

        # 消息模式与提示词系统
        try:
            self.message_pattern_tab = MessagePatternPanel()
            self.center_tabs.addTab(self.message_pattern_tab, "📝 消息模式")
        except Exception as e:
            self.message_pattern_tab = None

        # 聚合推荐面板
        try:
            self.aggregator_tab = AggregatorPanel()
            self.center_tabs.addTab(self.aggregator_tab, "📰 聚合推荐")
        except Exception as e:
            self.aggregator_tab = None

        # 归档工具面板
        try:
            self.archive_tool_tab = ArchiveToolPanel()
            self.center_tabs.addTab(self.archive_tool_tab, "📦 归档工具")
        except Exception as e:
            self.archive_tool_tab = None

        # 云盘面板
        try:
            self.cloud_disk_tab = CloudDiskPanel()
            self.center_tabs.addTab(self.cloud_disk_tab, "☁️ 云盘")
        except Exception as e:
            self.cloud_disk_tab = None

        # 提佣系统面板
        try:
            self.commission_tab = CommissionPanel()
            self.center_tabs.addTab(self.commission_tab, "💰 提佣")
        except Exception as e:
            self.commission_tab = None

        # 专业审核增强面板
        try:
            self.creative_review_tab = CreativeReviewPanel()
            self.center_tabs.addTab(self.creative_review_tab, "✅ 专业审核")
        except Exception as e:
            self.creative_review_tab = None

        # 决策支持面板
        try:
            self.decision_tab = DecisionSupportPanel()
            self.center_tabs.addTab(self.decision_tab, "🎯 决策支持")
        except Exception as e:
            self.decision_tab = None

        # 增强任务面板
        try:
            self.enhanced_task_tab = EnhancedTaskPanel()
            self.center_tabs.addTab(self.enhanced_task_tab, "🚀 增强任务")
        except Exception as e:
            self.enhanced_task_tab = None

        # Karpathy规则面板
        try:
            self.karpathy_tab = KarpathyRulesPanel()
            self.center_tabs.addTab(self.karpathy_tab, "📚 Karpathy")
        except Exception as e:
            self.karpathy_tab = None

        # 轻量级UI面板
        try:
            self.lightweight_ui_tab = LightweightUIPanel()
            self.center_tabs.addTab(self.lightweight_ui_tab, "🪶 轻量UI")
        except Exception as e:
            self.lightweight_ui_tab = None

        # Markdown转Doc面板
        try:
            self.md_to_doc_tab = MarkdownToDocPanel()
            self.center_tabs.addTab(self.md_to_doc_tab, "📄 MD转Word")
        except Exception as e:
            self.md_to_doc_tab = None

        # P2P广播面板
        try:
            self.p2p_broadcast_tab = P2PBroadcastPanel()
            self.center_tabs.addTab(self.p2p_broadcast_tab, "📡 P2P广播")
        except Exception as e:
            self.p2p_broadcast_tab = None

        # 用户画像面板
        try:
            self.profile_tab = ProfilePanel()
            self.center_tabs.addTab(self.profile_tab, "👤 用户画像")
        except Exception as e:
            self.profile_tab = None

        # 模型提供商面板
        try:
            self.provider_tab = ProviderPanel()
            self.center_tabs.addTab(self.provider_tab, "🔧 提供商")
        except Exception as e:
            self.provider_tab = None

        # 智能推荐面板
        try:
            self.recommendation_tab = RecommendationPanel()
            self.center_tabs.addTab(self.recommendation_tab, "🎬 智能推荐")
        except Exception as e:
            self.recommendation_tab = None

        # 中继面板
        try:
            self.relay_tab = RelayPanel()
            self.center_tabs.addTab(self.relay_tab, "🔄 中继")
        except Exception as e:
            self.relay_tab = None

        # 安全诊断面板
        try:
            self.security_diagnostic_tab = SecurityDiagnosticPanel()
            self.center_tabs.addTab(self.security_diagnostic_tab, "🛡️ 安全诊断")
        except Exception as e:
            self.security_diagnostic_tab = None

        # 智能助手面板
        try:
            self.smart_assistant_tab = SmartAssistantPanel()
            self.center_tabs.addTab(self.smart_assistant_tab, "🤖 智能助手")
        except Exception as e:
            self.smart_assistant_tab = None

        # 智能写作面板
        try:
            self.smart_writing_tab = SmartWritingPanel()
            self.center_tabs.addTab(self.smart_writing_tab, "✍️ 智能写作")
        except Exception as e:
            self.smart_writing_tab = None

        # 社交电商面板
        try:
            self.social_commerce_tab = SocialCommercePanel()
            self.center_tabs.addTab(self.social_commerce_tab, "🛒 社交电商")
        except Exception as e:
            self.social_commerce_tab = None

        # 状态面板
        try:
            self.status_tab = StatusPanel()
            self.center_tabs.addTab(self.status_tab, "📊 状态")
        except Exception as e:
            self.status_tab = None

        # Toonflow短剧面板
        try:
            self.toonflow_tab = ToonflowPanel()
            self.center_tabs.addTab(self.toonflow_tab, "🎭 短剧")
        except Exception as e:
            self.toonflow_tab = None

        # URL智能优化面板
        try:
            self.url_intelligence_tab = URLIntelligencePanel()
            self.center_tabs.addTab(self.url_intelligence_tab, "🔗 URL优化")
        except Exception as e:
            self.url_intelligence_tab = None

        # 写作助手面板
        try:
            self.writing_assistant_tab = WritingAssistantPanel()
            self.center_tabs.addTab(self.writing_assistant_tab, "📝 写作助手")
        except Exception as e:
            self.writing_assistant_tab = None

        # 🔐 智能授权与实名认证系统 - Activation License
        # 核心理念："授权码 = 付款凭证 = 使用权限"
        try:
            self.activation_license_tab = ActivationLicensePanel()
            self.center_tabs.addTab(self.activation_license_tab, "🔐 授权中心")
        except Exception as e:
            self.activation_license_tab = None

        self.splitter.addWidget(self.center_tabs)

        # 右侧：工作区 + 模型池
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

        root.addWidget(self.splitter)

        # 状态栏
        self.status_bar = QLabel()
        self.status_bar.setObjectName("StatusBar")
        self.status_bar.setStyleSheet(
            "background:#0d0d0d;border-top:1px solid #1e1e1e;"
            "padding:4px 12px;color:#555;font-size:11px;"
        )
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
        root.addWidget(self.status_bar)

        # 默认
        self.center_tabs.setCurrentIndex(0)
        self.right_stack.setCurrentIndex(0)

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

    # ── Agent ───────────────────────────────────────────────────

    def _init_agent(self):
        self.ollama_client = OllamaClient(self.config.ollama)
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
