"""
Base Config Manager
基础配置管理器，为所有业务模块的配置管理器提供通用功能。

支持两种配置存储模式：
  1. dataclass 模式：传入 config_class，配置以 dataclass 实例存储
  2. 字典模式：不传入 config_class，配置以 dict 存储（支持点路径访问）

使用方式（dataclass 模式）：
    from client.src.business.base_config_manager import BaseConfigManager
    
    class MyConfigManager(BaseConfigManager):
        def __init__(self, config_path: Path):
            super().__init__(config_class=MyConfig, config_path=config_path)

使用方式（字典模式，推荐用于复杂嵌套配置）：
    class MyConfigManager(BaseConfigManager):
        def __init__(self, config_path: Path):
            super().__init__(config_path=config_path)  # 不传 config_class
        
        def _init_default_config(self) -> dict:
            return {"version": "1.0", "settings": {...}}
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, List, Callable, Type
from dataclasses import dataclass, fields

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

logger = logging.getLogger(__name__)


class BaseConfigManager:
    """
    基础配置管理器
    
    提供通用功能：
    1. 从 JSON/YAML 文件加载配置
    2. 保存配置到 JSON/YAML 文件
    3. 获取/设置配置值（支持点路径，如 "modules.deep_search.enabled"）
    4. 配置验证（钩子方法）
    5. 变更通知（观察者模式）
    
    内部存储：
    - 如果传入 config_class：使用 dataclass 实例（self._config_obj）
    - 如果不传 config_class：使用字典（self._config_dict）
    
    子类可重写：
    - _init_default_config() -> dict  ：返回默认配置（字典模式）
    - _validate_section(section)       ：验证指定区块
    - validate()                       ：验证整个配置
    """
    
    def __init__(self, config_class: Optional[Type] = None, config_path: Optional[Path] = None):
        """
        初始化配置管理器
        
        Args:
            config_class: 配置数据类（dataclass），传入则使用 dataclass 模式
                         不传则使用字典模式
            config_path: 配置文件路径
        """
        self._config_class = config_class
        self._config_path = config_path
        self._observers: List[Callable[[str, Any, Any], None]] = []

        # 根据模式初始化配置存储
        if config_class is not None:
            # dataclass 模式：暂不初始化，等 load() 或手动设置
            self._config_obj = None
            self._config_dict = None
        else:
            # 字典模式：立即调用钩子方法获取默认配置
            self._config_dict = self._init_default_config()
            self._config_obj = None
        
    def load(self, path: Optional[Path] = None) -> bool:
        """
        从 JSON/YAML 文件加载配置
        
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
            if self._config_class is not None:
                self._config_obj = self._config_class()
            else:
                self._config_dict = self._init_default_config()
            return True
            
        try:
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            # 根据文件扩展名选择解析方式
            if path.suffix in ('.yaml', '.yml'):
                if not _HAS_YAML:
                    # fallback to json
                    data = json.loads(text)
                else:
                    data = yaml.safe_load(text) or {}
            else:
                data = json.loads(text)
            
            # 根据模式存储
            if self._config_class is not None:
                # dataclass 模式：处理 Path 类型字段
                for f in fields(self._config_class):
                    if f.type == Path and f.name in data:
                        data[f.name] = Path(data[f.name])
                self._config_obj = self._config_class(**data)
            else:
                # 字典模式
                self._config_dict = data
            
            logger.info(f"Config loaded: {path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            if self._config_class is not None:
                self._config_obj = self._config_class()
            else:
                self._config_dict = self._init_default_config()
            return False
    
    def save(self, path: Optional[Path] = None) -> bool:
        """
        保存配置到 JSON/YAML 文件
        
        Args:
            path: 配置文件路径（可选，默认使用 self._config_path）
            
        Returns:
            bool: 是否成功
        """
        path = path or self._config_path
        if path is None:
            logger.error("Config path not set")
            return False
            
        config_data = self._get_config_data()
        if config_data is None:
            logger.error("Config not loaded")
            return False
            
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                if path.suffix in ('.yaml', '.yml'):
                    if _HAS_YAML:
                        yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)
                    else:
                        json.dump(config_data, f, ensure_ascii=False, indent=2)
                else:
                    json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Config saved: {path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
    
    def _get_config_data(self) -> Optional[Dict]:
        """获取配置数据（字典格式）"""
        if self._config_class is not None:
            # dataclass 模式
            if self._config_obj is None:
                return None
            data = {}
            for f in fields(self._config_class):
                value = getattr(self._config_obj, f.name)
                if isinstance(value, Path):
                    data[f.name] = str(value)
                elif isinstance(value, list):
                    data[f.name] = [
                        str(item) if isinstance(item, Path) else item
                        for item in value
                    ]
                else:
                    data[f.name] = value
            return data
        else:
            # 字典模式
            return self._config_dict
    
    def _init_default_config(self) -> Dict:
        """
        初始化默认配置（字典模式钩子方法，子类可重写）
        
        Returns:
            Dict: 默认配置字典
        """
        return {}
    
    def get(self, key: str) -> Any:
        """
        获取配置值（支持点路径，如 "modules.deep_search.enabled"）
        
        Args:
            key: 配置键名（支持点路径）
            
        Returns:
            配置值
        """
        data = self._get_config_data()
        if data is None:
            self.load()
            data = self._get_config_data()
            if data is None:
                return None
        
        # 点路径访问
        keys = key.split('.')
        value = data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            elif hasattr(value, k):
                value = getattr(value, k)
            else:
                logger.warning(f"Config key not found: {key}")
                return None
        return value
    
    def set(self, key: str, value: Any) -> bool:
        """
        设置配置值（支持点路径，如 "modules.deep_search.enabled"）
        
        Args:
            key: 配置键名（支持点路径）
            value: 配置值
            
        Returns:
            bool: 是否成功
        """
        data = self._get_config_data()
        if data is None:
            logger.error("Config not loaded")
            return False
            
        # 点路径设置
        keys = key.split('.')
        if len(keys) == 1:
            # 单层键
            old_value = data.get(key) if isinstance(data, dict) else getattr(data, key, None)
            if isinstance(data, dict):
                data[key] = value
            else:
                setattr(data, key, value)
        else:
            # 嵌套键
            target = data
            for k in keys[:-1]:
                if isinstance(target, dict):
                    if k not in target:
                        target[k] = {}
                    target = target[k]
                else:
                    target = getattr(target, k, None)
                    if target is None:
                        logger.warning(f"Config path not found: {key}")
                        return False
            
            last_key = keys[-1]
            old_value = target.get(last_key) if isinstance(target, dict) else getattr(target, last_key, None)
            if isinstance(target, dict):
                target[last_key] = value
            else:
                setattr(target, last_key, value)
        
        # 更新内部存储
        self._update_config_data(data)
        
        # 通知观察者
        for observer in self._observers:
            try:
                observer(key, old_value, value)
            except Exception as e:
                logger.error(f"Observer callback failed: {e}")
            
        return True
    
    def _update_config_data(self, data: Dict) -> None:
        """更新内部配置存储"""
        if self._config_class is not None:
            # dataclass 模式：从字典重建 dataclass
            for f in fields(self._config_class):
                if f.name in data:
                    setattr(self._config_obj, f.name, data[f.name])
        else:
            # 字典模式
            self._config_dict = data
    
    def update(self, **kwargs) -> None:
        """
        批量更新配置
        
        Args:
            **kwargs: 配置键值对（支持点路径）
        """
        for key, value in kwargs.items():
            self.set(key, value)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        
        Returns:
            Dict: 配置字典
        """
        return self._get_config_data() or {}
    
    def validate(self) -> bool:
        """
        验证配置（钩子方法，子类可重写）
        
        Returns:
            bool: 是否有效
        """
        return True
    
    def validate_section(self, section_path: str) -> bool:
        """
        验证指定配置区块（钩子方法，子类可重写）
        
        Args:
            section_path: 区块路径（如 "payment" 或 "modules.deep_search"）
            
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
