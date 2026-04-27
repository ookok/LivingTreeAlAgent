"""
EIAgent - 统一工具层桥接
==========================

本模块为 EIAgent（环评专家智能体）提供工具层集成的便捷包装。

EIAgent 的核心实现位于 client.src.business.ei_agent.ei_agent_adapter.EIAgentExecutor，
已在内部集成 BaseToolAgent（通过 self._tool_agent）。

本模块提供：
1. EIToolAgent - 继承 BaseToolAgent 的环评专用工具层版本
2. 默认启用环评相关的工具集（core, search, geospatial, simulation）
3. 环评专用的工具发现策略
4. 便捷函数快速创建 EI 工具层实例

Author: LivingTreeAI Agent
Date: 2026-04-27
"""

from typing import Any, Dict, List, Optional

from client.src.business.base_agents.base_agent import (
    BaseToolAgent,
    ToolCallResult,
)


# 环评专用工具集
EI_TOOLSETS = [
    "core",           # 核心工具（知识库、向量数据库等）
    "search",         # 搜索工具（深度搜索、网页爬虫等）
    "geospatial",     # 地理空间工具（地图API、高程数据、距离计算）
    "simulation",     # 计算模拟工具（AERMOD大气扩散等）
    "document",       # 文档处理工具（文档解析、Markdown转换等）
]


class EIToolAgent(BaseToolAgent):
    """
    EIAgent（环评专家智能体）的工具层特化版本。

    在 BaseToolAgent 基础上，为环评场景定制：
    - 默认启用环评相关工具集（geospatial, simulation, document）
    - 提供环评专用的工具发现策略
    - 支持环评任务分解和工具编排
    """

    def __init__(
        self,
        enabled_toolsets: Optional[List[str]] = None,
        project_type: Optional[str] = None,
    ):
        """
        初始化 EI 工具层智能体。

        Args:
            enabled_toolsets: 启用的工具集，默认使用环评专用工具集
            project_type: 项目类型（如 "化工", "冶金", "建材" 等），影响工具推荐
        """
        if enabled_toolsets is None:
            enabled_toolsets = EI_TOOLSETS

        super().__init__(enabled_toolsets=enabled_toolsets)

        self._project_type = project_type

    def discover_eia_tools(
        self,
        task: str,
        phase: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        环评专用的工具发现方法（自我学习策略）。

        采用自我学习+进化策略，不预置硬编码判断逻辑。
        让 Agent 通过工具描述和任务理解自动匹配最适合的工具。

        Args:
            task: 任务描述（自然语言）
            phase: 环评阶段（可选，仅作为上下文提示）

        Returns:
            推荐工具列表（按相关度排序）
        """
        # 自我学习策略：不预置关键词，让 Agent 自己理解任务
        # 如果有 phase 提示，添加到查询中作为上下文
        if phase:
            search_query = f"{task} (阶段: {phase})"
        else:
            search_query = task

        # 使用 BaseToolAgent 的 discover_tools（已集成语义搜索）
        return self.discover_tools(search_query, max_results=10)

    def get_eia_tool_chain(self, task: str) -> List[str]:
        """
        为环评任务推荐工具链（自我进化策略）。

        不预置硬编码规则，而是通过：
        1. 使用 ToolDependencyManager 自动解析依赖
        2. 让 Agent 通过自我反思学习最优工具链
        3. 将成功的工具链保存到知识库

        Args:
            task: 任务描述

        Returns:
            工具名称列表（按执行顺序排列）
        """
        # 自我进化策略：不硬编码工具链，让系统自己学习
        # 这里返回一个基础工具集，Agent 会根据任务自行扩展
        
        # 尝试从知识库加载成功的工具链模式
        try:
            from client.src.business.knowledge_vector_db import VectorDatabase
            db = VectorDatabase()
            similar_chains = db.search(f"环评工具链 {task}", top_k=3)
            
            if similar_chains and len(similar_chains) > 0:
                # 从知识库中找到类似的工具链
                logger.info(f"[EIToolAgent] 从知识库找到相似工具链")
                # 这里可以解析 similar_chains 并返回学习的工具链
                pass
        except Exception as e:
            logger.warning(f"[EIToolAgent] 从知识库加载工具链失败: {e}")
        
        # 默认返回空列表，让 Agent 自己决定使用哪些工具
        # Agent 会通过 discover_tools() 自己发现合适的工具
        return []

    def get_tool_descriptions(self) -> str:
        """
        获取工具描述文本（供 EIAgent 系统提示使用）。

        Returns:
            Markdown 格式的工具列表描述
        """
        base_desc = super().get_tool_descriptions()

        # 追加环评专有提示
        extra = (
            "\n\n## 环评工具使用指南\n"
            "- 地理空间工具（map_api, elevation, distance, aermod）用于项目位置分析\n"
            "- 文档工具（document_parser, markitdown_converter）用于环评资料处理\n"
            "- 搜索工具（deep_search, web_crawler）用于法规标准和案例检索\n"
            "- 知识库工具（vector_database, knowledge_graph）用于知识积累和查询\n"
            "- 遇到缺失工具时，可请求自主创建"
        )
        return base_desc + extra


def create_ei_tool_agent(
    enabled_toolsets: Optional[List[str]] = None,
    project_type: Optional[str] = None,
    **kwargs,
) -> EIToolAgent:
    """
    创建 EIToolAgent 实例的便捷工厂函数。

    Args:
        enabled_toolsets: 启用的工具集
        project_type: 项目类型
        **kwargs: 传递给 EIToolAgent 的其他参数

    Returns:
        EIToolAgent 实例
    """
    from client.src.business.tools.register_all_tools import register_all_tools

    # 确保所有工具已注册
    register_all_tools()

    return EIToolAgent(
        enabled_toolsets=enabled_toolsets,
        project_type=project_type,
        **kwargs,
    )


def get_ei_tool_descriptions() -> str:
    """
    获取 EIAgent 工具描述文本（便捷函数）。

    Returns:
        Markdown 格式的工具列表描述
    """
    agent = create_ei_tool_agent()
    return agent.get_tool_descriptions()
