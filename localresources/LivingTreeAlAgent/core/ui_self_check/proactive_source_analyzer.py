"""
主动式静默分析通道 - ProactiveSourceAnalyzer
核心理念：巡检员 - 在后台静默分析源码结构、交互逻辑

触发条件：操作成功但无响应、用户停留时间过长、特定高频操作
特点：低优先级，完全异步，绝不阻塞主线程
"""

import threading
import time
import logging
import os
import ast
from typing import Callable, Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import re

from .context_collector import ContextCollector, SilentContext
from .async_task_queue import AsyncTaskQueue, TaskPriority

logger = logging.getLogger(__name__)


class IssueSeverity(Enum):
    """问题严重程度"""
    INFO = 0       # 提示级
    WARNING = 1    # 警告级
    ERROR = 2      # 错误级


@dataclass
class SourceIssue:
    """源码问题"""
    issue_type: str           # 'logic_flaw' | 'performance_issue' | 'ux_suggestion'
    severity: IssueSeverity
    file_path: str
    line_number: int
    component_name: str
    description: str
    suggestion: str
    code_snippet: Optional[str] = None


@dataclass
class SourceAnalysisResult:
    """源码分析结果"""
    context: SilentContext
    issues: List[SourceIssue]
    analyzed_at: float
    analysis_duration_ms: float
    components_analyzed: int
    confidence: float = 0.8


class SourceCodeAnalyzer:
    """
    源码静态分析器

    分析维度：
    1. 逻辑缺陷：缺少加载状态、未处理异步错误
    2. 性能隐患：大文件未分片、循环中频繁更新DOM
    3. 体验建议：缺少Toast提示、操作反馈不明确
    """

    def __init__(self, project_root: str):
        self._project_root = project_root
        self._source_cache: Dict[str, str] = {}  # 文件源码缓存
        self._max_cache_size = 100

    def load_source(self, file_path: str) -> Optional[str]:
        """加载源码（带缓存）"""
        if file_path in self._source_cache:
            return self._source_cache[file_path]

        if not os.path.exists(file_path):
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 缓存管理
            if len(self._source_cache) >= self._max_cache_size:
                # 淘汰最旧的
                oldest = next(iter(self._source_cache))
                del self._source_cache[oldest]

            self._source_cache[file_path] = content
            return content
        except Exception as e:
            logger.error(f"Failed to load source {file_path}: {e}")
            return None

    def analyze_file(self, file_path: str, component_name: str) -> List[SourceIssue]:
        """分析单个文件"""
        issues = []
        content = self.load_source(file_path)

        if not content:
            return issues

        try:
            # 解析AST
            tree = ast.parse(content, filename=file_path)

            # 分析问题
            issues.extend(self._check_loading_state(tree, content, component_name))
            issues.extend(self._check_async_error_handling(tree, content, component_name))
            issues.extend(self._check_performance_issues(tree, content, component_name, file_path))
            issues.extend(self._check_ux_suggestions(tree, content, component_name))

        except SyntaxError:
            issues.append(SourceIssue(
                issue_type="syntax_error",
                severity=IssueSeverity.ERROR,
                file_path=file_path,
                line_number=0,
                component_name=component_name,
                description="Python语法错误",
                suggestion="检查语法错误"
            ))
        except Exception as e:
            logger.error(f"Analysis error for {file_path}: {e}")

        return issues

    def _check_loading_state(self, tree: ast.AST, content: str, component: str) -> List[SourceIssue]:
        """检查是否缺少加载状态"""
        issues = []

        # 查找可能缺少loading状态的函数
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_name = node.name.lower()
                has_async = isinstance(node, (ast.AsyncFunctionDef, ast.Await))

                # 检查是否有loading相关变量
                func_source = ast.get_source_segment(content, node)
                if func_source and has_async:
                    if 'loading' not in func_source.lower() and 'is_loading' not in func_source.lower():
                        # 可能缺少加载状态
                        if any(keyword in func_name for keyword in ['load', 'fetch', 'get', 'request']):
                            issues.append(SourceIssue(
                                issue_type="logic_flaw",
                                severity=IssueSeverity.WARNING,
                                file_path=component,
                                line_number=node.lineno or 0,
                                component_name=component,
                                description=f"异步函数 '{node.name}' 可能缺少加载状态",
                                suggestion=f"考虑添加 loading 状态来改善用户体验"
                            ))

        return issues

    def _check_async_error_handling(self, tree: ast.AST, content: str, component: str) -> List[SourceIssue]:
        """检查异步错误处理"""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                func_source = ast.get_source_segment(content, node)
                if func_source and 'try' not in func_source:
                    if any(keyword in node.name.lower() for keyword in ['fetch', 'load', 'get', 'request']):
                        issues.append(SourceIssue(
                            issue_type="logic_flaw",
                            severity=IssueSeverity.WARNING,
                            file_path=component,
                            line_number=node.lineno or 0,
                            component_name=component,
                            description=f"异步函数 '{node.name}' 缺少异常处理",
                            suggestion="添加 try-except 来捕获可能的异常"
                        ))

        return issues

    def _check_performance_issues(self, tree: ast.AST, content: str, component: str, file_path: str = "") -> List[SourceIssue]:
        """检查性能隐患"""
        issues = []

        for node in ast.walk(tree):
            # 检查循环中的DOM更新
            if isinstance(node, (ast.For, ast.While)):
                body_source = ast.get_source_segment(content, node)
                if body_source and ('append' in body_source or 'update' in body_source):
                    if len(body_source) > 500:  # 循环体较大
                        issues.append(SourceIssue(
                            issue_type="performance_issue",
                            severity=IssueSeverity.INFO,
                            file_path=file_path or component,
                            line_number=node.lineno or 0,
                            component_name=component,
                            description="循环中可能有频繁的列表/字典更新",
                            suggestion="考虑批量更新或使用更高效的数据结构"
                        ))

        return issues

    def _check_ux_suggestions(self, tree: ast.AST, content: str, component: str) -> List[SourceIssue]:
        """检查用户体验建议"""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_source = ast.get_source_segment(content, node)
                if func_source:
                    # 检查是否在操作成功后缺少反馈
                    if 'success' in func_source.lower() or 'complete' in func_source.lower():
                        if 'toast' not in func_source.lower() and 'notify' not in func_source.lower() and 'message' not in func_source.lower():
                            issues.append(SourceIssue(
                                issue_type="ux_suggestion",
                                severity=IssueSeverity.INFO,
                                file_path=component,
                                line_number=node.lineno or 0,
                                component_name=component,
                                description=f"操作成功后可能缺少用户反馈",
                                suggestion="考虑添加 Toast/Message 提示操作结果"
                            ))

        return issues


