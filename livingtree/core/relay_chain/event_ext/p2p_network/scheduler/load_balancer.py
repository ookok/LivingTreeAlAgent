"""
负载均衡器 - Load Balancer

核心功能：
1. 收集各节点的负载信息
2. 根据负载选择最佳节点
3. 支持多种负载均衡策略

负载指标：
- CPU 使用率
- 内存使用率
- 网络带宽
- 任务队列长度
- 响应时间

负载均衡策略：
1. LeastLoad：选择负载最低的节点
2. RoundRobin：轮询
3. Random：随机
4. WeightedLoad：加权负载

使用示例：
```python
lb = LoadBalancer(node_id="node-001")

# 上报本地负载
lb.report_local_load(cpu=0.3, mem=0.5, queue=2)

# 更新远程节点负载
lb.update_node_load("node-002", cpu=0.4, mem=0.6)

# 选择最佳节点
best = lb.select_best_node()
if best:
    print(f"最佳节点: {best['node_id']}, 负载: {best['load']}")

# 选择满足要求的节点
gpu_node = lb.select_best_node(capability="gpu")
```
"""

import time
import random
import logging
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from threading import RLock

logger = logging.getLogger(__name__)


class BalanceStrategy(Enum):
    """负载均衡策略"""
    LEAST_LOAD = "least_load"    # 最小负载
    ROUND_ROBIN = "round_robin"  # 轮询
    RANDOM = "random"           # 随机
    WEIGHTED = "weighted"       # 加权


@dataclass
class NodeLoad:
    """节点负载信息"""
    node_id: str
    cpu: float = 0.0       # CPU 使用率 0.0 ~ 1.0
    memory: float = 0.0     # 内存使用率 0.0 ~ 1.0
    queue: int = 0          # 任务队列长度
    response_time: float = 0.0  # 响应时间（毫秒）
    network: float = 0.0   # 网络使用率 0.0 ~ 1.0

    # 综合负载
    load_score: float = 0.0

    # 元数据
    capabilities: List[str] = field(default_factory=list)
    last_update: float = field(default_factory=time.time)

    def compute_load(self) -> float:
        """
        计算综合负载分数

        权重：
        - CPU: 30%
        - Memory: 20%
        - Queue: 25%
        - ResponseTime: 15%
        - Network: 10%
        """
        self.load_score = (
            self.cpu * 0.30 +
            self.memory * 0.20 +
            min(self.queue / 10.0, 1.0) * 0.25 +
            min(self.response_time / 1000.0, 1.0) * 0.15 +
            self.network * 0.10
        )
        return self.load_score

    def is_overloaded(self, threshold: float = 0.9) -> bool:
        """检查是否过载"""
        return self.compute_load() > threshold

    def is_stale(self, timeout: float = 30.0) -> bool:
        """检查负载信息是否过期"""
        return time.time() - self.last_update > timeout


