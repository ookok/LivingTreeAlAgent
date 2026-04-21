# -*- coding: utf-8 -*-
"""
🐍 Python智能日志分析与自动修复系统 - Python Mind
==================================================

核心理念: "从错误中学习，从日志中洞察，自动诊断，智能修复"

三层架构:
- Log Ingestion Layer: 实时日志收集、结构化解析、上下文关联
- Intelligent Analysis Layer: 错误模式识别、根因分析、代码关联
- Auto-Fix Generation Layer: 代码补丁生成、配置优化、测试用例生成

Author: Hermes Desktop Team
Version: 1.0.0
"""

import ast
import asyncio
import datetime
import hashlib
import importlib
import inspect
import json
import linecache
import os
import re
import sys
import threading
import traceback
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Tuple, Set
from io import StringIO
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================
# 枚举定义
# ============================================================

class ErrorSeverity(Enum):
    """错误严重性级别"""
    BLOCKER = "blocker"      # 阻断性问题
    CRITICAL = "critical"    # 严重问题
    MAJOR = "major"          # 主要问题
    MINOR = "minor"          # 次要问题
    TRIVIAL = "trivial"       # 轻微问题
    INFO = "info"            # 信息


class ErrorCategory(Enum):
    """错误类别"""
    SYNTAX_ERROR = "syntax_error"
    IMPORT_ERROR = "import_error"
    TYPE_ERROR = "type_error"
    VALUE_ERROR = "value_error"
    KEY_ERROR = "key_error"
    ATTRIBUTE_ERROR = "attribute_error"
    IO_ERROR = "io_error"
    TIMEOUT_ERROR = "timeout_error"
    MEMORY_ERROR = "memory_error"
    CONCURRENCY_ERROR = "concurrency_error"
    PERMISSION_ERROR = "permission_error"
    CONFIG_ERROR = "config_error"
    DEPENDENCY_ERROR = "dependency_error"
    API_ERROR = "api_error"
    DATA_ERROR = "data_error"
    RUNTIME_ERROR = "runtime_error"
    UNKNOWN = "unknown"


class FixStatus(Enum):
    """修复状态"""
    PENDING = "pending"
    APPLIED = "applied"
    TESTED = "tested"
    FAILED = "failed"
    REVERTED = "reverted"


