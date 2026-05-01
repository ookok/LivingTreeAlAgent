"""
学习反馈系统 (Learning Feedback System)
========================================

实现持续学习和反馈优化：
1. 执行数据收集
2. 模型持续训练
3. 调度策略优化

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

import asyncio
import json
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from loguru import logger


class FeedbackType(Enum):
    """反馈类型"""
    USER_RATING = "user_rating"
    TASK_SUCCESS = "task_success"
    LATENCY_WARNING = "latency_warning"
    ERROR_REPORT = "error_report"
    AUTOMATIC_EVAL = "automatic_eval"


@dataclass
class FeedbackRecord:
    """反馈记录"""
    module_name: str
    task_type: str
    feedback_type: FeedbackType
    score: float  # 0-1
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionLog:
    """执行日志"""
    module_name: str
    task_type: str
    success: bool
    latency: float
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    error_message: Optional[str] = None
    confidence: float = 0.0


class LearningFeedbackSystem:
    """
    学习反馈系统
    
    收集执行数据，持续优化调度策略：
    - 数据收集
    - 模型训练
    - 策略优化
    """
    
    def __init__(self, update_interval: int = 60):
        """
        初始化反馈系统
        
        Args:
            update_interval: 更新间隔（秒）
        """
        self._feedback_records: List[FeedbackRecord] = []
        self._execution_logs: List[ExecutionLog] = []
        self._module_stats: Dict[str, Dict[str, Any]] = {}
        self._update_interval = update_interval
        self._update_task = None
        self._running = False
        self._optimization_callbacks: List[Callable] = []
        
    async def start(self):
        """启动反馈系统"""
        self._running = True
        self._update_task = asyncio.create_task(self._update_loop())
        logger.info("[LearningFeedbackSystem] 反馈系统已启动")
        
    async def stop(self):
        """停止反馈系统"""
        self._running = False
        if self._update_task:
            self._update_task.cancel()
        logger.info("[LearningFeedbackSystem] 反馈系统已停止")
        
    async def _update_loop(self):
        """更新循环"""
        while self._running:
            await self._perform_optimization()
            await asyncio.sleep(self._update_interval)
            
    def record_execution(self, log: ExecutionLog):
        """
        记录执行日志
        
        Args:
            log: 执行日志
        """
        self._execution_logs.append(log)
        
        # 更新模块统计
        if log.module_name not in self._module_stats:
            self._module_stats[log.module_name] = {
                'total_executions': 0,
                'success_count': 0,
                'total_latency': 0.0,
                'avg_confidence': 0.0,
                'last_execution': 0.0
            }
            
        stats = self._module_stats[log.module_name]
        stats['total_executions'] += 1
        if log.success:
            stats['success_count'] += 1
        stats['total_latency'] += log.latency
        stats['avg_confidence'] = (stats['avg_confidence'] * (stats['total_executions'] - 1) + log.confidence) / stats['total_executions']
        stats['last_execution'] = log.timestamp
        
        logger.debug(f"[LearningFeedbackSystem] 记录执行: {log.module_name} ({'成功' if log.success else '失败'})")
        
    def record_feedback(self, record: FeedbackRecord):
        """
        记录反馈
        
        Args:
            record: 反馈记录
        """
        self._feedback_records.append(record)
        logger.debug(f"[LearningFeedbackSystem] 记录反馈: {record.module_name} - {record.feedback_type.value}")
        
    async def _perform_optimization(self):
        """执行优化"""
        if not self._execution_logs:
            return
            
        logger.info("[LearningFeedbackSystem] 执行策略优化")
        
        # 计算各模块的成功率和平均延迟
        module_metrics = self._calculate_module_metrics()
        
        # 调用优化回调
        for callback in self._optimization_callbacks:
            try:
                await callback(module_metrics)
            except Exception as e:
                logger.warning(f"[LearningFeedbackSystem] 优化回调执行失败: {e}")
                
        # 清理旧数据（保留最近1000条）
        if len(self._execution_logs) > 1000:
            self._execution_logs = self._execution_logs[-1000:]
        if len(self._feedback_records) > 500:
            self._feedback_records = self._feedback_records[-500:]
            
    def _calculate_module_metrics(self) -> Dict[str, Dict[str, float]]:
        """
        计算模块指标
        
        Returns:
            模块指标字典
        """
        metrics = {}
        
        for module_name, stats in self._module_stats.items():
            if stats['total_executions'] == 0:
                continue
                
            metrics[module_name] = {
                'success_rate': stats['success_count'] / stats['total_executions'],
                'avg_latency': stats['total_latency'] / stats['total_executions'],
                'avg_confidence': stats['avg_confidence'],
                'execution_count': stats['total_executions']
            }
            
        return metrics
        
    def register_optimization_callback(self, callback: Callable):
        """
        注册优化回调
        
        Args:
            callback: 回调函数
        """
        if callback not in self._optimization_callbacks:
            self._optimization_callbacks.append(callback)
            
    def get_module_stats(self, module_name: Optional[str] = None) -> Dict[str, Any]:
        """
        获取模块统计信息
        
        Args:
            module_name: 模块名称，如果为 None 返回所有模块
            
        Returns:
            统计信息
        """
        if module_name:
            return self._module_stats.get(module_name, {})
        return self._module_stats.copy()
        
    def get_recent_executions(self, limit: int = 10) -> List[ExecutionLog]:
        """
        获取最近的执行日志
        
        Args:
            limit: 返回数量限制
            
        Returns:
            执行日志列表
        """
        return self._execution_logs[-limit:]
        
    def export_data(self, file_path: str):
        """
        导出数据到文件
        
        Args:
            file_path: 文件路径
        """
        data = {
            'feedback_records': [record.__dict__ for record in self._feedback_records],
            'execution_logs': [log.__dict__ for log in self._execution_logs],
            'module_stats': self._module_stats
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"[LearningFeedbackSystem] 数据已导出到: {file_path}")
