"""
Base Config Manager
基础配置管理器，为所有业务模块的配置管理器提供通用功能。

使用方式：
    from client.src.business.base_config_manager import BaseConfigManager
    
    class MyConfigManager(BaseConfigManager):
        def __init__(self, config_path: Path):
            super().__init__(config_class=MyConfig, config_path=config_path)
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, List, Callable, Type
from dataclasses import dataclass, fields

logger = logging.getLogger(__name__)


class BaseConfigManager:
    """
    基础配置管理器
    
    提供通用功能：
    1. 从 JSON 文件加载配置
    2. 保存配置到 JSON 文件
    3. 获取/设置配置值
    4. 配置验证（钩子方法）
    5. 变更通知（观察者模式）
    
    子类应：
    1. 定义配置数据类（dataclass）
    2. 调用 super().__init__(config_class, config_path)
    3. 按需重写 validate() 方法
    """
    
    def __init__(self, config_class: Type, config_path: Optional[Path] = None):
        """
        初始化配置管理器
        
        Args:
            config_class: 配置数据类（dataclass）
            config_path: 配置文件路径
        """
        self._config_class = config_class
        self._config_path = config_path
        self._config = None
        self._observers: List[Callable[[str, Any, Any], None]] = []
        
    def load(self, path: Optional[Path] = None) -> bool:
        """
        从 JSON 文件加载配置
        
        Args:
            path: 配置文件路径（可选，默认使用 self._config_path）
            
        Returns:
            bool: 是否成功
        """
        path = path or self._config_path
        if path is None:
            logger.error("Config path not set")
            return False
            
        if not path.exists():
            logger.info(f"Config file not found, using defaults: {path}")
            self._config = self._config_class()
            return True
            
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 处理 Path 类型的字段
            for f in fields(self._config_class):
                if f.type == Path and f.name in data:
                    data[f.name] = Path(data[f.name])
            
            self._config = self._config_class(**data)
            logger.info(f"Config loaded: {path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self._config = self._config_class()
            return False
    
    def save(self, path: Optional[Path] = None) -> bool:
        """
        保存配置到 JSON 文件
        
        Args:
            path: 配置文件路径（可选，默认使用 self._config_path）
            
        Returns:
            bool: 是否成功
        """
        path = path or self._config_path
        if path is None:
            logger.error("Config path not set")
            return False
            
        if self._config is None:
            logger.error("Config not loaded")
            return False
            
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # 转换为字典（处理 Path 类型）
            data = {}
            for f in fields(self._config):
                value = getattr(self._config, f.name)
                if isinstance(value, Path):
                    data[f.name] = str(value)
                elif isinstance(value, list):
                    # 处理列表中的 Path
                    data[f.name] = [
                        str(item) if isinstance(item, Path) else item
                        for item in value
                    ]
                else:
                    data[f.name] = value
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Config saved: {path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
    
    def get(self, key: str) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键名
            
        Returns:
            配置值
        """
        if self._config is None:
            self.load()
        return getattr(self._config, key)
    
    def set(self, key: str, value: Any) -> bool:
        """
        设置配置值
        
        Args:
            key: 配置键名
            value: 配置值
            
        Returns:
            bool: 是否成功
        """
        if self._config is None:
            self.load()
            
        if not hasattr(self._config, key):
            logger.warning(f"Unknown config key: {key}")
            return False
            
        old_value = getattr(self._config, key)
        setattr(self._config, key, value)
        
        # 通知观察者
        for observer in self._observers:
            try:
                observer(key, old_value, value)
            except Exception as e:
                logger.error(f"Observer callback failed: {e}")
            
        return True
    
    def update(self, **kwargs) -> None:
        """
        批量更新配置
        
        Args:
            **kwargs: 配置键值对
        """
        for key, value in kwargs.items():
            self.set(key, value)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        
        Returns:
            Dict: 配置字典
        """
        if self._config is None:
            self.load()
        
        result = {}
        for f in fields(self._config):
            value = getattr(self._config, f.name)
            if isinstance(value, Path):
                result[f.name] = str(value)
            else:
                result[f.name] = value
        return result
    
    def validate(self) -> bool:
        """
        验证配置（钩子方法，子类可重写）
        
        Returns:
            bool: 是否有效
        """
        return True
    
    def register_observer(self, callback: Callable[[str, Any, Any], None]) -> None:
        """
        注册配置变更观察者
        
        Args:
            callback: 回调函数，接收 (key, old_value, new_value)
        """
        self._observers.append(callback)
    
    def unregister_observer(self, callback: Callable[[str, Any, Any], None]) -> None:
        """
        取消注册配置变更观察者
        
        Args:
            callback: 回调函数
        """
        if callback in self._observers:
            self._observers.remove(callback)
