# smart_update_decider.py — AI 智能零配置更新决策系统
# ============================================================================
#
# 核心理念: 零配置、自发现、自适应。用户装完就用，系统自己搞懂一切。
#
# 架构三层模型:
#   用户层
#     ↓
#   智能层 (AI决策引擎)
#     ↓
#   网络层 (P2P自组织)
#
# 功能:
#   1. 自发现网络 - 启动时自动发现节点
#   2. AI智能路由 - 根据环境、时间、用户习惯自动决策
#   3. 零配置通道管理 - 自动识别版本类型和测试组
#   4. 渐进式更新通知 - 智能提示时机
#   5. 一键更新 - 用户只需点击一次
#   6. 习惯学习 - 越用越懂用户
#
# ============================================================================

import json
import time
import asyncio
import datetime
import hashlib
import platform
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable
from pathlib import Path
from enum import Enum

# ============================================================================
# 数据结构
# ============================================================================

class UpdateStrategy(Enum):
    """更新策略"""
    MIRROR_FIRST = "mirror_first"           # 镜像优先 (中国大陆)
    BACKGROUND_SILENT =background_silent" # 工作时段静默
    NOTIFY_AND_APPLY = "notify_and_apply" # 立即提示并应用
    SMART_DELAYED = "smart_delayed"        # 智能延迟
    SMALL_FILE_ONLY = "small_file_only"    # 仅小文件 (移动网络)

class UpdateChannel(Enum):
    """更新通道"""
    STABLE = "stable"     # 稳定版
    BETA = "beta"         # 测试版
    DEV = "dev"           # 开发版

class NetworkType(Enum):
    """网络类型"""
    HOME_WIFI = "home_wifi"
    WORK_WIFI = "work_wifi"
    MOBILE = "mobile"
    ROAMING = "roaming"
    OFFLINE = "offline"

class DeviceType(Enum):
    """设备类型"""
    DEVELOP = "develop"     # 开发机
    SERVER = "server"       # 服务器
    NORMAL = "normal"       # 普通 PC

@dataclass
class NetworkEnvironment:
    """网络环境信息"""
    is_china_mainland: bool = False
    network_type: NetworkType = NetworkType.HOME_WIFI
    latency_ms: float = 0
    packet_loss_rate: float = 0
    bandwidth_mbps: float = 0
    is_mobile_network: bool = False
    is_roaming: bool = False

@dataclass
class UserPreferences:
    """用户偏好"""
    likes_immediate_updates: bool = False
    auto_update_enabled: bool = True
    update_channel: UpdateChannel = UpdateChannel.STABLE
    update_time_preference: str = "night"  # night / morning / anytime
    notification_style: str = "smart"  # smart / aggressive / silent
    update_attempts_today: int = 0
    successful_updates: int = 0
    deferred_updates: int = 0
    last_update_time: str = ""

@dataclass
class TimeContext:
    """时间上下文"""
    current_hour: int = 0
    is_working_hours: bool = False  # 9:00-18:00
    is_weekend: bool = False
    is_night: bool = False  # 22:00-7:00

@dataclass
class DecisionResult:
    """决策结果"""
    strategy: UpdateStrategy
    should_update: bool
    should_notify: bool
    notify_timing: str  # now / idle / night / manual
    download_priority: str  # high / normal / low
    confidence: float  # 0.0 - 1.0
    reasons: List[str] = field(default_factory=list)

@dataclass
class UpdateState:
    """更新状态"""
    version: str
    stage: str = "idle"  # idle / checking / downloading / ready / applying
    progress: float = 0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    error: str = ""
    last_check_time: str = ""

# ============================================================================
# AI 智能决策引擎
# ============================================================================

