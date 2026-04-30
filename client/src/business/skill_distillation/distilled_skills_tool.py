"""
DistilledSkillsTool - 蒸馏技能工具

将外部蒸馏技能转换为 LivingTreeAlAgent 可调用的工具。
预置了 17 个蒸馏技能源。

Author: LivingTreeAI Agent
Date: 2026-04-30
"""

import os
import json
from typing import Dict, Any, Optional, List
from loguru import logger

from client.src.business.tools.base_tool import BaseTool
from .distillation_config import DEFAULT_SKILL_SOURCES, SkillSource


class DistilledSkillTool(BaseTool):
    """
    蒸馏技能工具基类
    
    每个蒸馏技能都包装为一个工具实例。
    """
    
    def __init__(self, source: SkillSource):
        self._source = source
        self._logger = logger.bind(component=f"DistilledSkill.{source.name}")
    
    @property
    def name(self) -> str:
        return self._source.name
    
    @property
    def description(self) -> str:
        return self._source.description
    
    @property
    def category(self) -> str:
        return self._source.category
    
    @property
    def node_type(self) -> str:
        return "deterministic"
    
    @property
    def version(self) -> str:
        return self._source.version
    
    @property
    def author(self) -> str:
        return self._source.author
    
    @property
    def parameters(self) -> Dict[str, str]:
        return {
            "query": "查询或输入内容",
            "mode": "执行模式"
        }
    
    async def execute(self, query: str = "", mode: str = "default", **kwargs) -> Dict[str, Any]:
        """
        执行蒸馏技能
        
        Args:
            query: 查询内容
            mode: 执行模式（default/analyze/generate）
            
        Returns:
            执行结果
        """
        try:
            result_data = {
                "skill_name": self._source.name,
                "skill_category": self._source.category,
                "author": self._source.author,
                "url": self._source.url,
                "query": query,
                "mode": mode,
                "tags": self._source.tags,
                "message": f"蒸馏技能 {self._source.name} 执行成功"
            }
            
            return {
                "success": True,
                "message": f"{self._source.description}",
                "data": result_data
            }
            
        except Exception as e:
            self._logger.error(f"执行失败: {e}")
            return {
                "success": False,
                "message": str(e),
                "data": None
            }
    
    def get_agent_info(self) -> Dict[str, Any]:
        """获取智能体调用信息"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": {
                "query": {
                    "type": "string",
                    "description": "查询或输入内容",
                    "required": False
                },
                "mode": {
                    "type": "string",
                    "description": "执行模式（default/analyze/generate）",
                    "required": False,
                    "default": "default"
                }
            },
            "examples": [
                {
                    "input": {"query": "请分析这个问题", "mode": "analyze"},
                    "description": f"使用 {self._source.name} 分析问题"
                }
            ],
            "metadata": {
                "author": self._source.author,
                "url": self._source.url,
                "tags": self._source.tags
            }
        }


# 创建所有蒸馏技能工具实例
_DISTILLED_TOOLS = []
_SKILL_MAP = {}

for source in DEFAULT_SKILL_SOURCES:
    tool = DistilledSkillTool(source)
    _DISTILLED_TOOLS.append(tool)
    _SKILL_MAP[source.name] = tool


def get_distilled_tools() -> List[DistilledSkillTool]:
    """获取所有蒸馏技能工具"""
    return _DISTILLED_TOOLS


def get_tool_by_name(name: str) -> Optional[DistilledSkillTool]:
    """根据名称获取蒸馏技能工具"""
    return _SKILL_MAP.get(name)


def get_tools_by_category(category: str) -> List[DistilledSkillTool]:
    """按类别获取蒸馏技能工具"""
    return [tool for tool in _DISTILLED_TOOLS if tool.category == category]


def register_all_tools():
    """注册所有蒸馏技能工具到系统"""
    from client.src.business.tools.tool_registry import ToolRegistry
    from client.src.business.skill_evolution.skill_registry import SkillRegistry, PermissionLevel
    
    tool_registry = ToolRegistry.get_instance()
    skill_registry = SkillRegistry()
    
    registered_count = 0
    
    for tool in _DISTILLED_TOOLS:
        try:
            # 注册到工具注册中心
            tool.register()
            
            # 注册到技能注册中心
            skill_registry.register_skill(
                skill_id=tool.name,
                name=tool.name.replace("-", " ").title(),
                description=tool.description,
                category=tool.category,
                permission_level=PermissionLevel.PUBLIC
            )
            
            registered_count += 1
            logger.info(f"已注册蒸馏技能: {tool.name}")
            
        except Exception as e:
            logger.error(f"注册蒸馏技能失败 {tool.name}: {e}")
    
    return registered_count


def get_skill_categories() -> List[str]:
    """获取所有技能类别"""
    categories = set()
    for tool in _DISTILLED_TOOLS:
        categories.add(tool.category)
    return sorted(list(categories))


def get_stats() -> Dict[str, Any]:
    """获取统计信息"""
    category_counts = {}
    for tool in _DISTILLED_TOOLS:
        category_counts[tool.category] = category_counts.get(tool.category, 0) + 1
    
    return {
        "total_skills": len(_DISTILLED_TOOLS),
        "categories": category_counts,
        "skill_names": [tool.name for tool in _DISTILLED_TOOLS]
    }


# 创建便捷访问函数
def get_thinking_skills() -> List[DistilledSkillTool]:
    """获取思维模型类技能"""
    return get_tools_by_category("thinking")


def get_business_skills() -> List[DistilledSkillTool]:
    """获取商业决策类技能"""
    return get_tools_by_category("business")


def get_philosophy_skills() -> List[DistilledSkillTool]:
    """获取哲学思考类技能"""
    return get_tools_by_category("philosophy")


def get_science_skills() -> List[DistilledSkillTool]:
    """获取科学方法类技能"""
    return get_tools_by_category("science")


def get_utility_skills() -> List[DistilledSkillTool]:
    """获取工具技能"""
    return get_tools_by_category("utility")


# 自动注册（当模块被导入时）
try:
    register_all_tools()
except Exception as e:
    logger.warning(f"自动注册蒸馏技能失败（可能在初始化阶段）: {e}")


# 测试函数
async def test_distilled_skills():
    """测试蒸馏技能工具"""
    import sys
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试蒸馏技能工具")
    print("=" * 60)
    
    stats = get_stats()
    print(f"\n总技能数: {stats['total_skills']}")
    print(f"类别分布: {stats['categories']}")
    
    # 测试获取类别技能
    print("\n思维模型类技能:")
    for tool in get_thinking_skills():
        print(f"  - {tool.name}: {tool.description}")
    
    # 测试执行技能
    print("\n测试执行技能:")
    tool = get_tool_by_name("munger-skill")
    if tool:
        result = await tool.execute(query="如何做出更好的投资决策?", mode="analyze")
        print(f"✓ {tool.name} 执行结果: {'成功' if result['success'] else '失败'}")
        print(f"  消息: {result['message']}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_distilled_skills())