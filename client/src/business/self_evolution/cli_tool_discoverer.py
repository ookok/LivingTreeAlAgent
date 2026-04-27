"""
CLIToolDiscoverer - CLI 工具自动发现和封装

功能：
1. 扫描系统 PATH 中的 CLI 工具
2. 解析 CLI 工具的帮助文档（--help / --version）
3. 通过 LLM 自动生成 BaseTool 封装代码
4. 自动测试工具有效性
5. 注册到 ToolRegistry

流程：
  scan PATH → parse help → LLM generate wrapper → sandbox test → register
"""

import os
import re
import asyncio
import subprocess
import shutil
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from loguru import logger

from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_result import ToolResult


# ── 已知的系统工具黑名单（避免扫描噪音） ──────────────

# Windows 内置命令（非 CLI 工具）
WINDOWS_BLACKLIST = {
    "con", "prn", "aux", "nul", "com1", "com2", "com3", "com4",
    "lpt1", "lpt2", "lpt3",
}

# 已知的大型 GUI 程序（非 CLI）
GUI_BLACKLIST = {
    "code", "idea", "pycharm", "webstorm", "clion", "goland",
    "notepad", "notepad++", "chrome", "firefox", "msedge",
    "explorer", "cmd", "powershell", "pwsh", "conhost",
    "taskmgr", "regedit", "msconfig", "calc", "mspaint",
}

# 已知无意义的系统工具
NOISE_BLACKLIST = {
    "more", "find", "sort", "replace", "tree", "attrib",
    "cacls", "choice", "color", "endlocal", "erase",
    "ftype", "goto", "if", "pause", "prompt", "rd",
    "ren", "set", "shift", "start", "title", "ver", "vol",
}


@dataclass
class CLIToolInfo:
    """发现的 CLI 工具信息"""
    name: str                    # 工具名称
    path: str                    # 完整路径
    help_text: str = ""          # 帮助文档（截取前 2000 字符）
    version: str = ""            # 版本信息
    category: str = "general"    # 分类
    description: str = ""        # LLM 生成的描述
    wrapped: bool = False        # 是否已封装


