"""
ToolMissingDetector - 工具缺失检测器

功能：在执行任务时，智能体能够发现自己缺少哪些工具。
"""

import json
import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger

from client.src.business.tools.tool_registry import ToolRegistry


class ToolMissingDetector:
    """
    工具缺失检测器
    
    功能：
    1. 让 LLM 分析任务，列出所需工具
    2. 对比已有工具列表
    3. 返回缺失的工具名称
    
    用法：
        detector = ToolMissingDetector()
        missing_tools = await detector.detect_missing_tools(task, available_tools)
    """
    
    def __init__(self, llm_client=None):
        """
        初始化工具缺失检测器
        
        Args:
            llm_client: LLM 客户端（用于调用 L4 模型进行推理）
        """
        self._llm = llm_client
        self._logger = logger.bind(component="ToolMissingDetector")
    
    async def detect_missing_tools(
        self,
        task: str,
        available_tools: Optional[List[str]] = None
    ) -> List[str]:
        """
        检测完成任务需要的工具，但当前缺失
        
        Args:
            task: 要完成的任务描述
            available_tools: 已有工具列表（如果为 None，则从 ToolRegistry 获取）
            
        Returns:
            缺失的工具名称列表
        """
        # 1. 获取可用工具列表
        if available_tools is None:
            registry = ToolRegistry.get_instance()
            available_tools = [tool.name for tool in registry.list_tools()]
        
        self._logger.info(f"检测任务所需工具: {task[:50]}...")
        self._logger.info(f"已有工具数量: {len(available_tools)}")
        
        # 2. 让 LLM 分析任务，列出所需工具
        prompt = self._build_prompt(task, available_tools)
        
        try:
            # 调用 L4 模型进行推理
            response = await self._call_llm(prompt)
            
            # 3. 解析 JSON 响应
            result = self._parse_response(response)
            
            missing_tools = result.get("missing_tools", [])
            
            self._logger.info(f"检测到 {len(missing_tools)} 个缺失工具: {missing_tools}")
            
            return missing_tools
            
        except Exception as e:
            self._logger.error(f"检测缺失工具失败: {e}")
            return []
    
    async def analyze_task_requirements(self, task: str) -> Dict[str, Any]:
        """
        详细分析任务需求（更详细的版本）
        
        Args:
            task: 任务描述
            
        Returns:
            包含详细分析结果的字典
        """
        prompt = f"""
你是任务分析专家。

当前任务：
{task}

请详细分析：
1. 任务的主要目标是什么？
2. 完成任务需要哪些步骤？
3. 每个步骤需要什么工具或能力？
4. 哪些工具是必须的？哪些是可选的？

请以 JSON 格式输出：
{{
    "task_goal": "任务目标",
    "steps": [
        {{
            "step": 1,
            "description": "步骤描述",
            "required_tools": ["tool1", "tool2"],
            "optional_tools": ["tool3"]
        }}
    ],
    "must_have_tools": ["tool1", "tool2"],
    "nice_to_have_tools": ["tool3"]
}}
"""
        
        try:
            response = await self._call_llm(prompt)
            result = self._parse_response(response)
            return result
        except Exception as e:
            self._logger.error(f"分析任务需求失败: {e}")
            return {}
    
    def _build_prompt(self, task: str, available_tools: List[str]) -> str:
        """构建提示词"""
        prompt = f"""
你是任务分析专家。

当前任务：
{task}

已有工具列表：
{json.dumps(available_tools, ensure_ascii=False, indent=2)}

请分析：
1. 完成这个任务需要哪些工具？
2. 哪些工具是缺失的（不在已有工具列表中）？

请仔细思考任务需求，包括：
- 数据获取工具（如果需要从网络、数据库、文件获取数据）
- 数据处理工具（如果需要解析、转换、分析数据）
- 计算工具（如果需要进行数学计算、模拟）
- 输出工具（如果需要生成报告、图表、文件）

输出格式（严格 JSON，不要有任何其他输出）：
{{
    "required_tools": ["完成此任务需要的所有工具名称"],
    "missing_tools": ["缺失的工具名称（不在已有工具列表中）"],
    "reasoning": "推理过程"
}}
"""
        return prompt
    
    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM（L4 模型）"""
        if self._llm is not None:
            # 使用提供的 LLM 客户端
            return await self._llm.chat(prompt, model="qwen3.6:35b-a3b")
        else:
            # 尝试导入默认的 LLM 客户端
            try:
                from client.src.business.hermes_agent.llm_client import LLMClient
                llm = LLMClient()
                return await llm.chat(prompt, model="qwen3.6:35b-a3b")
            except Exception as e:
                self._logger.error(f"调用 LLM 失败: {e}")
                raise
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """解析 LLM 响应（JSON）"""
        try:
            # 尝试直接解析
            result = json.loads(response)
            return result
        except json.JSONDecodeError:
            # 尝试从响应中提取 JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
            else:
                raise ValueError(f"无法解析 LLM 响应为 JSON: {response}")
    
    async def suggest_tool_implementation(
        self,
        tool_name: str,
        task_context: str
    ) -> Dict[str, Any]:
        """
        建议工具的实现方式
        
        Args:
            tool_name: 工具名称
            task_context: 任务上下文
            
        Returns:
            包含实现建议的字典
        """
        prompt = f"""
你是工具设计专家。

需要创建一个新的工具：{tool_name}

任务上下文：
{task_context}

请分析：
1. 这个工具应该实现什么功能？
2. 应该封装哪个 Python 库、CLI 工具、或 API？
3. 工具的输入参数应该是什么？
4. 工具的输出应该是什么？

请以 JSON 格式输出：
{{
    "tool_name": "{tool_name}",
    "description": "工具描述",
    "implementation_type": "python_library|cli_tool|api|algorithm",
    "library_or_tool": "要封装的库或工具名称",
    "input_parameters": [
        {{"name": "param1", "type": "string", "description": "参数描述"}}
    ],
    "output_format": "输出格式描述",
    "example_usage": "使用示例"
}}
"""
        
        try:
            response = await self._call_llm(prompt)
            result = self._parse_response(response)
            return result
        except Exception as e:
            self._logger.error(f"建议工具实现失败: {e}")
            return {}


async def test_tool_missing_detector():
    """测试工具缺失检测器"""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    # 配置 loguru
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 ToolMissingDetector")
    print("=" * 60)
    
    # 创建检测器
    detector = ToolMissingDetector()
    
    # 测试任务
    test_task = "从新浪财经获取苹果公司的财报数据，并分析其营收趋势"
    
    # 模拟已有工具列表
    available_tools = [
        "web_crawler",
        "deep_search",
        "task_decomposer",
        "knowledge_graph"
    ]
    
    print(f"\n测试任务: {test_task}")
    print(f"已有工具: {available_tools}")
    
    # 检测缺失工具
    missing_tools = await detector.detect_missing_tools(test_task, available_tools)
    
    print(f"\n[结果] 缺失工具: {missing_tools}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_tool_missing_detector())
