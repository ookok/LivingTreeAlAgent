"""节点发现器

自动发现 OpenHarness 集成的工具和技能，作为工作流节点
"""

from typing import List, Dict, Any

from .node_registry import NodeRegistry, NodeDefinition
from ...openharness_integration.tools import ToolSystem
from ...openharness_integration.skills import SkillSystem


class NodeDiscoverer:
    """节点发现器
    
    自动发现 OpenHarness 集成的工具和技能，作为工作流节点
    """
    
    def __init__(self):
        """初始化节点发现器"""
        # 工具系统实例
        self.tool_system = ToolSystem()
        
        # 技能系统实例
        self.skill_system = SkillSystem()
    
    def discover_nodes(self) -> List[NodeDefinition]:
        """发现所有可用的节点
        
        Returns:
            发现的节点定义列表
        """
        nodes = []
        
        # 发现工具节点
        tool_nodes = self._discover_tool_nodes()
        nodes.extend(tool_nodes)
        
        # 发现技能节点
        skill_nodes = self._discover_skill_nodes()
        nodes.extend(skill_nodes)
        
        return nodes
    
    def _discover_tool_nodes(self) -> List[NodeDefinition]:
        """发现工具节点
        
        Returns:
            工具节点定义列表
        """
        tool_nodes = []
        
        # 获取所有工具
        tools = self.tool_system.get_all_tools()
        
        for tool_info in tools:
            tool_name = tool_info["name"]
            tool_description = tool_info["description"]
            parameters = tool_info.get("parameters", {})
            
            # 构建输入端口
            inputs = []
            for param_name, param_type in parameters.items():
                if param_name != "description":
                    inputs.append({
                        "name": param_name,
                        "type": "string",  # 简化处理，所有参数都作为字符串输入
                        "description": parameters.get("description", param_name)
                    })
            
            # 构建节点定义
            node_def = NodeDefinition(
                node_type=f"tool.{tool_name}",
                name=f"工具: {tool_name}",
                description=tool_description,
                category="tool",
                icon="🔧",
                inputs=inputs,
                outputs=[
                    {"name": "result", "type": "any", "description": "工具执行结果"}
                ],
                config_schema={
                    "tool_name": {"type": "string", "default": tool_name}
                },
                default_config={
                    "tool_name": tool_name
                }
            )
            
            tool_nodes.append(node_def)
        
        print(f"[NodeDiscoverer] 发现了 {len(tool_nodes)} 个工具节点")
        return tool_nodes
    
    def _discover_skill_nodes(self) -> List[NodeDefinition]:
        """发现技能节点
        
        Returns:
            技能节点定义列表
        """
        skill_nodes = []
        
        # 获取所有技能
        skills = self.skill_system.get_all_skills()
        
        for skill_info in skills:
            skill_name = skill_info["name"]
            skill_description = skill_info["description"]
            
            # 构建节点定义
            node_def = NodeDefinition(
                node_type=f"skill.{skill_name}",
                name=f"技能: {skill_name}",
                description=skill_description,
                category="skill",
                icon="🧠",
                inputs=[
                    {"name": "prompt", "type": "string", "description": "技能输入提示"},
                    {"name": "context", "type": "any", "description": "上下文信息"}
                ],
                outputs=[
                    {"name": "result", "type": "any", "description": "技能执行结果"}
                ],
                config_schema={
                    "skill_name": {"type": "string", "default": skill_name}
                },
                default_config={
                    "skill_name": skill_name
                }
            )
            
            skill_nodes.append(node_def)
        
        print(f"[NodeDiscoverer] 发现了 {len(skill_nodes)} 个技能节点")
        return skill_nodes
    
    def register_discovered_nodes(self, registry: NodeRegistry):
        """注册发现的节点到注册表
        
        Args:
            registry: 节点注册表
        """
        nodes = self.discover_nodes()
        
        for node in nodes:
            registry.register(node)
        
        print(f"[NodeDiscoverer] 注册了 {len(nodes)} 个发现的节点")


# 导出节点发现器
def get_node_discoverer() -> NodeDiscoverer:
    """获取节点发现器实例
    
    Returns:
        节点发现器实例
    """
    return NodeDiscoverer()


# 导出函数
__all__ = ['NodeDiscoverer', 'get_node_discoverer']