class AnalysisStatus(Enum):
    """分析状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================
# 数据类定义
# ============================================================

@dataclass
class LogEntry:
    """日志条目"""
    entry_id: str
    timestamp: str
    level: str                          # DEBUG/INFO/WARNING/ERROR/CRITICAL
    message: str
    source: str                         # stderr/stdout/file/metrics
    raw_content: str
    parsed_data: Dict = field(default_factory=dict)
    context: Dict = field(default_factory=dict)
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    traceback: Optional[str] = None


@dataclass
class CodeLocation:
    """代码位置"""
    file_path: str
    line_number: int
    column_number: int = 0
    function_name: str = ""
    class_name: Optional[str] = None


@dataclass
class ErrorPattern:
    """错误模式"""
    pattern_id: str
    name: str
    category: ErrorCategory
    severity: ErrorSeverity
    description: str
    detection_regex: Optional[str] = None
    symptoms: List[str] = field(default_factory=list)
    root_causes: List[str] = field(default_factory=list)
    fix_templates: List[Dict] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)


@dataclass
class ErrorAnalysis:
    """错误分析结果"""
    analysis_id: str
    timestamp: str
    error_type: ErrorCategory
    severity: ErrorSeverity
    matched_patterns: List[str]
    error_message: str
    error_location: Optional[CodeLocation]
    code_context: Optional[str]
    root_cause: Dict
    fix_suggestions: List['FixSuggestion']
    confidence: float
    status: AnalysisStatus
    metadata: Dict = field(default_factory=dict)


@dataclass
class FixSuggestion:
    """修复建议"""
    fix_id: str
    title: str
    description: str
    fix_type: str                        # code/config/dependency/environment/architecture
    patch_type: str                      # syntax_correction/import_addition/null_check等
    code_snippet: str
    original_code: str
    fixed_code: str
    confidence: float
    difficulty: str                     # easy/medium/hard
    risk_level: str                      # low/medium/high
    expected_impact: str
    test_cases: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    side_effects: List[str] = field(default_factory=list)


@dataclass
class CodePatch:
    """代码补丁"""
    patch_id: str
    file_path: str
    line_start: int
    line_end: int
    original_snippet: str
    patched_snippet: str
    diff: str
    applied: bool = False
    verified: bool = False
    verification_result: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


@dataclass
class TestCase:
    """测试用例"""
    test_id: str
    test_name: str
    test_type: str                       # unit/integration/regression/boundary/fuzz
    code: str
    expected_result: str
    is_passing: Optional[bool] = None


@dataclass
class AnalysisReport:
    """分析报告"""
    report_id: str
    timestamp: str
    error_analysis: ErrorAnalysis
    root_cause_analysis: Dict
    fix_recommendations: List[FixSuggestion]
    generated_patches: List[CodePatch]
    test_cases: List[TestCase]
    prevention_strategies: List[str]
    monitoring_suggestions: List[str]
    markdown_content: str = ""


# ============================================================
# 日志收集器 (Log Ingestion Layer)
# ============================================================

class LogCollector:
    """多源日志收集器"""

    def __init__(self):
        self.sources: Dict[str, Any] = {}
        self.parsers: List[Callable] = []
        self.log_buffer: List[LogEntry] = []
        self.max_buffer_size = 10000
        self._init_parsers()

    def _init_parsers(self):
        """初始化日志解析器"""
        self.parsers = [
            self._parse_standard_logging,
            self._parse_print_statements,
            self._parse_exception_traceback,
            self._parse_json_logs,
            self._parse_python_error_format,
        ]

    def collect_from_stderr(self, raw_log: str) -> Optional[LogEntry]:
        """从stderr收集日志"""
        return self._parse_log_entry(raw_log, "stderr")

    def collect_from_stdout(self, raw_log: str) -> Optional[LogEntry]:
        """从stdout收集日志"""
        return self._parse_log_entry(raw_log, "stdout")

    def collect_from_exception(self, exc_type, exc_value, exc_traceback) -> LogEntry:
        """从异常收集日志"""
        timestamp = datetime.datetime.now().isoformat()
        entry_id = f"exc_{hashlib.md5(f'{timestamp}{str(exc_value)}'.encode()).hexdigest()[:12]}"

        # 格式化traceback
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

        # 解析异常信息
        parsed_data = self._parse_exception_details(exc_type, exc_value, exc_traceback)

        return LogEntry(
            entry_id=entry_id,
            timestamp=timestamp,
            level="ERROR",
            message=str(exc_value),
            source="exception",
            raw_content=tb_str,
            parsed_data=parsed_data,
            error_type=exc_type.__name__ if exc_type else None,
            error_message=str(exc_value),
            traceback=tb_str
        )

    def _parse_log_entry(self, raw_log: str, source: str) -> Optional[LogEntry]:
        """解析日志条目"""
        for parser in self.parsers:
            try:
                parsed = parser(raw_log, source)
                if parsed:
                    return self._enrich_log_entry(parsed)
            except Exception as e:
                logger.debug(f"Parser failed: {e}")
                continue

        # 回退解析
        return self._fallback_parse(raw_log, source)

    def _parse_standard_logging(self, raw_log: str, source: str) -> Optional[LogEntry]:
        """解析标准logging格式"""
        # 标准格式: 2024-01-01 12:00:00,000 ERROR module - message
        pattern = r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3})\s+(\w+)\s+(\S+)\s+-\s+(.*)"
        match = re.match(pattern, raw_log)

        if match:
            timestamp, level, module, message = match.groups()
            entry_id = f"log_{hashlib.md5(raw_log.encode()).hexdigest()[:12]}"

            return LogEntry(
                entry_id=entry_id,
                timestamp=timestamp,
                level=level,
                message=message,
                source=source,
                raw_content=raw_log,
                parsed_data={"module": module}
            )
        return None

    def _parse_print_statements(self, raw_log: str, source: str) -> Optional[LogEntry]:
        """解析print语句"""
        # 简单的print输出检测
        if not raw_log.strip().startswith("20") and not raw_log.strip().startswith("{"):
            timestamp = datetime.datetime.now().isoformat()
            entry_id = f"print_{hashlib.md5(raw_log.encode()).hexdigest()[:12]}"

            return LogEntry(
                entry_id=entry_id,
                timestamp=timestamp,
                level="INFO",
                message=raw_log.strip(),
                source=source,
                raw_content=raw_log
            )
        return None

    def _parse_exception_traceback(self, raw_log: str, source: str) -> Optional[LogEntry]:
        """解析异常traceback"""
        tb_pattern = r'Traceback \(most recent call last\):(.*?)(?:\n\S|\Z)'
        match = re.search(tb_pattern, raw_log, re.DOTALL)

        if match:
            tb_content = match.group(0)
            lines = tb_content.split("\n")

            # 提取最后一行作为错误消息
            error_msg = ""
            for line in reversed(lines):
                if line.strip() and not line.strip().startswith("File"):
                    error_msg = line.strip()
                    break

            timestamp = datetime.datetime.now().isoformat()
            entry_id = f"tb_{hashlib.md5(raw_log.encode()).hexdigest()[:12]}"

            return LogEntry(
                entry_id=entry_id,
                timestamp=timestamp,
                level="ERROR",
                message=error_msg,
                source=source,
                raw_content=raw_log,
                traceback=tb_content
            )
        return None

    def _parse_json_logs(self, raw_log: str, source: str) -> Optional[LogEntry]:
        """解析JSON格式日志"""
        try:
            data = json.loads(raw_log)
            if isinstance(data, dict) and "message" in data:
                entry_id = f"json_{hashlib.md5(raw_log.encode()).hexdigest()[:12]}"
                return LogEntry(
                    entry_id=entry_id,
                    timestamp=data.get("timestamp", datetime.datetime.now().isoformat()),
                    level=data.get("level", "INFO"),
                    message=data["message"],
                    source=source,
                    raw_content=raw_log,
                    parsed_data=data
                )
        except json.JSONDecodeError:
            pass
        return None

    def _parse_python_error_format(self, raw_log: str, source: str) -> Optional[LogEntry]:
        """解析Python错误格式"""
        # 检测 Python 错误格式: ErrorType: message
        error_pattern = r'(\w+Error|\w+Exception):\s*(.*)'
        match = re.match(error_pattern, raw_log.strip())

        if match:
            error_type, error_msg = match.groups()
            timestamp = datetime.datetime.now().isoformat()
            entry_id = f"pyerr_{hashlib.md5(raw_log.encode()).hexdigest()[:12]}"

            return LogEntry(
                entry_id=entry_id,
                timestamp=timestamp,
                level="ERROR",
                message=error_msg.strip(),
                source=source,
                raw_content=raw_log,
                error_type=error_type,
                error_message=error_msg.strip()
            )
        return None

    def _parse_exception_details(self, exc_type, exc_value, exc_traceback) -> Dict:
        """解析异常详情"""
        details = {
            "exception_type": exc_type.__name__ if exc_type else None,
            "exception_message": str(exc_value),
            "traceback_frames": []
        }

        # 提取traceback帧
        for frame in traceback.extract_tb(exc_traceback):
            details["traceback_frames"].append({
                "filename": frame.filename,
                "lineno": frame.lineno,
                "function": frame.name,
                "code": frame.line
            })

        return details

    def _fallback_parse(self, raw_log: str, source: str) -> LogEntry:
        """回退解析"""
        timestamp = datetime.datetime.now().isoformat()
        entry_id = f"fallback_{hashlib.md5(raw_log.encode()).hexdigest()[:12]}"

        return LogEntry(
            entry_id=entry_id,
            timestamp=timestamp,
            level="INFO",
            message=raw_log.strip()[:500],
            source=source,
            raw_content=raw_log
        )

    def _enrich_log_entry(self, entry: LogEntry) -> LogEntry:
        """丰富日志条目上下文"""
        # 添加进程/线程信息
        try:
            import psutil
            process = psutil.Process()

            entry.context = {
                "process_id": os.getpid(),
                "thread_id": threading.get_ident(),
                "thread_name": threading.current_thread().name,
                "call_stack": self._get_call_stack(),
                "code_location": self._get_code_location(),
                "memory_usage_mb": process.memory_info().rss / 1024 / 1024,
                "cpu_percent": process.cpu_percent(),
                "python_path": sys.path[:3],
                "working_directory": os.getcwd(),
            }
        except ImportError:
            entry.context = {
                "process_id": os.getpid(),
                "thread_id": threading.get_ident(),
                "call_stack": self._get_call_stack()
            }

        return entry

    def _get_call_stack(self, limit: int = 10) -> List[Dict]:
        """获取调用栈"""
        stack = []
        for i, (filename, lineno, func, code) in enumerate(inspect.stack()[:limit]):
            stack.append({
                "frame": i,
                "filename": filename,
                "lineno": lineno,
                "function": func,
                "code": code if code else ""
            })
        return stack

    def _get_code_location(self) -> Dict:
        """获取代码位置"""
        frame = inspect.currentframe()
        if frame:
            caller_frame = frame.f_back
            if caller_frame:
                return {
                    "filename": caller_frame.f_code.co_filename,
                    "lineno": caller_frame.f_lineno,
                    "function": caller_frame.f_code.co_name
                }
        return {}

    def add_to_buffer(self, entry: LogEntry):
        """添加到缓冲区"""
        self.log_buffer.append(entry)
        if len(self.log_buffer) > self.max_buffer_size:
            self.log_buffer.pop(0)

    def get_buffer(self) -> List[LogEntry]:
        """获取缓冲区"""
        return self.log_buffer.copy()

    def clear_buffer(self):
        """清空缓冲区"""
        self.log_buffer.clear()


# ============================================================
# 错误模式识别系统 (Analysis Layer)
# ============================================================

class ErrorPatternRecognizer:
    """错误模式识别器"""

    def __init__(self):
        self.patterns: Dict[str, ErrorPattern] = {}
        self.ml_model = None
        self._init_patterns()

    def _init_patterns(self):
        """初始化预定义错误模式"""
        patterns = [
            ErrorPattern(
                pattern_id="syntax_error",
                name="语法错误",
                category=ErrorCategory.SYNTAX_ERROR,
                severity=ErrorSeverity.BLOCKER,
                description="Python代码存在语法错误",
                detection_regex=r'SyntaxError:\s*(.*)',
                symptoms=["代码无法解析", "缩进不正确", "括号不匹配"],
                root_causes=["打字错误", "缩进混乱", "语法规则违反"],
                examples=["print('hello)", "def foo: pass"]
            ),
            ErrorPattern(
                pattern_id="import_error",
                name="导入错误",
                category=ErrorCategory.IMPORT_ERROR,
                severity=ErrorSeverity.CRITICAL,
                description="模块导入失败",
                detection_regex=r'ImportError:\s*(.*)|ModuleNotFoundError:\s*(.*)',
                symptoms=["找不到模块", "循环导入", "导入路径错误"],
                root_causes=["未安装依赖", "PYTHONPATH配置错误", "包名拼写错误"],
                examples=["import numpy", "from pandas import Datafram"]
            ),
            ErrorPattern(
                pattern_id="type_error",
                name="类型错误",
                category=ErrorCategory.TYPE_ERROR,
                severity=ErrorSeverity.MAJOR,
                description="操作使用了错误的数据类型",
                detection_regex=r'TypeError:\s*(.*)',
                symptoms=["类型不匹配", "操作不支持该类型"],
                root_causes=["参数类型错误", "函数期望类型不一致"],
                examples=["'str' + 123", "len(123)"]
            ),
            ErrorPattern(
                pattern_id="value_error",
                name="值错误",
                category=ErrorCategory.VALUE_ERROR,
                severity=ErrorSeverity.MAJOR,
                description="参数值不符合函数要求",
                detection_regex=r'ValueError:\s*(.*)',
                symptoms=["参数值无效", "转换失败"],
                root_causes=["参数值超出范围", "格式不正确"],
                examples=["int('abc')", "range(5)[10]"]
            ),
            ErrorPattern(
                pattern_id="key_error",
                name="键错误",
                category=ErrorCategory.KEY_ERROR,
                severity=ErrorSeverity.MINOR,
                description="字典中找不到指定的键",
                detection_regex=r"KeyError:\s*'([^']+)'",
                symptoms=["字典访问失败", "配置键不存在"],
                root_causes=["键名拼写错误", "键不存在", "大小写不匹配"],
                examples=["d = {}; d['key']"]
            ),
            ErrorPattern(
                pattern_id="attribute_error",
                name="属性错误",
                category=ErrorCategory.ATTRIBUTE_ERROR,
                severity=ErrorSeverity.MAJOR,
                description="对象没有该属性或方法",
                detection_regex=r"AttributeError:\s*(.*)",
                symptoms=["方法不存在", "属性未定义"],
                root_causes=["拼写错误", "对象类型错误", "版本不兼容"],
                examples=["'str'.split(',')", "None.fn()"]
            ),
            ErrorPattern(
                pattern_id="io_error",
                name="IO错误",
                category=ErrorCategory.IO_ERROR,
                severity=ErrorSeverity.MAJOR,
                description="输入输出操作失败",
                detection_regex=r'(IOError|OSError|FileNotFoundError):\s*(.*)',
                symptoms=["文件不存在", "权限不足", "磁盘空间不足"],
                root_causes=["路径错误", "权限问题", "文件被占用"],
                examples=["open('/nonexistent/file.txt')"]
            ),
            ErrorPattern(
                pattern_id="timeout_error",
                name="超时错误",
                category=ErrorCategory.TIMEOUT_ERROR,
                severity=ErrorSeverity.MAJOR,
                description="操作超时",
                detection_regex=r'TimeoutError:\s*(.*)|timed out',
                symptoms=["请求超时", "连接超时"],
                root_causes=["网络延迟", "服务端响应慢", "死循环"],
                examples=["requests.get(url, timeout=0.001)"]
            ),
            ErrorPattern(
                pattern_id="memory_error",
                name="内存错误",
                category=ErrorCategory.MEMORY_ERROR,
                severity=ErrorSeverity.CRITICAL,
                description="内存不足或内存泄漏",
                detection_regex=r'MemoryError:\s*(.*)',
                symptoms=["内存耗尽", "OOM killer"],
                root_causes=["数据量过大", "内存泄漏", "无限创建对象"],
                examples=["[None] * (10**10)"]
            ),
            ErrorPattern(
                pattern_id="index_error",
                name="索引错误",
                category=ErrorCategory.VALUE_ERROR,
                severity=ErrorSeverity.MINOR,
                description="序列索引超出范围",
                detection_regex=r'IndexError:\s*(.*)',
                symptoms=["列表索引越界", "字符串索引越界"],
                root_causes=["索引计算错误", "空序列访问"],
                examples=["[1,2,3][10]", "''[0]"]
            ),
            ErrorPattern(
                pattern_id="zero_division_error",
                name="除零错误",
                category=ErrorCategory.VALUE_ERROR,
                severity=ErrorSeverity.MINOR,
                description="除法或取模运算的除数为零",
                detection_regex=r'ZeroDivisionError:\s*(.*)',
                symptoms=["除数为零", "取模运算除数为零"],
                root_causes=["除数变量未初始化", "条件判断遗漏"],
                examples=["1/0", "10 % 0"]
            ),
            ErrorPattern(
                pattern_id="assertion_error",
                name="断言错误",
                category=ErrorCategory.RUNTIME_ERROR,
                severity=ErrorSeverity.MAJOR,
                description="断言条件不满足",
                detection_regex=r'AssertionError:\s*(.*)',
                symptoms=["调试断言失败", "条件检查不通过"],
                root_causes=["预期条件未满足", "内部一致性检查失败"],
                examples=["assert False", "assert x > 0"]
            ),
            ErrorPattern(
                pattern_id="recursion_error",
                name="递归错误",
                category=ErrorCategory.RUNTIME_ERROR,
                severity=ErrorSeverity.CRITICAL,
                description="递归深度超出限制",
                detection_regex=r'RecursionError:\s*(.*)',
                symptoms=["无限递归", "调用栈溢出"],
                root_causes=["递归终止条件缺失", "递归深度过大"],
                examples=["def f(): return f()"]
            ),
        ]

        for pattern in patterns:
            self.patterns[pattern.pattern_id] = pattern

        logger.info(f"[PythonMind] 📋 已加载 {len(self.patterns)} 个错误模式")

    def recognize(self, log_entry: LogEntry) -> List[str]:
        """识别错误模式"""
        matched = []
        message = log_entry.message or ""
        raw = log_entry.raw_content or ""

        for pattern_id, pattern in self.patterns.items():
            if pattern.detection_regex:
                if re.search(pattern.detection_regex, message) or re.search(pattern.detection_regex, raw):
                    matched.append(pattern_id)

        return matched

    def get_pattern(self, pattern_id: str) -> Optional[ErrorPattern]:
        """获取错误模式"""
        return self.patterns.get(pattern_id)

    def get_all_patterns(self) -> List[ErrorPattern]:
        """获取所有模式"""
        return list(self.patterns.values())

    def classify_severity(self, error_type: str) -> ErrorSeverity:
        """分类错误严重性"""
        severity_map = {
            ErrorCategory.SYNTAX_ERROR: ErrorSeverity.BLOCKER,
            ErrorCategory.IMPORT_ERROR: ErrorSeverity.CRITICAL,
            ErrorCategory.MEMORY_ERROR: ErrorSeverity.CRITICAL,
            ErrorCategory.CONCURRENCY_ERROR: ErrorSeverity.CRITICAL,
            ErrorCategory.TYPE_ERROR: ErrorSeverity.MAJOR,
            ErrorCategory.VALUE_ERROR: ErrorSeverity.MAJOR,
            ErrorCategory.ATTRIBUTE_ERROR: ErrorSeverity.MAJOR,
            ErrorCategory.IO_ERROR: ErrorSeverity.MAJOR,
            ErrorCategory.API_ERROR: ErrorSeverity.MAJOR,
            ErrorCategory.CONFIG_ERROR: ErrorSeverity.MAJOR,
            ErrorCategory.TIMEOUT_ERROR: ErrorSeverity.MAJOR,
            ErrorCategory.KEY_ERROR: ErrorSeverity.MINOR,
            ErrorCategory.DATA_ERROR: ErrorSeverity.MINOR,
        }
        return severity_map.get(error_type, ErrorSeverity.UNKNOWN)


# ============================================================
# 代码关联分析器
# ============================================================

class CodeCorrelator:
    """代码关联分析器"""

    def __init__(self, source_root: str = "."):
        self.source_root = source_root
        self.cache: Dict[str, Any] = {}

    def find_source_file(self, error_location: CodeLocation) -> Optional[str]:
        """查找源文件"""
        file_path = error_location.file_path

        # 尝试直接路径
        if os.path.isfile(file_path):
            return file_path

        # 尝试相对于源根目录
        rel_path = os.path.join(self.source_root, file_path)
        if os.path.isfile(rel_path):
            return rel_path

        # 尝试sys.path中的路径
        for path in sys.path:
            alt_path = os.path.join(path, file_path)
            if os.path.isfile(alt_path):
                return alt_path

        return None

    def read_source_code(self, file_path: str) -> Optional[str]:
        """读取源代码"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"[PythonMind] 读取源文件失败: {file_path}, {e}")
            return None

    def parse_ast(self, source_code: str) -> Optional[ast.AST]:
        """解析AST"""
        try:
            return ast.parse(source_code)
        except SyntaxError as e:
            logger.error(f"[PythonMind] AST解析失败: {e}")
            return None

    def get_line_at(self, source_code: str, line_number: int, context_lines: int = 5) -> str:
        """获取指定行的代码上下文"""
        lines = source_code.split('\n')
        start_line = max(0, line_number - context_lines - 1)
        end_line = min(len(lines), line_number + context_lines)

        context = []
        for i in range(start_line, end_line):
            prefix = ">>> " if i == line_number - 1 else "    "
            context.append(f"{prefix}{i + 1}: {lines[i]}")

        return '\n'.join(context)

    def extract_error_context(self, file_path: str, line_number: int,
                             context_lines: int = 10) -> Optional[str]:
        """提取错误上下文"""
        source = self.read_source_code(file_path)
        if source:
            return self.get_line_at(source, line_number, context_lines)
        return None

    def analyze_code_structure(self, source_code: str) -> Dict:
        """分析代码结构"""
        tree = self.parse_ast(source_code)
        if not tree:
            return {}

        structure = {
            "imports": [],
            "functions": [],
            "classes": [],
            "decorators": [],
            "variables": []
        }

        for node in ast.walk(tree):
            # 导入
            if isinstance(node, ast.Import):
                for alias in node.names:
                    structure["imports"].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    structure["imports"].append(f"{module}.{alias.name}")

            # 函数定义
            elif isinstance(node, ast.FunctionDef):
                structure["functions"].append({
                    "name": node.name,
                    "lineno": node.lineno,
                    "args": [arg.arg for arg in node.args.args]
                })

            # 类定义
            elif isinstance(node, ast.ClassDef):
                structure["classes"].append({
                    "name": node.name,
                    "lineno": node.lineno,
                    "bases": [base.attr if isinstance(base, ast.Attribute) else base.id for base in node.bases]
                })

        return structure


