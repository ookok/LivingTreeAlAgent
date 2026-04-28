"""
CostMonitor - 成本监控器

实现成本认知系统的第三层：成本监控

核心功能：
- 实时监控任务执行成本
- 超预算时触发熔断
- 提供警告和熔断策略

借鉴金融交易系统的熔断机制：分级预警、及时止损

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import time
import threading


class MonitorStatus(Enum):
    """监控状态"""
    NORMAL = "normal"           # 正常
    WARNING = "warning"         # 警告（接近预算上限）
    CRITICAL = "critical"       # 临界（超预算）
    STOPPED = "stopped"         # 已停止（熔断）


class CostMetrics:
    """
    成本指标
    """
    def __init__(self):
        # 金钱成本
        self.money_spent_usd = 0.0
        self.money_budget_usd = 0.0
        
        # 时间成本
        self.time_spent_seconds = 0.0
        self.time_budget_seconds = 0.0
        
        # 空间成本
        self.space_used_mb = 0.0
        self.space_budget_mb = 0.0
        
        # 调用统计
        self.api_calls = 0
        self.l4_calls = 0
        self.steps_completed = 0


class CostMonitor:
    """
    成本监控器
    
    实时监控任务执行成本，支持：
    1. 监控金钱成本（API调用费用）
    2. 监控时间成本（执行时间）
    3. 监控空间成本（存储/内存）
    4. 熔断机制（超预算时停止任务）
    
    熔断策略：
    - 已消耗 > 预算 × 80%: 警告
    - 已消耗 > 预算: 熔断
    """
    
    def __init__(self):
        self._logger = logger.bind(component="CostMonitor")
        
        # 监控状态
        self._status: Dict[str, MonitorStatus] = {}
        
        # 成本指标
        self._metrics: Dict[str, CostMetrics] = {}
        
        # 熔断回调函数
        self._on_fuse_callbacks: List[callable] = []
        
        # 监控线程
        self._monitor_threads: Dict[str, threading.Thread] = {}
        self._stop_events: Dict[str, threading.Event] = {}
        
        self._logger.info("✅ CostMonitor 初始化完成")
    
    def start_monitoring(self, session_id: str, budget_usd: float, 
                        time_budget_seconds: float = 600,
                        space_budget_mb: float = 1000):
        """
        开始监控任务
        
        Args:
            session_id: 会话ID
            budget_usd: 预算金额（USD）
            time_budget_seconds: 时间预算（秒）
            space_budget_mb: 空间预算（MB）
        """
        # 初始化指标
        self._metrics[session_id] = CostMetrics()
        self._metrics[session_id].money_budget_usd = budget_usd
        self._metrics[session_id].time_budget_seconds = time_budget_seconds
        self._metrics[session_id].space_budget_mb = space_budget_mb
        
        # 设置初始状态
        self._status[session_id] = MonitorStatus.NORMAL
        
        # 创建停止事件
        self._stop_events[session_id] = threading.Event()
        
        # 启动监控线程
        monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(session_id,),
            daemon=True
        )
        self._monitor_threads[session_id] = monitor_thread
        monitor_thread.start()
        
        self._logger.debug(f"🔍 开始监控: {session_id}, 预算: ${budget_usd}")
    
    def _monitor_loop(self, session_id: str):
        """
        监控循环
        
        定期检查成本消耗，触发警告或熔断
        """
        stop_event = self._stop_events[session_id]
        
        while not stop_event.is_set():
            metrics = self._metrics.get(session_id)
            if not metrics:
                break
            
            # 检查金钱成本
            self._check_money_budget(session_id, metrics)
            
            # 检查时间成本
            self._check_time_budget(session_id, metrics)
            
            # 检查空间成本
            self._check_space_budget(session_id, metrics)
            
            # 检查是否需要熔断
            if self._status[session_id] == MonitorStatus.CRITICAL:
                self._trigger_fuse(session_id)
                break
            
            # 每秒检查一次
            stop_event.wait(1.0)
    
    def _check_money_budget(self, session_id: str, metrics: CostMetrics):
        """检查金钱预算"""
        if metrics.money_budget_usd <= 0:
            return
        
        ratio = metrics.money_spent_usd / metrics.money_budget_usd
        
        if ratio >= 1.0:
            self._status[session_id] = MonitorStatus.CRITICAL
            self._logger.warning(f"🔥 金钱成本超预算: {session_id}, 已消耗 ${metrics.money_spent_usd:.2f}, 预算 ${metrics.money_budget_usd:.2f}")
        elif ratio >= 0.8:
            if self._status[session_id] == MonitorStatus.NORMAL:
                self._status[session_id] = MonitorStatus.WARNING
                self._logger.warning(f"⚠️ 金钱成本接近预算上限: {session_id}, 已消耗 {ratio:.0%}")
    
    def _check_time_budget(self, session_id: str, metrics: CostMetrics):
        """检查时间预算"""
        if metrics.time_budget_seconds <= 0:
            return
        
        ratio = metrics.time_spent_seconds / metrics.time_budget_seconds
        
        if ratio >= 1.0:
            self._status[session_id] = MonitorStatus.CRITICAL
            self._logger.warning(f"🔥 时间成本超预算: {session_id}, 已耗时 {metrics.time_spent_seconds:.1f}s, 预算 {metrics.time_budget_seconds:.1f}s")
        elif ratio >= 0.8:
            if self._status[session_id] == MonitorStatus.NORMAL:
                self._status[session_id] = MonitorStatus.WARNING
                self._logger.warning(f"⚠️ 时间成本接近预算上限: {session_id}, 已耗时 {ratio:.0%}")
    
    def _check_space_budget(self, session_id: str, metrics: CostMetrics):
        """检查空间预算"""
        if metrics.space_budget_mb <= 0:
            return
        
        ratio = metrics.space_used_mb / metrics.space_budget_mb
        
        if ratio >= 1.0:
            self._status[session_id] = MonitorStatus.CRITICAL
            self._logger.warning(f"🔥 空间成本超预算: {session_id}, 已使用 {metrics.space_used_mb:.1f}MB, 预算 {metrics.space_budget_mb:.1f}MB")
        elif ratio >= 0.8:
            if self._status[session_id] == MonitorStatus.NORMAL:
                self._status[session_id] = MonitorStatus.WARNING
                self._logger.warning(f"⚠️ 空间成本接近预算上限: {session_id}, 已使用 {ratio:.0%}")
    
    def _trigger_fuse(self, session_id: str):
        """触发熔断"""
        self._status[session_id] = MonitorStatus.STOPPED
        self._logger.error(f"🔴 触发熔断: {session_id}")
        
        # 调用熔断回调
        for callback in self._on_fuse_callbacks:
            try:
                callback(session_id)
            except Exception as e:
                self._logger.error(f"熔断回调失败: {e}")
    
    def stop_monitoring(self, session_id: str):
        """停止监控"""
        # 设置停止事件
        if session_id in self._stop_events:
            self._stop_events[session_id].set()
        
        # 等待线程结束
        if session_id in self._monitor_threads:
            self._monitor_threads[session_id].join(timeout=5.0)
        
        self._logger.debug(f"⏹️ 停止监控: {session_id}")
    
    def record_spending(self, session_id: str, amount_usd: float):
        """
        记录成本消耗
        
        Args:
            session_id: 会话ID
            amount_usd: 消耗金额（USD）
        """
        if session_id in self._metrics:
            self._metrics[session_id].money_spent_usd += amount_usd
            self._logger.debug(f"💸 记录成本消耗: {session_id} -> +${amount_usd:.4f}")
    
    def record_time(self, session_id: str, seconds: float):
        """
        记录时间消耗
        
        Args:
            session_id: 会话ID
            seconds: 消耗时间（秒）
        """
        if session_id in self._metrics:
            self._metrics[session_id].time_spent_seconds += seconds
    
    def record_space(self, session_id: str, mb: float):
        """
        记录空间消耗
        
        Args:
            session_id: 会话ID
            mb: 消耗空间（MB）
        """
        if session_id in self._metrics:
            self._metrics[session_id].space_used_mb += mb
    
    def record_api_call(self, session_id: str, is_l4: bool = False):
        """
        记录API调用
        
        Args:
            session_id: 会话ID
            is_l4: 是否是L4调用
        """
        if session_id in self._metrics:
            self._metrics[session_id].api_calls += 1
            if is_l4:
                self._metrics[session_id].l4_calls += 1
    
    def record_step(self, session_id: str):
        """
        记录步骤完成
        
        Args:
            session_id: 会话ID
        """
        if session_id in self._metrics:
            self._metrics[session_id].steps_completed += 1
    
    def get_status(self, session_id: str) -> Dict[str, Any]:
        """
        获取监控状态
        
        Args:
            session_id: 会话ID
            
        Returns:
            监控状态信息
        """
        if session_id not in self._status:
            return {"error": "未找到会话"}
        
        metrics = self._metrics.get(session_id)
        
        return {
            "session_id": session_id,
            "status": self._status[session_id].value,
            "money": {
                "spent": metrics.money_spent_usd if metrics else 0.0,
                "budget": metrics.money_budget_usd if metrics else 0.0,
                "ratio": (metrics.money_spent_usd / metrics.money_budget_usd * 100) if metrics and metrics.money_budget_usd > 0 else 0.0
            },
            "time": {
                "spent": metrics.time_spent_seconds if metrics else 0.0,
                "budget": metrics.time_budget_seconds if metrics else 0.0,
                "ratio": (metrics.time_spent_seconds / metrics.time_budget_seconds * 100) if metrics and metrics.time_budget_seconds > 0 else 0.0
            },
            "space": {
                "used": metrics.space_used_mb if metrics else 0.0,
                "budget": metrics.space_budget_mb if metrics else 0.0,
                "ratio": (metrics.space_used_mb / metrics.space_budget_mb * 100) if metrics and metrics.space_budget_mb > 0 else 0.0
            },
            "calls": {
                "api": metrics.api_calls if metrics else 0,
                "l4": metrics.l4_calls if metrics else 0,
                "steps": metrics.steps_completed if metrics else 0
            }
        }
    
    def register_fuse_callback(self, callback: callable):
        """
        注册熔断回调函数
        
        Args:
            callback: 回调函数，接收 session_id 作为参数
        """
        self._on_fuse_callbacks.append(callback)
        self._logger.debug(f"📌 注册熔断回调")
    
    def is_running(self, session_id: str) -> bool:
        """检查监控是否在运行"""
        return session_id in self._status and self._status[session_id] != MonitorStatus.STOPPED


# 创建全局实例
cost_monitor = CostMonitor()


def get_cost_monitor() -> CostMonitor:
    """获取成本监控器实例"""
    return cost_monitor


# 测试函数
async def test_cost_monitor():
    """测试成本监控器"""
    import sys
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 CostMonitor")
    print("=" * 60)
    
    monitor = CostMonitor()
    
    # 1. 注册熔断回调
    print("\n[1] 注册熔断回调...")
    def on_fuse(session_id):
        print(f"    🔥 熔断触发: {session_id}")
    
    monitor.register_fuse_callback(on_fuse)
    
    # 2. 开始监控
    print("\n[2] 开始监控...")
    session_id = "test_session"
    monitor.start_monitoring(session_id, budget_usd=1.0, time_budget_seconds=60)
    
    # 3. 模拟成本消耗
    print("\n[3] 模拟成本消耗...")
    for i in range(5):
        monitor.record_spending(session_id, 0.2)
        monitor.record_api_call(session_id, is_l4=True)
        monitor.record_step(session_id)
        status = monitor.get_status(session_id)
        print(f"    步骤 {i+1}: 状态={status['status']}, 已消耗=${status['money']['spent']:.2f}")
        await asyncio.sleep(0.5)
    
    # 4. 检查状态
    print("\n[4] 检查监控状态...")
    status = monitor.get_status(session_id)
    print(f"    ✓ 状态: {status['status']}")
    print(f"    ✓ 金钱消耗: ${status['money']['spent']:.2f}")
    print(f"    ✓ API调用: {status['calls']['api']}")
    print(f"    ✓ L4调用: {status['calls']['l4']}")
    
    # 5. 停止监控
    print("\n[5] 停止监控...")
    monitor.stop_monitoring(session_id)
    
    print("\n" + "=" * 60)
    print("🎉 所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_cost_monitor())