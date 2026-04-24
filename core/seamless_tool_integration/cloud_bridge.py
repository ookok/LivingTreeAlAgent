"""
Cloud Bridge - 云端计算备选

当本地计算资源不足时，提供云端计算选项

功能：
1. 检测本地计算能力
2. 云端任务提交
3. 进度追踪
4. 结果获取
5. 费用估算
"""

import os
import time
import json
import hashlib
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from pathlib import Path


class CloudExecutionMode(Enum):
    """云端执行模式"""
    OFF = "off"              # 关闭，不使用云端
    AUTO = "auto"            # 自动（本地不足时切换）
    ALWAYS = "always"        # 总是使用云端
    ONLY_CLOUD = "only_cloud"  # 仅云端


class CloudProvider(Enum):
    """云服务提供商"""
    ALIYUN = "aliyun"        # 阿里云
    TENCENT = "tencent"      # 腾讯云
    AWS = "aws"              # 亚马逊AWS
    CUSTOM = "custom"        # 自定义


class TaskStatus(Enum):
    """云端任务状态"""
    PENDING = "pending"      # 等待中
    RUNNING = "running"      # 运行中
    COMPLETED = "completed"  # 完成
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 取消


@dataclass
class CloudConfig:
    """云端配置"""
    provider: CloudProvider = CloudProvider.ALIYUN

    # API配置
    api_endpoint: str = ""       # API地址
    api_key: str = ""            # API密钥
    api_secret: str = ""         # API Secret

    # 计费配置
    price_per_minute: float = 0.5  # 每分钟价格
    currency: str = "CNY"

    # 资源配额
    max_concurrent_tasks: int = 2
    max_execution_time: int = 7200  # 秒

    # 网络配置
    timeout: int = 30
    max_retries: int = 3