# ============================================================
# 根因分析器
# ============================================================

class RootCauseAnalyzer:
    """根本原因分析器"""

    def __init__(self):
        self.cause_patterns: Dict[str, Dict] = {
            "import_error": {
                "common_causes": [
                    "模块未安装 (pip install)",
                    "PYTHONPATH环境变量未设置",
                    "模块名拼写错误",
                    "循环导入问题",
                    "包结构问题 (__init__.py缺失)"
                ],
                "solutions": [
                    "检查并安装缺失的依赖",
                    "设置PYTHONPATH",
                    "修正模块名",
                    "重构导入结构"
                ]
            },
            "type_error": {
                "common_causes": [
                    "函数参数类型不匹配",
                    "对不同类型使用相同操作",
                    "类型注解与实际类型不符"
                ],
                "solutions": [
                    "检查参数类型",
                    "添加类型转换",
                    "使用类型守卫"
                ]
            },
            "key_error": {
                "common_causes": [
                    "字典键不存在",
                    "键名拼写错误",
                    "大小写不匹配",
                    "键类型不匹配 (int vs str)"
                ],
                "solutions": [
                    "使用 dict.get() 提供默认值",
                    "检查键名拼写",
                    "使用 collections.defaultdict"
                ]
            },
            "attribute_error": {
                "common_causes": [
                    "属性/方法名拼写错误",
                    "对象为None",
                    "模块版本不兼容"
                ],
                "solutions": [
                    "检查属性名拼写",
                    "添加None检查",
                    "查看版本文档"
                ]
            },
            "io_error": {
                "common_causes": [
                    "文件路径不存在",
                    "权限不足",
                    "文件被其他程序占用",
                    "磁盘空间不足"
                ],
                "solutions": [
                    "检查文件路径",
                    "修改文件权限",
                    "关闭其他程序",
                    "清理磁盘空间"
                ]
            }
        }

    def analyze(self, error_analysis: ErrorAnalysis,
                historical_logs: Optional[List[LogEntry]] = None) -> Dict:
        """执行根因分析"""
        analysis = {
            "symptoms": self._identify_symptoms(error_analysis),
            "root_causes": [],
            "contributing_factors": [],
            "chain_of_events": [],
            "fix_priority": []
        }

        # 获取错误模式对应的原因
        for pattern_id in error_analysis.matched_patterns:
            if pattern_id in self.cause_patterns:
                pattern_info = self.cause_patterns[pattern_id]
                analysis["root_causes"].extend(pattern_info["common_causes"])
                analysis["fix_priority"].extend(pattern_info["solutions"])

        # 添加错误消息特定分析
        if error_analysis.error_message:
            specific_causes = self._analyze_error_message(error_analysis.error_message)
            analysis["root_causes"].extend(specific_causes)

        # 去重
        analysis["root_causes"] = list(dict.fromkeys(analysis["root_causes"]))
        analysis["fix_priority"] = list(dict.fromkeys(analysis["fix_priority"]))

        return analysis

    def _identify_symptoms(self, error_analysis: ErrorAnalysis) -> List[str]:
        """识别症状"""
        symptoms = []
        error_msg = error_analysis.error_message or ""

        # 基于错误消息识别症状
        if "not found" in error_msg.lower():
            symptoms.append("资源未找到")
        if "permission" in error_msg.lower():
            symptoms.append("权限问题")
        if "timeout" in error_msg.lower():
            symptoms.append("操作超时")
        if "memory" in error_msg.lower():
            symptoms.append("内存问题")
        if "connection" in error_msg.lower():
            symptoms.append("连接问题")

        return symptoms if symptoms else ["一般运行时错误"]

    def _analyze_error_message(self, error_msg: str) -> List[str]:
        """分析错误消息"""
        causes = []

        # 提取文件路径
        file_pattern = r'[/\\]?\w+[/\\]\w+\.py'
        files = re.findall(file_pattern, error_msg)
        if files:
            causes.append(f"问题可能与文件 {files[0]} 相关")

        # 提取模块名
        module_pattern = r"ModuleNotFoundError: No module named '(\w+)'"
        module_match = re.search(module_pattern, error_msg)
        if module_match:
            causes.append(f"模块 '{module_match.group(1)}' 未安装")

        return causes


