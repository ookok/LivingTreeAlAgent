"""
Browser Consciousness - 浏览器意识模块
=======================================

三层觉醒系统：
1. 环境感知 (Awareness) - 检测在线/离线/地铁/节点模式
2. 协议翻译 (Translation) - 路由多种协议到不同引擎
3. 行为预测 (Prediction) - 预测用户下一步操作

Author: Hermes Desktop AI
"""

from .awareness import (
    EnvironmentMode,
    NetworkQuality,
    AwarenessEngine,
    create_awareness_engine,
)

from .protocol_translator import (
    ProtocolType,
    ProtocolRoute,
    ProtocolTranslator,
    create_protocol_translator,
)

from .behavior_predictor import (
    UserIntent,
    Prediction,
    BehaviorPredictor,
    create_behavior_predictor,
)

from .network_adapter import (
    NodeDiscovery,
    ReverseProxy,
    BrowserPlugin,
    NetworkAdapter,
    create_network_adapter,
)

from .consciousness import (
    BrowserConsciousness,
    create_browser_consciousness,
)

__all__ = [
    # 环境感知
    "EnvironmentMode",
    "NetworkQuality",
    "AwarenessEngine",
    "create_awareness_engine",
    # 协议翻译
    "ProtocolType",
    "ProtocolRoute",
    "ProtocolTranslator",
    "create_protocol_translator",
    # 行为预测
    "UserIntent",
    "Prediction",
    "BehaviorPredictor",
    "create_behavior_predictor",
    # 网络适配器
    "NodeDiscovery",
    "ReverseProxy",
    "BrowserPlugin",
    "NetworkAdapter",
    "create_network_adapter",
    # 意识体
    "BrowserConsciousness",
    "create_browser_consciousness",
]