# -*- coding: utf-8 -*-
"""
Relay Router 统一常量配置
===========================

集中管理 relay_router 子模块的所有硬编码默认值。
所有子模块从此文件导入默认值，确保修改一处即可全局生效。

设计原则：
- 所有值都有合理的默认值（与原代码保持一致）
- 支持被 unified_config 覆盖
- 按功能分组，便于查找

Author: LivingTreeAI Team
Version: 1.0.0
"""

# ── 连接阶段超时（秒）───────────────────────────────────────────────

STAGE_TIMEOUTS = {
    "private_server": 5,
    "public_signaling": 10,
    "public_stun": 5,
    "p2p_direct": 15,
    "public_turn": 10,
    "storage_relay": 30,
}
STAGE_TIMEOUT_DEFAULT = 10  # 未匹配阶段的兜底

# ── 各阶段最大重试次数 ─────────────────────────────────────────────

MAX_RETRIES = {
    "private_server": 2,
    "public_signaling": 3,
    "public_stun": 2,
    "p2p_direct": 1,
    "public_turn": 2,
    "storage_relay": 1,
}
MAX_RETRIES_DEFAULT = 1  # 兜底

# ── 循环间隔（秒）────────────────────────────────────────────────────

HEALTH_CHECK_INTERVAL = 5         # 健康检查间隔（已连接状态）
DEGRADED_RECOVER_INTERVAL = 10   # 降级恢复尝试间隔
OFFLINE_CHECK_INTERVAL = 30      # 离线模式检查恢复间隔
RECONNECT_WAIT = 5               # 重连等待时间
UPGRADE_CHECK_INTERVAL = 60      # 升级检测间隔（私有服务器是否恢复）
NAT_TRAVERSE_DELAY = 1           # NAT穿透模拟延迟

# ── 健康监控 ────────────────────────────────────────────────────────

HEARTBEAT_DEFAULT_INTERVAL = 30  # 心跳检测间隔
HEARTBEAT_FAST_INTERVAL = 5      # 快速心跳（有失败时）

# 阈值
LATENCY_THRESHOLD_MS = 500          # 延迟告警阈值
SUCCESS_RATE_THRESHOLD = 0.8       # 成功率告警阈值
CONSECUTIVE_FAILURE_THRESHOLD = 3  # 连续失败告警阈值
RECOVERY_CHECK_COUNT = 3          # 恢复确认次数
MAX_HISTORY_SIZE = 100            # 历史数据保留条数
ALERT_COOLDOWN_SECONDS = 300      # 告警冷却时间(5分钟)

# Socket/HTTP 探测超时
SOCKET_TIMEOUT_STUN = 5           # STUN TCP 探测超时
SOCKET_TIMEOUT_TURN = 5           # TURN TCP 探测超时
SOCKET_TIMEOUT_TCP = 5            # 通用 TCP 探测超时
HTTP_TIMEOUT_SIGNALING = 5        # 信令 HTTP HEAD 探测超时
HTTP_TIMEOUT_STORAGE = 10        # 存储 HTTP 探测超时
MONITOR_STOP_TIMEOUT = 5          # 停止监控线程 join 超时

# ── 智能路由器 ──────────────────────────────────────────────────────

ROUTER_CACHE_TTL = 10              # 路由缓存有效期（秒）
ROUTER_MAX_FAILURE_HISTORY = 10   # 失败历史上限

# 连接类型权重（按类型）
CONNECTION_WEIGHTS = {
    "p2p_signaling": {
        "latency": 0.4, "reliability": 0.4, "privacy": 0.2,
        "cost": 0.0, "bandwidth": 0.0,
    },
    "p2p_direct": {
        "latency": 0.5, "reliability": 0.3, "privacy": 0.2,
        "cost": 0.0, "bandwidth": 0.0,
    },
    "file_sync": {
        "latency": 0.2, "reliability": 0.2, "privacy": 0.1,
        "cost": 0.2, "bandwidth": 0.3,
    },
    "state_sync": {
        "latency": 0.5, "reliability": 0.3, "privacy": 0.2,
        "cost": 0.0, "bandwidth": 0.0,
    },
    "backup": {
        "latency": 0.0, "reliability": 0.6, "privacy": 0.1,
        "cost": 0.3, "bandwidth": 0.0,
    },
}
DEFAULT_WEIGHTS = {
    "latency": 0.3, "reliability": 0.3, "privacy": 0.2,
    "cost": 0.1, "bandwidth": 0.1,
}