# ============================================================
# 修复建议生成器
# ============================================================

class FixSuggestionGenerator:
    """修复建议生成器"""

    def __init__(self):
        self.fix_templates: Dict[str, Dict] = {}
        self._init_templates()

    def _init_templates(self):
        """初始化修复模板"""
        self.fix_templates = {
            "import_error": {
                "template": """# 解决方案: 安装缺失的模块
# 运行以下命令安装:

# 对于标准PyPI包:
# pip install {module_name}

# 或使用国内镜像:
# pip install {module_name} -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或安装特定版本:
# pip install {module_name}=={version}""",
                "code_fix": "import {module_name}"
            },
            "syntax_error_indent": {
                "template": """# 解决方案: 检查并修正缩进
# Python使用4个空格或Tab进行缩进
# 确保所有同一代码块的行使用相同的缩进量

# 错误的写法:
# def foo():
# print("hello")  # 缺少缩进

# 正确的写法:
# def foo():
#     print("hello")  # 添加4个空格""",
                "code_fix": None
            },
            "key_error": {
                "template": """# 解决方案1: 使用 dict.get() 提供默认值
value = my_dict.get('key', 'default_value')

# 解决方案2: 使用 defaultdict
from collections import defaultdict
my_dict = defaultdict(lambda: 'default_value', my_dict)

# 解决方案3: 先检查键是否存在
if 'key' in my_dict:
    value = my_dict['key']
else:
    value = 'default_value'""",
                "code_fix": "my_dict.get('key', None)"
            },
            "type_error_concat": {
                "template": """# 解决方案: 类型转换
# 错误: 'string' + 123
# 正确: 'string' + str(123)

# 或者使用f-string:
# f"string {123}\"""",
                "code_fix": "str(value)"
            },
            "attribute_error_none": {
                "template": """# 解决方案: 添加None检查
# 在调用方法前检查对象是否为None

if obj is not None:
    obj.method()
else:
    # 处理None的情况
    pass

# 或使用try-except:
try:
    obj.method()
except AttributeError:
    # 处理错误
    pass""",
                "code_fix": None
            },
            "file_not_found": {
                "template": """# 解决方案: 检查文件路径
import os

file_path = 'your/file/path.txt'

# 检查文件是否存在
if os.path.exists(file_path):
    with open(file_path, 'r') as f:
        content = f.read()
else:
    print(f"文件不存在: {file_path}")

# 或使用绝对路径
abs_path = os.path.abspath(file_path)""",
                "code_fix": "os.path.exists(path)"
            },
            "index_error": {
                "template": """# 解决方案: 添加边界检查
my_list = [1, 2, 3]
index = 5

# 方法1: 使用try-except
try:
    value = my_list[index]
except IndexError:
    value = None

# 方法2: 先检查长度
if 0 <= index < len(my_list):
    value = my_list[index]
else:
    value = None

# 方法3: 使用切片
value = my_list[index] if index < len(my_list) else None""",
                "code_fix": None
            }
        }

    def generate(self, error_analysis: ErrorAnalysis,
                 code_context: Optional[str] = None) -> List[FixSuggestion]:
        """生成修复建议"""
        suggestions = []
        error_msg = error_analysis.error_message or ""

        for pattern_id in error_analysis.matched_patterns:
            if pattern_id in self.fix_templates:
                template = self.fix_templates[pattern_id]

                # 提取模块名（如果是导入错误）
                module_name = ""
                module_match = re.search(r"No module named '(\w+)'", error_msg)
                if module_match:
                    module_name = module_match.group(1)

                suggestion = FixSuggestion(
                    fix_id=f"fix_{pattern_id}_{uuid.uuid4().hex[:8]}",
                    title=self._get_fix_title(pattern_id),
                    description=self._get_fix_description(pattern_id, error_msg),
                    fix_type="code",
                    patch_type=pattern_id,
                    code_snippet=template["template"].format(
                        module_name=module_name,
                        version="latest"
                    ),
                    original_code=code_context or "",
                    fixed_code=template.get("code_fix", "") or "",
                    confidence=0.85,
                    difficulty="easy",
                    risk_level="low",
                    expected_impact="修复后代码应正常工作"
                )
                suggestions.append(suggestion)

        # 如果没有匹配的模板，生成通用建议
        if not suggestions:
            suggestions.append(self._generate_generic_fix(error_analysis))

        return suggestions

    def _get_fix_title(self, pattern_id: str) -> str:
        """获取修复标题"""
        titles = {
            "import_error": "安装缺失的模块",
            "syntax_error": "修正语法错误",
            "type_error": "修复类型不匹配",
            "key_error": "处理缺失的键",
            "attribute_error": "修复属性访问错误",
            "io_error": "处理文件IO问题",
            "index_error": "添加索引边界检查"
        }
        return titles.get(pattern_id, "应用修复")

    def _get_fix_description(self, pattern_id: str, error_msg: str) -> str:
        """获取修复描述"""
        return f"根据错误模式 '{pattern_id}' 提供的标准修复方案。错误信息: {error_msg[:100]}"

    def _generate_generic_fix(self, error_analysis: ErrorAnalysis) -> FixSuggestion:
        """生成通用修复"""
        return FixSuggestion(
            fix_id=f"fix_generic_{uuid.uuid4().hex[:8]}",
            title="查看完整堆栈跟踪信息",
            description="分析错误消息和堆栈跟踪，定位问题根源",
            fix_type="analysis",
            patch_type="generic",
            code_snippet="""# 调试步骤:
# 1. 查看完整的traceback信息
# 2. 定位到错误发生的具体文件和行号
# 3. 检查相关变量的值
# 4. 使用print或logging输出调试信息
# 5. 逐步排除可能的问题原因""",
            original_code="",
            fixed_code="",
            confidence=0.5,
            difficulty="medium",
            risk_level="low",
            expected_impact="帮助定位问题"
        )


