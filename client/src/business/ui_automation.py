"""
UI 自动化理解模块
让系统大脑能够理解软件 UI，根据自然语言自动化操作界面

功能：
1. 屏幕截图与元素识别
2. UI 结构解析
3. 自然语言操作指令解析
4. 自动化操作执行（点击、输入、滚动等）
"""

import os
import time
import json
import base64
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

# 配置管理
from client.src.business.config import UnifiedConfig

# 屏幕截图依赖
try:
    import mss
    import numpy as np
    MSCS_AVAILABLE = True
except ImportError:
    MSCS_AVAILABLE = False

# 图像处理依赖
try:
    from PIL import Image
    import cv2
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class ActionType(Enum):
    """可执行的操作类型"""
    CLICK = "click"
    RIGHT_CLICK = "right_click"
    DOUBLE_CLICK = "double_click"
    TYPE = "type"
    PRESS_KEY = "press_key"
    HOTKEY = "hotkey"
    SCROLL = "scroll"
    DRAG = "drag"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    UNKNOWN = "unknown"


@dataclass
class UIElement:
    """UI 元素"""
    element_type: str           # 按钮、输入框、下拉框等
    text: str = ""              # 元素文本
    bounds: Tuple[int, int, int, int] = (0, 0, 0, 0)  # x, y, width, height
    x: int = 0                  # 中心 x 坐标
    y: int = 0                  # 中心 y 坐标
    confidence: float = 0.0     # 识别置信度
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UISnapshot:
    """UI 快照"""
    screenshot_path: str
    elements: List[UIElement] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    screen_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Action:
    """操作指令"""
    action_type: ActionType
    target: str                 # 操作目标描述
    element: Optional[UIElement] = None
    value: str = ""             # 输入值或按键名
    x: int = 0
    y: int = 0
    duration: float = 0.0       # 拖动持续时间
    direction: str = ""         # 滚动方向


@dataclass
class ActionResult:
    """操作结果"""
    success: bool
    action: Action
    message: str = ""
    screenshot_after: Optional[str] = None


class UIAutomationError(Exception):
    """UI 自动化异常"""
    pass