# ── 沙箱执行器 ──────────────────────────────────────────────────────

SANDBOX_MAX_STEPS = 100             # 最大执行步数
SANDBOX_TIMEOUT_SECONDS = 300       # 总超时（秒）
SANDBOX_MEMORY_LIMIT_MB = 512      # 内存限制(MB)
SANDBOX_CPU_LIMIT = 1.0            # CPU限制(核)
SANDBOX_DISK_LIMIT_GB = 5           # 磁盘限制(GB)
SANDBOX_EXECUTE_TIMEOUT = 60        # execute_sandbox 接口超时
SANDBOX_DOCKER_EXEC_CAP = 60      # Docker 执行硬上限
SANDBOX_SIM_DURATION_MS = 100      # 模拟步骤固定耗时(ms)

# ── Vheer 客户端 ──────────────────────────────────────────────────────

VHEER_DEFAULT_BASE_URL = "https://api.vheer.com/v1"
VHEER_DEFAULT_TIMEOUT = 120          # API 请求超时(秒)
VHEER_RATE_LIMIT_INTERVAL = 1.0     # 速率限制间隔(秒)
VHEER_DOWNLOAD_TIMEOUT = 300       # 下载超时(秒)
VHEER_POLL_IMAGE_INTERVAL = 2     # 图像轮询间隔(秒)
VHEER_POLL_IMAGE_MAX_WAIT = 120   # 图像最大等待(秒)
VHEER_POLL_VIDEO_INTERVAL = 3      # 视频轮询间隔(秒)
VHEER_POLL_VIDEO_MAX_WAIT = 360    # 视频最大等待(秒)

# ── 通用延迟配置 ────────────────────────────────────────────────────

POLLING_SHORT_DELAY = 0.1           # 短暂停轮询(秒)
DEPLOY_STEP_MAX = 1                 # 部署模拟步骤最大延迟(秒)
TIMEOUT_QUICK = 5                   # Docker 探测等快速操作超时(秒)
TIME_PER_LINE_ESTIMATE = 0.5        # 每行脚本估算耗时系数


