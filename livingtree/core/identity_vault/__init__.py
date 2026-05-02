"""
身份保险箱 (Identity Vault)

核心理念：身份即钥匙，数据主权牢牢掌握在用户手中

模块：状态数据库、内容仓库、P2P 同步、云端备份、Hermes 集成
"""

from .state_db import StateDB, get_state_db, reset_state_db, VectorClock, Operation, OpType, CRDTType, CRDTOperation, LWWRegister, LWWRegisterDB, GCounter, ORSet
from .content_store import ContentStore, ContentRepository, get_content_repo, reset_content_repo, FileEntry, Tree, Snapshot
from .sync_layer import SyncMessage, MessageType, DeviceInfo, DeviceDiscovery, P2PConnection, P2PConnectionManager, SyncManager, P2PSyncManager, get_p2p_manager, initialize_p2p, reset_p2p_manager
from .cloud_backup import CloudProvider, BackupManifest, CloudCredentials, BackupPacker, CloudAdapter, CloudBackupManager, get_cloud_backup_manager, reset_cloud_backup_manager, AliyunOSSAdapter, TencentCOSAdapter, GoogleDriveAdapter
from .hermes_data管家 import UserProfile, HermesDataButler, get_data_butler, initialize_data_butler, reset_data_butler

__version__ = '1.0.0'
__all__ = [
    'StateDB', 'get_state_db', 'reset_state_db', 'VectorClock', 'Operation', 'OpType', 'CRDTType', 'CRDTOperation', 'LWWRegister', 'LWWRegisterDB', 'GCounter', 'ORSet',
    'ContentStore', 'ContentRepository', 'get_content_repo', 'reset_content_repo', 'FileEntry', 'Tree', 'Snapshot',
    'SyncMessage', 'MessageType', 'DeviceInfo', 'DeviceDiscovery', 'P2PConnection', 'P2PConnectionManager', 'SyncManager', 'P2PSyncManager', 'get_p2p_manager', 'initialize_p2p', 'reset_p2p_manager',
    'CloudProvider', 'BackupManifest', 'CloudCredentials', 'BackupPacker', 'CloudAdapter', 'CloudBackupManager', 'get_cloud_backup_manager', 'reset_cloud_backup_manager', 'AliyunOSSAdapter', 'TencentCOSAdapter', 'GoogleDriveAdapter',
    'UserProfile', 'HermesDataButler', 'get_data_butler', 'initialize_data_butler', 'reset_data_butler',
]
