"""
Credit Sync Client - 积分同步客户端
====================================

用于客户端和节点同步积分数据

策略：
1. 写操作优先本地，然后异步同步到中继服务器
2. 读操作先读本地缓存，然后从服务器同步最新
3. 冲突通过版本号 + 时间戳解决
"""

import os
import json
import time
import uuid
import asyncio
import random
from typing import Optional, Dict, Any, Tuple, List
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field
import httpx


# ============ 同步状态枚举 ============

class SyncStatus(str, Enum):
    """同步状态"""
    SYNCED = "synced"           # 已同步
    PENDING = "pending"         # 待同步
    SYNCING = "syncing"         # 同步中
    CONFLICT = "conflict"       # 冲突
    ERROR = "error"             # 错误


# ============ 积分缓存模型 ============

@dataclass
class LocalCreditCache:
    """本地积分缓存"""
    user_id: str
    balance: int
    version: int
    last_synced_at: int
    last_modified_at: int
    sync_status: SyncStatus
    pending_operations: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "balance": self.balance,
            "version": self.version,
            "last_synced_at": self.last_synced_at,
            "last_modified_at": self.last_modified_at,
            "sync_status": self.sync_status.value if isinstance(self.sync_status, SyncStatus) else self.sync_status,
            "pending_operations": self.pending_operations,
        }


@dataclass
class CreditOperation:
    """积分操作记录"""
    op_id: str
    op_type: str                    # recharge/consume/daily_bonus/...
    amount: int
    balance_after: int
    timestamp: int
    version: int
    source: str                     # local/remote
    synced: bool = False


# ============ 积分同步客户端 ============

