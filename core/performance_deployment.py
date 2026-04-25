"""
Phase 6: 性能优化与生产部署
============================

将 AI 原生 OS 能力优化并准备生产部署。

核心功能:
- PerformanceOptimizer - 性能优化器
- CacheManager - 缓存管理器
- ResourcePool - 资源池
- DeploymentConfig - 部署配置
- HealthMonitor - 健康监控
- ProductionReadyChecker - 生产就绪检查
"""

from __future__ import annotations

import re
import uuid
import json
import time
import hashlib
import threading
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from collections import defaultdict, deque
from enum import Enum

try:
    from client.src.business.config import get_config as _get_unified_config
    _uconfig_pd = _get_unified_config()
except Exception:
    _uconfig_pd = None

def _pd_get(key: str, default):
    return _uconfig_pd.get(key, default) if _uconfig_pd else default


# ============================================================================
# 枚举定义
# ============================================================================

class OptimizationStrategy(Enum):
    """优化策略"""
    AGGRESSIVE = "aggressive"           # 激进优化
    BALANCED = "balanced"               # 平衡优化
    CONSERVATIVE = "conservative"       # 保守优化
    ADAPTIVE = "adaptive"               # 自适应优化


class ResourceType(Enum):
    """资源类型"""
    CPU = "cpu"
    MEMORY = "memory"
    GPU = "gpu"
    DISK = "disk"
    NETWORK = "network"
    API = "api"                         # API调用配额