# ============================================================
# 代码补丁生成器
# ============================================================

class PatchGenerator:
    """代码补丁生成器"""

    def __init__(self):
        self.patch_strategies: Dict[str, Callable] = {}

    def generate(self, fix_suggestion: FixSuggestion,
                 original_code: str,
                 line_number: int) -> CodePatch:
        """生成代码补丁"""
        patch_id = f"patch_{uuid.uuid4().hex[:12]}"

        # 简单的行替换策略
        lines = original_code.split('\n')
        patched_lines = lines.copy()

        # 在错误行插入修复代码
        if fix_suggestion.fixed_code:
            # 这里只是简单演示，实际会更复杂
            insert_line = max(0, line_number - 1)
            patched_lines.insert(insert_line, fix_suggestion.fixed_code)

        # 生成diff
        diff = self._generate_diff(
            original_code,
            '\n'.join(patched_lines),
            line_number
        )

        return CodePatch(
            patch_id=patch_id,
            file_path="",
            line_start=line_number,
            line_end=line_number,
            original_snippet='\n'.join(lines[max(0, line_number-2):line_number+1]),
            patched_snippet='\n'.join(patched_lines[max(0, line_number-2):line_number+2]),
            diff=diff,
            metadata={
                "fix_id": fix_suggestion.fix_id,
                "confidence": fix_suggestion.confidence
            }
        )

    def _generate_diff(self, original: str, patched: str, context_line: int) -> str:
        """生成diff字符串"""
        original_lines = original.split('\n')
        patched_lines = patched.split('\n')

        diff_lines = [f"--- original", f"+++ patched"]

        for i, (orig, patch) in enumerate(zip(original_lines, patched_lines)):
            if orig != patch:
                diff_lines.append(f"@@ -{i+1} +{i+1} @@")
                diff_lines.append(f"- {orig}")
                diff_lines.append(f"+ {patch}")

        return '\n'.join(diff_lines)


