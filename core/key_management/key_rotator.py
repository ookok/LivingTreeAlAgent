"""
密钥自动轮转器 (Key Rotator)
============================

功能：
1. 密钥过期前自动轮转
2. 支持API自动轮转的provider
3. 密钥轮转通知
4. 轮转历史追踪

Author: Hermes Desktop AI Assistant
"""

import os
import time
import logging
import threading
from typing import Dict, Optional, List, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from queue import Queue, Empty
import hashlib

from core.config.unified_config import UnifiedConfig

logger = logging.getLogger(__name__)


class RotationStatus(Enum):
    """轮转状态"""
    PENDING = "pending"           # 待轮转
    IN_PROGRESS = "in_progress"   # 轮转中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    SKIPPED = "skipped"           # 跳过（不支持）


class RotationStrategy(Enum):
    """轮转策略"""
    AUTO = "auto"                 # 自动轮转（API支持）
    MANUAL = "manual"             # 手动轮转（需要人工）
    DISABLED = "disabled"         # 禁用轮转


@dataclass
class RotationConfig:
    """轮转配置"""
    strategy: RotationStrategy = RotationStrategy.AUTO
    threshold_days: int = 30      # 提前多少天开始轮转
    retry_count: int = 3           # 重试次数
    retry_delay_seconds: int = 300 # 重试间隔（5分钟）
    notify_before_days: int = 7   # 提前多少天通知
    auto_rotate: bool = True       # 是否自动轮转

    @classmethod
    def from_config(cls, provider: str = None, strategy: RotationStrategy = RotationStrategy.MANUAL) -> "RotationConfig":
        """从统一配置创建 RotationConfig"""
        config = UnifiedConfig.get_instance()
        key_config = config.get_key_rotation_config()
        return cls(
            strategy=strategy,
            threshold_days=key_config.get("threshold_days", 30),
            retry_delay_seconds=key_config.get("retry_delay", 300),
            notify_before_days=key_config.get("notify_before_days", 7),
            auto_rotate=False if strategy == RotationStrategy.MANUAL else True
        )


@dataclass
class RotationTask:
    """轮转任务"""
    provider: str
    key_id: str
    status: RotationStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    new_key_id: Optional[str] = None
    retries: int = 0


@dataclass
class RotationResult:
    """轮转结果"""
    success: bool
    provider: str
    old_key_id: str
    new_key_id: Optional[str] = None
    message: str = ""
    rotated_at: Optional[datetime] = None


class ProviderRotationSupport:
    """
    各provider的轮转支持情况

    记录哪些provider支持API自动轮转
    """

    # 支持API自动轮转的provider
    API_AUTO_ROTATE = {
        'aws_access': {
            'api': 'aws_iam',
            'method': 'create_access_key',
            'cleanup': 'delete_access_key',
        },
        'azure': {
            'api': 'azure_keyvault',
            'method': 'regenerate_key',
        },
        'gcp': {
            'api': 'gcp_secretmanager',
            'method': 'rotate_version',
        },
    }

    # 只支持手动轮转的provider
    MANUAL_ROTATE_ONLY = {
        'openai',
        'anthropic',
        'google',
        'github',
        'gitlab',
    }

    @classmethod
    def supports_auto_rotate(cls, provider: str) -> bool:
        """检查是否支持自动轮转"""
        provider_lower = provider.lower()
        return (
            provider_lower in cls.API_AUTO_ROTATE or
            provider_lower in cls.MANUAL_ROTATE_ONLY
        )

    @classmethod
    def get_rotation_method(cls, provider: str) -> Optional[Dict]:
        """获取轮转方法信息"""
        return cls.API_AUTO_ROTATE.get(provider.lower())


class NotificationChannel:
    """
    通知渠道基类

    支持：Slack、Email、Webhook、企业微信、钉钉等
    """

    def __init__(self, config: Dict):
        self.config = config

    def send(self, message: Dict) -> bool:
        """发送通知"""
        raise NotImplementedError


class SlackNotification(NotificationChannel):
    """Slack通知"""

    def send(self, message: Dict) -> bool:
        import urllib.request
        import urllib.error

        try:
            webhook_url = self.config.get('webhook_url')
            if not webhook_url:
                return False

            payload = {
                'text': message.get('text', ''),
                'blocks': message.get('blocks', [])
            }

            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )

            config = UnifiedConfig.get_instance()
            timeout = config.get_timeout("quick")
            urllib.request.urlopen(req, timeout=timeout)
            return True

        except Exception as e:
            logger.error(f"Slack通知发送失败: {e}")
            return False


