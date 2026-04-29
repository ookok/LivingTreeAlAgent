"""
Consistency - 一致性保证
========================

功能：
- 写操作复制
- 读时修复
- 冲突解决策略

Author: LivingTreeAI Community
"""

import asyncio
import time
import json
import hashlib
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Any, List, Dict, Set
from enum import Enum
from collections import defaultdict


class ConsistencyLevel(Enum):
    """一致性级别"""
    STRONG = "strong"       # 强一致：写入多数节点
    QUORUM = "quorum"      # Quorum：写入N/2+1节点
    EVENTUAL = "eventual"  # 最终一致：异步复制
    LOCAL = "local"       # 本地写入


@dataclass
class WriteOperation:
    """写操作"""
    operation_id: str
    key: str
    value: Any
    timestamp: float
    node_id: str
    version: int
    consistency: ConsistencyLevel
    replicas: List[str] = field(default_factory=list)
    acks: Set[str] = field(default_factory=set)
    completed: bool = False


class ConflictResolver:
    """
    冲突解决策略

    支持策略：
    - latest-wins: 最新时间戳获胜
    - reputation-based: 基于节点声誉
    - majority-wins: 多数值获胜
    - manual: 标记冲突待手动解决
    """

    def __init__(self, get_reputation_func: Optional[Callable[[str], float]] = None):
        self.policy = "latest-wins"
        self._get_reputation = get_reputation_func or (lambda node_id: 1.0)

    def set_policy(self, policy: str):
        """设置冲突解决策略"""
        self.policy = policy

    def resolve(self, versions: List[dict]) -> dict:
        """
        解决数据冲突

        Args:
            versions: 多个版本的列表，每项包含 {value, timestamp, node_id}

        Returns:
            解决后的值
        """
        if len(versions) <= 1:
            return versions[0] if versions else {}

        if self.policy == "latest-wins":
            return self._resolve_latest(versions)
        elif self.policy == "reputation-based":
            return self._resolve_reputation(versions)
        elif self.policy == "majority-wins":
            return self._resolve_majority(versions)
        else:
            return self._mark_conflict(versions)

    def _resolve_latest(self, versions: List[dict]) -> dict:
        """最新时间戳获胜"""
        return max(versions, key=lambda v: v.get("timestamp", 0))

    def _resolve_reputation(self, versions: List[dict]) -> dict:
        """基于节点声誉"""
        scored = []
        for v in versions:
            reputation = self._get_reputation(v.get("node_id", ""))
            scored.append((reputation, v))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def _resolve_majority(self, versions: List[dict]) -> dict:
        """多数值获胜"""
        value_counts: Dict[str, int] = defaultdict(int)
        for v in versions:
            # 使用值的哈希作为键
            value_key = json.dumps(v.get("value"), sort_keys=True, default=str)
            value_counts[value_key] += 1

        # 找最多
        max_key = max(value_counts.items(), key=lambda x: x[1])[0]

        # 返回对应版本
        for v in versions:
            value_key = json.dumps(v.get("value"), sort_keys=True, default=str)
            if value_key == max_key:
                return v

        return versions[0]

    def _mark_conflict(self, versions: List[dict]) -> dict:
        """标记冲突"""
        return {
            "_conflict": True,
            "versions": versions,
            "timestamp": time.time(),
        }


