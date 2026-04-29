"""
智能提示系统 — 统一调度器 (全局交互版)
======================================
整合 handbook 本地匹配 + 轻量 Hermes 润色 + MemPalace 记忆
"""

import json
import threading
import time
from typing import Optional, Callable, List, Dict, Any
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from .models import (
    ContextInfo,
    GeneratedHint,
    HintConfig,
    HintLevel,
    HintType,
)
from .context_sniffer import ContextSniffer, get_context_sniffer
from .intent_engine import HintIntentEngine, get_hint_engine
from .hint_templates import HintTemplateStore, get_hint_store
from .global_signals import (
    HintSignal,
    HintSignalType,
    GlobalHintSignalBus,
    get_signal_bus,
    emit_hint_signal,
)
from .handbook_matcher import HandbookMatcher, get_handbook_matcher
from .polisher import LightweightPolisher, HermesPolisher, get_polisher, get_hermes_polisher
from .hint_memory import HintMemory, get_hint_memory


class IntelligentHintsSystem(QObject):
    """
    智能提示系统 — 统一调度器 (全局交互版)

    信号：
    - hint_generated: 新提示生成
    - context_changed: 场景变化
    - hint_dismissed: 提示被忽略
    - chat_requested: 聊天请求
    """

    hint_generated = pyqtSignal(object)
    context_changed = pyqtSignal(object)
    hint_dismissed = pyqtSignal(str)
    chat_requested = pyqtSignal(str, object)  # scene_id, context

    _instance = None
    _lock = threading.Lock()

    def __init__(
        self,
        config: HintConfig = None,
    ):
        super().__init__()
        self.config = config or HintConfig()

        # 核心组件
        self._sniffer = get_context_sniffer()
        self._engine = get_hint_engine()
        self._store = get_hint_store()
        self._matcher = get_handbook_matcher()
        self._polisher = get_polisher()
        self._memory = get_hint_memory()
        self._signal_bus = get_signal_bus()

        # 状态
        self._is_running = False
        self._current_hints: Dict[str, GeneratedHint] = {}
        self._hint_history: List[GeneratedHint] = []
        self._current_scene: str = "global"

        # UI（延迟初始化）
        self._air_icon = None
        self._chat_window = None

        # 订阅信号
        self._signal_bus.subscribe_global(self._on_signal)
        self._signal_bus.start_processing()

        # 定时器
        self._generate_timer = QTimer()
        self._generate_timer.timeout.connect(self._on_generate_tick)

        # 加载配置
        self._load_config()

    @classmethod
    def get_instance(cls) -> "IntelligentHintsSystem":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _load_config(self):
        config_path = Path.home() / ".hermes-desktop" / "hints_config.json"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.config = HintConfig.from_dict(data)
            except Exception as e:
                print(f"Failed to load hints config: {e}")

    def save_config(self):
        config_path = Path.home() / ".hermes-desktop" / "hints_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.config.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save hints config: {e}")

    # ── 生命周期 ────────────────────────────────────────────

    def start(self):
        """启动系统"""
        if self._is_running:
            return

        self._is_running = True

        # 创建空气图标
        if self.config.enabled and self.config.show_air_icon:
            self._ensure_air_icon()
            self._air_icon.set_visible(True)

        # 启动生成定时器
        if self.config.generate_interval > 0:
            self._generate_timer.start(self.config.generate_interval)

    def stop(self):
        """停止系统"""
        self._is_running = False
        self._generate_timer.stop()
        if self._air_icon:
            self._air_icon.set_visible(False)

    def _ensure_air_icon(self):
        """确保空气图标已创建"""
        if self._air_icon is None:
            from .air_ui import get_global_air_icon, show_chat_window
            self._air_icon = get_global_air_icon(self.config, self._current_scene)

            # 连接信号
            self._air_icon.menu_signal.connect(self._on_menu_signal)

    # ── 信号处理 ───────────────────────────────────────────

    def _on_signal(self, signal: HintSignal):
        """处理全局信号"""
        if signal.signal_type == HintSignalType.HINT_NEEDED:
            self._handle_hint_needed(signal)
        elif signal.signal_type == HintSignalType.HIDE_THIS_SCENE:
            self._handle_hide_scene(signal)
        elif signal.signal_type == HintSignalType.SHOW_CHAT_WINDOW:
            self._handle_chat_request(signal)
        elif signal.signal_type == HintSignalType.HINT_CHAT:
            self._handle_chat_input(signal)

    def _handle_hint_needed(self, signal: HintSignal):
        """处理需要提示"""
        context = self._build_context(signal)
        self._current_scene = signal.scene_id

        # 检查是否被隐藏
        if self._memory.is_hidden(signal.scene_id):
            return

        # 匹配 handbook
        hint = self._matcher.generate_hint(signal.scene_id, context, signal.payload)

        if hint:
            # 润色
            hint = self._polisher.polish(hint, context)

            # 添加
            self._add_hint(hint)

            # 更新图标状态
            if self._air_icon:
                self._air_icon.set_hint(True, hint.hint_level)

    def _handle_hide_scene(self, signal: HintSignal):
        """处理隐藏场景"""
        hide_type = signal.payload.get("hide_type", "perma")
        message = signal.payload.get("message", "好的~")

        # 如果是"别烦我"，显示消息
        if hide_type == "perma":
            self._show_temp_message(message)

    def _handle_chat_request(self, signal: HintSignal):
        """处理聊天请求"""
        from .air_ui import show_chat_window
        context = self._build_context(signal)
        self._chat_window = show_chat_window(signal.scene_id, context)

    def _handle_chat_input(self, signal: HintSignal):
        """处理聊天输入"""
        question = signal.payload.get("question", "")
        if not question:
            return

        # 获取回复
        context = self._build_context(signal)
        hermes = get_hermes_polisher()
        response = hermes.chat(question, signal.scene_id, context)

        # 如果聊天窗口存在，显示回复
        if self._chat_window:
            self._chat_window.add_message("user", question)
            self._chat_window.add_message("bot", response)

    def _on_menu_signal(self, interaction: str, scene_id: str):
        """处理菜单信号"""
        if interaction == "hide_temp":
            self._memory.hide_scene(scene_id, hide_type="temp")
        elif interaction == "hide_perma":
            self._memory.hide_scene(scene_id, hide_type="perma")
            self._show_temp_message("好的，这个页面不会再闪了～")
        elif interaction == "chat":
            self._handle_chat_request(HintSignal(
                signal_type=HintSignalType.SHOW_CHAT_WINDOW,
                scene_id=scene_id
            ))

    def _build_context(self, signal: HintSignal) -> ContextInfo:
        """构建上下文"""
        return ContextInfo(
            scene_id=signal.scene_id,
            scene_name=signal.scene_id,
            user_action=signal.payload.get("action", ""),
            user_goal=signal.payload.get("goal", ""),
            options=signal.payload.get("options", []),
            device_info=signal.payload.get("device_info", {}),
            user_profile=self._get_user_preferences(),
            urgency=signal.payload.get("urgency", 0.5),
            importance=signal.payload.get("importance", 0.5),
        )

    def _get_user_preferences(self) -> Dict[str, Any]:
        """获取用户偏好"""
        return {
            "prefers_free": self._memory.get_preference("prefers_free", False),
            "prioritizes": self._memory.get_preference("prioritizes", ""),
            "is_new_user": self._memory.get_preference("is_new_user", True),
        }

    def _show_temp_message(self, message: str):
        """显示临时消息（可以用 Toast）"""
        print(f"🌿 {message}")

    # ── 提示生成 ────────────────────────────────────────────

    def _on_generate_tick(self):
        """定时生成检查"""
        if not self.config.enabled:
            return

        # 获取当前上下文
        context = self._sniffer.get_current_context()
        if not context:
            return

        # 检查隐藏
        if self._memory.is_hidden(context.scene_id):
            return

        # 生成提示
        hint = self._matcher.generate_hint(
            context.scene_id,
            context,
            {}
        )

        if hint:
            hint = self._polisher.polish(hint, context)
            self._add_hint(hint)

            if self._air_icon:
                self._air_icon.set_hint(True, hint.hint_level)

    def _add_hint(self, hint: GeneratedHint):
        """添加提示"""
        self._current_hints[hint.hint_id] = hint
        self._hint_history.append(hint)

        # 限制历史
        if len(self._hint_history) > 100:
            self._hint_history.pop(0)

        # 发送到UI
        if self._air_icon:
            self._air_icon.show_hint(hint)

        # 发送信号
        self.hint_generated.emit(hint)

    # ── 公开接口 ────────────────────────────────────────────

    def emit_context(
        self,
        scene_id: str,
        user_action: str = "",
        user_goal: str = "",
        options: List[str] = None,
        device_info: Dict[str, Any] = None,
        **kwargs
    ) -> Optional[ContextInfo]:
        """发射上下文"""
        return self._sniffer.emit_context({
            "scene_id": scene_id,
            "user_action": user_action,
            "user_goal": user_goal,
            "options": options or [],
            "device_info": device_info or {},
            **kwargs
        })

    def update_device_info(self, device_info: Dict[str, Any]):
        """更新设备信息"""
        self._sniffer.update_device_info(device_info)

    def update_user_profile(self, profile: Dict[str, Any]):
        """更新用户画像"""
        self._sniffer.update_user_profile(profile)

    def record_action(self, action: str, metadata: Dict[str, Any] = None):
        """记录用户操作"""
        self._sniffer.record_action(action, metadata)
        self._memory.learn_from_action(self._current_scene, action, metadata or {})

    def get_current_hints(self) -> List[GeneratedHint]:
        """获取当前提示"""
        return list(self._current_hints.values())

    def get_hint_history(self, limit: int = 50) -> List[GeneratedHint]:
        """获取提示历史"""
        return self._hint_history[-limit:]

    def clear_hints(self):
        """清除所有提示"""
        self._current_hints.clear()
        if self._air_icon:
            self._air_icon.set_hint(False)

    def set_enabled(self, enabled: bool):
        """启用/禁用"""
        self.config.enabled = enabled
        if enabled:
            self.start()
        else:
            self.stop()
        self.save_config()

    def is_enabled(self) -> bool:
        return self.config.enabled

    def show_air_icon(self, show: bool):
        self.config.show_air_icon = show
        if self._air_icon:
            self._air_icon.set_visible(show)
        self.save_config()

    def get_air_icon(self):
        self._ensure_air_icon()
        return self._air_icon


# ── 全局便捷函数 ──────────────────────────────────────────

_system: Optional[IntelligentHintsSystem] = None


def get_hints_system() -> IntelligentHintsSystem:
    global _system
    if _system is None:
        _system = IntelligentHintsSystem.get_instance()
    return _system


def emit_hint_context(
    scene_id: str,
    user_action: str = "",
    user_goal: str = "",
    options: List[str] = None,
    device_info: Dict[str, Any] = None,
    **kwargs
) -> Optional[ContextInfo]:
    """快捷发射上下文"""
    return get_hints_system().emit_context(
        scene_id, user_action, user_goal, options, device_info, **kwargs
    )
