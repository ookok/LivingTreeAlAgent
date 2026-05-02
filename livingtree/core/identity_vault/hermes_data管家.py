"""
Hermes 数据管家 (Hermes Data Butler)
=====================================

将身份保险箱、状态数据库、内容仓库、同步层、云端备份
整合为 Hermes Agent 的智能数据管理工具集

核心理念：
- Hermes Agent 是策略的大脑，不是数据的搬运工
- 所有操作都通过 Hermes Tools 调用
- 记忆系统自动沉淀交互经验

Author: Hermes Desktop AI Assistant
"""

import os
import json
import time
import logging
import threading
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============================================================
# 用户画像
# ============================================================

@dataclass
class UserProfile:
    """用户画像"""
    device_id: str
    tech_level: str = "intermediate"  # beginner/intermediate/advanced
    preferred_cloud: str = "auto"      # auto/aliyun/tencent/google
    auto_sync: bool = True
    auto_backup: bool = True
    backup_schedule: str = "weekly"    # daily/weekly/monthly
    sync_on_wifi_only: bool = False
    privacy_level: str = "normal"      # normal/high/maximum
    interests: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "tech_level": self.tech_level,
            "preferred_cloud": self.preferred_cloud,
            "auto_sync": self.auto_sync,
            "auto_backup": self.auto_backup,
            "backup_schedule": self.backup_schedule,
            "sync_on_wifi_only": self.sync_on_wifi_only,
            "privacy_level": self.privacy_level,
            "interests": self.interests
        }


# ============================================================
# 数据管家主类
# ============================================================