def get_relay_default(key: str, default=None):
    """
    获取中继默认值
    
    用法: from core.relay_router.relay_constants import get_relay_default
         timeout = get_relay_default("STAGE_TIMEOUT_PRIVATE_SERVER", 5)
    """
    # 映射表
    _all = {
        # Stage timeouts
        **{f"STAGE_TIMEOUT_{k.upper()}": v for k, v in STAGE_TIMEOUTS.items()},
        **{f"MAX_RETRIES_{k.upper()}": v for k, v in MAX_RETRIES.items()},
        "STAGE_TIMEOUT_DEFAULT": STAGE_TIMEOUT_DEFAULT,
        "MAX_RETRIES_DEFAULT": MAX_RETRIES_DEFAULT,
        # Intervals
        "HEALTH_CHECK_INTERVAL": HEALTH_CHECK_INTERVAL,
        "DEGRADED_RECOVER_INTERVAL": DEGRADED_RECOVER_INTERVAL,
        "OFFLINE_CHECK_INTERVAL": OFFLINE_CHECK_INTERVAL,
        "RECONNECT_WAIT": RECONNECT_WAIT,
        "UPGRADE_CHECK_INTERVAL": UPGRADE_CHECK_INTERVAL,
        "NAT_TRAVERSE_DELAY": NAT_TRAVERSE_DELAY,
        # Health monitor
        "HEARTBEAT_DEFAULT_INTERVAL": HEARTBEAT_DEFAULT_INTERVAL,
        "HEARTBEAT_FAST_INTERVAL": HEARTBEAT_FAST_INTERVAL,
        "LATENCY_THRESHOLD_MS": LATENCY_THRESHOLD_MS,
        "SUCCESS_RATE_THRESHOLD": SUCCESS_RATE_THRESHOLD,
        "CONSECUTIVE_FAILURE_THRESHOLD": CONSECUTIVE_FAILURE_THRESHOLD,
        "RECOVERY_CHECK_COUNT": RECOVERY_CHECK_COUNT,
        "MAX_HISTORY_SIZE": MAX_HISTORY_SIZE,
        "ALERT_COOLDOWN_SECONDS": ALERT_COOLDOWN_SECONDS,
        # Socket timeouts
        "SOCKET_TIMEOUT_STUN": SOCKET_TIMEOUT_STUN,
        "SOCKET_TIMEOUT_TURN": SOCKET_TIMEOUT_TURN,
        "SOCKET_TIMEOUT_TCP": SOCKET_TIMEOUT_TCP,
        "HTTP_TIMEOUT_SIGNALING": HTTP_TIMEOUT_SIGNALING,
        "HTTP_TIMEOUT_STORAGE": HTTP_TIMEOUT_STORAGE,
        "MONITOR_STOP_TIMEOUT": MONITOR_STOP_TIMEOUT,
        # Router
        "ROUTER_CACHE_TTL": ROUTER_CACHE_TTL,
        "ROUTER_MAX_FAILURE_HISTORY": ROUTER_MAX_FAILURE_HISTORY,
        # Sandbox
        "SANDBOX_MAX_STEPS": SANDBOX_MAX_STEPS,
        "SANDBOX_TIMEOUT_SECONDS": SANDBOX_TIMEOUT_SECONDS,
        "SANDBOX_MEMORY_LIMIT_MB": SANDBOX_MEMORY_LIMIT_MB,
        "SANDBOX_CPU_LIMIT": SANDBOX_CPU_LIMIT,
        "SANDBOX_DISK_LIMIT_GB": SANDBOX_DISK_LIMIT_GB,
        "SANDBOX_EXECUTE_TIMEOUT": SANDBOX_EXECUTE_TIMEOUT,
        "SANDBOX_DOCKER_EXEC_CAP": SANDBOX_DOCKER_EXEC_CAP,
        "SANDBOX_SIM_DURATION_MS": SANDBOX_SIM_DURATION_MS,
        # Vheer
        "VHEER_DEFAULT_BASE_URL": VHEER_DEFAULT_BASE_URL,
        "VHEER_DEFAULT_TIMEOUT": VHEER_DEFAULT_TIMEOUT,
        "VHEER_RATE_LIMIT_INTERVAL": VHEER_RATE_LIMIT_INTERVAL,
        "VHEER_DOWNLOAD_TIMEOUT": VHEER_DOWNLOAD_TIMEOUT,
        "VHEER_POLL_IMAGE_INTERVAL": VHEER_POLL_IMAGE_INTERVAL,
        "VHEER_POLL_IMAGE_MAX_WAIT": VHEER_POLL_IMAGE_MAX_WAIT,
        "VHEER_POLL_VIDEO_INTERVAL": VHEER_POLL_VIDEO_INTERVAL,
        "VHEER_POLL_VIDEO_MAX_WAIT": VHEER_POLL_VIDEO_MAX_WAIT,
        # General
        "POLLING_SHORT_DELAY": POLLING_SHORT_DELAY,
        "DEPLOY_STEP_MAX": DEPLOY_STEP_MAX,
        "TIMEOUT_QUICK": TIMEOUT_QUICK,
        "TIME_PER_LINE_ESTIMATE": TIME_PER_LINE_ESTIMATE,
    }
    
    if default is None:
        default = _all.get(key, 0)
    
    return _all.get(key, default)
