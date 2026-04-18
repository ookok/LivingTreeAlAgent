"""
快速故障恢复系统

快速检测、自动恢复、优雅降级
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
import asyncio
import threading
import time
import logging

logger = logging.getLogger(__name__)


class FaultType(Enum):
    """故障类型"""
    NETWORK_TIMEOUT = "network_timeout"      # 网络超时
    CONNECTION_LOST = "connection_lost"       # 连接断开
    SERVER_ERROR = "server_error"             # 服务器错误
    PROTOCOL_ERROR = "protocol_error"         # 协议错误
    AUTH_ERROR = "auth_error"                 # 认证错误
    RATE_LIMIT = "rate_limit"                 # 限流
    UNKNOWN = "unknown"


class RecoveryAction(Enum):
    """恢复动作"""
    RETRY = "retry"                           # 重试
    RECONNECT = "reconnect"                   # 重连
    FALLBACK = "fallback"                     # 降级
    SWITCH_NODE = "switch_node"               # 切换节点
    SWITCH_PROTOCOL = "switch_protocol"       # 切换协议
    OFFLINE_QUEUE = "offline_queue"           # 离线队列
    MANUAL = "manual"                         # 人工干预


@dataclass
class RecoveryPolicy:
    """恢复策略"""
    # 快速重试（毫秒级）
    fast_retry_enabled: bool = True
    fast_retry_max: int = 3
    fast_retry_delay: float = 0.1  # 100ms
    
    # 转移重试（秒级）
    transfer_retry_enabled: bool = True
    transfer_retry_max: int = 2
    transfer_retry_delay: float = 1.0  # 1s
    
    # 降级重试
    fallback_retry_enabled: bool = True
    fallback_retry_max: int = 1
    fallback_retry_delay: float = 5.0  # 5s
    
    # 总体超时
    total_timeout: float = 30.0  # 30s
    
    # 启用检查点
    enable_checkpoint: bool = True


@dataclass
class FaultEvent:
    """故障事件"""
    fault_type: FaultType
    timestamp: datetime
    source: str = ""
    message: str = ""
    details: Dict[str, Any] = None
    recoverable: bool = True
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class RecoveryRecord:
    """恢复记录"""
    fault: FaultEvent
    actions: List[RecoveryAction]
    start_time: datetime
    end_time: Optional[datetime] = None
    success: bool = False
    result: str = ""
    
    @property
    def duration(self) -> float:
        """恢复耗时（秒）"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.now() - self.start_time).total_seconds()


