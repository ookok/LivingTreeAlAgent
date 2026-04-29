"""
Network Monitoring and Self-Healing System

Network monitoring and self-healing features:
- Real-time monitoring
- Anomaly detection
- Automatic optimization
- Failure recovery
"""

import asyncio
import time
import psutil
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional, Callable, Any


@dataclass
class NetworkMonitor:
    """
    Network Status Monitor
    
    Features:
    - Real-time monitoring
    - Anomaly detection
    - Trend analysis
    - Alert system
    """
    
    node_id: str
    _running: bool = False
    _monitor_task: Optional[asyncio.Task] = None
    
    # Metrics
    _metrics: dict = field(default_factory=lambda: defaultdict(list))
    _metrics_history: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    # Alert thresholds
    ALERT_LATENCY_MS: float = 500
    ALERT_PACKET_LOSS: float = 0.05
    ALERT_CPU_PERCENT: float = 80
    ALERT_MEMORY_PERCENT: float = 90
    
    # Callbacks
    _alert_callbacks: list = field(default_factory=list)
    
    async def start(self):
        """Start monitor"""
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
    
    async def stop(self):
        """Stop monitor"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
    
    async def _monitor_loop(self):
        """Monitoring loop"""
        while self._running:
            try:
                await self._collect_metrics()
                await self._detect_anomalies()
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception:
                pass
    
    async def _collect_metrics(self):
        """Collect metrics"""
        timestamp = time.time()
        
        cpu_percent = psutil.cpu_percent(interval=0.1)
        self._metrics["cpu"].append(cpu_percent)
        
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        self._metrics["memory"].append(memory_percent)
        
        net_io = psutil.net_io_counters()
        self._metrics["bytes_sent"].append(net_io.bytes_sent)
        self._metrics["bytes_recv"].append(net_io.bytes_recv)
        
        connections = len(psutil.net_connections())
        self._metrics["connections"].append(connections)
        
        disk_io = psutil.disk_io_counters()
        if disk_io:
            self._metrics["disk_read"].append(disk_io.read_bytes)
            self._metrics["disk_write"].append(disk_io.write_bytes)
        
        self._metrics_history.append({
            "timestamp": timestamp,
            "cpu": cpu_percent,
            "memory": memory_percent,
            "connections": connections,
        })
    
    async def _detect_anomalies(self):
        """Detect anomalies"""
        alerts = []
        
        if self._metrics["cpu"]:
            avg_cpu = sum(self._metrics["cpu"][-10:]) / min(10, len(self._metrics["cpu"]))
            if avg_cpu > self.ALERT_CPU_PERCENT:
                alerts.append({
                    "type": "cpu_high",
                    "value": avg_cpu,
                    "threshold": self.ALERT_CPU_PERCENT,
                })
        
        if self._metrics["memory"]:
            avg_mem = sum(self._metrics["memory"][-10:]) / min(10, len(self._metrics["memory"]))
            if avg_mem > self.ALERT_MEMORY_PERCENT:
                alerts.append({
                    "type": "memory_high",
                    "value": avg_mem,
                    "threshold": self.ALERT_MEMORY_PERCENT,
                })
        
        if alerts:
            for callback in self._alert_callbacks:
                try:
                    await callback(alerts)
                except Exception:
                    pass
    
    def register_alert_callback(self, callback: Callable):
        """Register alert callback"""
        self._alert_callbacks.append(callback)
    
    def get_current_metrics(self) -> dict:
        """Get current metrics"""
        return {
            "cpu_percent": self._metrics["cpu"][-1] if self._metrics["cpu"] else 0,
            "memory_percent": self._metrics["memory"][-1] if self._metrics["memory"] else 0,
            "connections": self._metrics["connections"][-1] if self._metrics["connections"] else 0,
            "bytes_sent": self._metrics["bytes_sent"][-1] if self._metrics["bytes_sent"] else 0,
            "bytes_recv": self._metrics["bytes_recv"][-1] if self._metrics["bytes_recv"] else 0,
        }
    
    def get_trend(self, metric: str, duration: int = 60) -> str:
        """Get metric trend"""
        history = [
            m[metric] for m in self._metrics_history
            if time.time() - m["timestamp"] <= duration
        ]
        
        if len(history) < 2:
            return "stable"
        
        recent = history[-len(history)//2:]
        older = history[:len(history)//2]
        
        avg_recent = sum(recent) / len(recent)
        avg_older = sum(older) / len(older) if older else avg_recent
        
        if avg_recent > avg_older * 1.1:
            return "increasing"
        elif avg_recent < avg_older * 0.9:
            return "decreasing"
        else:
            return "stable"
    
    def get_state(self) -> dict:
        """Get monitor state"""
        return {
            "running": self._running,
            "metrics_collected": len(self._metrics_history),
            "current": self.get_current_metrics(),
            "trends": {
                "cpu": self.get_trend("cpu"),
                "memory": self.get_trend("memory"),
            },
        }


@dataclass
class SelfHealingManager:
    """
    Self-Healing Manager
    
    Features:
    - Failure detection
    - Automatic recovery
    - Load balancing
    - Circuit breaker
    """
    
    optimizer: Any
    _running: bool = False
    _healing_task: Optional[asyncio.Task] = None
    
    # Failure tracking
    _failure_counts: dict = field(default_factory=lambda: defaultdict(int))
    _circuit_breakers: dict = field(default_factory=lambda: defaultdict(lambda: {
        "state": "closed",
        "failure_count": 0,
        "last_failure": 0,
        "recovery_time": 0,
    }))
    
    # Thresholds
    FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_TIMEOUT: float = 60
    
    async def start(self):
        """Start self-healing"""
        self._running = True
        self._healing_task = asyncio.create_task(self._healing_loop())
    
    async def stop(self):
        """Stop self-healing"""
        self._running = False
        if self._healing_task:
            self._healing_task.cancel()
    
    async def _healing_loop(self):
        """Healing loop"""
        while self._running:
            try:
                await self._check_health()
                await self._update_circuit_breakers()
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception:
                pass
    
    async def _check_health(self):
        """Check health status"""
        pool_stats = self.optimizer.connection_pool.get_pool_stats()
        failed_connections = pool_stats["total"] - pool_stats["active"]
        
        if failed_connections > self.FAILURE_THRESHOLD:
            self._record_failure("connection_pool")
            await self._heal_connection_pool()
    
    async def _heal_connection_pool(self):
        """Heal connection pool"""
        for conn in self.optimizer.connection_pool.connections:
            if not conn.is_alive:
                await self.optimizer.connection_pool.close_connection(conn.conn_id)
        
        optimal = self.optimizer.node_grader.get_optimal_nodes(count=5)
        for node in optimal:
            if node.node_id != self.optimizer.node_id:
                await self.optimizer.connect_to_peer(node.node_id, (node.host, node.port))
    
    def _record_failure(self, component: str):
        """Record failure"""
        self._failure_counts[component] += 1
    
    async def _update_circuit_breakers(self):
        """Update circuit breakers"""
        now = time.time()
        
        for component, state in self._circuit_breakers.items():
            if state["state"] == "open":
                if now - state["last_failure"] > self.CIRCUIT_BREAKER_TIMEOUT:
                    state["state"] = "half_open"
    
    def is_circuit_open(self, component: str) -> bool:
        """Check if circuit is open"""
        state = self._circuit_breakers[component]
        return state["state"] == "open"
    
    def record_component_failure(self, component: str):
        """Record component failure"""
        state = self._circuit_breakers[component]
        state["failure_count"] += 1
        state["last_failure"] = time.time()
        
        if state["failure_count"] >= self.FAILURE_THRESHOLD:
            state["state"] = "open"
    
    def record_component_success(self, component: str):
        """Record component success"""
        state = self._circuit_breakers[component]
        state["failure_count"] = 0
        state["state"] = "closed"
    
    def get_healing_stats(self) -> dict:
        """Get healing stats"""
        return {
            "failure_counts": dict(self._failure_counts),
            "circuit_breakers": {
                k: v["state"]
                for k, v in self._circuit_breakers.items()
            },
            "running": self._running,
        }
