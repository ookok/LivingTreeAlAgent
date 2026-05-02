"""
歧义交互模块
处理歧义检测后的用户确认流程
"""

import asyncio
from dataclasses import dataclass
from typing import Optional, Callable, Awaitable
from enum import Enum

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QComboBox
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont

from .rules import AmbiguitySignal


class AmbiguityResolver(QObject):
    """
    歧义解析器
    管理歧义检测和用户确认流程
    """

    # 信号：当歧义被解决时发出
    resolved = pyqtSignal(str, str)  # (signal_id, selected_interpretation)
    cancelled = pyqtSignal(str)  # (signal_id)

    def __init__(self):
        super().__init__()
        self._pending_signals: dict[str, AmbiguitySignal] = {}
        self._dialog: Optional["AmbiguityDialog"] = None
        self._resolve_callback: Optional[Callable[[str, str], Awaitable[None]]] = None

    def set_resolve_callback(self, callback: Callable[[str, str], Awaitable[None]]):
        """设置解决后的回调函数"""
        self._resolve_callback = callback

    def add_pending(self, signal: AmbiguitySignal) -> str:
        """
        添加待处理的歧义信号

        Args:
            signal: 歧义信号

        Returns:
            signal_id: 用于后续匹配的 ID
        """
        signal_id = f"amb_{len(self._pending_signals)}_{hash(signal.original_text[:50])}"
        self._pending_signals[signal_id] = signal
        return signal_id

    def get_pending(self) -> list[tuple[str, AmbiguitySignal]]:
        """获取所有待处理的歧义"""
        return list(self._pending_signals.items())

    def resolve(self, signal_id: str, selected: str):
        """
        解决歧义

        Args:
            signal_id: 信号 ID
            selected: 用户选择的解读
        """
        if signal_id in self._pending_signals:
            signal = self._pending_signals[signal_id]
            signal.resolved = True
            signal.selected_interpretation = selected

            # 发出信号
            self.resolved.emit(signal_id, selected)

            # 异步回调
            if self._resolve_callback:
                asyncio.create_task(
                    self._resolve_callback(signal_id, selected)
                )

            # 移除已解决的
            del self._pending_signals[signal_id]

    def cancel(self, signal_id: str):
        """
        取消歧义（用户拒绝提供信息）

        Args:
            signal_id: 信号 ID
        """
        if signal_id in self._pending_signals:
            self.cancelled.emit(signal_id)
            del self._pending_signals[signal_id]

    def clear_all(self):
        """清除所有待处理的歧义"""
        self._pending_signals.clear()


class AmbiguityDialog(QDialog):
    """
    歧义确认对话框
    PyQt6 实现，用于在检测到歧义时询问用户
    """

    def __init__(self, signal: AmbiguitySignal, parent=None):
        super().__init__(parent)
        self.signal = signal
        self.selected_result: Optional[str] = None

        self.setWindowTitle("检测到需求歧义")
        self.setMinimumWidth(600)
        self.setModal(True)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 类型标签
        type_label = QLabel(f"【歧义类型】{self.signal.ambiguity_type}")
        type_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        layout.addWidget(type_label)

        # 原文显示
        original_label = QLabel("【原文】")
        original_label.setFont(QFont("Microsoft YaHei", 9))
        layout.addWidget(original_label)

        original_text = QTextEdit()
        original_text.setPlainText(self.signal.original_text)
        original_text.setReadOnly(True)
        original_text.setMaximumHeight(100)
        layout.addWidget(original_text)

        # 选项选择
        option_label = QLabel("【可能的解读】请选择或输入您的意图：")
        option_label.setFont(QFont("Microsoft YaHei", 9))
        layout.addWidget(option_label)

        # 选项下拉框
        self.option_combo = QComboBox()
        for i, opt in enumerate(self.signal.possible_interpretations):
            self.option_combo.addItem(f"选项{i+1}: {opt}", opt)
        layout.addWidget(self.option_combo)

        # 自定义输入
        self.custom_input = QTextEdit()
        self.custom_input.setPlaceholderText("或直接输入您的补充说明...")
        self.custom_input.setMaximumHeight(60)
        layout.addWidget(self.custom_input)

        # 按钮区域
        btn_layout = QHBoxLayout()

        self.confirm_btn = QPushButton("确认")
        self.confirm_btn.setDefault(True)
        self.confirm_btn.clicked.connect(self._on_confirm)
        btn_layout.addWidget(self.confirm_btn)

        self.cancel_btn = QPushButton("取消（使用默认理解）")
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def _on_confirm(self):
        """确认选择"""
        # 优先使用自定义输入
        custom = self.custom_input.toPlainText().strip()
        if custom:
            self.selected_result = custom
        else:
            # 使用下拉框选择
            self.selected_result = self.option_combo.currentData()

        self.accept()

    def _on_cancel(self):
        """取消"""
        self.selected_result = None
        self.reject()

    def get_result(self) -> Optional[str]:
        """获取结果"""
        return self.selected_result


async def show_ambiguity_dialog_async(
    signal: AmbiguitySignal,
) -> Optional[str]:
    """
    异步显示歧义对话框（用于非 Qt 线程）

    Args:
        signal: 歧义信号

    Returns:
        用户选择的解读，或 None（取消）
    """
    loop = asyncio.get_event_loop()

    # 在 Qt 线程中显示对话框
    def show_dialog():
        dialog = AmbiguityDialog(signal)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_result()
        return None

    return await loop.run_in_executor(None, show_dialog)


class ResolverContext:
    """
    歧义解析上下文
    在 Agent 执行过程中管理歧义流程
    """

    def __init__(self):
        self.resolver = AmbiguityResolver()
        self._execution_paused = False
        self._pending_confirmation: Optional[asyncio.Future] = None

    async def pause_and_ask(
        self,
        signal: AmbiguitySignal,
        timeout: float = 120.0,
    ) -> Optional[str]:
        """
        暂停执行并询问用户

        Args:
            signal: 歧义信号
            timeout: 超时时间（秒）

        Returns:
            用户选择的解读，或 None（超时/取消）
        """
        self._execution_paused = True
        self._pending_confirmation = asyncio.Future()

        # 在 Qt 线程显示对话框
        result = await show_ambiguity_dialog_async(signal)

        if result:
            self._pending_confirmation.set_result(result)
        else:
            self._pending_confirmation.set_result(None)

        self._execution_paused = False
        self._pending_confirmation = None

        return result

    def is_paused(self) -> bool:
        """检查是否处于暂停状态"""
        return self._execution_paused


# 全局单例
_resolver_context = None


def get_resolver_context() -> ResolverContext:
    """获取全局歧义解析上下文"""
    global _resolver_context
    if _resolver_context is None:
        _resolver_context = ResolverContext()
    return _resolver_context