# ============================================================
# 测试用例生成器
# ============================================================

class TestCaseGenerator:
    """测试用例生成器"""

    def __init__(self):
        self.test_templates = {}

    def generate(self, error_analysis: ErrorAnalysis,
                 fix_suggestion: FixSuggestion) -> List[TestCase]:
        """生成测试用例"""
        test_cases = []

        # 基于错误类型生成测试
        for pattern_id in error_analysis.matched_patterns:
            if pattern_id == "import_error":
                test_cases.append(self._generate_import_test(fix_suggestion))
            elif pattern_id == "key_error":
                test_cases.append(self._generate_key_error_test())
            elif pattern_id == "type_error":
                test_cases.append(self._generate_type_test())
            elif pattern_id == "io_error":
                test_cases.append(self._generate_io_test())
            else:
                test_cases.append(self._generate_regression_test())

        # 确保至少有回归测试
        if not test_cases:
            test_cases.append(self._generate_regression_test())

        return test_cases

    def _generate_import_test(self, fix: FixSuggestion) -> TestCase:
        """生成导入测试"""
        module_name = "your_module"
        match = re.search(r"No module named '(\w+)'", fix.description)
        if match:
            module_name = match.group(1)

        return TestCase(
            test_id=f"test_import_{module_name}",
            test_name=f"测试导入 {module_name}",
            test_type="unit",
            code=f'''def test_import_module():
    """测试模块导入"""
    try:
        import {module_name}
        assert {module_name} is not None
    except ImportError as e:
        pytest.fail(f"模块导入失败: {{e}}")''',
            expected_result="模块成功导入，无ImportError"
        )

    def _generate_key_error_test(self) -> TestCase:
        """生成KeyError测试"""
        return TestCase(
            test_id="test_dict_key_access",
            test_name="测试字典键访问",
            test_type="unit",
            code='''def test_dict_key_access():
    """测试字典的安全访问"""
    my_dict = {{"key1": "value1"}}
    
    # 使用get方法安全访问
    value = my_dict.get("key1")
    assert value == "value1"
    
    # 访问不存在的键
    value = my_dict.get("nonexistent", "default")
    assert value == "default"''',
            expected_result="安全访问不存在的键时返回默认值"
        )

    def _generate_type_test(self) -> TestCase:
        """生成类型测试"""
        return TestCase(
            test_id="test_type_conversion",
            test_name="测试类型转换",
            test_type="unit",
            code='''def test_type_conversion():
    """测试类型转换"""
    # 整数转字符串
    num = 123
    result = str(num)
    assert result == "123"
    
    # 字符串转整数
    text = "456"
    result = int(text)
    assert result == 456
    
    # 验证类型
    assert type(result) == int''',
            expected_result="类型转换成功，无TypeError"
        )

    def _generate_io_test(self) -> TestCase:
        """生成IO测试"""
        return TestCase(
            test_id="test_file_operations",
            test_name="测试文件操作",
            test_type="integration",
            code='''import tempfile
import os

def test_file_operations():
    """测试文件操作"""
    # 创建临时文件
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("test content")
        temp_path = f.name
    
    try:
        # 读取文件
        with open(temp_path, 'r') as f:
            content = f.read()
        assert content == "test content"
    finally:
        # 清理
        if os.path.exists(temp_path):
            os.remove(temp_path)''',
            expected_result="文件操作成功，无IOError"
        )

    def _generate_regression_test(self) -> TestCase:
        """生成回归测试"""
        return TestCase(
            test_id="test_regression",
            test_name="回归测试",
            test_type="regression",
            code='''def test_regression():
    """回归测试 - 确保修复后功能正常"""
    # 这里根据具体修复添加测试
    # 例如: 验证之前出错的功能现在正常工作
    pass''',
            expected_result="测试通过"
        )


# ============================================================
# Markdown报告生成器
# ============================================================

