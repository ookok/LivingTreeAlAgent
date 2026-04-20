"""
指标收集器

负责收集和管理 CDN 系统的性能指标
"""

from __future__ import annotations

import time
from typing import Dict, List, Any


class MetricsCollector:
    """
    指标收集器
    负责收集和管理 CDN 系统的性能指标
    """
    
    def __init__(self):
        self.metrics: Dict[str, List[Dict[str, Any]]] = {}
        self.start_time = time.time()
    
    def record_metric(self, metric_name: str, value: Any, tags: Dict[str, str] = None):
        """
        记录指标
        
        Args:
            metric_name: 指标名称
            value: 指标值
            tags: 指标标签
        """
        if metric_name not in self.metrics:
            self.metrics[metric_name] = []
        
        self.metrics[metric_name].append({
            "timestamp": time.time(),
            "value": value,
            "tags": tags or {}
        })
    
    def get_metric(self, metric_name: str, limit: int = None) -> List[Dict[str, Any]]:
        """
        获取指标
        
        Args:
            metric_name: 指标名称
            limit: 返回的最大数量
            
        Returns:
            指标列表
        """
        if metric_name not in self.metrics:
            return []
        
        if limit:
            return self.metrics[metric_name][-limit:]
        return self.metrics[metric_name]
    
    def get_metrics(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取所有指标
        
        Returns:
            所有指标字典
        """
        return self.metrics
    
    def clear_metrics(self, metric_name: str = None):
        """
        清除指标
        
        Args:
            metric_name: 指标名称，如果为 None 则清除所有指标
        """
        if metric_name:
            if metric_name in self.metrics:
                del self.metrics[metric_name]
        else:
            self.metrics.clear()
    
    def get_aggregated_metrics(self) -> Dict[str, Any]:
        """
        获取聚合指标
        
        Returns:
            聚合指标字典
        """
        aggregated = {
            "uptime": time.time() - self.start_time,
            "metrics_count": sum(len(values) for values in self.metrics.values())
        }
        
        # 计算一些基本的聚合统计
        for metric_name, values in self.metrics.items():
            if values:
                # 计算平均值
                if all(isinstance(v["value"], (int, float)) for v in values):
                    avg_value = sum(v["value"] for v in values) / len(values)
                    max_value = max(v["value"] for v in values)
                    min_value = min(v["value"] for v in values)
                    
                    aggregated[f"{metric_name}_avg"] = avg_value
                    aggregated[f"{metric_name}_max"] = max_value
                    aggregated[f"{metric_name}_min"] = min_value
                    aggregated[f"{metric_name}_count"] = len(values)
        
        return aggregated
    
    def record_cache_hit(self):
        """
        记录缓存命中
        """
        self.record_metric("cache_hit", 1)
    
    def record_cache_miss(self):
        """
        记录缓存未命中
        """
        self.record_metric("cache_miss", 1)
    
    def record_data_transfer(self, size: int):
        """
        记录数据传输
        
        Args:
            size: 传输数据大小（字节）
        """
        self.record_metric("data_transfer", size)
    
    def record_request_latency(self, latency: float):
        """
        记录请求延迟
        
        Args:
            latency: 延迟（毫秒）
        """
        self.record_metric("request_latency", latency)
    
    def record_node_latency(self, node_id: str, latency: float):
        """
        记录节点延迟
        
        Args:
            node_id: 节点 ID
            latency: 延迟（毫秒）
        """
        self.record_metric("node_latency", latency, {"node_id": node_id})