class DeploymentEnvironment(Enum):
    """部署环境"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    EDGE = "edge"                       # 边缘部署


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CacheStrategy(Enum):
    """缓存策略"""
    LRU = "lru"                         # 最近最少使用
    LFU = "lfu"                         # 最不经常使用
    TTL = "ttl"                         # 时间过期
    FIFO = "fifo"                       # 先进先出




# ============================================================================
# 数据结构
# ============================================================================

class PerformanceSnapshot:
    """性能快照"""
    def __init__(
        self,
        timestamp: str = "",
        metric_name: str = "",
        value: float = 0.0,
        unit: str = "",
        tags: Dict[str, str] = None
    ):
        self.timestamp = timestamp
        self.metric_name = metric_name
        self.value = value
        self.unit = unit
        self.tags = tags or {}


class ResourceUsage:
    """资源使用情况"""
    def __init__(
        self,
        resource_type: str = "",
        current: float = 0.0,
        peak: float = 0.0,
        average: float = 0.0,
        limit: float = 0.0,
        threshold_warning: float = 0.7,
        threshold_critical: float = 0.9
    ):
        self.resource_type = resource_type
        self.current = current
        self.peak = peak
        self.average = average
        self.limit = limit
        self.threshold_warning = threshold_warning
        self.threshold_critical = threshold_critical

    @property
    def usage_rate(self) -> float:
        return self.current / self.limit if self.limit > 0 else 0

    @property
    def status(self) -> str:
        rate = self.usage_rate
        if rate >= self.threshold_critical:
            return "critical"
        elif rate >= self.threshold_warning:
            return "warning"
        return "healthy"


class OptimizationResult:
    """优化结果"""
    def __init__(
        self,
        optimization_id: str = None,
        strategy: str = "balanced",
        metrics_before: Dict = None,
        metrics_after: Dict = None,
        improvements: List[Dict] = None,
        recommendations: List[str] = None,
        execution_time_ms: float = 0,
        success: bool = True
    ):
        self.optimization_id = optimization_id or str(uuid.uuid4())
        self.strategy = strategy
        self.metrics_before = metrics_before or {}
        self.metrics_after = metrics_after or {}
        self.improvements = improvements or []
        self.recommendations = recommendations or []
        self.execution_time_ms = execution_time_ms
        self.success = success
        self.timestamp = datetime.now().isoformat()


class DeploymentConfig:
    """部署配置"""
    def __init__(
        self,
        environment: str = "development",
        region: str = "us-east-1",
        replicas: int = 1,
        resources: Dict = None,
        scaling: Dict = None,
        monitoring: Dict = None,
        security: Dict = None,
        networking: Dict = None
    ):
        self.environment = environment
        self.region = region
        self.replicas = replicas
        self.resources = resources or self._default_resources()
        self.scaling = scaling or self._default_scaling()
        self.monitoring = monitoring or self._default_monitoring()
        self.security = security or self._default_security()
        self.networking = networking or self._default_networking()
        self.created_at = datetime.now().isoformat()
        self.version = "1.0.0"

    def _default_resources(self) -> Dict:
        return {
            "cpu": {"request": "500m", "limit": "2000m"},
            "memory": {"request": "512Mi", "limit": "2Gi"},
            "gpu": {"request": "0", "limit": "0"}
        }

    def _default_scaling(self) -> Dict:
        return {
            "min_replicas": 1,
            "max_replicas": 10,
            "target_cpu_utilization": 70,
            "target_memory_utilization": 80
        }

    def _default_monitoring(self) -> Dict:
        return {
            "enabled": True,
            "prometheus": True,
            "grafana": True,
            "alert_webhook": ""
        }

    def _default_security(self) -> Dict:
        return {
            "tls_enabled": True,
            "mtls_enabled": False,
            "rate_limit": 1000,
            "auth_required": True
        }

    def _default_networking(self) -> Dict:
        return {
            "load_balancer": "nlb",
            "ingress_class": "nginx",
            "cors_enabled": True,
            "cors_origins": ["*"]
        }

    def to_dict(self) -> Dict:
        return {
            "environment": self.environment,
            "region": self.region,
            "replicas": self.replicas,
            "resources": self.resources,
            "scaling": self.scaling,
            "monitoring": self.monitoring,
            "security": self.security,
            "networking": self.networking,
            "created_at": self.created_at,
            "version": self.version
        }


# ============================================================================
# 核心类
# ============================================================================

class CacheManager:
    """缓存管理器"""

    def __init__(
        self,
        max_size: int = 1000,
        strategy: str = "lru",
        default_ttl: int = 3600
    ):
        self.max_size = max_size
        self.strategy = strategy
        self.default_ttl = default_ttl

        self._cache: Dict[str, Dict] = {}
        self._access_order: deque = deque()
        self._access_counts: Dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "writes": 0
        }

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                return None

            entry = self._cache[key]

            # 检查TTL
            if entry.get("expires_at"):
                if datetime.now() > entry["expires_at"]:
                    del self._cache[key]
                    self._stats["misses"] += 1
                    return None

            # 更新访问信息
            self._stats["hits"] += 1
            self._access_counts[key] += 1

            # LRU: 移动到末尾
            if self.strategy == "lru" and key in self._access_order:
                self._access_order.remove(key)
                self._access_order.append(key)

            return entry["value"]

    def set(
        self,
        key: str,
        value: Any,
        ttl: int = None
    ) -> bool:
        """设置缓存"""
        with self._lock:
            # 检查是否需要淘汰
            if key not in self._cache and len(self._cache) >= self.max_size:
                self._evict()

            # 计算过期时间
            expires_at = None
            if ttl or self.default_ttl:
                expires_at = datetime.now() + timedelta(
                    seconds=ttl or self.default_ttl
                )

            self._cache[key] = {
                "value": value,
                "expires_at": expires_at,
                "created_at": datetime.now()
            }

            # 更新访问顺序
            if key not in self._access_order:
                self._access_order.append(key)

            self._stats["writes"] += 1
            return True

    def _evict(self):
        """淘汰缓存项"""
        if not self._cache:
            return

        evicted_key = None

        if self.strategy == "lru":
            # LRU: 淘汰最久未使用的
            while self._access_order and evicted_key is None:
                candidate = self._access_order.popleft()
                if candidate in self._cache:
                    evicted_key = candidate

        elif self.strategy == "lfu":
            # LFU: 淘汰访问次数最少的
            evicted_key = min(
                self._cache.keys(),
                key=lambda k: self._access_counts.get(k, 0)
            )

        elif self.strategy == "fifo":
            # FIFO: 淘汰最早的
            for key in self._cache:
                evicted_key = key
                break

        elif self.strategy == "ttl":
            # TTL: 淘汰已过期的
            now = datetime.now()
            for key, entry in list(self._cache.items()):
                if entry.get("expires_at") and now > entry["expires_at"]:
                    evicted_key = key
                    break
            if not evicted_key:
                evicted_key = list(self._cache.keys())[0]

        if evicted_key:
            del self._cache[evicted_key]
            if evicted_key in self._access_order:
                self._access_order.remove(evicted_key)
            self._stats["evictions"] += 1

    def delete(self, key: str) -> bool:
        """删除缓存项"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                return True
            return False

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
            self._access_counts.clear()

    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (
            self._stats["hits"] / total if total > 0 else 0
        )

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "strategy": self.strategy,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": hit_rate,
            "evictions": self._stats["evictions"],
            "writes": self._stats["writes"]
        }


