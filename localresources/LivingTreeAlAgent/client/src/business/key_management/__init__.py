"""
环保全生命周期智能体系统 - 分层密钥管理模块
============================================

核心理念：零交互、全自动、零人工干预的密钥生命周期管理

四层架构：
1. KeyInjector   - 密钥注入层（CI/CD、环境变量、云元数据、外部Vault）
2. KeyProcessor - 密钥处理层（解密、验证、标准化）
3. KeyStorage   - 密钥存储层（内存缓存、加密文件、外部缓存）
4. KeyConsumer  - 密钥使用层（模型API调用、云服务认证、审计追踪）

支持功能：
- 多源容错：至少有一种密钥来源可用
- 自动轮转：密钥过期前自动更新
- 环境感知：根据部署环境自动选择策略
- 完备审计：所有密钥操作均有日志

Author: Hermes Desktop AI Assistant
"""

from .key_manager import KeyManager, get_key_manager
from .key_injector import KeyInjector
from .key_processor import KeyProcessor, ProcessedKey
from .key_storage import KeyStorage, InMemoryCache, EncryptedFileCache
from .key_consumer import KeyConsumer, AuditLogger
from .key_rotator import KeyRotator
from .key_health_monitor import KeyHealthMonitor

__all__ = [
    # 核心管理器
    'KeyManager',
    'get_key_manager',
    # 四层架构
    'KeyInjector',
    'KeyProcessor',
    'ProcessedKey',
    'KeyStorage',
    'InMemoryCache',
    'EncryptedFileCache',
    'KeyConsumer',
    'AuditLogger',
    # 自动化管理
    'KeyRotator',
    'KeyHealthMonitor',
]

# 版本信息
__version__ = '1.0.0'
__author__ = 'Hermes Desktop AI Assistant'