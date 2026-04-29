"""
去中心化配置管理
Decentralized Configuration Management
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


@dataclass
class DecentralizedConfig:
    """去中心化系统配置"""
    
    # ============ 基础配置 ============
    node_id: str = ""
    storage_path: Path = field(default_factory=lambda: Path.home() / ".hermes-desktop")
    
    # ============ P2P配置 ============
    p2p_enabled: bool = True
    p2p_port: int = 18888
    max_peers: int = 100
    connection_timeout: int = 30
    
    # ============ 中继服务器配置 ============
    relay_enabled: bool = False
    relay_servers: List[Dict[str, Any]] = field(default_factory=list)
    relay_auto_discover: bool = True
    
    # ============ 知识库同步配置 ============
    sync_enabled: bool = True
    sync_interval: int = 300  # 秒
    sync_on_startup: bool = True
    sync_wifi_only: bool = False
    
    # ============ 腾讯云同步配置 ============
    tencent_sync_enabled: bool = False
    tencent_sync_config: Any = None  # TencentSyncConfig
    
    # ============ 消息配置 ============
    message_enabled: bool = True
    message_retry_count: int = 5
    message_retry_delay: int = 30
    offline_storage: bool = True
    
    # ============ 协同编辑配置 ============
    collab_enabled: bool = True
    collab_cursor_update_interval: int = 100  # 毫秒
    
    # ============ 网络配置 ============
    network_check_interval: int = 30
    preferred_connection: str = "auto"  # auto, p2p, relay
    min_connection_quality: str = "fair"
    
    # ============ 存储配置 ============
    storage_encryption: bool = True
    local_cache_size_mb: int = 1024
    auto_cleanup_days: int = 30
    
    # ============ 安全配置 ============
    require_auth: bool = False
    session_timeout_hours: int = 24
    device_management: bool = True
    
    def __post_init__(self):
        # 确保路径存在
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # 设置默认中继服务器
        if not self.relay_servers:
            self.relay_servers = [
                {"host": "relay1.hermes-p2p.net", "port": 18890, "region": "Global-1"},
                {"host": "relay2.hermes-p2p.net", "port": 18890, "region": "Global-2"},
            ]
    
    @classmethod
    def load(cls, path: Optional[Path] = None) -> "DecentralizedConfig":
        """
        从文件加载配置
        
        Args:
            path: 配置文件路径
        
        Returns:
            DecentralizedConfig: 配置对象
        """
        if path is None:
            path = Path.home() / ".hermes-desktop" / "decentralized_config.json"
        
        if not path.exists():
            logger.info("配置文件不存在，使用默认配置")
            return cls()
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 转换路径
            if 'storage_path' in data:
                data['storage_path'] = Path(data['storage_path'])
            
            return cls(**data)
            
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return cls()
    
    def save(self, path: Optional[Path] = None) -> bool:
        """
        保存配置到文件
        
        Args:
            path: 配置文件路径
        
        Returns:
            bool: 是否成功
        """
        if path is None:
            path = Path.home() / ".hermes-desktop" / "decentralized_config.json"
        
        try:
            # 转换为字典
            data = {
                'node_id': self.node_id,
                'storage_path': str(self.storage_path),
                'p2p_enabled': self.p2p_enabled,
                'p2p_port': self.p2p_port,
                'max_peers': self.max_peers,
                'connection_timeout': self.connection_timeout,
                'relay_enabled': self.relay_enabled,
                'relay_servers': self.relay_servers,
                'relay_auto_discover': self.relay_auto_discover,
                'sync_enabled': self.sync_enabled,
                'sync_interval': self.sync_interval,
                'sync_on_startup': self.sync_on_startup,
                'sync_wifi_only': self.sync_wifi_only,
                'tencent_sync_enabled': self.tencent_sync_enabled,
                'message_enabled': self.message_enabled,
                'message_retry_count': self.message_retry_count,
                'message_retry_delay': self.message_retry_delay,
                'offline_storage': self.offline_storage,
                'collab_enabled': self.collab_enabled,
                'collab_cursor_update_interval': self.collab_cursor_update_interval,
                'network_check_interval': self.network_check_interval,
                'preferred_connection': self.preferred_connection,
                'min_connection_quality': self.min_connection_quality,
                'storage_encryption': self.storage_encryption,
                'local_cache_size_mb': self.local_cache_size_mb,
                'auto_cleanup_days': self.auto_cleanup_days,
                'require_auth': self.require_auth,
                'session_timeout_hours': self.session_timeout_hours,
                'device_management': self.device_management,
            }
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"配置已保存: {path}")
            return True
            
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            return False
    
    def update(self, **kwargs) -> None:
        """
        更新配置
        
        Args:
            **kwargs: 配置项
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                logger.warning(f"未知配置项: {key}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, Path):
                result[key] = str(value)
            else:
                result[key] = value
        return result
    
    def merge(self, other: "DecentralizedConfig") -> None:
        """
        合并另一个配置
        
        Args:
            other: 另一个配置对象
        """
        for key, value in other.__dict__.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)


