# core/security/__init__.py
# Living Tree AI 安全防护系统

"""
安全防护系统架构：

1. SecurityManager - 安全管理器
   - 首次运行引导
   - 安全状态检查
   - 信任引导

2. FirewallManager - 防火墙管理
   - Windows 防火墙规则
   - 端口管理
   - 规则持久化

3. AntivirusHelper - 杀毒软件检测
   - 主流杀软检测
   - 白名单引导
   - 兼容性检查

4. BehaviorMonitor - 行为监控
   - 进程行为追踪
   - 风险评估
   - 透明化日志
"""

from .security_manager import (
    SecurityManager,
    SecurityConfig,
    SecurityStatus,
    get_security_manager,
)

from .firewall_manager import (
    FirewallManager,
    FirewallRule,
    PortConfig,
    get_firewall_manager,
)

from .antivirus_helper import (
    AntivirusHelper,
    AntivirusProduct,
    TrustGuide,
    get_antivirus_helper,
)

from .behavior_monitor import (
    BehaviorMonitor,
    BehaviorEvent,
    RiskLevel,
    get_behavior_monitor,
)

__version__ = "1.0.0"

__all__ = [
    # 安全管理器
    "SecurityManager",
    "SecurityConfig",
    "SecurityStatus",
    "get_security_manager",
    # 防火墙
    "FirewallManager",
    "FirewallRule",
    "PortConfig",
    "get_firewall_manager",
    # 杀毒软件
    "AntivirusHelper",
    "AntivirusProduct",
    "TrustGuide",
    "get_antivirus_helper",
    # 行为监控
    "BehaviorMonitor",
    "BehaviorEvent",
    "RiskLevel",
    "get_behavior_monitor",
    # 模型
    "SecurityLevel",
    "FirewallStatus",
    "AntivirusStatus",
]