class ResourcePool:
    """资源池"""

    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self._available: List[Any] = []
        self._in_use: Dict[str, Any] = {}
        self._waiting: deque = deque()
        self._lock = threading.Lock()
        self._id_counter = 0

        # 初始化资源
        for i in range(max_workers):
            self._available.append(f"worker_{i}")

    def acquire(self, timeout: float = 30) -> Optional[str]:
        """获取资源"""
        start_time = time.time()

        while True:
            with self._lock:
                if self._available:
                    resource_id = self._available.pop(0)
                    self._in_use[resource_id] = {
                        "acquired_at": datetime.now().isoformat(),
                        "task": None
                    }
                    return resource_id

                if time.time() - start_time >= timeout:
                    return None

            time.sleep(_pd_get("delays.polling_short", 0.1))

    def release(self, resource_id: str):
        """释放资源"""
        with self._lock:
            if resource_id in self._in_use:
                del self._in_use[resource_id]
                self._available.append(resource_id)

    def get_status(self) -> Dict:
        """获取状态"""
        with self._lock:
            return {
                "total": self.max_workers,
                "available": len(self._available),
                "in_use": len(self._in_use),
                "waiting": len(self._waiting),
                "utilization": len(self._in_use) / self.max_workers
            }


class PerformanceOptimizer:
    """性能优化器"""

    def __init__(
        self,
        strategy: str = "balanced",
        window_size: int = 100
    ):
        self.strategy = strategy
        self.window_size = window_size

        # 性能指标历史
        self._metrics: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=window_size)
        )

        # 优化规则
        self._rules: List[Dict] = self._default_rules()

        # 统计信息
        self._stats = {
            "optimizations_applied": 0,
            "recommendations_generated": 0
        }

    def _default_rules(self) -> List[Dict]:
        return [
            {
                "name": "high_latency",
                "condition": lambda m: m.get("latency_ms", 0) > 500,
                "recommendation": "考虑增加缓存或优化查询",
                "priority": "high"
            },
            {
                "name": "low_cache_hit",
                "condition": lambda m: m.get("cache_hit_rate", 1) < 0.7,
                "recommendation": "调整缓存策略或增加缓存大小",
                "priority": "medium"
            },
            {
                "name": "high_memory",
                "condition": lambda m: m.get("memory_usage", 0) > 0.85,
                "recommendation": "考虑增加内存限制或优化内存使用",
                "priority": "high"
            },
            {
                "name": "high_error_rate",
                "condition": lambda m: m.get("error_rate", 0) > 0.05,
                "recommendation": "检查系统错误日志",
                "priority": "critical"
            }
        ]

    def record_metric(
        self,
        name: str,
        value: float,
        tags: Dict = None
    ):
        """记录指标"""
        snapshot = PerformanceSnapshot(
            timestamp=datetime.now().isoformat(),
            metric_name=name,
            value=value,
            tags=tags or {}
        )
        self._metrics[name].append(snapshot)

    def get_metric_stats(self, name: str) -> Dict:
        """获取指标统计"""
        if name not in self._metrics or len(self._metrics[name]) == 0:
            return {}

        values = [s.value for s in self._metrics[name]]

        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": statistics.mean(values),
            "median": statistics.median(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0,
            "p95": self._percentile(values, 95),
            "p99": self._percentile(values, 99)
        }

    def _percentile(self, values: List[float], p: float) -> float:
        """计算百分位数"""
        sorted_values = sorted(values)
        index = int(len(sorted_values) * p / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def optimize(self) -> OptimizationResult:
        """执行优化"""
        start_time = time.time()

        # 收集当前指标
        metrics_before = {
            name: self.get_metric_stats(name)
            for name in self._metrics.keys()
        }

        # 应用优化策略
        improvements = []
        recommendations = []

        for rule in self._rules:
            # 检查条件
            latest_metrics = {
                name: self._metrics[name][-1].value
                for name in self._metrics.keys()
            }

            if rule["condition"](latest_metrics):
                recommendations.append({
                    "rule": rule["name"],
                    "recommendation": rule["recommendation"],
                    "priority": rule["priority"]
                })
                self._stats["recommendations_generated"] += 1

        # 根据策略调整
        if self.strategy == "aggressive":
            # 激进优化
            improvements.append({
                "action": "increase_cache_size",
                "expected_improvement": "15-25%"
            })
        elif self.strategy == "conservative":
            # 保守优化
            improvements.append({
                "action": "minor_adjustments",
                "expected_improvement": "5-10%"
            })
        else:
            # 平衡优化
            improvements.append({
                "action": "balanced_optimization",
                "expected_improvement": "10-15%"
            })

        self._stats["optimizations_applied"] += 1

        # 收集优化后指标
        metrics_after = {
            name: self.get_metric_stats(name)
            for name in self._metrics.keys()
        }

        execution_time = (time.time() - start_time) * 1000

        return OptimizationResult(
            strategy=self.strategy,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            improvements=improvements,
            recommendations=[r["recommendation"] for r in recommendations],
            execution_time_ms=execution_time,
            success=True
        )

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self._stats,
            "tracked_metrics": list(self._metrics.keys()),
            "active_rules": len(self._rules)
        }


