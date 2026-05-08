"""Integration layer — Central hub that wires all layers together.

The IntegrationHub is the entry point that:
1. Loads configuration
2. Creates all components with DI
3. Wires LifeEngine with all layers
4. Manages lifecycle (start/stop)
5. Provides the unified API surface
"""

from .hub import IntegrationHub
from .launcher import launch, LaunchMode
from .sse_server import SSEAgentServer, create_sse_server
from .self_updater import check_update, run_update, version_check, install_dependencies, find_package_manager
from .message_gateway import MessageGateway, GatewayMessage, get_gateway
from .sms_gateway import SmsGateway, SmsConfig, get_sms_gateway
from .wechat_notifier import WXBizMsgCrypt, WeWorkBot, get_bot, init_bot
from .unified_notifier import UnifiedNotifier, NotifyResult, get_unified_notifier

__all__ = [
    "IntegrationHub", "launch", "LaunchMode",
    "SSEAgentServer", "create_sse_server",
    "check_update", "run_update", "version_check", "install_dependencies", "find_package_manager",
    "MessageGateway", "GatewayMessage", "get_gateway",
    "SmsGateway", "SmsConfig", "get_sms_gateway",
    "WXBizMsgCrypt", "WeWorkBot", "get_bot", "init_bot",
    "UnifiedNotifier", "NotifyResult", "get_unified_notifier",
]
