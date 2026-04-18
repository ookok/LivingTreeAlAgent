"""
Device Optimizer - 设备优化器
===========================

根据设备自动优化体验
"""

import re
import platform
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class DeviceInfo:
    """设备信息"""
    type: str  # desktop/phone/tablet/tv
    os: str  # windows/macos/linux/android/ios/unknown
    browser: str  # chrome/firefox/safari/edge/unknown
    is_mobile: bool
    is_tablet: bool
    has_keyboard: bool
    has_stylus: bool
    screen_width: int
    screen_height: int
    pixel_ratio: float
    supports_webgl: bool
    supports_pwa: bool
    supports_websocket: bool
    connection_type: str  # wifi/cellular/none/unknown


class DeviceOptimizer:
    """
    设备优化器

    根据设备信息自动优化功能和UI
    """

    def __init__(self):
        self._device_info: Optional[DeviceInfo] = None
        self._optimizations: Dict[str, bool] = {}

    def detect_from_user_agent(self, user_agent: str) -> DeviceInfo:
        """
        从User-Agent检测设备信息

        Args:
            user_agent: 浏览器的User-Agent字符串

        Returns:
            DeviceInfo: 设备信息
        """
        ua = user_agent.lower()

        info = DeviceInfo(
            type="desktop",
            os=self._detect_os(ua),
            browser=self._detect_browser(ua),
            is_mobile=False,
            is_tablet=False,
            has_keyboard=True,
            has_stylus=False,
            screen_width=1920,
            screen_height=1080,
            pixel_ratio=1.0,
            supports_webgl=True,
            supports_pwa=True,
            supports_websocket=True,
            connection_type="unknown"
        )

        # 检测移动设备
        if any(x in ua for x in ["iphone", "ipod", "android", "mobile", "blackberry"]):
            info.is_mobile = True
            info.type = "phone"
            info.has_keyboard = False

        # 检测平板
        if "ipad" in ua or ("android" in ua and "mobile" not in ua):
            info.type = "tablet"
            info.is_tablet = True

        # iOS检测
        if "ipad" in ua or "iphone" in ua or "ipod" in ua:
            info.os = "ios"
            info.has_keyboard = False

        # Android检测
        if "android" in ua:
            info.os = "android"
            if "mobile" not in ua:
                info.type = "tablet"
                info.is_tablet = True

        return info

    def detect_from_system(self) -> DeviceInfo:
        """
        从系统环境检测设备信息

        Returns:
            DeviceInfo: 设备信息
        """
        system = platform.system().lower()

        os_map = {
            "windows": "windows",
            "darwin": "macos",
            "linux": "linux",
        }

        info = DeviceInfo(
            type="desktop",
            os=os_map.get(system, "unknown"),
            browser="native",  # 桌面应用
            is_mobile=False,
            is_tablet=False,
            has_keyboard=True,
            has_stylus=False,
            screen_width=1920,
            screen_height=1080,
            pixel_ratio=1.0,
            supports_webgl=True,
            supports_pwa=False,
            supports_websocket=True,
            connection_type="wifi"
        )

        return info

    def _detect_os(self, ua: str) -> str:
        """检测操作系统"""
        if "windows" in ua:
            return "windows"
        elif "macintosh" in ua or "mac os" in ua:
            return "macos"
        elif "linux" in ua:
            return "linux"
        elif "android" in ua:
            return "android"
        elif "iphone" in ua or "ipad" in ua or "ipod" in ua:
            return "ios"
        elif "tv" in ua or "appletv" in ua:
            return "tv"
        return "unknown"

    def _detect_browser(self, ua: str) -> str:
        """检测浏览器"""
        if "edg/" in ua or "edge/" in ua:
            return "edge"
        elif "chrome/" in ua and "safari/" in ua and "chromium" not in ua:
            return "chrome"
        elif "firefox/" in ua:
            return "firefox"
        elif "safari/" in ua and "chrome" not in ua:
            return "safari"
        elif "opera" in ua or "opr/" in ua:
            return "opera"
        elif "msie" in ua or "trident/" in ua:
            return "ie"
        return "unknown"

    def optimize_for_device(self, device_info: DeviceInfo) -> Dict[str, Any]:
        """
        根据设备信息生成优化配置

        Returns:
            优化配置字典
        """
        optimizations = {
            # UI优化
            "ui": self._optimize_ui(device_info),

            # 功能优化
            "features": self._optimize_features(device_info),

            # 性能优化
            "performance": self._optimize_performance(device_info),

            # 网络优化
            "network": self._optimize_network(device_info),
        }

        self._device_info = device_info
        self._optimizations = optimizations

        return optimizations

    def _optimize_ui(self, info: DeviceInfo) -> Dict[str, Any]:
        """UI优化"""
        if info.type == "desktop":
            return {
                "layout": "full",  # 完整布局
                "sidebar": True,
                "toolbar": True,
                "font_size": 14,
                "icon_size": 24,
                "animation": True,
                "transitions": True,
            }
        elif info.type == "tablet":
            return {
                "layout": "adaptive",  # 自适应
                "sidebar": True,
                "toolbar": True,
                "font_size": 15,
                "icon_size": 32,
                "animation": True,
                "transitions": True,
                "split_view": True,  # 分屏支持
            }
        else:  # phone
            return {
                "layout": "mobile",  # 移动布局
                "sidebar": False,
                "toolbar": False,
                "bottom_nav": True,  # 底部导航
                "font_size": 14,
                "icon_size": 40,
                "animation": False,
                "transitions": False,
                "pull_to_refresh": True,
            }

    def _optimize_features(self, info: DeviceInfo) -> Dict[str, bool]:
        """功能优化"""
        features = {
            # 基础功能（所有设备）
            "basic_routing": True,
            "status_view": True,
            "quick_toggle": True,

            # 桌面专属
            "keyboard_shortcuts": info.type == "desktop",
            "multi_window": info.type == "desktop",
            "full_editor": info.type == "desktop",
            "advanced_config": info.type == "desktop",

            # 平板专属
            "split_screen": info.is_tablet,
            "stylus_input": info.has_stylus,
            "desktop_mode": info.type == "desktop" or (info.is_tablet and info.has_keyboard),

            # 移动专属
            "voice_input": info.is_mobile,
            "gesture_control": info.is_mobile,
            "haptic_feedback": info.is_mobile,
            "qr_scan": info.is_mobile,

            # PWA
            "pwa_install": info.supports_pwa,
            "offline_mode": info.supports_pwa,

            # 高级
            "ai_suggestions": True,
            "auto_update": True,
            "background_sync": info.supports_pwa,
        }

        return features

    def _optimize_performance(self, info: DeviceInfo) -> Dict[str, Any]:
        """性能优化"""
        if info.type == "desktop":
            return {
                "cache_size_mb": 100,
                "max_connections": 10,
                "preload_enabled": True,
                "lazy_load_images": False,
                "compression": True,
                "max_concurrent_downloads": 5,
            }
        elif info.is_tablet:
            return {
                "cache_size_mb": 50,
                "max_connections": 6,
                "preload_enabled": True,
                "lazy_load_images": True,
                "compression": True,
                "max_concurrent_downloads": 3,
            }
        else:  # phone
            return {
                "cache_size_mb": 20,
                "max_connections": 4,
                "preload_enabled": False,
                "lazy_load_images": True,
                "compression": True,
                "max_concurrent_downloads": 2,
            }

    def _optimize_network(self, info: DeviceInfo) -> Dict[str, Any]:
        """网络优化"""
        if info.connection_type == "cellular":
            return {
                "auto_update": False,
                "high_res_images": False,
                "background_sync": False,
                "aggressive_caching": True,
                "batch_requests": True,
            }
        elif info.connection_type == "wifi":
            return {
                "auto_update": True,
                "high_res_images": True,
                "background_sync": True,
                "aggressive_caching": False,
                "batch_requests": False,
            }
        else:
            return {
                "auto_update": False,
                "high_res_images": False,
                "background_sync": False,
                "aggressive_caching": True,
                "batch_requests": True,
            }

    def get_recommended_ui_mode(self, info: DeviceInfo) -> str:
        """
        获取推荐的UI模式

        Returns:
            str: desktop/tablet/mobile/compact
        """
        if info.type == "desktop":
            return "desktop"
        elif info.is_tablet:
            return "tablet"
        elif info.is_mobile:
            return "mobile"
        return "compact"

    def should_show_feature(self, feature: str) -> bool:
        """检查是否应该显示某个功能"""
        if not self._optimizations:
            return True

        # 遍历所有优化配置检查
        for category in self._optimizations.values():
            if isinstance(category, dict) and feature in category:
                return category[feature]

        return True