class HermesDataButler:
    """
    Hermes 数据管家

    整合所有数据层模块，为 Hermes Agent 提供：
    1. 统一的工具接口
    2. 智能的调度策略
    3. 跨会话的记忆
    """

    def __init__(self, device_id: str):
        self.device_id = device_id

        # 子组件
        self._vault = None
        self._state_db = None
        self._content_repo = None
        self._p2p_manager = None
        self._backup_manager = None

        # 用户画像
        self._profile: Optional[UserProfile] = None

        # 回调
        self._callbacks: Dict[str, List[Callable]] = {}

        # 同步状态
        self._sync_status = {
            "last_sync": 0,
            "pending_changes": 0,
            "online_peers": [],
            "sync_errors": []
        }

    # ============================================================
    # 初始化
    # ============================================================

    def initialize(self, config: Dict[str, Any] = None):
        """
        初始化数据管家

        Args:
            config: 配置字典
        """
        if config is None:
            config = {}

        # 1. 初始化身份保险箱
        self._init_vault(config)

        # 2. 初始化状态数据库
        self._init_state_db(config)

        # 3. 初始化内容仓库
        self._init_content_repo(config)

        # 4. 初始化同步层
        self._init_p2p(config)

        # 5. 初始化云端备份
        self._init_backup(config)

        # 6. 加载用户画像
        self._load_profile()

    def _init_vault(self, config: Dict[str, Any]):
        """初始化身份保险箱"""
        try:
            from . import IdentityVaultManager, get_vault_manager

            self._vault = get_vault_manager()
            logger.info("Identity Vault initialized")

        except Exception as e:
            logger.error(f"Vault init failed: {e}")

    def _init_state_db(self, config: Dict[str, Any]):
        """初始化状态数据库"""
        try:
            from .state_db import StateDB, get_state_db

            self._state_db = get_state_db(self.device_id)
            logger.info("State DB initialized")

        except Exception as e:
            logger.error(f"State DB init failed: {e}")

    def _init_content_repo(self, config: Dict[str, Any]):
        """初始化内容仓库"""
        try:
            from .content_store import ContentRepository, get_content_repo

            self._content_repo = get_content_repo(self.device_id)
            logger.info("Content Repository initialized")

        except Exception as e:
            logger.error(f"Content Repo init failed: {e}")

    def _init_p2p(self, config: Dict[str, Any]):
        """初始化P2P同步"""
        try:
            from .sync_layer import initialize_p2p, get_p2p_manager

            relay_servers = config.get("relay_servers", ["139.199.124.242:8888"])

            self._p2p_manager = initialize_p2p(
                self.device_id,
                relay_servers,
                self._state_db,
                self._content_repo
            )
            logger.info("P2P Sync initialized")

        except Exception as e:
            logger.error(f"P2P init failed: {e}")

    def _init_backup(self, config: Dict[str, Any]):
        """初始化云端备份"""
        try:
            from .cloud_backup import CloudBackupManager, get_cloud_backup_manager

            self._backup_manager = get_cloud_backup_manager()
            logger.info("Cloud Backup initialized")

        except Exception as e:
            logger.error(f"Backup init failed: {e}")

    def _load_profile(self):
        """加载用户画像"""
        if not self._state_db:
            return

        profile_data = self._state_db.get("user_profile")
        if profile_data:
            try:
                self._profile = UserProfile(**profile_data)
            except Exception:
                self._profile = UserProfile(device_id=self.device_id)
        else:
            self._profile = UserProfile(device_id=self.device_id)

    def save_profile(self):
        """保存用户画像"""
        if self._state_db and self._profile:
            self._state_db.set("user_profile", self._profile.to_dict())

    # ============================================================
    # 身份管理
    # ============================================================

    def create_identity(self, password: str) -> Dict[str, Any]:
        """
        创建新身份

        Returns:
            {"success": bool, "mnemonic": str, "device_id": str}
        """
        if not self._vault:
            return {"success": False, "error": "Vault not initialized"}

        try:
            mnemonic, device_id = self._vault.create_identity(password)
            self.device_id = device_id

            return {
                "success": True,
                "mnemonic": mnemonic,
                "device_id": device_id,
                "warning": "请立即抄写助记词并妥善保管！"
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def recover_identity(self, mnemonic: str, password: str) -> Dict[str, Any]:
        """
        恢复身份

        Args:
            mnemonic: 助记词
            password: 保险箱密码

        Returns:
            {"success": bool, "device_id": str}
        """
        if not self._vault:
            return {"success": False, "error": "Vault not initialized"}

        try:
            device_id = self._vault.recover_identity(mnemonic, password)
            self.device_id = device_id

            return {
                "success": True,
                "device_id": device_id
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def unlock_vault(self, password: str) -> bool:
        """解锁保险箱"""
        if not self._vault:
            return False
        return self._vault.unlock(password)

    def lock_vault(self):
        """锁定保险箱"""
        if self._vault:
            self._vault.lock()

    def is_vault_unlocked(self) -> bool:
        """检查保险箱是否已解锁"""
        return self._vault.is_unlocked() if self._vault else False

    def get_public_identity(self) -> Dict[str, Any]:
        """获取公共身份信息"""
        if not self._vault:
            return {}
        return self._vault.export_public_identity()

    # ============================================================
    # 状态管理 (CRDT)
    # ============================================================

    def set_state(self, key: str, value: Any, crdt_type: str = "lww_register") -> bool:
        """
        设置状态

        Args:
            key: 状态键
            value: 状态值
            crdt_type: CRDT类型 (lww_register/g_counter/or_set)

        Returns:
            是否成功
        """
        if not self._state_db:
            return False

        try:
            self._state_db.set(key, value, crdt_type)
            return True
        except Exception as e:
            logger.error(f"Set state failed: {e}")
            return False

    def get_state(self, key: str, default: Any = None) -> Any:
        """获取状态"""
        if not self._state_db:
            return default

        return self._state_db.get(key, default)

    def get_all_state(self) -> Dict[str, Any]:
        """获取所有状态"""
        if not self._state_db:
            return {}
        return self._state_db.get_all()

    def add_to_set(self, key: str, element: Any) -> bool:
        """添加到集合"""
        if not self._state_db:
            return False

        try:
            self._state_db.add_to_set(key, element)
            return True
        except Exception as e:
            logger.error(f"Add to set failed: {e}")
            return False

    def get_set(self, key: str) -> List[Any]:
        """获取集合"""
        if not self._state_db:
            return []

        return self._state_db.get(key, [])

    # ============================================================
    # 快照管理
    # ============================================================

    def create_snapshot(self, message: str = "") -> Dict[str, Any]:
        """
        创建快照

        Args:
            message: 快照消息

        Returns:
            快照信息
        """
        if not self._content_repo:
            return {"success": False, "error": "Content repo not initialized"}

        try:
            # 快照哪些目录
            source_dirs = [
                str(Path.home() / ".hermes" / "data"),
                str(Path.home() / ".hermes" / "config")
            ]

            snapshot = self._content_repo.create_snapshot(
                source_dirs[0],  # 先快照数据目录
                message or f"Auto snapshot at {time.strftime('%Y-%m-%d %H:%M')}"
            )

            return {
                "success": True,
                "snapshot_hash": snapshot.get_hash_id(),
                "timestamp": snapshot.timestamp,
                "fingerprint": snapshot.fingerprint
            }

        except Exception as e:
            logger.error(f"Create snapshot failed: {e}")
            return {"success": False, "error": str(e)}

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """列出快照"""
        if not self._content_repo:
            return []

        snapshots = self._content_repo.get_all_snapshots()
        return [
            {
                "hash": s.get_hash_id(),
                "timestamp": s.timestamp,
                "message": s.message,
                "fingerprint": s.fingerprint
            }
            for s in snapshots
        ]

    def restore_snapshot(self, snapshot_hash: str) -> Dict[str, Any]:
        """恢复快照"""
        if not self._content_repo:
            return {"success": False, "error": "Content repo not initialized"}

        try:
            target_dir = str(Path.home() / ".hermes" / "restore")
            success = self._content_repo.restore_snapshot(snapshot_hash, target_dir)

            return {
                "success": success,
                "target_dir": target_dir if success else None
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ============================================================
    # 同步管理
    # ============================================================

    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        if not self._p2p_manager:
            return {"error": "P2P not initialized"}

        try:
            online_peers = self._p2p_manager.get_online_peers()

            return {
                "online": len(online_peers) > 0,
                "peer_count": len(online_peers),
                "peers": [p.device_id for p in online_peers],
                "last_sync": self._sync_status.get("last_sync", 0),
                "pending_ops": len(self._state_db.get_pending_ops()) if self._state_db else 0
            }

        except Exception as e:
            return {"error": str(e)}

    def sync_with_peer(self, peer_id: str) -> Dict[str, Any]:
        """与指定对等节点同步"""
        if not self._p2p_manager or not self._p2p_manager.sync_manager:
            return {"success": False, "error": "P2P not initialized"}

        try:
            result = self._p2p_manager.sync_manager.sync_state_with_peer(peer_id)
            if result.get("success"):
                self._sync_status["last_sync"] = time.time()
            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def sync_all(self) -> Dict[str, Any]:
        """同步所有对等节点"""
        if not self._p2p_manager or not self._p2p_manager.sync_manager:
            return {"success": False, "error": "P2P not initialized"}

        try:
            results = self._p2p_manager.sync_manager.sync_all()
            self._sync_status["last_sync"] = time.time()
            return {"success": True, "results": results}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_pending_operations(self) -> List[Dict[str, Any]]:
        """获取待同步的操作"""
        if not self._state_db:
            return []

        ops = self._state_db.get_pending_ops()
        return [op.to_dict() for op in ops]

    # ============================================================
    # 备份管理
    # ============================================================

    def create_backup(self, categories: List[str] = None) -> Dict[str, Any]:
        """
        创建云端备份

        Args:
            categories: 数据类别 ["state", "content", "config"]

        Returns:
            备份结果
        """
        if not self._backup_manager:
            return {"success": False, "error": "Backup not initialized"}

        if categories is None:
            categories = ["state", "content", "config"]

        try:
            source_dirs = []
            if "state" in categories:
                source_dirs.append(str(Path.home() / ".hermes" / "data"))
            if "content" in categories:
                source_dirs.append(str(Path.home() / ".hermes" / "content"))
            if "config" in categories:
                source_dirs.append(str(Path.home() / ".hermes" / "config"))

            # 获取加密密钥
            encryption_key = None
            if self._vault and self._vault.is_unlocked():
                derived = self._vault.derive_key(KeyType.BACKUP_ENCRYPTION)
                if derived:
                    encryption_key = derived.private_key

            from . import CloudProvider
            provider = CloudProvider.ALIYUN_OSS  # 默认

            result = self._backup_manager.create_backup(
                source_dirs=source_dirs,
                data_categories=categories,
                provider=provider,
                encrypt=True,
                encryption_key=encryption_key
            )

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def restore_backup(self, backup_id: str) -> Dict[str, Any]:
        """恢复备份"""
        if not self._backup_manager:
            return {"success": False, "error": "Backup not initialized"}

        try:
            target_dir = str(Path.home() / ".hermes" / "restore")

            # 获取解密密钥
            decryption_key = None
            if self._vault and self._vault.is_unlocked():
                derived = self._vault.derive_key(KeyType.BACKUP_ENCRYPTION)
                if derived:
                    decryption_key = derived.private_key

            result = self._backup_manager.restore_backup(
                backup_id=backup_id,
                target_dir=target_dir,
                decryption_key=decryption_key
            )

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_backups(self) -> List[Dict[str, Any]]:
        """列出备份"""
        if not self._backup_manager:
            return []

        backups = self._backup_manager.list_backups()
        return [
            {
                "backup_id": b.backup_id,
                "timestamp": b.timestamp,
                "provider": b.provider,
                "size": b.file_size,
                "categories": b.data_categories,
                "status": b.status
            }
            for b in backups
        ]

    def schedule_backup(self, schedule: str = "weekly"):
        """
        设置定时备份

        Args:
            schedule: 备份频率 (daily/weekly/monthly)
        """
        if not self._backup_manager:
            return False

        try:
            source_dirs = [
                str(Path.home() / ".hermes" / "data"),
                str(Path.home() / ".hermes" / "config")
            ]

            self._backup_manager.add_schedule(
                name="Auto Backup",
                source_dirs=source_dirs,
                schedule_type="cron",
                schedule_value=schedule
            )

            self._backup_manager.start_schedule()
            return True

        except Exception as e:
            logger.error(f"Schedule backup failed: {e}")
            return False

    # ============================================================
    # 用户画像
    # ============================================================

    def get_user_profile(self) -> Dict[str, Any]:
        """获取用户画像"""
        if not self._profile:
            return {}
        return self._profile.to_dict()

    def update_user_profile(self, updates: Dict[str, Any]):
        """更新用户画像"""
        if not self._profile:
            return

        for key, value in updates.items():
            if hasattr(self._profile, key):
                setattr(self._profile, key, value)

        self.save_profile()

    def detect_user_type(self) -> str:
        """
        检测用户类型

        基于交互历史推断用户技术等级
        """
        if not self._state_db:
            return "intermediate"

        # 检查用户使用过的命令
        commands = self._state_db.get("user_commands", [])

        advanced_count = sum(1 for c in commands if any(
            kw in str(c) for kw in ["docker", "git", "ssh", "cron", "api"]
        ))
        beginner_count = len(commands) - advanced_count

        if advanced_count > 10:
            return "advanced"
        elif beginner_count > len(commands) * 0.8:
            return "beginner"
        else:
            return "intermediate"

    # ============================================================
    # 事件处理
    # ============================================================

    def on_device_event(self, event_type: str, data: Dict[str, Any]):
        """
        处理设备事件

        用于 Hermes Agent 响应设备状态变化
        """
        handlers = self._callbacks.get(event_type, [])

        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    def register_callback(self, event_type: str, handler: Callable):
        """注册事件回调"""
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(handler)

    # ============================================================
    # 诊断
    # ============================================================

    def diagnose(self) -> Dict[str, Any]:
        """
        运行诊断

        返回系统健康状态
        """
        result = {
            "timestamp": time.time(),
            "device_id": self.device_id,
            "components": {}
        }

        # 保险箱状态
        result["components"]["vault"] = {
            "initialized": self._vault is not None,
            "unlocked": self.is_vault_unlocked(),
            "has_device_id": bool(self.device_id)
        }

        # 状态数据库
        result["components"]["state_db"] = {
            "initialized": self._state_db is not None,
            "pending_ops": len(self._state_db.get_pending_ops()) if self._state_db else -1
        }

        # 内容仓库
        result["components"]["content_repo"] = {
            "initialized": self._content_repo is not None,
            "snapshots": len(self._content_repo.get_all_snapshots()) if self._content_repo else -1
        }

        # P2P同步
        if self._p2p_manager:
            online = self._p2p_manager.get_online_peers()
            result["components"]["p2p"] = {
                "initialized": True,
                "online_peers": len(online),
                "relay_servers": self._p2p_manager.relay_servers
            }
        else:
            result["components"]["p2p"] = {"initialized": False}

        # 云端备份
        result["components"]["backup"] = {
            "initialized": self._backup_manager is not None,
            "last_backup": None  # 可以从数据库查询
        }

        return result


# ============================================================
# 导入辅助类
# ============================================================

try:
    from . import KeyType
except ImportError:
    KeyType = None


# ============================================================
# 全局单例
# ============================================================

_data_butler: Optional[HermesDataButler] = None


def get_data_butler() -> HermesDataButler:
    """获取全局数据管家"""
    global _data_butler
    if _data_butler is None:
        import uuid
        device_id = str(uuid.uuid4())[:16]
        _data_butler = HermesDataButler(device_id)
    return _data_butler


def initialize_data_butler(device_id: str, config: Dict[str, Any] = None) -> HermesDataButler:
    """初始化数据管家"""
    global _data_butler
    _data_butler = HermesDataButler(device_id)
    _data_butler.initialize(config)
    return _data_butler


def reset_data_butler():
    """重置全局数据管家"""
    global _data_butler
    _data_butler = None