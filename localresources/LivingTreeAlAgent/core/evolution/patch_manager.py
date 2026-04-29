# patch_manager.py — 自我修补系统

import json
import time
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime
from dataclasses import asdict

from .models import (
    PatchDoc, PatchAction, PatchStatus,
    ClientConfig, generate_client_id,
)


class PatchManager:
    """
    自我修补管理器

    功能：
    1. 补丁生成与存储
    2. 白名单验证
    3. 运行时补丁加载
    4. 补丁状态管理
    """

    def __init__(
        self,
        data_dir: Path = None,
        config: ClientConfig = None,
    ):
        """
        初始化补丁管理器

        Args:
            data_dir: 数据存储目录
            config: 客户端配置
        """
        self._data_dir = data_dir or self._default_data_dir()
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._config = config or ClientConfig()
        if not self._config.client_id:
            self._config.client_id = generate_client_id()

        # 存储文件
        self._patches_file = self._data_dir / "patches.json"
        self._applied_file = self._data_dir / "applied_patches.json"
        self._config_file = self._data_dir / "config.json"

        # 内存缓存
        self._patches: Dict[str, PatchDoc] = {}
        self._applied: Dict[str, PatchDoc] = {}
        self._runtime_overrides: Dict[str, Any] = {}  # 运行时覆盖值

        # 加载数据
        self._load_patches()
        self._load_applied()
        self._load_config()

        # 白名单规则
        self._whitelist = set(self._config.whitelist_modules)
        self._blacklist = set(self._config.blacklist_modules)

    def _default_data_dir(self) -> Path:
        """默认数据目录"""
        return Path.home() / ".hermes-desktop" / "evolution" / "patches"

    def _load_patches(self):
        """加载补丁列表"""
        if self._patches_file.exists():
            try:
                with open(self._patches_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        patch = PatchDoc.from_dict(item)
                        self._patches[patch.id] = patch
            except (json.JSONDecodeError, KeyError):
                pass

    def _load_applied(self):
        """加载已应用补丁"""
        if self._applied_file.exists():
            try:
                with open(self._applied_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        patch = PatchDoc.from_dict(item)
                        self._applied[patch.id] = patch
                        # 同步到运行时覆盖
                        self._runtime_overrides[patch.module] = patch.new_value
            except (json.JSONDecodeError, KeyError):
                pass

    def _load_config(self):
        """加载配置"""
        if self._config_file.exists():
            try:
                with open(self._config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._config = ClientConfig.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_patches(self):
        """保存补丁列表"""
        data = [p.to_dict() for p in self._patches.values()]
        with open(self._patches_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_applied(self):
        """保存已应用补丁"""
        data = [p.to_dict() for p in self._applied.values()]
        with open(self._applied_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_config(self):
        """保存配置"""
        with open(self._config_file, "w", encoding="utf-8") as f:
            json.dump(self._config.to_dict(), f, ensure_ascii=False, indent=2)

    def _generate_patch_id(self, module: str, action: str, new_value: Any) -> str:
        """生成补丁ID"""
        raw = f"{module}:{action}:{str(new_value)}:{int(time.time())}"
        return hashlib.sha256(raw.encode()).hexdigest()[:8]

    def _sign_patch(self, patch_id: str, module: str, new_value: Any) -> str:
        """签名补丁"""
        raw = f"{patch_id}:{module}:{str(new_value)}:hermes_evo"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def is_module_allowed(self, module: str) -> bool:
        """
        检查模块是否在白名单中

        Args:
            module: 模块名

        Returns:
            bool: 是否允许
        """
        # 黑名单优先
        for black in self._blacklist:
            if black in module.lower():
                return False

        # 白名单检查
        for white in self._whitelist:
            if white in module.lower():
                return True

        return False

    def create_patch(
        self,
        module: str,
        action: PatchAction,
        old_value: Any,
        new_value: Any,
        reason: str,
    ) -> Optional[PatchDoc]:
        """
        创建补丁

        Args:
            module: 模块名
            action: 动作类型
            old_value: 旧值
            new_value: 新值
            reason: 生成原因

        Returns:
            PatchDoc: 补丁文档，或None（如果被拦截）
        """
        # 白名单检查
        if not self.is_module_allowed(module):
            return None

        # 生成补丁
        timestamp = int(time.time())
        patch_id = self._generate_patch_id(module, action.value, new_value)
        signature = self._sign_patch(patch_id, module, new_value)

        patch = PatchDoc(
            id=patch_id,
            module=module,
            action=action,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            signature=signature,
            timestamp=timestamp,
            client_id=self._config.client_id,
            status=PatchStatus.PENDING,
        )

        self._patches[patch_id] = patch
        self._save_patches()

        return patch

    def apply_patch(self, patch_id: str) -> bool:
        """
        应用补丁

        Args:
            patch_id: 补丁ID

        Returns:
            bool: 是否成功
        """
        patch = self._patches.get(patch_id)
        if patch is None:
            return False

        # 签名验证
        expected_sig = self._sign_patch(patch.id, patch.module, patch.new_value)
        if patch.signature != expected_sig:
            return False

        # 更新状态
        patch.status = PatchStatus.APPLIED
        patch.applied_at = int(time.time())

        # 同步到已应用
        self._applied[patch_id] = patch

        # 同步到运行时覆盖
        self._runtime_overrides[patch.module] = patch.new_value

        self._save_patches()
        self._save_applied()

        return True

    def reject_patch(self, patch_id: str) -> bool:
        """拒绝补丁"""
        patch = self._patches.get(patch_id)
        if patch is None:
            return False

        patch.status = PatchStatus.REJECTED
        self._save_patches()

        return True

    def get_runtime_value(self, module: str, default: Any = None) -> Any:
        """
        获取运行时覆盖值

        Args:
            module: 模块名
            default: 默认值

        Returns:
            Any: 覆盖值或默认值
        """
        return self._runtime_overrides.get(module, default)

    def set_runtime_value(self, module: str, value: Any):
        """
        设置运行时覆盖值（手动干预）

        Args:
            module: 模块名
            value: 新值
        """
        self._runtime_overrides[module] = value

    def get_pending_patches(self) -> List[PatchDoc]:
        """获取待处理补丁"""
        return [
            p for p in self._patches.values()
            if p.status == PatchStatus.PENDING
        ]

    def get_applied_patches(self) -> List[PatchDoc]:
        """获取已应用补丁"""
        return list(self._applied.values())

    def get_all_patches(self) -> List[PatchDoc]:
        """获取所有补丁"""
        return list(self._patches.values())

    def auto_apply_all(self) -> int:
        """
        自动应用所有待处理补丁

        Returns:
            int: 成功应用数量
        """
        if not self._config.auto_patch:
            return 0

        count = 0
        for patch in self.get_pending_patches():
            if self.apply_patch(patch.id):
                count += 1

        return count

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        all_patches = list(self._patches.values())
        return {
            "total_patches": len(all_patches),
            "pending": sum(1 for p in all_patches if p.status == PatchStatus.PENDING),
            "applied": sum(1 for p in all_patches if p.status == PatchStatus.APPLIED),
            "rejected": sum(1 for p in all_patches if p.status == PatchStatus.REJECTED),
            "runtime_overrides": len(self._runtime_overrides),
        }

    def update_config(self, **kwargs):
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
        self._save_config()

    def get_config(self) -> ClientConfig:
        """获取配置"""
        return self._config


# 全局单例
_patch_manager_instance: Optional[PatchManager] = None


def get_patch_manager() -> PatchManager:
    """获取补丁管理器全局实例"""
    global _patch_manager_instance
    if _patch_manager_instance is None:
        _patch_manager_instance = PatchManager()
    return _patch_manager_instance


# ============ 终极版新增：P2P 广播功能 ============

import socket
import struct
import threading
from typing import Set, Callable, Optional
from dataclasses import dataclass


@dataclass
class P2PMessage:
    """P2P消息结构"""
    msg_type: str              # patch_broadcast / patch_request / ack
    payload: Dict[str, Any]    # 消息内容
    sender_id: str            # 发送者ID
    ttl: int = 3              # 生存时间
    timestamp: int = 0        # 时间戳

    def to_bytes(self) -> bytes:
        data = json.dumps({
            "msg_type": self.msg_type,
            "payload": self.payload,
            "sender_id": self.sender_id,
            "ttl": self.ttl,
            "timestamp": self.timestamp or int(time.time()),
        }, ensure_ascii=False)
        return data.encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> "P2PMessage":
        obj = json.loads(data.decode("utf-8"))
        return cls(
            msg_type=obj["msg_type"],
            payload=obj["payload"],
            sender_id=obj["sender_id"],
            ttl=obj.get("ttl", 3),
            timestamp=obj.get("timestamp", 0),
        )


class P2PBroadcastService:
    """
    P2P 广播服务

    功能：
    1. 补丁广播（带 TTL 衰减）
    2. 补丁请求（邻居验证转发）
    3. ACK 确认机制
    """

    BROADCAST_PORT = 18765
    BUFFER_SIZE = 4096

    def __init__(self, patch_manager: PatchManager):
        self._pm = patch_manager
        self._running = False
        self._socket: Optional[socket.socket] = None
        self._neighbors: Set[str] = set()  # 邻居节点ID
        self._lock = threading.Lock()
        self._callbacks: Dict[str, Callable] = {}  # 消息回调

    def start(self, bind_interface: str = "0.0.0.0") -> bool:
        """
        启动 P2P 服务

        Args:
            bind_interface: 绑定接口

        Returns:
            bool: 是否成功
        """
        if self._running:
            return True

        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.settimeout(1.0)  # 非阻塞超时
            self._socket.bind((bind_interface, self.BROADCAST_PORT))
            self._running = True

            # 启动接收线程
            self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
            self._recv_thread.start()

            return True
        except (OSError, PermissionError):
            return False

    def stop(self):
        """停止 P2P 服务"""
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    def _recv_loop(self):
        """接收循环"""
        while self._running:
            try:
                data, addr = self._socket.recvfrom(self.BUFFER_SIZE)
                msg = P2PMessage.from_bytes(data)
                self._handle_message(msg, addr)
            except socket.timeout:
                continue
            except Exception:
                continue

    def _handle_message(self, msg: P2PMessage, addr):
        """处理接收到的消息"""
        # 跳过自己发送的消息
        if msg.sender_id == self._pm.get_config().client_id:
            return

        # TTL 衰减
        if msg.ttl <= 0:
            return

        # 处理不同类型消息
        if msg.msg_type == "patch_broadcast":
            self._handle_patch_broadcast(msg)
            # 继续广播给其他邻居
            self._forward_broadcast(msg)
        elif msg.msg_type == "patch_request":
            self._handle_patch_request(msg, addr)
        elif msg.msg_type == "ack":
            self._handle_ack(msg)

    def _handle_patch_broadcast(self, msg: P2PMessage):
        """处理补丁广播"""
        payload = msg.payload
        patch_data = payload.get("patch", {})
        if not patch_data:
            return

        # 验证补丁签名
        patch = PatchDoc.from_dict(patch_data)
        expected_sig = self._pm._sign_patch(patch.id, patch.module, patch.new_value)
        if patch.signature != expected_sig:
            return  # 签名不匹配，丢弃

        # 记录邻居
        with self._lock:
            self._neighbors.add(msg.sender_id)

        # 如果模块在白名单，自动应用
        if self._pm.is_module_allowed(patch.module):
            self._pm.apply_patch(patch.id)

        # 触发回调
        callback = self._callbacks.get("on_patch_received")
        if callback:
            callback(patch)

    def _handle_patch_request(self, msg: P2PMessage, addr):
        """处理补丁请求"""
        patch_id = msg.payload.get("patch_id")
        if not patch_id:
            return

        patch = self._pm._patches.get(patch_id) or self._pm._applied.get(patch_id)
        if not patch:
            return

        # 发送 ACK
        ack = P2PMessage(
            msg_type="ack",
            payload={"patch": patch.to_dict()},
            sender_id=self._pm.get_config().client_id,
            timestamp=int(time.time()),
        )
        try:
            self._socket.sendto(ack.to_bytes(), addr)
        except Exception:
            pass

    def _handle_ack(self, msg: P2PMessage):
        """处理 ACK"""
        patch_data = msg.payload.get("patch", {})
        if not patch_data:
            return

        callback = self._callbacks.get("on_ack_received")
        if callback:
            callback(PatchDoc.from_dict(patch_data))

    def _forward_broadcast(self, msg: P2PMessage):
        """转发广播"""
        # TTL 衰减
        forwarded = P2PMessage(
            msg_type=msg.msg_type,
            payload=msg.payload,
            sender_id=msg.sender_id,  # 保持原始发送者
            ttl=msg.ttl - 1,
            timestamp=msg.timestamp,
        )
        try:
            self._socket.sendto(forwarded.to_bytes(), ("<broadcast>", self.BROADCAST_PORT))
        except Exception:
            pass

    def broadcast_patch(self, patch: PatchDoc) -> bool:
        """
        广播补丁

        Args:
            patch: 补丁文档

        Returns:
            bool: 是否成功
        """
        if not self._running:
            return False

        msg = P2PMessage(
            msg_type="patch_broadcast",
            payload={"patch": patch.to_dict()},
            sender_id=self._pm.get_config().client_id,
            ttl=3,
            timestamp=int(time.time()),
        )
        try:
            self._socket.sendto(msg.to_bytes(), ("<broadcast>", self.BROADCAST_PORT))
            return True
        except Exception:
            return False

    def request_patch(self, patch_id: str, target_addr: tuple) -> bool:
        """
        请求特定补丁

        Args:
            patch_id: 补丁ID
            target_addr: 目标地址

        Returns:
            bool: 是否成功
        """
        if not self._running:
            return False

        msg = P2PMessage(
            msg_type="patch_request",
            payload={"patch_id": patch_id},
            sender_id=self._pm.get_config().client_id,
            timestamp=int(time.time()),
        )
        try:
            self._socket.sendto(msg.to_bytes(), target_addr)
            return True
        except Exception:
            return False

    def register_callback(self, event: str, callback: Callable):
        """
        注册消息回调

        Args:
            event: 事件类型 (on_patch_received / on_ack_received)
            callback: 回调函数
        """
        self._callbacks[event] = callback

    def get_neighbors(self) -> Set[str]:
        """获取邻居节点"""
        with self._lock:
            return set(self._neighbors)

    def is_running(self) -> bool:
        """检查是否运行"""
        return self._running
