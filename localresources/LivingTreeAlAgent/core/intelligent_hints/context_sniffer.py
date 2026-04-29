"""
智能提示系统 — 情境捕捉器
=========================
在每个窗口/操作步骤埋轻量钩子，捕获用户当前情境
"""

import json
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from collections import defaultdict
import queue

from .models import ContextInfo, HintLevel


class SceneType(Enum):
    """场景类型"""
    PAGE = "page"                      # 页面
    OPERATION = "operation"           # 操作
    DIALOG = "dialog"                # 对话
    BACKGROUND = "background"        # 后台


@dataclass
class ContextHook:
    """上下文钩子"""
    hook_id: str
    name: str
    scene_id: str
    callback: Callable[[Dict], Optional[ContextInfo]]
    priority: int = 0                # 优先级，数字越大越先执行
    enabled: bool = True


@dataclass
class SceneDefinition:
    """场景定义"""
    scene_id: str
    name: str
    scene_type: SceneType
    description: str = ""
    keywords: List[str] = field(default_factory=list)
    related_scenes: List[str] = field(default_factory=list)  # 进入/离开时可能关联的场景


class ContextSniffer:
    """
    情境捕捉器

    功能：
    1. 注册场景钩子
    2. 捕捉进入/离开场景事件
    3. 聚合上下文信息
    4. 生成 ContextInfo 推送给意图引擎
    """

    # 内置场景定义
    BUILTIN_SCENES: Dict[str, SceneDefinition] = {
        "model_select": SceneDefinition(
            scene_id="model_select",
            name="模型选择",
            scene_type=SceneType.PAGE,
            description="用户正在选择 AI 模型",
            keywords=["模型", "选择", "Ollama", "DeepSeek", "OpenRouter", "性能", "成本"],
            related_scenes=["chat", "settings"]
        ),
        "chat": SceneDefinition(
            scene_id="chat",
            name="聊天",
            scene_type=SceneType.PAGE,
            description="用户正在进行对话",
            keywords=["聊天", "对话", "发送", "消息"],
            related_scenes=["model_select", "writing"]
        ),
        "writing": SceneDefinition(
            scene_id="writing",
            name="写作",
            scene_type=SceneType.PAGE,
            description="用户正在使用写作助手",
            keywords=["写作", "文章", "文案", "创作"],
            related_scenes=["chat", "research"]
        ),
        "research": SceneDefinition(
            scene_id="research",
            name="研究搜索",
            scene_type=SceneType.PAGE,
            description="用户正在进行研究搜索",
            keywords=["搜索", "研究", "查询", "信息"],
            related_scenes=["chat", "writing"]
        ),
        "settings": SceneDefinition(
            scene_id="settings",
            name="设置",
            scene_type=SceneType.PAGE,
            description="用户正在调整设置",
            keywords=["设置", "配置", "偏好"],
            related_scenes=["model_select"]
        ),
        "file_operation": SceneDefinition(
            scene_id="file_operation",
            name="文件操作",
            scene_type=SceneType.OPERATION,
            description="用户正在操作文件",
            keywords=["打开", "保存", "导出", "删除", "移动", "重命名"],
            related_scenes=[]
        ),
        "code_edit": SceneDefinition(
            scene_id="code_edit",
            name="代码编辑",
            scene_type=SceneType.OPERATION,
            description="用户正在编写或编辑代码",
            keywords=["代码", "编程", "函数", "类", "变量", "调试"],
            related_scenes=["chat"]
        ),
        "network_issue": SceneDefinition(
            scene_id="network_issue",
            name="网络问题",
            scene_type=SceneType.BACKGROUND,
            description="检测到网络连接问题",
            keywords=["网络", "连接", "超时", "失败", "重试"],
            related_scenes=[]
        ),
        "low_performance": SceneDefinition(
            scene_id="low_performance",
            name="性能问题",
            scene_type=SceneType.BACKGROUND,
            description="检测到系统性能下降",
            keywords=["卡顿", "慢", "内存", "CPU", "性能"],
            related_scenes=[]
        ),
    }

    def __init__(self):
        self._hooks: Dict[str, List[ContextHook]] = defaultdict(list)
        self._scenes: Dict[str, SceneDefinition] = self.BUILTIN_SCENES.copy()
        self._current_scene: Optional[str] = None
        self._scene_history: List[str] = []
        self._user_action_history: List[Dict] = []
        self._lock = threading.RLock()

        # 上下文队列（异步传递）
        self._context_queue: queue.Queue = queue.Queue()
        self._subscribers: List[Callable[[ContextInfo], None]] = []

        # 设备信息缓存
        self._device_info: Dict[str, Any] = {}

        # 用户画像（来自记忆宫殿）
        self._user_profile: Dict[str, Any] = {}

    def register_hook(self, hook: ContextHook) -> None:
        """注册上下文钩子"""
        with self._lock:
            self._hooks[hook.scene_id].append(hook)
            # 按优先级排序
            self._hooks[hook.scene_id].sort(key=lambda h: h.priority, reverse=True)

    def unregister_hook(self, hook_id: str) -> None:
        """取消注册钩子"""
        with self._lock:
            for scene_id in self._hooks:
                self._hooks[scene_id] = [h for h in self._hooks[scene_id] if h.hook_id != hook_id]

    def register_scene(self, scene: SceneDefinition) -> None:
        """注册新场景"""
        with self._lock:
            self._scenes[scene.scene_id] = scene

    def subscribe(self, callback: Callable[[ContextInfo], None]) -> None:
        """订阅上下文更新"""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[ContextInfo], None]) -> None:
        """取消订阅"""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def emit_context(self, context_data: Dict[str, Any]) -> Optional[ContextInfo]:
        """
        手动发射上下文（供外部调用）

        用法：
        >>> sniffer.emit_context({
        ...     "scene_id": "model_select",
        ...     "user_action": "比较模型性能",
        ...     "options": ["Ollama", "DeepSeek", "OpenRouter"],
        ...     "device_info": {"network": "poor"}
        ... })
        """
        # 构建 ContextInfo
        scene_id = context_data.get("scene_id", "unknown")
        scene_def = self._scenes.get(scene_id)

        if not scene_def:
            scene_def = SceneDefinition(
                scene_id=scene_id,
                name=scene_id,
                scene_type=SceneType.UNKNOWN if hasattr(SceneType, "UNKNOWN") else SceneType.PAGE
            )

        context = ContextInfo(
            scene_id=scene_id,
            scene_name=scene_def.name,
            scene_type=scene_def.scene_type.value,
            user_action=context_data.get("user_action", ""),
            user_goal=context_data.get("user_goal", ""),
            user_history=context_data.get("user_history", []),
            device_info=context_data.get("device_info", self._device_info),
            app_state=context_data.get("app_state", {}),
            options=context_data.get("options", []),
            user_profile=self._user_profile,
            urgency=context_data.get("urgency", 0.5),
            importance=context_data.get("importance", 0.5),
        )

        # 触发钩子
        self._trigger_hooks(context)

        # 通知订阅者
        self._notify_subscribers(context)

        # 更新当前场景
        if scene_id != self._current_scene:
            self._on_scene_change(self._current_scene, scene_id)
            self._current_scene = scene_id

        return context

    def _trigger_hooks(self, context: ContextInfo) -> None:
        """触发场景钩子"""
        with self._lock:
            hooks = self._hooks.get(context.scene_id, [])
            for hook in hooks:
                if not hook.enabled:
                    continue
                try:
                    hook.callback(context.__dict__)
                except Exception as e:
                    print(f"Hook {hook.hook_id} error: {e}")

    def _notify_subscribers(self, context: ContextInfo) -> None:
        """通知所有订阅者"""
        for callback in self._subscribers:
            try:
                callback(context)
            except Exception as e:
                print(f"Subscriber callback error: {e}")

    def _on_scene_change(self, old_scene: Optional[str], new_scene: str) -> None:
        """场景变化处理"""
        self._scene_history.append(new_scene)
        if len(self._scene_history) > 50:  # 保留最近50个场景
            self._scene_history.pop(0)

        # 触发退出钩子
        if old_scene:
            self._trigger_scene_event(old_scene, "exit")

        # 触发进入钩子
        self._trigger_scene_event(new_scene, "enter")

    def _trigger_scene_event(self, scene_id: str, event: str) -> None:
        """触发场景事件"""
        with self._lock:
            hooks = self._hooks.get(f"{scene_id}_{event}", [])
            for hook in hooks:
                if not hook.enabled:
                    continue
                try:
                    hook.callback({"scene_id": scene_id, "event": event})
                except Exception as e:
                    print(f"Scene hook {hook.hook_id} error: {e}")

    def record_action(self, action: str, metadata: Dict[str, Any] = None) -> None:
        """记录用户操作（用于学习用户习惯）"""
        self._user_action_history.append({
            "action": action,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
            "scene": self._current_scene
        })
        if len(self._user_action_history) > 100:
            self._user_action_history.pop(0)

    def update_device_info(self, device_info: Dict[str, Any]) -> None:
        """更新设备信息"""
        self._device_info.update(device_info)

    def update_user_profile(self, profile: Dict[str, Any]) -> None:
        """更新用户画像"""
        self._user_profile.update(profile)

    def get_current_context(self) -> Optional[ContextInfo]:
        """获取当前上下文"""
        if not self._current_scene:
            return None

        scene_def = self._scenes.get(self._current_scene)
        return ContextInfo(
            scene_id=self._current_scene,
            scene_name=scene_def.name if scene_def else self._current_scene,
            scene_type=scene_def.scene_type.value if scene_def else "unknown",
            user_history=[a["action"] for a in self._user_action_history[-10:]],
            device_info=self._device_info,
            user_profile=self._user_profile,
        )

    def get_scene_history(self) -> List[str]:
        """获取场景历史"""
        return self._scene_history.copy()

    def get_action_history(self) -> List[Dict]:
        """获取操作历史"""
        return self._user_action_history.copy()

    # ── 便捷的预定义钩子工厂 ────────────────────────────────

    def create_model_select_hook(self) -> ContextHook:
        """创建模型选择场景钩子"""
        def callback(data: Dict) -> Optional[ContextInfo]:
            return self.emit_context({
                "scene_id": "model_select",
                "user_action": data.get("action", "查看模型选项"),
                "options": data.get("options", []),
                "device_info": data.get("device_info", {}),
                "user_goal": "选择最适合当前任务的模型",
            })
        return ContextHook(
            hook_id="model_select_hook",
            name="模型选择钩子",
            scene_id="model_select",
            callback=callback,
            priority=10
        )

    def create_network_monitor_hook(self) -> ContextHook:
        """创建网络监控钩子"""
        def callback(data: Dict) -> Optional[ContextInfo]:
            network_status = data.get("network_status", "unknown")
            if network_status == "poor" or network_status == "disconnected":
                return self.emit_context({
                    "scene_id": "network_issue",
                    "scene_type": "background",
                    "user_action": "网络连接不稳定",
                    "urgency": 0.8,
                    "importance": 0.7,
                })
            return None
        return ContextHook(
            hook_id="network_monitor_hook",
            name="网络监控钩子",
            scene_id="network_status",
            callback=callback,
            priority=100  # 高优先级，网络问题要立即响应
        )

    def create_performance_monitor_hook(self) -> ContextHook:
        """创建性能监控钩子"""
        def callback(data: Dict) -> Optional[ContextInfo]:
            cpu_usage = data.get("cpu_usage", 0)
            memory_usage = data.get("memory_usage", 0)
            if cpu_usage > 80 or memory_usage > 85:
                return self.emit_context({
                    "scene_id": "low_performance",
                    "scene_type": "background",
                    "user_action": "系统性能下降",
                    "urgency": 0.6,
                    "importance": 0.5,
                    "device_info": {"cpu": cpu_usage, "memory": memory_usage}
                })
            return None
        return ContextHook(
            hook_id="performance_monitor_hook",
            name="性能监控钩子",
            scene_id="performance_status",
            callback=callback,
            priority=90
        )


# 全局单例
_sniffer_instance: Optional[ContextSniffer] = None
_sniffer_lock = threading.Lock()


def get_context_sniffer() -> ContextSniffer:
    """获取情境捕捉器单例"""
    global _sniffer_instance
    with _sniffer_lock:
        if _sniffer_instance is None:
            _sniffer_instance = ContextSniffer()
            # 注册内置钩子
            _sniffer_instance.register_hook(_sniffer_instance.create_network_monitor_hook())
            _sniffer_instance.register_hook(_sniffer_instance.create_performance_monitor_hook())
        return _sniffer_instance