# ==================== JavaScript设备检测 ====================

DEVICE_DETECTION_JS = """
// 设备检测JavaScript
function detectDevice() {
    const ua = navigator.userAgent.toLowerCase();

    const info = {
        type: 'desktop',
        os: 'unknown',
        browser: 'unknown',
        is_mobile: false,
        is_tablet: false,
        has_keyboard: true,
        has_stylus: false,
        screen_width: window.screen.width,
        screen_height: window.screen.height,
        pixel_ratio: window.devicePixelRatio || 1,
        supports_webgl: false,
        supports_pwa: 'serviceWorker' in navigator,
        supports_websocket: true,
        connection_type: 'unknown'
    };

    // 检测OS
    if (ua.includes('windows')) info.os = 'windows';
    else if (ua.includes('macintosh') || ua.includes('mac os')) info.os = 'macos';
    else if (ua.includes('linux')) info.os = 'linux';
    else if (ua.includes('android')) info.os = 'android';
    else if (ua.includes('iphone') || ua.includes('ipad') || ua.includes('ipod')) info.os = 'ios';

    // 检测浏览器
    if (ua.includes('edg/')) info.browser = 'edge';
    else if (ua.includes('chrome/')) info.browser = 'chrome';
    else if (ua.includes('firefox/')) info.browser = 'firefox';
    else if (ua.includes('safari/') && !ua.includes('chrome')) info.browser = 'safari';

    // 检测移动设备
    if (/iphone|ipod|android|mobile|blackberry/i.test(ua)) {
        info.is_mobile = true;
        info.type = 'phone';
        info.has_keyboard = false;
    }

    // 检测平板
    if (ua.includes('ipad') || (ua.includes('android') && !ua.includes('mobile'))) {
        info.type = 'tablet';
        info.is_tablet = true;
    }

    // 检测TV
    if (ua.includes('tv') || ua.includes('appletv')) {
        info.type = 'tv';
    }

    // WebGL支持
    try {
        const canvas = document.createElement('canvas');
        info.supports_webgl = !!(canvas.getContext('webgl') || canvas.getContext('experimental-webgl'));
    } catch (e) {
        info.supports_webgl = false;
    }

    // 网络连接类型
    if (navigator.connection) {
        const conn = navigator.connection;
        info.connection_type = conn.effectiveType || 'unknown';
    }

    return info;
}

// 导出设备信息
window.deviceInfo = detectDevice();
"""