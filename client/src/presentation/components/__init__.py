"""
🌿 生命之树风格 · 无弹窗组件库
========================

提供无弹窗、醒目且可测试的 UI 交互范式。

组件列表:
- CanopyAlertBand (林冠警报带): 顶部全局提醒
- RootInquiryDeck (根系询问台): 右侧边栏确认
- SoilStatusRail (沃土状态栏): 底部进度状态
- DewdropHintCard (晨露提示卡): 上下文提示卡

自动化测试友好性:
- 固定 ObjectName (canopy-alert-band, root-inquiry-deck, soil-status-rail, dewdrop-hint)
- 稳定控件树
- 无焦点抢夺
- 可轮询状态
"""

from .canopy_alert import CanopyAlertBand, get_alert_band, assert_alert_visible
from .inquiry_deck import RootInquiryDeck, get_inquiry_deck, get_visible_inquiry_deck, select_inquiry_option
from .status_rail import SoilStatusRail, get_status_rail, wait_for_status_active, get_status_message
from .dewdrop_hint import DewdropHintCard, show_hint_below, show_hint_right, get_all_hints, get_visible_hints
from .living_tree_ui import LivingTreeUI

__all__ = [
    # 组件类
    "CanopyAlertBand",
    "RootInquiryDeck",
    "SoilStatusRail",
    "DewdropHintCard",
    "LivingTreeUI",
    # 辅助函数
    "get_alert_band",
    "assert_alert_visible",
    "get_inquiry_deck",
    "get_visible_inquiry_deck",
    "select_inquiry_option",
    "get_status_rail",
    "wait_for_status_active",
    "get_status_message",
    "show_hint_below",
    "show_hint_right",
    "get_all_hints",
    "get_visible_hints",
]
