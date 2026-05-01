"""
修复引擎模块 - 协调修复策略的执行

功能：
1. 分析问题并选择最佳修复策略
2. 执行修复操作
3. 验证修复结果
4. 记录修复历史
"""

import logging
import time
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class RepairStatus(Enum):
    """修复状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"


@dataclass
class RepairResult:
    """修复结果"""
    repair_id: str
    problem_id: str
    strategy_name: str
    status: RepairStatus
    message: str
    details: Dict = None
    start_time: float = None
    end_time: float = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.start_time is None:
            self.start_time = time.time()
    
    @property
    def duration(self) -> float:
        """修复持续时间"""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time
    
    def to_dict(self) -> Dict:
        return {
            'repair_id': self.repair_id,
            'problem_id': self.problem_id,
            'strategy_name': self.strategy_name,
            'status': self.status.value,
            'message': self.message,
            'details': self.details,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': self.duration
        }


class RepairEngine:
    """
    修复引擎 - 协调修复策略的执行
    
    工作流程：
    1. 接收问题报告
    2. 分析问题严重程度和类型
    3. 选择最佳修复策略
    4. 执行修复
    5. 验证修复结果
    6. 记录修复历史
    """
    
    def __init__(self):
        self._strategies = []
        self._history: List[RepairResult] = []
        self._max_history = 100
        self._lock = threading.Lock()
        
        # 初始化策略（延迟加载）
        self._strategy_instances = {}
    
    def register_strategy(self, strategy):
        """注册修复策略"""
        self._strategies.append(strategy)
        logger.info(f"注册修复策略: {strategy.get_name()}")
    
    def _init_strategies(self):
        """初始化策略实例"""
        if self._strategy_instances:
            return
        
        from .recovery_strategies import (
            RestartStrategy,
            CheckpointRestoreStrategy,
            FallbackStrategy,
            ParameterOptimizationStrategy,
            RollbackStrategy
        )
        
        # 创建策略实例（传入None作为依赖，实际使用时需要注入）
        self._strategy_instances['restart'] = RestartStrategy(None)
        self._strategy_instances['checkpoint'] = CheckpointRestoreStrategy(None)
        self._strategy_instances['fallback'] = FallbackStrategy(None)
        self._strategy_instances['optimization'] = ParameterOptimizationStrategy(None)
        self._strategy_instances['rollback'] = RollbackStrategy(None)
        
        # 注册策略
        for strategy in self._strategy_instances.values():
            self.register_strategy(strategy)
    
    def select_strategy(self, problem: Dict) -> Optional[Any]:
        """选择最佳修复策略"""
        self._init_strategies()
        
        severity = problem.get('severity', 'warning')
        category = problem.get('category', 'unknown')
        
        # 根据问题类型选择策略
        strategy_map = {
            'critical': ['rollback', 'checkpoint', 'restart'],
            'error': ['checkpoint', 'restart', 'fallback'],
            'warning': ['optimization', 'fallback', 'restart'],
            'info': ['optimization']
        }
        
        # 根据类别调整优先级
        category_priority = {
            'memory': ['checkpoint', 'rollback', 'restart'],
            'network': ['fallback', 'restart'],
            'performance': ['optimization', 'fallback', 'restart'],
            'crash': ['rollback', 'checkpoint', 'restart'],
            'configuration': ['optimization', 'restart'],
            'dependency': ['fallback', 'restart']
        }
        
        # 获取候选策略列表
        candidates = strategy_map.get(severity, ['restart', 'fallback'])
        
        # 根据类别重新排序
        if category in category_priority:
            category_strategies = category_priority[category]
            # 优先选择类别相关的策略
            candidates = [s for s in category_strategies if s in candidates] + \
                        [s for s in candidates if s not in category_strategies]
        
        # 选择置信度最高的策略
        best_strategy = None
        best_confidence = 0.0
        
        for strategy_name in candidates:
            strategy = self._strategy_instances.get(strategy_name)
            if strategy and strategy.get_confidence() > best_confidence:
                best_confidence = strategy.get_confidence()
                best_strategy = strategy
        
        return best_strategy
    
    def execute_repair(self, problem: Dict) -> RepairResult:
        """执行修复"""
        import uuid
        
        repair_id = str(uuid.uuid4())
        problem_id = problem.get('report_id', 'unknown')
        
        logger.info(f"开始修复: {repair_id}")
        
        result = RepairResult(
            repair_id=repair_id,
            problem_id=problem_id,
            strategy_name="",
            status=RepairStatus.RUNNING,
            message="修复进行中"
        )
        
        try:
            # 选择策略
            strategy = self.select_strategy(problem)
            
            if not strategy:
                result.status = RepairStatus.FAILED
                result.message = "无法找到合适的修复策略"
                result.end_time = time.time()
                self._add_history(result)
                return result
            
            result.strategy_name = strategy.get_name()
            
            # 执行策略
            strategy_result = strategy.execute(problem)
            
            if strategy_result.success:
                result.status = RepairStatus.SUCCESS
                result.message = strategy_result.message
                result.details = strategy_result.details
            else:
                result.status = RepairStatus.FAILED
                result.message = strategy_result.message
                result.details = strategy_result.details
            
            # 如果修复失败，尝试下一个策略
            if result.status == RepairStatus.FAILED:
                result = self._try_next_strategy(problem, repair_id, result)
            
        except Exception as e:
            logger.error(f"修复执行失败: {e}")
            result.status = RepairStatus.FAILED
            result.message = f"修复执行失败: {str(e)}"
        
        result.end_time = time.time()
        self._add_history(result)
        
        logger.info(f"修复完成: {repair_id} -> {result.status.value}")
        return result
    
    def _try_next_strategy(self, problem: Dict, repair_id: str, previous_result: RepairResult) -> RepairResult:
        """尝试下一个策略"""
        logger.info(f"尝试下一个修复策略")
        
        # 获取所有可用策略
        strategies = self._strategy_instances.values()
        
        # 排除已尝试的策略
        tried_strategies = [previous_result.strategy_name]
        
        # 按置信度排序
        available_strategies = sorted(
            [s for s in strategies if s.get_name() not in tried_strategies],
            key=lambda x: x.get_confidence(),
            reverse=True
        )
        
        for strategy in available_strategies[:2]:  # 最多尝试2个额外策略
            try:
                strategy_result = strategy.execute(problem)
                
                if strategy_result.success:
                    return RepairResult(
                        repair_id=repair_id,
                        problem_id=problem.get('report_id', 'unknown'),
                        strategy_name=strategy.get_name(),
                        status=RepairStatus.SUCCESS,
                        message=strategy_result.message,
                        details=strategy_result.details,
                        start_time=previous_result.start_time,
                        end_time=time.time()
                    )
                else:
                    tried_strategies.append(strategy.get_name())
            
            except Exception as e:
                logger.error(f"尝试策略 {strategy.get_name()} 失败: {e}")
        
        # 所有策略都失败
        return RepairResult(
            repair_id=repair_id,
            problem_id=problem.get('report_id', 'unknown'),
            strategy_name=", ".join(tried_strategies),
            status=RepairStatus.FAILED,
            message="所有修复策略均失败",
            start_time=previous_result.start_time,
            end_time=time.time()
        )
    
    def get_history(self, limit: int = 20) -> List[RepairResult]:
        """获取修复历史"""
        with self._lock:
            return self._history[-limit:]
    
    def get_stats(self) -> Dict:
        """获取修复统计"""
        total = len(self._history)
        success_count = sum(1 for r in self._history if r.status == RepairStatus.SUCCESS)
        failed_count = sum(1 for r in self._history if r.status == RepairStatus.FAILED)
        
        return {
            'total_repairs': total,
            'success_count': success_count,
            'failed_count': failed_count,
            'success_rate': success_count / total if total > 0 else 0,
            'avg_duration': sum(r.duration for r in self._history) / total if total > 0 else 0
        }
    
    def _add_history(self, result: RepairResult):
        """添加修复历史"""
        with self._lock:
            self._history.append(result)
            # 限制历史记录数量
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
    
    def rollback_repair(self, repair_id: str) -> RepairResult:
        """回滚修复"""
        logger.info(f"回滚修复: {repair_id}")
        
        # 查找修复记录
        repair = next((r for r in self._history if r.repair_id == repair_id), None)
        
        if not repair:
            return RepairResult(
                repair_id=repair_id,
                problem_id="unknown",
                strategy_name="回滚",
                status=RepairStatus.FAILED,
                message="未找到修复记录"
            )
        
        # 创建回滚策略
        from .recovery_strategies import RollbackStrategy
        rollback_strategy = RollbackStrategy(None)
        
        result = rollback_strategy.execute({
            'component': repair.details.get('component', 'unknown'),
            'issue': f"回滚修复 {repair_id}"
        })
        
        return RepairResult(
            repair_id=repair_id + "_rollback",
            problem_id=repair.problem_id,
            strategy_name="回滚",
            status=RepairStatus.SUCCESS if result.success else RepairStatus.FAILED,
            message=result.message,
            details=result.details,
            start_time=time.time(),
            end_time=time.time()
        )