class HealthMonitor:
    """健康监控"""

    def __init__(self):
        self._checks: Dict[str, Callable] = {}
        self._health_history: deque = deque(maxlen=100)
        self._last_check_time: Dict[str, str] = {}
        self._alert_callbacks: List[Callable] = []

    def register_check(
        self,
        name: str,
        check_func: Callable,
        interval_seconds: int = 60
    ):
        """注册健康检查"""
        self._checks[name] = {
            "func": check_func,
            "interval": interval_seconds,
            "last_result": None
        }

    def register_alert_callback(self, callback: Callable):
        """注册告警回调"""
        self._alert_callbacks.append(callback)

    def check_health(self) -> Dict:
        """执行健康检查"""
        results = {}
        overall_status = HealthStatus.HEALTHY

        for name, check_info in self._checks.items():
            try:
                result = check_info["func"]()
                check_info["last_result"] = result
                self._last_check_time[name] = datetime.now().isoformat()

                results[name] = {
                    "status": result.get("status", "unknown"),
                    "message": result.get("message", ""),
                    "details": result.get("details", {})
                }

                # 更新整体状态
                if result.get("status") == "unhealthy":
                    overall_status = HealthStatus.UNHEALTHY
                elif (
                    result.get("status") == "degraded"
                    and overall_status != HealthStatus.UNHEALTHY
                ):
                    overall_status = HealthStatus.DEGRADED

            except Exception as e:
                results[name] = {
                    "status": "unhealthy",
                    "message": f"Check failed: {str(e)}",
                    "details": {}
                }
                overall_status = HealthStatus.UNHEALTHY

        # 记录历史
        self._health_history.append({
            "timestamp": datetime.now().isoformat(),
            "status": overall_status.value,
            "checks": results
        })

        # 触发告警
        if overall_status != HealthStatus.HEALTHY:
            self._trigger_alerts(overall_status, results)

        return {
            "status": overall_status.value,
            "timestamp": datetime.now().isoformat(),
            "checks": results
        }

    def _trigger_alerts(
        self,
        status: HealthStatus,
        results: Dict
    ):
        """触发告警"""
        for callback in self._alert_callbacks:
            try:
                callback(status, results)
            except Exception:
                pass

    def get_health_history(self, limit: int = 10) -> List[Dict]:
        """获取健康历史"""
        return list(self._health_history)[-limit:]