class MarkdownReportGenerator:
    """Markdown报告生成器"""

    def __init__(self):
        self.template_sections = [
            "executive_summary",
            "error_details",
            "root_cause_analysis",
            "fix_recommendations",
            "code_patches",
            "test_cases",
            "prevention_strategies"
        ]

    def generate(self, report: AnalysisReport) -> str:
        """生成完整报告"""
        sections = []

        sections.append(self._generate_header(report))
        sections.append(self._generate_executive_summary(report))
        sections.append(self._generate_error_details(report))
        sections.append(self._generate_root_cause(report))
        sections.append(self._generate_fix_recommendations(report))
        sections.append(self._generate_code_patches(report))
        sections.append(self._generate_test_cases(report))
        sections.append(self._generate_prevention(report))
        sections.append(self._generate_footer())

        return '\n\n'.join(sections)

    def _generate_header(self, report: AnalysisReport) -> str:
        """生成报告头部"""
        return f"""# 🐍 Python智能错误分析报告

<div align="center">

**报告ID**: `{report.report_id}`  
**生成时间**: {report.timestamp}  
**分析状态**: ✅ 完成

</div>"""

    def _generate_executive_summary(self, report: AnalysisReport) -> str:
        """生成执行摘要"""
        error = report.error_analysis
        severity_emoji = {
            "BLOCKER": "🔴",
            "CRITICAL": "🟠",
            "MAJOR": "🟡",
            "MINOR": "🔵",
            "TRIVIAL": "⚪",
            "INFO": "ℹ️"
        }

        emoji = severity_emoji.get(error.severity.value.upper(), "ℹ️")

        return f"""## 📋 执行摘要

| 项目 | 值 |
|------|-----|
| **{emoji} 严重性** | {error.severity.value.upper()} |
| **错误类型** | {error.error_type.value} |
| **匹配模式** | {len(error.matched_patterns)} 个 |
| **修复建议** | {len(report.fix_recommendations)} 条 |
| **置信度** | {error.confidence * 100:.1f}% |
| **自动修复** | {"✅ 可用" if report.generated_patches else "❌ 需手动"} |

### 🎯 关键发现

- 错误类型: **{error.error_type.value}**
- 错误消息: {error.error_message[:200] if error.error_message else 'N/A'}
- 错误位置: `{error.error_location.file_path}:{error.error_location.line_number}` (如果可定位)

### 📊 分析统计

- 代码上下文: {"✅ 已提取" if error.code_context else "❌ 不可用"}
- 根因分析: {"✅ 完成" if report.root_cause_analysis.get("root_causes") else "⚠️ 部分完成"}
- 修复建议: **{len(report.fix_recommendations)} 条可用**
"""

    def _generate_error_details(self, report: AnalysisReport) -> str:
        """生成错误详情"""
        error = report.error_analysis

        details = f"""## 🔍 错误详情

### 错误信息
```
{error.error_message or 'N/A'}
```

### 错误类型
- **类别**: {error.error_type.value}
- **严重性**: {error.severity.value}
- **匹配模式数**: {len(error.matched_patterns)}
"""

        if error.error_location:
            details += f"""
### 错误位置
| 属性 | 值 |
|------|-----|
| 文件 | `{error.error_location.file_path}` |
| 行号 | {error.error_location.line_number} |
| 函数 | {error.error_location.function_name} |
| 类名 | {error.error_location.class_name or 'N/A'} |
"""
        if error.code_context:
            details += f"""
### 代码上下文
```python
{error.code_context}
```
"""
        if error.matched_patterns:
            details += f"""
### 匹配的错误模式
"""
            for pattern in error.matched_patterns:
                details += f"- 🔹 `{pattern}`\n"

        return details

    def _generate_root_cause(self, report: AnalysisReport) -> str:
        """生成根因分析"""
        rca = report.root_cause_analysis

        section = """## 🔬 根因分析

### 可能的根本原因

"""
        if rca.get("root_causes"):
            for i, cause in enumerate(rca["root_causes"], 1):
                section += f"{i}. {cause}\n"
        else:
            section += "_暂无根因分析结果_\n"

        if rca.get("symptoms"):
            section += """
### 观察到的症状
"""
            for symptom in rca["symptoms"]:
                section += f"- 🔸 {symptom}\n"

        if rca.get("contributing_factors"):
            section += """
### 影响因素
"""
            for factor in rca["contributing_factors"]:
                section += f"- 🔹 {factor}\n"

        return section

    def _generate_fix_recommendations(self, report: AnalysisReport) -> str:
        """生成修复建议"""
        section = "## 🛠️ 修复建议\n"

        if report.fix_recommendations:
            for i, fix in enumerate(report.fix_recommendations, 1):
                section += f"""
### 建议 {i}: {fix.title}

| 属性 | 值 |
|------|-----|
| **类型** | {fix.fix_type} |
| **置信度** | {fix.confidence * 100:.1f}% |
| **难度** | {fix.difficulty} |
| **风险** | {fix.risk_level} |

**问题描述**: {fix.description}

**建议的修复方案**:
```python
{fix.code_snippet}
```

**预期影响**: {fix.expected_impact}

"""
                if fix.test_cases:
                    section += f"**相关测试**: {', '.join(fix.test_cases)}\n"

                if fix.side_effects:
                    section += f"**可能的副作用**: {', '.join(fix.side_effects)}\n"

                section += "---\n"
        else:
            section += "\n_暂无修复建议_\n"

        return section

    def _generate_code_patches(self, report: AnalysisReport) -> str:
        """生成代码补丁"""
        section = "## 💻 代码补丁\n"

        if report.generated_patches:
            for patch in report.generated_patches:
                section += f"""
### 补丁: `{patch.patch_id}`

**文件**: `{patch.file_path}`  
**行号**: {patch.line_start} - {patch.line_end}

**原始代码**:
```python
{patch.original_snippet}
```

**修复后**:
```python
{patch.patched_snippet}
```

**Diff**:
```diff
{patch.diff}
```

**状态**: {"✅ 已应用" if patch.applied else "⏳ 未应用"} / {"✅ 已验证" if patch.verified else "❌ 未验证"}

---
"""
        else:
            section += "\n_暂无代码补丁_\n"

        return section

    def _generate_test_cases(self, report: AnalysisReport) -> str:
        """生成测试用例"""
        section = "## 🧪 测试用例\n"

        if report.test_cases:
            for test in report.test_cases:
                section += f"""
### {test.test_name}

| 属性 | 值 |
|------|-----|
| **测试ID** | `{test.test_id}` |
| **类型** | {test.test_type} |
| **预期结果** | {test.expected_result} |

**测试代码**:
```python
{test.code}
```

**状态**: {"✅ 通过" if test.is_passing == True else "❌ 失败" if test.is_passing == False else "⏳ 待运行"}

---
"""
        else:
            section += "\n_暂无测试用例_\n"

        return section

    def _generate_prevention(self, report: AnalysisReport) -> str:
        """生成预防策略"""
        section = "## 🛡️ 预防策略\n"

        if report.prevention_strategies:
            for i, strategy in enumerate(report.prevention_strategies, 1):
                section += f"{i}. {strategy}\n"
        else:
            section += """
1. **使用类型注解**: 添加Python类型提示便于静态检查
2. **编写单元测试**: 确保关键函数有充分的测试覆盖
3. **使用lint工具**: 定期运行 pylint、flake8 检查代码
4. **添加异常处理**: 对可能失败的操作添加try-except
5. **日志记录**: 记录关键操作和错误信息便于调试
"""

        section += """
### 📊 推荐的工具

| 工具 | 用途 | 命令 |
|------|------|------|
| pylint | 代码检查 | `pip install pylint` |
| black | 代码格式化 | `pip install black` |
| mypy | 静态类型检查 | `pip install mypy` |
| pytest | 单元测试 | `pip install pytest` |
| loguru | 增强日志 | `pip install loguru` |
"""
        return section

    def _generate_footer(self) -> str:
        """生成页脚"""
        return """
---

<div align="center">

**报告由 Python Mind 自动生成**  
🐍 *从错误中学习，从日志中洞察*

</div>
"""


# ============================================================
# 主引擎 - Python Mind
# ============================================================

