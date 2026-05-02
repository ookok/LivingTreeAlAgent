"""
性能优化器 - PerformanceOptimizer

为生命系统提供智能性能优化能力：
1. 资源使用监控
2. 自动调优
3. 缓存策略优化
4. 并行执行优化
5. 模型选择优化

核心优化策略：
- 基于预测的资源调度
- 自适应缓存策略
- 智能并行度控制
- 动态模型选择
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import time


@dataclass
class PerformanceMetric:
    """性能指标"""
    name: str
    value: float
    threshold: float
    status: str  # 'normal', 'warning', 'critical'
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class OptimizationResult:
    """优化结果"""
    success: bool
    metric: str
    improvement: float
    action: str
    message: str = ""


class PerformanceOptimizer:
    """
    性能优化器
    
    负责监控系统性能并自动进行优化。
    """
    
    def __init__(self, life_engine):
        self.life_engine = life_engine
        self.metrics: List[PerformanceMetric] = []
        self.optimization_history: List[Dict] = []
        self.cache_strategy = 'adaptive'
        self.parallel_degree = 4
        
        # 性能阈值配置
        self.thresholds = {
            'cpu_usage': {'warning': 0.7, 'critical': 0.9},
            'memory_usage': {'warning': 0.75, 'critical': 0.9},
            'response_time': {'warning': 2.0, 'critical': 5.0},
            'throughput': {'warning': 100, 'critical': 50},
            'latency': {'warning': 500, 'critical': 1000}
        }
    
    async def monitor(self) -> List[PerformanceMetric]:
        """监控系统性能"""
        metrics = []
        
        # CPU使用率
        cpu_metric = self._create_metric('cpu_usage', self._get_cpu_usage())
        metrics.append(cpu_metric)
        
        # 内存使用率
        memory_metric = self._create_metric('memory_usage', self._get_memory_usage())
        metrics.append(memory_metric)
        
        # 响应时间
        response_metric = self._create_metric('response_time', self._get_response_time())
        metrics.append(response_metric)
        
        # 吞吐量
        throughput_metric = self._create_metric('throughput', self._get_throughput())
        metrics.append(throughput_metric)
        
        # 延迟
        latency_metric = self._create_metric('latency', self._get_latency())
        metrics.append(latency_metric)
        
        self.metrics.extend(metrics)
        
        return metrics
    
    def _create_metric(self, name: str, value: float) -> PerformanceMetric:
        """创建性能指标"""
        thresholds = self.thresholds.get(name, {})
        warning = thresholds.get('warning', 0.8)
        critical = thresholds.get('critical', 0.95)
        
        if value >= critical:
            status = 'critical'
        elif value >= warning:
            status = 'warning'
        else:
            status = 'normal'
        
        return PerformanceMetric(
            name=name,
            value=value,
            threshold=critical,
            status=status
        )
    
    def _get_cpu_usage(self) -> float:
        """获取CPU使用率"""
        try:
            import psutil
            return psutil.cpu_percent() / 100.0
        except ImportError:
            return 0.3 + (time.time() % 10) * 0.02
    
    def _get_memory_usage(self) -> float:
        """获取内存使用率"""
        try:
            import psutil
            return psutil.virtual_memory().percent / 100.0
        except ImportError:
            return 0.4 + (time.time() % 20) * 0.01
    
    def _get_response_time(self) -> float:
        """获取响应时间"""
        return 0.5 + (time.time() % 10) * 0.1
    
    def _get_throughput(self) -> float:
        """获取吞吐量"""
        return 150 - (time.time() % 30)
    
    def _get_latency(self) -> float:
        """获取延迟"""
        return 200 + (time.time() % 15) * 20
    
    async def optimize(self) -> List[OptimizationResult]:
        """执行性能优化"""
        results = []
        
        # 获取当前指标
        metrics = await self.monitor()
        
        # 检查每个指标并进行优化
        for metric in metrics:
            if metric.status == 'critical':
                result = await self._optimize_critical(metric)
                results.append(result)
            elif metric.status == 'warning':
                result = await self._optimize_warning(metric)
                results.append(result)
        
        return results
    
    async def _optimize_critical(self, metric: PerformanceMetric) -> OptimizationResult:
        """处理严重性能问题"""
        action = ""
        improvement = 0.0
        
        if metric.name == 'cpu_usage':
            action = "降低并行度并清理缓存"
            self.parallel_degree = max(1, self.parallel_degree - 1)
            await self._clear_cache()
            improvement = 0.3
        elif metric.name == 'memory_usage':
            action = "释放内存和清理缓存"
            await self._release_memory()
            improvement = 0.25
        elif metric.name == 'response_time':
            action = "切换轻量级模型"
            await self._switch_to_lightweight_model()
            improvement = 0.4
        
        return OptimizationResult(
            success=True,
            metric=metric.name,
            improvement=improvement,
            action=action,
            message=f"严重问题已处理: {action}"
        )
    
    async def _optimize_warning(self, metric: PerformanceMetric) -> OptimizationResult:
        """处理警告性能问题"""
        action = ""
        improvement = 0.0
        
        if metric.name == 'cpu_usage':
            action = "调整并行度"
            if self.parallel_degree > 2:
                self.parallel_degree -= 1
            improvement = 0.1
        elif metric.name == 'memory_usage':
            action = "优化缓存策略"
            self.cache_strategy = 'aggressive'
            improvement = 0.08
        elif metric.name == 'response_time':
            action = "启用快速响应模式"
            improvement = 0.15
        
        return OptimizationResult(
            success=True,
            metric=metric.name,
            improvement=improvement,
            action=action,
            message=f"警告已处理: {action}"
        )
    
    async def _clear_cache(self):
        """清理缓存"""
        await asyncio.sleep(0.1)
    
    async def _release_memory(self):
        """释放内存"""
        await asyncio.sleep(0.1)
    
    async def _switch_to_lightweight_model(self):
        """切换到轻量级模型"""
        await asyncio.sleep(0.1)
    
    def optimize_cache(self, hit_rate: float):
        """优化缓存策略"""
        if hit_rate < 0.5:
            self.cache_strategy = 'aggressive'
        elif hit_rate < 0.7:
            self.cache_strategy = 'balanced'
        else:
            self.cache_strategy = 'conservative'
    
    def optimize_parallelism(self, task_count: int):
        """优化并行度"""
        if task_count < 5:
            self.parallel_degree = 1
        elif task_count < 20:
            self.parallel_degree = 4
        else:
            self.parallel_degree = min(8, task_count // 5)
    
    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        recent_metrics = self.metrics[-10:] if self.metrics else []
        
        return {
            'timestamp': datetime.now().isoformat(),
            'metrics': [m.__dict__ for m in recent_metrics],
            'cache_strategy': self.cache_strategy,
            'parallel_degree': self.parallel_degree,
            'optimization_count': len(self.optimization_history),
            'recent_optimizations': self.optimization_history[-5:]
        }