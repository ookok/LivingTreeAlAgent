"""
自适应超时机制 - AdaptiveTimeout
创新理念：告别"随便设个30秒"，让超时时间根据实际情况动态调整

功能：
1. 基于历史执行时间预测
2. 考虑服务器性能
3. 网络状况感知
4. 任务复杂度评估
"""

import time
import statistics
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class TimeoutConfig:
    """超时配置"""
    base_timeout: int           # 基础超时（秒）
    estimated_time: float       # 预估时间（秒）
    adjusted_timeout: int      # 调整后的超时（秒）
    confidence: float          # 置信度 0-1
    factors: Dict[str, Any]    # 调整因素


class AdaptiveTimeout:
    """
    自适应超时系统

    预测模型考虑因素：
    1. 命令类型（安装/编译/启动）
    2. 服务器性能（CPU/内存）
    3. 网络延迟
    4. 历史执行时间
    5. 并发任务数
    """

    def __init__(self):
        # 命令类型基准时间（秒）
        self._command_baselines = {
            # 包管理
            "apt-get install": 120,
            "apt-get update": 60,
            "yum install": 120,
            "pip install": 90,
            "npm install": 180,
            "cargo build": 300,
            "mvn package": 180,

            # 文件操作
            "cp": 10,
            "mv": 10,
            "rm": 30,
            "mkdir": 5,

            # 服务操作
            "systemctl start": 15,
            "systemctl restart": 30,
            "docker run": 60,
            "docker build": 300,
            "docker-compose up": 120,

            # 一般命令
            "echo": 1,
            "cat": 5,
            "grep": 10,
        }

        # 性能调整因子
        self._performance_factors = {
            "low": 2.0,      # 低配服务器超时加倍
            "medium": 1.5,   # 中配1.5倍
            "high": 1.0,     # 高配不变
            "unknown": 1.3    # 未知性能取中间值
        }

        # 历史执行记录
        self._execution_history: Dict[str, list] = {}  # command -> [(duration, timestamp), ...]
        self._max_history_per_command = 50

        # 全局统计
        self._network_latency_ms = 0  # 估计的网络延迟
        self._concurrent_tasks = 0    # 当前并发任务数

    def calculate_timeout(
        self,
        command: str,
        server_performance: str = "unknown",
        server_info: Any = None,
        network_latency_ms: int = 0
    ) -> TimeoutConfig:
        """
        计算自适应超时

        Args:
            command: 要执行的命令
            server_performance: 服务器性能等级 ("low", "medium", "high", "unknown")
            server_info: 服务器详细信息（可选）
            network_latency_ms: 网络延迟（毫秒）

        Returns:
            TimeoutConfig: 超时配置
        """
        # 1. 获取命令基准时间
        base_timeout = self._get_command_baseline(command)

        # 2. 获取历史执行数据
        history_timeout = self._get_history_timeout(command)

        # 3. 合并基准和历史（历史优先）
        if history_timeout:
            estimated_time = (base_timeout + history_timeout) / 2
            confidence = 0.7  # 有历史数据的置信度
        else:
            estimated_time = base_timeout
            confidence = 0.5  # 无历史数据的置信度

        # 4. 考虑服务器性能
        perf_factor = self._performance_factors.get(server_performance, 1.3)
        estimated_time *= perf_factor

        # 5. 考虑服务器资源（如果有）
        if server_info and hasattr(server_info, 'memory_available_mb'):
            if server_info.memory_available_mb < 512:
                estimated_time *= 1.5
            elif server_info.memory_available_mb > 2048:
                estimated_time *= 0.8

        # 6. 考虑网络延迟
        if network_latency_ms > 100:
            # 高延迟网络，增加超时
            estimated_time += network_latency_ms / 1000 * 5

        # 7. 考虑并发任务
        if self._concurrent_tasks > 3:
            estimated_time *= (1 + 0.2 * (self._concurrent_tasks - 3))

        # 8. 添加安全边际（20%）
        adjusted_timeout = int(estimated_time * 1.2)

        # 确保最小超时为5秒，最大不超过3600秒（1小时）
        adjusted_timeout = max(5, min(3600, adjusted_timeout))

        return TimeoutConfig(
            base_timeout=base_timeout,
            estimated_time=estimated_time,
            adjusted_timeout=adjusted_timeout,
            confidence=confidence,
            factors={
                "command_baseline": base_timeout,
                "history_timeout": history_timeout,
                "perf_factor": perf_factor,
                "server_performance": server_performance,
                "network_latency_ms": network_latency_ms,
                "concurrent_tasks": self._concurrent_tasks
            }
        )

    def _get_command_baseline(self, command: str) -> float:
        """获取命令基准时间"""
        command_lower = command.lower().strip()

        # 精确匹配
        for cmd_pattern, baseline in self._command_baselines.items():
            if command_lower.startswith(cmd_pattern):
                return baseline

        # 部分匹配
        for cmd_pattern, baseline in self._command_baselines.items():
            if cmd_pattern in command_lower:
                return baseline

        # 默认值（根据命令长度估算）
        if "install" in command_lower or "build" in command_lower:
            return 120
        elif "start" in command_lower or "stop" in command_lower:
            return 15
        elif len(command) > 100:
            return 30
        else:
            return 10

    def _get_history_timeout(self, command: str) -> Optional[float]:
        """从历史数据估算超时"""
        if command not in self._execution_history:
            return None

        history = self._execution_history[command]

        if len(history) < 2:
            return None

        # 只使用最近30天的数据
        cutoff = datetime.now() - timedelta(days=30)
        recent = [
            duration for duration, timestamp in history
            if timestamp > cutoff
        ]

        if not recent:
            return None

        # 计算平均值和标准差
        avg = statistics.mean(recent)
        stdev = statistics.stdev(recent) if len(recent) > 1 else 0

        # 使用 avg + 1.5*stdev 作为估计（更保守）
        estimated = avg + 1.5 * stdev

        return min(estimated, 3600)  # 最大不超过1小时

    def record_execution(self, command: str, duration_seconds: float):
        """
        记录命令执行时间

        Args:
            command: 执行的命令
            duration_seconds: 执行耗时（秒）
        """
        if command not in self._execution_history:
            self._execution_history[command] = []

        self._execution_history[command].append((
            duration_seconds,
            datetime.now()
        ))

        # 保持历史数量限制
        if len(self._execution_history[command]) > self._max_history_per_command:
            self._execution_history[command] = self._execution_history[command][-self._max_history_per_command:]

        # 更新网络延迟估计（如果是网络相关命令）
        if command.startswith("ssh") or command.startswith("curl"):
            pass  # 可以添加延迟估算逻辑

    def set_concurrent_tasks(self, count: int):
        """设置当前并发任务数"""
        self._concurrent_tasks = max(0, count)

    def get_command_statistics(self, command: str) -> Dict[str, Any]:
        """获取命令统计信息"""
        if command not in self._execution_history:
            return {"count": 0, "avg": 0, "min": 0, "max": 0}

        history = self._execution_history[command]
        durations = [d for d, _ in history]

        return {
            "count": len(durations),
            "avg": statistics.mean(durations),
            "min": min(durations),
            "max": max(durations),
            "recent": durations[-5:]  # 最近5次
        }

    def suggest_timeout_for_deployment(
        self,
        steps: list,
        server_performance: str = "unknown"
    ) -> int:
        """
        为部署流程建议总体超时

        Args:
            steps: 部署步骤列表
            server_performance: 服务器性能等级

        Returns:
            建议的超时时间（秒）
        """
        total_estimated = 0
        critical_path_steps = []  # 关键路径上的步骤

        for step in steps:
            # 跳过可以并行的步骤
            if hasattr(step, 'can_parallel') and step.can_parallel:
                continue

            if hasattr(step, 'command'):
                config = self.calculate_timeout(
                    step.command,
                    server_performance
                )
                total_estimated += config.estimated_time
                critical_path_steps.append({
                    "step": step.name if hasattr(step, 'name') else "unknown",
                    "timeout": config.adjusted_timeout
                })

        # 添加15%的安全边际
        total_timeout = int(total_estimated * 1.15)

        return total_timeout


# 全局实例
adaptive_timeout = AdaptiveTimeout()
