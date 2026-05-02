"""
系统集成模块 - 向后兼容层

⚠️ 已迁移至 livingtree.core.integration
本模块保留为兼容层，所有导入将自动重定向到新位置。
"""

from livingtree.core.integration import (
    SystemManager, SysState as SystemState, SubsystemInfo,
    get_system_manager,
)

__all__ = [
    'SystemManager',
    'get_system_manager',
    'SystemState',
    'SubsystemInfo',
]


def initialize_systems():
    manager = get_system_manager()
    manager.initialize()


def shutdown_systems():
    manager = get_system_manager()
    manager.shutdown()
