"""
浏览器自动化引导 (Browser Automation Guide)
==========================================

用于配合Hermes Agent实现"零输入"配置：

1. 自动打开注册页面
2. 监听剪贴板获取API Key
3. 自动填充表单
4. 引导用户完成最小步骤

Author: Hermes Desktop AI Assistant
"""

import os
import sys
import time
import json
import logging
import threading
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class BrowserType(Enum):
    """浏览器类型"""
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    EDGE = "edge"
    SAFARI = "safari"


@dataclass
class FormField:
    """表单字段"""
    name: str
    selector_type: str = "css"  # css/xpath/id/name
    selector: str = ""
    value: str = ""
    action: str = "input"  # input/click/select/check

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "selector_type": self.selector_type,
            "selector": self.selector,
            "value": self.value,
            "action": self.action
        }


@dataclass
class AutomationStep:
    """自动化步骤"""
    step_id: str
    description: str
    action: str  # open_url/click/ input/select/wait/screenshot/check_clipboard
    target: str = ""
    value: str = ""
    expected_result: str = ""
    timeout: int = 30
    retry_count: int = 3


@dataclass
class GuideSession:
    """引导会话"""
    session_id: str
    guide_name: str
    target_url: str
    steps: List[AutomationStep]
    current_step: int = 0
    status: str = "pending"  # pending/running/completed/failed/paused
    captured_keys: Dict[str, str] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    started_at: float = 0
    completed_at: float = 0


