"""
密钥管理器总成 (Key Manager)
============================

协调所有密钥管理组件的统一接口

组件：
- KeyInjector   - 密钥注入层
- KeyProcessor  - 密钥处理层
- KeyStorage    - 密钥存储层
- KeyConsumer   - 密钥使用层
- KeyRotator    - 自动轮转
- KeyHealthMonitor - 健康监控

Author: Hermes Desktop AI Assistant
"""

import os
import logging
import threading
from typing import Dict, Optional, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)


# 全局单例
_key_manager_instance: Optional['KeyManager'] = None
_key_manager_lock = threading.Lock()


class KeyManager:
    """
    密钥管理器 - 统一协调所有组件

    这是密钥管理系统的总入口，协调：
    1. KeyInjector - 密钥自动注入
    2. KeyProcessor - 密钥处理验证
    3. KeyStorage - 密钥安全存储
    4. KeyConsumer - 密钥使用审计
    5. KeyRotator - 自动轮转
    6. KeyHealthMonitor - 健康监控

    使用示例：
        # 获取单例
        manager = get_key_manager()

        # 初始化（注入所有密钥）
        manager.initialize()

        # 获取密钥
        api_key = manager.get_key('openai')

        # 获取健康报告
        health = manager.get_health_report()
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化密钥管理器

        Args:
            config: 配置字典
                - inject_config: KeyInjector配置
                - storage_config: KeyStorage配置
                - rotation_config: KeyRotator配置
                - monitor_config: KeyHealthMonitor配置
                - auto_init: 是否自动初始化（默认True）
        """
        self.config = config or {}
        self._initialized = False
        self._lock = threading.RLock()

        # 各层组件（延迟初始化）
        self._injector = None
        self._processor = None
        self._storage = None
        self._consumer = None
        self._rotator = None
        self._health_monitor = None

        # 组件引用（用于Consumer访问Storage）
        self.injector = None      # KeyInjector
        self.processor = None      # KeyProcessor
        self.storage = None        # KeyStorage
        self.consumer = None       # KeyConsumer
        self.rotator = None        # KeyRotator
        self.health_monitor = None # KeyHealthMonitor

        logger.info("KeyManager 实例创建完成")

        # 自动初始化
        if self.config.get('auto_init', True):
            self.initialize()

    def initialize(self) -> bool:
        """
        初始化密钥管理系统

        执行完整的初始化流程：
        1. 注入密钥
        2. 处理密钥
        3. 存储密钥
        4. 启动轮转守护进程（可选）
        5. 启动健康监控（可选）

        Returns:
            是否初始化成功
        """
        with self._lock:
            if self._initialized:
                logger.warning("KeyManager 已经初始化")
                return True

            try:
                logger.info("开始初始化密钥管理系统...")

                # 1. 初始化并执行密钥注入
                from .key_injector import KeyInjector
                self._injector = KeyInjector(
                    config=self.config.get('inject_config')
                )
                raw_keys = self._injector.inject_all_keys()
                logger.info(f"密钥注入完成，获取 {len(raw_keys)} 个密钥")

                if not raw_keys:
                    logger.warning("未获取到任何密钥")

                # 2. 初始化处理器并处理密钥
                from .key_processor import KeyProcessor
                self._processor = KeyProcessor(
                    master_key=self.config.get('master_key'),
                    config=self.config.get('processor_config')
                )
                processed_keys = self._processor.process_keys(raw_keys)
                logger.info(f"密钥处理完成，{len(processed_keys)} 个密钥")

                # 3. 初始化存储并持久化
                from .key_storage import KeyStorage
                self._storage = KeyStorage(
                    config=self.config.get('storage_config')
                )
                self._storage.store_keys(processed_keys)
                logger.info("密钥存储完成")

                # 4. 初始化消费者
                from .key_consumer import KeyConsumer, AuditLogger
                audit_logger = AuditLogger(
                    config=self.config.get('audit_config')
                )
                self._consumer = KeyConsumer(
                    storage=self._storage,
                    audit_logger=audit_logger,
                    config=self.config.get('consumer_config')
                )
                logger.info("审计日志初始化完成")

                # 5. 初始化轮转器
                self._rotator = None
                if self.config.get('enable_rotation', False):
                    from .key_rotator import KeyRotator
                    self._rotator = KeyRotator(
                        key_manager=self,
                        config=self.config.get('rotation_config')
                    )
                    # 将rotator注入consumer
                    self._consumer.rotator = self._rotator
                    # 启动轮转守护进程
                    check_interval = self.config.get('rotation_check_interval', 3600)
                    self._rotator.start(check_interval=check_interval)
                    logger.info(f"密钥轮转守护进程已启动（间隔 {check_interval}秒）")

                # 6. 初始化健康监控
                self._health_monitor = None
                if self.config.get('enable_health_monitor', True):
                    from .key_health_monitor import KeyHealthMonitor
                    self._health_monitor = KeyHealthMonitor(
                        key_manager=self,
                        config=self.config.get('monitor_config')
                    )
                    # 执行首次健康检查
                    self._health_monitor.check_all_keys()
                    # 启动后台监控
                    monitor_interval = self.config.get('monitor_interval', 3600)
                    self._health_monitor.start(interval=monitor_interval)
                    logger.info(f"健康监控已启动（间隔 {monitor_interval}秒）")

                # 更新组件引用
                self.injector = self._injector
                self.processor = self._processor
                self.storage = self._storage
                self.consumer = self._consumer
                self.rotator = self._rotator
                self.health_monitor = self._health_monitor

                self._initialized = True
                logger.info("密钥管理系统初始化完成！")

                return True

            except Exception as e:
                logger.error(f"密钥管理系统初始化失败: {e}")
                import traceback
                traceback.print_exc()
                return False

    def get_key(self, provider: str) -> str:
        """
        获取指定提供商的密钥

        这是最常用的API

        Args:
            provider: 提供商名称（如 'openai', 'anthropic' 等）

        Returns:
            密钥值字符串

        Raises:
            KeyError: 密钥不存在
            ValueError: 密钥无效
        """
        if not self._initialized:
            self.initialize()

        return self.consumer.get_key_for_provider(provider)

    def get_all_keys(self) -> Dict[str, str]:
        """
        获取所有可用密钥

        Returns:
            provider -> key_value 的字典
        """
        if not self._initialized:
            self.initialize()

        return self.consumer.get_all_keys()

    def get_key_info(self, provider: str) -> Optional[Dict]:
        """
        获取密钥信息（不含值）

        Args:
            provider: 提供商名称

        Returns:
            密钥信息字典
        """
        if not self._initialized:
            self.initialize()

        return self.consumer.get_key_info(provider)

    def list_providers(self) -> List[str]:
        """列出所有密钥provider"""
        if not self._initialized:
            self.initialize()

        return self.storage.list_providers()

    def add_key(self, provider: str, key_value: str, metadata: Optional[Dict] = None) -> bool:
        """
        添加新密钥

        Args:
            provider: 提供商名称
            key_value: 密钥值
            metadata: 额外元数据

        Returns:
            是否添加成功
        """
        if not self._initialized:
            self.initialize()

        try:
            processed = self.processor.process_keys({provider: key_value})
            if provider in processed:
                processed[provider].metadata.update(metadata or {})
                self.storage.store_keys({provider: processed[provider]})
                return True
        except Exception as e:
            logger.error(f"添加密钥 {provider} 失败: {e}")

        return False

    def update_key(self, provider: str, key_value: str, metadata: Optional[Dict] = None) -> bool:
        """
        更新现有密钥

        Args:
            provider: 提供商名称
            key_value: 新的密钥值
            metadata: 新的元数据

        Returns:
            是否更新成功
        """
        return self.add_key(provider, key_value, metadata)

    def delete_key(self, provider: str) -> bool:
        """
        删除密钥

        Args:
            provider: 提供商名称

        Returns:
            是否删除成功
        """
        if not self._initialized:
            self.initialize()

        return self.storage.delete_key(provider)

    def rotate_key(self, provider: str) -> bool:
        """
        手动触发密钥轮转

        Args:
            provider: 提供商名称

        Returns:
            是否轮转成功
        """
        if not self._initialized:
            self.initialize()

        if not self.rotator:
            logger.warning("轮转器未启用")
            return False

        result = self.rotator.rotate_key(provider)
        return result.success

    def get_health_report(self) -> Dict[str, Any]:
        """
        获取健康报告

        Returns:
            健康报告字典
        """
        if not self._initialized:
            self.initialize()

        if not self.health_monitor:
            return {'status': 'disabled'}

        return self.health_monitor.check_all_keys().to_dict()

    def get_health_summary(self) -> Dict[str, Any]:
        """
        获取健康摘要

        Returns:
            健康摘要
        """
        if not self._initialized:
            self.initialize()

        if not self.health_monitor:
            return {'status': 'disabled'}

        return self.health_monitor.get_health_summary()

    def get_access_stats(self) -> Dict[str, Any]:
        """
        获取访问统计

        Returns:
            访问统计字典
        """
        if not self._initialized:
            self.initialize()

        return self.consumer.get_access_stats()

    def get_injection_history(self) -> List:
        """获取注入历史"""
        if self.injector:
            return self.injector.get_injection_history()
        return []

    def get_rotation_status(self) -> Dict[str, Any]:
        """获取轮转状态"""
        if self.rotator:
            return self.rotator.get_status()
        return {'status': 'disabled'}

    def export_keys(self, format: str = 'json') -> str:
        """
        导出密钥信息（不含值）

        Args:
            format: 导出格式（json/markdown/html）

        Returns:
            导出的报告内容
        """
        if not self._initialized:
            self.initialize()

        if format == 'json':
            import json
            providers_info = self.consumer.list_providers_with_info()
            return json.dumps(providers_info, ensure_ascii=False, indent=2)

        elif format == 'markdown':
            lines = ["# 密钥清单", ""]
            lines.append("| 提供商 | 类型 | 有效 | 过期天数 | 轮转 | 评分 |")
            lines.append("|--------|------|------|----------|------|------|")

            for info in self.consumer.list_providers_with_info():
                lines.append(
                    f"| {info['provider']} | {info['key_type']} | "
                    f"{'是' if info['is_valid'] else '否'} | "
                    f"{info.get('days_until_expiry', 'N/A')} | "
                    f"{'是' if info['needs_rotation'] else '否'} | "
                    f"{info.get('score', 'N/A')} |"
                )

            return "\n".join(lines)

        return "{}"

    def shutdown(self):
        """
        优雅关闭密钥管理系统

        停止所有后台守护进程
        """
        logger.info("正在关闭密钥管理系统...")

        if self.health_monitor:
            self.health_monitor.stop()

        if self.rotator:
            self.rotator.stop()

        logger.info("密钥管理系统已关闭")

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized

    def __enter__(self):
        """上下文管理器入口"""
        if not self._initialized:
            self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.shutdown()
        return False