class LoadBalancer:
    """
    负载均衡器

    使用示例：
    ```python
    lb = LoadBalancer(node_id="node-001")

    # 定期更新本地负载
    lb.report_local_load(cpu=0.3, mem=0.5, queue=2)

    # 选择最佳节点执行任务
    best = lb.select_best_node()
    if best:
        await dispatch_task(best["node_id"], task)

    # 选择有 GPU 的节点
    gpu_best = lb.select_best_node(capability="gpu")
    ```
    """

    # 默认负载阈值
    DEFAULT_THRESHOLD = 0.9

    # 负载信息过期时间
    LOAD_EXPIRY = 30.0

    # 最小节点数（用于选举协调者）
    MIN_NODES = 1

    def __init__(
        self,
        node_id: str,
        strategy: BalanceStrategy = BalanceStrategy.LEAST_LOAD,
    ):
        self.node_id = node_id
        self.strategy = strategy
        self._lock = RLock()

        # 节点负载表
        self._loads: Dict[str, NodeLoad] = {}

        # 本地负载
        self._local_load = NodeLoad(node_id=node_id)

        # 轮询索引
        self._round_robin_index = 0

        # 回调
        self.on_load_update: Optional[Callable[[str, NodeLoad], None]] = None

    def report_local_load(
        self,
        cpu: float = None,
        memory: float = None,
        queue: int = None,
        response_time: float = None,
        network: float = None,
    ):
        """
        上报本地负载

        Args:
            cpu: CPU 使用率 0.0 ~ 1.0
            memory: 内存使用率 0.0 ~ 1.0
            queue: 任务队列长度
            response_time: 响应时间（毫秒）
            network: 网络使用率 0.0 ~ 1.0
        """
        with self._lock:
            if cpu is not None:
                self._local_load.cpu = max(0.0, min(1.0, cpu))
            if memory is not None:
                self._local_load.memory = max(0.0, min(1.0, memory))
            if queue is not None:
                self._local_load.queue = max(0, queue)
            if response_time is not None:
                self._local_load.response_time = max(0.0, response_time)
            if network is not None:
                self._local_load.network = max(0.0, min(1.0, network))

            self._local_load.last_update = time.time()
            self._local_load.compute_load()

        logger.debug(
            f"[{self.node_id}] 本地负载: "
            f"cpu={self._local_load.cpu:.2f}, "
            f"mem={self._local_load.memory:.2f}, "
            f"queue={self._local_load.queue}, "
            f"score={self._local_load.load_score:.2f}"
        )

    def update_node_load(self, node_id: str, **kwargs):
        """
        更新远程节点负载

        Args:
            node_id: 节点ID
            **kwargs: 负载指标
        """
        with self._lock:
            if node_id not in self._loads:
                self._loads[node_id] = NodeLoad(node_id=node_id)

            load = self._loads[node_id]

            if "cpu" in kwargs:
                load.cpu = max(0.0, min(1.0, kwargs["cpu"]))
            if "memory" in kwargs:
                load.memory = max(0.0, min(1.0, kwargs["memory"]))
            if "queue" in kwargs:
                load.queue = max(0, kwargs["queue"])
            if "response_time" in kwargs:
                load.response_time = max(0.0, kwargs["response_time"])
            if "network" in kwargs:
                load.network = max(0.0, min(1.0, kwargs["network"]))
            if "capabilities" in kwargs:
                load.capabilities = kwargs["capabilities"]

            load.last_update = time.time()
            load.compute_load()

        logger.debug(
            f"[{self.node_id}] 更新节点 {node_id} 负载: "
            f"score={load.load_score:.2f}"
        )

        if self.on_load_update:
            self.on_load_update(node_id, load)

    def get_node_load(self, node_id: str) -> Optional[NodeLoad]:
        """获取节点负载"""
        with self._lock:
            if node_id == self.node_id:
                return self._local_load
            return self._loads.get(node_id)

    def get_all_loads(self) -> Dict[str, NodeLoad]:
        """获取所有节点负载"""
        with self._lock:
            result = {self.node_id: self._local_load}
            result.update(self._loads)
            return result

    def select_best_node(
        self,
        capability: str = None,
        threshold: float = None,
    ) -> Optional[Dict[str, Any]]:
        """
        选择最佳节点

        Args:
            capability: 需要的 capability（如 "gpu"）
            threshold: 最大负载阈值

        Returns:
            最佳节点信息，如果无可用节点则返回 None
        """
        threshold = threshold or self.DEFAULT_THRESHOLD

        with self._lock:
            # 收集所有可用节点
            candidates = []

            # 添加本地节点
            if not self._local_load.is_stale(self.LOAD_EXPIRY):
                if self._local_load.compute_load() < threshold:
                    candidates.append(self._local_load)

            # 添加远程节点
            for node_id, load in self._loads.items():
                if load.is_stale(self.LOAD_EXPIRY):
                    continue
                if load.is_overloaded(threshold):
                    continue
                if capability and capability not in load.capabilities:
                    continue
                candidates.append(load)

        if not candidates:
            logger.warning(f"[{self.node_id}] 没有可用节点")
            return None

        # 根据策略选择
        if self.strategy == BalanceStrategy.LEAST_LOAD:
            selected = min(candidates, key=lambda l: l.load_score)
        elif self.strategy == BalanceStrategy.ROUND_ROBIN:
            if self._round_robin_index >= len(candidates):
                self._round_robin_index = 0
            selected = candidates[self._round_robin_index]
            self._round_robin_index += 1
        elif self.strategy == BalanceStrategy.RANDOM:
            selected = random.choice(candidates)
        elif self.strategy == BalanceStrategy.WEIGHTED:
            # 加权随机
            weights = [1.0 - l.load_score for l in candidates]
            total = sum(weights)
            r = random.uniform(0, total)
            cumulative = 0
            selected = candidates[0]
            for i, w in enumerate(weights):
                cumulative += w
                if r <= cumulative:
                    selected = candidates[i]
                    break
        else:
            selected = min(candidates, key=lambda l: l.load_score)

        logger.info(
            f"[{self.node_id}] 选择节点: {selected.node_id}, "
            f"负载: {selected.load_score:.3f}, 策略: {self.strategy.value}"
        )

        return {
            "node_id": selected.node_id,
            "load": selected.load_score,
            "cpu": selected.cpu,
            "memory": selected.memory,
            "queue": selected.queue,
            "capabilities": selected.capabilities,
        }

    def get_least_loaded_nodes(
        self,
        count: int = 3,
        capability: str = None,
    ) -> List[Dict[str, Any]]:
        """
        获取负载最低的 N 个节点

        Args:
            count: 返回数量
            capability: 需要的 capability

        Returns:
            节点列表
        """
        with self._lock:
            candidates = []

            # 本地节点
            if not self._local_load.is_stale(self.LOAD_EXPIRY):
                candidates.append(self._local_load)

            # 远程节点
            for load in self._loads.values():
                if load.is_stale(self.LOAD_EXPIRY):
                    continue
                if capability and capability not in load.capabilities:
                    continue
                candidates.append(load)

        # 按负载排序
        sorted_candidates = sorted(candidates, key=lambda l: l.load_score)

        return [
            {
                "node_id": l.node_id,
                "load": l.load_score,
                "cpu": l.cpu,
                "memory": l.memory,
                "queue": l.queue,
                "capabilities": l.capabilities,
            }
            for l in sorted_candidates[:count]
        ]

    def cleanup_stale(self):
        """清理过期的负载信息"""
        with self._lock:
            expired = [
                node_id
                for node_id, load in self._loads.items()
                if load.is_stale(self.LOAD_EXPIRY)
            ]

            for node_id in expired:
                del self._loads[node_id]

        if expired:
            logger.debug(f"[{self.node_id}] 清理过期负载: {len(expired)}")

    def set_strategy(self, strategy: BalanceStrategy):
        """设置负载均衡策略"""
        self.strategy = strategy
        logger.info(f"[{self.node_id}] 负载均衡策略: {strategy.value}")

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        with self._lock:
            return {
                "node_id": self.node_id,
                "strategy": self.strategy.value,
                "local_load": {
                    "cpu": self._local_load.cpu,
                    "memory": self._local_load.memory,
                    "queue": self._local_load.queue,
                    "load_score": self._local_load.load_score,
                },
                "known_nodes": len(self._loads),
                "nodes": [
                    {
                        "node_id": l.node_id,
                        "load_score": l.load_score,
                        "cpu": l.cpu,
                        "memory": l.memory,
                        "queue": l.queue,
                        "capabilities": l.capabilities,
                        "stale": l.is_stale(self.LOAD_EXPIRY),
                    }
                    for l in self._loads.values()
                ],
            }
