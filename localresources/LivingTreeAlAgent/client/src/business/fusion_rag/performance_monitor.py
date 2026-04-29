"""
性能监控系统 (Performance Monitor)
实时追踪系统性能指标

监控维度:
- 响应时间 (P50/P95/P99)
- 各层命中率
- 缓存命中率
- LLM 调用节省
- 资源使用
"""

import time
import threading
from typing import Dict, Any, List, Optional
from collections import defaultdict, deque
from datetime import datetime


class PerformanceMonitor:
    """性能监控系统"""
    
    def __init__(
        self,
        window_size: int = 1000,
        alert_thresholds: Optional[Dict] = None
    ):
        """
        初始化性能监控
        
        Args:
            window_size: 统计窗口大小
            alert_thresholds: 告警阈值
        """
        self.window_size = window_size
        
        # 告警阈值
        self.alert_thresholds = alert_thresholds or {
            "p99_latency_ms": 500,
            "cache_hit_rate_min": 0.5,
            "error_rate_max": 0.05
        }
        
        # 数据存储
        self.query_records: deque = deque(maxlen=window_size)
        self.layer_latencies: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        
        # 统计计数器
        self.counters = defaultdict(int)
        
        # 锁
        self.lock = threading.Lock()
        
        # 告警记录
        self.alerts: List[Dict] = []
        
        print(f"[PerformanceMonitor] 初始化完成，窗口大小: {window_size}")
    
    def record_query(
        self,
        query: str,
        timings: Dict[str, float],
        cache_hit: bool = False,
        success: bool = True,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        记录查询性能
        
        Args:
            query: 查询文本
            timings: 各层耗时 {"layer_name": ms}
            cache_hit: 是否命中缓存
            success: 是否成功
            metadata: 额外元数据
        """
        with self.lock:
            record = {
                "timestamp": time.time(),
                "query": query[:100],  # 截断
                "total_latency_ms": sum(timings.values()),
                "timings": timings.copy(),
                "cache_hit": cache_hit,
                "success": success,
                "metadata": metadata or {}
            }
            
            self.query_records.append(record)
            
            # 更新各层统计
            for layer, latency in timings.items():
                self.layer_latencies[layer].append(latency)
            
            # 更新计数器
            self.counters["total_queries"] += 1
            self.counters["cache_hits" if cache_hit else "cache_misses"] += 1
            self.counters["successes" if success else "failures"] += 1
            
            # 检查告警
            self._check_alerts()
    
    def _check_alerts(self) -> None:
        """检查是否触发告警"""
        stats = self.get_stats()
        
        # P99 延迟告警
        if stats.get("p99_latency", 0) > self.alert_thresholds.get("p99_latency_ms", 500):
            self._add_alert("high_latency", f"P99延迟过高: {stats['p99_latency']:.1f}ms")
        
        # 缓存命中率告警
        if stats.get("cache_hit_rate", 1.0) < self.alert_thresholds.get("cache_hit_rate_min", 0.5):
            self._add_alert("low_cache_hit", f"缓存命中率过低: {stats['cache_hit_rate']:.1%}")
        
        # 错误率告警
        error_rate = stats.get("error_rate", 0)
        if error_rate > self.alert_thresholds.get("error_rate_max", 0.05):
            self._add_alert("high_error_rate", f"错误率过高: {error_rate:.1%}")
    
    def _add_alert(self, alert_type: str, message: str) -> None:
        """添加告警"""
        # 避免重复告警 (5分钟内)
        now = time.time()
        
        for alert in self.alerts[-5:]:  # 检查最近5条
            if alert["type"] == alert_type and (now - alert["timestamp"]) < 300:
                return
        
        self.alerts.append({
            "type": alert_type,
            "message": message,
            "timestamp": now
        })
    
    def _calculate_percentile(self, values: List[float], percentile: float) -> float:
        """计算百分位数"""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        index = min(index, len(sorted_values) - 1)
        
        return sorted_values[index]
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取性能统计
        
        Returns:
            {
                "total_queries": 1000,
                "cache_hit_rate": 0.75,
                "error_rate": 0.01,
                "avg_latency": 45.5,
                "p50_latency": 30.0,
                "p95_latency": 120.0,
                "p99_latency": 250.0,
                "avg_layer_times": {...},
                "estimated_llm_savings": 65.0
            }
        """
        with self.lock:
            total = self.counters["total_queries"]
            
            if total == 0:
                return {
                    "total_queries": 0,
                    "cache_hit_rate": 0.0,
                    "error_rate": 0.0,
                    "avg_latency": 0.0,
                    "p50_latency": 0.0,
                    "p95_latency": 0.0,
                    "p99_latency": 0.0,
                    "avg_layer_times": {},
                    "estimated_llm_savings": 0.0
                }
            
            # 计算延迟百分位数
            all_latencies = [r["total_latency_ms"] for r in self.query_records]
            
            avg_latency = sum(all_latencies) / len(all_latencies)
            p50 = self._calculate_percentile(all_latencies, 50)
            p95 = self._calculate_percentile(all_latencies, 95)
            p99 = self._calculate_percentile(all_latencies, 99)
            
            # 缓存命中率
            cache_hits = self.counters["cache_hits"]
            cache_misses = self.counters["cache_misses"]
            cache_hit_rate = cache_hits / (cache_hits + cache_misses) if (cache_hits + cache_misses) > 0 else 0
            
            # 错误率
            successes = self.counters["successes"]
            failures = self.counters["failures"]
            error_rate = failures / total if total > 0 else 0
            
            # 各层平均耗时
            avg_layer_times = {}
            for layer, latencies in self.layer_latencies.items():
                if latencies:
                    avg_layer_times[layer] = sum(latencies) / len(latencies)
            
            # 估算 LLM 调用节省
            # 假设缓存命中时不需要 LLM 调用
            estimated_llm_savings = cache_hit_rate * 70  # 假设缓存命中可节省70% LLM调用
            
            return {
                "total_queries": total,
                "cache_hit_rate": cache_hit_rate,
                "error_rate": error_rate,
                "avg_latency": avg_latency,
                "p50_latency": p50,
                "p95_latency": p95,
                "p99_latency": p99,
                "avg_layer_times": avg_layer_times,
                "estimated_llm_savings": estimated_llm_savings,
                "success_count": successes,
                "failure_count": failures
            }
    
    def get_realtime_stats(self, last_n: int = 100) -> Dict[str, Any]:
        """
        获取实时统计 (最近N条)
        
        Args:
            last_n: 最近N条记录
            
        Returns:
            实时统计数据
        """
        with self.lock:
            recent = list(self.query_records)[-last_n:]
            
            if not recent:
                return {"total": 0}
            
            latencies = [r["total_latency_ms"] for r in recent]
            cache_hits = sum(1 for r in recent if r["cache_hit"])
            
            return {
                "total": len(recent),
                "avg_latency": sum(latencies) / len(latencies),
                "max_latency": max(latencies),
                "min_latency": min(latencies),
                "cache_hit_rate": cache_hits / len(recent)
            }
    
    def get_layer_stats(self) -> Dict[str, Dict[str, float]]:
        """获取各层详细统计"""
        with self.lock:
            stats = {}
            
            for layer, latencies in self.layer_latencies.items():
                if not latencies:
                    continue
                
                sorted_latencies = sorted(latencies)
                n = len(sorted_latencies)
                
                stats[layer] = {
                    "count": n,
                    "avg": sum(latencies) / n,
                    "min": sorted_latencies[0],
                    "max": sorted_latencies[-1],
                    "p50": sorted_latencies[n // 2],
                    "p95": sorted_latencies[int(n * 0.95)],
                    "p99": sorted_latencies[int(n * 0.99)]
                }
            
            return stats
    
    def get_trend(self, bucket_size: int = 10) -> List[Dict]:
        """
        获取性能趋势
        
        Args:
            bucket_size: 桶大小 (记录数)
            
        Returns:
            趋势数据
        """
        with self.lock:
            records = list(self.query_records)
            
            if len(records) < bucket_size:
                return []
            
            trends = []
            
            for i in range(0, len(records), bucket_size):
                bucket = records[i:i + bucket_size]
                
                if not bucket:
                    continue
                
                latencies = [r["total_latency_ms"] for r in bucket]
                cache_hits = sum(1 for r in bucket if r["cache_hit"])
                
                trends.append({
                    "start_time": bucket[0]["timestamp"],
                    "end_time": bucket[-1]["timestamp"],
                    "count": len(bucket),
                    "avg_latency": sum(latencies) / len(latencies),
                    "p95_latency": self._calculate_percentile(latencies, 95),
                    "cache_hit_rate": cache_hits / len(bucket)
                })
            
            return trends
    
    def get_alerts(self, since: Optional[float] = None) -> List[Dict]:
        """
        获取告警列表
        
        Args:
            since: 时间戳 (只返回此后的告警)
            
        Returns:
            告警列表
        """
        with self.lock:
            if since is None:
                return self.alerts.copy()
            
            return [a for a in self.alerts if a["timestamp"] >= since]
    
    def clear_alerts(self) -> None:
        """清空告警"""
        with self.lock:
            self.alerts.clear()
    
    def reset(self) -> None:
        """重置所有统计"""
        with self.lock:
            self.query_records.clear()
            self.layer_latencies.clear()
            self.counters.clear()
            self.alerts.clear()
    
    def export_stats(self) -> Dict[str, Any]:
        """导出完整统计"""
        return {
            "timestamp": time.time(),
            "datetime": datetime.now().isoformat(),
            "stats": self.get_stats(),
            "layer_stats": self.get_layer_stats(),
            "recent_trend": self.get_trend(bucket_size=20),
            "alerts": self.get_alerts(since=time.time() - 3600)  # 最近1小时
        }
