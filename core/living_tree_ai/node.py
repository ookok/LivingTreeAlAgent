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

from .openharness_integration import OpenHarnessEngine, ToolSystem, SkillSystem, PluginSystem, PermissionSystem, MemorySystem
from ..p2p_cdn import create_p2p_cdn, CDNNode, NodeCapability
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

    def __lt__(self, other):
        """实现比较方法，用于优先级队列"""
        if self.priority != other.priority:
            return self.priority < other.priority
        # 当优先级相同时，按创建时间排序
        return self.created_at < other.created_at


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

        # OpenHarness 集成
        self.openharness_engine = OpenHarnessEngine()
        self.tool_system = ToolSystem()
        self.skill_system = SkillSystem()
        self.plugin_system = PluginSystem()
        self.permission_system = PermissionSystem()
        self.memory_system = MemorySystem()
        
        # 注册 OpenHarness 工具到引擎
        for tool_info in self.tool_system.get_all_tools():
            tool_name = tool_info["name"]
            tool = self.tool_system.get_tool(tool_name)
            if tool:
                self.openharness_engine.register_tool(
                    name=tool_name,
                    func=tool.func,
                    description=tool.description
                )

        # 会话状态
        self.start_time: Optional[float] = None
        
        # P2P CDN 集成
        self.cdn = None

    async def start(self):
        """启动节点"""
        self.status = NodeStatus.BOOTING
        self.start_time = time.time()
        self.info.status = NodeStatus.BOOTING

        # 启动 P2P CDN
        try:
            self.cdn = await create_p2p_cdn(self.node_id)
            print(f"[LivingTreeNode:{self.node_id}] P2P CDN 启动成功")
        except Exception as e:
            print(f"[LivingTreeNode:{self.node_id}] P2P CDN 启动失败: {e}")

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
        
        # 停止 P2P CDN
        if self.cdn:
            try:
                await self.cdn.stop()
                print(f"[LivingTreeNode:{self.node_id}] P2P CDN 已停止")
            except Exception as e:
                print(f"[LivingTreeNode:{self.node_id}] P2P CDN 停止失败: {e}")
        
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
        # 使用 OpenHarness 引擎处理推理任务
        input_data = task.input_data
        prompt = input_data.get("prompt", "")
        
        # 定义简单的模型模拟函数
        async def mock_model(context):
            """模拟模型响应"""
            await asyncio.sleep(0.5)
            if "tool_call" in str(context):
                return {
                    "tool_call": {
                        "name": "read_file",
                        "args": {
                            "file_path": "test.txt"
                        }
                    }
                }
            return f"基于输入: {context['prompt']} 的推理结果"
        
        # 执行 Agent Loop
        result = await self.openharness_engine.run_agent(
            prompt=prompt,
            model=mock_model,
            max_steps=5
        )
        
        # 模拟进度更新
        for i in range(10):
            await asyncio.sleep(0.1)
            task.progress = (i + 1) / 10
            if task.callback:
                task.callback(task.progress, f"推理中... {int(task.progress*100)}%")
        
        return {
            "answer": result["response"],
            "steps": result["steps"],
            "events": len(result["events"]),
            "confidence": 0.95
        }

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
    
    async def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """执行工具"""
        # 检查权限
        try:
            # 执行权限检查钩子
            self.permission_system.execute_hook("tool_execution", tool_name=tool_name, args=kwargs)
            
            # 执行工具
            result = await self.tool_system.execute_tool(tool_name, **kwargs)
            
            # 执行工具执行后钩子
            self.permission_system.execute_hook("tool_execution", tool_name=tool_name, result=result)
            
            return result
        except Exception as e:
            print(f"[ToolExecution] 工具执行失败 {tool_name}: {e}")
            raise
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """获取可用工具"""
        return self.tool_system.get_all_tools()
    
    def load_skill(self, skill_name: str) -> Any:
        """加载技能"""
        # 执行技能加载前钩子
        self.permission_system.execute_hook("skill_loading", skill_name=skill_name)
        
        # 加载技能
        skill = self.skill_system.load_skill(skill_name)
        
        # 将技能知识集成到知识库
        if skill:
            # 提取技能知识
            skill_knowledge = {
                "name": skill.name,
                "description": skill.description,
                "knowledge": skill.knowledge,
                "version": skill.version
            }
            
            # 存储到知识库
            self.knowledge_base[skill.name] = skill_knowledge
            
            # 添加到内存系统
            self.memory_system.add_memory(
                content=skill_knowledge,
                tags=["skill", skill.name, skill.knowledge.get("domain", "")],
                metadata={"type": "skill", "version": skill.version}
            )
        
        return skill
    
    def get_available_skills(self) -> List[Dict[str, Any]]:
        """获取可用技能"""
        return self.skill_system.get_all_skills()
    
    def get_skill_by_tool(self, tool_name: str) -> List[str]:
        """根据工具获取使用该工具的技能"""
        return self.skill_system.get_skill_by_tool(tool_name)
    
    def load_plugin(self, plugin_name: str) -> Any:
        """加载插件"""
        plugin = self.plugin_system.load_plugin(plugin_name)
        return plugin
    
    def execute_plugin(self, plugin_name: str, **kwargs) -> Any:
        """执行插件"""
        return self.plugin_system.execute_plugin(plugin_name, **kwargs)
    
    def get_available_plugins(self) -> List[Dict[str, Any]]:
        """获取可用插件"""
        return self.plugin_system.get_all_plugins()
    
    def check_permission(self, permission_name: str) -> bool:
        """检查权限"""
        return self.permission_system.check_permission(permission_name)
    
    def grant_permission(self, permission_name: str):
        """授予权限"""
        self.permission_system.grant_permission(permission_name)
    
    def revoke_permission(self, permission_name: str):
        """撤销权限"""
        self.permission_system.revoke_permission(permission_name)
    
    def execute_hook(self, event: str, **kwargs) -> List[Any]:
        """执行钩子"""
        return self.permission_system.execute_hook(event, **kwargs)
    
    def get_all_permissions(self) -> List[Dict[str, Any]]:
        """获取所有权限"""
        return self.permission_system.get_all_permissions()
    
    def get_all_hooks(self) -> List[Dict[str, Any]]:
        """获取所有钩子"""
        return self.permission_system.get_all_hooks()
    
    def add_memory(self, content: Any, tags: List[str] = None, metadata: Dict[str, Any] = None) -> str:
        """添加内存项"""
        return self.memory_system.add_memory(content, tags, metadata)
    
    def get_memory(self, item_id: str) -> Any:
        """获取内存项"""
        return self.memory_system.get_memory(item_id)
    
    def search_memory(self, query: str, tags: List[str] = None) -> List[Any]:
        """搜索内存项"""
        return self.memory_system.search_memory(query, tags)
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """获取内存统计信息"""
        return self.memory_system.get_memory_stats()
    
    # P2P CDN 相关方法
    async def store_cdn_data(self, data: Dict[str, Any], data_type: str = "json") -> Optional[str]:
        """存储数据到 P2P CDN
        
        Args:
            data: 要存储的结构化数据
            data_type: 数据类型
            
        Returns:
            数据 ID，如果存储失败则返回 None
        """
        if not self.cdn:
            print(f"[LivingTreeNode:{self.node_id}] P2P CDN 未初始化")
            return None
        
        try:
            data_id = await self.cdn.store_data(data, data_type)
            print(f"[LivingTreeNode:{self.node_id}] 数据存储到 CDN 成功，数据 ID: {data_id}")
            return data_id
        except Exception as e:
            print(f"[LivingTreeNode:{self.node_id}] 数据存储到 CDN 失败: {e}")
            return None
    
    async def get_cdn_data(self, data_id: str) -> Optional[Dict[str, Any]]:
        """从 P2P CDN 获取数据
        
        Args:
            data_id: 数据 ID
            
        Returns:
            获取的数据，如果获取失败则返回 None
        """
        if not self.cdn:
            print(f"[LivingTreeNode:{self.node_id}] P2P CDN 未初始化")
            return None
        
        try:
            data = await self.cdn.get_data(data_id)
            if data:
                print(f"[LivingTreeNode:{self.node_id}] 从 CDN 获取数据成功")
            else:
                print(f"[LivingTreeNode:{self.node_id}] 从 CDN 获取数据失败: 数据不存在")
            return data
        except Exception as e:
            print(f"[LivingTreeNode:{self.node_id}] 从 CDN 获取数据失败: {e}")
            return None
    
    async def update_cdn_data(self, data_id: str, data: Dict[str, Any]) -> bool:
        """更新 P2P CDN 中的数据
        
        Args:
            data_id: 数据 ID
            data: 更新后的数据
            
        Returns:
            是否更新成功
        """
        if not self.cdn:
            print(f"[LivingTreeNode:{self.node_id}] P2P CDN 未初始化")
            return False
        
        try:
            result = await self.cdn.update_data(data_id, data)
            if result:
                print(f"[LivingTreeNode:{self.node_id}] CDN 数据更新成功")
            else:
                print(f"[LivingTreeNode:{self.node_id}] CDN 数据更新失败: 数据不存在")
            return result
        except Exception as e:
            print(f"[LivingTreeNode:{self.node_id}] CDN 数据更新失败: {e}")
            return False
    
    async def delete_cdn_data(self, data_id: str) -> bool:
        """从 P2P CDN 删除数据
        
        Args:
            data_id: 数据 ID
            
        Returns:
            是否删除成功
        """
        if not self.cdn:
            print(f"[LivingTreeNode:{self.node_id}] P2P CDN 未初始化")
            return False
        
        try:
            result = await self.cdn.delete_data(data_id)
            if result:
                print(f"[LivingTreeNode:{self.node_id}] CDN 数据删除成功")
            else:
                print(f"[LivingTreeNode:{self.node_id}] CDN 数据删除失败: 数据不存在")
            return result
        except Exception as e:
            print(f"[LivingTreeNode:{self.node_id}] CDN 数据删除失败: {e}")
            return False
    
    def add_cdn_node(self, node_id: str, storage_available: int, bandwidth: int, uptime: int, reliability: float):
        """添加 CDN 节点
        
        Args:
            node_id: 节点 ID
            storage_available: 可用存储空间（字节）
            bandwidth: 带宽（Mbps）
            uptime: 在线时间（秒）
            reliability: 可靠性（0-1）
        """
        if not self.cdn:
            print(f"[LivingTreeNode:{self.node_id}] P2P CDN 未初始化")
            return
        
        try:
            node = CDNNode(
                node_id=node_id,
                capability=NodeCapability(
                    storage_available=storage_available,
                    bandwidth=bandwidth,
                    uptime=uptime,
                    reliability=reliability
                ),
                last_seen=time.time()
            )
            self.cdn.add_node(node)
            print(f"[LivingTreeNode:{self.node_id}] 添加 CDN 节点成功: {node_id}")
        except Exception as e:
            print(f"[LivingTreeNode:{self.node_id}] 添加 CDN 节点失败: {e}")
    
    def remove_cdn_node(self, node_id: str):
        """移除 CDN 节点
        
        Args:
            node_id: 节点 ID
        """
        if not self.cdn:
            print(f"[LivingTreeNode:{self.node_id}] P2P CDN 未初始化")
            return
        
        try:
            self.cdn.remove_node(node_id)
            print(f"[LivingTreeNode:{self.node_id}] 移除 CDN 节点成功: {node_id}")
        except Exception as e:
            print(f"[LivingTreeNode:{self.node_id}] 移除 CDN 节点失败: {e}")
    
    def get_cdn_stats(self) -> Optional[Dict[str, Any]]:
        """获取 CDN 统计信息
        
        Returns:
            CDN 统计信息，如果 CDN 未初始化则返回 None
        """
        if not self.cdn:
            print(f"[LivingTreeNode:{self.node_id}] P2P CDN 未初始化")
            return None
        
        try:
            stats = self.cdn.get_stats()
            print(f"[LivingTreeNode:{self.node_id}] 获取 CDN 统计信息成功")
            return stats
        except Exception as e:
            print(f"[LivingTreeNode:{self.node_id}] 获取 CDN 统计信息失败: {e}")
            return None

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
