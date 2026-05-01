"""
统一日志系统
"""
import os
import sys
import logging
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler


def setup_logger(name: str = 'livingtree', log_dir: str = 'data/logs'):
    """
    配置日志系统
    
    Args:
        name: 日志名称
        log_dir: 日志目录
        
    Returns:
        logger: 配置好的 logger
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 文件处理器
    file_handler = RotatingFileHandler(
        log_path / f'{name}.log',
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str = 'livingtree'):
    """获取 logger"""
    return setup_logger(name)


# 初始化默认 logger
logger = setup_logger('livingtree')

# 导出为公共函数
__all__ = ['setup_logger', 'get_logger', 'logger']