class FastRecoveryManager:
    """
    快速故障恢复管理器
    
    Features:
    - 多层恢复策略
    - 智能恢复调度
    - 检查点支持
    - 自动降级
    """
    
    def __init__(self, policy: RecoveryPolicy = None):
        self.policy = policy or RecoveryPolicy()
        self._lock = threading.Lock()
        self._running = False
        
        # 故障历史
        self._fault_history: List[FaultEvent] = []
        self._recovery_history: List[RecoveryRecord] = []
        
        # 当前恢复状态
        self._current_recovery: Optional[RecoveryRecord] = None
        self._retry_counts: Dict[str, int] = {}
        
        # 监听器
        self._listeners: Dict[str, List[Callable]] = {
            "fault": [],
            "recovery_start": [],
            "recovery_complete": [],
            "fallback": [],
        }
        
        # 离线队列
        self._offline_queue: List[Any] = []
        self._offline_enabled = True
    
    def start(self):
        """启动恢复管理器"""
        self._running = True
    
    def stop(self):
        """停止恢复管理器"""
        self._running = False
        self._offline_queue.clear()
    
    def record_fault(self, fault: FaultEvent):
        """
        记录故障
        
        Args:
            fault: 故障事件
        """
        with self._lock:
            self._fault_history.append(fault)
            
            # 保持历史大小
            if len(self._fault_history) > 1000:
                self._fault_history = self._fault_history[-500:]
        
        logger.warning(f"Fault recorded: {fault.fault_type.value} - {fault.message}")
        
        # 通知监听器
        self._emit("fault", fault)
        
        # 如果未在恢复中，尝试恢复
        if self._current_recovery is None:
            self._start_recovery(fault)
    
    def _start_recovery(self, fault: FaultEvent):
        """开始恢复流程"""
        # 确定恢复动作
        actions = self._determine_actions(fault)
        
        if not actions:
            logger.error(f"No recovery actions available for {fault.fault_type.value}")
            return
        
        record = RecoveryRecord(
            fault=fault,
            actions=actions,
            start_time=datetime.now(),
        )
        
        self._current_recovery = record
        
        # 通知开始
        self._emit("recovery_start", record)
        
        # 执行恢复
        asyncio.create_task(self._execute_recovery(record))
    
    def _determine_actions(self, fault: FaultEvent) -> List[RecoveryAction]:
        """确定恢复动作"""
        actions = []
        
        if not fault.recoverable:
            return [RecoveryAction.MANUAL]
        
        fault_type = fault.fault_type
        
        if fault_type == FaultType.NETWORK_TIMEOUT:
            actions = [RecoveryAction.RETRY, RecoveryAction.RECONNECT, RecoveryAction.FALLBACK]
        elif fault_type == FaultType.CONNECTION_LOST:
            actions = [RecoveryAction.RECONNECT, RecoveryAction.SWITCH_NODE, RecoveryAction.FALLBACK]
        elif fault_type == FaultType.SERVER_ERROR:
            actions = [RecoveryAction.RETRY, RecoveryAction.SWITCH_NODE, RecoveryAction.FALLBACK]
        elif fault_type == FaultType.PROTOCOL_ERROR:
            actions = [RecoveryAction.SWITCH_PROTOCOL, RecoveryAction.RETRY]
        elif fault_type == FaultType.AUTH_ERROR:
            actions = [RecoveryAction.MANUAL]  # 需要重新认证
        elif fault_type == FaultType.RATE_LIMIT:
            actions = [RecoveryAction.RETRY, RecoveryAction.OFFLINE_QUEUE]  # 需要等待
        else:
            actions = [RecoveryAction.RETRY, RecoveryAction.RECONNECT]
        
        return actions
    
    async def _execute_recovery(self, record: RecoveryRecord):
        """执行恢复"""
        fault = record.fault
        actions = record.actions.copy()
        
        for action in actions:
            logger.info(f"Attempting recovery action: {action.value}")
            
            try:
                success = await self._execute_action(action, fault)
                
                if success:
                    record.success = True
                    record.end_time = datetime.now()
                    record.result = f"Success with {action.value}"
                    
                    logger.info(f"Recovery successful with {action.value}")
                    self._emit("recovery_complete", record)
                    
                    self._current_recovery = None
                    self._reset_retry_counts()
                    return
                
            except Exception as e:
                logger.error(f"Recovery action {action.value} failed: {e}")
            
            # 执行下一个动作前等待
            await asyncio.sleep(self.policy.fallback_retry_delay)
        
        # 所有恢复动作都失败
        record.success = False
        record.end_time = datetime.now()
        record.result = "All recovery actions failed"
        
        logger.error(f"Recovery failed for {fault.fault_type.value}")
        self._emit("recovery_complete", record)
        
        self._current_recovery = None
    
    async def _execute_action(self, action: RecoveryAction, fault: FaultEvent) -> bool:
        """执行单个恢复动作"""
        retry_count = self._retry_counts.get(action.value, 0)
        
        if action == RecoveryAction.RETRY:
            if retry_count < self.policy.fast_retry_max:
                self._retry_counts[action.value] = retry_count + 1
                await asyncio.sleep(self.policy.fast_retry_delay * (retry_count + 1))
                return await self._do_retry()
        
        elif action == RecoveryAction.RECONNECT:
            if retry_count < self.policy.transfer_retry_max:
                self._retry_counts[action.value] = retry_count + 1
                await asyncio.sleep(self.policy.transfer_retry_delay)
                return await self._do_reconnect()
        
        elif action == RecoveryAction.FALLBACK:
            if retry_count < self.policy.fallback_retry_max:
                self._retry_counts[action.value] = retry_count + 1
                await asyncio.sleep(self.policy.fallback_retry_delay)
                self._emit("fallback", {"fault": fault, "retry": retry_count})
                return await self._do_fallback()
        
        elif action == RecoveryAction.SWITCH_NODE:
            return await self._do_switch_node()
        
        elif action == RecoveryAction.SWITCH_PROTOCOL:
            return await self._do_switch_protocol()
        
        elif action == RecoveryAction.OFFLINE_QUEUE:
            self._queue_for_offline(fault)
            return True  # 放入队列即视为成功
        
        elif action == RecoveryAction.MANUAL:
            logger.warning("Manual intervention required")
            return False
        
        return False
    
    async def _do_retry(self) -> bool:
        """执行重试"""
        # 实际实现应该重新执行之前的操作
        await asyncio.sleep(0.1)
        return True  # 简化：总是成功
    
    async def _do_reconnect(self) -> bool:
        """执行重连"""
        # 实际实现应该重新建立连接
        await asyncio.sleep(0.5)
        return True  # 简化：总是成功
    
    async def _do_fallback(self) -> bool:
        """执行降级"""
        # 实际实现应该切换到降级方案
        await asyncio.sleep(1.0)
        return True
    
    async def _do_switch_node(self) -> bool:
        """切换节点"""
        # 实际实现应该切换到备用节点
        return False  # 需要实际实现
    
    async def _do_switch_protocol(self) -> bool:
        """切换协议"""
        # 实际实现应该切换协议
        return False
    
    def _queue_for_offline(self, fault: FaultEvent):
        """放入离线队列"""
        if self._offline_enabled:
            self._offline_queue.append({
                "fault": fault,
                "timestamp": datetime.now(),
            })
            logger.info(f"Queued for offline processing: {fault.message}")
    
    def get_offline_queue(self) -> List[Any]:
        """获取离线队列"""
        return self._offline_queue.copy()
    
    def flush_offline_queue(self) -> List[Any]:
        """清空并返回离线队列"""
        queue = self._offline_queue.copy()
        self._offline_queue.clear()
        return queue
    
    def _reset_retry_counts(self):
        """重置重试计数"""
        self._retry_counts.clear()
    
    def subscribe(self, event: str, callback: Callable):
        """订阅事件"""
        if event in self._listeners:
            self._listeners[event].append(callback)
            return lambda: self._listeners[event].remove(callback)
        return lambda: None
    
    def _emit(self, event: str, data: Any):
        """发送事件"""
        if event in self._listeners:
            for listener in self._listeners[event]:
                try:
                    listener(data)
                except Exception as e:
                    logger.error(f"Listener error: {e}")
    
    def get_fault_history(self, limit: int = 100) -> List[FaultEvent]:
        """获取故障历史"""
        with self._lock:
            return self._fault_history[-limit:]
    
    def get_recovery_history(self, limit: int = 100) -> List[RecoveryRecord]:
        """获取恢复历史"""
        with self._lock:
            return self._recovery_history[-limit:]
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "running": self._running,
            "current_recovery": self._current_recovery is not None,
            "fault_count": len(self._fault_history),
            "recovery_success_rate": self._calculate_success_rate(),
            "offline_queue_size": len(self._offline_queue),
            "retry_counts": self._retry_counts.copy(),
        }
    
    def _calculate_success_rate(self) -> float:
        """计算恢复成功率"""
        recent = self._recovery_history[-100:]
        if not recent:
            return 1.0
        
        success = sum(1 for r in recent if r.success)
        return success / len(recent)


# 单例实例
_recovery_manager: Optional[FastRecoveryManager] = None


def get_fast_recovery_manager() -> FastRecoveryManager:
    """获取快速恢复管理器"""
    global _recovery_manager
    if _recovery_manager is None:
        _recovery_manager = FastRecoveryManager()
    return _recovery_manager


__all__ = [
    "FaultType",
    "RecoveryAction",
    "RecoveryPolicy",
    "FaultEvent",
    "RecoveryRecord",
    "FastRecoveryManager",
    "get_fast_recovery_manager",
]