@dataclass
class CloudTask:
    """云端任务"""
    task_id: str
    project_name: str

    # 输入
    input_files: Dict[str, str] = field(default_factory=dict)  # 文件名 -> 文件内容(base64)
    parameters: Dict[str, Any] = field(default_factory=dict)

    # 输出
    output_files: Dict[str, str] = field(default_factory=dict)  # 文件名 -> 文件内容(base64)
    result_data: Dict[str, Any] = field(default_factory=dict)

    # 状态
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0

    # 计费
    estimated_cost: float = 0.0
    actual_cost: float = 0.0

    # 时间
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 错误
    error_message: str = ""

    @property
    def execution_time(self) -> float:
        """执行时间（秒）"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.now() - self.started_at).total_seconds()
        return 0.0

    @property
    def is_finished(self) -> bool:
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]


class LocalCapabilityDetector:
    """
    本地计算能力检测

    检测本地环境是否能高效运行模型
    """

    @staticmethod
    def detect() -> Dict[str, Any]:
        """
        检测本地计算能力

        Returns:
            检测结果字典
        """
        try:
            import psutil
            cpu_count = psutil.cpu_count(logical=False) or 4
            cpu_count_logical = psutil.cpu_count(logical=True) or 8
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_total = psutil.virtual_memory().total / (1024**3)
            memory_available = psutil.virtual_memory().available / (1024**3)
            memory_percent = psutil.virtual_memory().percent
        except Exception:
            # Fallback values if psutil is not available
            cpu_count = 4
            cpu_count_logical = 8
            cpu_percent = 50.0
            memory_total = 16.0
            memory_available = 8.0
            memory_percent = 50.0

        try:
            import platform as _platform_module
            os_name = _platform_module.system()
            os_version = _platform_module.version()
        except Exception:
            os_name = "Unknown"
            os_version = "Unknown"

        result = {
            "os": os_name,
            "os_version": os_version,
            "cpu_count": cpu_count,
            "cpu_count_logical": cpu_count_logical,
            "cpu_percent": cpu_percent,
            "memory_total_gb": memory_total,
            "memory_available_gb": memory_available,
            "memory_percent": memory_percent,
        }

        # GPU检测
        result["gpu"] = LocalCapabilityDetector._detect_gpu()

        # 磁盘空间
        try:
            import shutil
            disk = shutil.disk_usage("/")
            result["disk_free_gb"] = disk.free / (1024**3)
        except:
            result["disk_free_gb"] = 0

        # 综合评分
        result["capability_score"] = LocalCapabilityDetector._calculate_score(result)

        return result

    @staticmethod
    def _detect_gpu() -> Dict[str, Any]:
        """检测GPU"""
        gpu_info = {
            "available": False,
            "name": "",
            "memory_total_mb": 0,
            "driver_version": ""
        }

        try:
            # 尝试使用NVIDIA GPU
            import subprocess
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader'],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.decode('utf-8').strip().split('\n')
                if lines:
                    parts = lines[0].split(',')
                    gpu_info["available"] = True
                    gpu_info["name"] = parts[0].strip()
                    gpu_info["memory_total_mb"] = int(parts[1].strip().split()[0])
                    if len(parts) > 2:
                        gpu_info["driver_version"] = parts[2].strip()
        except:
            pass

        return gpu_info

    @staticmethod
    def _calculate_score(cap_info: Dict) -> float:
        """
        计算综合评分 (0-100)

        考虑因素：
        - CPU核心数
        - 内存大小
        - GPU可用性
        - 磁盘空间
        """
        score = 0.0

        # CPU评分 (最高30分)
        cpu_count = cap_info.get("cpu_count", 1)
        if cpu_count >= 8:
            score += 30
        elif cpu_count >= 4:
            score += 20
        elif cpu_count >= 2:
            score += 10

        # 内存评分 (最高30分)
        mem_gb = cap_info.get("memory_total_gb", 0)
        if mem_gb >= 32:
            score += 30
        elif mem_gb >= 16:
            score += 20
        elif mem_gb >= 8:
            score += 10

        # GPU评分 (最高40分)
        gpu = cap_info.get("gpu", {})
        if gpu.get("available"):
            score += 40

        return min(score, 100)

    @staticmethod
    def is_capable_for_aermod(cap_info: Dict) -> bool:
        """检查是否能运行AERMOD"""
        # AERMOD对硬件要求不高，基础配置即可
        return cap_info.get("capability_score", 0) >= 20

    @staticmethod
    def is_capable_for_calpuff(cap_info: Dict) -> bool:
        """检查是否能运行CALPUFF"""
        # CALPUFF计算量大，需要较高配置
        return cap_info.get("capability_score", 0) >= 50


class CloudBridge:
    """
    云端计算桥接器

    提供云端计算的统一接口

    使用示例：
    ```python
    bridge = CloudBridge()

    # 检测本地能力
    local_cap = bridge.detect_local_capability()
    logger.info(f"本地评分: {local_cap['capability_score']}")

    # 设置云端配置
    bridge.configure(api_key="your-key", endpoint="https://api.example.com")

    # 提交云端任务
    task = bridge.submit_task(
        project_name="南京XX项目",
        input_files={"input.inp": open("aermod.inp").read()},
        parameters={"tool": "aermod"}
    )

    # 查询进度
    while not task.is_finished:
        task = bridge.get_task_status(task.task_id)
        logger.info(f"进度: {task.progress}%")
        time.sleep(10)
    ```
    """

    def __init__(self, config: Optional[CloudConfig] = None):
        self.config = config or CloudConfig()
        self._tasks: Dict[str, CloudTask] = {}
        self._local_capability: Optional[Dict] = None

    def configure(self, **kwargs):
        """配置云端参数"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

    def detect_local_capability(self) -> Dict[str, Any]:
        """检测本地计算能力"""
        self._local_capability = LocalCapabilityDetector.detect()
        return self._local_capability

    @property
    def local_capability(self) -> Dict[str, Any]:
        """获取本地能力（已缓存）"""
        if self._local_capability is None:
            self.detect_local_capability()
        return self._local_capability

    def should_use_cloud(
        self,
        tool_type: str,
        mode: CloudExecutionMode = CloudExecutionMode.AUTO,
        estimated_time_minutes: float = 30
    ) -> bool:
        """
        判断是否应该使用云端

        Args:
            tool_type: 工具类型
            mode: 执行模式
            estimated_time_minutes: 预估执行时间

        Returns:
            是否使用云端
        """
        if mode == CloudExecutionMode.OFF:
            return False

        if mode == CloudExecutionMode.ALWAYS or mode == CloudExecutionMode.ONLY_CLOUD:
            return True

        if mode == CloudExecutionMode.AUTO:
            # 检查本地能力
            cap = self.local_capability

            if tool_type == "aermod":
                if not LocalCapabilityDetector.is_capable_for_aermod(cap):
                    return True
                # 长时间任务考虑云端
                if estimated_time_minutes > 60:
                    return True

            elif tool_type == "calpuff":
                if not LocalCapabilityDetector.is_capable_for_calpuff(cap):
                    return True
                if estimated_time_minutes > 30:
                    return True

            return False

        return False

    def estimate_cost(self, tool_type: str, execution_time_minutes: float) -> float:
        """
        估算云端费用

        Args:
            tool_type: 工具类型
            execution_time_minutes: 执行时间（分钟）

        Returns:
            预估费用
        """
        # 根据工具类型调整价格
        price_multiplier = {
            "aermod": 1.0,
            "calpuff": 2.0,
            "pyspray": 0.5
        }

        multiplier = price_multiplier.get(tool_type, 1.0)
        base_cost = execution_time_minutes * self.config.price_per_minute

        return base_cost * multiplier

    def submit_task(
        self,
        project_name: str,
        input_files: Dict[str, bytes],
        parameters: Dict[str, Any],
        tool_type: str = "aermod"
    ) -> CloudTask:
        """
        提交云端任务

        Args:
            project_name: 项目名称
            input_files: 输入文件 {文件名: 文件内容}
            parameters: 运行参数
            tool_type: 工具类型

        Returns:
            CloudTask
        """
        import base64

        # 生成任务ID
        task_id = self._generate_task_id(project_name)

        # 创建任务
        task = CloudTask(
            task_id=task_id,
            project_name=project_name,
            input_files={
                name: base64.b64encode(content).decode('utf-8')
                for name, content in input_files.items()
            },
            parameters=parameters
        )

        # 估算费用
        est_time = parameters.get("estimated_time_minutes", 30)
        task.estimated_cost = self.estimate_cost(tool_type, est_time)

        # 保存任务
        self._tasks[task_id] = task

        # 模拟提交（实际应调用云端API）
        self._submit_to_cloud(task, tool_type)

        return task

    def _generate_task_id(self, project_name: str) -> str:
        """生成任务ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        hash_input = f"{project_name}_{timestamp}"
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        return f"task_{timestamp}_{hash_value}"

    def _submit_to_cloud(self, task: CloudTask, tool_type: str):
        """提交任务到云端（模拟）"""
        # 实际实现应该调用云端API
        # 这里简化为直接设置状态为RUNNING
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()

        # 在后台模拟执行
        import threading
from core.logger import get_logger
logger = get_logger('seamless_tool_integration.cloud_bridge')


        def simulate_execution():
            time.sleep(5)  # 模拟执行5秒
            task.progress = 100.0
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.actual_cost = task.estimated_cost * 0.8  # 实际费用打个折
            task.result_data = {
                "output_file": "result.out",
                "summary": {
                    "max_concentration": 125.5,
                    "exceedance_count": 0
                }
            }

        thread = threading.Thread(target=simulate_execution)
        thread.daemon = True
        thread.start()

    def get_task_status(self, task_id: str) -> Optional[CloudTask]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            CloudTask或None
        """
        task = self._tasks.get(task_id)

        if task and task.status == TaskStatus.RUNNING:
            # 模拟进度更新
            elapsed = task.execution_time
            task.progress = min(elapsed / 60 * 100, 95)  # 假设1分钟完成

        return task

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self._tasks.get(task_id)
        if task and not task.is_finished:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            return True
        return False

    def get_task_result(self, task_id: str) -> Optional[Dict]:
        """获取任务结果"""
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.COMPLETED:
            return task.result_data
        return None

    def list_tasks(self) -> List[CloudTask]:
        """列出所有任务"""
        return list(self._tasks.values())


