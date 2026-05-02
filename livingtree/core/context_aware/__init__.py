"""
上下文感知模块

包含两个核心能力：
1. EnvironmentAwareness - 环境感知能力
   - 硬件资源监控（CPU、内存、GPU）
   - 网络状态监控（在线/离线、延迟）
   - 系统信息获取（OS、Python版本）
   - 电池状态（移动设备）

2. IdentityAwareness - 身份感知能力
   - 用户身份识别（多账户支持）
   - 用户画像构建（兴趣、偏好、历史行为）
   - 访问权限管理（RBAC）
   - 个性化推荐
   - 会话上下文管理
"""

from .environment_awareness import (
    EnvironmentAwareness,
    NetworkStatus,
    HardwareInfo,
    NetworkInfo,
    SystemInfo,
    BatteryInfo
)

from .identity_awareness import (
    IdentityAwareness,
    UserRole,
    PermissionLevel,
    UserProfile,
    SessionContext
)

__all__ = [
    # 环境感知
    "EnvironmentAwareness",
    "NetworkStatus",
    "HardwareInfo",
    "NetworkInfo",
    "SystemInfo",
    "BatteryInfo",
    
    # 身份感知
    "IdentityAwareness",
    "UserRole",
    "PermissionLevel",
    "UserProfile",
    "SessionContext"
]