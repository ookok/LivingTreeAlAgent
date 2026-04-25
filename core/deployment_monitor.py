"""
部署状态监控器
实时监控 L0-L4 模型和 Agent 的运行状态
"""

import time
import threading
from typing import Optional, List, Dict, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

from core.logger import get_logger
from core.model_layer_config import ModelTier, ServiceStatus, DeployMode
from core.deployment_engine import DeploymentEngine, get_deployment_engine


def _get_default_monitor_config() -> Dict[str, Any]:
    """从统一配置获取默认值"""
    try:
        from core.config.unified_config import get_config
        config = get_config()
        return config.get_polling_config("check")
    except Exception:
        return {"interval": 5.0, "max_wait": 60.0}


# 获取默认值
_default_monitor_config = _get_default_monitor_config()


# ── 数据结构 ────────────────────────────────────────────────────────────────

@dataclass
class TierStatus:
    """层级状态"""
    tier: ModelTier
    status: ServiceStatus
    model_name: str = ""
    memory_usage_mb: float = 0.0
    last_check: float = 0.0
    error: str = ""


@dataclass
class AgentStatus:
    """Agent 状态"""
    name: str
    status: ServiceStatus
    endpoint: str = ""
    latency_ms: float = 0.0
    last_check: float = 0.0
    error: str = ""


@dataclass
class SystemStatus:
    """系统状态"""
    timestamp: float = 0.0
    ollama_running: bool = False
    ollama_version: str = ""
    total_memory_gb: float = 0.0
    used_memory_gb: float = 0.0
    tier_status: Dict[str, TierStatus] = field(default_factory=dict)
    agent_status: Dict[str, AgentStatus] = field(default_factory=dict)


# ── 状态监控器 ──────────────────────────────────────────────────────────────

