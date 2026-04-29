"""
Skill 自进化系统 - 原子工具集

9个原子工具（参考 GenericAgent）：
- code_run: 执行任意代码
- file_read: 读取文件
- file_write: 写入文件
- file_patch: 修改/补丁文件
- web_scan: 感知网页内容
- web_execute_js: 控制浏览器行为
- ask_user: 人机协作确认

额外的记忆管理工具：
- update_working_checkpoint: 持久化上下文
- start_long_term_update: 跨会话积累经验
"""

import os
import re
import json
import time
import hashlib
import subprocess
from pathlib import Path
from typing import Any, Optional, Dict, Callable, List
from dataclasses import dataclass
from enum import Enum


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: Any = None
    error: str = ""
    duration: float = 0.0


class BaseToolHandler:
    """
    基础工具处理器

    提供工具调度的生命周期钩子
    """

    def tool_before_callback(self, tool_name: str, args: Dict, response: Any):
        """工具执行前回调"""
        pass

    def tool_after_callback(self, tool_name: str, args: Dict, response: Any, ret: ToolResult):
        """工具执行后回调"""
        pass

    def dispatch(self, tool_name: str, args: Dict, response: Any = None, index: int = 0) -> ToolResult:
        """分发工具调用"""
        method_name = f"do_{tool_name}"
        if hasattr(self, method_name):
            return getattr(self, method_name)(args, response)
        else:
            return ToolResult(success=False, error=f"未知工具: {tool_name}")


class FileTools(BaseToolHandler):
    """文件操作工具集"""

    def do_file_read(self, args: Dict, response: Any = None) -> ToolResult:
        """读取文件"""
        start = time.time()
        try:
            path = args.get("path")
            if not path:
                return ToolResult(success=False, error="缺少 path 参数", duration=time.time() - start)

            file_path = Path(path)
            if not file_path.exists():
                return ToolResult(success=False, error=f"文件不存在: {path}", duration=time.time() - start)

            if file_path.is_dir():
                # 返回目录列表
                items = [
                    {"name": p.name, "path": str(p), "is_dir": p.is_dir()}
                    for p in file_path.iterdir()
                ]
                return ToolResult(success=True, data={"type": "directory", "items": items}, duration=time.time() - start)

            # 读取文件内容
            encoding = args.get("encoding", "utf-8")
            with open(file_path, "r", encoding=encoding, errors="replace") as f:
                content = f.read()

            return ToolResult(
                success=True,
                data={
                    "type": "file",
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "content": content
                },
                duration=time.time() - start
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), duration=time.time() - start)

    def do_file_write(self, args: Dict, response: Any = None) -> ToolResult:
        """写入文件"""
        start = time.time()
        try:
            path = args.get("path")
            content = args.get("content", "")
            if not path:
                return ToolResult(success=False, error="缺少 path 参数", duration=time.time() - start)

            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            encoding = args.get("encoding", "utf-8")
            with open(file_path, "w", encoding=encoding) as f:
                f.write(content)

            return ToolResult(
                success=True,
                data={"path": str(file_path), "size": file_path.stat().st_size},
                duration=time.time() - start
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), duration=time.time() - start)

    def do_file_patch(self, args: Dict, response: Any = None) -> ToolResult:
        """打补丁修改文件"""
        start = time.time()
        try:
            path = args.get("path")
            old_str = args.get("old_str")
            new_str = args.get("new_str")
            if not path or old_str is None or new_str is None:
                return ToolResult(success=False, error="缺少必要参数", duration=time.time() - start)

            file_path = Path(path)
            if not file_path.exists():
                return ToolResult(success=False, error=f"文件不存在: {path}", duration=time.time() - start)

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            if old_str not in content:
                return ToolResult(success=False, error="未找到要替换的内容", duration=time.time() - start)

            new_content = content.replace(old_str, new_str, 1)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return ToolResult(
                success=True,
                data={"path": str(file_path), "patches": 1},
                duration=time.time() - start
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), duration=time.time() - start)


class CodeTools(BaseToolHandler):
    """代码执行工具集"""

    def __init__(self, workspace_root: str = None):
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()

    def do_code_run(self, args: Dict, response: Any = None) -> ToolResult:
        """执行代码"""
        start = time.time()
        try:
            code = args.get("code")
            language = args.get("language", "python")
            timeout = args.get("timeout", 30)

            if not code:
                return ToolResult(success=False, error="缺少 code 参数", duration=time.time() - start)

            # 安全检查：限制可执行的路径
            cwd = self.workspace_root

            if language.lower() in ("python", "py"):
                result = subprocess.run(
                    ["python", "-c", code],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(cwd)
                )
                output = result.stdout
                error = result.stderr
            elif language.lower() in ("javascript", "js"):
                result = subprocess.run(
                    ["node", "-e", code],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(cwd)
                )
                output = result.stdout
                error = result.stderr
            elif language.lower() in ("bash", "shell", "sh"):
                result = subprocess.run(
                    code,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(cwd)
                )
                output = result.stdout
                error = result.stderr
            else:
                return ToolResult(success=False, error=f"不支持的语言: {language}", duration=time.time() - start)

            return ToolResult(
                success=result.returncode == 0,
                data={"output": output, "error": error, "returncode": result.returncode},
                duration=time.time() - start
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error="执行超时", duration=time.time() - start)
        except Exception as e:
            return ToolResult(success=False, error=str(e), duration=time.time() - start)


