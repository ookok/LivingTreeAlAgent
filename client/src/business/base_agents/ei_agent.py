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
        环评专用的工具发现方法。

        根据环评报告的阶段（工程分析、环境现状、影响预测、环保措施等）
        推荐不同的工具组合。

        Args:
            task: 任务描述
            phase: 环评阶段，可选值：
                - "engineering"   - 工程分析
                - "environmental" - 环境现状调查
                - "prediction"    - 环境影响预测
                - "measures"      - 环保措施
                - "conclusion"    - 环评结论
                None 表示自动判断

        Returns:
            推荐工具列表
        """
        # 根据阶段优化搜索
        if phase:
            search_query = self._build_phase_query(task, phase)
        else:
            search_query = task

        return self.discover_tools(search_query, max_results=8)

    def _build_phase_query(self, task: str, phase: str) -> str:
        """
        根据环评阶段构建优化后的搜索查询。

        Args:
            task: 原始任务描述
            phase: 环评阶段

        Returns:
            优化后的搜索查询
        """
        phase_keywords = {
            "engineering": "工程分析 污染源 排放系数 工艺流程",
            "environmental": "环境现状 监测数据 敏感点 大气 水质 噪声 土壤",
            "prediction": "环境影响预测 大气扩散 AERMOD 水动力 噪声模拟",
            "measures": "环保措施 污染防治 达标排放 总量控制",
            "conclusion": "环评结论 综合评估 风险评价",
        }

        keywords = phase_keywords.get(phase, "")
        return f"{task} {keywords}"

    def get_eia_tool_chain(self, task: str) -> List[str]:
        """
        为环评任务推荐工具链。

        根据任务描述，推荐一个有序的工具执行序列。

        Args:
            task: 任务描述

        Returns:
            工具名称列表（按执行顺序排列）
        """
        # 默认环评工具链
        default_chain = [
            "deep_search",           # 1. 搜索相关案例和法规
            "web_crawler",           # 2. 爬取详细信息
            "markitdown_converter",  # 3. 转换为可处理格式
            "vector_database",       # 4. 存入知识库
            "knowledge_graph",       # 5. 构建知识图谱
        ]

        # 根据任务类型调整
        task_lower = task.lower()

        if any(kw in task_lower for kw in ["大气", "扩散", "aermod", "废气"]):
            # 大气相关：加入地理和模拟工具
            idx = default_chain.index("vector_database")
            default_chain.insert(idx, "aermod_tool")
            default_chain.insert(idx, "elevation_tool")
            default_chain.insert(idx, "map_api_tool")
            default_chain.insert(idx, "distance_tool")

        elif any(kw in task_lower for kw in ["噪声", "cadnaa"]):
            idx = default_chain.index("vector_database")
            default_chain.insert(idx, "distance_tool")
            default_chain.insert(idx, "map_api_tool")

        elif any(kw in task_lower for kw in ["水", "河流", "mike21", "水文"]):
            idx = default_chain.index("vector_database")
            default_chain.insert(idx, "map_api_tool")

        return default_chain

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
