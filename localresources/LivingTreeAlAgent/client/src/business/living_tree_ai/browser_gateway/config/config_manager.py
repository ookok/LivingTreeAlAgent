"""
配置管理器

借鉴 qutebrowser 的配置管理，为 AI 增强浏览器提供配置功能
"""

import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass

from .config_types import ConfigType, ConfigValue
from .config_validator import ConfigValidator


@dataclass
class ConfigOption:
    """配置选项"""
    name: str
    default: Any
    config_type: ConfigType
    description: str = ""
    validator: Optional[ConfigValidator] = None
    restart_required: bool = False


class ConfigManager:
    """配置管理器"""
    
    def __init__(self):
        self._options: Dict[str, ConfigOption] = {}
        self._config: Dict[str, Any] = {}
        self._config_path: Optional[str] = None
        self._defaults: Dict[str, Any] = {}
    
    def set_config_path(self, path: str):
        """
        设置配置文件路径
        
        Args:
            path: 配置文件路径
        """
        self._config_path = path
    
    def add_option(self, option: ConfigOption):
        """
        添加配置选项
        
        Args:
            option: 配置选项
        """
        self._options[option.name] = option
        self._defaults[option.name] = option.default
    
    def add_options(self, options: list[ConfigOption]):
        """
        添加多个配置选项
        
        Args:
            options: 配置选项列表
        """
        for option in options:
            self.add_option(option)
    
    def load(self):
        """
        加载配置
        """
        if not self._config_path:
            return
        
        try:
            if os.path.exists(self._config_path):
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                
                # 验证并加载配置
                for key, value in loaded_config.items():
                    if key in self._options:
                        option = self._options[key]
                        # 验证类型
                        if isinstance(value, option.config_type.value):
                            # 验证值
                            if option.validator:
                                if option.validator.validate(value):
                                    self._config[key] = value
                            else:
                                self._config[key] = value
        except Exception as e:
            print(f"Failed to load config: {e}")
    
    def save(self):
        """
        保存配置
        """
        if not self._config_path:
            return
        
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
            
            # 保存配置
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save config: {e}")
    
    def get(self, name: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            name: 配置名称
            default: 默认值
            
        Returns:
            Any: 配置值
        """
        if name in self._config:
            return self._config[name]
        elif name in self._defaults:
            return self._defaults[name]
        else:
            return default
    
    def set(self, name: str, value: Any) -> bool:
        """
        设置配置值
        
        Args:
            name: 配置名称
            value: 配置值
            
        Returns:
            bool: 是否成功
        """
        if name not in self._options:
            return False
        
        option = self._options[name]
        
        # 验证类型
        if not isinstance(value, option.config_type.value):
            return False
        
        # 验证值
        if option.validator:
            if not option.validator.validate(value):
                return False
        
        # 设置值
        self._config[name] = value
        return True
    
    def reset(self, name: str):
        """
        重置配置值
        
        Args:
            name: 配置名称
        """
        if name in self._options:
            if name in self._config:
                del self._config[name]
    
    def reset_all(self):
        """
        重置所有配置值
        """
        self._config.clear()
    
    def list_options(self) -> Dict[str, ConfigOption]:
        """
        列出所有配置选项
        
        Returns:
            Dict[str, ConfigOption]: 配置选项字典
        """
        return self._options
    
    def get_config_dict(self) -> Dict[str, Any]:
        """
        获取配置字典
        
        Returns:
            Dict[str, Any]: 配置字典
        """
        config = {}
        for name, option in self._options.items():
            config[name] = self.get(name)
        return config


# 单例实例
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """
    获取配置管理器实例
    
    Returns:
        ConfigManager: 配置管理器实例
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
