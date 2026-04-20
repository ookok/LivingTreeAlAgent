"""
错误日志配置
============
配置结构化错误日志，支持分类写入、自动轮转、错误诊断
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler


# 日志目录
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 日志文件路径
LOG_FILE_MAIN = LOG_DIR / "main.log"
LOG_FILE_ERROR = LOG_DIR / "error.log"
LOG_FILE_WARNING = LOG_DIR / "warning.log"
LOG_FILE_DEBUG = LOG_DIR / "debug.log"
LOG_FILE_UI = LOG_DIR / "ui.log"
LOG_FILE_NETWORK = LOG_DIR / "network.log"

# 最大日志文件数
MAX_LOG_FILES = 5

# 单个日志文件最大大小 (10MB)
MAX_LOG_SIZE = 10 * 1024 * 1024


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""
    
    COLORS = {
        logging.DEBUG: "\033[36m",      # 青色
        logging.INFO: "\033[32m",       # 绿色
        logging.WARNING: "\033[33m",    # 黄色
        logging.ERROR: "\033[31m",      # 红色
        logging.CRITICAL: "\033[35m",   # 紫色
    }
    RESET = "\033[0m"
    
    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_error_logger():
    """
    配置错误日志系统
    
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    # 创建主日志记录器
    logger = logging.getLogger("hermes")
    logger.setLevel(logging.DEBUG)
    
    # 清除已有的处理器
    logger.handlers.clear()
    
    # 日志格式
    detailed_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # ── 控制台输出 ──────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ColoredFormatter(simple_format))
    logger.addHandler(console_handler)
    
    # ── 主日志文件 (所有级别) ───────────────────────────
    main_handler = RotatingFileHandler(
        LOG_FILE_MAIN,
        maxBytes=MAX_LOG_SIZE,
        backupCount=MAX_LOG_FILES,
        encoding='utf-8'
    )
    main_handler.setLevel(logging.DEBUG)
    main_handler.setFormatter(detailed_format)
    logger.addHandler(main_handler)
    
    # ── 错误日志文件 (仅 ERROR 和 CRITICAL) ─────────────
    error_handler = RotatingFileHandler(
        LOG_FILE_ERROR,
        maxBytes=MAX_LOG_SIZE,
        backupCount=MAX_LOG_FILES,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_format)
    logger.addHandler(error_handler)
    
    # ── 警告日志文件 (WARNING 及以上) ───────────────────
    warning_handler = RotatingFileHandler(
        LOG_FILE_WARNING,
        maxBytes=MAX_LOG_SIZE,
        backupCount=MAX_LOG_FILES,
        encoding='utf-8'
    )
    warning_handler.setLevel(logging.WARNING)
    warning_handler.setFormatter(detailed_format)
    logger.addHandler(warning_handler)
    
    # ── UI 日志文件 ─────────────────────────────────────
    ui_handler = RotatingFileHandler(
        LOG_FILE_UI,
        maxBytes=MAX_LOG_SIZE,
        backupCount=MAX_LOG_FILES,
        encoding='utf-8'
    )
    ui_handler.setLevel(logging.DEBUG)
    ui_handler.setFormatter(detailed_format)
    ui_handler.addFilter(lambda record: 'ui' in record.name.lower() or 'presentation' in record.name.lower())
    logger.addHandler(ui_handler)
    
    # ── 网络日志文件 ────────────────────────────────────
    network_handler = RotatingFileHandler(
        LOG_FILE_NETWORK,
        maxBytes=MAX_LOG_SIZE,
        backupCount=MAX_LOG_FILES,
        encoding='utf-8'
    )
    network_handler.setLevel(logging.DEBUG)
    network_handler.setFormatter(detailed_format)
    network_handler.addFilter(lambda record: any(kw in record.name.lower() for kw in ['network', 'http', 'ollama', 'api']))
    logger.addHandler(network_handler)
    
    # ── 每日轮转的调试日志 ──────────────────────────────
    debug_handler = TimedRotatingFileHandler(
        LOG_FILE_DEBUG,
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(detailed_format)
    logger.addHandler(debug_handler)
    
    return logger


def get_logger(name: str = None) -> logging.Logger:
    """
    获取命名日志记录器
    
    Args:
        name: 日志记录器名称，会自动添加 hermes 前缀
    
    Returns:
        logging.Logger: 日志记录器
    """
    full_name = f"hermes.{name}" if name else "hermes"
    return logging.getLogger(full_name)


def log_startup(logger: logging.Logger):
    """记录系统启动日志"""
    logger.info("=" * 60)
    logger.info("  Hermes Desktop 启动")
    logger.info("=" * 60)
    logger.info(f"Python 版本: {sys.version}")
    logger.info(f"日志目录: {LOG_DIR}")
    logger.info(f"系统平台: {sys.platform}")
    logger.info("-" * 60)


def log_shutdown(logger: logging.Logger):
    """记录系统关闭日志"""
    logger.info("-" * 60)
    logger.info("  Hermes Desktop 关闭")
    logger.info("=" * 60)


def get_recent_errors(count: int = 10) -> list:
    """
    获取最近的错误日志
    
    Args:
        count: 获取的错误日志条数
    
    Returns:
        list: 错误日志条目列表
    """
    if not LOG_FILE_ERROR.exists():
        return []
    
    errors = []
    try:
        with open(LOG_FILE_ERROR, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # 取最后 count 条
            for line in lines[-count:]:
                line = line.strip()
                if line:
                    errors.append(line)
    except Exception:
        pass
    
    return errors


def get_log_summary() -> dict:
    """
    获取日志统计摘要
    
    Returns:
        dict: 日志统计信息
    """
    summary = {
        'log_dir': str(LOG_DIR),
        'log_files': [],
        'total_size': 0,
        'error_count': 0,
        'warning_count': 0,
    }
    
    if not LOG_DIR.exists():
        return summary
    
    for log_file in LOG_DIR.glob("*.log"):
        size = log_file.stat().st_size
        summary['log_files'].append({
            'name': log_file.name,
            'size': size,
            'size_mb': round(size / 1024 / 1024, 2)
        })
        summary['total_size'] += size
    
    # 统计错误和警告数量
    if LOG_FILE_ERROR.exists():
        try:
            with open(LOG_FILE_ERROR, 'r', encoding='utf-8') as f:
                summary['error_count'] = len(f.readlines())
        except Exception:
            pass
    
    if LOG_FILE_WARNING.exists():
        try:
            with open(LOG_FILE_WARNING, 'r', encoding='utf-8') as f:
                summary['warning_count'] = len(f.readlines())
        except Exception:
            pass
    
    return summary


__all__ = [
    'setup_error_logger',
    'get_logger',
    'log_startup',
    'log_shutdown',
    'get_recent_errors',
    'get_log_summary',
    'LOG_DIR',
    'LOG_FILE_MAIN',
    'LOG_FILE_ERROR',
    'LOG_FILE_WARNING',
    'LOG_FILE_DEBUG',
    'LOG_FILE_UI',
    'LOG_FILE_NETWORK',
]
