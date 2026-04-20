"""
🌿 生命之树 UI 管理器
==================

统一管理无弹窗组件，提供简洁的调用接口。

使用方式:
    from ui.components import LivingTreeUI

    # 初始化
    self.ui = LivingTreeUI(self)

    # 显示全局警告
    self.ui.alert.show("新版本已就绪", level="info",
        actions=[("查看", lambda: ...), ("忽略", None)])

    # 显示确认询问
    self.ui.inquiry.ask("确认删除？", options=[
        ("delete", "确认删除", None),
        ("cancel", "取消", None)
    ])

    # 显示进度
    self.ui.status.show_progress("下载中...", 50)

    # 显示上下文提示
    self.ui.hint.show_below(input_field, "输入格式不正确")
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout

from .canopy_alert import CanopyAlertBand
from .status_rail import SoilStatusRail
from .dewdrop_hint import DewdropHintCard


class LivingTreeUI:
    """
    生命之树 UI 管理器

    统一管理所有无弹窗组件，提供链式调用接口。
    """

    def __init__(self, parent: QWidget):
        self._parent = parent

        # 创建组件
        self._create_components()

    def _create_components(self):
        """创建所有组件"""
        parent = self._parent

        # 1. 林冠警报带 - 顶部（需要特殊处理，放在状态栏上方）
        self._alert_band = CanopyAlertBand(parent)
        parent.layout().insertWidget(0, self._alert_band)

        # 2. 根系询问台 - 已移除
        # self._inquiry_deck = RootInquiryDeck(parent)
        # parent.layout().addWidget(self._inquiry_deck)
        # # 默认隐藏根系询问台
        # self._inquiry_deck.hide()

        # 3. 沃土状态栏 - 底部（替换原有状态栏）
        self._status_rail = SoilStatusRail(parent)
        parent.layout().addWidget(self._status_rail)

    @property
    def alert(self) -> CanopyAlertBand:
        """林冠警报带"""
        return self._alert_band

    # @property
    # def inquiry(self) -> RootInquiryDeck:
    #     """根系询问台"""
    #     return self._inquiry_deck

    @property
    def status(self) -> SoilStatusRail:
        """沃土状态栏"""
        return self._status_rail

    @property
    def hint(self) -> type:
        """晨露提示卡（静态类）"""
        return DewdropHintCard

    def show_success(self, message: str, auto_hide_ms: int = 3000):
        """显示成功提示（便捷方法）"""
        self._alert_band.show_alert(message, "success", auto_hide_ms=auto_hide_ms)

    def show_warning(self, message: str, actions: list = None):
        """显示警告（便捷方法）"""
        self._alert_band.show_alert(message, "warning", actions=actions)

    def show_error(self, message: str, actions: list = None):
        """显示错误（便捷方法）"""
        self._alert_band.show_alert(message, "error", actions=actions, auto_hide_ms=5000)

    # def ask_confirm(
    #     self,
    #     title: str,
    #     message: str,
    #     confirm_text: str = "确认",
    #     cancel_text: str = "取消",
    #     on_confirm=None,
    #     on_cancel=None,
    #     risk_level: str = "low"
    # ):
    #     """
    #     显示确认询问（便捷方法）

    #     Args:
    #         title: 标题
    #         message: 消息
    #         confirm_text: 确认按钮文本
    #         cancel_text: 取消按钮文本
    #         on_confirm: 确认回调
    #         on_cancel: 取消回调
    #         risk_level: 风险等级 low/medium/high
    #     """
    #     icons = {"low": "💡", "medium": "⚠️", "high": "🚨"}
    #     self._inquiry_deck.ask(
    #         title=f"{icons.get(risk_level, '💡')} {title}",
    #         description=message,
    #         icon=icons.get(risk_level, "💡"),
    #         options=[
    #             ("confirm", confirm_text, on_confirm),
    #             ("cancel", cancel_text, on_cancel or (lambda: None))
    #         ]
    #     )

    # def ask_delete(self, item_name: str, on_confirm=None):
    #     """显示删除确认（便捷方法）"""
    #     self.ask_confirm(
    #         title="确认删除",
    #         message=f"确定要删除「{item_name}」吗？此操作不可撤销。",
    #         confirm_text="确认删除",
    #         on_confirm=on_confirm,
    #         risk_level="high"
    #     )

    # def ask_risk(self, action: str, risk_level: str = "medium", on_confirm=None):
    #     """显示风险确认"""
    #     self._inquiry_deck.ask_risk_confirm(action, risk_level, on_confirm)

    def set_busy(self, message: str = "处理中..."):
        """设置忙状态"""
        self._status_rail.show_progress(message, -1)

    def set_progress(self, progress: int, message: str = None):
        """设置进度"""
        if message:
            self._status_rail.update_progress(progress, message)
        else:
            self._status_rail.update_progress(progress)

    def clear_status(self):
        """清除状态"""
        self._status_rail.clear()

    def cleanup(self):
        """清理所有组件"""
        DewdropHintCard.dismiss_all()
        self._status_rail.clear()
        # self._inquiry_deck.hide_deck()
        self._alert_band.hide_alert()