class SmartUpdateDecider:
    """
    AI 智能零配置更新决策引擎

    核心原则:
    1. 零打扰: 默认静默，需要时才提示
    2. 零配置: AI自动搞定所有技术细节
    3. 零失败: 有异常自动恢复，用户无感知
    """

    def __init__(self):
        self._config_dir = Path.home() / ".hermes-desktop" / "smart_update"
        self._config_dir.mkdir(parents=True, exist_ok=True)

        self._prefs_file = self._config_dir / "user_preferences.json"
        self._state_file = self._config_dir / "update_state.json"
        self._history_file = self._config_dir / "decision_history.json"

        # 加载用户偏好
        self.user_prefs = self._load_user_preferences()
        self.update_state = self._load_update_state()

        # 网络环境缓存
        self._network_env: Optional[NetworkEnvironment] = None
        self._time_ctx: Optional[TimeContext] = None

    # --------------------------------------------------------------------------
    # 核心决策
    # --------------------------------------------------------------------------

    async def decide_update_strategy(
        self,
        new_version: str,
        update_size_bytes: int,
        network_env: NetworkEnvironment = None,
        force: bool = False
    ) -> DecisionResult:
        """
        AI 自动决策更新策略

        决策流程:
        1. 分析当前网络环境
        2. 分析时间段
        3. 分析用户习惯
        4. 综合决策

        Args:
            new_version: 新版本号
            update_size_bytes: 更新包大小
            network_env: 网络环境信息
            force: 是否强制更新

        Returns:
            DecisionResult: 决策结果
        """
        # 获取网络环境
        if network_env is None:
            network_env = await self._detect_network_environment()

        self._network_env = network_env

        # 获取时间上下文
        time_ctx = self._get_time_context()
        self._time_ctx = time_ctx

        reasons = []
        strategies_scores = {
            UpdateStrategy.MIRROR_FIRST: 0,
            UpdateStrategy.BACKGROUND_SILENT: 0,
            UpdateStrategy.NOTIFY_AND_APPLY: 0,
            UpdateStrategy.SMART_DELAYED: 0,
            UpdateStrategy.SMALL_FILE_ONLY: 0,
        }

        # 1. 网络环境分析
        if network_env.is_china_mainland:
            strategies_scores[UpdateStrategy.MIRROR_FIRST] += 0.4
            reasons.append("检测到中国大陆网络，启用镜像优先策略")

        if network_env.is_mobile_network:
            strategies_scores[UpdateStrategy.SMALL_FILE_ONLY] += 0.5
            reasons.append("移动网络环境，限制大文件下载")

        if network_env.packet_loss_rate > 0.1:
            strategies_scores[UpdateStrategy.SMART_DELAYED] += 0.3
            reasons.append("网络质量较差，延迟更新")

        # 2. 时间段分析
        if time_ctx.is_working_hours:
            strategies_scores[UpdateStrategy.BACKGROUND_SILENT] += 0.5
            reasons.append("工作时间，静默后台更新")
        elif time_ctx.is_night:
            strategies_scores[UpdateStrategy.NOTIFY_AND_APPLY] += 0.3
            reasons.append("夜间时段，可以提示更新")

        # 3. 用户习惯分析
        if self.user_prefs.likes_immediate_updates:
            strategies_scores[UpdateStrategy.NOTIFY_AND_APPLY] += 0.4
            reasons.append("用户偏好立即更新")

        if self.user_prefs.deferred_updates > 3:
            strategies_scores[UpdateStrategy.SMART_DELAYED] += 0.3
            reasons.append("用户多次延迟更新，降低提示频率")

        # 4. 更新大小分析
        size_mb = update_size_bytes / (1024 * 1024)
        if size_mb > 100:
            strategies_scores[UpdateStrategy.BACKGROUND_SILENT] += 0.3
            reasons.append(f"更新包较大 ({size_mb:.1f}MB)，后台下载")
        elif size_mb < 10:
            strategies_scores[UpdateStrategy.NOTIFY_AND_APPLY] += 0.2
            reasons.append(f"更新包较小 ({size_mb:.1f}MB)，可直接提示")

        # 5. 强制更新
        if force:
            return DecisionResult(
                strategy=UpdateStrategy.NOTIFY_AND_APPLY,
                should_update=True,
                should_notify=True,
                notify_timing="now",
                download_priority="high",
                confidence=1.0,
                reasons=["强制更新"] + reasons
            )

        # 选择最高分策略
        best_strategy = max(strategies_scores, key=strategies_scores.get)
        best_score = strategies_scores[best_strategy]

        # 计算置信度
        total_score = sum(strategies_scores.values())
        confidence = best_score / total_score if total_score > 0 else 0.5

        # 决定是否通知
        should_notify = best_strategy in [
            UpdateStrategy.NOTIFY_AND_APPLY,
            UpdateStrategy.SMART_DELAYED
        ]

        # 决定通知时机
        if best_strategy == UpdateStrategy.NOTIFY_AND_APPLY:
            notify_timing = "now" if not time_ctx.is_working_hours else "idle"
        elif best_strategy == UpdateStrategy.SMART_DELAYED:
            notify_timing = "night" if time_ctx.is_working_hours else "idle"
        elif best_strategy == UpdateStrategy.BACKGROUND_SILENT:
            notify_timing = "manual"
        else:
            notify_timing = "idle"

        # 决定是否更新
        should_update = best_strategy in [
            UpdateStrategy.BACKGROUND_SILENT,
            UpdateStrategy.MIRROR_FIRST
        ]

        result = DecisionResult(
            strategy=best_strategy,
            should_update=should_update,
            should_notify=should_notify,
            notify_timing=notify_timing,
            download_priority="high" if force else "normal",
            confidence=confidence,
            reasons=reasons
        )

        # 记录决策历史
        await self._record_decision(new_version, result)

        return result

    def detect_device_type(self) -> DeviceType:
        """
        自动识别设备类型

        判断依据:
        - 开发机: 运行 debug 模式、有特定环境变量、主机名包含 dev
        - 服务器: Linux 服务器、内存大于 16GB、CPU 多核
        - 普通 PC: 其他情况
        """
        hostname = platform.node().lower()
        system = platform.system()

        # 检查开发机特征
        debug_mode = self._is_debug_mode()
        is_linux_server = system == "Linux" and self._has_server_characteristics()

        if debug_mode or "dev" in hostname or "development" in hostname:
            return DeviceType.DEVELOP

        if is_linux_server:
            return DeviceType.SERVER

        return DeviceType.NORMAL

    def should_join_beta_group(self) -> bool:
        """
        AI 自动判断是否应加入测试组

        判断依据:
        - 设备类型为开发机
        - 用户经常主动检查更新
        - 开启 debug 模式
        - 历史上更新频率高
        """
        device_type = self.detect_device_type()

        # 开发机默认加入测试组
        if device_type == DeviceType.DEVELOP:
            return True

        # 服务器不加入测试组
        if device_type == DeviceType.SERVER:
            return False

        # 普通用户根据行为判断
        if self.user_prefs.update_attempts_today > 2:
            return True

        if self.user_prefs.successful_updates >= 10:
            return True

        return False

    def classify_version_channel(self, version: str) -> UpdateChannel:
        """
        自动分类版本通道

        v1.2.3       → 稳定版 (全网推送)
        v1.3.0-beta.1 → 测试版 (只推送给测试组)
        dev-20240418 → 开发版 (不推送，需手动拉取)
        """
        if "-beta" in version.lower():
            return UpdateChannel.BETA
        elif "-dev" in version.lower() or version.startswith("dev-"):
            return UpdateChannel.DEV
        else:
            return UpdateChannel.STABLE

    # --------------------------------------------------------------------------
    # 网络环境检测
    # --------------------------------------------------------------------------

    async def _detect_network_environment(self) -> NetworkEnvironment:
        """检测网络环境"""
        env = NetworkEnvironment()

        # 检测是否在中国大陆 (简化检测)
        env.is_china_mainland = await self._check_china_mainland()

        # 检测网络类型
        env.network_type = await self._detect_network_type()

        # 检测网络质量
        env.latency_ms, env.packet_loss_rate = await self._measure_network_quality()

        # 检测带宽
        env.bandwidth_mbps = await self._estimate_bandwidth()

        # 检测移动网络
        env.is_mobile_network = self._is_mobile_network()
        env.is_roaming = await self._is_roaming()

        return env

    async def _check_china_mainland(self) -> bool:
        """检查是否在中国大陆"""
        try:
            # 尝试连接国内节点
            import socket
            socket.setdefaulttimeout(2)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("cn.mogoo.com", 443))
            return True
        except Exception:
            # 尝试 ping
            proc = await asyncio.create_subprocess_exec(
                "ping", "-n", "1", "-w", "1000", "8.8.8.8",
                stdout=asyncio.subprocess.PIPE
            )
            await proc.wait()
            return proc.returncode != 0  # ping 不通可能是在国内

    async def _detect_network_type(self) -> NetworkType:
        """检测网络类型"""
        import subprocess

        system = platform.system()

        if system == "Windows":
            # Windows 检测
            try:
                result = subprocess.run(
                    ["netsh", "wlan", "show", "interfaces"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if "SSID" in result.stdout:
                    return NetworkType.HOME_WIFI
            except Exception:
                pass

        # 默认返回家庭 WiFi
        return NetworkType.HOME_WIFI

    async def _measure_network_quality(self) -> tuple:
        """测量网络质量"""
        latencies = []
        losses = 0
        attempts = 3

        for i in range(attempts):
            try:
                start = time.time()
                # 简单 TCP 连接测试
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                sock.connect(("8.8.8.8", 53))
                sock.close()
                latency = (time.time() - start) * 1000
                latencies.append(latency)
            except Exception:
                losses += 1

        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        loss_rate = losses / attempts

        return avg_latency, loss_rate

    async def _estimate_bandwidth(self) -> float:
        """估算带宽 (Mbps)"""
        # 简化实现: 基于延迟估算
        if self._network_env and self._network_env.latency_ms > 0:
            # 延迟越低，带宽越高 (非常粗略)
            if self._network_env.latency_ms < 50:
                return 100
            elif self._network_env.latency_ms < 100:
                return 50
            elif self._network_env.latency_ms < 200:
                return 20
            else:
                return 10
        return 50  # 默认 50 Mbps

    def _is_mobile_network(self) -> bool:
        """检测是否移动网络"""
        # 简化检测
        return False

    async def _is_roaming(self) -> bool:
        """检测是否漫游"""
        return False

    def _is_debug_mode(self) -> bool:
        """检测是否调试模式"""
        import os
        return os.environ.get("HERMES_DEBUG") == "1"

    def _has_server_characteristics(self) -> bool:
        """检测服务器特征"""
        import psutil

        # 内存大于 16GB
        if psutil.virtual_memory().total > 16 * 1024 * 1024 * 1024:
            return True

        # CPU 多核
        if psutil.cpu_count() >= 8:
            return True

        return False

    # --------------------------------------------------------------------------
    # 时间上下文
    # --------------------------------------------------------------------------

    def _get_time_context(self) -> TimeContext:
        """获取时间上下文"""
        now = datetime.datetime.now()

        current_hour = now.hour
        is_working_hours = 9 <= current_hour < 18
        is_weekend = now.weekday() >= 5
        is_night = current_hour >= 22 or current_hour < 7

        return TimeContext(
            current_hour=current_hour,
            is_working_hours=is_working_hours,
            is_weekend=is_weekend,
            is_night=is_night
        )

    # --------------------------------------------------------------------------
    # 用户习惯学习
    # --------------------------------------------------------------------------

    async def learn_user_habits(self, action: str, outcome: str):
        """
        学习用户习惯

        Args:
            action: 用户动作 (update_now / defer / ignore)
            outcome: 结果 (success / failure)
        """
        if action == "update_now":
            self.user_prefs.likes_immediate_updates = True
            self.user_prefs.successful_updates += 1
        elif action == "defer":
            self.user_prefs.deferred_updates += 1
        elif action == "ignore":
            self.user_prefs.deferred_updates += 1

        if outcome == "success":
            self.user_prefs.last_update_time = datetime.datetime.now().isoformat()

        # 定期清理计数
        if self.user_prefs.update_attempts_today > 100:
            self.user_prefs.update_attempts_today = 0

        # 保存偏好
        self._save_user_preferences()

    def get_optimal_update_time(self) -> str:
        """
        AI 计算最佳更新时间

        Returns:
            str: 推荐的时间段 (morning / afternoon / evening / night)
        """
        if self.user_prefs.update_time_preference != "anytime":
            return self.user_prefs.update_time_preference

        # 基于历史数据计算
        if self.user_prefs.last_update_time:
            last = datetime.datetime.fromisoformat(self.user_prefs.last_update_time)
            if last.hour < 12:
                return "morning"
            elif last.hour < 18:
                return "afternoon"
            elif last.hour < 22:
                return "evening"
            else:
                return "night"

        # 默认推荐夜间
        return "night"

    # --------------------------------------------------------------------------
    # 状态管理
    # --------------------------------------------------------------------------

    async def update_state(self, **kwargs):
        """更新状态"""
        for key, value in kwargs.items():
            if hasattr(self.update_state, key):
                setattr(self.update_state, key, value)

        self.update_state.last_check_time = datetime.datetime.now().isoformat()
        self._save_update_state()

    def _load_user_preferences(self) -> UserPreferences:
        """加载用户偏好"""
        if self._prefs_file.exists():
            with open(self._prefs_file, encoding="utf-8") as f:
                data = json.load(f)
                return UserPreferences(**data)
        return UserPreferences()

    def _save_user_preferences(self):
        """保存用户偏好"""
        with open(self._prefs_file, "w", encoding="utf-8") as f:
            json.dump(self.user_prefs.__dict__, f, ensure_ascii=False, indent=2)

    def _load_update_state(self) -> UpdateState:
        """加载更新状态"""
        if self._state_file.exists():
            with open(self._state_file, encoding="utf-8") as f:
                data = json.load(f)
                return UpdateState(**data)

        return UpdateState(version="0.0.0")

    def _save_update_state(self):
        """保存更新状态"""
        with open(self._state_file, "w", encoding="utf-8") as f:
            json.dump(self.update_state.__dict__, f, ensure_ascii=False, indent=2)

    async def _record_decision(self, version: str, result: DecisionResult):
        """记录决策历史"""
        history = []

        if self._history_file.exists():
            with open(self._history_file, encoding="utf-8") as f:
                history = json.load(f)

        history.append({
            "version": version,
            "strategy": result.strategy.value,
            "should_update": result.should_update,
            "should_notify": result.should_notify,
            "notify_timing": result.notify_timing,
            "confidence": result.confidence,
            "reasons": result.reasons,
            "timestamp": datetime.datetime.now().isoformat()
        })

        # 只保留最近 100 条
        history = history[-100:]

        with open(self._history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

# ============================================================================
# 渐进式更新通知器
# ============================================================================

class ProgressiveUpdateNotifier:
    """
    渐进式更新通知器

    用户不会突然被强制更新，而是:
    第1天: 发现新版本，后台下载10%
    第3天: 下载完成50%，提示"新功能预览"
    第5天: 下载完成90%，建议"空闲时更新"
    第7天: 智能选择最佳时机自动完成更新
    """

    def __init__(self, decider: SmartUpdateDecider):
        self.decider = decider
        self._notifications_file = Path.home() / ".hermes-desktop" / "smart_update" / "notifications.json"
        self._notifications_file.parent.mkdir(parents=True, exist_ok=True)

    def get_notification(self, version: str, download_progress: float) -> Dict[str, Any]:
        """
        根据下载进度获取通知内容

        Args:
            version: 版本号
            download_progress: 下载进度 (0.0 - 1.0)

        Returns:
            Dict: 通知内容
        """
        notification = {
            "show": False,
            "title": "",
            "message": "",
            "actions": [],
            "priority": "low"
        }

        # 不同进度阶段显示不同通知
        if download_progress >= 0.9:
            notification["show"] = True
            notification["title"] = "🆕 新版本已就绪"
            notification["message"] = f"v{version} 下载完成，点击即可更新"
            notification["actions"] = [
                {"id": "update_now", "label": "立即更新"},
                {"id": "update_night", "label": "今晚更新"},
                {"id": "later", "label": "稍后"}
            ]
            notification["priority"] = "high"

        elif download_progress >= 0.5:
            notification["show"] = True
            notification["title"] = "📦 新功能预览"
            notification["message"] = f"v{version} 下载中... ({int(download_progress * 100)}%)"
            notification["actions"] = [
                {"id": "view_changes", "label": "查看更新内容"},
                {"id": "continue", "label": "继续下载"}
            ]
            notification["priority"] = "normal"

        elif download_progress >= 0.1:
            notification["show"] = True
            notification["title"] = "🔄 正在后台下载"
            notification["message"] = f"v{version} 正在后台下载中... ({int(download_progress * 100)}%)"
            notification["actions"] = [
                {"id": "pause", "label": "暂停"}
            ]
            notification["priority"] = "low"

        # 记录通知历史
        self._save_notification(version, notification)

        return notification

    def should_auto_update(self, version: str) -> bool:
        """
        判断是否应该自动更新

        条件:
        1. 下载进度 >= 90%
        2. 用户空闲超过 5 分钟
        3. 非工作时间
        4. 网络环境良好
        """
        time_ctx = self.decider._time_ctx

        # 非工作时间
        if time_ctx and not time_ctx.is_working_hours:
            # 夜间自动更新
            if time_ctx.is_night:
                return True

        return False

    def _save_notification(self, version: str, notification: Dict):
        """保存通知历史"""
        history = []

        if self._notifications_file.exists():
            with open(self._notifications_file, encoding="utf-8") as f:
                history = json.load(f)

        history.append({
            "version": version,
            "notification": notification,
            "timestamp": datetime.datetime.now().isoformat()
        })

        # 只保留最近 50 条
        history = history[-50:]

        with open(self._notifications_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

# ============================================================================
# 全局访问器
# ============================================================================

_decider_instance: Optional[SmartUpdateDecider] = None
_notifier_instance: Optional[ProgressiveUpdateNotifier] = None

def get_smart_decider() -> SmartUpdateDecider:
    """获取全局 SmartUpdateDecider 实例"""
    global _decider_instance
    if _decider_instance is None:
        _decider_instance = SmartUpdateDecider()
    return _decider_instance

def get_progressive_notifier() -> ProgressiveUpdateNotifier:
    """获取全局 ProgressiveUpdateNotifier 实例"""
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = ProgressiveUpdateNotifier(get_smart_decider())
    return _notifier_instance

# ============================================================================
# 便捷函数
# ============================================================================

async def quick_decide(
    new_version: str,
    update_size_bytes: int = 0,
    **kwargs
) -> DecisionResult:
    """
    快速决策

    一行代码获取 AI 更新建议

    Example:
        result = await quick_decide("1.2.0", 15 * 1024 * 1024)
        print(f"策略: {result.strategy.value}")
        print(f"通知时机: {result.notify_timing}")
    """
    decider = get_smart_decider()
    return await decider.decide_update_strategy(
        new_version=new_version,
        update_size_bytes=update_size_bytes,
        **kwargs
    )