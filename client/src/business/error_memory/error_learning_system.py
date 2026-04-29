# -*- coding: utf-8 -*-
"""
Error Learning System - 错误学习系统
===================================

智能错误修复记忆与复用系统主入口

核心功能：
1. 错误检测与记录
2. 模式匹配与推荐
3. 修复执行与验证
4. 知识学习与进化

Author: LivingTreeAI Agent
Date: 2026-04-24
from __future__ import annotations
"""

from client.src.business.logger import get_logger
logger = get_logger('error_memory.error_learning_system')


import re
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
import traceback

try:
    from .error_models import (
        ErrorSurfaceFeatures,
        ErrorRecord,
        FixStatus,
        ErrorCategory,
        ErrorSeverity,
        PRESET_PATTERNS,
        PRESET_TEMPLATES,
    )
except ImportError:
    from error_models import (
        ErrorSurfaceFeatures,
        ErrorRecord,
        FixStatus,
        ErrorCategory,
        ErrorSeverity,
        PRESET_PATTERNS,
        PRESET_TEMPLATES,
    )

try:
    from .pattern_matcher import ErrorPatternMatcher, MatcherConfig, get_matcher
except ImportError:
    from pattern_matcher import ErrorPatternMatcher, MatcherConfig, get_matcher

try:
    from .error_knowledge_base import ErrorKnowledgeBase, KnowledgeBaseConfig, get_knowledge_base
except ImportError:
    from error_knowledge_base import ErrorKnowledgeBase, KnowledgeBaseConfig, get_knowledge_base


# ═══════════════════════════════════════════════════════════════════════════════
# 错误学习系统
# ═══════════════════════════════════════════════════════════════════════════════