class CloudExecutionPlanner:
    """
    云端执行规划器

    帮助用户选择最优执行方案
    """

    def __init__(self):
        self.bridge = CloudBridge()

    def plan(
        self,
        tool_type: str,
        project_data: Any,
        mode: CloudExecutionMode = CloudExecutionMode.AUTO
    ) -> Dict[str, Any]:
        """
        规划执行方案

        Args:
            tool_type: 工具类型
            project_data: 项目数据
            mode: 执行模式

        Returns:
            执行方案
        """
        # 检测本地能力
        local_cap = self.bridge.detect_local_capability()

        # 估算执行时间
        estimated_time = self._estimate_execution_time(tool_type, project_data)

        # 决定执行方式
        use_cloud = self.bridge.should_use_cloud(
            tool_type, mode, estimated_time
        )

        # 估算费用
        cloud_cost = self.bridge.estimate_cost(tool_type, estimated_time)

        # 生成建议
        plan = {
            "tool_type": tool_type,
            "execution_mode": "cloud" if use_cloud else "local",
            "local_capability": local_cap,
            "estimated_local_time_minutes": estimated_time,
            "estimated_cloud_cost": cloud_cost,
            "recommendation": "",
            "warnings": []
        }

        # 生成建议文本
        if use_cloud:
            if local_cap["capability_score"] < 50:
                plan["recommendation"] = "本地计算能力不足，建议使用云端计算"
            else:
                plan["recommendation"] = f"任务预估耗时较长（{estimated_time:.0f}分钟），建议使用云端加速"
        else:
            plan["recommendation"] = "本地计算能力充足，可直接运行"

        # 添加警告
        if estimated_time > 120:
            plan["warnings"].append("任务执行时间较长，可能需要耐心等待")

        if local_cap.get("memory_percent", 0) > 80:
            plan["warnings"].append("本地内存使用率较高，可能影响性能")

        return plan

    def _estimate_execution_time(self, tool_type: str, project_data: Any) -> float:
        """估算执行时间"""
        # 简单估算：基于网格点数和源数量
        grid_points = getattr(project_data, 'receptor_grid', None)
        if grid_points:
            point_count = getattr(grid_points, 'total_points', 1000)
        else:
            point_count = 1000

        sources = getattr(project_data, 'emission_sources', [])
        source_count = len(sources) if sources else 1

        # 基础时间（分钟）
        base_time = point_count / 100 * source_count / 10

        # 根据工具类型调整
        multipliers = {
            "aermod": 1.0,
            "calpuff": 3.0,
            "pyspray": 2.0
        }

        return base_time * multipliers.get(tool_type, 1.0)


# 便捷函数
def quick_plan(tool_type: str, project_data: Any, mode: str = "auto") -> Dict:
    """
    快速规划执行方案

    使用示例：
    ```python
    plan = quick_plan("aermod", project_data, mode="auto")
    logger.info(f"推荐方案: {plan['recommendation']}")
    logger.info(f"执行方式: {plan['execution_mode']}")
    ```
    """
    planner = CloudExecutionPlanner()
    mode_enum = CloudExecutionMode(mode)
    return planner.plan(tool_type, project_data, mode_enum)


def submit_cloud_task(
    project_name: str,
    input_files: Dict[str, bytes],
    tool_type: str = "aermod",
    api_key: Optional[str] = None
) -> CloudTask:
    """
    快速提交云端任务

    使用示例：
    ```python
    task = submit_cloud_task(
        "南京项目",
        {"input.inp": open("aermod.inp", "rb").read()}
    )
    logger.info(f"任务ID: {task.task_id}")
    ```
    """
    bridge = CloudBridge()
    if api_key:
        bridge.configure(api_key=api_key)
    return bridge.submit_task(project_name, input_files, {}, tool_type)