class DeploymentMonitor:
    """
    部署状态监控器
    
    功能：
    1. 实时监控 Ollama 服务状态
    2. 监控各层级模型运行状态
    3. 监控 Agent 服务状态
    4. 系统资源使用情况
    5. 告警和事件通知
    """

    def __init__(
        self,
        engine: Optional[DeploymentEngine] = None,
        check_interval: Optional[float] = None
    ):
        self.engine = engine or get_deployment_engine()
        self.check_interval = check_interval or _default_monitor_config.get("interval", 5.0)
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable[[SystemStatus], None]] = []
        self._status = SystemStatus()
        self._lock = threading.Lock()

    # ── 事件回调 ──────────────────────────────────────────────────────────────

    def add_callback(self, callback: Callable[[SystemStatus], None]):
        """添加状态更新回调"""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[SystemStatus], None]):
        """移除状态更新回调"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify_callbacks(self):
        """通知所有回调"""
        status_copy = self._get_status()
        for cb in self._callbacks:
            try:
                cb(status_copy)
            except Exception:
                pass

    # ── 状态获取 ──────────────────────────────────────────────────────────────

    def _get_status(self) -> SystemStatus:
        """获取当前状态快照"""
        with self._lock:
            return SystemStatus(
                timestamp=self._status.timestamp,
                ollama_running=self._status.ollama_running,
                ollama_version=self._status.ollama_version,
                total_memory_gb=self._status.total_memory_gb,
                used_memory_gb=self._status.used_memory_gb,
                tier_status=dict(self._status.tier_status),
                agent_status=dict(self._status.agent_status)
            )

    def get_status(self) -> SystemStatus:
        """获取当前系统状态"""
        # 立即执行一次检查
        self._check_all()
        return self._get_status()

    def get_tier_status(self, tier: ModelTier) -> TierStatus:
        """获取指定层级状态"""
        status = self.get_status()
        return status.tier_status.get(tier.value, TierStatus(
            tier=tier,
            status=ServiceStatus.STOPPED
        ))

    def get_all_tier_status(self) -> Dict[ModelTier, TierStatus]:
        """获取所有层级状态"""
        status = self.get_status()
        result = {}
        for tier in ModelTier:
            result[tier] = status.tier_status.get(
                tier.value,
                TierStatus(tier=tier, status=ServiceStatus.STOPPED)
            )
        return result

    # ── 状态检查 ──────────────────────────────────────────────────────────────

    def _check_all(self):
        """执行所有检查"""
        with self._lock:
            self._status.timestamp = time.time()
            
            # 检查 Ollama
            self._check_ollama()
            
            # 检查各层级
            self._check_tiers()
            
            # 检查系统资源
            self._check_resources()

    def _check_ollama(self):
        """检查 Ollama 服务"""
        self._status.ollama_running = self.engine.is_ollama_running()
        
        if self._status.ollama_running:
            # 获取版本
            try:
                import httpx
                resp = httpx.get(
                    f"{self.engine.config.ollama_base_url}/api/version",
                    timeout=5.0
                )
                if resp.status_code == 200:
                    self._status.ollama_version = resp.json().get("version", "")
            except Exception:
                pass

    def _check_tiers(self):
        """检查各层级状态"""
        for tier in ModelTier:
            tier_key = tier.value
            
            # 获取层级配置
            layer_config = self.engine.config.layers.get(tier_key)
            
            if not layer_config or not layer_config.model:
                self._status.tier_status[tier_key] = TierStatus(
                    tier=tier,
                    status=ServiceStatus.STOPPED,
                    last_check=time.time()
                )
                continue
            
            model_name = layer_config.model.ollama_name
            
            # 检查模型是否安装
            if not self.engine.is_model_installed(model_name):
                self._status.tier_status[tier_key] = TierStatus(
                    tier=tier,
                    status=ServiceStatus.STOPPED,
                    model_name=model_name,
                    last_check=time.time()
                )
                continue
            
            # 检查模型是否运行（通过调用测试）
            if self.engine.is_ollama_running():
                self._status.tier_status[tier_key] = TierStatus(
                    tier=tier,
                    status=ServiceStatus.RUNNING,
                    model_name=model_name,
                    last_check=time.time()
                )
            else:
                self._status.tier_status[tier_key] = TierStatus(
                    tier=tier,
                    status=ServiceStatus.ERROR,
                    model_name=model_name,
                    error="Ollama 服务未运行",
                    last_check=time.time()
                )

    def _check_resources(self):
        """检查系统资源"""
        try:
            import psutil
            mem = psutil.virtual_memory()
            self._status.total_memory_gb = mem.total / (1024**3)
            self._status.used_memory_gb = mem.used / (1024**3)
        except ImportError:
            pass

    # ── 监控控制 ──────────────────────────────────────────────────────────────

    def start_monitoring(self):
        """启动监控"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self._monitor_thread.start()

    def stop_monitoring(self):
        """停止监控"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
            self._monitor_thread = None

    def _monitor_loop(self):
        """监控循环"""
        while self._monitoring:
            self._check_all()
            self._notify_callbacks()
            time.sleep(self.check_interval)

    # ── 服务启停 ──────────────────────────────────────────────────────────────

    def start_service(self, tier: ModelTier) -> bool:
        """启动指定层级的服务"""
        result = self.engine.auto_deploy_tier(tier)
        return result.success

    def stop_service(self, tier: ModelTier) -> bool:
        """停止指定层级的服务"""
        layer_config = self.engine.config.layers.get(tier.value)
        if not layer_config or not layer_config.model:
            return False
        
        model_name = layer_config.model.ollama_name
        result = self.engine.unload_model(model_name)
        return result.success

    def restart_service(self, tier: ModelTier) -> bool:
        """重启指定层级的服务"""
        self.stop_service(tier)
        time.sleep(1)
        return self.start_service(tier)

    def start_all_services(self) -> Dict[ModelTier, bool]:
        """启动所有服务"""
        results = {}
        for tier in ModelTier:
            results[tier] = self.start_service(tier)
        return results

    def stop_all_services(self) -> Dict[ModelTier, bool]:
        """停止所有服务"""
        results = {}
        for tier in ModelTier:
            results[tier] = self.stop_service(tier)
        return results

    # ── 诊断信息 ──────────────────────────────────────────────────────────────

    def get_diagnostic_report(self) -> str:
        """获取诊断报告"""
        status = self.get_status()
        
        lines = [
            "=" * 60,
            "部署状态诊断报告",
            "=" * 60,
            f"时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(status.timestamp))}",
            "",
            "[Ollama 服务]",
            f"  运行状态: {'运行中' if status.ollama_running else '未运行'}",
            f"  版本: {status.ollama_version or '未知'}",
            "",
            "[系统资源]",
            f"  总内存: {status.total_memory_gb:.1f} GB",
            f"  已用内存: {status.used_memory_gb:.1f} GB",
            f"  使用率: {status.used_memory_gb / status.total_memory_gb * 100:.1f}%" if status.total_memory_gb > 0 else "  使用率: N/A",
            "",
            "[模型层级状态]",
        ]
        
        for tier in ModelTier:
            tier_status = status.tier_status.get(tier.value)
            if tier_status:
                status_icon = {
                    ServiceStatus.RUNNING: "✅",
                    ServiceStatus.STOPPED: "⏹️",
                    ServiceStatus.STARTING: "🔄",
                    ServiceStatus.ERROR: "❌",
                    ServiceStatus.DOWNLOADING: "📥",
                }.get(tier_status.status, "❓")
                
                lines.append(
                    f"  {tier.value} {status_icon} {tier_status.model_name or '(无模型)'} "
                    f"- {tier_status.status.value}"
                )
                if tier_status.error:
                    lines.append(f"      错误: {tier_status.error}")
        
        lines.append("")
        lines.append("=" * 60)
        
        return "\n".join(lines)


# ── 单例 ─────────────────────────────────────────────────────────────────────

_monitor: Optional[DeploymentMonitor] = None


def get_deployment_monitor() -> DeploymentMonitor:
    """获取监控器单例"""
    global _monitor
    if _monitor is None:
        _monitor = DeploymentMonitor()
    return _monitor


# ── 测试 ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    monitor = DeploymentMonitor()
    
    logger.info("=" * 60)
    logger.info("部署状态监控器测试")
    logger.info("=" * 60)
    
    # 获取诊断报告
    report = monitor.get_diagnostic_report()
    logger.info(report)
    
    # 测试回调
    def on_status_change(status: SystemStatus):
        logger.info(f"[回调] Ollama: {status.ollama_running}, 时间: {status.timestamp}")
    
    monitor.add_callback(on_status_change)
    monitor.start_monitoring()
    
    logger.info("\n监控已启动，5秒后停止...")
    time.sleep(5)
    monitor.stop_monitoring()
    
    logger.info("\n" + "=" * 60)