def get_key_manager(config: Optional[Dict] = None) -> KeyManager:
    """
    获取KeyManager单例

    Args:
        config: 可选配置字典。首次调用时生效，后续调用返回已创建的实例。

    Returns:
        KeyManager实例

    使用示例：
        manager = get_key_manager()
        api_key = manager.get_key('openai')
    """
    global _key_manager_instance

    with _key_manager_lock:
        if _key_manager_instance is None:
            _key_manager_instance = KeyManager(config=config)
        return _key_manager_instance


def reset_key_manager():
    """
    重置KeyManager单例

    用于测试或重新初始化
    """
    global _key_manager_instance

    with _key_manager_lock:
        if _key_manager_instance:
            _key_manager_instance.shutdown()
        _key_manager_instance = None

    logger.info("KeyManager 单例已重置")


class KeyManagerContext:
    """
    KeyManager上下文管理器

    提供临时的KeyManager配置

    使用示例：
        with KeyManagerContext(config={'auto_init': False}) as manager:
            manager.initialize()
    """

    def __init__(self, config: Dict):
        self.config = config
        self._previous_manager = None

    def __enter__(self) -> KeyManager:
        global _key_manager_instance

        self._previous_manager = _key_manager_instance

        # 创建新的KeyManager
        _key_manager_instance = KeyManager(config=self.config)

        return _key_manager_instance

    def __exit__(self, exc_type, exc_val, exc_tb):
        global _key_manager_instance

        # 恢复之前的KeyManager
        if _key_manager_instance:
            _key_manager_instance.shutdown()

        _key_manager_instance = self._previous_manager

        return False