class UIAutomation:
    """
    UI 自动化核心类

    结合视觉识别和自然语言理解，让 AI 能够操作软件界面
    """

    def __init__(
        self,
        system_brain=None,
        screenshot_dir: str = None,
        auto_install_deps: bool = True
    ):
        """
        初始化 UI 自动化

        Args:
            system_brain: 系统大脑实例（用于理解 UI）
            screenshot_dir: 截图保存目录
            auto_install_deps: 自动安装依赖
        """
        self.system_brain = system_brain

        # 截图目录
        if screenshot_dir:
            self.screenshot_dir = Path(screenshot_dir)
        else:
            self.screenshot_dir = Path.home() / ".hermes-desktop" / "screenshots"
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        # 截图器
        self._sct = None
        if MSCS_AVAILABLE:
            self._sct = mss.mss()

        # 锁定（防止并发操作）
        self._lock = threading.Lock()

        # 历史操作记录
        self._action_history: List[ActionResult] = []

        # 状态
        self._is_running = False

        # 检查依赖
        self._check_dependencies(auto_install_deps)

    def _check_dependencies(self, auto_install: bool):
        """检查依赖是否满足"""
        missing = []

        if not MSCS_AVAILABLE:
            missing.append("mss (pip install mss)")
        if not PIL_AVAILABLE:
            missing.append("Pillow + opencv-python (pip install Pillow opencv-python)")

        if missing and auto_install:
            self._install_dependencies(missing)
        elif missing:
            import logging
            logging.warning(f"UI Automation missing dependencies: {missing}")

    def _install_dependencies(self, packages: List[str]):
        """安装依赖"""
        import subprocess
        import sys

        for pkg in packages:
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", pkg.split()[0]],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                pass

    # ── 截图功能 ────────────────────────────────────────────────────────

    def capture_screen(self, monitor: int = 0, save: bool = True) -> str:
        """
        截取屏幕

        Args:
            monitor: 显示器编号（0=主屏）
            save: 是否保存到文件

        Returns:
            截图文件路径或 base64 编码的图像
        """
        if not MSCS_AVAILABLE:
            raise UIAutomationError("mss 未安装，无法截屏")

        with self._lock:
            try:
                # 获取监视器信息
                monitors = self._sct.monitors
                mon = monitors[monitor] if monitor < len(monitors) else monitors[0]

                # 截图
                screenshot = self._sct.grab(mon)

                if save:
                    # 保存到文件
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    filename = f"screenshot_{timestamp}.png"
                    filepath = self.screenshot_dir / filename

                    mss.tools.to_png(
                        screenshot.rgb,
                        screenshot.size,
                        output=str(filepath)
                    )
                    return str(filepath)
                else:
                    # 返回 base64
                    img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
                    import io
                    buffer = io.BytesIO()
                    img.save(buffer, format="PNG")
                    return base64.b64encode(buffer.getvalue()).decode()

            except Exception as e:
                raise UIAutomationError(f"截屏失败: {e}")

    def capture_region(self, x: int, y: int, width: int, height: int) -> str:
        """
        截取屏幕区域

        Args:
            x, y: 左上角坐标
            width, height: 区域宽高

        Returns:
            截图文件路径
        """
        if not MSCS_AVAILABLE:
            raise UIAutomationError("mss 未安装")

        with self._lock:
            monitor = {"left": x, "top": y, "width": width, "height": height}
            screenshot = self._sct.grab(monitor)

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"region_{x}_{y}_{width}x{height}_{timestamp}.png"
            filepath = self.screenshot_dir / filename

            mss.tools.to_png(
                screenshot.rgb,
                screenshot.size,
                output=str(filepath)
            )
            return str(filepath)

    def get_screen_info(self) -> Dict[str, Any]:
        """获取屏幕信息"""
        if not MSCS_AVAILABLE:
            return {}

        monitors = self._sct.monitors
        return {
            "num_monitors": len(monitors) - 1,  # 排除全屏虚拟
            "primary": {
                "width": monitors[0]["width"],
                "height": monitors[0]["height"]
            },
            "monitors": [
                {"left": m["left"], "top": m["top"], "width": m["width"], "height": m["height"]}
                for m in monitors[1:]
            ]
        }

    # ── UI 理解 ────────────────────────────────────────────────────────

    def analyze_screen(self, screenshot_path: str = None) -> Dict[str, Any]:
        """
        分析屏幕内容，理解 UI 结构

        Args:
            screenshot_path: 截图路径（None=自动截屏）

        Returns:
            UI 分析结果
        """
        if not screenshot_path:
            screenshot_path = self.capture_screen()

        # 读取截图
        with open(screenshot_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode()

        # 调用系统大脑理解 UI
        if self.system_brain:
            prompt = self._build_ui_analysis_prompt(screenshot_path)
            response = self.system_brain.generate(prompt, max_tokens=2048)
            return self._parse_ui_analysis(response)
        else:
            # 无系统大脑时返回基本信息
            return self._basic_screen_analysis(screenshot_path)

    def _build_ui_analysis_prompt(self, screenshot_path: str) -> str:
        """构建 UI 分析提示词"""
        screen_info = self.get_screen_info()

        prompt = f"""请分析这张截图中的 UI 界面结构。

屏幕信息：{json.dumps(screen_info, ensure_ascii=False)}

请以 JSON 格式返回分析结果，包含以下字段：
{{
    "ui_type": "桌面应用/浏览器/游戏/未知",
    "main_elements": [
        {{
            "type": "按钮/输入框/菜单/文本/图片/图标",
            "text": "可见文本",
            "location": "左上/右上/中间/左下/右下",
            "description": "元素描述"
        }}
    ],
    "interactive_elements": [
        {{
            "type": "按钮/输入框/下拉框/复选框",
            "text": "可见文本",
            "bounds": "粗略位置描述",
            "action": "可能的操作"
        }}
    ],
    "operation_hint": "下一步操作的建议"
}}

只返回 JSON，不要有其他内容。"""
        return prompt

    def _parse_ui_analysis(self, response: str) -> Dict[str, Any]:
        """解析 UI 分析结果"""
        try:
            # 提取 JSON
            json_str = self._extract_json(response)
            return json.loads(json_str)
        except Exception:
            return {
                "ui_type": "未知",
                "main_elements": [],
                "interactive_elements": [],
                "operation_hint": "无法分析界面",
                "raw_response": response
            }

    def _extract_json(self, text: str) -> str:
        """从文本中提取 JSON"""
        import re

        # 尝试提取 ```json ... ```
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()

        # 尝试提取 { ... }
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return match.group(0)

        return text

    def _basic_screen_analysis(self, screenshot_path: str) -> Dict[str, Any]:
        """基础屏幕分析（无 AI）"""
        try:
            img = Image.open(screenshot_path)
            width, height = img.size

            return {
                "ui_type": "未知",
                "resolution": f"{width}x{height}",
                "main_elements": [],
                "interactive_elements": [],
                "operation_hint": "请描述你想执行的操作"
            }
        except Exception:
            return {"error": "分析失败"}

    # ── 自然语言操作解析 ──────────────────────────────────────────────

    def parse_operation(self, instruction: str, screenshot_path: str = None) -> Action:
        """
        将自然语言指令解析为操作

        Args:
            instruction: 自然语言指令，如"点击确定按钮"、"在搜索框输入 hello"
            screenshot_path: 截图路径

        Returns:
            解析后的操作
        """
        if not screenshot_path:
            screenshot_path = self.capture_screen()

        # 调用 AI 解析
        if self.system_brain:
            prompt = self._build_operation_parse_prompt(instruction, screenshot_path)
            response = self.system_brain.generate(prompt, max_tokens=512)

            try:
                json_str = self._extract_json(response)
                data = json.loads(json_str)
                return self._build_action_from_parsed(data, instruction)
            except Exception:
                pass

        # 回退：基础解析
        return self._basic_operation_parse(instruction)

    def _build_operation_parse_prompt(self, instruction: str, screenshot_path: str) -> str:
        """构建操作解析提示词"""
        prompt = f"""用户指令："{instruction}"

请将这个自然语言指令解析为具体的 UI 操作。

根据以下格式返回 JSON：
{{
    "action_type": "click/right_click/double_click/type/press_key/hotkey/scroll/drag",
    "target": "按钮/输入框等的目标描述",
    "value": "输入内容（仅 type 类型需要）",
    "key": "按键名（仅 press_key/hotkey 类型需要）",
    "direction": "up/down（仅 scroll 类型需要）",
    "duration": 拖动持续秒数（仅 drag 类型需要）
}}

示例：
- 输入："点击确定按钮" → {{"action_type": "click", "target": "确定按钮"}}
- 输入："在搜索框输入 hello" → {{"action_type": "click", "target": "搜索框"}, {"action_type": "type", "target": "搜索框", "value": "hello"}}
- 输入："按 Ctrl+S 保存" → {{"action_type": "hotkey", "key": "ctrl+s"}}

只返回 JSON。"""
        return prompt

    def _build_action_from_parsed(self, data: Dict[str, Any], instruction: str) -> Action:
        """从解析结果构建 Action"""
        action_type_str = data.get("action_type", "unknown").lower()
        try:
            action_type = ActionType(action_type_str)
        except ValueError:
            action_type = ActionType.UNKNOWN

        return Action(
            action_type=action_type,
            target=data.get("target", instruction),
            value=data.get("value", ""),
            x=0,
            y=0,
            duration=data.get("duration", 0.5)
        )

    def _basic_operation_parse(self, instruction: str) -> Action:
        """基础操作解析"""
        instruction_lower = instruction.lower()

        # 点击检测
        if "点击" in instruction or "点一下" in instruction or "click" in instruction_lower:
            target = instruction.replace("点击", "").replace("点一下", "").replace("click", "").strip()
            return Action(action_type=ActionType.CLICK, target=target)

        # 双击检测
        if "双击" in instruction or "double click" in instruction_lower:
            target = instruction.replace("双击", "").strip()
            return Action(action_type=ActionType.DOUBLE_CLICK, target=target)

        # 右键检测
        if "右键" in instruction or "右击" in instruction:
            target = instruction.replace("右键", "").replace("右击", "").strip()
            return Action(action_type=ActionType.RIGHT_CLICK, target=target)

        # 输入检测
        if "输入" in instruction or "打字" in instruction or "type" in instruction_lower:
            parts = instruction.replace("输入", "").replace("打字", "").split("到")
            if len(parts) == 2:
                return Action(action_type=ActionType.TYPE, target=parts[1].strip(), value=parts[0].strip())
            return Action(action_type=ActionType.TYPE, target="", value=instruction)

        # 按键检测
        if "按" in instruction:
            key = instruction.replace("按", "").strip()
            return Action(action_type=ActionType.PRESS_KEY, target="", value=key)

        # 滚动检测
        if "滚动" in instruction or "scroll" in instruction_lower:
            direction = "up" if "上" in instruction or "up" in instruction_lower else "down"
            return Action(action_type=ActionType.SCROLL, target="", direction=direction)

        return Action(action_type=ActionType.UNKNOWN, target=instruction)

    # ── 操作执行 ──────────────────────────────────────────────────────

    def execute_action(self, action: Action) -> ActionResult:
        """
        执行操作

        Args:
            action: 操作指令

        Returns:
            执行结果
        """
        with self._lock:
            try:
                # 查找操作目标
                if action.element is None and action.target:
                    action.element = self._find_element(action.target)

                # 执行操作
                if action.action_type == ActionType.CLICK:
                    self._do_click(action)
                elif action.action_type == ActionType.RIGHT_CLICK:
                    self._do_right_click(action)
                elif action.action_type == ActionType.DOUBLE_CLICK:
                    self._do_double_click(action)
                elif action.action_type == ActionType.TYPE:
                    self._do_type(action)
                elif action.action_type == ActionType.PRESS_KEY:
                    self._do_press_key(action)
                elif action.action_type == ActionType.HOTKEY:
                    self._do_hotkey(action)
                elif action.action_type == ActionType.SCROLL:
                    self._do_scroll(action)
                elif action.action_type == ActionType.DRAG:
                    self._do_drag(action)
                elif action.action_type == ActionType.SCREENSHOT:
                    self._do_screenshot(action)
                else:
                    return ActionResult(False, action, "不支持的操作类型")

                # 操作后截图
                screenshot_after = self.capture_screen()

                result = ActionResult(True, action, "操作成功", screenshot_after)
                self._action_history.append(result)
                return result

            except Exception as e:
                result = ActionResult(False, action, str(e))
                self._action_history.append(result)
                return result

    def _find_element(self, target: str) -> Optional[UIElement]:
        """
        查找 UI 元素

        通过 AI 分析屏幕找到目标元素
        """
        if not self.system_brain:
            return None

        screenshot_path = self.capture_screen()

        prompt = f"""用户想要操作："{target}"

请在截图中找到这个元素的位置。

返回 JSON 格式：
{{
    "found": true/false,
    "element": {{
        "type": "按钮/输入框/菜单项",
        "text": "元素文本",
        "center_x": 中心x坐标,
        "center_y": 中心y坐标,
        "bounds": [x, y, width, height],
        "confidence": 置信度 0-1
    }}
}}

如果找不到，返回 {{"found": false}}。只返回 JSON。"""

        response = self.system_brain.generate(prompt, max_tokens=512)

        try:
            json_str = self._extract_json(response)
            data = json.loads(json_str)

            if data.get("found"):
                elem_data = data["element"]
                return UIElement(
                    element_type=elem_data.get("type", "未知"),
                    text=elem_data.get("text", ""),
                    x=elem_data.get("center_x", 0),
                    y=elem_data.get("center_y", 0),
                    bounds=tuple(elem_data.get("bounds", [0, 0, 0, 0])),
                    confidence=elem_data.get("confidence", 0.5)
                )
        except Exception:
            pass

        return None

    def _do_click(self, action: Action):
        """执行点击"""
        import pyautogui
        pyautogui.FAILSAFE = True

        if action.element and action.element.x > 0:
            pyautogui.click(action.element.x, action.element.y)
        elif action.x > 0:
            pyautogui.click(action.x, action.y)
        else:
            raise UIAutomationError(f"未找到目标: {action.target}")

    def _do_right_click(self, action: Action):
        """执行右键点击"""
        import pyautogui
        pyautogui.FAILSAFE = True

        if action.element and action.element.x > 0:
            pyautogui.rightClick(action.element.x, action.element.y)
        elif action.x > 0:
            pyautogui.rightClick(action.x, action.y)
        else:
            raise UIAutomationError(f"未找到目标: {action.target}")

    def _do_double_click(self, action: Action):
        """执行双击"""
        import pyautogui
        pyautogui.FAILSAFE = True

        if action.element and action.element.x > 0:
            pyautogui.doubleClick(action.element.x, action.element.y)
        elif action.x > 0:
            pyautogui.doubleClick(action.x, action.y)
        else:
            raise UIAutomationError(f"未找到目标: {action.target}")

    def _do_type(self, action: Action):
        """执行输入"""
        import pyautogui
        pyautogui.FAILSAFE = True

        # 先点击目标
        if action.element and action.element.x > 0:
            pyautogui.click(action.element.x, action.element.y)
        elif action.x > 0:
            pyautogui.click(action.x, action.y)

        # 从配置获取延迟
        ui_config = UnifiedConfig.get_instance().get_ui_automation_config()
        time.sleep(ui_config.get("type_interval", 0.1))

        # 输入文本
        pyautogui.typewrite(action.value, interval=0.05)

    def _do_press_key(self, action: Action):
        """执行按键"""
        import pyautogui
        pyautogui.FAILSAFE = True

        key = action.value.lower().strip()
        pyautogui.press(key)

    def _do_hotkey(self, action: Action):
        """执行组合键"""
        import pyautogui
        pyautogui.FAILSAFE = True

        keys = action.value.lower().replace("+", " ").split()
        pyautogui.hotkey(*keys)

    def _do_scroll(self, action: Action):
        """执行滚动"""
        import pyautogui
        pyautogui.FAILSAFE = True

        clicks = 5
        if action.direction == "up":
            pyautogui.scroll(clicks)
        else:
            pyautogui.scroll(-clicks)

    def _do_drag(self, action: Action):
        """执行拖动"""
        import pyautogui
        pyautogui.FAILSAFE = True

        # 暂不支持起点/终点定位
        raise UIAutomationError("拖动操作需要指定起点和终点")

    def _do_screenshot(self, action: Action):
        """执行截图"""
        self.capture_screen()

    # ── 组合操作 ──────────────────────────────────────────────────────

    def execute_instruction(self, instruction: str) -> ActionResult:
        """
        执行自然语言指令（一步到位）

        Args:
            instruction: 自然语言指令

        Returns:
            执行结果
        """
        # 1. 解析操作
        action = self.parse_operation(instruction)

        if action.action_type == ActionType.UNKNOWN:
            return ActionResult(False, action, f"无法理解指令: {instruction}")

        # 2. 执行操作
        return self.execute_action(action)

    def execute_workflow(self, steps: List[str]) -> List[ActionResult]:
        """
        执行工作流（多个步骤）

        Args:
            steps: 步骤列表，如 ["点击开始菜单", "点击设置", "点击系统"]

        Returns:
            每个步骤的执行结果
        """
        results = []
        for step in steps:
            result = self.execute_instruction(step)
            results.append(result)

            if not result.success:
                break

            # 步骤间等待（从配置获取）
            ui_config = UnifiedConfig.get_instance().get_ui_automation_config()
            time.sleep(ui_config.get("workflow_step_delay", 0.3))

        return results

    # ── 历史记录 ──────────────────────────────────────────────────────

    def get_action_history(self) -> List[ActionResult]:
        """获取操作历史"""
        return self._action_history.copy()

    def clear_history(self):
        """清空操作历史"""
        self._action_history.clear()

    # ── 工具方法 ──────────────────────────────────────────────────────

    def wait_for_element(
        self,
        target: str,
        timeout: float = None,
        poll_interval: float = None
    ) -> Optional[UIElement]:
        """
        等待元素出现

        Args:
            target: 元素描述
            timeout: 超时时间（秒），默认从配置获取
            poll_interval: 轮询间隔，默认从配置获取

        Returns:
            找到的元素或 None
        """
        # 从配置获取默认值
        ui_config = UnifiedConfig.get_instance().get_ui_automation_config()
        if timeout is None:
            timeout = ui_config.get("wait_timeout", 10.0)
        if poll_interval is None:
            poll_interval = ui_config.get("poll_interval", 0.5)

        start_time = time.time()

        while time.time() - start_time < timeout:
            element = self._find_element(target)
            if element and element.confidence > 0.7:
                return element
            time.sleep(poll_interval)

        return None

    def close(self):
        """关闭自动化"""
        self._is_running = False
        if self._sct:
            self._sct.close()


# ── 单例管理 ──────────────────────────────────────────────────────────

_automation_instance: Optional[UIAutomation] = None


def get_automation(
    system_brain=None,
    screenshot_dir: str = None
) -> UIAutomation:
    """获取 UI 自动化实例"""
    global _automation_instance

    if _automation_instance is None:
        _automation_instance = UIAutomation(system_brain, screenshot_dir)

    return _automation_instance
