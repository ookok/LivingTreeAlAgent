"""
ToolDefinition - 工具定义数据类
定义工具的元数据结构
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable


@dataclass
class ToolDefinition:
    """工具定义 - 描述一个工具的完整元数据"""
    
    name: str                                           # 工具名称（唯一标识）
    description: str                                    # 工具描述（用于 LLM 理解）
    handler: Optional[Callable] = None                 # 工具处理函数
    parameters: Dict[str, Any] = field(default_factory=dict)   # 参数定义（JSON Schema 格式）
    returns: Dict[str, Any] = field(default_factory=dict)      # 返回值定义
    category: str = "general"                          # 工具分类
    version: str = "1.0.0"                            # 工具版本
    is_builtin: bool = False                           # 是否内置工具
    is_enabled: bool = True                            # 是否启用
    dependencies: List[str] = field(default_factory=list)      # 依赖的其他工具
    tags: List[str] = field(default_factory=list)              # 标签（用于搜索/分类）
    examples: List[Dict[str, Any]] = field(default_factory=list)  # 使用示例
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "returns": self.returns,
            "category": self.category,
            "version": self.version,
            "is_builtin": self.is_builtin,
            "is_enabled": self.is_enabled,
            "dependencies": self.dependencies,
            "tags": self.tags,
            "examples": self.examples
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolDefinition":
        """从字典创建"""
        return cls(**data)
    
    def validate_params(self, params: Dict[str, Any]) -> tuple[bool, str]:
        """
        验证参数是否符合定义
        
        Args:
            params: 待验证的参数
            
        Returns:
            (is_valid, error_message)
        """
        # 检查必需参数
        required = self.parameters.get("required", [])
        for param in required:
            if param not in params:
                return False, f"缺少必需参数: {param}"
        
        # 检查参数类型（简单检查）
        properties = self.parameters.get("properties", {})
        for param_name, param_value in params.items():
            if param_name in properties:
                expected_type = properties[param_name].get("type")
                if expected_type:
                    # 简单类型检查
                    type_map = {
                        "string": str,
                        "number": (int, float),
                        "integer": int,
                        "boolean": bool,
                        "array": list,
                        "object": dict
                    }
                    if expected_type in type_map:
                        if not isinstance(param_value, type_map[expected_type]):
                            return False, f"参数 {param_name} 类型错误，期望 {expected_type}"
        
        return True, ""
