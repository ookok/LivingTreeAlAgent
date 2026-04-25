# -*- coding: utf-8 -*-
"""
Evolution Engine UI Integration - Evolution Dashboard 集成助手
==============================================================

提供便捷的方法来初始化和连接 Evolution Engine 到 Dashboard

Usage:
    from client.src.business.evolution_engine.ui_integration import init_evolution_dashboard
    
    # 在主窗口中调用
    dashboard = init_evolution_dashboard(project_root=".")
"""

import os
import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from client.src.business.evolution_engine import EvolutionEngine
    from ui.evolution_dashboard import EvolutionDashboard

logger = logging.getLogger(__name__)

# 全局引擎实例
_evolution_engine: Optional['EvolutionEngine'] = None


def init_evolution_engine(
    project_root: str = ".",
    auto_scan: bool = True,
    scan_interval: int = 3600  # 1小时
) -> 'EvolutionEngine':
    """
    初始化 Evolution Engine
    
    Args:
        project_root: 项目根目录
        auto_scan: 是否自动扫描
        scan_interval: 扫描间隔（秒）
    
    Returns:
        EvolutionEngine 实例
    """
    global _evolution_engine
    
    try:
        from client.src.business.evolution_engine import create_evolution_engine
        
        _evolution_engine = create_evolution_engine(
            project_root=str(project_root)
        )
        
        logger.info(f"Evolution Engine 初始化成功: {project_root}")
        
        # 可选：启动自动扫描
        if auto_scan:
            _start_auto_scan(_evolution_engine, scan_interval)
        
        return _evolution_engine
        
    except Exception as e:
        logger.error(f"Evolution Engine 初始化失败: {e}")
        return None


def _start_auto_scan(engine: 'EvolutionEngine', interval: int):
    """启动自动扫描"""
    import threading
    import time
    
    def scan_loop():
        while True:
            try:
                time.sleep(interval)
                logger.debug("执行自动扫描...")
                # engine.scan()  # 如果有 scan 方法
            except Exception as e:
                logger.error(f"自动扫描失败: {e}")
    
    thread = threading.Thread(target=scan_loop, daemon=True)
    thread.start()


def init_evolution_dashboard(
    engine: Optional['EvolutionEngine'] = None,
    project_root: str = "."
) -> 'EvolutionDashboard':
    """
    初始化 Evolution Dashboard 并连接引擎
    
    Args:
        engine: EvolutionEngine 实例（可选，会自动创建）
        project_root: 项目根目录（engine 为 None 时使用）
    
    Returns:
        EvolutionDashboard 实例
    """
    try:
        from ui.evolution_dashboard import EvolutionDashboard
        
        # 如果没有传入引擎，自动创建
        if engine is None:
            engine = _evolution_engine
            if engine is None:
                engine = init_evolution_engine(project_root)
        
        # 创建 Dashboard
        dashboard = EvolutionDashboard(engine)
        
        logger.info("Evolution Dashboard 初始化成功")
        return dashboard
        
    except ImportError as e:
        logger.error(f"无法导入 Evolution Dashboard: {e}")
        return None


def connect_dashboard_to_engine(
    dashboard: 'EvolutionDashboard',
    engine: 'EvolutionEngine'
):
    """
    将 Dashboard 连接到 Engine
    
    Args:
        dashboard: EvolutionDashboard 实例
        engine: EvolutionEngine 实例
    """
    dashboard.set_engine(engine)


def get_evolution_engine() -> Optional['EvolutionEngine']:
    """获取全局 Evolution Engine 实例"""
    global _evolution_engine
    return _evolution_engine


def create_evolution_snapshot() -> dict:
    """
    创建 Evolution Engine 当前状态的快照
    
    Returns:
        包含所有进化数据的字典
    """
    engine = get_evolution_engine()
    if engine is None:
        return {'error': 'Evolution Engine 未初始化'}
    
    try:
        summary = engine.get_evolution_summary()
        return {
            'timestamp': __import__('datetime').datetime.now().isoformat(),
            'summary': summary,
            'status': 'ok'
        }
    except Exception as e:
        return {
            'error': str(e),
            'status': 'error'
        }


# ==================== 便捷函数 ====================

def quick_start(project_root: str = ".") -> 'EvolutionDashboard':
    """
    快速启动 Evolution Dashboard（一步到位）
    
    Args:
        project_root: 项目根目录
    
    Returns:
        已连接的 EvolutionDashboard
    """
    engine = init_evolution_engine(project_root)
    return init_evolution_dashboard(engine)


# ==================== 导出 ====================

__all__ = [
    'init_evolution_engine',
    'init_evolution_dashboard',
    'connect_dashboard_to_engine',
    'get_evolution_engine',
    'create_evolution_snapshot',
    'quick_start',
]
