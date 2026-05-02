"""
身份保险箱 (Identity Vault) - 向后兼容层

⚠️ 已迁移至 livingtree.core.identity_vault
本模块保留为兼容层。
"""

from livingtree.core.identity_vault.state_db import StateDB, get_state_db, reset_state_db, VectorClock, Operation, OpType, CRDTType, CRDTOperation, LWWRegister, LWWRegisterDB, GCounter, ORSet
from livingtree.core.identity_vault.content_store import ContentStore, ContentRepository, get_content_repo, reset_content_repo, FileEntry, Tree, Snapshot
from livingtree.core.identity_vault.sync_layer import SyncMessage, MessageType, DeviceInfo, DeviceDiscovery, P2PConnection, P2PConnectionManager, SyncManager, P2PSyncManager, get_p2p_manager, initialize_p2p, reset_p2p_manager
from livingtree.core.identity_vault.cloud_backup import CloudProvider, BackupManifest, CloudCredentials, BackupPacker, CloudAdapter, CloudBackupManager, get_cloud_backup_manager, reset_cloud_backup_manager, AliyunOSSAdapter, TencentCOSAdapter, GoogleDriveAdapter
from livingtree.core.identity_vault.hermes_data管家 import UserProfile, HermesDataButler, get_data_butler, initialize_data_butler, reset_data_butler

__all__ = [
    'StateDB', 'get_state_db', 'reset_state_db', 'VectorClock', 'Operation', 'OpType', 'CRDTType', 'CRDTOperation', 'LWWRegister', 'LWWRegisterDB', 'GCounter', 'ORSet',
    'ContentStore', 'ContentRepository', 'get_content_repo', 'reset_content_repo', 'FileEntry', 'Tree', 'Snapshot',
    'SyncMessage', 'MessageType', 'DeviceInfo', 'DeviceDiscovery', 'P2PConnection', 'P2PConnectionManager', 'SyncManager', 'P2PSyncManager', 'get_p2p_manager', 'initialize_p2p', 'reset_p2p_manager',
    'CloudProvider', 'BackupManifest', 'CloudCredentials', 'BackupPacker', 'CloudAdapter', 'CloudBackupManager', 'get_cloud_backup_manager', 'reset_cloud_backup_manager', 'AliyunOSSAdapter', 'TencentCOSAdapter', 'GoogleDriveAdapter',
    'UserProfile', 'HermesDataButler', 'get_data_butler', 'initialize_data_butler', 'reset_data_butler',
]
