"""
健康监控器 - 实时监测 + 自动恢复
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, Callable, List, Optional


@dataclass
class HealthResult:
    """健康检查结果"""
    healthy: bool
    component: str
    message: str = ""
    latency_ms: float = 0.0


@dataclass
class Alert:
    """告警信息"""
    timestamp: float
    component: str
    level: str  # info, warning, critical
    message: str


class HealthMonitor:
    """健康监控器 - 实时监测 + 自动恢复"""
    
    def __init__(self):
        self._checks: Dict[str, Callable] = {}
        self._recovery_actions: Dict[str, Callable] = {}
        self._alerts: List[Alert] = []
        self._monitor_task: Optional[asyncio.Task] = None
        self._check_interval = 30  # 检查间隔（秒）
    
    def register_check(self, component: str, check_func: Callable, recovery_func: Optional[Callable] = None):
        """注册健康检查"""
        self._checks[component] = check_func
        if recovery_func:
            self._recovery_actions[component] = recovery_func
    
    async def run_health_checks(self) -> Dict[str, HealthResult]:
        """运行所有健康检查"""
        results = {}
        for component, check_func in self._checks.items():
            start_time = time.time()
            try:
                result = await check_func()
                result.latency_ms = (time.time() - start_time) * 1000
                results[component] = result
                
                if not result.healthy:
                    await self._trigger_recovery(component)
            except Exception as e:
                results[component] = HealthResult(
                    healthy=False,
                    component=component,
                    message=str(e),
                    latency_ms=(time.time() - start_time) * 1000
                )
                await self._trigger_recovery(component)
        
        return results
    
    async def _trigger_recovery(self, component: str):
        """触发自动恢复"""
        recovery_func = self._recovery_actions.get(component)
        if recovery_func:
            try:
                await recovery_func()
                self._send_alert(component, "info", f"自动恢复 {component} 成功")
            except Exception as e:
                self._send_alert(component, "critical", f"自动恢复 {component} 失败: {str(e)}")
        else:
            self._send_alert(component, "warning", f"{component} 健康检查失败，无恢复策略")
    
    def _send_alert(self, component: str, level: str, message: str):
        """发送告警"""
        alert = Alert(
            timestamp=time.time(),
            component=component,
            level=level,
            message=message
        )
        self._alerts.append(alert)
        
        # 保留最近100条告警
        if len(self._alerts) > 100:
            self._alerts.pop(0)
    
    def start_monitoring(self):
        """启动监控任务"""
        if self._monitor_task is None:
            self._monitor_task = asyncio.create_task(self._monitor_loop())
    
    def stop_monitoring(self):
        """停止监控任务"""
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None
    
    async def _monitor_loop(self):
        """监控循环"""
        while True:
            await self.run_health_checks()
            await asyncio.sleep(self._check_interval)
    
    def get_alerts(self, level: Optional[str] = None) -> List[Alert]:
        """获取告警列表"""
        if level:
            return [a for a in self._alerts if a.level == level]
        return list(self._alerts)
    
    def get_recent_alerts(self, minutes: int = 10) -> List[Alert]:
        """获取最近N分钟的告警"""
        threshold = time.time() - minutes * 60
        return [a for a in self._alerts if a.timestamp >= threshold]


def get_health_monitor() -> HealthMonitor:
    """获取健康监控器单例"""
    if not hasattr(get_health_monitor, '_instance'):
        get_health_monitor._instance = HealthMonitor()
    return get_health_monitor._instance