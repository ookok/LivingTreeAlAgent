# -*- coding: utf-8 -*-
"""
CLI工具自动安装 - CLI Automation
=================================

功能：
1. 自动检测CLI工具依赖
2. 自动下载和安装工具
3. 版本管理和更新
4. 环境配置

复用模块：
- CLIAnything (现有CLI管理)

Author: Hermes Desktop Team
"""

import logging
import os
import json
import subprocess
import hashlib
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class ToolStatus(Enum):
    """工具状态"""
    UNKNOWN = "unknown"
    NOT_INSTALLED = "not_installed"
    INSTALLING = "installing"
    INSTALLED = "installed"
    UPDATE_AVAILABLE = "update_available"
    ERROR = "error"


@dataclass
class CLITool:
    """CLI工具定义"""
    name: str
    description: str
    command: str  # 命令名
    install_command: str  # 安装命令
    version_command: str  # 版本查询命令
    required: bool = False
    version: str = ""
    install_path: Optional[str] = None
    status: ToolStatus = ToolStatus.UNKNOWN
    dependencies: List[str] = field(default_factory=list)  # 依赖的其他工具
    env_vars: Dict[str, str] = field(default_factory=dict)  # 环境变量
    config_files: List[str] = field(default_factory=list)  # 配置文件


@dataclass
class InstallResult:
    """安装结果"""
    tool_name: str
    success: bool
    message: str
    installed_version: Optional[str] = None
    error: Optional[str] = None


# CLI工具注册表
CLI_TOOLS_REGISTRY: Dict[str, CLITool] = {}


def _init_tools_registry():
    """初始化工具注册表"""
    
    # EIA计算工具
    CLI_TOOLS_REGISTRY["eia-cli"] = CLITool(
        name="eia-cli",
        description="环境影响评价计算工具（排放量、风险计算等）",
        command="eia-cli",
        install_command="pip install eia-calculation-cli",
        version_command="eia-cli --version",
        required=False,
        dependencies=[],
        config_files=["~/.eia-cli/config.yaml"],
    )
    
    # PhantomJS (PDF转换)
    CLI_TOOLS_REGISTRY["phantomjs"] = CLITool(
        name="phantomjs",
        description="无头浏览器，用于PDF生成和网页抓取",
        command="phantomjs",
        install_command="npm install -g phantomjs-prebuilt",
        version_command="phantomjs --version",
        required=False,
        dependencies=["node"],
    )
    
    # Pandoc (文档转换)
    CLI_TOOLS_REGISTRY["pandoc"] = CLITool(
        name="pandoc",
        description="通用文档转换器",
        command="pandoc",
        install_command="choco install pandoc" if os.name == "nt" else "brew install pandoc",
        version_command="pandoc --version",
        required=False,
    )
    
    # wkhtmltopdf (HTML转PDF)
    CLI_TOOLS_REGISTRY["wkhtmltopdf"] = CLITool(
        name="wkhtmltopdf",
        description="HTML转PDF工具",
        command="wkhtmltopdf",
        install_command="choco install wkhtmltopdf" if os.name == "nt" else "brew install wkhtmltopdf",
        version_command="wkhtmltopdf --version",
        required=False,
    )
    
    # ImageMagick (图像处理)
    CLI_TOOLS_REGISTRY["imagemagick"] = CLITool(
        name="imagemagick",
        description="图像处理工具集",
        command="convert",
        install_command="choco install imagemagick" if os.name == "nt" else "brew install imagemagick",
        version_command="convert --version",
        required=False,
    )
    
    # Graphviz (图表生成)
    CLI_TOOLS_REGISTRY["graphviz"] = CLITool(
        name="graphviz",
        description="图表可视化工具",
        command="dot",
        install_command="choco install graphviz" if os.name == "nt" else "brew install graphviz",
        version_command="dot -V",
        required=False,
    )
    
    # Mermaid CLI (图表)
    CLI_TOOLS_REGISTRY["mermaid-cli"] = CLITool(
        name="mermaid-cli",
        description="Mermaid图表CLI",
        command="mmdc",
        install_command="npm install -g @mermaid-js/mermaid-cli",
        version_command="mmdc --version",
        required=False,
        dependencies=["node"],
    )
    
    # PlantUML (UML图表)
    CLI_TOOLS_REGISTRY["plantuml"] = CLITool(
        name="plantuml",
        description="UML图表生成器",
        command="plantuml",
        install_command="choco install plantuml" if os.name == "nt" else "brew install plantuml",
        version_command="plantuml -version",
        required=False,
        dependencies=["java"],
    )
    
    # Tesseract (OCR)
    CLI_TOOLS_REGISTRY["tesseract"] = CLITool(
        name="tesseract",
        description="OCR文字识别",
        command="tesseract",
        install_command="choco install tesseract" if os.name == "nt" else "brew install tesseract",
        version_command="tesseract --version",
        required=False,
    )


