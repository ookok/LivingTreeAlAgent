"""
配置类型定义

定义配置的类型和值
"""

from enum import Enum
from typing import Any, Optional


class ConfigType(Enum):
    """配置类型"""
    BOOL = bool
    INT = int
    FLOAT = float
    STRING = str
    LIST = list
    DICT = dict


class ConfigValue:
    """配置值"""
    
    def __init__(self, value: Any, config_type: ConfigType):
        """
        初始化配置值
        
        Args:
            value: 配置值
            config_type: 配置类型
        """
        self.value = value
        self.config_type = config_type
    
    def validate(self) -> bool:
        """
        验证配置值
        
        Returns:
            bool: 是否有效
        """
        return isinstance(self.value, self.config_type.value)
    
    def to_dict(self) -> dict:
        """
        转换为字典
        
        Returns:
            dict: 字典表示
        """
        return {
            'value': self.value,
            'type': self.config_type.name
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Optional['ConfigValue']:
        """
        从字典创建配置值
        
        Args:
            data: 字典数据
            
        Returns:
            ConfigValue: 配置值实例
        """
        try:
            config_type = ConfigType[data['type']]
            return cls(data['value'], config_type)
        except (KeyError, ValueError):
            return None
