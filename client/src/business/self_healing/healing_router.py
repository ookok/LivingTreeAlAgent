"""
自愈路由器 - 统一自愈管理接口

功能：
1. 统一健康监控入口
2. 问题检测与报告
3. 修复策略协调
4. 状态汇总与查询
"""

import time
import threading
from typing import Dict, List, Any, Optional
from loguru import logger


class HealingRouter:
    """
    自愈路由器 - 协调健康监控、问题检测和修复执行
    
    核心流程：
    1. 监控健康指标
    2. 检测问题
    3. 分析问题
    4. 选择修复策略
    5. 执行修复
    6. 验证结果
    """
    
    def __init__(self):
        self._logger = logger.bind(component="HealingRouter")
        
        # 延迟加载组件
        self._health_monitor = None
        self._problem_detector = None
        self._repair_engine = None
        
        # 状态
        self._auto_heal_enabled = True
        self._running = False
        
        # 回调函数
        self._on_problem_detected = None
        self._on_repair_completed = None
    
    def _init_components(self):
        """延迟初始化组件"""
        if self._health_monitor is None:
            from .health_monitor import HealthMonitor
            from .problem_detector import ProblemDetector
            from .repair_engine import RepairEngine
            
            self._health_monitor = HealthMonitor(monitor_interval=5)
            self._problem_detector = ProblemDetector()
            self._repair_engine = RepairEngine()
            
            # 设置监控回调
            self._health_monitor.set_callback(
                on_metric_update=self._on_metrics_updated,
                on_status_change=self._on_status_changed
            )
            
            self._logger.info("自愈组件初始化完成")
    
    def _on_metrics_updated(self, metrics: Dict):
        """指标更新回调"""
        # 检测问题
        reports = self._problem_detector.detect_from_metrics(metrics)
        
        for report in reports:
            if self._auto_heal_enabled:
                # 自动修复
                self._auto_repair(report)
            else:
                # 通知但不修复
                if self._on_problem_detected:
                    self._on_problem_detected(report)
    
    def _on_status_changed(self, metric):
        """状态变化回调"""
        if metric.status.value in ['warning', 'error']:
            self._logger.warning(f"指标异常: {metric.name} = {metric.value}{metric.unit}")
    
    def start(self):
        """启动自愈系统"""
        self._init_components()
        self._health_monitor.start()
        self._running = True
        self._logger.info("自愈系统已启动")
    
    def stop(self):
        """停止自愈系统"""
        if self._health_monitor:
            self._health_monitor.stop()
        self._running = False
        self._logger.info("自愈系统已停止")
    
    def _auto_repair(self, report):
        """自动修复问题"""
        if not self._auto_heal_enabled:
            return
        
        self._logger.info(f"自动修复问题: {report.title}")
        
        # 转换报告为问题字典
        problem = {
            'report_id': report.report_id,
            'title': report.title,
            'description': report.description,
            'severity': report.severity.value,
            'category': report.category.value,
            'location': report.location,
            'metadata': report.metadata
        }
        
        # 执行修复
        result = self._repair_engine.execute_repair(problem)
        
        # 标记问题已解决
        if result.status.value == 'success':
            self._problem_detector.resolve_report(report.report_id)
        
        # 触发回调
        if self._on_repair_completed:
            self._on_repair_completed(result)
    
    def trigger_repair(self, component: str, issue: str = None) -> Dict:
        """手动触发修复"""
        self._init_components()
        
        problem = {
            'report_id': f"manual_{int(time.time())}",
            'title': f"手动修复: {component}",
            'description': issue or f"手动触发修复 {component}",
            'severity': 'error',
            'category': 'unknown',
            'component': component,
            'issue': issue
        }
        
        result = self._repair_engine.execute_repair(problem)
        return result.to_dict()
    
    def get_health_status(self) -> Dict:
        """获取健康状态"""
        self._init_components()
        
        return {
            'overall': self._health_monitor.get_overall_status().value,
            'metrics': self._health_monitor.get_metrics(),
            'unresolved_problems': len(self._problem_detector.get_unresolved_reports()),
            'repair_stats': self._repair_engine.get_stats(),
            'running': self._running,
            'auto_heal_enabled': self._auto_heal_enabled
        }
    
    def get_problems(self, unresolved_only: bool = True) -> List[Dict]:
        """获取问题列表"""
        self._init_components()
        
        if unresolved_only:
            reports = self._problem_detector.get_unresolved_reports()
        else:
            reports = self._problem_detector.get_all_reports()
        
        return [report.to_dict() for report in reports]
    
    def get_repair_history(self, limit: int = 20) -> List[Dict]:
        """获取修复历史"""
        self._init_components()
        history = self._repair_engine.get_history(limit)
        return [h.to_dict() for h in history]
    
    def enable_auto_heal(self):
        """启用自动修复"""
        self._auto_heal_enabled = True
        self._logger.info("自动修复已启用")
    
    def disable_auto_heal(self):
        """禁用自动修复"""
        self._auto_heal_enabled = False
        self._logger.info("自动修复已禁用")
    
    def set_callbacks(self, on_problem_detected=None, on_repair_completed=None):
        """设置回调函数"""
        self._on_problem_detected = on_problem_detected
        self._on_repair_completed = on_repair_completed
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        self._init_components()
        
        return {
            'health': self._health_monitor.get_summary(),
            'problems': self._problem_detector.get_stats(),
            'repairs': self._repair_engine.get_stats()
        }


# 单例模式
_router_instance = None

def get_healing_router() -> HealingRouter:
    """获取自愈路由器实例"""
    global _router_instance
    if _router_instance is None:
        _router_instance = HealingRouter()
    return _router_instance