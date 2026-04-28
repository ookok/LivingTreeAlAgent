"""
ToolDefinition - 工具定义

定义工具的元数据，用于工具注册和发现。
"""

from dataclasses import dataclass, field
from typing import Dict, Callable, Any, Optional


@dataclass
class ToolDefinition:
    """
    工具定义
    
    用于描述工具的元数据，包括名称、描述、处理函数、参数等。
    """
    
    name: str
    """工具名称"""
    
    description: str
    """工具描述"""
    
    handler: Callable
    """工具处理函数"""
    
    parameters: Dict[str, str] = field(default_factory=dict)
    """参数 schema，key 为参数名，value 为参数类型"""
    
    returns: str = "ToolResult"
    """返回值 schema"""
    
    category: str = "general"
    """工具类别（network/document/database/task/learning/geo/simulation）"""
    
    version: str = "1.0"
    """工具版本"""
    
    author: str = "system"
    """工具作者"""
    
    enabled: bool = True
    """是否启用"""
    
    tags: Optional[list] = None
    """工具标签"""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "author": self.author,
            "parameters": self.parameters,
            "returns": self.returns,
            "enabled": self.enabled,
            "tags": self.tags or [],
        }

    def is_compatible(self, query: str) -> float:
        """
        判断工具是否与查询兼容
        
        Args:
            query: 用户查询
            
        Returns:
            匹配度（0-1）
        """
        query_lower = query.lower()
        description_lower = self.description.lower()
        
        # 简单匹配：检查关键词
        match_count = 0
        keywords = query_lower.split()
        
        for keyword in keywords:
            if keyword in description_lower or keyword in self.name.lower():
                match_count += 1
        
        return match_count / max(len(keywords), 1)