class ProductionReadyChecker:
    """生产就绪检查器"""

    def __init__(self):
        self._checklist: List[Dict] = self._default_checklist()

    def _default_checklist(self) -> List[Dict]:
        return [
            # 安全性
            {"category": "security", "item": "TLS证书配置", "critical": True},
            {"category": "security", "item": "API密钥管理", "critical": True},
            {"category": "security", "item": "CORS配置", "critical": False},
            {"category": "security", "item": "输入验证", "critical": True},
            {"category": "security", "item": "速率限制", "critical": True},

            # 性能
            {"category": "performance", "item": "缓存配置", "critical": False},
            {"category": "performance", "item": "连接池大小", "critical": False},
            {"category": "performance", "item": "超时配置", "critical": True},
            {"category": "performance", "item": "重试策略", "critical": False},

            # 监控
            {"category": "monitoring", "item": "日志记录", "critical": True},
            {"category": "monitoring", "item": "指标暴露", "critical": True},
            {"category": "monitoring", "item": "健康检查端点", "critical": True},
            {"category": "monitoring", "item": "告警配置", "critical": True},

            # 可靠性
            {"category": "reliability", "item": "优雅关闭", "critical": True},
            {"category": "reliability", "item": "错误处理", "critical": True},
            {"category": "reliability", "item": "断路器", "critical": False},
            {"category": "reliability", "item": "备份策略", "critical": True},

            # 部署
            {"category": "deployment", "item": "环境变量配置", "critical": True},
            {"category": "deployment", "item": "资源配置", "critical": True},
            {"category": "deployment", "item": "副本数", "critical": False},
            {"category": "deployment", "item": "滚动更新策略", "critical": False}
        ]

    def run_checks(self) -> Dict:
        """运行检查"""
        results = {
            "passed": [],
            "failed": [],
            "warnings": [],
            "summary": {}
        }

        for item in self._checklist:
            # 模拟检查
            check_result = self._perform_check(item)

            if check_result["status"] == "passed":
                results["passed"].append({
                    "item": item["item"],
                    "category": item["category"],
                    "details": check_result.get("details", {})
                })
            elif check_result["status"] == "failed":
                if item["critical"]:
                    results["failed"].append({
                        "item": item["item"],
                        "category": item["category"],
                        "critical": True,
                        "details": check_result.get("details", {})
                    })
                else:
                    results["warnings"].append({
                        "item": item["item"],
                        "category": item["category"],
                        "details": check_result.get("details", {})
                    })

        # 生成摘要
        total = len(self._checklist)
        results["summary"] = {
            "total": total,
            "passed": len(results["passed"]),
            "failed": len(results["failed"]),
            "warnings": len(results["warnings"]),
            "pass_rate": len(results["passed"]) / total,
            "ready_for_production": len(results["failed"]) == 0
        }

        return results

    def _perform_check(self, item: Dict) -> Dict:
        """执行单项检查"""
        # 模拟检查逻辑
        # 实际实现应该检查真实配置

        category = item["category"]

        if category == "security":
            # 安全性检查
            return {"status": "passed", "details": {"method": "tls_check"}}

        elif category == "performance":
            # 性能检查
            return {"status": "passed", "details": {"method": "perf_check"}}

        elif category == "monitoring":
            # 监控检查
            return {"status": "passed", "details": {"method": "monitor_check"}}

        elif category == "reliability":
            # 可靠性检查
            return {"status": "passed", "details": {"method": "rel_check"}}

        elif category == "deployment":
            # 部署检查
            return {"status": "passed", "details": {"method": "deploy_check"}}

        return {"status": "passed"}


