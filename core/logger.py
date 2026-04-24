# -*- coding: utf-8 -*-
"""
LivingTree AI 统一日志系统
=========================

提供集中式日志管理，支持:
- 多级别日志 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
- 多输出目标 (控制台/文件/滚动文件)
- 多格式输出 (普通/JSON)
- 模块级别独立控制
- 环境变量配置

使用方式:
    from core.logger import logger

    logger.info("信息日志")
    logger.debug("调试日志")
    logger.warning("警告日志")
    logger.error("错误日志")
    logger.critical("严重错误")

或者使用模块级日志器:
    from core.logger import get_logger

    log = get_logger(__name__)
    log.info("模块日志")
"""

import os
import sys
import json
import logging
import logging.handlers
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

# ============================================================================
# 配置常量
# ============================================================================

DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_LEVEL = logging.INFO

# 日志目录
LOG_DIR = Path.home() / ".livingtree" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 文件路径
LOG_FILE = LOG_DIR / "livingtree.log"
ERROR_LOG_FILE = LOG_DIR / "error.log"
DEBUG_LOG_FILE = LOG_DIR / "debug.log"

# ============================================================================
# 日志级别映射
# ============================================================================

LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# ============================================================================
# 自定义格式化器
# ============================================================================

class ColoredFormatter(logging.Formatter):
    """带颜色的控制台格式化器"""

    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',     # 青色
        'INFO': '\033[32m',      # 绿色
        'WARNING': '\033[33m',   # 黄色
        'ERROR': '\033[31m',     # 红色
        'CRITICAL': '\033[35m', # 紫色
        'RESET': '\033[0m',
    }

    def format(self, record):
        # 添加颜色
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        return super().format(record)


class JSONFormatter(logging.Formatter):
    """JSON格式日志"""

    def format(self, record):
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # 添加额外字段
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, 'extra'):
            log_data.update(record.extra)

        return json.dumps(log_data, ensure_ascii=False)


# ============================================================================
# 日志处理器管理
# ============================================================================

class LogHandlerManager:
    """日志处理器管理器"""

    def __init__(self):
        self.handlers: Dict[str, logging.Handler] = {}
        self._configure_from_env()

    def _configure_from_env(self):
        """从环境变量配置"""
        # 日志级别
        level = os.getenv("LIVINGTREE_LOG_LEVEL", "INFO")
        self.default_level = LOG_LEVELS.get(level.upper(), DEFAULT_LEVEL)

        # 是否启用文件输出
        self.enable_file = os.getenv("LIVINGTREE_LOG_FILE", "true").lower() == "true"
        self.enable_error_file = os.getenv("LIVINGTREE_LOG_ERROR_FILE", "true").lower() == "true"

        # 是否启用JSON格式
        self.json_format = os.getenv("LIVINGTREE_LOG_JSON", "false").lower() == "true"

        # 是否启用颜色输出
        self.colored = os.getenv("LIVINGTREE_LOG_COLOR", "true").lower() == "true"

    def get_console_handler(self) -> logging.Handler:
        """获取控制台处理器"""
        if "console" not in self.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(self.default_level)

            if self.json_format:
                formatter = JSONFormatter()
            elif self.colored and sys.stdout.isatty():
                formatter = ColoredFormatter(DEFAULT_FORMAT, DEFAULT_DATE_FORMAT)
            else:
                formatter = logging.Formatter(DEFAULT_FORMAT, DEFAULT_DATE_FORMAT)

            handler.setFormatter(formatter)
            self.handlers["console"] = handler

        return self.handlers["console"]

    def get_file_handler(self, filename: Path, level: int = logging.INFO) -> logging.Handler:
        """获取文件处理器"""
        key = f"file_{filename.name}"

        if key not in self.handlers:
            handler = logging.handlers.RotatingFileHandler(
                filename,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding="utf-8"
            )
            handler.setLevel(level)

            if self.json_format:
                formatter = JSONFormatter()
            else:
                formatter = logging.Formatter(DEFAULT_FORMAT, DEFAULT_DATE_FORMAT)

            handler.setFormatter(formatter)
            self.handlers[key] = handler

        return self.handlers[key]

    def get_error_file_handler(self) -> logging.Handler:
        """获取错误日志文件处理器"""
        if "error_file" not in self.handlers:
            handler = logging.FileHandler(ERROR_LOG_FILE, encoding="utf-8")
            handler.setLevel(logging.ERROR)
            formatter = logging.Formatter(DEFAULT_FORMAT, DEFAULT_DATE_FORMAT)
            handler.setFormatter(formatter)
            self.handlers["error_file"] = handler

        return self.handlers["error_file"]

    def cleanup_handlers(self):
        """清理所有处理器"""
        for handler in self.handlers.values():
            handler.close()
        self.handlers.clear()


# ============================================================================
# 全局日志管理器
# ============================================================================

_manager = LogHandlerManager()


