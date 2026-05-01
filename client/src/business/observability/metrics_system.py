"""
指标收集系统

收集和聚合任务链执行的关键指标，包括：
- 计数器 (Counter)
- 仪表盘 (Gauge)
- 直方图 (Histogram)
- 摘要 (Summary)
"""

import time
import statistics
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

@dataclass
class Counter:
    """计数器"""
    name: str
    description: str
    value: int = 0
    labels: Dict[str, str] = field(default_factory=dict)

    def inc(self, amount: int = 1):
        """增加计数"""
        self.value += amount

    def dec(self, amount: int = 1):
        """减少计数"""
        self.value -= amount

@dataclass
class Gauge:
    """仪表盘"""
    name: str
    description: str
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)

    def set(self, value: float):
        """设置值"""
        self.value = value

    def inc(self, amount: float = 1.0):
        """增加"""
        self.value += amount

    def dec(self, amount: float = 1.0):
        """减少"""
        self.value -= amount

@dataclass
class Histogram:
    """直方图"""
    name: str
    description: str
    buckets: List[float] = field(default_factory=lambda: [0.001, 0.01, 0.1, 1.0, 10.0, 60.0])
    counts: List[int] = field(default_factory=list)
    sum: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        self.counts = [0] * (len(self.buckets) + 1)

    def observe(self, value: float):
        """观察值"""
        self.sum += value
        for i, bucket in enumerate(self.buckets):
            if value <= bucket:
                self.counts[i] += 1
                return
        self.counts[-1] += 1

@dataclass
class Summary:
    """摘要"""
    name: str
    description: str
    values: List[float] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)

    def observe(self, value: float):
        """观察值"""
        self.values.append(value)

    def get_summary(self) -> Dict[str, float]:
        """获取摘要统计"""
        if not self.values:
            return {}
        
        return {
            "count": len(self.values),
            "sum": sum(self.values),
            "min": min(self.values),
            "max": max(self.values),
            "avg": sum(self.values) / len(self.values),
            "p50": statistics.median(self.values),
            "p90": self._percentile(90),
            "p99": self._percentile(99)
        }

    def _percentile(self, p: int) -> float:
        """计算百分位数"""
        if not self.values:
            return 0.0
        sorted_vals = sorted(self.values)
        index = int((p / 100) * len(sorted_vals))
        return sorted_vals[min(index, len(sorted_vals) - 1)]

class MetricsSystem:
    """
    指标系统
    
    收集和管理任务链执行的各项指标。
    """
    
    def __init__(self):
        self.counters: Dict[str, Counter] = {}
        self.gauges: Dict[str, Gauge] = {}
        self.histograms: Dict[str, Histogram] = {}
        self.summaries: Dict[str, Summary] = {}
    
    def create_counter(self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None) -> Counter:
        """
        创建计数器
        
        Args:
            name: 名称
            description: 描述
            labels: 标签
        
        Returns:
            计数器实例
        """
        counter = Counter(name=name, description=description, labels=labels or {})
        self.counters[name] = counter
        return counter
    
    def create_gauge(self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None) -> Gauge:
        """
        创建仪表盘
        
        Args:
            name: 名称
            description: 描述
            labels: 标签
        
        Returns:
            仪表盘实例
        """
        gauge = Gauge(name=name, description=description, labels=labels or {})
        self.gauges[name] = gauge
        return gauge
    
    def create_histogram(self, name: str, description: str = "", 
                        buckets: Optional[List[float]] = None, labels: Optional[Dict[str, str]] = None) -> Histogram:
        """
        创建直方图
        
        Args:
            name: 名称
            description: 描述
            buckets: 桶边界
            labels: 标签
        
        Returns:
            直方图实例
        """
        histogram = Histogram(
            name=name, 
            description=description, 
            buckets=buckets or [0.001, 0.01, 0.1, 1.0, 10.0, 60.0],
            labels=labels or {}
        )
        self.histograms[name] = histogram
        return histogram
    
    def create_summary(self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None) -> Summary:
        """
        创建摘要
        
        Args:
            name: 名称
            description: 描述
            labels: 标签
        
        Returns:
            摘要实例
        """
        summary = Summary(name=name, description=description, labels=labels or {})
        self.summaries[name] = summary
        return summary
    
    def get_counter(self, name: str) -> Optional[Counter]:
        """获取计数器"""
        return self.counters.get(name)
    
    def get_gauge(self, name: str) -> Optional[Gauge]:
        """获取仪表盘"""
        return self.gauges.get(name)
    
    def get_histogram(self, name: str) -> Optional[Histogram]:
        """获取直方图"""
        return self.histograms.get(name)
    
    def get_summary(self, name: str) -> Optional[Summary]:
        """获取摘要"""
        return self.summaries.get(name)
    
    def collect_all(self) -> Dict[str, Any]:
        """收集所有指标"""
        return {
            "counters": {
                name: {
                    "value": counter.value,
                    "description": counter.description,
                    "labels": counter.labels
                } for name, counter in self.counters.items()
            },
            "gauges": {
                name: {
                    "value": gauge.value,
                    "description": gauge.description,
                    "labels": gauge.labels
                } for name, gauge in self.gauges.items()
            },
            "histograms": {
                name: {
                    "buckets": histogram.buckets,
                    "counts": histogram.counts,
                    "sum": histogram.sum,
                    "description": histogram.description,
                    "labels": histogram.labels
                } for name, histogram in self.histograms.items()
            },
            "summaries": {
                name: {
                    "summary": summary.get_summary(),
                    "description": summary.description,
                    "labels": summary.labels
                } for name, summary in self.summaries.items()
            },
            "timestamp": time.time()
        }
    
    def reset(self):
        """重置所有指标"""
        self.counters.clear()
        self.gauges.clear()
        self.histograms.clear()
        self.summaries.clear()

# 全局指标系统实例
_metrics_instance = None

def get_metrics_system() -> MetricsSystem:
    """获取全局指标系统实例"""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = MetricsSystem()
    return _metrics_instance