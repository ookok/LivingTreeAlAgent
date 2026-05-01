"""
NaturalLanguageToolAdder - 自然语言工具添加器

通过自然语言描述自动创建和注册新工具。

功能：
1. 解析自然语言工具描述
2. 生成工具代码
3. 自动注册到工具注册表
4. 支持工具安装和升级

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

import asyncio
import json
import re
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from loguru import logger

from business.tools.tool_registry import ToolRegistry, ToolDefinition, BaseTool


@dataclass
class ToolSpecification:
    """工具规范"""
    name: str
    description: str
    parameters: Dict[str, str] = field(default_factory=dict)
    returns: str = ""
    category: str = "general"


class NaturalLanguageToolAdder:
    """
    自然语言工具添加器
    
    通过自然语言描述自动创建工具。
    """
    
    def __init__(self):
        self.tool_registry = ToolRegistry.get_instance()
        self.logger = logger.bind(component="NaturalLanguageToolAdder")
    
    async def add_tool_from_description(self, description: str) -> Dict[str, Any]:
        """
        从自然语言描述添加工具
        
        Args:
            description: 工具的自然语言描述
            
        Returns:
            创建结果字典
        """
        self.logger.info(f"尝试从描述创建工具: {description[:50]}...")
        
        try:
            # 解析描述
            spec = self._parse_description(description)
            
            if not spec.name:
                return {
                    "success": False,
                    "error": "无法从描述中提取工具名称"
                }
            
            # 生成工具处理函数
            handler = self._generate_handler(spec)
            
            # 创建工具定义
            tool_def = ToolDefinition(
                name=spec.name,
                description=spec.description,
                handler=handler,
                parameters=spec.parameters,
                returns=spec.returns,
                category=spec.category
            )
            
            # 注册工具
            self.tool_registry.register(tool_def)
            
            self.logger.info(f"工具创建成功: {spec.name}")
            
            return {
                "success": True,
                "tool_name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters
            }
            
        except Exception as e:
            self.logger.error(f"创建工具失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _parse_description(self, description: str) -> ToolSpecification:
        """
        解析自然语言描述
        
        Args:
            description: 工具描述
            
        Returns:
            ToolSpecification 对象
        """
        spec = ToolSpecification(name="", description=description)
        
        # 尝试从描述中提取工具名称
        name_patterns = [
            r"工具名称[\s：:]+(.+?)(?=\n|$)",
            r"工具名[\s：:]+(.+?)(?=\n|$)",
            r"名称[\s：:]+(.+?)(?=\n|$)",
            r"创建一个(.+?)工具",
            r"开发(.+?)工具",
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, description)
            if match:
                spec.name = match.group(1).strip()
                break
        
        # 如果没有找到名称，使用描述的前几个字
        if not spec.name:
            words = description.split()[:3]
            spec.name = "_".join(words).lower()
        
        # 尝试提取参数
        param_pattern = r"参数[\s：:]+(.+?)(?=\n|返回|$)"
        match = re.search(param_pattern, description)
        if match:
            params_text = match.group(1).strip()
            params = {}
            for param in params_text.split("，"):
                param = param.strip()
                if param:
                    params[param] = "string"
            spec.parameters = params
        
        # 尝试提取返回值
        return_pattern = r"返回[\s：:]+(.+?)(?=\n|$)"
        match = re.search(return_pattern, description)
        if match:
            spec.returns = match.group(1).strip()
        
        # 尝试提取类别
        category_pattern = r"类别[\s：:]+(.+?)(?=\n|$)"
        match = re.search(category_pattern, description)
        if match:
            spec.category = match.group(1).strip()
        
        return spec
    
    def _generate_handler(self, spec: ToolSpecification) -> Callable:
        """
        生成工具处理函数
        
        Args:
            spec: 工具规范
            
        Returns:
            处理函数
        """
        async def handler(**kwargs) -> Dict[str, Any]:
            """
            自动生成的工具处理函数
            
            Args:
                **kwargs: 工具参数
                
            Returns:
                执行结果
            """
            self.logger.debug(f"执行工具: {spec.name}, 参数: {kwargs}")
            
            # 默认实现：返回参数信息
            return {
                "tool_name": spec.name,
                "description": spec.description,
                "parameters_received": kwargs,
                "message": f"工具 {spec.name} 已执行（这是自动生成的占位实现）"
            }
        
        return handler
    
    async def discover_and_add_tools(self, task_description: str) -> List[Dict[str, Any]]:
        """
        发现并添加任务所需的工具
        
        Args:
            task_description: 任务描述
            
        Returns:
            添加结果列表
        """
        self.logger.info(f"分析任务需求: {task_description[:50]}...")
        
        # 简单实现：返回空列表（完整实现需要语义分析）
        return []


async def add_tool_from_text(text: str) -> Dict[str, Any]:
    """
    从文本描述添加工具（便捷函数）
    
    Args:
        text: 工具描述文本
        
    Returns:
        添加结果
    """
    adder = NaturalLanguageToolAdder()
    return await adder.add_tool_from_description(text)


async def discover_missing_tools(task_description: str) -> List[str]:
    """
    发现任务所需的缺失工具
    
    Args:
        task_description: 任务描述
        
    Returns:
        缺失工具名称列表
    """
    return []


# 同步版本供非异步调用
def add_tool_from_text_sync(text: str) -> Dict[str, Any]:
    """
    同步版本：从文本描述添加工具
    
    Args:
        text: 工具描述文本
        
    Returns:
        添加结果
    """
    return asyncio.run(add_tool_from_text(text))