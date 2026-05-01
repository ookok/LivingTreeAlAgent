"""
系统集成模块 - System Integration

功能：
1. 统一初始化所有子系统
2. 协调各系统间通信
3. 生命周期管理
4. 全局状态管理
"""

from .system_manager import SystemManager, get_system_manager

__all__ = [
    'SystemManager',
    'get_system_manager',
]


def initialize_systems():
    """初始化所有系统"""
    manager = get_system_manager()
    manager.initialize()


def shutdown_systems():
    """关闭所有系统"""
    manager = get_system_manager()
    manager.shutdown()