class CLIToolDiscoverer:
    """
    CLI 工具发现器

    功能：
    1. 扫描系统 PATH 中的可执行文件
    2. 通过 --help / --version 识别真正的 CLI 工具
    3. 让 LLM 解析帮助文档并生成 BaseTool 封装代码
    4. 测试封装后的工具
    5. 注册到 ToolRegistry

    用法：
        discoverer = CLIToolDiscoverer()

        # 扫描所有 CLI 工具
        tools = await discoverer.discover()

        # 发现并封装指定工具
        info = await discoverer.discover_one("aermod")
        if info:
            code = await discoverer.generate_wrapper(info)
            success = await discoverer.wrap_and_register(info, code)
    """

    def __init__(
        self,
        output_dir: Optional[str] = None,
        scan_blacklist: Optional[set] = None,
        help_timeout: int = 5,
        max_help_length: int = 2000,
    ):
        """
        初始化

        Args:
            output_dir: 封装代码输出目录（默认 client/src/business/tools/）
            scan_blacklist: 额外的扫描黑名单
            help_timeout: 获取帮助文档的超时秒数
            max_help_length: 帮助文档最大截取长度
        """
        self._output_dir = output_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            ))),
            "client", "src", "business", "tools"
        )
        self._help_timeout = help_timeout
        self._max_help_length = max_help_length
        self._discovered: Dict[str, CLIToolInfo] = {}
        self._logger = logger.bind(component="CLIToolDiscoverer")

        # 合并黑名单
        self._blacklist = set()
        self._blacklist.update(WINDOWS_BLACKLIST)
        self._blacklist.update(GUI_BLACKLIST)
        self._blacklist.update(NOISE_BLACKLIST)
        if scan_blacklist:
            self._blacklist.update(scan_blacklist)

    # ── Phase 1: 发现 ────────────────────────────────────

    def scan_path_dirs(self) -> List[str]:
        """获取所有 PATH 目录"""
        path_env = os.environ.get("PATH", "")
        dirs = []
        for d in path_env.split(os.pathsep):
            d = d.strip().strip('"')
            if d and os.path.isdir(d):
                dirs.append(d)
        return dirs

    def list_executables(self) -> List[str]:
        """列出 PATH 中所有可执行文件路径"""
        executables = []
        seen = set()

        for dir_path in self.scan_path_dirs():
            try:
                for entry in os.scandir(dir_path):
                    if not entry.is_file():
                        continue

                    name_lower = entry.name.lower()

                    # 黑名单过滤
                    if name_lower in self._blacklist:
                        continue

                    # 跳过目录/没有扩展名但常见的非可执行
                    if entry.name.startswith("."):
                        continue

                    # 检查可执行性
                    is_exe = os.access(entry.path, os.X_OK)
                    # Windows: 也检查常见可执行扩展名
                    if not is_exe:
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in (".exe", ".bat", ".cmd", ".com", ".ps1"):
                            is_exe = True

                    if is_exe and entry.name.lower() not in seen:
                        seen.add(entry.name.lower())
                        executables.append(entry.path)
            except (PermissionError, OSError):
                continue

        return executables

    async def discover_one(self, tool_name: str) -> Optional[CLIToolInfo]:
        """
        发现单个 CLI 工具

        Args:
            tool_name: 工具名称（不带路径）

        Returns:
            CLIToolInfo 或 None
        """
        # 先检查缓存
        if tool_name in self._discovered:
            return self._discovered[tool_name]

        # 在 PATH 中查找
        tool_path = shutil.which(tool_name)
        if not tool_path:
            self._logger.warning(f"未找到 CLI 工具: {tool_name}")
            return None

        # 获取帮助文档和版本
        help_text = await self._get_help_text(tool_path)
        version = await self._get_version(tool_path)

        info = CLIToolInfo(
            name=tool_name,
            path=tool_path,
            help_text=help_text,
            version=version,
        )
        self._discovered[tool_name] = info
        return info

    async def discover(self, max_tools: int = 50) -> List[CLIToolInfo]:
        """
        发现所有系统 CLI 工具

        Args:
            max_tools: 最多发现数量

        Returns:
            发现的 CLI 工具列表
        """
        self._logger.info("开始扫描系统 CLI 工具...")

        executables = self.list_executables()
        self._logger.info(f"PATH 中发现 {len(executables)} 个可执行文件")

        discovered = []
        sem = asyncio.Semaphore(10)  # 限制并发数

        async def _check_one(exe_path: str) -> Optional[CLIToolInfo]:
            async with sem:
                name = os.path.basename(exe_path)
                info = await self._quick_probe(exe_path)
                if info:
                    return info
                return None

        tasks = [_check_one(p) for p in executables[:200]]  # 最多探测 200 个
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, CLIToolInfo):
                discovered.append(r)
                if len(discovered) >= max_tools:
                    break

        self._logger.info(
            f"扫描完成: 发现 {len(discovered)} 个 CLI 工具"
        )
        return discovered

    async def _quick_probe(self, exe_path: str) -> Optional[CLIToolInfo]:
        """快速探测一个可执行文件是否为 CLI 工具"""
        name = os.path.basename(exe_path)

        try:
            # 尝试 --version（比 --help 更轻量）
            version = await self._get_version(exe_path)
            if version:
                help_text = await self._get_help_text(exe_path)
                info = CLIToolInfo(
                    name=name,
                    path=exe_path,
                    version=version,
                    help_text=help_text,
                )
                self._discovered[name] = info
                return info

            # --version 没输出，尝试 --help
            help_text = await self._get_help_text(exe_path)
            if help_text and len(help_text) > 50:
                info = CLIToolInfo(
                    name=name,
                    path=exe_path,
                    help_text=help_text,
                )
                self._discovered[name] = info
                return info

        except Exception:
            pass

        return None

    # ── Phase 2: 帮助文档解析 ────────────────────────────

    async def _get_help_text(self, exe_path: str) -> str:
        """获取 CLI 工具的帮助文档"""
        for flag in ["--help", "-h", "-help", "help"]:
            try:
                help_text = await self._run_command(
                    exe_path, [flag],
                    timeout=self._help_timeout
                )
                if help_text and len(help_text) > 20:
                    return help_text[:self._max_help_length]
            except Exception:
                continue
        return ""

    async def _get_version(self, exe_path: str) -> str:
        """获取 CLI 工具的版本信息"""
        for flag in ["--version", "-v", "-V", "version"]:
            try:
                output = await self._run_command(
                    exe_path, [flag],
                    timeout=self._help_timeout
                )
                if output and any(c.isdigit() for c in output):
                    return output.strip()[:200]
            except Exception:
                continue
        return ""

    async def _run_command(
        self, exe_path: str, args: List[str], timeout: int = 5
    ) -> str:
        """执行命令并返回输出"""
        loop = asyncio.get_event_loop()
        cmd = [exe_path] + args

        def _run():
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                return (result.stdout or "") + (result.stderr or "")
            except Exception:
                return ""

        return await loop.run_in_executor(None, _run)

    # ── Phase 3: 封装代码生成 ────────────────────────────

    async def generate_wrapper(
        self,
        tool_info: CLIToolInfo,
        category: str = "cli_tool",
    ) -> Optional[str]:
        """
        让 LLM 生成 BaseTool 封装代码

        Args:
            tool_info: CLI 工具信息
            category: 工具分类

        Returns:
            生成的 Python 代码，或 None
        """
        self._logger.info(f"为 {tool_info.name} 生成 BaseTool 封装...")

        prompt = f"""你是一个 Python 代码生成专家。

任务：为以下 CLI 工具生成 Python 封装代码（继承 BaseTool）。

CLI 工具名称：{tool_info.name}
CLI 工具路径：{tool_info.path}
版本：{tool_info.version or '未知'}
帮助文档：
```
{tool_info.help_text or '无帮助文档'}
```

要求：
1. 继承 BaseTool 类（from client.src.business.tools.base_tool import BaseTool）
2. 实现 name、description 属性和 execute() 方法
3. 通过 subprocess 调用 CLI 工具
4. 返回 ToolResult（from client.src.business.tools.tool_result import ToolResult）
5. execute() 接受 **kwargs，将其转为 CLI 参数
6. 添加必要的参数解析和错误处理
7. description 要准确描述工具功能（用中文）
8. 代码要完整可运行，不要省略任何部分

只输出 Python 代码，不要任何解释。"""

        code = await self._call_llm(prompt)

        if code:
            # 清理可能的 markdown 包裹
            code = self._clean_llm_code(code)
            self._logger.info(f"封装代码生成完成: {len(code)} 字符")
            return code

        self._logger.error(f"封装代码生成失败: {tool_info.name}")
        return None

    async def analyze_and_categorize(self, tool_info: CLIToolInfo) -> CLIToolInfo:
        """
        通过 LLM 分析 CLI 工具的功能并分类

        Args:
            tool_info: CLI 工具信息

        Returns:
            更新后的 CLIToolInfo
        """
        prompt = f"""分析以下 CLI 工具的功能，返回 JSON 格式：

工具名称：{tool_info.name}
版本：{tool_info.version or '未知'}
帮助文档：
```
{tool_info.help_text[:1000] or '无帮助文档'}
```

返回格式（纯 JSON，不要其他内容）：
{{
    "description": "一句话描述工具功能（中文）",
    "category": "分类（search/development/system/network/media/document/analysis/science/general 之一）"
}}"""

        response = await self._call_llm(prompt)
        if response:
            try:
                import json
                # 清理可能的 markdown 包裹
                cleaned = response.strip()
                if cleaned.startswith("```"):
                    cleaned = re.sub(r'^```\w*\n?', '', cleaned)
                    cleaned = re.sub(r'\n?```$', '', cleaned)
                result = json.loads(cleaned)
                tool_info.description = result.get("description", "")
                tool_info.category = result.get("category", "general")
            except Exception as e:
                self._logger.warning(f"解析 LLM 响应失败: {e}")

        return tool_info

    def _clean_llm_code(self, code: str) -> str:
        """清理 LLM 生成的代码（去除 markdown 包裹等）"""
        code = code.strip()
        # 去掉 ```python ... ```
        if code.startswith("```"):
            code = re.sub(r'^```\w*\n?', '', code)
            code = re.sub(r'\n?```\s*$', '', code)
        return code.strip()

    # ── Phase 4: 封装、测试、注册 ────────────────────────

    async def wrap_and_register(
        self,
        tool_info: CLIToolInfo,
        code: Optional[str] = None,
        auto_analyze: bool = True,
    ) -> Tuple[bool, Optional[str]]:
        """
        完整流程：生成封装 → 写入文件 → 测试 → 注册

        Args:
            tool_info: CLI 工具信息
            code: 预生成的代码（None 则自动生成）
            auto_analyze: 是否先让 LLM 分析功能

        Returns:
            (是否成功, 文件路径或 None)
        """
        self._logger.info(f"[完整流程] 封装 CLI 工具: {tool_info.name}")

        # 1. 分析功能
        if auto_analyze and not tool_info.description:
            tool_info = await self.analyze_and_categorize(tool_info)

        # 2. 生成代码（如果未提供）
        if not code:
            code = await self.generate_wrapper(tool_info)
            if not code:
                return False, None

        # 3. 写入文件
        file_path = self._get_output_path(tool_info.name)
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)
            self._logger.info(f"封装代码已写入: {file_path}")
        except Exception as e:
            self._logger.error(f"写入文件失败: {e}")
            return False, None

        # 4. 语法检查
        try:
            import py_compile
            py_compile.compile(file_path, doraise=True)
            self._logger.info("语法检查通过")
        except py_compile.PyCompileError as e:
            self._logger.error(f"语法检查失败: {e}")
            os.remove(file_path)
            return False, None

        # 5. 测试导入
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                f"_test_{tool_info.name}", file_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 查找 BaseTool 子类
            tool_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type)
                        and issubclass(attr, BaseTool)
                        and attr != BaseTool):
                    tool_class = attr
                    break

            if not tool_class:
                self._logger.error("未找到 BaseTool 子类")
                return False, file_path

            self._logger.info(f"封装测试通过: {tool_class.__name__}")

        except Exception as e:
            self._logger.error(f"导入测试失败: {e}")
            return False, file_path

        # 6. 注册到 ToolRegistry
        try:
            from client.src.business.tools.tool_registry import ToolRegistry
            registry = ToolRegistry.get_instance()
            registry.register_tool(tool_class())
            tool_info.wrapped = True
            self._logger.info(f"已注册到 ToolRegistry: {tool_info.name}")
            return True, file_path
        except Exception as e:
            self._logger.error(f"注册失败: {e}")
            return False, file_path

    def _get_output_path(self, tool_name: str) -> str:
        """获取封装代码的输出路径"""
        safe_name = re.sub(r'[^\w]', '_', tool_name.lower())
        return os.path.join(self._output_dir, f"{safe_name}_cli_wrapper.py")

    # ── LLM 调用 ────────────────────────────────────────

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM（通过 GlobalModelRouter）"""
        try:
            from client.src.business.global_model_router import (
                call_model_sync, ModelCapability
            )
            return call_model_sync(
                capability=ModelCapability.CODE_GENERATION,
                prompt=prompt,
            )
        except Exception as e:
            self._logger.error(f"LLM 调用失败: {e}")
            return ""

    # ── 工具方法 ────────────────────────────────────────

    def list_discovered(self) -> List[Dict[str, Any]]:
        """列出所有已发现的 CLI 工具"""
        return [
            {
                "name": info.name,
                "path": info.path,
                "version": info.version,
                "category": info.category,
                "description": info.description,
                "wrapped": info.wrapped,
                "has_help": bool(info.help_text),
            }
            for info in self._discovered.values()
        ]

    def get_tool_info(self, name: str) -> Optional[CLIToolInfo]:
        """获取指定工具的信息"""
        return self._discovered.get(name)

    def add_to_blacklist(self, name: str):
        """添加工具到黑名单"""
        self._blacklist.add(name.lower())
        self._discovered.pop(name.lower(), None)
