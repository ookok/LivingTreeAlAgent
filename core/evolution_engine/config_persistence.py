# -*- coding: utf-8 -*-
"""
配置持久化模块
=============

提供配置的持久化存储:
1. JSON 文件存储
2. QSettings (PyQt6)
3. 环境变量支持
4. 配置导入/导出

Author: LivingTreeAI Team
"""

from __future__ import annotations

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from datetime import datetime


logger = logging.getLogger(__name__)


# ── 配置存储类型 ──────────────────────────────────────────────────────────


class StorageType:
    """存储类型"""
    JSON = "json"
    QSETTINGS = "qsettings"
    ENV = "env"
    MEMORY = "memory"


# ── 配置元数据 ────────────────────────────────────────────────────────────


@dataclass
class ConfigMetadata:
    """配置元数据"""
    created_at: str = ""
    updated_at: str = ""
    version: str = "1.0"
    author: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'version': self.version,
            'author': self.author,
            'description': self.description,
            'tags': self.tags,
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ConfigMetadata':
        return ConfigMetadata(
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            version=data.get('version', '1.0'),
            author=data.get('author', ''),
            description=data.get('description', ''),
            tags=data.get('tags', []),
        )


# ── 配置存储 ──────────────────────────────────────────────────────────────


class ConfigStorage:
    """
    配置持久化存储
    
    支持多种存储后端:
    1. JSON 文件
    2. QSettings (PyQt6)
    3. 环境变量
    4. 内存 (临时)
    """
    
    def __init__(
        self,
        storage_type: str = StorageType.JSON,
        file_path: Optional[str] = None,
        app_name: str = "LivingTreeAI",
        config_name: str = "OptimalConfig",
    ):
        self.storage_type = storage_type
        self.file_path = file_path
        self.app_name = app_name
        self.config_name = config_name
        
        # 内存缓存
        self._memory_cache: Dict[str, Any] = {}
        
        # PyQt6 QSettings
        self._qsettings = None
        if storage_type == StorageType.QSETTINGS:
            self._init_qsettings()
        
        # 默认文件路径
        if file_path is None and storage_type == StorageType.JSON:
            self.file_path = self._get_default_path()
    
    def _get_default_path(self) -> str:
        """获取默认文件路径"""
        config_dir = Path.home() / ".config" / self.app_name
        config_dir.mkdir(parents=True, exist_ok=True)
        return str(config_dir / f"{self.config_name}.json")
    
    def _init_qsettings(self):
        """初始化 QSettings"""
        try:
            from PyQt6.QtCore import QSettings
            self._qsettings = QSettings(self.app_name, self.config_name)
            logger.info("QSettings initialized")
        except ImportError:
            logger.warning("PyQt6 not available, falling back to JSON")
            self.storage_type = StorageType.JSON
    
    # ── 基础操作 ──────────────────────────────────────────────────────────
    
    def save(self, config: Dict[str, Any], metadata: Optional[ConfigMetadata] = None) -> bool:
        """
        保存配置
        
        Args:
            config: 配置字典
            metadata: 元数据
            
        Returns:
            bool: 是否成功
        """
        try:
            # 添加元数据
            save_data = {
                'config': config,
                'metadata': (metadata or ConfigMetadata()).to_dict(),
            }
            
            if self.storage_type == StorageType.JSON:
                return self._save_json(save_data)
            elif self.storage_type == StorageType.QSETTINGS:
                return self._save_qsettings(config)
            elif self.storage_type == StorageType.ENV:
                return self._save_env(config)
            else:
                self._memory_cache = config.copy()
                return True
                
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
    
    def load(self) -> Optional[Dict[str, Any]]:
        """
        加载配置
        
        Returns:
            Optional[Dict[str, Any]]: 配置字典
        """
        try:
            if self.storage_type == StorageType.JSON:
                return self._load_json()
            elif self.storage_type == StorageType.QSETTINGS:
                return self._load_qsettings()
            elif self.storage_type == StorageType.ENV:
                return self._load_env()
            else:
                return self._memory_cache.copy() if self._memory_cache else None
                
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return None
    
    def delete(self) -> bool:
        """删除配置"""
        try:
            if self.storage_type == StorageType.JSON and self.file_path:
                path = Path(self.file_path)
                if path.exists():
                    path.unlink()
                    logger.info(f"Deleted config file: {self.file_path}")
                    return True
            elif self.storage_type == StorageType.QSETTINGS and self._qsettings:
                self._qsettings.clear()
                logger.info("Cleared QSettings")
                return True
            else:
                self._memory_cache.clear()
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete config: {e}")
            return False
    
    def exists(self) -> bool:
        """检查配置是否存在"""
        if self.storage_type == StorageType.JSON and self.file_path:
            return Path(self.file_path).exists()
        elif self.storage_type == StorageType.QSETTINGS:
            return self._qsettings is not None and len(self._qsettings.allKeys()) > 0
        else:
            return bool(self._memory_cache)
    
    # ── JSON 存储 ──────────────────────────────────────────────────────────
    
    def _save_json(self, data: Dict[str, Any]) -> bool:
        """保存为 JSON 文件"""
        if not self.file_path:
            return False
        
        # 确保目录存在
        Path(self.file_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved config to: {self.file_path}")
        return True
    
    def _load_json(self) -> Optional[Dict[str, Any]]:
        """从 JSON 文件加载"""
        if not self.file_path or not Path(self.file_path).exists():
            return None
        
        with open(self.file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data.get('config')
    
    # ── QSettings 存储 ─────────────────────────────────────────────────────
    
    def _save_qsettings(self, config: Dict[str, Any]) -> bool:
        """保存到 QSettings"""
        if not self._qsettings:
            return False
        
        for key, value in config.items():
            self._qsettings.setValue(key, value)
        
        self._qsettings.sync()
        logger.info("Saved config to QSettings")
        return True
    
    def _load_qsettings(self) -> Optional[Dict[str, Any]]:
        """从 QSettings 加载"""
        if not self._qsettings:
            return None
        
        config = {}
        for key in self._qsettings.allKeys():
            config[key] = self._qsettings.value(key)
        
        return config if config else None
    
    # ── 环境变量存储 ───────────────────────────────────────────────────────
    
    def _save_env(self, config: Dict[str, Any]) -> bool:
        """保存到环境变量"""
        prefix = f"{self.app_name.upper()}_{self.config_name.upper()}_"
        
        for key, value in config.items():
            env_key = f"{prefix}{key.upper()}"
            os.environ[env_key] = str(value)
        
        logger.info("Saved config to environment variables")
        return True
    
    def _load_env(self) -> Optional[Dict[str, Any]]:
        """从环境变量加载"""
        prefix = f"{self.app_name.upper()}_{self.config_name.upper()}_"
        
        config = {}
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower()
                # 类型转换
                if value.lower() == 'true':
                    config[config_key] = True
                elif value.lower() == 'false':
                    config[config_key] = False
                elif '.' in value:
                    try:
                        config[config_key] = float(value)
                    except ValueError:
                        config[config_key] = value
                else:
                    try:
                        config[config_key] = int(value)
                    except ValueError:
                        config[config_key] = value
        
        return config if config else None


# ── 配置快照 ──────────────────────────────────────────────────────────────


class ConfigSnapshot:
    """
    配置快照
    
    用于保存和恢复配置状态
    """
    
    def __init__(self, storage: ConfigStorage):
        self.storage = storage
        self._snapshots: Dict[str, Dict[str, Any]] = {}
    
    def create_snapshot(self, name: str) -> bool:
        """
        创建快照
        
        Args:
            name: 快照名称
            
        Returns:
            bool: 是否成功
        """
        config = self.storage.load()
        if config:
            self._snapshots[name] = config.copy()
            logger.info(f"Created snapshot: {name}")
            return True
        return False
    
    def restore_snapshot(self, name: str) -> bool:
        """
        恢复快照
        
        Args:
            name: 快照名称
            
        Returns:
            bool: 是否成功
        """
        if name in self._snapshots:
            return self.storage.save(self._snapshots[name])
        return False
    
    def delete_snapshot(self, name: str) -> bool:
        """删除快照"""
        if name in self._snapshots:
            del self._snapshots[name]
            return True
        return False
    
    def list_snapshots(self) -> List[str]:
        """列出所有快照"""
        return list(self._snapshots.keys())


# ── 配置管理器 ──────────────────────────────────────────────────────────


class ConfigManager:
    """
    配置管理器
    
    提供统一的配置管理接口
    """
    
    def __init__(
        self,
        storage_type: str = StorageType.JSON,
        file_path: Optional[str] = None,
    ):
        self.storage = ConfigStorage(storage_type, file_path)
        self.snapshot = ConfigSnapshot(self.storage)
        
        # 默认配置
        self._defaults = {
            'depth': 5,
            'timeout': 60.0,
            'max_retries': 3,
            'context_limit': 8192,
            'max_tokens': 4096,
            'temperature': 0.7,
            'use_reasoning': True,
            'use_execution': False,
            'use_verification': False,
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        config = self.storage.load()
        if config:
            return config.get(key, default)
        return default
    
    def set(self, key: str, value: Any) -> bool:
        """设置配置值"""
        config = self.storage.load() or self._defaults.copy()
        config[key] = value
        return self.storage.save(config)
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return self.storage.load() or self._defaults.copy()
    
    def set_all(self, config: Dict[str, Any]) -> bool:
        """设置所有配置"""
        # 合并默认值
        merged = self._defaults.copy()
        merged.update(config)
        return self.storage.save(merged)
    
    def reset(self) -> bool:
        """重置为默认值"""
        return self.storage.save(self._defaults)
    
    def export(self, path: str) -> bool:
        """导出配置到文件"""
        try:
            config = self.storage.load()
            if config:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump({
                        'config': config,
                        'exported_at': datetime.now().isoformat(),
                    }, f, indent=2, ensure_ascii=False)
                return True
        except Exception as e:
            logger.error(f"Failed to export config: {e}")
        return False
    
    def import_config(self, path: str) -> bool:
        """从文件导入配置"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            config = data.get('config', data)
            return self.set_all(config)
            
        except Exception as e:
            logger.error(f"Failed to import config: {e}")
        return False


# ── 工厂函数 ─────────────────────────────────────────────────────────────


def create_storage(
    storage_type: str = StorageType.JSON,
    file_path: Optional[str] = None,
) -> ConfigStorage:
    """创建配置存储"""
    return ConfigStorage(storage_type, file_path)


def create_manager(
    storage_type: str = StorageType.JSON,
    file_path: Optional[str] = None,
) -> ConfigManager:
    """创建配置管理器"""
    return ConfigManager(storage_type, file_path)


# ── 测试入口 ─────────────────────────────────────────────────────────────


if __name__ == "__main__":
    print("=" * 60)
    print("配置持久化模块测试")
    print("=" * 60)
    
    # 测试配置
    test_config = {
        'depth': 7,
        'timeout': 120.0,
        'max_retries': 4,
        'context_limit': 16384,
    }
    
    # 1. JSON 存储测试
    print("\n[1] JSON 存储测试")
    json_storage = create_storage(StorageType.JSON, "test_config.json")
    json_storage.save(test_config)
    loaded = json_storage.load()
    print(f"  Saved: {json_storage.exists()}")
    print(f"  Loaded: {loaded}")
    
    # 2. 内存存储测试
    print("\n[2] 内存存储测试")
    mem_storage = create_storage(StorageType.MEMORY)
    mem_storage.save(test_config)
    print(f"  Loaded from memory: {mem_storage.load()}")
    
    # 3. 配置管理器测试
    print("\n[3] 配置管理器测试")
    manager = create_manager(StorageType.MEMORY)
    
    manager.set('depth', 8)
    print(f"  Get depth: {manager.get('depth')}")
    
    manager.set_all({'depth': 5, 'timeout': 60.0})
    print(f"  Get all: {manager.get_all()}")
    
    # 4. 快照测试
    print("\n[4] 快照测试")
    manager.storage.save({'depth': 10})
    manager.snapshot.create_snapshot('backup')
    manager.storage.save({'depth': 1})
    print(f"  Current depth: {manager.get('depth')}")
    manager.snapshot.restore_snapshot('backup')
    print(f"  Restored depth: {manager.get('depth')}")
    print(f"  Snapshots: {manager.snapshot.list_snapshots()}")
    
    # 5. 元数据测试
    print("\n[5] 元数据测试")
    metadata = ConfigMetadata(
        created_at=datetime.now().isoformat(),
        author="Test User",
        description="Test configuration",
        tags=["test", "example"],
    )
    print(f"  Metadata: {metadata.to_dict()}")
    
    # 清理测试文件
    import os
    if os.path.exists("test_config.json"):
        os.remove("test_config.json")
        print("\n  Cleaned up test file")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