class PythonMindEngine:
    """
    Python智能日志分析与自动修复系统 - 主引擎

    核心理念: "从错误中学习，从日志中洞察，自动诊断，智能修复"

    使用流程:
    1. 日志收集 -> 2. 模式识别 -> 3. 代码关联 -> 4. 根因分析 -> 5. 修复生成 -> 6. 报告输出
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

        # 核心组件
        self.log_collector = LogCollector()
        self.pattern_recognizer = ErrorPatternRecognizer()
        self.code_correlator = CodeCorrelator(
            source_root=self.config.get("source_root", ".")
        )
        self.root_cause_analyzer = RootCauseAnalyzer()
        self.fix_generator = FixSuggestionGenerator()
        self.patch_generator = PatchGenerator()
        self.test_generator = TestCaseGenerator()
        self.report_generator = MarkdownReportGenerator()

        # 状态
        self.node_id = self.config.get("node_id", f"pythonmind_{uuid.uuid4().hex[:8]}")
        self.version = "1.0.0"
        self.is_analyzing = False

        # 历史记录
        self.analysis_history: List[ErrorAnalysis] = []
        self.fix_history: List[FixSuggestion] = []
        self.report_history: List[AnalysisReport] = []

        # 统计
        self.stats = {
            "total_analyzed": 0,
            "patterns_matched": defaultdict(int),
            "fixes_generated": 0,
            "fixes_applied": 0,
            "reports_generated": 0
        }

        logger.info(f"[PythonMind] 🐍 Python智能日志分析系统 v{self.version} 初始化完成")
        logger.info(f"[PythonMind] 🆔 节点ID: {self.node_id}")

    def analyze_error(self, error_log: LogEntry,
                     source_code_path: Optional[str] = None) -> ErrorAnalysis:
        """分析错误"""
        logger.info(f"[PythonMind] 🔍 开始分析错误: {error_log.error_type}")

        # 1. 模式识别
        matched_patterns = self.pattern_recognizer.recognize(error_log)

        # 2. 确定错误类别
        error_category = ErrorCategory.UNKNOWN
        if matched_patterns:
            first_pattern = matched_patterns[0]
            if hasattr(ErrorCategory, first_pattern.upper()):
                error_category = ErrorCategory[first_pattern.upper()]

        # 3. 确定严重性
        severity = self.pattern_recognizer.classify_severity(error_category)

        # 4. 代码关联
        code_context = None
        error_location = None

        if error_log.parsed_data.get("traceback_frames"):
            frames = error_log.parsed_data["traceback_frames"]
            if frames:
                first_frame = frames[0]
                error_location = CodeLocation(
                    file_path=first_frame.get("filename", ""),
                    line_number=first_frame.get("lineno", 0),
                    function_name=first_frame.get("function", "")
                )

                if source_code_path:
                    code_context = self.code_correlator.extract_error_context(
                        source_code_path,
                        error_location.line_number
                    )

        # 5. 创建分析结果
        analysis_id = f"analysis_{uuid.uuid4().hex[:12]}"
        analysis = ErrorAnalysis(
            analysis_id=analysis_id,
            timestamp=datetime.datetime.now().isoformat(),
            error_type=error_category,
            severity=severity,
            matched_patterns=matched_patterns,
            error_message=error_log.error_message or error_log.message,
            error_location=error_location,
            code_context=code_context,
            root_cause={},
            fix_suggestions=[],
            confidence=min(0.5 + 0.1 * len(matched_patterns), 0.95),
            status=AnalysisStatus.IN_PROGRESS
        )

        # 更新统计
        self.stats["total_analyzed"] += 1
        for pattern in matched_patterns:
            self.stats["patterns_matched"][pattern] += 1

        # 添加到历史
        self.analysis_history.append(analysis)

        logger.info(f"[PythonMind] ✅ 分析完成: {len(matched_patterns)} 个模式匹配")
        return analysis

    def analyze_and_fix(self, exc_type, exc_value, exc_traceback,
                       source_code_path: Optional[str] = None) -> AnalysisReport:
        """分析错误并生成修复"""
        logger.info("[PythonMind] 🛠️ 开始分析并生成修复...")

        # 1. 收集异常日志
        log_entry = self.log_collector.collect_from_exception(
            exc_type, exc_value, exc_traceback
        )

        # 2. 分析错误
        error_analysis = self.analyze_error(log_entry, source_code_path)

        # 3. 根因分析
        root_cause = self.root_cause_analyzer.analyze(error_analysis)
        error_analysis.root_cause = root_cause

        # 4. 生成修复建议
        fix_suggestions = self.fix_generator.generate(error_analysis, error_analysis.code_context)
        error_analysis.fix_suggestions = fix_suggestions

        # 5. 生成代码补丁
        patches = []
        if error_analysis.code_context and error_analysis.error_location:
            for fix in fix_suggestions:
                if fix.fixed_code:
                    patch = self.patch_generator.generate(
                        fix,
                        error_analysis.code_context,
                        error_analysis.error_location.line_number
                    )
                    patches.append(patch)

        # 6. 生成测试用例
        test_cases = []
        for fix in fix_suggestions:
            tests = self.test_generator.generate(error_analysis, fix)
            test_cases.extend(tests)

        # 7. 生成预防策略
        prevention = self._generate_prevention_strategies(error_analysis)

        # 8. 创建报告
        report_id = f"report_{uuid.uuid4().hex[:12]}"
        report = AnalysisReport(
            report_id=report_id,
            timestamp=datetime.datetime.now().isoformat(),
            error_analysis=error_analysis,
            root_cause_analysis=root_cause,
            fix_recommendations=fix_suggestions,
            generated_patches=patches,
            test_cases=test_cases,
            prevention_strategies=prevention
        )

        # 9. 生成Markdown报告
        report.markdown_content = self.report_generator.generate(report)

        # 更新统计
        self.stats["fixes_generated"] += len(fix_suggestions)
        self.stats["reports_generated"] += 1
        error_analysis.status = AnalysisStatus.COMPLETED

        # 保存到历史
        self.report_history.append(report)
        self.fix_history.extend(fix_suggestions)

        logger.info(f"[PythonMind] ✅ 分析报告生成完成: {report_id}")
        return report

    def _generate_prevention_strategies(self, error_analysis: ErrorAnalysis) -> List[str]:
        """生成预防策略"""
        strategies = []

        # 基于错误类型添加策略
        for pattern in error_analysis.matched_patterns:
            if pattern == "import_error":
                strategies.extend([
                    "使用 requirements.txt 管理依赖",
                    "使用虚拟环境隔离项目依赖",
                    "定期检查并更新依赖版本"
                ])
            elif pattern == "type_error":
                strategies.extend([
                    "添加函数参数类型注解",
                    "使用mypy进行静态类型检查",
                    "添加运行时类型验证"
                ])
            elif pattern == "key_error":
                strategies.extend([
                    "使用 dict.get() 提供默认值",
                    "使用 collections.defaultdict",
                    "在访问前检查键是否存在"
                ])
            elif pattern == "io_error":
                strategies.extend([
                    "使用 os.path.exists() 检查文件",
                    "使用 try-except 包装文件操作",
                    "使用上下文管理器确保资源释放"
                ])

        # 去重并限制数量
        strategies = list(dict.fromkeys(strategies))[:5]
        return strategies

    def get_system_status(self) -> Dict:
        """获取系统状态"""
        return {
            "node_id": self.node_id,
            "version": self.version,
            "stats": dict(self.stats),
            "pattern_library_size": len(self.pattern_recognizer.patterns),
            "fix_templates_size": len(self.fix_generator.fix_templates),
            "analysis_history_size": len(self.analysis_history),
            "report_history_size": len(self.report_history)
        }

    def get_analysis_history(self, limit: int = 10) -> List[ErrorAnalysis]:
        """获取分析历史"""
        return self.analysis_history[-limit:]

    def get_report_history(self, limit: int = 10) -> List[AnalysisReport]:
        """获取报告历史"""
        return self.report_history[-limit:]

    def clear_history(self):
        """清空历史"""
        self.analysis_history.clear()
        self.fix_history.clear()
        self.report_history.clear()
        logger.info("[PythonMind] 🗑️ 历史记录已清空")

    def setup_global_exception_handler(self):
        """设置全局异常处理器"""
        def smart_exception_handler(exc_type, exc_value, exc_traceback):
            # 分析异常
            report = self.analyze_and_fix(exc_type, exc_value, exc_traceback)

            # 打印报告摘要
            print("\n" + "=" * 60)
            print("🐍 Python Mind 错误分析报告")
            print("=" * 60)
            print(f"错误类型: {report.error_analysis.error_type.value}")
            print(f"严重性: {report.error_analysis.severity.value}")
            print(f"匹配模式: {', '.join(report.error_analysis.matched_patterns)}")
            print(f"修复建议: {len(report.fix_recommendations)} 条")
            print(f"报告ID: {report.report_id}")
            print("=" * 60)

            # 调用原始异常处理器
            sys.__excepthook__(exc_type, exc_value, exc_traceback)

        sys.excepthook = smart_exception_handler
        logger.info("[PythonMind] ✅ 全局异常处理器已设置")

    def get_dashboard_data(self) -> Dict:
        """获取仪表盘数据"""
        status = self.get_system_status()

        # 错误类型分布
        pattern_dist = []
        for pattern, count in self.stats["patterns_matched"].items():
            pattern_dist.append({"pattern": pattern, "count": count})

        # 最近分析
        recent_analysis = [
            {
                "id": a.analysis_id,
                "type": a.error_type.value,
                "severity": a.severity.value,
                "timestamp": a.timestamp,
                "patterns_count": len(a.matched_patterns)
            }
            for a in self.analysis_history[-5:]
        ]

        return {
            "system": status,
            "pattern_distribution": pattern_dist,
            "recent_analysis": recent_analysis,
            "fix_success_rate": (
                self.stats["fixes_applied"] / max(1, self.stats["fixes_generated"]) * 100
            )
        }