def _setup_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """设置日志器"""
    logger = logging.getLogger(name)

    if level is None:
        # 检查环境变量或模块特定配置
        module_level = os.getenv(f"LIVINGTREE_LOG_{name.upper().replace('.', '_')}_LEVEL")
        if module_level:
            level = LOG_LEVELS.get(module_level.upper(), _manager.default_level)
        else:
            level = _manager.default_level

    logger.setLevel(level)

    # 添加处理器
    if not logger.handlers:
        # 控制台
        logger.addHandler(_manager.get_console_handler())

        # 文件 (仅对主logger和核心模块启用)
        if _manager.enable_file and (name == "livingtree" or name.startswith("core.")):
            logger.addHandler(_manager.get_file_handler(LOG_FILE))

        # 错误日志文件
        if _manager.enable_error_file and name.startswith("core."):
            logger.addHandler(_manager.get_error_file_handler())

    return logger


# ============================================================================
# 主日志器
# ============================================================================

# 主日志器
logger = _setup_logger("livingtree")

# 便捷函数
def get_logger(name: str) -> logging.Logger:
    """获取模块日志器"""
    return _setup_logger(name)


def set_level(level: str):
    """设置全局日志级别"""
    numeric_level = LOG_LEVELS.get(level.upper(), DEFAULT_LEVEL)
    logging.getLogger("livingtree").setLevel(numeric_level)
    _manager.default_level = numeric_level


def add_file_handler(filename: Optional[Path] = None, level: int = logging.INFO):
    """添加额外的文件处理器"""
    if filename is None:
        filename = LOG_DIR / f"custom_{datetime.now().strftime('%Y%m%d')}.log"

    root_logger = logging.getLogger("livingtree")
    root_logger.addHandler(_manager.get_file_handler(filename, level))


# ============================================================================
# 便捷日志方法
# ============================================================================

def debug(message: str, *args, **kwargs):
    """调试日志"""
    logger.debug(message, *args, **kwargs)


def info(message: str, *args, **kwargs):
    """信息日志"""
    logger.info(message, *args, **kwargs)


def warning(message: str, *args, **kwargs):
    """警告日志"""
    logger.warning(message, *args, **kwargs)


def error(message: str, *args, **kwargs):
    """错误日志"""
    logger.error(message, *args, **kwargs)


def critical(message: str, *args, **kwargs):
    """严重错误日志"""
    logger.critical(message, *args, **kwargs)


def exception(message: str, *args, **kwargs):
    """异常日志 (自动包含堆栈)"""
    logger.exception(message, *args, **kwargs)


# ============================================================================
# 替换print的便捷函数
# ============================================================================

def print_info(message: str):
    """信息打印 (替换print)"""
    info(message)


def print_debug(message: str):
    """调试打印"""
    debug(message)


def print_warn(message: str):
    """警告打印"""
    warning(message)


def print_error(message: str):
    """错误打印"""
    error(message)


# ============================================================================
# 模块级print替换
# ============================================================================

class PrintReplacer:
    """
    Print语句替换工具

    使用方式:
        from core.logger import PrintReplacer
        PrintReplacer.replace_in_module("core.agent")

        # 或者替换当前模块
        PrintReplacer.replace_builtins(globals())
    """

    # Python内置的print函数
    _builtin_print = print

    @classmethod
    def replace_builtins(cls, namespace: dict):
        """替换命名空间中的print"""
        namespace['print'] = cls._make_logger_print(namespace.get('__name__', '__main__'))

    @classmethod
    def _make_logger_print(cls, module_name: str) -> callable:
        """创建日志打印函数"""
        def log_print(*args, **kwargs):
            message = ' '.join(str(arg) for arg in args)
            logger = get_logger(module_name)
            logger.info(message)
        return log_print

    @classmethod
    def replace_in_module(cls, module_path: str):
        """
        替换指定模块中的print

        注意: 这个方法需要在模块加载前调用
        推荐在应用启动时调用
        """
        try:
            import importlib
            module = importlib.import_module(module_path)

            # 替换模块的print
            module_globals = vars(module)
            if 'print' in module_globals:
                module_globals['print'] = cls._make_logger_print(module_path)

        except ImportError:
            pass


# ============================================================================
# 自动配置 (可选)
# ============================================================================

def auto_setup():
    """
    自动设置日志系统

    在应用入口点调用:
        from core.logger import auto_setup
        auto_setup()
    """
    # 设置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(_manager.default_level)

    # 移除默认处理器
    for handler in root_logger.handlers[:]:
        if not isinstance(handler, logging.handlers.RotatingFileHandler):
            root_logger.removeHandler(handler)

    # 添加我们的处理器
    root_logger.addHandler(_manager.get_console_handler())

    if _manager.enable_file:
        root_logger.addHandler(_manager.get_file_handler(LOG_FILE))

    info("LivingTree AI 日志系统初始化完成")


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    # 主日志器
    'logger',

    # 获取日志器
    'get_logger',

    # 日志级别设置
    'set_level',

    # 便捷函数
    'debug',
    'info',
    'warning',
    'error',
    'critical',
    'exception',

    # print替换
    'print_info',
    'print_debug',
    'print_warn',
    'print_error',

    # Print替换工具
    'PrintReplacer',

    # 自动配置
    'auto_setup',

    # 常量
    'LOG_DIR',
    'LOG_FILE',
    'ERROR_LOG_FILE',
]
