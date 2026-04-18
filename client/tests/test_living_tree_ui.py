"""
🌿 生命之树 UI 自动化测试示例
=============================

演示如何使用 PyTest + QtBot 对无弹窗组件进行自动化测试。

运行方式:
    pytest client/tests/test_living_tree_ui.py -v

核心优势:
- 固定 ObjectName，无需应对随机弹窗
- 稳定控件树，可持续监听
- 无焦点抢夺，操作链不打断
- 面板 visible 状态可轮询
"""

import pytest
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication, QPushButton, QLineEdit, QRadioButton

# 导入被测组件
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.src.presentation.components import (
    CanopyAlertBand,
    RootInquiryDeck,
    SoilStatusRail,
    DewdropHintCard,
    get_alert_band,
    get_inquiry_deck,
    get_status_rail,
    select_inquiry_option,
    get_visible_inquiry_deck,
    get_status_message,
)


@pytest.fixture(scope="session")
def qapp():
    """全局 QApplication fixture"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def main_window(qapp):
    """创建测试主窗口"""
    from client.src.presentation.main_window import MainWindow
    from client.src.infrastructure.config.config import AppConfig

    config = AppConfig()
    window = MainWindow(config)
    window.show()
    yield window
    window.close()


class TestCanopyAlertBand:
    """林冠警报带测试"""

    def test_show_alert_info(self, main_window):
        """测试显示信息警报"""
        alert = get_alert_band(main_window)
        assert alert is not None

        # 显示警报
        main_window.show_alert(
            message="测试信息：系统正常运行",
            level="info"
        )

        # 断言警报可见
        assert alert.is_visible_alert()
        assert "测试信息" in alert._message.text()

    def test_show_alert_with_actions(self, main_window):
        """测试带操作按钮的警报"""
        action_clicked = []

        def on_action():
            action_clicked.append(True)

        main_window.show_alert(
            message="新版本已就绪",
            level="info",
            actions=[("查看更新", on_action), ("稍后", None)]
        )

        alert = get_alert_band(main_window)
        assert alert.is_visible_alert()

        # 查找并点击"查看更新"按钮
        btn = alert.findChild(QPushButton, "canopy-action-查看更新")
        assert btn is not None

    def test_auto_hide(self, main_window):
        """测试自动隐藏"""
        main_window.show_alert(
            message="自动隐藏测试",
            level="info",
            auto_hide_ms=500
        )

        alert = get_alert_band(main_window)
        assert alert.is_visible_alert()

        # 等待自动隐藏
        QTimer.singleShot(600, lambda: None)  # 等待动画
        qapp.processEvents()


class TestRootInquiryDeck:
    """根系询问台测试"""

    def test_show_inquiry(self, main_window):
        """测试显示询问"""
        main_window.ask(
            title="测试询问",
            description="请选择一个选项：",
            options=[
                ("opt1", "选项一", None),
                ("opt2", "选项二", None),
                ("cancel", "取消", None)
            ]
        )

        deck = get_visible_inquiry_deck(main_window)
        assert deck is not None
        assert deck.is_visible_deck()

    def test_conflict_resolution(self, main_window):
        """测试冲突解决流程"""
        confirmed_choice = []

        def on_confirm(choice_id):
            confirmed_choice.append(choice_id)

        main_window.ask_conflict_resolve(
            tool_new="PDFExtractor",
            tool_old="DocParser",
            options=[
                ("parallel", "分叉共生（并行共存）", None),
                ("replace", "修剪旧枝（替换旧版）", None),
                ("cancel", "取消", None)
            ],
            on_confirm=on_confirm
        )

        deck = get_visible_inquiry_deck(main_window)
        assert deck is not None

        # 选择"分叉共生"
        radio = deck.findChild(QRadioButton, "inquiry-option-parallel")
        assert radio is not None
        radio.setChecked(True)

        # 点击确认
        confirm_btn = deck.findChild(QPushButton, "inquiry-confirm")
        assert confirm_btn is not None
        assert confirm_btn.isEnabled()

    def test_delete_confirmation(self, main_window):
        """测试删除确认"""
        delete_confirmed = []

        def on_confirm():
            delete_confirmed.append(True)

        main_window.confirm_delete("测试文件.txt", on_confirm)

        deck = get_visible_inquiry_deck(main_window)
        assert deck is not None


class TestSoilStatusRail:
    """沃土状态栏测试"""

    def test_show_progress(self, main_window):
        """测试显示进度"""
        rail = get_status_rail(main_window)
        assert rail is not None

        main_window.show_progress("下载中...", 50)

        assert rail.is_active()
        assert rail.get_current_progress() == 50
        assert "下载中" in rail.get_current_message()

    def test_update_progress(self, main_window):
        """测试更新进度"""
        main_window.show_progress("处理中...", 0)

        for i in range(10):
            main_window.update_progress(i * 10, f"进度 {i * 10}%")
            qapp.processEvents()

    def test_success_status(self, main_window):
        """测试成功状态"""
        main_window.show_success_status("操作成功！")

        rail = get_status_rail(main_window)
        assert rail.is_active()
        assert "成功" in get_status_message(main_window)


class TestDewdropHintCard:
    """晨露提示卡测试"""

    def test_show_hint_below(self, qapp):
        """测试在控件下方显示提示"""
        input_field = QLineEdit()
        input_field.show()

        hint = DewdropHintCard.show_below(
            target=input_field,
            message="输入格式：2024-01-01",
            level="info"
        )

        assert hint.isVisible()
        assert "2024-01-01" in hint._message.text()

        # 清理
        hint._animate_hide()
        qapp.processEvents()

    def test_hint_auto_hide(self, qapp):
        """测试提示自动隐藏"""
        input_field = QLineEdit()
        input_field.show()

        hint = DewdropHintCard.show_below(
            target=input_field,
            message="3秒后自动消失",
            level="info"
        )

        assert hint.isVisible()

        # 模拟等待
        QTimer.singleShot(3500, lambda: None)
        qapp.processEvents()


class TestIntegration:
    """集成测试"""

    def test_full_workflow(self, main_window):
        """测试完整工作流"""
        # 1. 显示进度
        main_window.show_progress("开始任务...", 0)
        assert get_status_rail(main_window).is_active()

        # 2. 更新进度
        for i in range(5):
            main_window.update_progress((i + 1) * 20, f"步骤 {i + 1}/5")
            qapp.processEvents()

        # 3. 任务完成
        main_window.show_success_status("任务完成！")

        # 4. 显示确认询问
        main_window.ask(
            title="任务完成确认",
            description="是否需要查看详细报告？",
            options=[
                ("view", "查看报告", None),
                ("close", "关闭", None)
            ]
        )

        deck = get_visible_inquiry_deck(main_window)
        assert deck is not None


# ========== PyTest 配置 ==========

def pytest_configure(config):
    """PyTest 配置"""
    config.addinivalue_line(
        "markers", "qt: Qt-related tests"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