class EmailNotification(NotificationChannel):
    """Email通知"""

    def send(self, message: Dict) -> bool:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        try:
            smtp_host = self.config.get('smtp_host')
            smtp_port = self.config.get('smtp_port', 587)
            smtp_user = self.config.get('smtp_user')
            smtp_password = self.config.get('smtp_password')
            to_addresses = self.config.get('to', [])

            if not all([smtp_host, smtp_user, smtp_password, to_addresses]):
                return False

            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = ', '.join(to_addresses)
            msg['Subject'] = message.get('subject', '密钥轮转通知')

            body = message.get('text', '')
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)

            return True

        except Exception as e:
            logger.error(f"Email通知发送失败: {e}")
            return False


class WebhookNotification(NotificationChannel):
    """通用Webhook通知"""

    def send(self, message: Dict) -> bool:
        import urllib.request
        import urllib.error

        try:
            webhook_url = self.config.get('webhook_url')
            if not webhook_url:
                return False

            # 支持自定义headers
            headers = self.config.get('headers', {})
            headers['Content-Type'] = 'application/json'

            data = json.dumps(message).encode()
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers=headers
            )

            config = UnifiedConfig.get_instance()
            timeout = config.get_timeout("quick")
            urllib.request.urlopen(req, timeout=timeout)
            return True

        except Exception as e:
            logger.error(f"Webhook通知发送失败: {e}")
            return False