class CreditSyncClient:
    """
    积分同步客户端

    用于：
    1. 客户端本地缓存积分数据
    2. 与中继服务器同步积分
    3. 处理离线操作
    4. 解决冲突
    """

    def __init__(
        self,
        user_id: str,
        cache_dir: Optional[Path] = None,
        relay_url: str = "http://localhost:8766"
    ):
        self.user_id = user_id
        self.relay_url = relay_url.rstrip("/")

        # 缓存目录
        if cache_dir is None:
            cache_dir = Path.home() / ".hermes-desktop" / "credit_cache"
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 缓存文件
        self.cache_file = cache_dir / f"{user_id}_credit.json"
        self.operations_file = cache_dir / f"{user_id}_operations.json"

        # 加载缓存
        self.cache = self._load_cache()

        # 同步锁
        self._sync_lock = asyncio.Lock()

        # 同步间隔（秒）
        self.sync_interval = 30  # 30秒同步一次

        # 最后同步时间
        self.last_sync_time = 0

    def _load_cache(self) -> Optional[LocalCreditCache]:
        """加载本地缓存"""
        if self.cache_file.exists():
            try:
                data = json.loads(self.cache_file.read_text(encoding="utf-8"))
                data["sync_status"] = SyncStatus(data.get("sync_status", "synced"))
                return LocalCreditCache(**data)
            except Exception:
                return None
        return None

    def _save_cache(self):
        """保存本地缓存"""
        if self.cache:
            self.cache_file.write_text(json.dumps(self.cache.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_operations(self) -> List[CreditOperation]:
        """加载操作记录"""
        if self.operations_file.exists():
            try:
                data = json.loads(self.operations_file.read_text(encoding="utf-8"))
                return [CreditOperation(**op) for op in data]
            except Exception:
                return []
        return []

    def _save_operations(self, operations: List[CreditOperation]):
        """保存操作记录"""
        data = [
            {
                "op_id": op.op_id,
                "op_type": op.op_type,
                "amount": op.amount,
                "balance_after": op.balance_after,
                "timestamp": op.timestamp,
                "version": op.version,
                "source": op.source,
                "synced": op.synced,
            }
            for op in operations
        ]
        self.operations_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ============ 本地操作 ============

    def get_local_balance(self) -> Tuple[int, int]:
        """
        获取本地余额

        Returns:
            (balance, version)
        """
        if self.cache:
            return self.cache.balance, self.cache.version
        return 0, 0

    def local_recharge(self, amount: int, op_type: str = "local_recharge") -> Tuple[bool, int]:
        """
        本地充值（乐观更新）

        Returns:
            (是否成功, 新的余额)
        """
        if not self.cache:
            # 初始化缓存
            self.cache = LocalCreditCache(
                user_id=self.user_id,
                balance=amount,
                version=1,
                last_synced_at=0,
                last_modified_at=int(time.time()),
                sync_status=SyncStatus.PENDING,
            )
        else:
            self.cache.balance += amount
            self.cache.version += 1
            self.cache.last_modified_at = int(time.time())
            self.cache.sync_status = SyncStatus.PENDING

        # 记录操作
        self._add_operation(
            op_type=op_type,
            amount=amount,
            balance_after=self.cache.balance,
        )

        self._save_cache()
        return True, self.cache.balance

    def local_consume(self, amount: int, op_type: str = "local_consume") -> Tuple[bool, str]:
        """
        本地消费（乐观更新）

        Returns:
            (是否成功, 错误消息或新余额)
        """
        if not self.cache:
            return False, "本地缓存不存在"

        if self.cache.balance < amount:
            return False, f"余额不足（{self.cache.balance} < {amount}）"

        self.cache.balance -= amount
        self.cache.version += 1
        self.cache.last_modified_at = int(time.time())
        self.cache.sync_status = SyncStatus.PENDING

        # 记录操作
        self._add_operation(
            op_type=op_type,
            amount=-amount,
            balance_after=self.cache.balance,
        )

        self._save_cache()
        return True, str(self.cache.balance)

    def _add_operation(self, op_type: str, amount: int, balance_after: int):
        """添加操作记录"""
        operations = self._load_operations()

        op = CreditOperation(
            op_id=f"op_{uuid.uuid4().hex[:16]}",
            op_type=op_type,
            amount=amount,
            balance_after=balance_after,
            timestamp=int(time.time()),
            version=self.cache.version,
            source="local",
            synced=False,
        )

        operations.append(op)

        # 只保留最近100条操作
        operations = operations[-100:]

        self._save_operations(operations)

    # ============ 同步操作 ============

    async def sync_with_server(self) -> Tuple[bool, str]:
        """
        与服务器同步积分数据

        流程：
        1. 先推送本地待同步操作
        2. 再拉取服务器最新数据
        3. 处理冲突

        Returns:
            (是否成功, 消息)
        """
        async with self._sync_lock:
            if not self.relay_url:
                return False, "未配置中继服务器地址"

            # 1. 推送本地操作到服务器
            await self._push_local_operations()

            # 2. 从服务器拉取最新数据
            success, message = await self._pull_remote_data()

            if success:
                self.last_sync_time = int(time.time())
                if self.cache:
                    self.cache.last_synced_at = self.last_sync_time
                    self.cache.sync_status = SyncStatus.SYNCED
                    self._save_cache()

            return success, message

    async def _push_local_operations(self) -> bool:
        """推送本地待同步操作到服务器"""
        operations = self._load_operations()
        unsynced = [op for op in operations if not op.synced]

        if not unsynced:
            return True

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.relay_url}/api/credit/sync/push",
                    json={
                        "user_id": self.user_id,
                        "operations": [
                            {
                                "op_id": op.op_id,
                                "op_type": op.op_type,
                                "amount": op.amount,
                                "balance_after": op.balance_after,
                                "timestamp": op.timestamp,
                                "version": op.version,
                            }
                            for op in unsynced
                        ],
                        "client_version": self.cache.version if self.cache else 0,
                    }
                )

                if response.status_code == 200:
                    # 标记为已同步
                    for op in unsynced:
                        op.synced = True
                    self._save_operations(operations)
                    return True
        except Exception:
            pass

        return False

    async def _pull_remote_data(self) -> Tuple[bool, str]:
        """从服务器拉取最新数据"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.relay_url}/api/credit/sync/pull",
                    params={
                        "user_id": self.user_id,
                        "client_version": self.cache.version if self.cache else 0,
                    }
                )

                if response.status_code == 200:
                    data = response.json()

                    if data.get("success"):
                        remote_data = data.get("data", {})

                        # 处理冲突或更新
                        if self.cache:
                            local_version = self.cache.version
                            remote_version = remote_data.get("version", 0)

                            if remote_version > local_version:
                                # 服务器版本更新，直接采用
                                self.cache.balance = remote_data.get("balance", self.cache.balance)
                                self.cache.version = remote_version
                                self.cache.last_modified_at = remote_data.get("last_modified_at", int(time.time()))
                                self.cache.sync_status = SyncStatus.SYNCED
                                self._save_cache()
                                return True, "同步成功（服务器更新）"
                            elif remote_version == local_version:
                                # 版本相同，可能冲突
                                return True, "同步成功（已是最新）"
                            else:
                                # 本地版本更新，应该先推送
                                return False, "本地有未同步操作"
                        else:
                            # 首次同步
                            self.cache = LocalCreditCache(
                                user_id=self.user_id,
                                balance=remote_data.get("balance", 0),
                                version=remote_data.get("version", 1),
                                last_synced_at=int(time.time()),
                                last_modified_at=remote_data.get("last_modified_at", int(time.time())),
                                sync_status=SyncStatus.SYNCED,
                            )
                            self._save_cache()
                            return True, "首次同步完成"

                return False, "服务器响应异常"
        except Exception as e:
            return False, f"同步失败: {str(e)}"

    # ============ 定时同步 ============

    async def start_periodic_sync(self, interval: Optional[int] = None):
        """启动定时同步"""
        if interval:
            self.sync_interval = interval

        while True:
            await asyncio.sleep(self.sync_interval)
            await self.sync_with_server()

    # ============ 强制同步 ============

    async def force_sync(self) -> Tuple[bool, str]:
        """强制同步（用于用户主动触发）"""
        # 先推送本地操作
        await self._push_local_operations()

        # 再拉取远程数据
        success, message = await self._pull_remote_data()

        if success and self.cache:
            self.last_sync_time = int(time.time())
            self.cache.last_synced_at = self.last_sync_time
            self.cache.sync_status = SyncStatus.SYNCED
            self._save_cache()

        return success, message


# ============ 客户端积分操作接口 ============

class CreditClient:
    """
    客户端积分操作接口

    提供给客户端应用使用的简单接口
    """

    def __init__(
        self,
        user_id: str,
        relay_url: str = "http://localhost:8766",
        cache_dir: Optional[Path] = None
    ):
        self.user_id = user_id
        self.sync_client = CreditSyncClient(user_id, cache_dir, relay_url)

    def get_balance(self) -> int:
        """获取余额（优先本地）"""
        balance, _ = self.sync_client.get_local_balance()
        return balance

    def recharge(self, amount: int) -> Tuple[bool, str]:
        """充值（本地乐观更新）"""
        return self.sync_client.local_recharge(amount, "recharge")

    def consume(self, amount: int) -> Tuple[bool, str]:
        """消费（本地乐观更新）"""
        return self.sync_client.local_consume(amount, "consume")

    async def sync(self) -> Tuple[bool, str]:
        """同步到服务器"""
        return await self.sync_client.sync_with_server()

    async def force_sync(self) -> Tuple[bool, str]:
        """强制同步"""
        return await self.sync_client.force_sync()

    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        cache = self.sync_client.cache
        if not cache:
            return {"status": "no_cache"}

        return {
            "status": cache.sync_status.value,
            "balance": cache.balance,
            "version": cache.version,
            "last_synced_at": cache.last_synced_at,
            "pending_ops": len([op for op in self.sync_client._load_operations() if not op.synced]),
        }
