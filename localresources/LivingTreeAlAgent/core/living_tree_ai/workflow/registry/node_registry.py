"""节点注册表"""

from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass


@dataclass
class NodeDefinition:
    """节点定义"""
    node_type: str
    name: str
    description: str
    category: str
    icon: str
    inputs: List[Dict[str, Any]]
    outputs: List[Dict[str, Any]]
    config_schema: Dict[str, Any]
    default_config: Dict[str, Any]
    template: Callable = None


class NodeRegistry:
    """节点注册表"""
    
    _instance = None
    _nodes: Dict[str, NodeDefinition] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._nodes = {}
        return cls._instance
    
    def register(self, definition: NodeDefinition):
        """注册节点"""
        self._nodes[definition.node_type] = definition
    
    def get(self, node_type: str) -> Optional[NodeDefinition]:
        """获取节点定义"""
        return self._nodes.get(node_type)
    
    def get_all(self) -> List[NodeDefinition]:
        """获取所有节点定义"""
        return list(self._nodes.values())
    
    def get_by_category(self, category: str) -> List[NodeDefinition]:
        """按类别获取节点"""
        return [n for n in self._nodes.values() if n.category == category]
    
    def get_categories(self) -> List[str]:
        """获取所有类别"""
        categories = set()
        for node in self._nodes.values():
            categories.add(node.category)
        return sorted(list(categories))
    
    def unregister(self, node_type: str):
        """注销节点"""
        if node_type in self._nodes:
            del self._nodes[node_type]


def get_registry() -> NodeRegistry:
    """获取全局节点注册表"""
    return NodeRegistry()
