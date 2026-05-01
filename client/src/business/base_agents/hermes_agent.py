"""
LivingTreeAgent - 统一工具层桥接
==============================

本模块为 LivingTreeAgent 提供工具层集成的便捷包装。

LivingTreeAgent 的核心实现位于 client.src.business.agent.LivingTreeAgent，
已在内部集成 BaseToolAgent（通过 self._tool_agent）。

本模块提供：
1. LivingTreeToolAgent - 继承 BaseToolAgent 的 LivingTreeAgent 工具层版本
2. 便捷函数快速创建 LivingTree 工具层实例
3. get_livingtree_tool_descriptions() - 获取工具描述文本

Author: LivingTreeAI Agent
Date: 2026-04-27
"""

from typing import Any, Dict, List, Optional

from business.base_agents.base_agent import (
    BaseToolAgent,
    ToolCallResult,
)

# 智能模块调度器（统一调度）
from business.fusion_rag import get_smart_scheduler, TaskType, TaskContext


class LivingTreeToolAgent(BaseToolAgent):
    """
    LivingTreeAgent 的工具层特化版本。

    在 BaseToolAgent 基础上，为 LivingTree（通用智能体）场景定制：
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
        初始化 LivingTree 工具层智能体。

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
        
        # 智能模块调度器
        self._scheduler = get_smart_scheduler()

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

        # 追加 LivingTree 特有提示
        extra = (
            "\n\n## 工具使用指南\n"
            "- 你可以根据用户需求自由组合使用以上工具\n"
            "- 优先使用搜索工具获取信息，再进行分析和生成\n"
            "- 如果缺少必要工具，请告知用户具体需求"
        )
        return base_desc + extra
    
    async def smart_ask(self, question: str) -> Dict[str, Any]:
        """
        使用智能模块调度器进行问答（统一调度）。
        
        Args:
            question: 用户问题
            
        Returns:
            问答结果
        """
        try:
            # 创建任务上下文
            context = TaskContext(
                task_type=TaskType.QUESTION_ANSWERING,
                query=question,
                required_capabilities=["reasoning", "knowledge_retrieval"]
            )
            
            # 使用调度器执行任务
            result = await self._scheduler.execute(context)
            
            if result.success:
                return {
                    "success": True,
                    "answer": result.result,
                    "module": result.module_name,
                    "confidence": result.confidence,
                    "latency": result.latency
                }
            else:
                # 回退到传统工具调用
                return await self._fallback_ask(question)
                
        except Exception as e:
            # 回退到传统工具调用
            return await self._fallback_ask(question)
    
    async def smart_analyze(self, document_path: str, query: str = None) -> Dict[str, Any]:
        """
        使用智能模块调度器分析文档（统一调度）。
        
        Args:
            document_path: 文档路径
            query: 分析查询
            
        Returns:
            分析结果
        """
        try:
            # 创建任务上下文
            context = TaskContext(
                task_type=TaskType.DOCUMENT_ANALYSIS,
                query=query,
                document_path=document_path,
                required_capabilities=["document_processing", "multi_modal_analysis"]
            )
            
            # 使用调度器执行任务
            result = await self._scheduler.execute(context)
            
            if result.success:
                return {
                    "success": True,
                    "result": result.result,
                    "module": result.module_name,
                    "confidence": result.confidence,
                    "latency": result.latency
                }
            else:
                # 回退到本地分析
                return {"success": False, "error": "分析失败"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def smart_retrieve(self, query: str) -> Dict[str, Any]:
        """
        使用智能模块调度器检索知识（统一调度）。
        
        Args:
            query: 检索查询
            
        Returns:
            检索结果
        """
        try:
            # 创建任务上下文
            context = TaskContext(
                task_type=TaskType.KNOWLEDGE_RETRIEVAL,
                query=query,
                required_capabilities=["semantic_retrieval", "knowledge_retrieval"]
            )
            
            # 使用调度器执行任务
            result = await self._scheduler.execute(context)
            
            if result.success:
                return {
                    "success": True,
                    "result": result.result,
                    "module": result.module_name,
                    "confidence": result.confidence,
                    "latency": result.latency
                }
            else:
                return {"success": False, "error": "检索失败"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _fallback_ask(self, question: str) -> Dict[str, Any]:
        """
        备用问答方法（当智能调度器不可用时）。
        
        Args:
            question: 用户问题
            
        Returns:
            问答结果
        """
        # 使用传统工具发现和执行
        result = self.discover_and_execute(question, auto_execute=True)
        
        return {
            "success": True,
            "answer": result,
            "module": "fallback",
            "method": "tool_execution"
        }


def create_livingtree_tool_agent(
    enabled_toolsets: Optional[List[str]] = None,
    **kwargs,
) -> LivingTreeToolAgent:
    """
    创建 LivingTreeToolAgent 实例的便捷工厂函数。

    Args:
        enabled_toolsets: 启用的工具集
        **kwargs: 传递给 LivingTreeToolAgent 的其他参数

    Returns:
        LivingTreeToolAgent 实例
    """
    from business.tools.register_all_tools import register_all_tools

    # 确保所有工具已注册
    register_all_tools()

    return LivingTreeToolAgent(enabled_toolsets=enabled_toolsets, **kwargs)


def get_livingtree_tool_descriptions() -> str:
    """
    获取 LivingTree 工具描述文本（便捷函数）。

    Returns:
        Markdown 格式的工具列表描述
    """
    agent = create_livingtree_tool_agent()
    return agent.get_tool_descriptions()
