"""
身份保险箱 (Identity Vault)
============================

核心理念：身份即钥匙，数据主权牢牢掌握在用户手中

架构模块：
1. identity_vault/__init__.py - 主入口，IdentityVaultManager
2. state_db.py - SQLite + CRDT 状态数据库
3. content_store.py - Git-like 内容仓库
4. sync_layer.py - P2P 同步层
5. cloud_backup.py - 云端冷备
6. hermes_data管家.py - Hermes Agent 集成

Author: Hermes Desktop AI Assistant
"""

from . import (
    IdentityVaultManager,
    get_vault_manager,
    reset_vault_manager,
    BIP39_WORDLIST,
    generate_mnemonic,
    mnemonic_to_seed,
    verify_mnemonic,
    KeyType,
    KeyDerivation,
    VaultCrypto,
    DeviceAuth
)

from .state_db import (
    StateDB,
    get_state_db,
    reset_state_db,
    CRDTType,
    CRDTOperation,
    VectorClock,
    Operation
)

from .content_store import (
    ContentStore,
    ContentRepository,
    get_content_repo,
    reset_content_repo,
    FileEntry,
    Tree,
    Snapshot
)

from .sync_layer import (
    SyncMessage,
    MessageType,
    DeviceInfo,
    DeviceDiscovery,
    P2PConnection,
    P2PConnectionManager,
    SyncManager,
    P2PSyncManager,
    get_p2p_manager,
    initialize_p2p,
    reset_p2p_manager
)

from .cloud_backup import (
    CloudProvider,
    BackupManifest,
    CloudCredentials,
    BackupPacker,
    CloudAdapter,
    AliyunOSSAdapter,
    TencentCOSAdapter,
    GoogleDriveAdapter,
    CloudBackupManager,
    get_cloud_backup_manager,
    reset_cloud_backup_manager
)

from .hermes_data管家 import (
    UserProfile,
    HermesDataButler,
    get_data_butler,
    initialize_data_butler,
    reset_data_butler
)

__all__ = [
    # 身份保险箱
    'IdentityVaultManager',
    'get_vault_manager',
    'reset_vault_manager',
    'generate_mnemonic',
    'verify_mnemonic',
    'KeyType',
    'KeyDerivation',
    'VaultCrypto',
    'DeviceAuth',

    # 状态数据库
    'StateDB',
    'get_state_db',
    'reset_state_db',
    'VectorClock',
    'Operation',

    # 内容仓库
    'ContentStore',
    'ContentRepository',
    'get_content_repo',
    'reset_content_repo',
    'FileEntry',
    'Tree',
    'Snapshot',

    # P2P同步
    'SyncMessage',
    'MessageType',
    'DeviceInfo',
    'DeviceDiscovery',
    'P2PConnection',
    'P2PConnectionManager',
    'SyncManager',
    'P2PSyncManager',
    'get_p2p_manager',
    'initialize_p2p',
    'reset_p2p_manager',

    # 云端备份
    'CloudProvider',
    'BackupManifest',
    'CloudCredentials',
    'BackupPacker',
    'CloudAdapter',
    'CloudBackupManager',
    'get_cloud_backup_manager',
    'reset_cloud_backup_manager',

    # Hermes集成
    'UserProfile',
    'HermesDataButler',
    'get_data_butler',
    'initialize_data_butler',
    'reset_data_butler',
]

__version__ = '1.0.0'
__author__ = 'Hermes Desktop AI Assistant'