class ConfigBackup:
    """
    配置备份与迁移
    
    功能：
    - 配置导出
    - 配置导入
    - 配置版本管理
    - 配置回滚
    """
    
    def __init__(self, config: DecentralizedConfig):
        self.config = config
        self._backup_path = config.storage_path / "backups"
        self._backup_path.mkdir(parents=True, exist_ok=True)
        
        # 版本历史
        self._versions: List[Dict[str, Any]] = []
        self._load_version_history()
    
    def _load_version_history(self) -> None:
        """加载版本历史"""
        history_file = self._backup_path / "version_history.json"
        
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    self._versions = json.load(f)
            except Exception as e:
                logger.error(f"加载版本历史失败: {e}")
    
    def _save_version_history(self) -> None:
        """保存版本历史"""
        history_file = self._backup_path / "version_history.json"
        
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(self._versions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存版本历史失败: {e}")
    
    def export(self, path: Optional[Path] = None) -> Optional[Path]:
        """
        导出配置
        
        Args:
            path: 导出路径
        
        Returns:
            Path: 导出文件路径
        """
        if path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = self._backup_path / f"config_backup_{timestamp}.json"
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.config.to_dict(), f, ensure_ascii=False, indent=2)
            
            logger.info(f"配置已导出: {path}")
            return path
            
        except Exception as e:
            logger.error(f"导出配置失败: {e}")
            return None
    
    def import_config(self, path: Path) -> bool:
        """
        导入配置
        
        Args:
            path: 导入文件路径
        
        Returns:
            bool: 是否成功
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 创建新配置
            new_config = DecentralizedConfig.load()
            new_config.merge(DecentralizedConfig(**data))
            
            # 保存
            new_config.save()
            
            # 更新当前配置
            self.config = new_config
            
            logger.info(f"配置已导入: {path}")
            return True
            
        except Exception as e:
            logger.error(f"导入配置失败: {e}")
            return False
    
    def create_backup(self) -> Optional[Path]:
        """
        创建配置备份
        
        Returns:
            Path: 备份文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"config_backup_{timestamp}.json"
        backup_path = self._backup_path / backup_name
        
        # 保存备份
        if self.export(backup_path):
            # 记录版本
            version = {
                'timestamp': timestamp,
                'path': str(backup_path),
                'size': backup_path.stat().st_size
            }
            self._versions.append(version)
            
            # 只保留最近10个版本
            if len(self._versions) > 10:
                old = self._versions.pop(0)
                old_path = Path(old['path'])
                if old_path.exists():
                    old_path.unlink()
            
            self._save_version_history()
            return backup_path
        
        return None
    
    def restore_backup(self, version_index: int = -1) -> bool:
        """
        恢复备份
        
        Args:
            version_index: 版本索引（-1表示最新）
        
        Returns:
            bool: 是否成功
        """
        if not self._versions:
            logger.warning("没有可用的备份")
            return False
        
        if version_index < 0:
            version_index = len(self._versions) - 1
        
        if version_index >= len(self._versions):
            logger.warning(f"无效的版本索引: {version_index}")
            return False
        
        version = self._versions[version_index]
        backup_path = Path(version['path'])
        
        if not backup_path.exists():
            logger.warning(f"备份文件不存在: {backup_path}")
            return False
        
        return self.import_config(backup_path)
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """列出所有备份"""
        return self._versions.copy()
    
    def get_backup_path(self) -> Path:
        """获取备份目录路径"""
        return self._backup_path