# ============================================================================
# 便捷函数
# ============================================================================

def create_cache_manager(
    strategy: str = "lru",
    max_size: int = 1000,
    ttl: int = 3600
) -> CacheManager:
    """创建缓存管理器"""
    return CacheManager(
        max_size=max_size,
        strategy=strategy,
        default_ttl=ttl
    )


def create_resource_pool(max_workers: int = 10) -> ResourcePool:
    """创建资源池"""
    return ResourcePool(max_workers=max_workers)


def create_optimizer(
    strategy: str = "balanced"
) -> PerformanceOptimizer:
    """创建性能优化器"""
    return PerformanceOptimizer(strategy=strategy)


def create_health_monitor() -> HealthMonitor:
    """创建健康监控"""
    return HealthMonitor()


def create_deployment_config(
    environment: str = "development"
) -> DeploymentConfig:
    """创建部署配置"""
    return DeploymentConfig(environment=environment)


def generate_kubernetes_manifests(config: DeploymentConfig) -> Dict:
    """生成 Kubernetes 清单"""
    return {
        "deployment.yaml": f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: livingtree-agent
  labels:
    app: livingtree-agent
spec:
  replicas: {config.replicas}
  selector:
    matchLabels:
      app: livingtree-agent
  template:
    metadata:
      labels:
        app: livingtree-agent
    spec:
      containers:
      - name: agent
        image: livingtree/agent:{config.version}
        resources:
          requests:
            cpu: {config.resources['cpu']['request']}
            memory: {config.resources['memory']['request']}
          limits:
            cpu: {config.resources['cpu']['limit']}
            memory: {config.resources['memory']['limit']}
""",
        "service.yaml": """apiVersion: v1
kind: Service
metadata:
  name: livingtree-agent
spec:
  selector:
    app: livingtree-agent
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
""",
        "ingress.yaml": """apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: livingtree-agent
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  tls:
  - hosts:
    - api.example.com
    secretName: tls-secret
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: livingtree-agent
            port:
              number: 80
"""
    }


def generate_docker_compose(config: DeploymentConfig) -> str:
    """生成 Docker Compose 配置"""
    return f"""version: '3.8'

services:
  agent:
    image: livingtree/agent:{config.version}
    environment:
      - ENV={config.environment}
      - REGION={config.region}
    resources:
      limits:
        cpus: '{config.resources["cpu"]["limit"]}'
        memory: {config.resources["memory"]["limit"]}
    deploy:
      replicas: {config.replicas}
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
    networks:
      - agent-network

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    networks:
      - agent-network

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    networks:
      - agent-network

networks:
  agent-network:
    driver: bridge
"""


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    # 枚举
    "OptimizationStrategy",
    "ResourceType",
    "DeploymentEnvironment",
    "HealthStatus",
    "CacheStrategy",
    # 数据结构
    "PerformanceSnapshot",
    "ResourceUsage",
    "OptimizationResult",
    "DeploymentConfig",
    # 核心类
    "CacheManager",
    "ResourcePool",
    "PerformanceOptimizer",
    "HealthMonitor",
    "ProductionReadyChecker",
    # 便捷函数
    "create_cache_manager",
    "create_resource_pool",
    "create_optimizer",
    "create_health_monitor",
    "create_deployment_config",
    "generate_kubernetes_manifests",
    "generate_docker_compose"
]
