"""
ProactiveDiscoveryAgent - 主动工具发现智能体

HermesAgent 的增强版本，具备主动工具发现与安装能力。

工作流程：
1. 接收用户任务
2. 分析任务所需的工具
3. 检查工具是否已安装
4. 如果缺失，主动调用 NaturalLanguageToolAdder 安装
5. 安装完成后，执行原任务

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

import asyncio
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from client.src.business.base_agents.hermes_agent import HermesToolAgent
from client.src.business.self_evolution.natural_language_tool_adder import (
    NaturalLanguageToolAdder,
    add_tool_from_text,
)
from client.src.business.tools.tool_registry import ToolRegistry
from loguru import logger


class ProactiveDiscoveryAgent(HermesToolAgent):
    """
    主动工具发现智能体
    
    继承自 HermesToolAgent，增加主动工具发现与安装能力。
    
    用法：
        agent = ProactiveDiscoveryAgent()
        result = await agent.execute_task("帮我分析 AERMOD 的大气扩散数据")
    """
    
    def __init__(
        self,
        enabled_toolsets: Optional[List[str]] = None,
        knowledge_base=None,
        knowledge_graph=None,
        auto_install: bool = True,
    ):
        """
        初始化主动工具发现智能体
        
        Args:
            enabled_toolsets: 启用的工具集
            knowledge_base: 知识库实例
            knowledge_graph: 知识图谱实例
            auto_install: 是否自动安装缺失工具（默认 True）
        """
        super().__init__(
            enabled_toolsets=enabled_toolsets,
            knowledge_base=knowledge_base,
            knowledge_graph=knowledge_graph,
        )
        self._auto_install = auto_install
        self._tool_adder = NaturalLanguageToolAdder()
        self._logger = logger.bind(component="ProactiveDiscoveryAgent")
    
    async def execute_task(self, task: str, **kwargs) -> Dict[str, Any]:
        """
        执行任务（带主动工具发现）
        
        工作流程：
        1. 分析任务所需工具
        2. 检查工具是否可用
        3. 缺失时主动安装
        4. 安装完成后执行任务
        
        Args:
            task: 任务描述
            **kwargs: 其他参数
            
        Returns:
            执行结果字典
        """
        self._logger.info(f"执行任务（主动工具发现）: {task[:50]}...")
        
        # 1. 分析任务所需的工具
        required_tools = await self._analyze_required_tools(task)
        self._logger.info(f"任务所需工具: {required_tools}")
        
        # 2. 检查哪些工具缺失
        missing_tools = self._check_missing_tools(required_tools)
        
        if missing_tools and self._auto_install:
            self._logger.info(f"发现缺失工具: {missing_tools}")
            
            # 3. 主动安装缺失工具
            install_results = await self._proactively_install_tools(
                missing_tools, task
            )
            
            # 4. 刷新工具注册表
            from client.src.business.tools.register_all_tools import register_all_tools
            register_all_tools()
            
            self._logger.info("工具注册表已刷新")
        
        # 5. 执行原任务
        return await self._execute_task_with_tools(task, **kwargs)
    
    async def _analyze_required_tools(self, task: str) -> List[str]:
        """
        分析任务需要哪些工具
        
        使用 LLM 分析任务，列出所需工具名称。
        
        Args:
            task: 任务描述
            
        Returns:
            所需工具名称列表
        """
        prompt = f"""你是任务分析专家。

用户任务：
{task}

请分析完成这个任务需要哪些工具。工具可以是：
- 数据处理工具（如：csv_parser, data_analyzer）
- 网络工具（如：web_crawler, api_caller）
- 计算工具（如：calculator, simulator）
- 报告工具（如：report_generator, chart_maker）
- 专业工具（如：aermod_tool, mike21_tool）