class ProactiveSourceAnalyzer:
    """
    主动式静默分析器

    特点：
    1. 延迟触发（3秒后）
    2. 后台静默分析
    3. 利用Source Map映射
    4. 完全异步，不阻塞
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._collector = ContextCollector()
        self._task_queue = AsyncTaskQueue()
        self._code_analyzer: Optional[SourceCodeAnalyzer] = None
        self._listeners: List[Callable] = []
        self._enabled = True
        self._analysis_count = 0
        self._whitelist_components: List[str] = []  # 只分析白名单组件
        self._last_activity_time = time.time()
        self._idle_threshold_seconds = 30  # 30秒空闲后分析

    def set_project_root(self, project_root: str):
        """设置项目根目录"""
        self._code_analyzer = SourceCodeAnalyzer(project_root)

    def set_ai_suggestion_callback(self, callback: Callable):
        """设置AI建议回调"""
        self._ai_callback = callback

    def add_listener(self, listener: Callable):
        """添加监听器"""
        self._listeners.append(listener)

    def set_idle_threshold(self, seconds: float):
        """设置空闲阈值"""
        self._idle_threshold_seconds = seconds

    def is_idle(self) -> bool:
        """检查是否空闲"""
        return (time.time() - self._last_activity_time) > self._idle_threshold_seconds

    def record_activity(self):
        """记录用户活动"""
        self._last_activity_time = time.time()
        # 用户活动时，抢占低优先级任务
        self._task_queue.preempt_low_priority()

    def submit_analysis(
        self,
        component_name: str,
        action: str,
        duration_ms: float,
        response_status: str = "success",
        callback: Optional[Callable] = None
    ) -> str:
        """
        提交静默分析任务

        带3秒防抖，只有用户空闲时才真正执行
        """
        if not self._enabled:
            return ""

        # 检查白名单
        if self._whitelist_components and component_name not in self._whitelist_components:
            return ""

        # 记录活动
        self.record_activity()

        # 采集上下文
        context = self._collector.collect_silent_context(
            component_name=component_name,
            action=action,
            duration_ms=duration_ms,
            response_status=response_status
        )

        # 判断是否需要分析
        if response_status == "success" and duration_ms < 1000:
            # 快速成功操作，不需要分析
            return ""

        task_context = {
            "context": context,
            "callback": callback,
            "component_name": component_name
        }

        def handler(ctx: Dict) -> SourceAnalysisResult:
            return self._perform_analysis(ctx["context"], ctx["component_name"])

        task_id = self._task_queue.submit_silent_analysis(
            context=task_context,
            callback=lambda r: self._handle_analysis_result(r, callback),
            handler=handler,
            component_key=f"source_{component_name}",
            debounce_delay=3.0  # 3秒防抖
        )

        return task_id

    def _perform_analysis(self, context: SilentContext, component_name: str) -> SourceAnalysisResult:
        """执行分析"""
        start_time = time.time()

        issues: List[SourceIssue] = []

        # 如果有源码分析器，进行静态分析
        if self._code_analyzer:
            # 查找相关源文件
            source_files = self._find_component_files(component_name)
            for file_path in source_files:
                file_issues = self._code_analyzer.analyze_file(file_path, component_name)
                issues.extend(file_issues)

        # AI增强分析（如果设置了回调）
        if hasattr(self, '_ai_callback') and self._ai_callback:
            try:
                ai_issues = self._ai_callback(context, issues)
                if ai_issues:
                    issues.extend(ai_issues)
            except Exception as e:
                logger.error(f"AI analysis failed: {e}")

        duration_ms = (time.time() - start_time) * 1000
        self._analysis_count += 1

        return SourceAnalysisResult(
            context=context,
            issues=issues,
            analyzed_at=time.time(),
            analysis_duration_ms=duration_ms,
            components_analyzed=len(set(i.component_name for i in issues)),
            confidence=0.8
        )

    def _find_component_files(self, component_name: str) -> List[str]:
        """查找组件对应的源文件"""
        # 简化实现，实际应该用source map
        if not self._code_analyzer:
            return []

        project_root = self._code_analyzer._project_root
        files = []

        # 查找可能的文件
        for root, dirs, filenames in os.walk(project_root):
            for filename in filenames:
                if component_name.lower() in filename.lower():
                    files.append(os.path.join(root, filename))

        return files[:5]  # 最多返回5个

    def _handle_analysis_result(self, result: Any, callback: Optional[Callable]):
        """处理分析结果"""
        if callback and result:
            callback(result)
        if result:
            self._notify_listeners(result)

    def _notify_listeners(self, result: SourceAnalysisResult):
        """通知监听器"""
        for listener in self._listeners:
            try:
                listener(result)
            except Exception as e:
                logger.error(f"Listener error: {e}")

    def add_to_whitelist(self, component_name: str):
        """添加到分析白名单"""
        if component_name not in self._whitelist_components:
            self._whitelist_components.append(component_name)

    def remove_from_whitelist(self, component_name: str):
        """从白名单移除"""
        if component_name in self._whitelist_components:
            self._whitelist_components.remove(component_name)

    def enable(self):
        """启用"""
        self._enabled = True

    def disable(self):
        """禁用"""
        self._enabled = False

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            "analysis_count": self._analysis_count,
            "whitelist_size": len(self._whitelist_components),
            "idle_threshold": self._idle_threshold_seconds,
            "last_activity": self._last_activity_time
        }


proactive_analyzer = ProactiveSourceAnalyzer()
