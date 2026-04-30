"""
智能提示系统 — UI集成钩子
=========================
提供便捷的钩子函数，方便在现有UI面板中集成智能提示
"""

from typing import Dict, List, Any, Optional, Callable

from client.src.business.intelligent_hints.system import get_hints_system


def emit_context(
    scene_id: str,
    user_action: str = "",
    user_goal: str = "",
    options: List[str] = None,
    device_info: Dict[str, Any] = None,
    urgency: float = 0.5,
    importance: float = 0.5,
    **kwargs
) -> Optional[dict]:
    """通用上下文发射函数"""
    system = get_hints_system()
    return system.emit_context(
        scene_id=scene_id,
        user_action=user_action,
        user_goal=user_goal,
        options=options or [],
        device_info=device_info or {},
        urgency=urgency,
        importance=importance,
        **kwargs
    )


def emit_model_select_hint(
    options: List[str] = None,
    user_action: str = "查看模型选项",
    device_info: Dict[str, Any] = None,
) -> Optional[dict]:
    """发射模型选择场景提示"""
    return emit_context(
        scene_id="model_select",
        user_action=user_action,
        user_goal="选择最适合当前任务的模型",
        options=options or [],
        device_info=device_info or {},
        importance=0.6
    )


def emit_chat_hint(
    user_action: str = "聊天中",
    device_info: Dict[str, Any] = None,
) -> Optional[dict]:
    """发射聊天场景提示"""
    return emit_context(
        scene_id="chat",
        user_action=user_action,
        device_info=device_info or {},
    )


def emit_writing_hint(
    user_action: str = "写作中",
    device_info: Dict[str, Any] = None,
) -> Optional[dict]:
    """发射写作场景提示"""
    return emit_context(
        scene_id="writing",
        user_action=user_action,
        device_info=device_info or {},
    )


def emit_network_issue_hint(
    network_status: str = "poor",
    device_info: Dict[str, Any] = None,
) -> Optional[dict]:
    """发射网络问题提示"""
    return emit_context(
        scene_id="network_issue",
        user_action="网络连接不稳定",
        device_info=device_info or {"network": network_status},
        urgency=0.8,
        importance=0.7
    )


def emit_performance_hint(
    cpu_usage: int = 0,
    memory_usage: int = 0,
    device_info: Dict[str, Any] = None,
) -> Optional[dict]:
    """发射性能问题提示"""
    info = device_info or {}
    info.update({"cpu": cpu_usage, "memory": memory_usage})
    return emit_context(
        scene_id="low_performance",
        user_action="系统性能下降",
        device_info=info,
        urgency=0.6,
        importance=0.5
    )


def emit_file_operation_hint(
    action: str = "",
    device_info: Dict[str, Any] = None,
) -> Optional[dict]:
    """发射文件操作提示"""
    return emit_context(
        scene_id="file_operation",
        user_action=action,
        device_info=device_info or {},
    )


def record_user_action(
    action: str = "",
    metadata: Dict[str, Any] = None
) -> None:
    """记录用户操作（用于学习用户习惯）"""
    system = get_hints_system()
    system.record_action(action, metadata)


class HintEmitter:
    """提示发射器类"""

    def __init__(self, scene_id: str):
        self.scene_id = scene_id
        self._system = get_hints_system()

    def emit(
        self,
        user_action: str = "",
        user_goal: str = "",
        options: List[str] = None,
        device_info: Dict[str, Any] = None,
        **kwargs
    ) -> Optional[dict]:
        return self._system.emit_context(
            scene_id=self.scene_id,
            user_action=user_action,
            user_goal=user_goal,
            options=options or [],
            device_info=device_info or {},
            **kwargs
        )

    def record(self, action: str, metadata: Dict[str, Any] = None):
        self._system.record_action(action, metadata)


ModelSelectEmitter = HintEmitter("model_select")
ChatEmitter = HintEmitter("chat")
WritingEmitter = HintEmitter("writing")
SettingsEmitter = HintEmitter("settings")
FileOperationEmitter = HintEmitter("file_operation")


class HintEventFilter:
    """PyQt 事件过滤器"""

    def __init__(
        self,
        scene_id: str,
        enter_action: Callable = None,
        leave_action: Callable = None
    ):
        self.scene_id = scene_id
        self.enter_action = enter_action
        self.leave_action = leave_action
        self._system = get_hints_system()

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.Enter and self.enter_action:
            self.enter_action()
            emit_context(scene_id=self.scene_id, user_action=f"进入{self.scene_id}")
        elif event.type() == QEvent.Type.Leave and self.leave_action:
            self.leave_action()
            emit_context(scene_id=self.scene_id, user_action=f"离开{self.scene_id}")
        return False