class KeyRotator:
    """
    密钥自动轮转器

    功能：
    1. 后台守护进程定期检查密钥过期
    2. 支持API自动轮转的provider自动更新
    3. 不支持的provider发送人工干预通知
    4. 轮转历史完整记录

    使用示例：
        rotator = KeyRotator(key_manager)
        rotator.start()  # 启动后台轮转

        # 或者手动触发轮转
        result = rotator.rotate_key('openai')
    """

    def __init__(self, key_manager, config: Optional[Dict] = None):
        """
        初始化密钥轮转器

        Args:
            key_manager: KeyManager实例
            config: 配置字典
        """
        self.key_manager = key_manager
        self.config = config or {}

        # 轮转配置
        self.rotation_config: Dict[str, RotationConfig] = {}
        self._init_rotation_config()

        # 任务队列
        self._task_queue: Queue = Queue()
        self._rotation_tasks: Dict[str, RotationTask] = {}

        # 后台线程
        self._daemon_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 通知渠道
        self._notification_channels: Dict[str, NotificationChannel] = {}
        self._init_notification_channels()

        # 轮转历史
        self._rotation_history: List[RotationResult] = []

        # 支持的自动轮转API
        self._rotation_apis = self._init_rotation_apis()

        logger.info("KeyRotator 初始化完成")

    def _init_rotation_config(self):
        """初始化轮转配置"""
        default_config = RotationConfig()

        for provider in ProviderRotationSupport.MANUAL_ROTATE_ONLY:
            self.rotation_config[provider] = RotationConfig.from_config(
                provider=provider,
                strategy=RotationStrategy.MANUAL
            )

    def _init_notification_channels(self):
        """初始化通知渠道"""
        # Slack
        slack_config = self.config.get('slack')
        if slack_config:
            self._notification_channels['slack'] = SlackNotification(slack_config)

        # Email
        email_config = self.config.get('email')
        if email_config:
            self._notification_channels['email'] = EmailNotification(email_config)

        # Webhook
        webhook_config = self.config.get('webhook')
        if webhook_config:
            self._notification_channels['webhook'] = WebhookNotification(webhook_config)

    def _init_rotation_apis(self) -> Dict[str, Callable]:
        """初始化轮转API"""
        return {
            'aws_access': self._rotate_aws_key,
            'aws_secret': self._rotate_aws_key,
        }

    def start(self, check_interval: Optional[int] = None):
        """
        启动自动轮转守护进程

        Args:
            check_interval: 检查间隔（秒），默认从配置读取
        """
        if self._daemon_thread and self._daemon_thread.is_alive():
            logger.warning("轮转守护进程已在运行")
            return

        # 从配置获取检查间隔
        if check_interval is None:
            config = UnifiedConfig.get_instance()
            check_interval = config.get_key_rotation_config()["check_interval"]

        self._stop_event.clear()
        self._daemon_thread = threading.Thread(
            target=self._rotation_daemon,
            args=(check_interval,),
            daemon=True,
            name="KeyRotationDaemon"
        )
        self._daemon_thread.start()

        logger.info(f"轮转守护进程已启动，检查间隔: {check_interval}秒")

    def stop(self):
        """停止轮转守护进程"""
        if not self._daemon_thread:
            return

        self._stop_event.set()
        config = UnifiedConfig.get_instance()
        timeout = config.get_timeout("quick")
        self._daemon_thread.join(timeout=timeout)
        self._daemon_thread = None

        logger.info("轮转守护进程已停止")

    def _rotation_daemon(self, check_interval: int):
        """轮转守护进程主循环"""
        while not self._stop_event.is_set():
            try:
                # 检查所有密钥是否需要轮转
                self._check_all_keys()

                # 处理轮转任务队列
                self._process_rotation_queue()

            except Exception as e:
                logger.error(f"轮转守护进程错误: {e}")

            # 等待下次检查
            self._stop_event.wait(check_interval)

    def _check_all_keys(self):
        """检查所有密钥是否需要轮转"""
        try:
            providers = self.key_manager.storage.list_providers()

            for provider in providers:
                processed_key = self.key_manager.storage.get_key(provider)
                if not processed_key:
                    continue

                # 检查是否需要轮转
                if processed_key.needs_rotation(self._get_threshold_days(provider)):
                    logger.info(f"密钥 {provider} 需要轮转")

                    # 创建轮转任务
                    task = RotationTask(
                        provider=provider,
                        key_id=processed_key.id,
                        status=RotationStatus.PENDING,
                        created_at=datetime.now()
                    )

                    self._rotation_tasks[provider] = task
                    self._task_queue.put(task)

                    # 如果即将过期且不支持自动轮转，发送通知
                    if not ProviderRotationSupport.supports_auto_rotate(provider):
                        self._notify_key_expiry(provider, processed_key)

    def _process_rotation_queue(self):
        """处理轮转任务队列"""
        while not self._task_queue.empty():
            try:
                task = self._task_queue.get_nowait()
                self._execute_rotation(task)
            except Empty:
                break
            except Exception as e:
                logger.error(f"处理轮转任务失败: {e}")

    def _execute_rotation(self, task: RotationTask):
        """执行轮转任务"""
        task.status = RotationStatus.IN_PROGRESS
        task.started_at = datetime.now()

        try:
            # 检查是否支持自动轮转
            if ProviderRotationSupport.supports_auto_rotate(task.provider):
                rotation_method = ProviderRotationSupport.get_rotation_method(task.provider)

                if rotation_method:
                    # API自动轮转
                    result = self._call_rotation_api(task.provider, rotation_method)
                else:
                    # 手动轮转
                    result = self._rotate_with_provider_api(task.provider)
            else:
                # 不支持轮转，标记为跳过
                task.status = RotationStatus.SKIPPED
                task.completed_at = datetime.now()
                return

            if result.success:
                task.status = RotationStatus.COMPLETED
                task.new_key_id = result.new_key_id
                logger.info(f"密钥 {task.provider} 轮转成功")
            else:
                task.status = RotationStatus.FAILED
                task.error_message = result.message
                logger.error(f"密钥 {task.provider} 轮转失败: {result.message}")

        except Exception as e:
            task.status = RotationStatus.FAILED
            task.error_message = str(e)
            logger.error(f"密钥 {task.provider} 轮转异常: {e}")

        finally:
            task.completed_at = datetime.now()

    def _call_rotation_api(self, provider: str, method_info: Dict) -> RotationResult:
        """调用provider的轮转API"""
        api_name = method_info.get('api')
        method_name = method_info.get('method')

        if api_name == 'aws_iam':
            return self._rotate_aws_key(provider)

        # 其他API轮转...
        return RotationResult(
            success=False,
            provider=provider,
            old_key_id="",
            message=f"Unknown rotation API: {api_name}"
        )

    def _rotate_aws_key(self, provider: str) -> RotationResult:
        """轮转AWS IAM密钥"""
        try:
            import boto3

            # 获取当前密钥信息
            old_key = self.key_manager.storage.get_key(provider)
            old_key_id = getattr(old_key, 'metadata', {}).get('key_id', '')

            # 创建新密钥
            iam = boto3.client('iam')
            new_key_response = iam.create_access_key()
            new_key = new_key_response['AccessKey']

            # 更新存储
            self.key_manager.storage.update_key(
                provider,
                {
                    'aws_access_key': new_key['AccessKeyId'],
                    'aws_secret_key': new_key['SecretAccessKey'],
                },
                metadata={
                    'key_id': new_key['AccessKeyId'],
                    'created_at': datetime.now().isoformat()
                }
            )

            # 删除旧密钥（可选）
            if old_key_id:
                try:
                    iam.delete_access_key(AccessKeyId=old_key_id)
                except Exception as e:
                    logger.warning(f"删除旧AWS密钥失败: {e}")

            return RotationResult(
                success=True,
                provider=provider,
                old_key_id=old_key_id,
                new_key_id=new_key['AccessKeyId'],
                message="AWS密钥轮转成功",
                rotated_at=datetime.now()
            )

        except Exception as e:
            return RotationResult(
                success=False,
                provider=provider,
                old_key_id="",
                message=f"AWS密钥轮转失败: {str(e)}"
            )

    def _rotate_with_provider_api(self, provider: str) -> RotationResult:
        """
        通过provider的API轮转密钥（通用方法）

        某些provider有API可以生成新密钥
        """
        # TODO: 实现provider特定的轮转逻辑
        return RotationResult(
            success=False,
            provider=provider,
            old_key_id="",
            message=f"Provider {provider} 不支持API自动轮转"
        )

    def schedule_rotation(self, provider: str):
        """调度密钥轮转"""
        task = RotationTask(
            provider=provider,
            key_id="",
            status=RotationStatus.PENDING,
            created_at=datetime.now()
        )

        self._task_queue.put(task)
        logger.info(f"已调度密钥 {provider} 的轮转任务")

    def rotate_key(self, provider: str) -> RotationResult:
        """
        手动触发密钥轮转

        Args:
            provider: 提供商名称

        Returns:
            RotationResult: 轮转结果
        """
        logger.info(f"手动触发密钥 {provider} 的轮转")

        task = RotationTask(
            provider=provider,
            key_id="",
            status=RotationStatus.IN_PROGRESS,
            created_at=datetime.now(),
            started_at=datetime.now()
        )

        self._execute_rotation(task)

        return RotationResult(
            success=task.status == RotationStatus.COMPLETED,
            provider=provider,
            old_key_id=task.key_id,
            new_key_id=task.new_key_id,
            message=task.error_message or "轮转完成",
            rotated_at=task.completed_at
        )

    def _get_threshold_days(self, provider: str) -> int:
        """获取轮转阈值天数"""
        config = self.rotation_config.get(provider)
        if config:
            return config.threshold_days
        return 30  # 默认30天

    def _notify_key_expiry(self, provider: str, processed_key):
        """发送密钥即将过期通知"""
        days_remaining = processed_key.days_until_expiry() or 0

        notification = {
            'type': 'key_expiry_warning',
            'provider': provider,
            'days_remaining': days_remaining,
            'expires_at': processed_key.expires_at.isoformat() if processed_key.expires_at else None,
            'action_required': '请手动更新密钥' if days_remaining < 7 else '计划密钥更新',
            'timestamp': datetime.now().isoformat()
        }

        # 发送到所有通知渠道
        for channel_name, channel in self._notification_channels.items():
            try:
                channel.send(notification)
                logger.info(f"已通过 {channel_name} 发送过期通知")
            except Exception as e:
                logger.error(f"通知渠道 {channel_name} 发送失败: {e}")

    def get_rotation_tasks(self) -> List[RotationTask]:
        """获取当前轮转任务列表"""
        return list(self._rotation_tasks.values())

    def get_rotation_history(self, limit: int = 100) -> List[RotationResult]:
        """获取轮转历史"""
        return self._rotation_history[-limit:]

    def get_status(self) -> Dict[str, Any]:
        """获取轮转器状态"""
        return {
            'daemon_running': self._daemon_thread is not None and self._daemon_thread.is_alive(),
            'pending_tasks': sum(1 for t in self._rotation_tasks.values() if t.status == RotationStatus.PENDING),
            'in_progress_tasks': sum(1 for t in self._rotation_tasks.values() if t.status == RotationStatus.IN_PROGRESS),
            'failed_tasks': sum(1 for t in self._rotation_tasks.values() if t.status == RotationStatus.FAILED),
            'notification_channels': list(self._notification_channels.keys()),
            'rotation_configured': list(self.rotation_config.keys())
        }


import json  # For Slack notification