"""
CLI-Anything Agent 集成工具
让 Hermes Agent 能够通过自然语言自动生成CLI工具
"""

import asyncio
import json
import re
from typing import Optional, Callable, Any
from dataclasses import dataclass


# ============= CLI生成工具 =============

@dataclass
class CLIGenerationContext:
    """CLI生成上下文"""
    user_id: str
    session_id: str
    request: str
    repo_url: Optional[str] = None
    progress_callback: Optional[Callable] = None


class CLIAgentTool:
    """
    CLI生成Agent工具

    注册到 Hermes Agent，使其能够：
    1. 理解用户的CLI生成需求
    2. 调用 CLI-Anything 引擎生成工具
    3. 自动注册生成的工具到清单
    """

    def __init__(self):
        self.name = "generate_cli_tool"
        self.description = """
生成自定义CLI工具。根据用户的自然语言描述，自动创建一个可执行的命令行工具。

输入：
- description: 自然语言描述工具功能（如"批量转换CAD格式的工具"）
- repo_url: 可选的源码仓库URL

输出：
- 生成的CLI工具信息（名称、路径、入口命令）
- 自动安装状态
- 注册到工具清单状态
"""
        self.parameters = {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "自然语言描述要生成的CLI工具功能"
                },
                "repo_url": {
                    "type": "string",
                    "description": "可选的源码仓库URL，用于参考代码结构"
                },
                "auto_install": {
                    "type": "boolean",
                    "description": "是否自动安装到本地",
                    "default": True
                },
                "auto_register": {
                    "type": "boolean",
                    "description": "是否注册到工具清单",
                    "default": True
                }
            },
            "required": ["description"]
        }

    async def execute(
        self,
        context: dict,
        description: str,
        repo_url: str = None,
        auto_install: bool = True,
        auto_register: bool = True
    ) -> dict:
        """
        执行CLI工具生成

        Args:
            context: Agent执行上下文
            description: 工具描述
            repo_url: 源码仓库URL
            auto_install: 自动安装
            auto_register: 自动注册

        Returns:
            生成结果字典
        """
        from client.src.business.cli_anything import get_cli_anything, get_tools_registry
        from client.src.business.cli_tool_installer import get_installer

        cli_anything = get_cli_anything()
        registry = get_tools_registry()

        # 进度回调
        progress_messages = []

        def progress_callback(pct: float, msg: str):
            progress_messages.append((pct, msg))

        # 执行生成
        result = await cli_anything.generate(
            description=description,
            repo_url=repo_url,
            progress_callback=progress_callback
        )

        response = {
            "success": result.success,
            "description": description,
            "progress": progress_messages,
        }

        if result.success:
            project = result.project
            artifacts = result.artifacts

            response["project"] = {
                "id": project.id,
                "name": project.name,
                "output_dir": project.output_dir,
                "entry_command": f"pip install -e {project.output_dir}",
            }

            # 自动注册到清单
            if auto_register and artifacts.get("tool_entry"):
                tool_entry = artifacts["tool_entry"]
                registry.register_tool(tool_entry)
                response["registered"] = True
                response["tool_id"] = tool_entry["id"]

            # 自动安装
            if auto_install and project.output_dir:
                try:
                    installer = get_installer()
                    # 安装生成的包
                    import subprocess
                    subprocess.run(
                        ["pip", "install", "-e", project.output_dir],
                        check=True,
                        capture_output=True
                    )
                    response["installed"] = True
                except Exception as e:
                    response["install_error"] = str(e)

        else:
            response["error"] = result.error

        return response

    def parse_user_intent(self, message: str) -> Optional[dict]:
        """
        解析用户消息中的CLI生成意图

        Args:
            message: 用户消息

        Returns:
            解析后的参数 或 None
        """
        # 触发词
        trigger_patterns = [
            r"生成.*?工具",
            r"创建.*?CLI",
            r"做个.*?命令行",
            r"我想.*?能.*?的工具",
            r"需要.*?工具.*?用来",
            r"帮我.*?做一个.*?工具",
        ]

        has_trigger = any(re.search(p, message) for p in trigger_patterns)
        if not has_trigger:
            return None

        # 提取描述
        description = None

        # 模式1: "生成一个xxx工具"
        match = re.search(r"[生成创建做个]一个(.+?)(?:工具|程序)", message)
        if match:
            description = match.group(1)

        # 模式2: "我需要一个xxx的工具"
        if not description:
            match = re.search(r"需要(.+?)(?:的|用来)", message)
            if match:
                description = match.group(1)

        # 模式3: 整个句子作为描述
        if not description:
            # 去掉常见前缀
            cleaned = re.sub(r"^(帮我|我想|给我|请).*?(生成|创建|做个|做)", "", message)
            if cleaned and len(cleaned) > 5:
                description = cleaned.strip()

        if not description:
            return None

        # 提取仓库URL
        repo_url = None
        url_pattern = r"https?://github\.com/[^\s]+"
        match = re.search(url_pattern, message)
        if match:
            repo_url = match.group(0)

        return {
            "description": description,
            "repo_url": repo_url,
        }


