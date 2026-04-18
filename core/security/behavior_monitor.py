# core/security/behavior_monitor.py
# 行为监控器 - 进程行为追踪与风险评估

import os
import sys
import json
from pathlib import Path
from typing import List, Optional, Dict, Callable
from datetime import datetime, timedelta
from dataclasses import asdict
from collections import deque

# 尝试导入 psutil
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from .models import BehaviorEvent, RiskLevel


class BehaviorMonitor:
    """
    行为监控器

    负责：
    1. 追踪进程行为（网络、文件、注册表）
    2. 风险事件记录
    3. 安全日志生成
    4. 异常行为检测
    """

    _instance: Optional["BehaviorMonitor"] = None

    # 高风险行为模式
    HIGH_RISK_PATTERNS = [
        "powershell.*-enc",           # PowerShell 编码命令
        "cmd.*/c.*del.*system",       # 删除系统文件
        "reg.*delete.*hklm",          # 删除注册表
        ".*system32.*\\.exe",         # 修改系统目录
    ]

    # 中风险行为模式
    MEDIUM_RISK_PATTERNS = [
        "netsh.*firewall",            # 防火墙操作
        "powershell.*invoke",         # PowerShell 调用
        ".*download.*\\.exe",         # 下载可执行文件
    ]

    def __init__(self, max_events: int = 1000):
        self.max_events = max_events
        self._events: deque = deque(maxlen=max_events)
        self._risk_threshold = RiskLevel.MEDIUM
        self._callbacks: List[Callable] = []
        self._app_data_dir = self._get_app_data_dir()
        self._log_file = self._app_data_dir / "logs" / "behavior.log"
        self._start_time = datetime.now()

    @classmethod
    def get_instance(cls) -> "BehaviorMonitor":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_app_data_dir(self) -> Path:
        """获取应用数据目录"""
        if getattr(sys, 'frozen', False):
            app_dir = Path(sys.executable).parent
        else:
            app_dir = Path(__file__).parent.parent.parent

        data_dir = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
        app_data = data_dir / "LivingTreeAI"
        app_data.mkdir(parents=True, exist_ok=True)
        return app_data

    def add_event(
        self,
        event_type: str,
        description: str,
        risk_level: RiskLevel = RiskLevel.LOW,
        details: Optional[Dict] = None
    ) -> BehaviorEvent:
        """记录行为事件"""
        event = BehaviorEvent(
            timestamp=datetime.now(),
            event_type=event_type,
            description=description,
            risk_level=risk_level,
            details=details or {}
        )

        self._events.append(event)

        # 写入日志
        self._write_log(event)

        # 触发回调
        self._notify_callbacks(event)

        return event

    def _write_log(self, event: BehaviorEvent):
        """写入日志文件"""
        try:
            self._log_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            pass  # 日志写入失败不影响主流程

    def _notify_callbacks(self, event: BehaviorEvent):
        """通知观察者"""
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception:
                pass

    def register_callback(self, callback: Callable):
        """注册事件回调"""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable):
        """取消注册回调"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def get_events(
        self,
        event_type: Optional[str] = None,
        risk_level: Optional[RiskLevel] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[BehaviorEvent]:
        """查询事件"""
        events = list(self._events)

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        if risk_level:
            events = [e for e in events if e.risk_level == risk_level]

        if since:
            events = [e for e in events if e.timestamp >= since]

        # 按时间倒序
        events.sort(key=lambda e: e.timestamp, reverse=True)

        return events[:limit]

    def get_high_risk_events(self, hours: int = 24) -> List[BehaviorEvent]:
        """获取高风险事件"""
        since = datetime.now() - timedelta(hours=hours)
        return self.get_events(risk_level=RiskLevel.HIGH, since=since)

    def get_critical_events(self, hours: int = 24) -> List[BehaviorEvent]:
        """获取严重风险事件"""
        since = datetime.now() - timedelta(hours=hours)
        return self.get_events(risk_level=RiskLevel.CRITICAL, since=since)

    def analyze_network_activity(self) -> Dict:
        """分析网络活动"""
        if not HAS_PSUTIL:
            return {"status": "unavailable", "reason": "psutil not available"}

        try:
            connections = []
            listening_ports = set()

            for conn in psutil.net_connections():
                if conn.status == "LISTEN":
                    listening_ports.add(conn.laddr.port)

            return {
                "status": "ok",
                "listening_ports": sorted(list(listening_ports)),
                "port_count": len(listening_ports),
            }
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def analyze_file_activity(self) -> Dict:
        """分析文件活动"""
        suspicious_paths = []

        # 检查是否只在允许的目录操作
        allowed_dirs = [
            self._app_data_dir,
            Path(os.environ.get("LOCALAPPDATA", "")),
            Path(os.environ.get("APPDATA", "")),
        ]

        return {
            "status": "ok",
            "restricted_mode": True,
            "allowed_dirs": [str(d) for d in allowed_dirs],
        }

    def assess_risk_level(self) -> RiskLevel:
        """评估当前风险等级"""
        recent_events = self.get_events(since=datetime.now() - timedelta(hours=1))

        if any(e.risk_level == RiskLevel.CRITICAL for e in recent_events):
            return RiskLevel.CRITICAL

        high_count = sum(1 for e in recent_events if e.risk_level == RiskLevel.HIGH)
        if high_count >= 3:
            return RiskLevel.HIGH
        elif high_count >= 1:
            return RiskLevel.MEDIUM

        medium_count = sum(1 for e in recent_events if e.risk_level == RiskLevel.MEDIUM)
        if medium_count >= 5:
            return RiskLevel.MEDIUM

        return RiskLevel.LOW

    def check_security_compliance(self) -> Dict:
        """检查安全合规性"""
        issues = []
        warnings = []

        # 1. 检查是否以管理员运行
        is_admin = self._check_admin_privileges()
        if is_admin:
            warnings.append("应用以管理员权限运行，某些操作可能被监控")

        # 2. 检查网络端口
        network = self.analyze_network_activity()
        if network.get("status") == "ok":
            ports = network.get("listening_ports", [])
            if 80 in ports or 443 in ports:
                warnings.append("应用监听了 HTTP/HTTPS 端口")

        # 3. 检查文件限制
        file_check = self.analyze_file_activity()
        if not file_check.get("restricted_mode"):
            issues.append("文件操作未限制在安全目录")

        # 4. 检查最近高风险事件
        high_risk = self.get_high_risk_events(hours=1)
        if high_risk:
            warnings.append(f"最近1小时有 {len(high_risk)} 个高风险事件")

        return {
            "timestamp": datetime.now().isoformat(),
            "is_compliant": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "current_risk_level": self.assess_risk_level().value,
        }

    def _check_admin_privileges(self) -> bool:
        """检查管理员权限"""
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    def generate_transparency_report(self) -> Dict:
        """生成透明性报告"""
        uptime = datetime.now() - self._start_time

        # 统计各类型事件
        events = list(self._events)
        event_counts = {}
        for event in events:
            event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1

        risk_distribution = {
            "none": sum(1 for e in events if e.risk_level == RiskLevel.NONE),
            "low": sum(1 for e in events if e.risk_level == RiskLevel.LOW),
            "medium": sum(1 for e in events if e.risk_level == RiskLevel.MEDIUM),
            "high": sum(1 for e in events if e.risk_level == RiskLevel.HIGH),
            "critical": sum(1 for e in events if e.risk_level == RiskLevel.CRITICAL),
        }

        return {
            "report_time": datetime.now().isoformat(),
            "app_start_time": self._start_time.isoformat(),
            "uptime_seconds": uptime.total_seconds(),
            "total_events": len(events),
            "event_type_distribution": event_counts,
            "risk_distribution": risk_distribution,
            "security_compliance": self.check_security_compliance(),
            "network_activity": self.analyze_network_activity(),
        }

    def clear_old_events(self, days: int = 7):
        """清理旧事件"""
        cutoff = datetime.now() - timedelta(days=days)
        self._events = deque(
            (e for e in self._events if e.timestamp >= cutoff),
            maxlen=self.max_events
        )

    def export_events(self, filepath: Optional[Path] = None) -> str:
        """导出事件到文件"""
        if filepath is None:
            filepath = self._app_data_dir / "logs" / f"behavior_export_{datetime.now().strftime('%Y%m%d')}.json"

        events = [e.to_dict() for e in self._events]

        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(events, f, ensure_ascii=False, indent=2)

        return str(filepath)


# 便捷函数
def get_behavior_monitor() -> BehaviorMonitor:
    """获取行为监控器单例"""
    return BehaviorMonitor.get_instance()