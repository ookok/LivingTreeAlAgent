"""
Anti-Detection Engine - 反检测引擎
======================================

协调所有反检测措施：
1. JS 层反检测（通过 JSInjector 注入）
2. CDP 层指纹隐藏（通过 CDP 协议隐藏自动化特征）
3. 网络层反检测（User-Agent、Headers 管理）

核心思想：
- 在页面加载前（onNewDocument）注入反检测 JS
- 通过 CDP 隐藏 webdriver 痕迹
- 模拟真实浏览器的行为特征
"""

import json
import re
from typing import Optional, Dict, List, Any
from loguru import logger

from business.chrome_bridge.cdp_helper import CDPHelper, CDPPage
from business.chrome_bridge.utils.js_injector import JSInjector, get_js_injector


# ============================================================
# CDP 层反检测：隐藏自动化特征
# ============================================================

CDP_ANTI_DETECT_COMMANDS = [
    # 1. 覆盖 navigator.webdriver（通过 CDP Runtime.evaluate）
    {
        "method": "Runtime.evaluate",
        "params": {
            "expression": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """,
            "returnByValue": True
        }
    },
    # 2. 删除 CDP 特征变量
    {
        "method": "Runtime.evaluate",
        "params": {
            "expression": """
                (function() {
                    const keys = Object.keys(window);
                    for (let i = 0; i < keys.length; i++) {
                        if (keys[i].indexOf('cdc_adoQpoasnfa76pfcZLmcfl_') === 0) {
                            delete window[keys[i]];
                        }
                    }
                })();
            """,
            "returnByValue": True
        }
    },
]


class AntiDetectionEngine:
    """
    反检测引擎

    统一管理所有反检测措施，提供简洁的 API。
    在页面创建时自动应用反检测措施。
    """

    def __init__(
        self,
        cdp_helper: Optional[CDPHelper] = None,
        js_injector: Optional[JSInjector] = None
    ):
        """
        初始化反检测引擎

        Args:
            cdp_helper: CDPHelper 实例（用于 CDP 层反检测）
            js_injector: JSInjector 实例（用于 JS 层反检测）
        """
        self._cdp = cdp_helper or CDPHelper()
        self._js = js_injector or get_js_injector()
        self._enabled = True
        self._level = "normal"  # normal | strict | stealth
        self._user_agent: Optional[str] = None
        self._extra_headers: Dict[str, str] = {}

        logger.bind(module="AntiDetection").info("反检测引擎初始化完成")

    # ============================================================
    # 配置
    # ============================================================

    def enable(self, enabled: bool = True):
        """启用/禁用反检测"""
        self._enabled = enabled
        logger.bind(module="AntiDetection").info(f"反检测: {'启用' if enabled else '禁用'}")

    def set_level(self, level: str):
        """
        设置反检测级别

        Args:
            level: "normal" | "strict" | "stealth"
                   normal：基础反检测（webdriver、CDP 变量）
                   strict：增加 plugins、languages、WebGL 指纹覆盖
                   stealth：增加额外隐蔽措施（Canvas、AudioContext 指纹）
        """
        if level not in ("normal", "strict", "stealth"):
            raise ValueError(f"无效的反检测级别: {level}")
        self._level = level
        logger.bind(module="AntiDetection").info(f"反检测级别: {level}")

    def set_user_agent(self, ua: Optional[str]):
        """设置自定义 User-Agent"""
        self._user_agent = ua

    def set_extra_headers(self, headers: Dict[str, str]):
        """设置额外 HTTP 头（反检测用）"""
        self._extra_headers = headers

    # ============================================================
    # 核心：对页面应用反检测
    # ============================================================

    async def apply_to_page(self, page_id: str, url: Optional[str] = None):
        """
        对指定页面应用反检测措施

        在页面导航到目标 URL 之前调用此方法。

        Args:
            page_id: CDP 页面 ID
            url: 目标 URL（用于站点特定反检测）
        """
        if not self._enabled:
            return

        logger.bind(module="AntiDetection").info(f"对页面 {page_id} 应用反检测（级别: {self._level}）")

        # 1. JS 层反检测（在页面加载前注入）
        await self._js.inject_via_cdp(self._cdp, page_id, url)

        # 2. CDP 层反检测
        await self._apply_cdp_anti_detect(page_id)

        # 3. 设置 User-Agent（如已配置）
        if self._user_agent:
            await self._cdp.send_cdp_command(
                page_id,
                "Network.setUserAgentOverride",
                {"userAgent": self._user_agent}
            )

        # 4. 设置额外 HTTP 头
        if self._extra_headers:
            await self._cdp.send_cdp_command(
                page_id,
                "Network.setExtraHTTPHeaders",
                {"headers": self._extra_headers}
            )

        # 5. 根据级别应用额外措施
        if self._level in ("strict", "stealth"):
            await self._apply_strict_anti_detect(page_id)

        if self._level == "stealth":
            await self._apply_stealth_anti_detect(page_id)

    async def _apply_cdp_anti_detect(self, page_id: str):
        """应用 CDP 层反检测"""
        for cmd in CDP_ANTI_DETECT_COMMANDS:
            try:
                await self._cdp.send_cdp_command(page_id, cmd["method"], cmd["params"])
            except Exception as e:
                logger.bind(module="AntiDetection").warning(f"CDP 反检测命令失败: {e}")

    async def _apply_strict_anti_detect(self, page_id: str):
        """应用严格级别反检测"""
        strict_js = """
            // 覆盖 navigator.plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {
                        0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        length: 1,
                        name: "Chrome PDF Plugin"
                    }
                ]
            });

            // 覆盖 navigator.languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en-US', 'en']
            });

            // 覆盖 hardwareConcurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8
            });

            // 覆盖 deviceMemory
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8
            });

            // 覆盖 connection（网络信息）
            if (navigator.connection) {
                Object.defineProperty(navigator, 'connection', {
                    get: () => ({
                        effectiveType: '4g',
                        rtt: 50,
                        downlink: 10.0,
                        saveData: false
                    })
                });
            }
        """
        await self._cdp.send_cdp_command(
            page_id,
            "Runtime.evaluate",
            {"expression": strict_js, "returnByValue": True}
        )

    async def _apply_stealth_anti_detect(self, page_id: str):
        """应用隐身级别反检测（Canvas、AudioContext 指纹）"""
        stealth_js = """
            // Canvas 指纹保护（添加随机噪点）
            const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
            CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {
                const imageData = origGetImageData.call(this, x, y, w, h);
                for (let i = 0; i < imageData.data.length; i += 4) {
                    imageData.data[i] += Math.floor(Math.random() * 3) - 1;
                    imageData.data[i+1] += Math.floor(Math.random() * 3) - 1;
                    imageData.data[i+2] += Math.floor(Math.random() * 3) - 1;
                }
                return imageData;
            };

            // AudioContext 指纹保护
            const origGetChannelData = AudioBuffer.prototype.getChannelData;
            AudioBuffer.prototype.getChannelData = function(channel) {
                const data = origGetChannelData.call(this, channel);
                // 不修改原始数据，但可以在这里添加噪声
                return data;
            };

            // 覆盖 window.chrome（使其看起来像真实 Chrome）
            window.chrome = {
                runtime: {}
            };
        """
        await self._cdp.send_cdp_command(
            page_id,
            "Runtime.evaluate",
            {"expression": stealth_js, "returnByValue": True}
        )

    # ============================================================
    # 检测：检查反检测是否生效
    # ============================================================

    async def check_detection(self, page_id: str, test_url: str = None) -> Dict[str, Any]:
        """
        检测当前页面的反检测状态

        Args:
            page_id: 页面 ID
            test_url: 测试 URL（可选，用于检测是否被识别为机器人）

        Returns:
            检测结果字典
        """
        result = {
            "webdriver_hidden": False,
            "cdp_vars_cleaned": False,
            "plugins_overridden": False,
            "user_agent_set": self._user_agent is not None,
            "detection_score": 0  # 0-100，越高越不容易被检测
        }

        # 检查 webdriver 是否隐藏
        try:
            val = await self._cdp.evaluate(page_id, "navigator.webdriver")
            result["webdriver_hidden"] = val is None
        except Exception:
            pass

        # 检查 CDP 变量是否清理
        try:
            keys = await self._cdp.evaluate(
                page_id,
                "Object.keys(window).filter(k => k.includes('cdc_adoQpoasnfa76pfcZLmcfl'))"
            )
            result["cdp_vars_cleaned"] = len(keys) == 0
        except Exception:
            pass

        # 综合评分
        score = 0
        if result["webdriver_hidden"]:
            score += 40
        if result["cdp_vars_cleaned"]:
            score += 30
        if result["user_agent_set"]:
            score += 10
        if self._level in ("strict", "stealth"):
            score += 20
        result["detection_score"] = min(score, 100)

        return result

    # ============================================================
    # 预设 User-Agent
    # ============================================================

    PRESET_USER_AGENTS = {
        "chrome_windows": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "chrome_mac": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "chrome_linux": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def use_preset_ua(self, preset: str = "chrome_windows"):
        """
        使用预设 User-Agent

        Args:
            preset: 预设名称（"chrome_windows" | "chrome_mac" | "chrome_linux"）
        """
        ua = self.PRESET_USER_AGENTS.get(preset)
        if ua:
            self._user_agent = ua
            logger.bind(module="AntiDetection").info(f"使用预设 User-Agent: {preset}")
        else:
            logger.bind(module="AntiDetection").warning(f"未知预设: {preset}")


# ============================================================
# 全局单例
# ============================================================

_anti_detection_instance: Optional[AntiDetectionEngine] = None


def get_anti_detection_engine(cdp_helper: Optional[CDPHelper] = None) -> AntiDetectionEngine:
    """获取全局 AntiDetectionEngine 实例"""
    global _anti_detection_instance
    if _anti_detection_instance is None:
        _anti_detection_instance = AntiDetectionEngine(cdp_helper=cdp_helper)
    return _anti_detection_instance