请以 JSON 格式输出：
{{
    "task_type": "任务类型（分析/计算/搜索/报告等）",
    "required_tools": ["tool_name1", "tool_name2"],
    "optional_tools": ["tool_name3"],
    "reasoning": "推理过程"
}}

只输出 JSON，不要有其他内容。"""

        try:
            from client.src.business.global_model_router import GlobalModelRouter
            router = GlobalModelRouter.get_instance()
            response = await router.call_model_sync(
                capability="reasoning",
                prompt=prompt,
                temperature=0.1,
            )
            
            # 解析响应（qwen3.6 答案在 thinking 字段）
            if hasattr(response, 'thinking') and response.thinking:
                text = response.thinking
            elif hasattr(response, 'content') and response.content:
                text = response.content
            else:
                text = str(response)
            
            # 提取 JSON
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result.get("required_tools", [])
            
            return []
            
        except Exception as e:
            self._logger.error(f"分析所需工具失败: {e}")
            return []
    
    def _check_missing_tools(self, required_tools: List[str]) -> List[str]:
        """
        检查哪些工具缺失
        
        Args:
            required_tools: 所需工具列表
            
        Returns:
            缺失工具列表
        """
        registry = ToolRegistry.get_instance()
        available_tools = {tool.name for tool in registry.list_tools()}
        
        missing = []
        for tool_name in required_tools:
            if tool_name not in available_tools:
                missing.append(tool_name)
        
        return missing
    
    async def _proactively_install_tools(
        self,
        missing_tools: List[str],
        task_context: str,
    ) -> List[Dict[str, Any]]:
        """
        主动安装缺失工具
        
        Args:
            missing_tools: 缺失工具列表
            task_context: 任务上下文（用于优化安装）
            
        Returns:
            安装结果列表
        """
        results = []
        
        for tool_name in missing_tools:
            self._logger.info(f"主动安装工具: {tool_name}")
            
            # 构造自然语言请求
            install_request = f"帮我安装 {tool_name} 工具。任务上下文：{task_context}"
            
            try:
                result = await add_tool_from_text(install_request)
                results.append({
                    "tool_name": tool_name,
                    "success": result.success,
                    "message": result.message,
                })
                
                if result.success:
                    self._logger.info(f"工具 {tool_name} 安装成功")
                else:
                    self._logger.warning(f"工具 {tool_name} 安装失败: {result.message}")
                    
            except Exception as e:
                self._logger.error(f"安装工具 {tool_name} 时出错: {e}")
                results.append({
                    "tool_name": tool_name,
                    "success": False,
                    "message": str(e),
                })
        
        return results
    
    async def _execute_task_with_tools(self, task: str, **kwargs) -> Dict[str, Any]:
        """
        使用可用工具执行任务
        
        Args:
            task: 任务描述
            **kwargs: 其他参数
            
        Returns:
            执行结果
        """
        # 使用父类的 discover_and_execute
        discovery_result = self.discover_and_execute(task, auto_execute=True)
        
        return {
            "task": task,
            "discovered_tools": discovery_result.get("discovered_tools", []),
            "execution_results": discovery_result.get("execution_results", []),
            "status": "completed",
        }


async def test_proactive_discovery_agent():
    """测试主动工具发现智能体"""
    import sys
    
    # 配置 loguru
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 ProactiveDiscoveryAgent")
    print("=" * 60)
    
    # 创建智能体
    agent = ProactiveDiscoveryAgent(auto_install=True)
    
    # 测试任务（假设缺少 pyswmm 工具）
    test_task = "使用 SWMM 分析城市排水系统的洪水风险"
    
    print(f"\n测试任务: {test_task}")
    
    # 执行任务
    result = await agent.execute_task(test_task)
    
    print(f"\n[结果]")
    print(f"状态: {result.get('status')}")
    print(f"发现的工具: {[t.get('name') for t in result.get('discovered_tools', [])]}")
    print(f"执行结果数量: {len(result.get('execution_results', []))}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_proactive_discovery_agent())
