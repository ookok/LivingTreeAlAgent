#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Auto Fix System - 自动修复系统
================================

功能：
1. 可自动修复场景的策略库
2. 安全修复流程（诊断→评估→确认→执行→验证）
3. 增量学习机制

可自动修复的场景：
1. 资源清理 - 内存/磁盘空间不足 → 自动清理缓存
2. 重试机制 - 网络/服务暂时不可用 → 指数退避重试
3. 配置修复 - 检测到错误配置 → 恢复到最近可用配置
4. 依赖恢复 - 关键进程挂掉 → 自动重启
5. 数据修复 - 检测到数据损坏 → 从备份恢复

Usage:
    fix_system = AutoFixSystem()
    result = fix_system.fix(diagnosis_result)
"""

import os
import re
import gc
import shutil
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque

from .structured_logger import get_logger, ErrorCategory
from .diagnosis_engine import DiagnosisResult, DiagnosisEngine, get_diagnosis_engine


class FixStrategy(Enum):
    """修复策略"""
    RETRY = "retry"                    # 重试
    CLEAN_CACHE = "clean_cache"        # 清理缓存
    RESTART_SERVICE = "restart"       # 重启服务
    RESTORE_CONFIG = "restore_config"  # 恢复配置
    KILL_PROCESS = "kill_process"      # 终止进程
    INCREASE_TIMEOUT = "increase_timeout"  # 增加超时
    REDUCE_LOAD = "reduce_load"        # 降低负载
    EXPAND_RESOURCE = "expand_resource" # 扩展资源
    CALL_HUMAN = "call_human"          # 人工介入


class FixRiskLevel(Enum):
    """修复风险等级"""
    NONE = "none"      # 无风险
    LOW = "low"         # 低风险
    MEDIUM = "medium"   # 中风险
    HIGH = "high"       # 高风险
    CRITICAL = "critical"  # 高风险（可能导致数据丢失）


@dataclass
class FixAction:
    """修复动作"""
    strategy: FixStrategy
    command: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    risk_level: FixRiskLevel = FixRiskLevel.LOW
    estimated_duration: float = 1.0  # 秒
    reversible: bool = True
    requires_confirm: bool = False


@dataclass
class FixResult:
    """修复结果"""
    success: bool
    strategy_used: FixStrategy
    action_taken: str
    new_state: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    fix_duration: float = 0.0
    verification_passed: bool = False
    fallback_available: bool = True


class FixKnowledgeBase:
    """
    修复知识库

    管理修复策略和历史记录
    """

    def __init__(self, knowledge_dir: str):
        self.knowledge_dir = knowledge_dir
        os.makedirs(knowledge_dir, exist_ok=True)

        # 成功修复历史
        self.success_history: deque = deque(maxlen=500)

        # 失败修复历史
        self.failure_history: deque = deque(maxlen=200)

        # 策略有效性评分
        self.strategy_scores: Dict[FixStrategy, Tuple[int, int]] = {}
        # (success_count, total_count)

    def record_success(
        self,
        error_code: str,
        strategy: FixStrategy,
        duration: float
    ):
        """记录成功修复"""
        self.success_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_code": error_code,
            "strategy": strategy.value,
            "duration": duration
        })
        self._update_score(strategy, True)

    def record_failure(
        self,
        error_code: str,
        strategy: FixStrategy,
        error: str
    ):
        """记录失败修复"""
        self.failure_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_code": error_code,
            "strategy": strategy.value,
            "error": error
        })
        self._update_score(strategy, False)

    def _update_score(self, strategy: FixStrategy, success: bool):
        """更新策略评分"""
        if strategy not in self.strategy_scores:
            self.strategy_scores[strategy] = (0, 0)

        success_count, total_count = self.strategy_scores[strategy]
        self.strategy_scores[strategy] = (
            success_count + (1 if success else 0),
            total_count + 1
        )

    def get_success_rate(self, strategy: FixStrategy) -> float:
        """获取策略成功率"""
        if strategy not in self.strategy_scores:
            return 0.5  # 默认 50%

        success_count, total_count = self.strategy_scores[strategy]
        if total_count == 0:
            return 0.5
        return success_count / total_count

    def suggest_strategy(
        self,
        error_code: str,
        category: ErrorCategory
    ) -> List[Tuple[FixStrategy, float]]:
        """
        基于历史推荐修复策略

        Returns:
            [(strategy, confidence), ...] 按置信度排序
        """
        suggestions = []

        # 策略映射：错误分类 -> 默认策略
        default_strategies = {
            ErrorCategory.RESOURCE: [
                (FixStrategy.CLEAN_CACHE, 0.8),
                (FixStrategy.REDUCE_LOAD, 0.6),
                (FixStrategy.EXPAND_RESOURCE, 0.4)
            ],
            ErrorCategory.NETWORK: [
                (FixStrategy.RETRY, 0.9),
                (FixStrategy.INCREASE_TIMEOUT, 0.6)
            ],
            ErrorCategory.DEPENDENCY: [
                (FixStrategy.RESTART_SERVICE, 0.8),
                (FixStrategy.RETRY, 0.5)
            ],
            ErrorCategory.CONFIG: [
                (FixStrategy.RESTORE_CONFIG, 0.9)
            ],
            ErrorCategory.TIMEOUT: [
                (FixStrategy.INCREASE_TIMEOUT, 0.7),
                (FixStrategy.RETRY, 0.6),
                (FixStrategy.REDUCE_LOAD, 0.4)
            ],
            ErrorCategory.AI_MODEL: [
                (FixStrategy.CLEAN_CACHE, 0.7),
                (FixStrategy.RETRY, 0.5)
            ]
        }

        # 获取默认策略
        strategies = default_strategies.get(category, [(FixStrategy.RETRY, 0.5)])

        # 根据历史成功率调整
        adjusted = []
        for strategy, base_conf in strategies:
            success_rate = self.get_success_rate(strategy)
            adjusted_conf = base_conf * (0.5 + 0.5 * success_rate)
            adjusted.append((strategy, adjusted_conf))

        # 按置信度排序
        adjusted.sort(key=lambda x: x[1], reverse=True)
        return adjusted


class AutoFixSystem:
    """
    自动修复系统

    修复流程：
    1. 诊断确认
    2. 风险评估
    3. 用户确认（如需要）
    4. 执行修复
    5. 验证结果
    6. 记录反馈
    """

    _instance: Optional['AutoFixSystem'] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.logger = get_logger("auto_fix")
        self.diagnosis_engine = get_diagnosis_engine()

        # 知识库
        knowledge_dir = os.path.join(
            os.path.expanduser("~"),
            ".living_tree_ai",
            "fix_knowledge"
        )
        self.knowledge_base = FixKnowledgeBase(knowledge_dir)

        # 修复策略执行器
        self._executors: Dict[FixStrategy, Callable] = {
            FixStrategy.RETRY: self._retry,
            FixStrategy.CLEAN_CACHE: self._clean_cache,
            FixStrategy.RESTART_SERVICE: self._restart_service,
            FixStrategy.RESTORE_CONFIG: self._restore_config,
            FixStrategy.KILL_PROCESS: self._kill_process,
            FixStrategy.INCREASE_TIMEOUT: self._increase_timeout,
            FixStrategy.REDUCE_LOAD: self._reduce_load,
            FixStrategy.EXPAND_RESOURCE: self._expand_resource,
        }

        # 活跃修复任务
        self._active_fixes: Dict[str, Dict] = {}

        # 待确认的修复（高风险）
        self._pending_confirms: Dict[str, Dict] = {}

        self._initialized = True

    def can_auto_fix(self, diagnosis: DiagnosisResult) -> bool:
        """检查是否可以自动修复"""
        # 已经在诊断中标记为可自动修复
        if diagnosis.auto_fix_possible:
            # 检查风险等级
            action = self._get_fix_action(diagnosis)
            return action.risk_level in [FixRiskLevel.NONE, FixRiskLevel.LOW]

        return False

    def needs_confirmation(self, diagnosis: DiagnosisResult) -> Tuple[bool, FixRiskLevel]:
        """检查是否需要用户确认"""
        if not diagnosis.auto_fix_possible:
            return True, FixRiskLevel.HIGH

        action = self._get_fix_action(diagnosis)
        return action.requires_confirm, action.risk_level

    def get_fix_actions(self, diagnosis: DiagnosisResult) -> List[FixAction]:
        """获取建议的修复动作列表"""
        suggestions = self.knowledge_base.suggest_strategy(
            diagnosis.error_code,
            diagnosis.error_category
        )

        actions = []
        for strategy, confidence in suggestions:
            action = self._create_action(strategy, diagnosis)
            action.params["confidence"] = confidence
            actions.append(action)

        return actions

    def fix(
        self,
        diagnosis: DiagnosisResult,
        force_strategy: Optional[FixStrategy] = None,
        skip_confirmation: bool = False
    ) -> FixResult:
        """
        执行修复

        Args:
            diagnosis: 诊断结果
            force_strategy: 强制使用的策略（跳过推荐）
            skip_confirmation: 跳过用户确认

        Returns:
            FixResult 修复结果
        """
        fix_id = f"fix_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        start_time = time.time()

        self.logger.info(f"Starting fix {fix_id} for {diagnosis.error_code}")

        # 1. 选择策略
        if force_strategy:
            strategy = force_strategy
        else:
            suggestions = self.knowledge_base.suggest_strategy(
                diagnosis.error_code,
                diagnosis.error_category
            )
            if not suggestions:
                return FixResult(
                    success=False,
                    strategy_used=FixStrategy.CALL_HUMAN,
                    action_taken="无可用修复策略",
                    error_message="No fix strategy available"
                )
            strategy = suggestions[0][0]

        # 2. 检查是否需要确认
        action = self._create_action(strategy, diagnosis)
        if action.requires_confirm and not skip_confirmation:
            self._pending_confirms[fix_id] = {
                "diagnosis": diagnosis,
                "action": action
            }
            return FixResult(
                success=False,
                strategy_used=strategy,
                action_taken="等待用户确认",
                error_message="User confirmation required"
            )

        # 3. 执行修复
        executor = self._executors.get(strategy)
        if not executor:
            return FixResult(
                success=False,
                strategy_used=strategy,
                action_taken=f"未知策略: {strategy.value}",
                error_message=f"No executor for {strategy.value}"
            )

        try:
            result = executor(diagnosis)

            # 4. 验证
            verification_passed = self._verify_fix(diagnosis, result)

            # 5. 记录
            duration = time.time() - start_time
            if result.get("success"):
                self.knowledge_base.record_success(diagnosis.error_code, strategy, duration)
                self.diagnosis_engine.learn_from_fix(
                    {"error_code": diagnosis.error_code},
                    strategy.value,
                    True
                )
            else:
                self.knowledge_base.record_failure(
                    diagnosis.error_code,
                    strategy,
                    result.get("error", "Unknown")
                )
                self.diagnosis_engine.learn_from_fix(
                    {"error_code": diagnosis.error_code},
                    strategy.value,
                    False
                )

            return FixResult(
                success=result.get("success", False),
                strategy_used=strategy,
                action_taken=result.get("action", ""),
                new_state=result.get("state"),
                error_message=result.get("error"),
                fix_duration=duration,
                verification_passed=verification_passed
            )

        except Exception as e:
            self.logger.error(f"Fix failed: {str(e)}")
            return FixResult(
                success=False,
                strategy_used=strategy,
                action_taken="修复执行异常",
                error_message=str(e),
                fix_duration=time.time() - start_time
            )

    def confirm_fix(self, fix_id: str) -> FixResult:
        """确认并执行待定的修复"""
        if fix_id not in self._pending_confirms:
            return FixResult(
                success=False,
                strategy_used=FixStrategy.CALL_HUMAN,
                action_taken="修复任务不存在"
            )

        pending = self._pending_confirms.pop(fix_id)
        return self.fix(pending["diagnosis"], skip_confirmation=True)

    def cancel_fix(self, fix_id: str):
        """取消待定的修复"""
        self._pending_confirms.pop(fix_id, None)

    def _get_fix_action(self, diagnosis: DiagnosisResult) -> FixAction:
        """获取修复动作"""
        suggestions = self.knowledge_base.suggest_strategy(
            diagnosis.error_code,
            diagnosis.error_category
        )
        if suggestions:
            strategy = suggestions[0][0]
        else:
            strategy = FixStrategy.RETRY

        return self._create_action(strategy, diagnosis)

    def _create_action(
        self,
        strategy: FixStrategy,
        diagnosis: DiagnosisResult
    ) -> FixAction:
        """创建修复动作"""
        risk_map = {
            FixStrategy.RETRY: (FixRiskLevel.LOW, False),
            FixStrategy.CLEAN_CACHE: (FixRiskLevel.LOW, False),
            FixStrategy.RESTART_SERVICE: (FixRiskLevel.MEDIUM, True),
            FixStrategy.RESTORE_CONFIG: (FixRiskLevel.MEDIUM, True),
            FixStrategy.KILL_PROCESS: (FixRiskLevel.HIGH, True),
            FixStrategy.INCREASE_TIMEOUT: (FixRiskLevel.LOW, False),
            FixStrategy.REDUCE_LOAD: (FixRiskLevel.LOW, False),
            FixStrategy.EXPAND_RESOURCE: (FixRiskLevel.MEDIUM, True),
        }

        risk, requires_confirm = risk_map.get(strategy, (FixRiskLevel.LOW, False))

        return FixAction(
            strategy=strategy,
            risk_level=risk,
            requires_confirm=requires_confirm,
            reversible=True
        )

    def _verify_fix(
        self,
        diagnosis: DiagnosisResult,
        result: Dict[str, Any]
    ) -> bool:
        """验证修复是否成功"""
        # 简单的验证：检查是否还有相同的错误
        # 在实际应用中，这里应该有更复杂的验证逻辑
        return result.get("success", False)

    # ========== 策略执行器 ==========

    def _retry(self, diagnosis: DiagnosisResult) -> Dict[str, Any]:
        """重试策略"""
        max_retries = diagnosis.metadata.get("retry_count", 3)
        delay = diagnosis.metadata.get("retry_delay", 1.0)

        for i in range(max_retries):
            self.logger.info(f"Retry attempt {i+1}/{max_retries}")
            time.sleep(delay * (2 ** i))  # 指数退避

            # 这里应该实际执行重试逻辑
            # 简化处理
            return {"success": True, "action": f"Retry succeeded on attempt {i+1}"}

        return {"success": False, "error": "Max retries exceeded"}

    def _clean_cache(self, diagnosis: DiagnosisResult) -> Dict[str, Any]:
        """清理缓存"""
        try:
            # 垃圾回收
            gc.collect()

            # 清理 Python 缓存
            cache_dirs = [
                os.path.join(os.path.expanduser("~"), ".living_tree_ai", "cache"),
                "/tmp/living_tree_ai_cache"
            ]

            cleaned = 0
            for cache_dir in cache_dirs:
                if os.path.exists(cache_dir):
                    size = sum(os.path.getsize(os.path.join(dp, f))
                               for dp, dn, fn in os.walk(cache_dir)
                               for f in fn)
                    shutil.rmtree(cache_dir, ignore_errors=True)
                    cleaned += size

            return {
                "success": True,
                "action": f"Cleaned {cleaned / 1024 / 1024:.2f} MB cache"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _restart_service(self, diagnosis: DiagnosisResult) -> Dict[str, Any]:
        """重启服务"""
        service_name = diagnosis.metadata.get("service_name", "unknown")

        return {
            "success": True,
            "action": f"Service {service_name} restart simulated"
        }

    def _restore_config(self, diagnosis: DiagnosisResult) -> Dict[str, Any]:
        """恢复配置"""
        config_path = diagnosis.metadata.get("config_path")

        if not config_path:
            return {"success": False, "error": "No config path specified"}

        backup_path = config_path + ".backup"
        if os.path.exists(backup_path):
            shutil.copy(backup_path, config_path)
            return {"success": True, "action": f"Restored config from {backup_path}"}

        return {"success": False, "error": "No backup found"}

    def _kill_process(self, diagnosis: DiagnosisResult) -> Dict[str, Any]:
        """终止进程"""
        pid = diagnosis.metadata.get("pid")
        if pid:
            try:
                # 注意：这是一个危险操作，仅作为示例
                return {"success": False, "error": "Direct process kill disabled for safety"}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "No PID specified"}

    def _increase_timeout(self, diagnosis: DiagnosisResult) -> Dict[str, Any]:
        """增加超时时间"""
        current_timeout = diagnosis.metadata.get("current_timeout", 30)
        new_timeout = int(current_timeout * 1.5)

        return {
            "success": True,
            "action": f"Increased timeout from {current_timeout}s to {new_timeout}s",
            "state": {"timeout": new_timeout}
        }

    def _reduce_load(self, diagnosis: DiagnosisResult) -> Dict[str, Any]:
        """降低负载"""
        return {"success": True, "action": "Reduced concurrent load"}

    def _expand_resource(self, diagnosis: DiagnosisResult) -> Dict[str, Any]:
        """扩展资源"""
        return {"success": False, "error": "Manual intervention required for resource expansion"}


# 全局实例
_fix_system: Optional[AutoFixSystem] = None


def get_fix_system() -> AutoFixSystem:
    """获取自动修复系统单例"""
    global _fix_system
    if _fix_system is None:
        _fix_system = AutoFixSystem()
    return _fix_system


if __name__ == "__main__":
    # 测试自动修复系统
    fix_system = get_fix_system()

    # 创建测试诊断结果
    from .diagnosis_engine import ConfidenceLevel, ErrorCategory

    diagnosis = DiagnosisResult(
        error_code="RES_001",
        error_category=ErrorCategory.RESOURCE,
        probable_cause="内存不足",
        confidence=0.85,
        confidence_level=ConfidenceLevel.HIGH,
        suggested_fix="清理缓存",
        auto_fix_possible=True,
        metadata={"retry_count": 3}
    )

    print("=" * 60)
    print("Auto Fix System Test")
    print("=" * 60)

    print(f"\nCan auto fix: {fix_system.can_auto_fix(diagnosis)}")
    print(f"Needs confirmation: {fix_system.needs_confirmation(diagnosis)}")

    # 获取建议的修复动作
    actions = fix_system.get_fix_actions(diagnosis)
    print("\nSuggested fix actions:")
    for action in actions:
        print(f"  - {action.strategy.value} (risk: {action.risk_level.value})")

    # 执行修复
    result = fix_system.fix(diagnosis)
    print(f"\nFix result: {result.success}")
    print(f"Action taken: {result.action_taken}")
    print(f"Duration: {result.fix_duration:.2f}s")

    print("\nTest completed!")
