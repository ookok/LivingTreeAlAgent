"""
配置验证器

验证配置值的有效性
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, List


class ConfigValidator(ABC):
    """配置验证器基类"""
    
    @abstractmethod
    def validate(self, value: Any) -> bool:
        """
        验证配置值
        
        Args:
            value: 配置值
            
        Returns:
            bool: 是否有效
        """
        pass


class RangeValidator(ConfigValidator):
    """
    范围验证器
    验证数值是否在指定范围内
    """
    
    def __init__(self, min_value: Optional[float] = None, max_value: Optional[float] = None):
        """
        初始化范围验证器
        
        Args:
            min_value: 最小值
            max_value: 最大值
        """
        self.min_value = min_value
        self.max_value = max_value
    
    def validate(self, value: Any) -> bool:
        """
        验证配置值
        
        Args:
            value: 配置值
            
        Returns:
            bool: 是否有效
        """
        if not isinstance(value, (int, float)):
            return False
        
        if self.min_value is not None and value < self.min_value:
            return False
        
        if self.max_value is not None and value > self.max_value:
            return False
        
        return True


class ChoicesValidator(ConfigValidator):
    """
    选项验证器
    验证值是否在指定选项中
    """
    
    def __init__(self, choices: List[Any]):
        """
        初始化选项验证器
        
        Args:
            choices: 可选值列表
        """
        self.choices = choices
    
    def validate(self, value: Any) -> bool:
        """
        验证配置值
        
        Args:
            value: 配置值
            
        Returns:
            bool: 是否有效
        """
        return value in self.choices


class RegexValidator(ConfigValidator):
    """
    正则表达式验证器
    验证字符串是否匹配指定正则表达式
    """
    
    def __init__(self, pattern: str):
        """
        初始化正则表达式验证器
        
        Args:
            pattern: 正则表达式
        """
        import re
        self.pattern = re.compile(pattern)
    
    def validate(self, value: Any) -> bool:
        """
        验证配置值
        
        Args:
            value: 配置值
            
        Returns:
            bool: 是否有效
        """
        if not isinstance(value, str):
            return False
        
        return bool(self.pattern.match(value))


class LengthValidator(ConfigValidator):
    """
    长度验证器
    验证字符串或列表的长度是否在指定范围内
    """
    
    def __init__(self, min_length: Optional[int] = None, max_length: Optional[int] = None):
        """
        初始化长度验证器
        
        Args:
            min_length: 最小长度
            max_length: 最大长度
        """
        self.min_length = min_length
        self.max_length = max_length
    
    def validate(self, value: Any) -> bool:
        """
        验证配置值
        
        Args:
            value: 配置值
            
        Returns:
            bool: 是否有效
        """
        if not hasattr(value, '__len__'):
            return False
        
        length = len(value)
        
        if self.min_length is not None and length < self.min_length:
            return False
        
        if self.max_length is not None and length > self.max_length:
            return False
        
        return True