_init_tools_registry()


class CLIAutomation:
    """
    CLI工具自动安装管理器
    
    使用示例：
    ```python
    automation = CLIAutomation()
    
    # 检查工具状态
    status = automation.check_tool("eia-cli")
    
    # 安装缺失工具
    result = await automation.install_tool("eia-cli")
    
    # 自动安装所有必需工具
    results = await automation.install_all(required_only=True)
    
    # 检查环境完整性
    report = automation.check_environment()
    ```
    """
    
    def __init__(self, tools_dir: Optional[str] = None):
        self.tools_dir = tools_dir or os.path.join(os.path.expanduser("~"), ".smartwriting", "tools")
        self._status_cache: Dict[str, ToolStatus] = {}
        self._installed_versions: Dict[str, str] = {}
        
    def check_tool(self, tool_name: str) -> ToolStatus:
        """
        检查工具状态
        
        Args:
            tool_name: 工具名称
        
        Returns:
            ToolStatus: 工具状态
        """
        if tool_name in self._status_cache:
            return self._status_cache[tool_name]
            
        tool = CLI_TOOLS_REGISTRY.get(tool_name)
        if not tool:
            return ToolStatus.UNKNOWN
            
        # 检查命令是否存在
        try:
            result = subprocess.run(
                tool.version_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode == 0:
                version = result.stdout.strip().split("\n")[0]
                self._installed_versions[tool_name] = version
                self._status_cache[tool_name] = ToolStatus.INSTALLED
                return ToolStatus.INSTALLED
            else:
                self._status_cache[tool_name] = ToolStatus.NOT_INSTALLED
                return ToolStatus.NOT_INSTALLED
                
        except FileNotFoundError:
            self._status_cache[tool_name] = ToolStatus.NOT_INSTALLED
            return ToolStatus.NOT_INSTALLED
        except subprocess.TimeoutExpired:
            self._status_cache[tool_name] = ToolStatus.ERROR
            return ToolStatus.ERROR
        except Exception as e:
            logger.debug(f"工具检查失败: {tool_name}, {e}")
            self._status_cache[tool_name] = ToolStatus.NOT_INSTALLED
            return ToolStatus.NOT_INSTALLED
    
    async def install_tool(
        self,
        tool_name: str,
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> InstallResult:
        """
        安装工具
        
        Args:
            tool_name: 工具名称
            progress_callback: 进度回调 (message, percentage)
        
        Returns:
            InstallResult: 安装结果
        """
        tool = CLI_TOOLS_REGISTRY.get(tool_name)
        if not tool:
            return InstallResult(
                tool_name=tool_name,
                success=False,
                message=f"未知的工具: {tool_name}"
            )
            
        # 先检查依赖
        if tool.dependencies:
            progress_callback and progress_callback("检查依赖...", 10)
            for dep in tool.dependencies:
                dep_status = self.check_tool(dep)
                if dep_status != ToolStatus.INSTALLED:
                    progress_callback and progress_callback(f"安装依赖: {dep}", 15)
                    result = await self.install_tool(dep)
                    if not result.success:
                        return InstallResult(
                            tool_name=tool_name,
                            success=False,
                            message=f"依赖安装失败: {dep}",
                            error=result.error
                        )
                        
        # 执行安装
        progress_callback and progress_callback(f"正在安装 {tool.name}...", 30)
        self._status_cache[tool_name] = ToolStatus.INSTALLING
        
        try:
            # 创建安装目录
            os.makedirs(self.tools_dir, exist_ok=True)
            
            # 根据操作系统选择安装方式
            install_cmd = self._prepare_install_command(tool)
            
            progress_callback and progress_callback("正在下载/安装...", 50)
            
            # 执行安装命令
            process = await self._run_install_command(install_cmd)
            
            if process.returncode == 0:
                progress_callback and progress_callback("验证安装...", 80)
                
                # 验证安装
                status = self.check_tool(tool_name)
                
                if status == ToolStatus.INSTALLED:
                    version = self._installed_versions.get(tool_name, "")
                    self._status_cache[tool_name] = ToolStatus.INSTALLED
                    progress_callback and progress_callback("安装完成!", 100)
                    
                    return InstallResult(
                        tool_name=tool_name,
                        success=True,
                        message=f"{tool.name} 安装成功",
                        installed_version=version
                    )
                else:
                    return InstallResult(
                        tool_name=tool_name,
                        success=False,
                        message="安装完成但验证失败"
                    )
            else:
                error = process.stderr or "安装命令执行失败"
                self._status_cache[tool_name] = ToolStatus.ERROR
                
                return InstallResult(
                    tool_name=tool_name,
                    success=False,
                    message=f"安装失败: {error}",
                    error=error
                )
                
        except Exception as e:
            logger.error(f"安装失败: {tool_name}, {e}")
            self._status_cache[tool_name] = ToolStatus.ERROR
            
            return InstallResult(
                tool_name=tool_name,
                success=False,
                message=f"安装异常: {str(e)}",
                error=str(e)
            )
    
    def _prepare_install_command(self, tool: CLITool) -> str:
        """准备安装命令"""
        cmd = tool.install_command
        
        # Windows使用chocolatey
        if os.name == "nt":
            if "choco install" in cmd:
                # 确认choco可用
                return f'start /wait cmd /c "{cmd}"'
            elif "pip install" in cmd:
                return f'pip install {tool.name}'
            elif "npm install" in cmd:
                # npm可能需要管理员权限
                return f'npm install -g {tool.name.replace("npm install -g ", "")}'
        else:
            # Unix-like系统
            if "brew install" in cmd:
                return cmd
            elif "pip install" in cmd:
                return f'pip3 install {tool.name}'
                
        return cmd
    
    async def _run_install_command(self, cmd: str) -> subprocess.CompletedProcess:
        """运行安装命令"""
        # 使用PowerShell执行Windows命令
        if os.name == "nt":
            # 简化：使用subprocess.run
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,  # 5分钟超时
            )
            return result
        else:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,
            )
            return result
    
    async def install_all(
        self,
        required_only: bool = False,
        tools: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> List[InstallResult]:
        """
        安装所有工具
        
        Args:
            required_only: 只安装必需工具
            tools: 指定工具列表（优先）
            progress_callback: 进度回调
        
        Returns:
            List[InstallResult]: 安装结果列表
        """
        results = []
        
        # 确定要安装的工具
        if tools:
            tool_list = [CLI_TOOLS_REGISTRY[t] for t in tools if t in CLI_TOOLS_REGISTRY]
        elif required_only:
            tool_list = [t for t in CLI_TOOLS_REGISTRY.values() if t.required]
        else:
            tool_list = list(CLI_TOOLS_REGISTRY.values())
            
        total = len(tool_list)
        
        for i, tool in enumerate(tool_list):
            status = self.check_tool(tool.name)
            
            if status == ToolStatus.INSTALLED:
                results.append(InstallResult(
                    tool_name=tool.name,
                    success=True,
                    message="已安装"
                ))
                continue
                
            progress_callback and progress_callback(
                f"[{i+1}/{total}] {tool.name}",
                int(i / total * 100)
            )
            
            result = await self.install_tool(tool.name, progress_callback)
            results.append(result)
            
        progress_callback and progress_callback("完成", 100)
        return results
    
    def check_environment(self) -> Dict[str, Any]:
        """
        检查环境完整性
        
        Returns:
            Dict: 环境报告
        """
        report = {
            "timestamp": self._get_timestamp(),
            "platform": os.name,
            "tools": {},
            "summary": {
                "total": len(CLI_TOOLS_REGISTRY),
                "installed": 0,
                "missing": 0,
                "required_installed": 0,
                "required_missing": 0,
            }
        }
        
        for name, tool in CLI_TOOLS_REGISTRY.items():
            status = self.check_tool(name)
            version = self._installed_versions.get(name, "")
            
            report["tools"][name] = {
                "status": status.value,
                "version": version,
                "description": tool.description,
                "required": tool.required,
            }
            
            if status == ToolStatus.INSTALLED:
                report["summary"]["installed"] += 1
                if tool.required:
                    report["summary"]["required_installed"] += 1
            else:
                report["summary"]["missing"] += 1
                if tool.required:
                    report["summary"]["required_missing"] += 1
                    
        return report
    
    def get_missing_tools(self, required_only: bool = False) -> List[str]:
        """
        获取缺失的工具列表
        
        Args:
            required_only: 只返回必需工具
        
        Returns:
            List[str]: 缺失的工具名列表
        """
        missing = []
        
        for name, tool in CLI_TOOLS_REGISTRY.items():
            status = self.check_tool(name)
            
            if status != ToolStatus.INSTALLED:
                if required_only and not tool.required:
                    continue
                missing.append(name)
                
        return missing
    
    def update_tool(self, tool_name: str) -> InstallResult:
        """
        更新工具
        
        Args:
            tool_name: 工具名称
        
        Returns:
            InstallResult: 更新结果
        """
        import asyncio
        
        # 重新安装即为更新
        return asyncio.get_event_loop().run_until_complete(
            self.install_tool(tool_name)
        )
    
    def uninstall_tool(self, tool_name: str) -> bool:
        """
        卸载工具
        
        Args:
            tool_name: 工具名称
        
        Returns:
            bool: 是否成功
        """
        tool = CLI_TOOLS_REGISTRY.get(tool_name)
        if not tool:
            return False
            
        try:
            # 尝试卸载命令
            if os.name == "nt":
                uninstall_cmd = f"choco uninstall {tool.name} -y" if "choco" in tool.install_command else f"pip uninstall {tool.name} -y"
            else:
                uninstall_cmd = f"brew uninstall {tool.name}" if "brew" in tool.install_command else f"pip3 uninstall {tool.name} -y"
                
            result = subprocess.run(uninstall_cmd, shell=True, capture_output=True)
            
            if result.returncode == 0:
                self._status_cache[tool_name] = ToolStatus.NOT_INSTALLED
                return True
            return False
            
        except Exception as e:
            logger.error(f"卸载失败: {tool_name}, {e}")
            return False
    
    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def get_tool_info(self, tool_name: str) -> Optional[Dict]:
        """获取工具信息"""
        tool = CLI_TOOLS_REGISTRY.get(tool_name)
        if not tool:
            return None
            
        return {
            "name": tool.name,
            "description": tool.description,
            "command": tool.command,
            "install_command": tool.install_command,
            "required": tool.required,
            "dependencies": tool.dependencies,
            "config_files": tool.config_files,
            "status": self.check_tool(tool_name).value,
            "installed_version": self._installed_versions.get(tool_name, ""),
        }
    
    def list_tools(self, filter_status: Optional[ToolStatus] = None) -> List[Dict]:
        """
        列出所有工具
        
        Args:
            filter_status: 按状态过滤
        
        Returns:
            List[Dict]: 工具信息列表
        """
        tools = []
        
        for name, tool in CLI_TOOLS_REGISTRY.items():
            status = self.check_tool(name)
            
            if filter_status and status != filter_status:
                continue
                
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "required": tool.required,
                "status": status.value,
                "version": self._installed_versions.get(name, ""),
            })
            
        return tools


# 全局实例
_automation: Optional[CLIAutomation] = None


def get_cli_automation() -> CLIAutomation:
    """获取全局CLI自动化管理器"""
    global _automation
    if _automation is None:
        _automation = CLIAutomation()
    return _automation


def quick_check() -> Dict[str, Any]:
    """快速检查环境"""
    automation = get_cli_automation()
    return automation.check_environment()


def quick_install(tool_name: str) -> InstallResult:
    """快速安装工具"""
    import asyncio
    automation = get_cli_automation()
    return asyncio.get_event_loop().run_until_complete(
        automation.install_tool(tool_name)
    )
