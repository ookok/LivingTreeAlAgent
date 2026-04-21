"""
智能提示系统 — 全局交互版
========================

定位：操作系统级智能伴侣

一颗🌿悬浮在应用最顶层，不抢焦点却无处不在；
用户可随时点开，选择"不看/记仇/细聊"，
把控制权完全交还给用户。

核心架构：
1. GlobalAirIcon — 全局置顶 + 右键三级菜单
2. HandbookMatcher — 本地 JSON 规则匹配
3. LightweightPolisher — <80 Token 润色
4. HintMemory — MemPalace 持久化记忆

Author: Hermes Desktop Team
"""

from .models import (
    HintLevel,
    HintType,
    ContextInfo,
    GeneratedHint,
    HintConfig,
)
from .context_sniffer import ContextSniffer, get_context_sniffer
from .intent_engine import HintIntentEngine, get_hint_engine
from .hint_templates import HintTemplateStore, get_hint_store
from .global_signals import (
    HintSignalType,
    HintSignal,
    GlobalHintSignalBus,
    get_signal_bus,
    emit_hint_signal,
)
from .handbook_matcher import (
    HandbookLoader,
    HandbookMatcher,
    get_handbook_loader,
    get_handbook_matcher,
)
from .polisher import (
    LightweightPolisher,
    HermesPolisher,
    get_polisher,
    get_hermes_polisher,
)
from .hint_memory import HintMemory, get_hint_memory
from .air_ui import (
    GlobalAirIcon,
    HintCardWidget,
    ChatWindow,
    get_global_air_icon,
    show_chat_window,
)
from .system import IntelligentHintsSystem, get_hints_system, emit_hint_context
from .ui_hooks import (
    emit_context,
    emit_model_select_hint,
    emit_chat_hint,
    emit_writing_hint,
    emit_network_issue_hint,
    emit_performance_hint,
    HintEmitter,
    ModelSelectEmitter,
    ChatEmitter,
    WritingEmitter,
)


__all__ = [
    # 模型
    "HintLevel",
    "HintType",
    "ContextInfo",
    "GeneratedHint",
    "HintConfig",
    # 情境捕捉
    "ContextSniffer",
    "get_context_sniffer",
    # 意图引擎
    "HintIntentEngine",
    "get_hint_engine",
    # 提示模板
    "HintTemplateStore",
    "get_hint_store",
    # 全局信号
    "HintSignalType",
    "HintSignal",
    "GlobalHintSignalBus",
    "get_signal_bus",
    "emit_hint_signal",
    # Handbook
    "HandbookLoader",
    "HandbookMatcher",
    "get_handbook_loader",
    "get_handbook_matcher",
    # 润色器
    "LightweightPolisher",
    "HermesPolisher",
    "get_polisher",
    "get_hermes_polisher",
    # 记忆
    "HintMemory",
    "get_hint_memory",
    # 空气UI
    "GlobalAirIcon",
    "HintCardWidget",
    "ChatWindow",
    "get_global_air_icon",
    "show_chat_window",
    # 系统
    "IntelligentHintsSystem",
    "get_hints_system",
    "emit_hint_context",
    # UI钩子
    "emit_context",
    "emit_model_select_hint",
    "emit_chat_hint",
    "emit_writing_hint",
    "emit_network_issue_hint",
    "emit_performance_hint",
    "HintEmitter",
    "ModelSelectEmitter",
    "ChatEmitter",
    "WritingEmitter",
]
