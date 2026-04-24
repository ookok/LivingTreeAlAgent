"""
API健康监控与自动优化系统

核心功能：
- 实时监控API健康状态
- 自动降级/恢复策略
- 性能指标收集
- 智能权重调整
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import json
from pathlib import Path

from .models import APIHealth, APIStatus, TierLevel
from core.logger import get_logger
logger = get_logger('search.api_monitor')



@dataclass
class MonitorConfig:
    """监控配置"""
    check_interval: int = 60  # 检查间隔（秒）
    health_threshold: float = 0.9  # 健康阈值
    degrade_threshold: float = 0.8  # 降级阈值
    failure_threshold: int = 3  # 连续失败次数阈值
    recovery_attempts: int = 3  # 恢复尝试次数
    stats_window: int = 300  # 统计窗口（秒）


@dataclass
class APIMetrics:
    """API性能指标"""
    api_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeout_requests: int = 0
    total_response_time: float = 0.0
    min_response_time: float = float('inf')
    max_response_time: float = 0.0
    response_times: List[float] = field(default_factory=list)
    last_request_time: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        return self.successful_requests / max(self.total_requests, 1)
    
    @property
    def avg_response_time(self) -> float:
        return self.total_response_time / max(self.successful_requests, 1)
    
    @property
    def p95_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[min(idx, len(sorted_times) - 1)]
    
    def record_request(self, success: bool, response_time: float = 0.0, timeout: bool = False):
        """记录请求"""
        self.total_requests += 1
        self.last_request_time = datetime.now()
        
        if timeout:
            self.timeout_requests += 1
        
        if success:
            self.successful_requests += 1
            self.total_response_time += response_time
            self.min_response_time = min(self.min_response_time, response_time)
            self.max_response_time = max(self.max_response_time, response_time)
            
            # 保持最近的100个响应时间
            self.response_times.append(response_time)
            if len(self.response_times) > 100:
                self.response_times = self.response_times[-100:]
        else:
            self.failed_requests += 1
    
    def to_dict(self) -> Dict:
        return {
            "api_name": self.api_name,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.success_rate,
            "avg_response_time": self.avg_response_time,
            "p95_response_time": self.p95_response_time,
        }


class APIMonitor:
    """
    API健康监控器
    
    监控API的可用性、响应时间、成功率等指标
    并提供自动降级和恢复机制
    """
    
    def __init__(
        self, 
        config: Optional[MonitorConfig] = None,
        on_status_change: Optional[Callable] = None
    ):
        self.config = config or MonitorConfig()
        self.on_status_change = on_status_change
        
        # API健康状态
        self._health: Dict[str, APIHealth] = {}
        
        # API性能指标
        self._metrics: Dict[str, APIMetrics] = {}
        
        # 监控任务
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        
        # 事件历史
        self._events: List[Dict] = []
        
        # 权重调整历史
        self._weight_history: Dict[str, List[Dict]] = {}
    
    def register_api(self, api_name: str, tier: TierLevel = TierLevel.TIER_3_GLOBAL):
        """注册API"""
        self._health[api_name] = APIHealth(
            api_name=api_name,
            status=APIStatus.HEALTHY,
        )
        self._metrics[api_name] = APIMetrics(api_name=api_name)
        self._weight_history[api_name] = []
    
    def record_request(
        self, 
        api_name: str, 
        success: bool, 
        response_time: float = 0.0,
        timeout: bool = False
    ):
        """记录请求结果"""
        if api_name not in self._health:
            self.register_api(api_name)
        
        # 更新健康状态
        health = self._health[api_name]
        metrics = self._metrics[api_name]
        
        health.total_requests += 1
        metrics.record_request(success, response_time, timeout)
        
        if success:
            health.failed_requests = 0
            health.consecutive_failures = 0
            health.last_success = datetime.now()
            health.avg_response_time = metrics.avg_response_time
            health.p95_response_time = metrics.p95_response_time
        else:
            health.failed_requests += 1
            health.consecutive_failures += 1
            health.last_failure = datetime.now()
        
        # 更新成功率
        health.success_rate = metrics.success_rate
        
        # 评估状态变化
        self._evaluate_status(api_name)
    
    def _evaluate_status(self, api_name: str):
        """评估并更新API状态"""
        health = self._health[api_name]
        old_status = health.status
        
        # 判断新状态
        if health.consecutive_failures >= self.config.failure_threshold * 2:
            new_status = APIStatus.DISABLED
        elif health.consecutive_failures >= self.config.failure_threshold:
            new_status = APIStatus.FAILING
        elif health.success_rate < self.config.degrade_threshold:
            new_status = APIStatus.DEGRADED
        elif health.success_rate >= self.config.health_threshold:
            new_status = APIStatus.HEALTHY
        else:
            new_status = APIStatus.DEGRADED
        
        # 状态变化处理
        if new_status != old_status:
            health.status = new_status
            
            # 记录事件
            self._record_event(api_name, old_status, new_status)
            
            # 触发回调
            if self.on_status_change:
                self.on_status_change(api_name, old_status, new_status)
    
    def _record_event(self, api_name: str, old_status: APIStatus, new_status: APIStatus):
        """记录状态变化事件"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "api_name": api_name,
            "old_status": old_status.value,
            "new_status": new_status.value,
        }
        self._events.append(event)
        
        # 保持最近1000个事件
        if len(self._events) > 1000:
            self._events = self._events[-1000:]
    
    def get_health(self, api_name: str) -> Optional[APIHealth]:
        """获取API健康状态"""
        return self._health.get(api_name)
    
    def get_all_health(self) -> Dict[str, APIHealth]:
        """获取所有API健康状态"""
        return self._health.copy()
    
    def get_metrics(self, api_name: str) -> Optional[APIMetrics]:
        """获取API性能指标"""
        return self._metrics.get(api_name)
    
    def get_all_metrics(self) -> Dict[str, APIMetrics]:
        """获取所有API性能指标"""
        return self._metrics.copy()
    
    def is_api_available(self, api_name: str) -> bool:
        """检查API是否可用"""
        health = self._health.get(api_name)
        if not health:
            return True  # 未注册的API默认为可用
        
        return health.status not in [APIStatus.DISABLED, APIStatus.FAILING]
    
    def get_best_api(self, api_names: List[str]) -> Optional[str]:
        """获取最佳API"""
        available = [name for name in api_names if self.is_api_available(name)]
        
        if not available:
            return None
        
        # 按健康状态和响应时间排序
        ranked = []
        for name in available:
            health = self._health.get(name)
            if health:
                score = health.success_rate * 100 - health.avg_response_time * 10
                ranked.append((name, score))
        
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked[0][0] if ranked else None
    
    def adjust_weights(self, api_weights: Dict[str, float]) -> Dict[str, float]:
        """根据健康状态调整权重"""
        adjusted = {}
        
        for api_name, base_weight in api_weights.items():
            health = self._health.get(api_name)
            
            if not health:
                adjusted[api_name] = base_weight
                continue
            
            # 调整因子
            factor = 1.0
            
            if health.status == APIStatus.HEALTHY:
                factor = 1.0
            elif health.status == APIStatus.DEGRADED:
                factor = 0.6
            elif health.status == APIStatus.FAILING:
                factor = 0.2
            elif health.status == APIStatus.DISABLED:
                factor = 0.0
            
            # 成功率调整
            factor *= health.success_rate
            
            new_weight = base_weight * factor
            adjusted[api_name] = max(0.0, new_weight)
            
            # 记录调整历史
            self._weight_history[api_name].append({
                "timestamp": datetime.now().isoformat(),
                "base_weight": base_weight,
                "factor": factor,
                "new_weight": new_weight,
                "health_status": health.status.value,
            })
        
        return adjusted
    
    def get_events(
        self, 
        api_name: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict]:
        """获取事件历史"""
        events = self._events
        
        if api_name:
            events = [e for e in events if e["api_name"] == api_name]
        
        if since:
            events = [e for e in events if datetime.fromisoformat(e["timestamp"]) >= since]
        
        return events[-limit:]
    
    def get_summary(self) -> Dict:
        """获取监控摘要"""
        total_apis = len(self._health)
        healthy = sum(1 for h in self._health.values() if h.status == APIStatus.HEALTHY)
        degraded = sum(1 for h in self._health.values() if h.status == APIStatus.DEGRADED)
        failing = sum(1 for h in self._health.values() if h.status == APIStatus.FAILING)
        disabled = sum(1 for h in self._health.values() if h.status == APIStatus.DISABLED)
        
        total_requests = sum(m.total_requests for m in self._metrics.values())
        total_success = sum(m.successful_requests for m in self._metrics.values())
        
        avg_success_rate = total_success / max(total_requests, 1) if total_requests > 0 else 0
        
        return {
            "total_apis": total_apis,
            "healthy": healthy,
            "degraded": degraded,
            "failing": failing,
            "disabled": disabled,
            "total_requests": total_requests,
            "total_success": total_success,
            "avg_success_rate": avg_success_rate,
            "recent_events": len(self._events[-10:]),
        }
    
    def export_report(self, filepath: Path) -> bool:
        """导出监控报告"""
        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": self.get_summary(),
            "health": {
                name: {
                    "status": h.status.value,
                    "success_rate": h.success_rate,
                    "avg_response_time": h.avg_response_time,
                    "total_requests": h.total_requests,
                }
                for name, h in self._health.items()
            },
            "metrics": {
                name: m.to_dict()
                for name, m in self._metrics.items()
            },
            "recent_events": self._events[-50:],
        }
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.info(f"[APIMonitor] Export failed: {e}")
            return False
    
    async def start_monitoring(self):
        """启动监控任务"""
        if self._running:
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
    
    async def stop_monitoring(self):
        """停止监控任务"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
    
    async def _monitor_loop(self):
        """监控循环"""
        while self._running:
            try:
                await asyncio.sleep(self.config.check_interval)
                await self._check_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.info(f"[APIMonitor] Monitor error: {e}")
    
    async def _check_health(self):
        """健康检查"""
        for api_name in self._health:
            health = self._health[api_name]
            
            # 检查是否需要恢复尝试
            if health.status == APIStatus.DISABLED:
                if health.last_failure:
                    time_since_failure = datetime.now() - health.last_failure
                    if time_since_failure > timedelta(minutes=5):
                        # 尝试恢复
                        health.consecutive_failures = 0
                        self._evaluate_status(api_name)
                        logger.info(f"[APIMonitor] Attempting recovery for {api_name}")


__all__ = ["APIMonitor", "APIMetrics", "MonitorConfig"]
