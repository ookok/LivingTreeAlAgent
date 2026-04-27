"""
HermesAgent - 统一工具层桥接
==============================

本模块为 HermesAgent 提供工具层集成的便捷包装。

HermesAgent 的核心实现位于 client.src.business.agent.HermesAgent，
已在内部集成 BaseToolAgent（通过 self._tool_agent）。

本模块提供：
1. HermesToolAgent - 继承 BaseToolAgent 的 HermesAgent 工具层版本
2. 便捷函数快速创建 Hermes 工具层实例
3. get_hermes_tool_descriptions() - 获取工具描述文本

Author: LivingTreeAI Agent
Date: 2026-04-27
"""

from typing import Any, Dict, List, Optional

from client.src.business.base_agents.base_agent import (
    BaseToolAgent,
    ToolCallResult,
)


class HermesToolAgent(BaseToolAgent):
    """
    HermesAgent 的工具层特化版本。

    在 BaseToolAgent 基础上，为 Hermes（通用智能体）场景定制：
    - 默认启用 core + search 工具集
    - 提供 think_and_execute() 高级方法
    - 自动发现和调用工具完成通用任务
    """

    def __init__(
        self,
        enabled_toolsets: Optional[List[str]] = None,
        knowledge_base=None,
        knowledge_graph=None,
    ):
        """
        初始化 Hermes 工具层智能体。

        Args:
            enabled_toolsets: 启用的工具集，默认 ["core", "search"]
            knowledge_base: 可选的知识库实例（用于增强工具发现）
            knowledge_graph: 可选的知识图谱实例（用于关系推理）
        """
        if enabled_toolsets is None:
            enabled_toolsets = ["core", "search"]

        super().__init__(enabled_toolsets=enabled_toolsets)

        self._knowledge_base = knowledge_base
        self._knowledge_graph = knowledge_graph

    def discover_and_execute(
        self,
        task: str,
        auto_execute: bool = False,
        max_tools: int = 3,
    ) -> Dict[str, Any]:
        """
        发现工具并（可选地）自动执行。

        Args:
            task: 任务描述
            auto_execute: 是否自动执行发现的工具
            max_tools: 最多发现的工具数量

        Returns:
            {
                "discovered_tools": [...],
                "execution_results": [...]  (auto_execute=True 时)
            }
        """
        # 1. 发现工具
        discovered = self.discover_tools(task, max_results=max_tools)

        result = {
            "discovered_tools": discovered,
            "execution_results": [],
        }

        if not auto_execute:
            return result

        # 2. 自动执行（简化版：不带参数的实际调用）
        for tool_info in discovered:
            tool_name = tool_info.get("name")
            if tool_name:
                call_result = self.execute_tool(tool_name)
                result["execution_results"].append(call_result.to_dict())

        return result

    def get_tool_descriptions(self) -> str:
        """
        获取工具描述文本（供系统提示使用）。

        Returns:
            Markdown 格式的工具列表描述
        """
        base_desc = super().get_tool_descriptions()

        # 追加 Hermes 特有提示
        extra = (
            "\n\n## 工具使用指南\n"
            "- 你可以根据用户需求自由组合使用以上工具\n"
            "- 优先使用搜索工具获取信息，再进行分析和生成\n"
            "- 如果缺少必要工具，请告知用户具体需求"
        )
        return base_desc + extra


def create_hermes_tool_agent(
    enabled_toolsets: Optional[List[str]] = None,
    **kwargs,
) -> HermesToolAgent:
    """
    创建 HermesToolAgent 实例的便捷工厂函数。

    Args:
        enabled_toolsets: 启用的工具集
        **kwargs: 传递给 HermesToolAgent 的其他参数

    Returns:
        HermesToolAgent 实例
    """
    from client.src.business.tools.register_all_tools import register_all_tools

    # 确保所有工具已注册
    register_all_tools()

    return HermesToolAgent(enabled_toolsets=enabled_toolsets, **kwargs)


def get_hermes_tool_descriptions() -> str:
    """
    获取 Hermes 工具描述文本（便捷函数）。

    Returns:
        Markdown 格式的工具列表描述
    """
    agent = create_hermes_tool_agent()
    return agent.get_tool_descriptions()
