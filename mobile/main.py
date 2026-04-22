"""
Hermes Desktop Mobile - 移动端主入口
==================================

Kivy 移动端应用入口

Usage:
    python mobile/main.py          # 启动移动端
    python mobile/main.py --debug  # 调试模式
"""

import sys
import argparse
import logging

try:
    from kivy.app import App
    from kivy.uix.screenmanager import ScreenManager
    from kivy.core.window import Window
    from kivy.config import Config
    KIVY_AVAILABLE = True
except ImportError:
    KIVY_AVAILABLE = False
    print("Kivy not installed. Install with: pip install kivy")
    sys.exit(1)

from mobile.adaptive_layout import AdaptiveManager, get_adaptive_manager
from mobile.screens import MobileScreenManager, ChatScreen, SkillsScreen, SettingsScreen
from mobile.tablet_features import TabletEnhancementManager
from mobile.pwa_integration import PWAManager, get_pwa_manager


logger = logging.getLogger(__name__)


class HermesMobileApp(App):
    """Hermes Desktop 移动端应用"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.adaptive_manager = get_adaptive_manager()
        self.tablet_manager = TabletEnhancementManager()
        self.pwa_manager = get_pwa_manager()
        self.screen_manager = None

    def build(self):
        """构建应用"""
        # 设置窗口
        self._setup_window()

        # 创建屏幕管理器
        self.screen_manager = MobileScreenManager()

        # 根据设备类型启用平板功能
        self._enable_tablet_features()

        # 返回根视图
        return self.screen_manager

    def _setup_window(self):
        """设置窗口"""
        device_type = self.adaptive_manager.device_type

        if device_type in ("phone", "phablet"):
            # 手机：全屏，固定方向
            Config.set('graphics', 'fullscreen', 'auto')
            Config.set('graphics', 'resizable', '1')
            Window.size = (360, 640)  # 默认手机尺寸
        else:
            # 平板：自适应
            Config.set('graphics', 'resizable', '1')
            Window.size = (800, 600)

    def _enable_tablet_features(self):
        """根据设备类型启用平板功能"""
        device_type = self.adaptive_manager.device_type
        self.tablet_manager.enable_tablet_features(device_type)

    def on_start(self):
        """应用启动"""
        logger.info(f"移动端应用启动: device={self.adaptive_manager.device_type}")
        logger.info(f"屏幕方向: {self.adaptive_manager.orientation}")
        logger.info(f"屏幕尺寸: {Window.width}x{Window.height}")

    def on_stop(self):
        """应用停止"""
        logger.info("移动端应用停止")


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="Hermes Desktop Mobile")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    parser.add_argument("--device", choices=["phone", "tablet"], help="模拟设备类型")
    args = parser.parse_args()

    if args.device:
        # 模拟设备类型
        from mobile.adaptive_layout import DeviceDetector
        if args.device == "phone":
            Window.size = (360, 640)
        else:
            Window.size = (800, 600)

    app = HermesMobileApp()
    app.run()


if __name__ == "__main__":
    main()
