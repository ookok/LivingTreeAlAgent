"""
状态监控服务 - Status Monitor Service
实时监控系统状态: 网络质量、节点状态、传输进度、硬件状态

功能:
1. 网络质量监控 (RTT/丢包/抖动)
2. 节点在线状态追踪
3. 文件传输进度
4. 通话状态
5. 硬件状态 (CPU/内存/电池)
"""

import time
import asyncio
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

try:
    import psutil
except ImportError:
    psutil = None

try:
    import socketio
except ImportError:
    socketio = None

from .models import NetworkStatus, OnlineStatus, ConnectionQuality, CallSession


class HardwareStatus(str, Enum):
    """硬件状态"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class TransferProgress:
    """传输进度"""
    transfer_id: str
    file_name: str
    total_size: int
    transferred: int
    speed: float = 0              # bytes/s
    status: str = "pending"       # pending/transferring/completed/failed
    started_at: float = 0
    completed_at: float = 0
    error: str = ""

    @property
    def progress(self) -> float:
        """获取进度百分比"""
        if self.total_size == 0:
            return 0
        return min(100, (self.transferred / self.total_size) * 100)

    @property
    def remaining_time(self) -> float:
        """预估剩余时间 (秒)"""
        if self.speed == 0:
            return 0
        remaining = self.total_size - self.transferred
        return remaining / self.speed

    def get_progress_str(self) -> str:
        """获取进度字符串"""
        if self.status == "completed":
            return "完成"
        elif self.status == "failed":
            return f"失败: {self.error}"
        elif self.status == "pending":
            return "等待中..."
        else:
            speed_mb = self.speed / (1024 * 1024)
            eta = self.remaining_time
            if eta > 60:
                eta_str = f"{int(eta / 60)}分"
            else:
                eta_str = f"{int(eta)}秒"
            return f"{self.progress:.1f}% ({speed_mb:.1f}MB/s, 剩余{eta_str})"


@dataclass
class SystemStatus:
    """系统状态"""
    cpu_percent: float = 0
    memory_percent: float = 0
    memory_used: int = 0           # bytes
    memory_total: int = 0
    battery_percent: Optional[int] = None
    battery_charging: bool = False
    disk_percent: float = 0
    uptime: float = 0              # 运行时间 (秒)


class StatusMonitor:
    """
    状态监控服务

    参考 Element/Discord 的状态栏设计:
    - Discord: 右下角显示语音连接状态、CPU/内存
    - Element: 底部显示网络质量、同步状态

    监控项:
    1. 网络状态 (连接模式、RTT、丢包)
    2. 节点状态 (在线/离线/离开)
    3. 传输进度 (文件上传下载)
    4. 通话状态 (语音/视频)
    5. 系统资源 (CPU/内存/电池)
    """

    def __init__(self, update_interval: float = 2.0):
        """
        Args:
            update_interval: 更新间隔 (秒)
        """
        self.update_interval = update_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # 状态数据
        self.network_status = NetworkStatus()
        self.system_status = SystemStatus()
        self.peer_statuses: Dict[str, OnlineStatus] = {}
        self.transfer_progress: Dict[str, TransferProgress] = {}
        self.active_call: Optional[CallSession] = None

        # RTT 历史 (用于抖动计算)
        self._rtt_history = deque(maxlen=50)

        # 回调函数
        self._callbacks: List[Callable] = []

        # 上次状态 (用于变化检测)
        self._last_network_status: Optional[NetworkStatus] = None
        self._last_system_status: Optional[SystemStatus] = None

    def add_callback(self, callback: Callable):
        """添加状态更新回调"""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable):
        """移除回调"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify_callbacks(self):
        """通知所有回调"""
        for cb in self._callbacks:
            try:
                cb(self)
            except Exception as e:
                print(f"[StatusMonitor] Callback error: {e}")

    async def start(self):
        """启动监控"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())

    async def stop(self):
        """停止监控"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self):
        """监控主循环"""
        boot_time = time.time()
        while self._running:
            try:
                # 更新系统状态
                self._update_system_status(boot_time)

                # 检查变化并通知
                if self._has_changes():
                    self._notify_callbacks()

                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[StatusMonitor] Monitor error: {e}")

    def _has_changes(self) -> bool:
        """检查状态是否有变化"""
        # 网络状态变化
        if self._last_network_status:
            if (self.network_status.mode != self._last_network_status.mode or
                self.network_status.rtt != self._last_network_status.rtt or
                self.network_status.connected != self._last_network_status.connected):
                self._last_network_status = NetworkStatus(
                    connected=self.network_status.connected,
                    mode=self.network_status.mode,
                    rtt=self.network_status.rtt,
                    relay_server=self.network_status.relay_server,
                    packet_loss=self.network_status.packet_loss,
                    jitter=self.network_status.jitter
                )
                return True

        # 系统状态变化
        if self._last_system_status:
            if (abs(self.system_status.cpu_percent - self._last_system_status.cpu_percent) > 1 or
                abs(self.system_status.memory_percent - self._last_system_status.memory_percent) > 1):
                self._last_system_status = SystemStatus(
                    cpu_percent=self.system_status.cpu_percent,
                    memory_percent=self.system_status.memory_percent,
                    memory_used=self.system_status.memory_used,
                    memory_total=self.system_status.memory_total,
                    battery_percent=self.system_status.battery_percent,
                    battery_charging=self.system_status.battery_charging,
                    disk_percent=self.system_status.disk_percent,
                    uptime=self.system_status.uptime
                )
                return True

        return False

    def _update_system_status(self, boot_time: float):
        """更新系统状态"""
        if psutil is None:
            return

        # CPU
        try:
            self.system_status.cpu_percent = psutil.cpu_percent(interval=0.1)
        except Exception:
            pass

        # 内存
        try:
            mem = psutil.virtual_memory()
            self.system_status.memory_percent = mem.percent
            self.system_status.memory_used = mem.used
            self.system_status.memory_total = mem.total
        except Exception:
            pass

        # 电池
        try:
            battery = psutil.sensors_battery()
            if battery:
                self.system_status.battery_percent = int(battery.percent)
                self.system_status.battery_charging = battery.power_plugged
        except Exception:
            pass

        # 磁盘
        try:
            disk = psutil.disk_usage('/')
            self.system_status.disk_percent = disk.percent
        except Exception:
            pass

        # 运行时间
        self.system_status.uptime = time.time() - boot_time

    # ============ 网络状态 ============

    def update_network_status(self,
                              connected: bool,
                              mode: str,
                              relay_server: str = "",
                              rtt: float = 0,
                              packet_loss: float = 0):
        """更新网络状态"""
        # 记录 RTT 历史
        if rtt > 0:
            self._rtt_history.append(rtt)

        # 计算抖动
        jitter = 0
        if len(self._rtt_history) >= 2:
            import statistics
            jitter = statistics.stdev(self._rtt_history) if len(self._rtt_history) > 1 else 0

        self.network_status = NetworkStatus(
            connected=connected,
            mode=mode,
            relay_server=relay_server,
            rtt=rtt,
            packet_loss=packet_loss,
            jitter=jitter
        )
        self._notify_callbacks()

    def get_connection_quality(self) -> ConnectionQuality:
        """根据 RTT 获取连接质量"""
        rtt = self.network_status.rtt
        if rtt < 50:
            return ConnectionQuality.EXCELLENT
        elif rtt < 150:
            return ConnectionQuality.GOOD
        elif rtt < 300:
            return ConnectionQuality.FAIR
        else:
            return ConnectionQuality.POOR

    def get_quality_icon(self) -> str:
        """获取连接质量图标"""
        return {
            ConnectionQuality.EXCELLENT: "🟢",
            ConnectionQuality.GOOD: "🟡",
            ConnectionQuality.FAIR: "🟠",
            ConnectionQuality.POOR: "🔴"
        }.get(self.get_connection_quality(), "⚪")

    # ============ 节点状态 ============

    def update_peer_status(self, node_id: str, status: OnlineStatus, last_seen: float = 0):
        """更新节点状态"""
        self.peer_statuses[node_id] = status
        if last_seen > 0:
            # 更新节点的 last_seen
            pass

    def get_peer_status(self, node_id: str) -> OnlineStatus:
        """获取节点状态"""
        return self.peer_statuses.get(node_id, OnlineStatus.OFFLINE)

    def get_peer_status_icon(self, node_id: str) -> str:
        """获取节点状态图标"""
        status = self.get_peer_status(node_id)
        return {
            OnlineStatus.ONLINE: "🟢",
            OnlineStatus.OFFLINE: "⚪",
            OnlineStatus.AWAY: "🟡",
            OnlineStatus.BUSY: "🔴",
            OnlineStatus.DO_NOT_DISTURB: "🔴"
        }.get(status, "⚪")

    # ============ 传输进度 ============

    def start_transfer(self, transfer_id: str, file_name: str, total_size: int):
        """开始传输"""
        self.transfer_progress[transfer_id] = TransferProgress(
            transfer_id=transfer_id,
            file_name=file_name,
            total_size=total_size,
            transferred=0,
            status="transferring",
            started_at=time.time()
        )
        self._notify_callbacks()

    def update_transfer(self, transfer_id: str, transferred: int, speed: float = 0):
        """更新传输进度"""
        if transfer_id in self.transfer_progress:
            self.transfer_progress[transfer_id].transferred = transferred
            self.transfer_progress[transfer_id].speed = speed
            self._notify_callbacks()

    def complete_transfer(self, transfer_id: str):
        """完成传输"""
        if transfer_id in self.transfer_progress:
            self.transfer_progress[transfer_id].status = "completed"
            self.transfer_progress[transfer_id].completed_at = time.time()
            self.transfer_progress[transfer_id].transferred = \
                self.transfer_progress[transfer_id].total_size
            self._notify_callbacks()

    def fail_transfer(self, transfer_id: str, error: str):
        """传输失败"""
        if transfer_id in self.transfer_progress:
            self.transfer_progress[transfer_id].status = "failed"
            self.transfer_progress[transfer_id].error = error
            self._notify_callbacks()

    def get_active_transfers(self) -> List[TransferProgress]:
        """获取活跃传输"""
        return [t for t in self.transfer_progress.values()
                if t.status in ("pending", "transferring")]

    def get_transfer_progress(self, transfer_id: str) -> Optional[TransferProgress]:
        """获取传输进度"""
        return self.transfer_progress.get(transfer_id)

    # ============ 通话状态 ============

    def start_call(self, peer_id: str, call_type: str = "voice") -> CallSession:
        """开始通话"""
        self.active_call = CallSession(
            peer_id=peer_id,
            call_type=call_type,
            status="calling",
            started_at=time.time()
        )
        self._notify_callbacks()
        return self.active_call

    def update_call_status(self, status: str):
        """更新通话状态"""
        if self.active_call:
            self.active_call.status = status
            self._notify_callbacks()

    def end_call(self):
        """结束通话"""
        if self.active_call:
            self.active_call.status = "ended"
            self.active_call.duration = time.time() - self.active_call.started_at
            self._notify_callbacks()
            self.active_call = None

    # ============ 状态显示 ============

    def get_status_bar_info(self) -> Dict[str, str]:
        """获取状态栏信息 (用于 UI 显示)"""
        info = {
            "connection_icon": "🟢" if self.network_status.connected else "⚪",
            "connection_mode": {
                "p2p": "P2P直连",
                "relay": f"中继 {self.network_status.relay_server}",
                "offline": "离线"
            }.get(self.network_status.mode, "未知"),
            "quality_icon": self.get_quality_icon(),
            "rtt": f"RTT: {self.network_status.rtt:.0f}ms",
            "cpu": f"CPU: {self.system_status.cpu_percent:.0f}%",
            "memory": f"内存: {self.system_status.memory_percent:.0f}%",
        }

        # 电池状态
        if self.system_status.battery_percent is not None:
            bat_icon = "🔌" if self.system_status.battery_charging else "🔋"
            info["battery"] = f"{bat_icon} {self.system_status.battery_percent}%"

        # 通话状态
        if self.active_call and self.active_call.status == "connected":
            duration = time.time() - self.active_call.started_at
            info["call"] = f"📞 {int(duration/60):02d}:{int(duration%60):02d}"

        # 传输状态
        active = self.get_active_transfers()
        if active:
            info["transfers"] = f"📤 {len(active)} 个传输中"

        return info

    def get_network_diagnostic(self) -> str:
        """获取网络诊断报告"""
        lines = [
            f"连接状态: {'在线' if self.network_status.connected else '离线'}",
            f"传输模式: {self.get_status_bar_info()['connection_mode']}",
            f"连接质量: {self.get_connection_quality().value}",
            f"RTT: {self.network_status.rtt:.0f}ms",
            f"抖动: {self.network_status.jitter:.0f}ms",
            f"丢包率: {self.network_status.packet_loss:.1f}%",
        ]
        if self.network_status.bandwidth_up > 0:
            lines.append(f"上行带宽: {self.network_status.bandwidth_up:.1f}Mbps")
        if self.network_status.bandwidth_down > 0:
            lines.append(f"下行带宽: {self.network_status.bandwidth_down:.1f}Mbps")
        return "\n".join(lines)


# 单例
_status_monitor: Optional[StatusMonitor] = None


def get_status_monitor() -> StatusMonitor:
    """获取状态监控服务单例"""
    global _status_monitor
    if _status_monitor is None:
        _status_monitor = StatusMonitor()
    return _status_monitor