class ErrorLearningSystem:
    """
    错误学习系统
    
    智能错误修复记忆与复用系统的统一入口
    
    使用示例：
    ```python
    from client.src.business.error_memory import ErrorLearningSystem

    
    # 初始化
    els = ErrorLearningSystem()
    
    # 记录并获取修复方案
    result = els.learn_and_fix(
        error_message="UnicodeDecodeError: 'utf-8' codec can't decode byte 0xd6",
        context={"operation": "read_file", "file": "data.csv"}
    )
    
    logger.info(f"匹配模式: {result['matched_pattern']['pattern_name']}")
    logger.info(f"推荐方案: {result['recommended_templates'][0]['template_name']}")
    ```
    """

    def __init__(
        self,
        auto_learn: bool = True,
        storage_path: str = "./error_knowledge",
    ):
        """
        初始化错误学习系统
        
        Args:
            auto_learn: 是否自动学习新错误模式
            storage_path: 知识库存储路径
        """
        self.auto_learn = auto_learn
        
        # 初始化组件
        self.matcher = get_matcher()
        self.knowledge_base = get_knowledge_base()
        
        # 配置知识库
        config = KnowledgeBaseConfig(
            storage_path=storage_path,
            auto_learn_enabled=auto_learn,
        )
        
        # 回调
        self._on_error_recorded: Optional[Callable] = None
        self._on_fix_applied: Optional[Callable] = None
        
        # 统计
        self._stats = {
            "total_errors": 0,
            "resolved_errors": 0,
            "auto_fixed_errors": 0,
            "new_patterns_learned": 0,
            "new_templates_created": 0,
        }
        
        logger.info(f"[ErrorLearningSystem] 已初始化")
        logger.info(f"  - 自动学习: {auto_learn}")
        logger.info(f"  - 知识库路径: {storage_path}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 核心API
    # ═══════════════════════════════════════════════════════════════════════════

    def learn_and_fix(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        学习并修复错误（同步版本）
        
        Args:
            error: 异常对象
            context: 额外上下文
            
        Returns:
            包含修复方案的字典
        """
        # 1. 提取错误特征
        surface = self._extract_from_exception(error, context)
        
        # 2. 记录错误
        record = self.knowledge_base.record_error(surface, context)
        self._stats["total_errors"] += 1
        
        # 3. 查找解决方案
        solution = self.knowledge_base.find_solution(surface, context)
        
        # 添加记录信息
        solution["record_id"] = record.record_id
        
        # 触发回调
        if self._on_error_recorded:
            self._on_error_recorded(record)
        
        return solution

    def learn_and_fix_from_message(
        self,
        error_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        从错误消息学习并修复
        
        Args:
            error_message: 错误消息字符串
            context: 额外上下文
            
        Returns:
            包含修复方案的字典
        """
        # 1. 提取错误特征
        surface = self._extract_from_message(error_message, context)
        
        # 2. 记录错误
        record = self.knowledge_base.record_error(surface, context)
        self._stats["total_errors"] += 1
        
        # 3. 查找解决方案
        solution = self.knowledge_base.find_solution(surface, context)
        
        # 添加记录信息
        solution["record_id"] = record.record_id
        
        # 触发回调
        if self._on_error_recorded:
            self._on_error_recorded(record)
        
        return solution

    def report_fix_result(
        self,
        record_id: str,
        template_id: str,
        success: bool,
        execution_time: float = 0.0,
        error_message: Optional[str] = None,
    ):
        """
        报告修复结果
        
        Args:
            record_id: 错误记录ID
            template_id: 使用的模板ID
            success: 是否成功
            execution_time: 执行时间
            error_message: 错误信息
        """
        self.knowledge_base.apply_fix(
            record_id=record_id,
            template_id=template_id,
            success=success,
            execution_time=execution_time,
            error_message=error_message,
        )
        
        if success:
            self._stats["resolved_errors"] += 1
            self._stats["auto_fixed_errors"] += 1
        
        # 触发回调
        if self._on_fix_applied:
            self._on_fix_applied(record_id, template_id, success)

    def learn_from_custom_fix(
        self,
        record_id: str,
        fix_steps: List[str],
        success: bool,
    ) -> Optional[str]:
        """
        从自定义修复中学习
        
        Args:
            record_id: 错误记录ID
            fix_steps: 修复步骤
            success: 是否成功
            
        Returns:
            新创建的模板ID
        """
        if success and self.auto_learn:
            template_id = self.knowledge_base.learn_from_fix(
                record_id=record_id,
                custom_fix_steps=fix_steps,
                success=success,
            )
            
            if template_id:
                self._stats["new_templates_created"] += 1
                return template_id
        
        return None

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        kb_stats = self.knowledge_base.get_statistics()
        
        return {
            **self._stats,
            "knowledge_base": kb_stats,
            "matcher": self.matcher.get_pattern_stats(),
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # 错误特征提取
    # ═══════════════════════════════════════════════════════════════════════════

    def _extract_from_exception(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
    ) -> ErrorSurfaceFeatures:
        """从异常提取特征"""
        context = context or {}
        
        # 提取错误消息
        error_message = str(error)
        
        # 提取错误类型
        error_type = type(error).__name__
        
        # 提取文件路径和行号
        tb = traceback.extract_tb(error.__traceback__)
        file_path = None
        line_number = None
        function_name = None
        
        if tb:
            frame = tb[-1]  # 最内层
            file_path = frame.filename
            line_number = frame.lineno
            function_name = frame.name
        
        return ErrorSurfaceFeatures(
            raw_message=error_message,
            error_type=error_type,
            error_code=None,
            file_path=file_path,
            line_number=line_number,
            function_name=function_name,
            os_platform=context.get("platform"),
            python_version=context.get("python_version"),
            environment=context.get("environment"),
            operation_type=context.get("operation"),
            target_resource=context.get("resource"),
            input_data_type=context.get("data_type"),
        )

    def _extract_from_message(
        self,
        error_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ErrorSurfaceFeatures:
        """从错误消息提取特征"""
        context = context or {}
        
        # 提取错误类型
        error_type_match = re.search(r"(\w+Error|\w+Exception)", error_message)
        error_type = error_type_match.group(1) if error_type_match else "UnknownError"
        
        # 提取文件路径
        file_path_match = re.search(r"['\"]([^\"']+\.py)['\"]", error_message)
        file_path = file_path_match.group(1) if file_path_match else None
        
        # 提取行号
        line_match = re.search(r"line (\d+)", error_message)
        line_number = int(line_match.group(1)) if line_match else None
        
        # 提取函数名
        func_match = re.search(r"in (\w+)\(", error_message)
        function_name = func_match.group(1) if func_match else None
        
        return ErrorSurfaceFeatures(
            raw_message=error_message,
            error_type=error_type,
            error_code=None,
            file_path=file_path,
            line_number=line_number,
            function_name=function_name,
            os_platform=context.get("platform"),
            python_version=context.get("python_version"),
            environment=context.get("environment"),
            operation_type=context.get("operation"),
            target_resource=context.get("resource"),
            input_data_type=context.get("data_type"),
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # 装饰器
    # ═══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def error_learning_decorator(els: 'ErrorLearningSystem'):
        """
        错误学习装饰器
        
        使用示例：
        ```python
        els = ErrorLearningSystem()
        
        @els.error_learning_decorator(els)
        def my_function(x):
            # 你的代码
            pass
        ```
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # 记录错误
                    solution = els.learn_and_fix(e, {"function": func.__name__})
                    
                    # 抛出带解决方案的异常
                    raise ErrorWithSolution(e, solution) from e
            
            return wrapper
        return decorator

    # ═══════════════════════════════════════════════════════════════════════════
    # 回调设置
    # ═══════════════════════════════════════════════════════════════════════════

    def set_on_error_recorded(self, callback: Callable):
        """设置错误记录回调"""
        self._on_error_recorded = callback

    def set_on_fix_applied(self, callback: Callable):
        """设置修复应用回调"""
        self._on_fix_applied = callback


# ═══════════════════════════════════════════════════════════════════════════════
# 带解决方案的异常
# ═══════════════════════════════════════════════════════════════════════════════

class ErrorWithSolution(Exception):
    """带解决方案的异常"""
    
    def __init__(self, original_error: Exception, solution: Dict[str, Any]):
        self.original_error = original_error
        self.solution = solution
        super().__init__(str(original_error))


# ═══════════════════════════════════════════════════════════════════════════════
# 上下文管理器
# ═══════════════════════════════════════════════════════════════════════════════

class ErrorLearningContext:
    """错误学习上下文管理器"""
    
    def __init__(self, els: ErrorLearningSystem, context: Dict[str, Any]):
        self.els = els
        self.context = context
        self.current_record_id: Optional[str] = None
        self.fix_steps: List[str] = []
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None and exc_val is not None:
            # 记录错误
            solution = self.els.learn_and_fix(exc_val, self.context)
            self.current_record_id = solution.get("record_id")
            
            # 保存解决方案信息
            exc_val._solution = solution  # type: ignore
        
        return False  # 不抑制异常
    
    def report_fix(self, template_id: str, success: bool):
        """报告修复结果"""
        if self.current_record_id:
            self.els.report_fix_result(
                record_id=self.current_record_id,
                template_id=template_id,
                success=success,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 快速使用API
# ═══════════════════════════════════════════════════════════════════════════════

_system: Optional[ErrorLearningSystem] = None


def get_error_system() -> ErrorLearningSystem:
    """获取错误学习系统实例"""
    global _system
    if _system is None:
        _system = ErrorLearningSystem()
    return _system


def quick_learn(error: Exception, context: Optional[Dict] = None) -> Dict[str, Any]:
    """
    快速学习错误并获取解决方案
    
    使用示例：
    ```python
    try:
        # 你的代码
        data = json.loads(invalid_json)
    except Exception as e:
        solution = quick_learn(e, {"operation": "json_parse"})
        logger.info(solution["matched_pattern"]["pattern_name"])
    ```
    """
    system = get_error_system()
    return system.learn_and_fix(error, context)


def quick_fix_from_message(
    error_message: str,
    context: Optional[Dict] = None,
) -> Dict[str, Any]:
    """快速从错误消息获取修复方案"""
    system = get_error_system()
    return system.learn_and_fix_from_message(error_message, context)


def quick_fix_from_exception(
    error: Exception,
    context: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    快速从异常获取修复方案
    
    使用示例：
    ```python
    try:
        # 你的代码
        process_data()
    except Exception as e:
        solution = quick_fix_from_exception(e, {"operation": "data_process"})
    ```
    """
    system = get_error_system()
    return system.learn_and_fix(error, context)