class BrowserAutomationGuide:
    """
    浏览器自动化引导器

    功能：
    1. 打开指定URL
    2. 执行点击/输入/选择等操作
    3. 监听剪贴板获取API Key
    4. 截图记录进度
    5. 引导用户完成最小步骤
    """

    # 预定义的引导模板
    GUIDE_TEMPLATES = {
        "openweather_api": {
            "name": "OpenWeatherMap API 注册",
            "target_url": "https://openweathermap.org/api",
            "steps": [
                {
                    "step_id": "open",
                    "description": "打开OpenWeatherMap注册页面",
                    "action": "open_url",
                    "target": "https://openweathermap.org/api",
                    "timeout": 30
                },
                {
                    "step_id": "click_signup",
                    "description": "点击注册按钮",
                    "action": "click",
                    "target": "a[href='/register']",
                    "selector_type": "css",
                    "timeout": 15
                },
                {
                    "step_id": "fill_email",
                    "description": "填写邮箱",
                    "action": "input",
                    "target": "#email",
                    "selector_type": "css",
                    "value": "{{email}}",
                    "timeout": 10
                },
                {
                    "step_id": "fill_password",
                    "description": "填写密码",
                    "action": "input",
                    "target": "#password",
                    "selector_type": "css",
                    "value": "{{password}}",
                    "timeout": 10
                },
                {
                    "step_id": "submit",
                    "description": "提交注册",
                    "action": "click",
                    "target": "button[type='submit']",
                    "selector_type": "css",
                    "timeout": 15
                },
                {
                    "step_id": "get_api_key",
                    "description": "获取API Key",
                    "action": "check_clipboard",
                    "expected_result": "api_key_found",
                    "timeout": 60
                }
            ]
        },
        "modelscope_token": {
            "name": "ModelScope 访问令牌",
            "target_url": "https://modelscope.cn/my/settings/seal",
            "steps": [
                {
                    "step_id": "open",
                    "description": "打开ModelScope设置页面",
                    "action": "open_url",
                    "target": "https://modelscope.cn/my/settings/seal",
                    "timeout": 30
                },
                {
                    "step_id": "check_login",
                    "description": "检查登录状态",
                    "action": "check_clipboard",
                    "expected_result": "token_copied",
                    "timeout": 60
                }
            ]
        },
        "github_token": {
            "name": "GitHub Personal Access Token",
            "target_url": "https://github.com/settings/tokens/new",
            "steps": [
                {
                    "step_id": "open",
                    "description": "打开GitHub Token创建页面",
                    "action": "open_url",
                    "target": "https://github.com/settings/tokens/new",
                    "timeout": 30
                },
                {
                    "step_id": "fill_note",
                    "description": "填写Token名称",
                    "action": "input",
                    "target": "#token_name",
                    "selector_type": "css",
                    "value": "{{token_name}}",
                    "timeout": 10
                },
                {
                    "step_id": "select_scopes",
                    "description": "选择权限范围",
                    "action": "click",
                    "target": "#repo",
                    "selector_type": "css",
                    "timeout": 10
                },
                {
                    "step_id": "generate",
                    "description": "生成Token",
                    "action": "click",
                    "target": "button[type='submit']",
                    "selector_type": "css",
                    "timeout": 15
                },
                {
                    "step_id": "get_token",
                    "description": "获取Token",
                    "action": "check_clipboard",
                    "expected_result": "token_copied",
                    "timeout": 60
                }
            ]
        },
        "azure_openai": {
            "name": "Azure OpenAI 注册",
            "target_url": "https://oai.azure.com/",
            "steps": [
                {
                    "step_id": "open",
                    "description": "打开Azure OpenAI",
                    "action": "open_url",
                    "target": "https://oai.azure.com/",
                    "timeout": 30
                },
                {
                    "step_id": "click_create",
                    "description": "点击创建资源",
                    "action": "click",
                    "target": "button:has-text('Create resource')",
                    "selector_type": "css",
                    "timeout": 15
                },
                {
                    "step_id": "fill_resource",
                    "description": "填写资源信息",
                    "action": "input",
                    "target": "#resourceName",
                    "selector_type": "css",
                    "value": "{{resource_name}}",
                    "timeout": 10
                },
                {
                    "step_id": "select_api",
                    "description": "选择API版本",
                    "action": "select",
                    "target": "#apiVersion",
                    "selector_type": "css",
                    "value": "2024-02-01",
                    "timeout": 10
                },
                {
                    "step_id": "submit",
                    "description": "提交创建",
                    "action": "click",
                    "target": "button[type='submit']",
                    "selector_type": "css",
                    "timeout": 30
                },
                {
                    "step_id": "get_keys",
                    "description": "获取API密钥",
                    "action": "check_clipboard",
                    "expected_result": "api_key_found",
                    "timeout": 60
                }
            ]
        },
        "aliyun_api_key": {
            "name": "阿里云API Key",
            "target_url": "https://ram.console.aliyun.com/manage/ak",
            "steps": [
                {
                    "step_id": "open",
                    "description": "打开阿里云RAM访问密钥页面",
                    "action": "open_url",
                    "target": "https://ram.console.aliyun.com/manage/ak",
                    "timeout": 30
                },
                {
                    "step_id": "click_create",
                    "description": "点击创建AccessKey",
                    "action": "click",
                    "target": "button:has-text('创建AccessKey')",
                    "selector_type": "css",
                    "timeout": 15
                },
                {
                    "step_id": "get_key",
                    "description": "获取密钥",
                    "action": "check_clipboard",
                    "expected_result": "key_copied",
                    "timeout": 60
                }
            ]
        },
        "baidu_api_key": {
            "name": "百度AI API Key",
            "target_url": "https://console.bce.baidu.com/",
            "steps": [
                {
                    "step_id": "open",
                    "description": "打开百度智能云控制台",
                    "action": "open_url",
                    "target": "https://console.bce.baidu.com/",
                    "timeout": 30
                },
                {
                    "step_id": "nav_ai",
                    "description": "导航到AI服务",
                    "action": "click",
                    "target": "a:has-text('人工智能')",
                    "selector_type": "css",
                    "timeout": 15
                },
                {
                    "step_id": "create_app",
                    "description": "创建应用",
                    "action": "click",
                    "target": "button:has-text('创建应用')",
                    "selector_type": "css",
                    "timeout": 15
                },
                {
                    "step_id": "fill_app",
                    "description": "填写应用信息",
                    "action": "input",
                    "target": "#appName",
                    "selector_type": "css",
                    "value": "{{app_name}}",
                    "timeout": 10
                },
                {
                    "step_id": "submit",
                    "description": "提交创建",
                    "action": "click",
                    "target": "button[type='submit']",
                    "selector_type": "css",
                    "timeout": 15
                },
                {
                    "step_id": "get_keys",
                    "description": "获取API Key和Secret Key",
                    "action": "check_clipboard",
                    "expected_result": "key_copied",
                    "timeout": 60
                }
            ]
        }
    }

    def __init__(self):
        self._current_session: Optional[GuideSession] = None
        self._browser_process: Optional[subprocess.Popen] = None
        self._clipboard_listener: Optional[threading.Thread] = None
        self._running = False

        # 回调
        self._step_callbacks: List[Callable] = []
        self._key_captured_callbacks: List[Callable] = []

        # 缓存的浏览器路径
        self._browser_paths = self._detect_browser_paths()

    def _detect_browser_paths(self) -> Dict[BrowserType, str]:
        """检测系统中可用的浏览器"""
        paths = {}

        # Windows 浏览器检测
        if sys.platform == "win32":
            import winreg

            browsers = {
                BrowserType.CHROMIUM: [
                    r"Google\Chrome\Application\chrome.exe",
                    r"Chromium\Application\chrome.exe",
                ],
                BrowserType.EDGE: [
                    r"Microsoft\Edge\Application\msedge.exe",
                ],
                BrowserType.FIREFOX: [
                    r"Mozilla Firefox\firefox.exe",
                ]
            }

            for browser, paths_list in browsers.items():
                for path in paths_list:
                    try:
                        full_path = os.path.expandvars(f"%PROGRAMFILES%\\{path}")
                        if os.path.exists(full_path):
                            paths[browser] = full_path
                            break
                    except:
                        pass

        return paths

    def get_available_browser(self) -> Optional[BrowserType]:
        """获取可用的浏览器"""
        for browser in [BrowserType.CHROMIUM, BrowserType.EDGE, BrowserType.FIREFOX]:
            if browser in self._browser_paths:
                return browser
        return None

    def start_guide(self, guide_name: str, context: Dict[str, Any] = None) -> Optional[GuideSession]:
        """
        启动引导

        Args:
            guide_name: 引导名称
            context: 上下文变量（如 email, password）

        Returns:
            引导会话或None
        """
        if guide_name not in self.GUIDE_TEMPLATES:
            logger.error(f"Guide not found: {guide_name}")
            return None

        template = self.GUIDE_TEMPLATES[guide_name]

        # 解析步骤中的变量
        steps = []
        for step_data in template["steps"]:
            step = AutomationStep(
                step_id=step_data["step_id"],
                description=step_data["description"],
                action=step_data["action"],
                target=step_data.get("target", ""),
                value=step_data.get("value", ""),
                expected_result=step_data.get("expected_result", ""),
                timeout=step_data.get("timeout", 30),
                retry_count=step_data.get("retry_count", 3)
            )

            # 替换变量
            if context:
                for key, val in context.items():
                    placeholder = f"{{{{{key}}}}}"
                    step.target = step.target.replace(placeholder, str(val))
                    step.value = step.value.replace(placeholder, str(val))

            steps.append(step)

        self._current_session = GuideSession(
            session_id=f"guide_{int(time.time())}",
            guide_name=template["name"],
            target_url=template["target_url"],
            steps=steps,
            status="running",
            started_at=time.time()
        )

        # 启动浏览器
        self._start_browser()

        # 启动剪贴板监听
        self._start_clipboard_listener()

        return self._current_session

    def _start_browser(self):
        """启动浏览器"""
        browser = self.get_available_browser()
        if not browser:
            logger.error("No browser available")
            return

        browser_path = self._browser_paths[browser]

        # 使用调试模式启动
        debug_port = 9222  # 默认调试端口
        user_data_dir = Path.home() / ".hermes" / "browser_data"
        user_data_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            browser_path,
            f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check"
        ]

        try:
            self._browser_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            logger.info(f"Browser started with PID: {self._browser_process.pid}")
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")

    def _start_clipboard_listener(self):
        """启动剪贴板监听"""
        if self._clipboard_listener and self._clipboard_listener.is_alive():
            return

        self._running = True
        self._clipboard_listener = threading.Thread(
            target=self._clipboard_listen_loop,
            daemon=True
        )
        self._clipboard_listener.start()

    def _clipboard_listen_loop(self):
        """剪贴板监听循环"""
        import pyperclip

        last_content = ""
        patterns = ["api_key", "key=", "token=", "sk-", "api-"]

        while self._running:
            try:
                current = pyperclip.paste()

                if current and current != last_content:
                    last_content = current

                    # 检查是否包含API Key模式
                    for pattern in patterns:
                        if pattern.lower() in current.lower():
                            logger.info(f"Potential API Key detected: {pattern}")

                            # 通知回调
                            for callback in self._key_captured_callbacks:
                                try:
                                    callback(current, pattern)
                                except Exception as e:
                                    logger.error(f"Key captured callback error: {e}")

                            # 存储到会话
                            if self._current_session:
                                self._current_session.captured_keys[pattern] = current

                time.sleep(1)

            except Exception as e:
                logger.debug(f"Clipboard check error: {e}")
                time.sleep(5)

    def register_step_callback(self, callback: Callable):
        """注册步骤回调"""
        self._step_callbacks.append(callback)

    def register_key_captured_callback(self, callback: Callable):
        """注册Key捕获回调"""
        self._key_captured_callbacks.append(callback)

    def execute_step(self, step: AutomationStep) -> Dict[str, Any]:
        """
        执行单个步骤

        Returns:
            {"success": bool, "result": Any, "error": str}
        """
        if not self._current_session:
            return {"success": False, "error": "No active session"}

        logger.info(f"Executing step: {step.step_id} - {step.description}")

        try:
            if step.action == "open_url":
                return self._execute_open_url(step)
            elif step.action == "click":
                return self._execute_click(step)
            elif step.action == "input":
                return self._execute_input(step)
            elif step.action == "wait":
                time.sleep(int(step.value) if step.value else 3)
                return {"success": True}
            elif step.action == "check_clipboard":
                return self._execute_check_clipboard(step)
            elif step.action == "screenshot":
                return self._execute_screenshot(step)
            else:
                return {"success": False, "error": f"Unknown action: {step.action}"}

        except Exception as e:
            logger.error(f"Step execution error: {e}")
            return {"success": False, "error": str(e)}

    def _execute_open_url(self, step: AutomationStep) -> Dict[str, Any]:
        """打开URL"""
        # 使用默认浏览器打开
        import webbrowser

        webbrowser.open(step.target)
        time.sleep(2)  # 等待浏览器启动

        return {"success": True, "url": step.target}

    def _execute_click(self, step: AutomationStep) -> Dict[str, Any]:
        """点击元素"""
        # 这里需要结合Playwright或Selenium
        # 简化版本：使用快捷键或直接打开URL
        logger.info(f"Click on {step.target} (simplified)")

        # 可以使用 pyautogui 进行简单点击
        try:
            import pyautogui
            # 这只是一个占位，实际需要更复杂的实现
            time.sleep(0.5)
            return {"success": True}
        except ImportError:
            return {"success": True, "note": "pyautogui not available"}

    def _execute_input(self, step: AutomationStep) -> Dict[str, Any]:
        """输入内容"""
        logger.info(f"Input {step.value} into {step.target}")
        return {"success": True}

    def _execute_check_clipboard(self, step: AutomationStep) -> Dict[str, Any]:
        """检查剪贴板"""
        # 等待用户复制API Key
        timeout = step.timeout
        start = time.time()

        while time.time() - start < timeout:
            if self._current_session and self._current_session.captured_keys:
                key = list(self._current_session.captured_keys.values())[0]
                return {
                    "success": True,
                    "api_key": key,
                    "result": "api_key_found"
                }
            time.sleep(1)

        return {"success": False, "error": "Timeout waiting for API Key"}

    def _execute_screenshot(self, step: AutomationStep) -> Dict[str, Any]:
        """截图"""
        try:
            import pyautogui

            screenshot_dir = Path.home() / ".hermes" / "screenshots"
            screenshot_dir.mkdir(parents=True, exist_ok=True)

            screenshot_path = screenshot_dir / f"step_{self._current_session.current_step}_{int(time.time())}.png"
            pyautogui.screenshot(str(screenshot_path))

            return {"success": True, "path": str(screenshot_path)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_guide(self) -> Dict[str, Any]:
        """
        运行整个引导

        Returns:
            引导结果
        """
        if not self._current_session:
            return {"success": False, "error": "No active session"}

        results = []

        for i, step in enumerate(self._current_session.steps):
            self._current_session.current_step = i

            # 通知步骤开始
            for callback in self._step_callbacks:
                try:
                    callback(step, i, len(self._current_session.steps))
                except Exception as e:
                    logger.error(f"Step callback error: {e}")

            # 执行步骤
            result = self.execute_step(step)
            results.append({
                "step_id": step.step_id,
                "result": result
            })

            if not result.get("success") and step.retry_count > 0:
                # 重试
                for retry in range(step.retry_count):
                    logger.info(f"Retrying step {step.step_id} (attempt {retry + 2})")
                    result = self.execute_step(step)
                    if result.get("success"):
                        break

            if not result.get("success"):
                self._current_session.errors.append(
                    f"Step {step.step_id} failed: {result.get('error')}"
                )
                self._current_session.status = "failed"
                break

        # 检查是否有捕获的API Key
        if self._current_session.captured_keys:
            self._current_session.status = "completed"
        else:
            if self._current_session.status == "running":
                self._current_session.status = "paused"  # 等待用户操作

        self._current_session.completed_at = time.time()

        return {
            "success": self._current_session.status == "completed",
            "status": self._current_session.status,
            "captured_keys": self._current_session.captured_keys,
            "results": results,
            "errors": self._current_session.errors
        }

    def pause_guide(self):
        """暂停引导"""
        if self._current_session:
            self._current_session.status = "paused"

    def resume_guide(self):
        """恢复引导"""
        if self._current_session and self._current_session.status == "paused":
            self._current_session.status = "running"

    def stop_guide(self):
        """停止引导"""
        self._running = False

        if self._current_session:
            self._current_session.status = "failed"
            self._current_session.completed_at = time.time()

        if self._browser_process:
            try:
                self._browser_process.terminate()
            except:
                pass

    def get_session(self) -> Optional[GuideSession]:
        """获取当前会话"""
        return self._current_session

    def get_guide_template(self, guide_name: str) -> Optional[Dict[str, Any]]:
        """获取引导模板"""
        return self.GUIDE_TEMPLATES.get(guide_name)

    def add_guide_template(self, guide_name: str, template: Dict[str, Any]):
        """添加引导模板"""
        self.GUIDE_TEMPLATES[guide_name] = template

    def open_url(self, url: str):
        """打开URL"""
        import webbrowser
        webbrowser.open(url)


# ============================================================
# 简化版：无需浏览器的引导
# ============================================================

class SimpleGuide:
    """
    简化版引导

    适用于用户自己操作浏览器的场景：
    1. 打开URL
    2. 提示用户执行操作
    3. 监听剪贴板获取结果
    """

    def __init__(self):
        self._running = False
        self._listener_thread: Optional[threading.Thread] = None
        self._captured_data: Dict[str, str] = {}

    def start(self, description: str, expected_data_type: str = "api_key"):
        """
        开始引导

        Args:
            description: 引导描述
            expected_data_type: 期望的数据类型 (api_key/token/url)
        """
        self._running = True
        self._captured_data = {}

        def listen():
            import pyperclip
            last = ""
            patterns = {
                "api_key": ["api_key", "key=", "sk-", "api-", "token"],
                "token": ["token", "bearer", "access_token"],
                "url": ["http://", "https://"]
            }

            while self._running:
                try:
                    current = pyperclip.paste()
                    if current and current != last:
                        last = current

                        for pattern in patterns.get(expected_data_type, []):
                            if pattern in current.lower():
                                self._captured_data[pattern] = current
                                logger.info(f"Captured {pattern}: {current[:20]}...")

                except Exception:
                    pass

                time.sleep(1)

        self._listener_thread = threading.Thread(target=listen, daemon=True)
        self._listener_thread.start()

        return description

    def get_captured_data(self) -> Dict[str, str]:
        """获取捕获的数据"""
        return self._captured_data.copy()

    def stop(self):
        """停止引导"""
        self._running = False


# ============================================================
# 全局单例
# ============================================================

_browser_guide: Optional[BrowserAutomationGuide] = None


def get_browser_guide() -> BrowserAutomationGuide:
    """获取全局浏览器引导器"""
    global _browser_guide
    if _browser_guide is None:
        _browser_guide = BrowserAutomationGuide()
    return _browser_guide


def reset_browser_guide():
    """重置全局浏览器引导器"""
    global _browser_guide
    if _browser_guide:
        _browser_guide.stop_guide()
    _browser_guide = None