class WebTools(BaseToolHandler):
    """网页操作工具集（需要浏览器环境）"""

    def __init__(self, browser_controller=None):
        self.browser = browser_controller

    def do_web_scan(self, args: Dict, response: Any = None) -> ToolResult:
        """感知网页内容"""
        start = time.time()
        try:
            url = args.get("url")
            selector = args.get("selector")

            if not self.browser:
                return ToolResult(
                    success=False,
                    error="浏览器未初始化",
                    duration=time.time() - start
                )

            if url:
                self.browser.navigate(url)

            content = self.browser.get_content(selector)
            return ToolResult(
                success=True,
                data={"content": content},
                duration=time.time() - start
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), duration=time.time() - start)

    def do_web_execute_js(self, args: Dict, response: Any = None) -> ToolResult:
        """执行 JavaScript"""
        start = time.time()
        try:
            script = args.get("script")
            if not self.browser:
                return ToolResult(
                    success=False,
                    error="浏览器未初始化",
                    duration=time.time() - start
                )

            result = self.browser.execute_script(script)
            return ToolResult(
                success=True,
                data={"result": result},
                duration=time.time() - start
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), duration=time.time() - start)


class DialogTools(BaseToolHandler):
    """对话框/人机协作工具"""

    def __init__(self, user_callback: Callable[[str], str] = None):
        self.user_callback = user_callback

    def do_ask_user(self, args: Dict, response: Any = None) -> ToolResult:
        """询问用户"""
        start = time.time()
        try:
            question = args.get("question", "")
            options = args.get("options", [])

            if self.user_callback:
                answer = self.user_callback(question, options)
                return ToolResult(
                    success=True,
                    data={"answer": answer},
                    duration=time.time() - start
                )
            else:
                return ToolResult(
                    success=False,
                    error="用户回调未设置",
                    duration=time.time() - start
                )
        except Exception as e:
            return ToolResult(success=False, error=str(e), duration=time.time() - start)


class UnifiedToolHandler(
    FileTools,
    CodeTools,
    WebTools,
    DialogTools
):
    """
    统一工具处理器

    组合所有原子工具，提供统一的工具调度接口
    """

    def __init__(self, workspace_root: str = None, browser_controller=None, user_callback: Callable = None):
        FileTools.__init__(self)
        CodeTools.__init__(self, workspace_root)
        WebTools.__init__(self, browser_controller)
        DialogTools.__init__(self, user_callback)

        self._done_hooks: List[Callable] = []
        self.max_turns = 40

    def register_done_hook(self, hook: Callable):
        """注册完成钩子"""
        self._done_hooks.append(hook)


# ============ 内置工具注册表 ============

def get_default_tools() -> List[Dict[str, Any]]:
    """获取默认工具定义（用于 LLM 工具调用）"""

    return [
        {
            "name": "file_read",
            "description": "读取文件或列出目录内容",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件或目录路径"},
                    "encoding": {"type": "string", "description": "编码，默认 utf-8"}
                },
                "required": ["path"]
            }
        },
        {
            "name": "file_write",
            "description": "写入文件",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "文件内容"},
                    "encoding": {"type": "string", "description": "编码，默认 utf-8"}
                },
                "required": ["path", "content"]
            }
        },
        {
            "name": "file_patch",
            "description": "打补丁修改文件（替换首次匹配的字符串）",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "old_str": {"type": "string", "description": "要替换的字符串"},
                    "new_str": {"type": "string", "description": "新字符串"}
                },
                "required": ["path", "old_str", "new_str"]
            }
        },
        {
            "name": "code_run",
            "description": "执行代码（Python/JavaScript/Bash）",
            "input_schema": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "要执行的代码"},
                    "language": {"type": "string", "description": "语言：python/js/bash"},
                    "timeout": {"type": "integer", "description": "超时秒数，默认30"}
                },
                "required": ["code"]
            }
        },
        {
            "name": "ask_user",
            "description": "询问用户确认或选择",
            "input_schema": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "要询问的问题"},
                    "options": {"type": "array", "items": {"type": "string"}, "description": "选项列表"}
                },
                "required": ["question"]
            }
        },
    ]


def get_tool_schemas() -> List[Dict[str, Any]]:
    """获取工具 schemas（用于 API 调用）"""
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"]
            }
        }
        for tool in get_default_tools()
    ]
