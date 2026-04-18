"""
LivingTreeAI Node - 生命之树节点核心模块
======================================

节点类型：
1. 通用节点 (UniversalNode) - 基础模型，处理常见任务
2. 专业节点 (SpecializedNode) - 特定领域深入训练
3. 协调节点 (CoordinatorNode) - 任务分解和调度
4. 存储节点 (StorageNode) - 存储历史知识和模型

Author: LivingTreeAI Community
"""

import asyncio
import json
import uuid
import time
import psutil
import platform
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from asyncio import Queue


class NodeStatus(Enum):
    """节点状态"""
    OFFLINE = "offline"           # 离线
    BOOTING = "booting"           # 启动中
    ONLINE = "online"             # 在线
    BUSY = "busy"                # 忙碌
    IDLE = "idle"                # 空闲
    SUSPENDED = "suspended"      # 暂停


class NodeType(Enum):
    """节点类型"""
    UNIVERSAL = "universal"       # 通用节点
    SPECIALIZED = "specialized"   # 专业节点
    COORDINATOR = "coordinator"   # 协调节点
    STORAGE = "storage"           # 存储节点


class HardwareProfile:
    """硬件配置"""

    def __init__(self):
        self.cpu_cores = psutil.cpu_count(logical=False) or 2
        self.cpu_freq = psutil.cpu_freq().current if psutil.cpu_freq() else 1500
        self.memory_total = psutil.virtual_memory().total
        self.memory_available = psutil.virtual_memory().available
        self.disk_total = psutil.disk_usage('/').total
        self.disk_available = psutil.disk_usage('/').free
        self.platform = platform.system()
        self.platform_version = platform.version()
        self.hostname = platform.node()

    def to_dict(self) -> Dict:
        return {
            "cpu_cores": self.cpu_cores,
            "cpu_freq_mhz": self.cpu_freq,
            "memory_total_gb": round(self.memory_total / (1024**3), 2),
            "memory_available_gb": round(self.memory_available / (1024**3), 2),
            "disk_available_gb": round(self.disk_available / (1024**3), 2),
            "platform": self.platform,
            "hostname": self.hostname,
        }

    def can_run_model(self, model_size_mb: int) -> bool:
        """检查是否能够运行指定大小的模型"""
        min_memory = model_size_mb * 1.5 * (1024**2)  # 模型大小的1.5倍
        return self.memory_available >= min_memory


@dataclass
class NodeInfo:
    """节点信息"""
    node_id: str
    node_type: NodeType
    status: NodeStatus
    hardware: Dict
    created_at: float
    last_heartbeat: float
    public_key: str = ""
    trusted: bool = False
    reputation: float = 1.0
    specialization: str = ""  # 专业领域
    model_loaded: str = ""     # 当前加载的模型
    task_completed: int = 0     # 完成的任务数
    online_hours: float = 0.0   # 在线时长

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "status": self.status.value,
            "hardware": self.hardware,
            "created_at": self.created_at,
            "last_heartbeat": self.last_heartbeat,
            "trusted": self.trusted,
            "reputation": self.reputation,
            "specialization": self.specialization,
            "model_loaded": self.model_loaded,
            "task_completed": self.task_completed,
            "online_hours": self.online_hours,
        }


