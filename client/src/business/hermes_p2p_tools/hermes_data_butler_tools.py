"""
Hermes Data Butler Tools - 数据管家工具集
==========================================

将身份保险箱、数据管家、中继路由封装为Hermes Tools

Author: Hermes Desktop AI Assistant
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def _get_butler():
    """获取数据管家实例"""
    from business.identity_vault import get_data_butler
    return get_data_butler()


def _get_relay_router():
    """获取中继路由器"""
    from business.relay_router import get_connection_manager, get_smart_router, get_health_monitor
    return {
        "connection_manager": get_connection_manager(),
        "smart_router": get_smart_router(),
        "health_monitor": get_health_monitor()
    }


def _get_vault():
    """获取身份保险箱"""
    from business.identity_vault import get_vault_manager
    return get_vault_manager()


# ============================================================
# 身份管理工具
# ============================================================

def create_identity(password: str) -> Dict[str, Any]:
    """
    创建新身份

    Args:
        password: 保险箱密码

    Returns:
        {"success": bool, "mnemonic": str, "device_id": str, "error": str}
    """
    try:
        vault = _get_vault()
        mnemonic, device_id = vault.create_identity(password)

        # 同时初始化数据管家
        butler = _get_butler()
        butler.initialize({"device_id": device_id})

        return {
            "success": True,
            "mnemonic": mnemonic,
            "device_id": device_id,
            "warning": "请立即抄写助记词并妥善保管！"
        }
    except Exception as e:
        logger.error(f"Create identity failed: {e}")
        return {"success": False, "error": str(e)}


def recover_identity(mnemonic: str, password: str) -> Dict[str, Any]:
    """
    从助记词恢复身份

    Args:
        mnemonic: 助记词
        password: 保险箱密码

    Returns:
        {"success": bool, "device_id": str, "error": str}
    """
    try:
        vault = _get_vault()
        device_id = vault.recover_identity(mnemonic, password)

        # 初始化数据管家
        butler = _get_butler()
        butler.initialize({"device_id": device_id})

        return {"success": True, "device_id": device_id}
    except Exception as e:
        logger.error(f"Recover identity failed: {e}")
        return {"success": False, "error": str(e)}


def unlock_vault(password: str) -> Dict[str, Any]:
    """
    解锁保险箱

    Args:
        password: 保险箱密码

    Returns:
        {"success": bool, "error": str}
    """
    try:
        vault = _get_vault()
        success = vault.unlock(password)

        if success:
            # 初始化数据管家
            butler = _get_butler()
            butler.initialize({})

        return {"success": success}
    except Exception as e:
        logger.error(f"Unlock vault failed: {e}")
        return {"success": False, "error": str(e)}


def lock_vault() -> Dict[str, Any]:
    """
    锁定保险箱

    Returns:
        {"success": bool}
    """
    try:
        vault = _get_vault()
        vault.lock()
        return {"success": True}
    except Exception as e:
        logger.error(f"Lock vault failed: {e}")
        return {"success": False, "error": str(e)}


def get_vault_status() -> Dict[str, Any]:
    """
    获取保险箱状态

    Returns:
        {"unlocked": bool, "device_id": str}
    """
    try:
        vault = _get_vault()
        butler = _get_butler()

        return {
            "unlocked": vault.is_unlocked(),
            "device_id": vault.get_device_id() or butler.device_id,
            "has_mnemonic": False  # 助记词加密存储，不暴露
        }
    except Exception as e:
        logger.error(f"Get vault status failed: {e}")
        return {"unlocked": False, "error": str(e)}


# ============================================================
# 状态管理工具
# ============================================================

def set_state(key: str, value: Any, crdt_type: str = "lww_register") -> Dict[str, Any]:
    """
    设置状态

    Args:
        key: 状态键
        value: 状态值
        crdt_type: CRDT类型 (lww_register/g_counter/or_set)

    Returns:
        {"success": bool}
    """
    try:
        butler = _get_butler()
        success = butler.set_state(key, value, crdt_type)
        return {"success": success}
    except Exception as e:
        logger.error(f"Set state failed: {e}")
        return {"success": False, "error": str(e)}


def get_state(key: str, default: Any = None) -> Dict[str, Any]:
    """
    获取状态

    Args:
        key: 状态键
        default: 默认值

    Returns:
        {"value": Any}
    """
    try:
        butler = _get_butler()
        value = butler.get_state(key, default)
        return {"value": value}
    except Exception as e:
        logger.error(f"Get state failed: {e}")
        return {"value": default, "error": str(e)}


def get_all_state() -> Dict[str, Any]:
    """
    获取所有状态

    Returns:
        {"state": Dict}
    """
    try:
        butler = _get_butler()
        state = butler.get_all_state()
        return {"state": state}
    except Exception as e:
        logger.error(f"Get all state failed: {e}")
        return {"state": {}, "error": str(e)}


# ============================================================
# 同步管理工具
# ============================================================

def sync_data() -> Dict[str, Any]:
    """
    同步所有数据

    Returns:
        {"success": bool, "results": dict}
    """
    try:
        butler = _get_butler()
        result = butler.sync_all()
        return result
    except Exception as e:
        logger.error(f"Sync data failed: {e}")
        return {"success": False, "error": str(e)}


def sync_with_peer(peer_id: str) -> Dict[str, Any]:
    """
    与指定对等节点同步

    Args:
        peer_id: 对等节点ID

    Returns:
        {"success": bool, "result": dict}
    """
    try:
        butler = _get_butler()
        result = butler.sync_with_peer(peer_id)
        return result
    except Exception as e:
        logger.error(f"Sync with peer failed: {e}")
        return {"success": False, "error": str(e)}


def get_pending_operations() -> Dict[str, Any]:
    """
    获取待同步的操作

    Returns:
        {"operations": List}
    """
    try:
        butler = _get_butler()
        ops = butler.get_pending_operations()
        return {"operations": ops, "count": len(ops)}
    except Exception as e:
        logger.error(f"Get pending operations failed: {e}")
        return {"operations": [], "error": str(e)}


# ============================================================
# 备份管理工具
# ============================================================

def create_backup(categories: list = None) -> Dict[str, Any]:
    """
    创建云端备份

    Args:
        categories: 数据类别 ["state", "content", "config"]

    Returns:
        {"success": bool, "backup_id": str, "error": str}
    """
    try:
        butler = _get_butler()
        result = butler.create_backup(categories)
        return result
    except Exception as e:
        logger.error(f"Create backup failed: {e}")
        return {"success": False, "error": str(e)}


def restore_backup(backup_id: str) -> Dict[str, Any]:
    """
    恢复备份

    Args:
        backup_id: 备份ID

    Returns:
        {"success": bool, "error": str}
    """
    try:
        butler = _get_butler()
        result = butler.restore_backup(backup_id)
        return result
    except Exception as e:
        logger.error(f"Restore backup failed: {e}")
        return {"success": False, "error": str(e)}


def list_backups() -> Dict[str, Any]:
    """
    列出所有备份

    Returns:
        {"backups": List}
    """
    try:
        butler = _get_butler()
        backups = butler.list_backups()
        return {"backups": backups, "count": len(backups)}
    except Exception as e:
        logger.error(f"List backups failed: {e}")
        return {"backups": [], "error": str(e)}


# ============================================================
# 连接管理工具
# ============================================================

def get_connection_status() -> Dict[str, Any]:
    """
    获取连接状态

    Returns:
        {"state": str, "stage": str, "endpoint": str}
    """
    try:
        routers = _get_relay_router()
        cm = routers["connection_manager"]
        status = cm.get_status()
        return status
    except Exception as e:
        logger.error(f"Get connection status failed: {e}")
        return {"state": "unknown", "error": str(e)}


def force_reconnect() -> Dict[str, Any]:
    """
    强制重新连接

    Returns:
        {"success": bool}
    """
    try:
        routers = _get_relay_router()
        cm = routers["connection_manager"]
        cm.force_reconnect()
        return {"success": True}
    except Exception as e:
        logger.error(f"Force reconnect failed: {e}")
        return {"success": False, "error": str(e)}


def get_route_table() -> Dict[str, Any]:
    """
    获取路由表

    Returns:
        {"routes": Dict}
    """
    try:
        routers = _get_relay_router()
        sr = routers["smart_router"]
        routes = sr.get_route_table()
        return routes
    except Exception as e:
        logger.error(f"Get route table failed: {e}")
        return {"routes": {}, "error": str(e)}


def get_relay_health() -> Dict[str, Any]:
    """
    获取中继健康状态

    Returns:
        {"health": Dict}
    """
    try:
        routers = _get_relay_router()
        hm = routers["health_monitor"]
        health = hm.get_health_summary()
        return health
    except Exception as e:
        logger.error(f"Get relay health failed: {e}")
        return {"health": {}, "error": str(e)}


# ============================================================
# 诊断工具
# ============================================================

def run_diagnose() -> Dict[str, Any]:
    """
    运行系统诊断

    Returns:
        {"diagnose": Dict}
    """
    try:
        butler = _get_butler()
        result = butler.diagnose()
        return result
    except Exception as e:
        logger.error(f"Run diagnose failed: {e}")
        return {"error": str(e)}


def get_public_identity() -> Dict[str, Any]:
    """
    获取公共身份信息（用于设备发现）

    Returns:
        {"device_id": str, "public_key": str}
    """
    try:
        vault = _get_vault()
        identity = vault.export_public_identity()
        return identity
    except Exception as e:
        logger.error(f"Get public identity failed: {e}")
        return {"error": str(e)}


# ============================================================
# 用户画像工具
# ============================================================

def get_user_profile() -> Dict[str, Any]:
    """
    获取用户画像

    Returns:
        {"profile": Dict}
    """
    try:
        butler = _get_butler()
        profile = butler.get_user_profile()
        return {"profile": profile}
    except Exception as e:
        logger.error(f"Get user profile failed: {e}")
        return {"profile": {}, "error": str(e)}


def update_user_profile(updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新用户画像

    Args:
        updates: 要更新的字段

    Returns:
        {"success": bool}
    """
    try:
        butler = _get_butler()
        butler.update_user_profile(updates)
        return {"success": True}
    except Exception as e:
        logger.error(f"Update user profile failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================================
# 快照管理工具
# ============================================================

def create_snapshot(message: str = "") -> Dict[str, Any]:
    """
    创建快照

    Args:
        message: 快照消息

    Returns:
        {"success": bool, "snapshot_hash": str}
    """
    try:
        butler = _get_butler()
        result = butler.create_snapshot(message)
        return result
    except Exception as e:
        logger.error(f"Create snapshot failed: {e}")
        return {"success": False, "error": str(e)}


def list_snapshots() -> Dict[str, Any]:
    """
    列出快照

    Returns:
        {"snapshots": List}
    """
    try:
        butler = _get_butler()
        snapshots = butler.list_snapshots()
        return {"snapshots": snapshots, "count": len(snapshots)}
    except Exception as e:
        logger.error(f"List snapshots failed: {e}")
        return {"snapshots": [], "error": str(e)}


def restore_snapshot(snapshot_hash: str) -> Dict[str, Any]:
    """
    恢复快照

    Args:
        snapshot_hash: 快照哈希

    Returns:
        {"success": bool}
    """
    try:
        butler = _get_butler()
        result = butler.restore_snapshot(snapshot_hash)
        return result
    except Exception as e:
        logger.error(f"Restore snapshot failed: {e}")
        return {"success": False, "error": str(e)}