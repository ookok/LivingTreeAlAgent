# sensors/performance_sensor.py - 性能传感器

"""
PerformanceSensor - 运行时性能感知传感器

监控内容：
- API响应时间
- 内存泄漏检测
- CPU瓶颈识别
- 吞吐量异常
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import time
import logging

from .base import BaseSensor, SensorType, EvolutionSignal

logger = logging.getLogger('evolution.sensor.performance')


class PerformanceSensor(BaseSensor):
    """
    运行时性能感知传感器
    
    通过集成 ResourceMonitor 获取性能数据，检测异常模式
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="PerformanceSensor",
            sensor_type=SensorType.PERFORMANCE,
            config=config
        )
        
        # 阈值配置
        self.latency_threshold_p95 = self.config.get('latency_p95_ms', 500)
        self.memory_leak_threshold = self.config.get('memory_growth_mb', 100)
        self.cpu_threshold = self.config.get('cpu_percent', 85)
        self.error_rate_threshold = self.config.get('error_rate_percent', 5)
        
        # 指标缓存
        self._latency_history: List[Dict[str, Any]] = []
        self._memory_history: List[Dict[str, Any]] = []
        self._max_history_size = self.config.get('max_history_size', 1000)
        
        # ResourceMonitor 集成（延迟导入避免循环依赖）
        self._resource_monitor = None
        
        logger.info(
            f"[PerformanceSensor] 配置: latency_p95={self.latency_threshold_p95}ms, "
            f"memory_growth={self.memory_leak_threshold}MB, cpu={self.cpu_threshold}%"
        )
    
    def _get_resource_monitor(self):
        """延迟获取 ResourceMonitor"""
        if self._resource_monitor is None:
            try:
                from client.src.business.resource_monitor import ResourceMonitor
                self._resource_monitor = ResourceMonitor()
            except ImportError:
                logger.warning("[PerformanceSensor] ResourceMonitor 不可用")
                return None
        return self._resource_monitor
    
    def start(self):
        """启动监控"""
        monitor = self._get_resource_monitor()
        if monitor:
            monitor.start()
        super().start()
    
    def stop(self):
        """停止监控"""
        monitor = self._get_resource_monitor()
        if monitor:
            monitor.stop()
        super().stop()
    
    def scan(self) -> List[EvolutionSignal]:
        """
        执行性能扫描
        
        Returns:
            检测到的性能信号列表
        """
        signals = []
        
        # 1. 检测内存泄漏
        signals.extend(self._detect_memory_leak())
        
        # 2. 检测CPU瓶颈
        signals.extend(self._detect_cpu_bottleneck())
        
        # 3. 检测高延迟
        signals.extend(self._detect_high_latency())
        
        logger.info(f"[PerformanceSensor] 扫描完成，检测到 {len(signals)} 个信号")
        return signals
    
    def record_latency(self, endpoint: str, latency_ms: float):
        """
        记录API延迟
        
        Args:
            endpoint: API端点
            latency_ms: 延迟（毫秒）
        """
        self._latency_history.append({
            'endpoint': endpoint,
            'latency_ms': latency_ms,
            'timestamp': time.time()
        })
        
        # 保持历史大小
        if len(self._latency_history) > self._max_history_size:
            self._latency_history = self._latency_history[-self._max_history_size:]
        
        # 实时检测异常
        if latency_ms > self.latency_threshold_p95:
            signal = self._create_signal(
                signal_type="high_latency",
                severity="warning" if latency_ms < 1000 else "critical",
                evidence=[
                    f"{endpoint} 响应时间 {latency_ms:.0f}ms > 阈值 {self.latency_threshold_p95}ms"
                ],
                metrics={
                    'latency_ms': latency_ms,
                    'threshold_ms': self.latency_threshold_p95,
                    'excess_percent': (latency_ms - self.latency_threshold_p95) / self.latency_threshold_p95 * 100
                },
                confidence=0.9,
                false_positive_rate=0.05
            )
            self._emit_signal(signal)
    
    def record_memory(self, module: str, memory_mb: float):
        """
        记录内存使用
        
        Args:
            module: 模块名
            memory_mb: 内存使用（MB）
        """
        self._memory_history.append({
            'module': module,
            'memory_mb': memory_mb,
            'timestamp': time.time()
        })
        
        if len(self._memory_history) > self._max_history_size:
            self._memory_history = self._memory_history[-self._max_history_size:]
        
        # 触发内存泄漏检测
        self._detect_memory_leak()
    
    def record_error(self, endpoint: str, error_type: str):
        """
        记录错误
        
        Args:
            endpoint: API端点
            error_type: 错误类型
        """
        # 简单实现：记录错误发生
        signal = self._create_signal(
            signal_type="error_rate",
            severity="warning",
            evidence=[f"{endpoint} 发生错误: {error_type}"],
            metrics={'error_type': 1},
            confidence=0.8,
            false_positive_rate=0.1
        )
        self._emit_signal(signal)
    
    def _detect_memory_leak(self) -> List[EvolutionSignal]:
        """检测内存泄漏"""
        signals = []
        
        if len(self._memory_history) < 100:
            return signals
        
        # 按模块分组分析
        modules: Dict[str, List[float]] = {}
        for record in self._memory_history:
            module = record['module']
            if module not in modules:
                modules[module] = []
            modules[module].append(record['memory_mb'])
        
        for module, memory_values in modules.items():
            if len(memory_values) < 50:
                continue
            
            # 计算增长趋势
            recent = memory_values[-20:]
            older = memory_values[-50:-20] if len(memory_values) >= 50 else memory_values[:20]
            
            avg_recent = sum(recent) / len(recent)
            avg_older = sum(older) / len(older) if older else avg_recent
            
            growth = avg_recent - avg_older
            
            if growth > self.memory_leak_threshold:
                signal = self._create_signal(
                    signal_type="memory_leak",
                    severity="critical" if growth > self.memory_leak_threshold * 2 else "warning",
                    evidence=[f"模块 {module} 内存增长 {growth:.1f}MB"],
                    metrics={
                        'growth_mb': growth,
                        'recent_avg_mb': avg_recent,
                        'older_avg_mb': avg_older,
                        'samples': len(memory_values)
                    },
                    affected_files=[f"模块: {module}"],
                    confidence=0.85,
                    false_positive_rate=0.1
                )
                signals.append(signal)
        
        return signals
    
    def _detect_cpu_bottleneck(self) -> List[EvolutionSignal]:
        """检测CPU瓶颈"""
        signals = []
        
        monitor = self._get_resource_monitor()
        if not monitor:
            return signals
        
        try:
            # 获取CPU使用率
            cpu_percent = getattr(monitor, '_current_cpu', 0)
            
            if cpu_percent > self.cpu_threshold:
                signal = self._create_signal(
                    signal_type="cpu_bottleneck",
                    severity="critical" if cpu_percent > 90 else "warning",
                    evidence=[f"CPU使用率 {cpu_percent:.1f}% > 阈值 {self.cpu_threshold}%"],
                    metrics={
                        'cpu_percent': cpu_percent,
                        'threshold_percent': self.cpu_threshold
                    },
                    confidence=0.9,
                    false_positive_rate=0.05
                )
                signals.append(signal)
                
        except Exception as e:
            logger.debug(f"[PerformanceSensor] CPU检测异常: {e}")
        
        return signals
    
    def _detect_high_latency(self) -> List[EvolutionSignal]:
        """检测高延迟模式"""
        signals = []
        
        if len(self._latency_history) < 10:
            return signals
        
        # 按端点分组分析
        endpoints: Dict[str, List[float]] = {}
        for record in self._latency_history:
            endpoint = record['endpoint']
            if endpoint not in endpoints:
                endpoints[endpoint] = []
            endpoints[endpoint].append(record['latency_ms'])
        
        for endpoint, latencies in endpoints.items():
            if len(latencies) < 5:
                continue
            
            # 计算P95
            sorted_latencies = sorted(latencies)
            p95_index = int(len(sorted_latencies) * 0.95)
            p95 = sorted_latencies[p95_index]
            
            if p95 > self.latency_threshold_p95:
                signal = self._create_signal(
                    signal_type="high_latency_p95",
                    severity="warning",
                    evidence=[
                        f"{endpoint} P95延迟 {p95:.0f}ms > 阈值 {self.latency_threshold_p95}ms"
                    ],
                    metrics={
                        'p95_ms': p95,
                        'avg_ms': sum(latencies) / len(latencies),
                        'max_ms': max(latencies),
                        'threshold_ms': self.latency_threshold_p95,
                        'samples': len(latencies)
                    },
                    affected_files=[f"API: {endpoint}"],
                    confidence=0.85,
                    false_positive_rate=0.1
                )
                signals.append(signal)
        
        return signals
    
    def get_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        return {
            'latency_samples': len(self._latency_history),
            'memory_samples': len(self._memory_history),
            'latency_p95': self._calculate_p95([r['latency_ms'] for r in self._latency_history]),
            'memory_avg': sum(r['memory_mb'] for r in self._memory_history) / len(self._memory_history) if self._memory_history else 0,
            'last_scan': self._last_scan_time.isoformat() if self._last_scan_time else None
        }
    
    def _calculate_p95(self, values: List[float]) -> float:
        """计算P95"""
        if not values:
            return 0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * 0.95)
        return sorted_values[min(index, len(sorted_values) - 1)]