@dataclass
class Task:
    """任务"""
    task_id: str
    task_type: str             # "inference", "training", "storage", "coordination"
    priority: int              # 0-3: 低/普通/高/紧急
    input_data: Any
    required_capability: Optional[str] = None  # 需要的专业能力
    model_size_limit_mb: Optional[int] = None
    max_time_seconds: int = 300
    callback: Optional[Callable] = None
    result: Any = None
    error: str = ""
    progress: float = 0.0
    status: str = "pending"    # pending/running/completed/failed/cancelled
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "priority": self.priority,
            "required_capability": self.required_capability,
            "max_time_seconds": self.max_time_seconds,
            "progress": self.progress,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class LivingTreeNode:
    """
    平民AI节点

    特性：
    - 自动发现P2P网络中的其他节点
    - 贡献闲置算力
    - 参与知识共享
    - 获得贡献证明
    """

    def __init__(
        self,
        node_type: NodeType = NodeType.UNIVERSAL,
        specialization: str = "",
        max_memory_usage: float = 0.5,  # 最大使用50%内存
        data_dir: str = "~/.living_tree_ai",
    ):
        self.node_id = str(uuid.uuid4())[:8]
        self.node_type = node_type
        self.specialization = specialization
        self.max_memory_usage = max_memory_usage

        # 状态
        self.status = NodeStatus.OFFLINE
        self.hardware = HardwareProfile()
        self.info = NodeInfo(
            node_id=self.node_id,
            node_type=node_type,
            status=NodeStatus.OFFLINE,
            hardware=self.hardware.to_dict(),
            created_at=time.time(),
            last_heartbeat=time.time(),
            specialization=specialization,
        )

        # 网络
        self.peers: Dict[str, 'LivingTreeNode'] = {}
        self.pending_messages: Queue = Queue()

        # 任务
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.running_tasks: Dict[str, Task] = {}

        # 知识库
        self.knowledge_base: Dict[str, Any] = {}

        # 会话状态
        self.start_time: Optional[float] = None

    async def start(self):
        """启动节点"""
        self.status = NodeStatus.BOOTING
        self.start_time = time.time()
        self.info.status = NodeStatus.BOOTING

        # 启动心跳
        asyncio.create_task(self._heartbeat_loop())

        # 启动任务处理器
        asyncio.create_task(self._task_processor())

        # 标记在线
        self.status = NodeStatus.ONLINE
        self.info.status = NodeStatus.ONLINE

        print(f"[LivingTreeNode:{self.node_id}] 节点启动成功")
        print(f"  类型: {self.node_type.value}")
        print(f"  特化: {self.specialization or '通用'}")
        print(f"  硬件: {self.hardware.cpu_cores}核, {self.hardware.memory_total/(1024**3):.1f}GB")

    async def stop(self):
        """停止节点"""
        self.status = NodeStatus.OFFLINE
        self.info.status = NodeStatus.OFFLINE
        self.save_state()
        print(f"[LivingTreeNode:{self.node_id}] 节点已停止")

    async def _heartbeat_loop(self):
        """心跳维护"""
        while self.status != NodeStatus.OFFLINE:
            self.info.last_heartbeat = time.time()
            self.info.online_hours = (time.time() - self.start_time) / 3600 if self.start_time else 0

            # 检查内存使用
            mem = psutil.virtual_memory()
            if mem.percent > self.max_memory_usage * 100:
                self.status = NodeStatus.BUSY
                self.info.status = NodeStatus.BUSY
            else:
                self.status = NodeStatus.IDLE
                self.info.status = NodeStatus.IDLE

            await asyncio.sleep(10)  # 每10秒心跳

    async def _task_processor(self):
        """任务处理器"""
        while self.status != NodeStatus.OFFLINE:
            try:
                # 等待任务
                priority, task = await asyncio.wait_for(
                    self.task_queue.get(),
                    timeout=1.0
                )

                # 执行任务
                asyncio.create_task(self._execute_task(task))

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"[LivingTreeNode:{self.node_id}] 任务处理错误: {e}")

    async def _execute_task(self, task: Task):
        """执行任务"""
        task.status = "running"
        task.started_at = time.time()
        self.running_tasks[task.task_id] = task
        self.status = NodeStatus.BUSY

        try:
            # 根据任务类型执行
            if task.task_type == "inference":
                task.result = await self._do_inference(task)
            elif task.task_type == "training":
                task.result = await self._do_training(task)
            elif task.task_type == "storage":
                task.result = await self._do_storage(task)
            elif task.task_type == "coordination":
                task.result = await self._do_coordination(task)
            else:
                raise ValueError(f"未知任务类型: {task.task_type}")

            task.status = "completed"
            task.completed_at = time.time()
            task.progress = 1.0
            self.info.task_completed += 1

        except asyncio.CancelledError:
            task.status = "cancelled"
            task.completed_at = time.time()
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.completed_at = time.time()

        finally:
            self.running_tasks.pop(task.task_id, None)
            if not self.running_tasks:
                self.status = NodeStatus.IDLE

    async def _do_inference(self, task: Task) -> Any:
        """执行推理任务"""
        # 模拟推理过程
        for i in range(10):
            await asyncio.sleep(0.1)
            task.progress = (i + 1) / 10
            if task.callback:
                task.callback(task.progress, f"推理中... {int(task.progress*100)}%")
        return {"answer": "模拟推理结果", "confidence": 0.95}

    async def _do_training(self, task: Task) -> Any:
        """执行训练任务"""
        for i in range(10):
            await asyncio.sleep(0.15)
            task.progress = (i + 1) / 10
            if task.callback:
                task.callback(task.progress, f"训练中... {int(task.progress*100)}%")
        return {"loss": 0.05, "accuracy": 0.98}

    async def _do_storage(self, task: Task) -> Any:
        """执行存储任务"""
        for i in range(5):
            await asyncio.sleep(0.1)
            task.progress = (i + 1) / 5
        return {"stored": True, "size": len(str(task.input_data))}

    async def _do_coordination(self, task: Task) -> Any:
        """执行协调任务"""
        for i in range(5):
            await asyncio.sleep(0.1)
            task.progress = (i + 1) / 5
        return {"coordinated": True, "subtasks": 3}

    def submit_task(
        self,
        task_type: str,
        input_data: Any,
        priority: int = 1,
        required_capability: Optional[str] = None,
        callback: Optional[Callable] = None,
    ) -> str:
        """提交任务"""
        task = Task(
            task_id=str(uuid.uuid4())[:8],
            task_type=task_type,
            priority=priority,
            input_data=input_data,
            required_capability=required_capability,
            callback=callback,
        )
        self.task_queue.put_nowait((priority, task))
        return task.task_id

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            task.status = "cancelled"
            return True
        return False

    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        # 简化实现：实际需要任务内部支持
        return False

    def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        return False

    def get_status(self) -> Dict:
        """获取状态"""
        return {
            "node_id": self.node_id,
            "status": self.status.value,
            "node_type": self.node_type.value,
            "specialization": self.specialization,
            "online_hours": round(self.info.online_hours, 2),
            "task_completed": self.info.task_completed,
            "peers": len(self.peers),
            "running_tasks": len(self.running_tasks),
            "queue_size": self.task_queue.qsize(),
            "hardware": self.hardware.to_dict(),
        }

    def save_state(self):
        """保存状态"""
        state = {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "specialization": self.specialization,
            "created_at": self.info.created_at,
            "online_hours": self.info.online_hours,
            "task_completed": self.info.task_completed,
        }
        import os
        path = os.path.expanduser("~/.living_tree_ai/node_state.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(state, f, indent=2)

    def load_state(self) -> bool:
        """加载状态"""
        import os
        path = os.path.expanduser("~/.living_tree_ai/node_state.json")
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r") as f:
                state = json.load(f)
            self.node_id = state.get("node_id", self.node_id)
            return True
        except:
            return False


# CLI工具函数
def print_node_status(node: LivingTreeNode):
    """打印节点状态"""
    status = node.get_status()
    print(f"""
╔══════════════════════════════════════════════════╗
║           🌾 平民AI节点状态 🌾                    ║
╠══════════════════════════════════════════════════╣
║  节点ID:    {status['node_id']:<35}║
║  状态:      {status['status']:<35}║
║  类型:      {status['node_type']:<35}║
║  特化:      {status['specialization'] or '通用':<35}║
╠══════════════════════════════════════════════════╣
║  在线时长:  {status['online_hours']:.2f} 小时                           ║
║  已完成任务: {status['task_completed']}                              ║
║  连接节点:  {status['peers']}                                    ║
║  运行任务:  {status['running_tasks']}                                    ║
║  队列任务:  {status['queue_size']}                                    ║
╠══════════════════════════════════════════════════╣
║  硬件配置                                           ║
║  CPU:     {status['hardware']['cpu_cores']}核 @ {status['hardware']['cpu_freq_mhz']:.0f}MHz                    ║
║  内存:     {status['hardware']['memory_total_gb']:.1f}GB / {status['hardware']['memory_available_gb']:.1f}GB可用           ║
║  平台:     {status['hardware']['platform']:<35}║
║  主机名:   {status['hardware']['hostname']:<35}║
╚══════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    # 测试节点
    async def test():
        node = LivingTreeNode(
            node_type=NodeType.UNIVERSAL,
            specialization="general"
        )
        await node.start()

        # 提交测试任务
        task_id = node.submit_task(
            task_type="inference",
            input_data={"prompt": "你好"},
            priority=1
        )
        print(f"已提交任务: {task_id}")

        # 等待执行
        await asyncio.sleep(3)

        # 打印状态
        print_node_status(node)

        await node.stop()

    asyncio.run(test())