# ============= 工具调用解析器 =============

class CLIToolCallParser:
    """
    解析Agent生成的工具调用

    识别以下模式：
    1. generate_cli_tool 调用
    2. 自然语言CLI生成请求
    3. CLI工具执行请求
    """

    # CLI生成模式
    GENERATE_PATTERNS = [
        r"generate_cli_tool\s*\(",
        r"生成CLI.*?工具",
        r"创建命令行工具",
    ]

    # CLI执行模式
    EXECUTE_PATTERNS = [
        r"execute_cli\s*\(",
        r"run_cli\s*\(",
        r"运行.*?cli",
        r"执行.*?命令",
    ]

    @classmethod
    def is_cli_generation_request(cls, message: str) -> bool:
        """判断是否为CLI生成请求"""
        return any(re.search(p, message, re.IGNORECASE) for p in cls.GENERATE_PATTERNS)

    @classmethod
    def is_cli_execution_request(cls, message: str) -> bool:
        """判断是否为CLI执行请求"""
        return any(re.search(p, message, re.IGNORECASE) for p in cls.EXECUTE_PATTERNS)

    @classmethod
    def extract_generate_params(cls, message: str) -> Optional[dict]:
        """从消息中提取生成参数"""
        # 尝试提取 JSON
        json_pattern = r'\{[^{}]*\}'
        matches = re.findall(json_pattern, message)

        for match in matches:
            try:
                params = json.loads(match)
                if "description" in params:
                    return params
            except json.JSONDecodeError:
                continue

        return None


# ============= Agent集成 =============

class CLIAgentIntegration:
    """
    CLI-Anything 与 Hermes Agent 的集成

    提供：
    1. 工具注册 - 将CLI生成工具注册到Agent工具集
    2. 意图拦截 - 在消息处理前拦截CLI生成请求
    3. 结果格式化 - 将生成结果格式化为自然语言
    """

    def __init__(self, agent=None):
        self.agent = agent
        self.cli_tool = CLIAgentTool()

    def register_to_agent(self):
        """注册到Agent"""
        if self.agent:
            from client.src.business.tools_registry import ToolRegistry, tool

            # 注册工具
            ToolRegistry.register(
                name=self.cli_tool.name,
                description=self.cli_tool.description,
                parameters=self.cli_tool.parameters,
                handler=self.cli_tool.execute,
                toolset="cli_anything"
            )

    def should_intercept(self, message: str) -> bool:
        """判断是否应该拦截处理"""
        return CLIToolCallParser.is_cli_generation_request(message)

    async def handle_cli_request(self, message: str, context: dict) -> dict:
        """
        处理CLI生成请求

        Args:
            message: 用户消息
            context: 执行上下文

        Returns:
            处理结果
        """
        params = CLIToolCallParser.extract_generate_params(message)

        if not params:
            # 使用意图解析
            parsed = self.cli_tool.parse_user_intent(message)
            if parsed:
                params = parsed
            else:
                return {
                    "success": False,
                    "error": "无法解析CLI生成请求"
                }

        result = await self.cli_tool.execute(context, **params)
        return result

    def format_result(self, result: dict) -> str:
        """格式化结果为自然语言"""
        if not result["success"]:
            return f"❌ 生成失败: {result.get('error', '未知错误')}"

        project = result.get("project", {})
        lines = [
            "✅ CLI工具生成成功!",
            "",
            f"📦 名称: {project.get('name', 'Unknown')}",
            f"📁 目录: {project.get('output_dir', '')}",
        ]

        if result.get("registered"):
            lines.append(f"✨ 已注册到工具清单 (ID: {result.get('tool_id', '')})")

        if result.get("installed"):
            lines.append("📥 已安装到本地环境")

        entry = project.get("entry_command", "")
        if entry:
            lines.append("")
            lines.append("安装命令:")
            lines.append(f"```")
            lines.append(entry)
            lines.append("```")

        return "\n".join(lines)


# 单例
_integration: Optional[CLIAgentIntegration] = None


def get_cli_agent_integration(agent=None) -> CLIAgentIntegration:
    """获取CLI集成单例"""
    global _integration
    if _integration is None:
        _integration = CLIAgentIntegration(agent)
    return _integration
