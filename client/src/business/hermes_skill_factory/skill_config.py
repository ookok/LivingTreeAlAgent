"""
SkillConfig - 技能配置数据结构

定义技能配置的标准化数据格式，支持从 YAML/JSON 加载配置。
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import json
import yaml


class ParameterType(Enum):
    """参数类型"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    ANY = "any"


class ToolCategory(Enum):
    """工具类别"""
    GENERAL = "general"
    SEARCH = "search"
    DOCUMENT = "document"
    DATABASE = "database"
    NETWORK = "network"
    GEO = "geo"
    SIMULATION = "simulation"
    UTILITY = "utility"
    DESIGN = "design"
    TASK = "task"
    LEARNING = "learning"


class NodeType(Enum):
    """节点类型"""
    DETERMINISTIC = "deterministic"
    AI = "ai"


@dataclass
class ParameterConfig:
    """参数配置"""
    name: str
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Any = None
    enum: Optional[List[str]] = None
    properties: Optional[Dict[str, 'ParameterConfig']] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "required": self.required,
        }
        if self.default is not None:
            result["default"] = self.default
        if self.enum:
            result["enum"] = self.enum
        if self.properties:
            result["properties"] = {k: v.to_dict() for k, v in self.properties.items()}
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ParameterConfig':
        """从字典创建"""
        return cls(
            name=data["name"],
            type=data.get("type", "string"),
            description=data.get("description", ""),
            required=data.get("required", False),
            default=data.get("default"),
            enum=data.get("enum"),
            properties={k: cls.from_dict(v) for k, v in data.get("properties", {}).items()}
        )


@dataclass
class ToolConfig:
    """工具配置"""
    name: str
    description: str
    category: str = "general"
    node_type: str = "deterministic"
    version: str = "1.0"
    author: str = "system"
    parameters: List[ParameterConfig] = field(default_factory=list)
    returns: str = "ToolResult"
    examples: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    icon: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "node_type": self.node_type,
            "version": self.version,
            "author": self.author,
            "parameters": [p.to_dict() for p in self.parameters],
            "returns": self.returns,
            "examples": self.examples,
            "tags": self.tags,
            "icon": self.icon
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ToolConfig':
        """从字典创建"""
        return cls(
            name=data["name"],
            description=data["description"],
            category=data.get("category", "general"),
            node_type=data.get("node_type", "deterministic"),
            version=data.get("version", "1.0"),
            author=data.get("author", "system"),
            parameters=[ParameterConfig.from_dict(p) for p in data.get("parameters", [])],
            returns=data.get("returns", "ToolResult"),
            examples=data.get("examples", []),
            tags=data.get("tags", []),
            icon=data.get("icon")
        )


@dataclass
class SkillConfig:
    """技能配置"""
    tools: List[ToolConfig] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "tools": [t.to_dict() for t in self.tools]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SkillConfig':
        """从字典创建"""
        return cls(
            tools=[ToolConfig.from_dict(t) for t in data.get("tools", [])]
        )

    @classmethod
    def from_yaml(cls, yaml_content: str) -> 'SkillConfig':
        """从 YAML 内容创建"""
        data = yaml.safe_load(yaml_content)
        return cls.from_dict(data)

    @classmethod
    def from_yaml_file(cls, filepath: str) -> 'SkillConfig':
        """从 YAML 文件创建"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return cls.from_yaml(f.read())

    @classmethod
    def from_json(cls, json_content: str) -> 'SkillConfig':
        """从 JSON 内容创建"""
        data = json.loads(json_content)
        return cls.from_dict(data)

    @classmethod
    def from_json_file(cls, filepath: str) -> 'SkillConfig':
        """从 JSON 文件创建"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return cls.from_json(f.read())

    def to_yaml(self) -> str:
        """转换为 YAML"""
        return yaml.dump(self.to_dict(), default_flow_style=False, allow_unicode=True)

    def to_json(self) -> str:
        """转换为 JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def save_to_yaml(self, filepath: str):
        """保存为 YAML 文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_yaml())

    def save_to_json(self, filepath: str):
        """保存为 JSON 文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_json())