class ConsistencyModel:
    """
    一致性模型

    功能：
    - 复制写入
    - 读时修复
    - 冲突检测与解决
    """

    def __init__(
        self,
        node_id: str,
        get_replicas_func: Optional[Callable[[str], List[str]]] = None,
        write_func: Optional[Callable[[str, str, Any], Awaitable]] = None,
        read_func: Optional[Callable[[str, str], Awaitable[Any]]] = None,
    ):
        self.node_id = node_id

        # 复制因子
        self.replication_factor = 3

        # 函数
        self._get_replicas = get_replicas_func or (lambda key: [])
        self._write_func = write_func or (lambda k, v, n: None)
        self._read_func = read_func or (lambda k, n: None)

        # 写操作日志
        self.write_log: List[WriteOperation] = []

        # 待修复队列
        self.repair_queue: asyncio.Queue = asyncio.Queue()

        # 配置
        self.read_repair = True  # 读时修复
        self.write_ack_timeout = 5.0  # 写确认超时

        # 冲突解决
        self.conflict_resolver = ConflictResolver()

    # ========== 写入操作 ==========

    async def replicate_write(
        self,
        key: str,
        value: Any,
        consistency: ConsistencyLevel = ConsistencyLevel.QUORUM,
    ) -> bool:
        """
        复制写入

        Args:
            key: 数据键
            value: 数据值
            consistency: 一致性级别

        Returns:
            是否成功
        """
        # 获取副本节点
        replicas = self._get_replicas(key)

        # 计算需要的确认数
        if consistency == ConsistencyLevel.STRONG:
            required_acks = len(replicas)
        elif consistency == ConsistencyLevel.QUORUM:
            required_acks = (len(replicas) // 2) + 1 if replicas else 1
        else:  # EVENTUAL or LOCAL
            required_acks = 1 if self.node_id in replicas else 0

        # 创建写操作
        operation = WriteOperation(
            operation_id=self._generate_operation_id(),
            key=key,
            value=value,
            timestamp=time.time(),
            node_id=self.node_id,
            version=self._generate_version(key, value),
            consistency=consistency,
            replicas=replicas,
        )

        # 记录到日志
        self.write_log.append(operation)

        # 并行写入
        write_tasks = []
        for replica in replicas:
            task = asyncio.create_task(
                self._write_to_replica(replica, operation)
            )
            write_tasks.append(task)

        # 等待确认
        if write_tasks:
            results = await asyncio.gather(*write_tasks, return_exceptions=True)
            operation.acks = {
                replicas[i]
                for i, r in enumerate(results)
                if r is True
            }

        operation.completed = len(operation.acks) >= required_acks

        return operation.completed

    async def _write_to_replica(self, replica: str, operation: WriteOperation) -> bool:
        """写入单个副本"""
        try:
            await asyncio.wait_for(
                self._write_func(replica, operation.key, operation.value),
                timeout=self.write_ack_timeout,
            )
            return True
        except Exception:
            return False

    # ========== 读取操作 ==========

    async def read_with_repair(
        self,
        key: str,
        consistency: ConsistencyLevel = ConsistencyLevel.QUORUM,
    ) -> Optional[Any]:
        """
        读取并修复

        Args:
            key: 数据键
            consistency: 一致性级别

        Returns:
            读取的值
        """
        replicas = self._get_replicas(key)

        # 确定读取的副本数
        if consistency == ConsistencyLevel.STRONG:
            read_from = replicas
        elif consistency == ConsistencyLevel.QUORUM:
            read_from = replicas[:((len(replicas) // 2) + 1) if len(replicas) > 2 else 1]
        else:
            read_from = [self.node_id] if self.node_id in replicas else (replicas[:1] if replicas else [])

        # 并行读取
        read_tasks = [
            self._read_from_replica(replica, key)
            for replica in read_from
        ]

        results = await asyncio.gather(*read_tasks, return_exceptions=True)
        valid_results = [r for r in results if not isinstance(r, Exception) and r is not None]

        if not valid_results:
            return None

        # 检查一致性
        if self.read_repair and len(valid_results) > 1:
            unique_values = set(
                json.dumps(v, sort_keys=True, default=str)
                for v in valid_results
            )

            if len(unique_values) > 1:
                # 发现不一致，进行修复
                versions = [
                    {"value": v, "timestamp": getattr(v, "_timestamp", 0), "node_id": r}
                    for r, v in zip(read_from, valid_results)
                ]
                consensus = self.conflict_resolver.resolve(versions)

                if "_conflict" not in consensus:
                    # 异步修复
                    asyncio.create_task(
                        self._repair_replicas(key, consensus["value"])
                    )
                    return consensus["value"]

        # 返回第一个结果
        return valid_results[0]

    async def _read_from_replica(self, replica: str, key: str) -> Optional[Any]:
        """从单个副本读取"""
        try:
            return await asyncio.wait_for(
                self._read_func(replica, key),
                timeout=self.write_ack_timeout,
            )
        except Exception:
            return None

    async def _repair_replicas(self, key: str, value: Any):
        """修复副本"""
        replicas = self._get_replicas(key)
        repair_tasks = [
            self._write_func(replica, key, value)
            for replica in replicas
        ]
        await asyncio.gather(*repair_tasks, return_exceptions=True)

    # ========== 版本号 ==========

    def _generate_operation_id(self) -> str:
        """生成操作ID"""
        data = f"{self.node_id}:{time.time()}:{id(self)}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _generate_version(self, key: str, value: Any) -> int:
        """生成版本号"""
        return int(time.time() * 1000)

    # ========== 冲突解决 ==========

    def resolve_conflict(self, versions: List[dict]) -> dict:
        """解决冲突"""
        return self.conflict_resolver.resolve(versions)

    def set_conflict_policy(self, policy: str):
        """设置冲突策略"""
        self.conflict_resolver.set_policy(policy)

    # ========== 统计 ==========

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "pending_writes": sum(1 for w in self.write_log if not w.completed),
            "completed_writes": sum(1 for w in self.write_log if w.completed),
            "conflict_policy": self.conflict_resolver.policy,
            "read_repair_enabled": self.read_repair,
        }


# 全局单例
_consistency_instance: Optional[ConsistencyModel] = None


def get_consistency_model(node_id: str = "local") -> ConsistencyModel:
    """获取一致性模型单例"""
    global _consistency_instance
    if _consistency_instance is None:
        _consistency_instance = ConsistencyModel(node_id)
    return _consistency_instance