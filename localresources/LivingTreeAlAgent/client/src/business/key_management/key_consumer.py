"""
第4层：密钥消费者与审计日志 (Key Consumer Layer)
================================================

功能：
1. 提供统一的密钥访问接口
2. 记录所有密钥操作的审计日志
3. 密钥使用追踪
4. 访问控制

Author: Hermes Desktop AI Assistant
"""

import os
import json
import logging
import threading
import traceback
from typing import Dict, Optional, List, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)


class AccessAction(Enum):
    """访问动作类型"""
    KEY_ACCESS = "key_access"           # 密钥访问
    KEY_ROTATE = "key_rotation"          # 密钥轮转
    KEY_INVALIDATE = "key_invalidate"   # 密钥失效
    KEY_STORE = "key_store"              # 密钥存储
    KEY_DELETE = "key_delete"             # 密钥删除
    KEY_VALIDATE = "key_validate"        # 密钥验证
    SYSTEM_START = "system_start"        # 系统启动
    SYSTEM_SHUTDOWN = "system_shutdown" # 系统关闭


@dataclass
class AuditLogEntry:
    """
    审计日志条目

    记录每一次密钥操作的完整上下文
    """
    timestamp: datetime
    action: AccessAction
    provider: str
    key_id: str
    caller_info: Dict[str, str]
    environment: str
    success: bool
    error_message: Optional[str] = None
    duration_ms: Optional[float] = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'action': self.action.value,
            'provider': self.provider,
            'key_id': self.key_id,
            'caller': self.caller_info,
            'environment': self.environment,
            'success': self.success,
            'error_message': self.error_message,
            'duration_ms': self.duration_ms,
            'metadata': self.metadata
        }


class AuditLogger:
    """
    审计日志记录器

    特性：
    - 结构化日志格式
    - 多输出目标（文件、Syslog、SIEM）
    - 敏感信息脱敏
    - 日志轮转

    使用示例：
        audit = AuditLogger()
        audit.log_access(provider='openai', key_id='xxx', action=AccessAction.KEY_ACCESS)
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.environment = os.getenv('ECO_ENV', os.getenv('HERMES_ENV', 'unknown'))

        # 日志文件配置
        self.log_dir = Path(self.config.get('log_dir', '~/.ecohub/logs'))
        self.log_dir = self.log_dir.expanduser()
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 日志文件
        self.audit_file = self.log_dir / 'audit.log'
        self.error_file = self.log_dir / 'audit_error.log'

        # 内存缓冲（批量写入）
        self._buffer: List[AuditLogEntry] = []
        self._buffer_size = self.config.get('buffer_size', 100)
        self._flush_interval = self.config.get('flush_interval', 60)  # 秒
        self._lock = threading.Lock()
        self._last_flush = datetime.now()

        # SIEM配置
        self.siem_enabled = self.config.get('siem_enabled', False)
        self.siem_endpoint = self.config.get('siem_endpoint')
        self.siem_api_key = os.getenv('ECO_SIEM_API_KEY')

        # 敏感信息脱敏配置
        self.sensitive_fields = ['key_value', 'key', 'token', 'password', 'secret']

        logger.info(f"AuditLogger 初始化完成，环境: {self.environment}")

    def log(self, entry: AuditLogEntry):
        """
        记录审计日志

        Args:
            entry: 审计日志条目
        """
        try:
            # 脱敏处理
            sanitized_entry = self._sanitize_entry(entry)

            # 写入内存缓冲
            with self._lock:
                self._buffer.append(sanitized_entry)

                # 检查是否需要刷新
                should_flush = (
                    len(self._buffer) >= self._buffer_size or
                    (datetime.now() - self._last_flush).seconds >= self._flush_interval
                )

                if should_flush:
                    self._flush_buffer()

            # 异步发送到SIEM
            if self.siem_enabled:
                self._send_to_siem_async(sanitized_entry)

        except Exception as e:
            logger.error(f"记录审计日志失败: {e}")

    def log_access(self, provider: str, key_id: str, action: AccessAction,
                   success: bool = True, error: Optional[str] = None,
                   duration_ms: Optional[float] = None, **metadata):
        """
        记录密钥访问

        Args:
            provider: 提供商名称
            key_id: 密钥ID
            action: 访问动作
            success: 是否成功
            error: 错误信息
            duration_ms: 耗时
            **metadata: 额外元数据
        """
        entry = AuditLogEntry(
            timestamp=datetime.now(),
            action=action,
            provider=provider,
            key_id=key_id,
            caller_info=self._get_caller_info(),
            environment=self.environment,
            success=success,
            error_message=error,
            duration_ms=duration_ms,
            metadata=metadata
        )

        self.log(entry)

        # 如果是错误，同时记录到错误日志
        if not success and error:
            self._log_error(entry)

    def _sanitize_entry(self, entry: AuditLogEntry) -> AuditLogEntry:
        """脱敏处理审计日志条目"""
        sanitized_metadata = {}

        for key, value in entry.metadata.items():
            if any(sensitive in key.lower() for sensitive in self.sensitive_fields):
                # 脱敏：只显示前后各2个字符
                if isinstance(value, str) and len(value) > 8:
                    sanitized_metadata[key] = value[:4] + '****' + value[-4:]
                else:
                    sanitized_metadata[key] = '****'
            else:
                sanitized_metadata[key] = value

        # 脱敏caller_info
        sanitized_caller = {}
        for key, value in entry.caller_info.items():
            if any(sensitive in key.lower() for sensitive in self.sensitive_fields):
                sanitized_caller[key] = '****'
            else:
                sanitized_caller[key] = value

        entry.metadata = sanitized_metadata
        entry.caller_info = sanitized_caller

        return entry

    def _get_caller_info(self) -> Dict[str, str]:
        """获取调用者信息"""
        info = {
            'process_id': str(os.getpid()),
            'thread_id': str(threading.get_ident()),
        }

        # 尝试获取调用栈信息
        try:
            import inspect
            stack = inspect.stack()

            # 获取直接调用者
            if len(stack) > 2:
                caller = stack[2]
                info['caller_file'] = os.path.basename(caller.filename)
                info['caller_function'] = caller.function
                info['caller_line'] = str(caller.lineno)
        except Exception:
            pass

        return info

    def _flush_buffer(self):
        """刷新缓冲区到磁盘"""
        if not self._buffer:
            return

        try:
            with open(self.audit_file, 'a', encoding='utf-8') as f:
                for entry in self._buffer:
                    log_line = json.dumps(entry.to_dict(), ensure_ascii=False)
                    f.write(log_line + '\n')

            self._buffer.clear()
            self._last_flush = datetime.now()

        except Exception as e:
            logger.error(f"刷新审计日志缓冲区失败: {e}")

    def _log_error(self, entry: AuditLogEntry):
        """记录错误日志"""
        try:
            with open(self.error_file, 'a', encoding='utf-8') as f:
                log_line = json.dumps(entry.to_dict(), ensure_ascii=False)
                f.write(log_line + '\n')
        except Exception as e:
            logger.error(f"写入错误日志失败: {e}")

    def _send_to_siem_async(self, entry: AuditLogEntry):
        """异步发送日志到SIEM"""
        import urllib.request
        import urllib.error

        def send():
            try:
                if not self.siem_endpoint:
                    return

                payload = json.dumps(entry.to_dict()).encode()

                req = urllib.request.Request(
                    self.siem_endpoint,
                    data=payload,
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {self.siem_api_key}'
                    },
                    method='POST'
                )

                urllib.request.urlopen(req, timeout=5)

            except Exception as e:
                logger.debug(f"SIEM发送失败: {e}")

        # 在后台线程发送
        thread = threading.Thread(target=send, daemon=True)
        thread.start()

    def get_recent_logs(self, limit: int = 100) -> List[AuditLogEntry]:
        """获取最近的审计日志"""
        logs = []

        try:
            if self.audit_file.exists():
                with open(self.audit_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                for line in lines[-limit:]:
                    try:
                        data = json.loads(line)
                        logs.append(AuditLogEntry(
                            timestamp=datetime.fromisoformat(data['timestamp']),
                            action=AccessAction(data['action']),
                            provider=data['provider'],
                            key_id=data['key_id'],
                            caller_info=data['caller'],
                            environment=data['environment'],
                            success=data['success'],
                            error_message=data.get('error_message'),
                            duration_ms=data.get('duration_ms'),
                            metadata=data.get('metadata', {})
                        ))
                    except Exception:
                        continue

        except Exception as e:
            logger.error(f"读取审计日志失败: {e}")

        return logs

    def flush(self):
        """手动刷新缓冲区"""
        with self._lock:
            self._flush_buffer()


class KeyConsumer:
    """
    密钥消费者 - 提供统一的密钥访问接口

    特性：
    1. 统一的密钥访问API
    2. 完整的审计追踪
    3. 访问统计和监控
    4. 自动触发轮转检查

    使用示例：
        consumer = KeyConsumer(storage)
        api_key = consumer.get_key_for_provider('openai')
    """

    def __init__(self, storage, audit_logger: Optional[AuditLogger] = None,
                 rotator=None, config: Optional[Dict] = None):
        """
        初始化密钥消费者

        Args:
            storage: KeyStorage实例
            audit_logger: 审计日志记录器
            rotator: KeyRotator实例（用于触发轮转）
            config: 配置字典
        """
        self.storage = storage
        self.audit_logger = audit_logger or AuditLogger()
        self.rotator = rotator
        self.config = config or {}

        # 访问统计
        self._access_count: Dict[str, int] = {}
        self._last_access: Dict[str, datetime] = {}
        self._lock = threading.Lock()

        # 轮转检查阈值
        self.rotation_threshold_days = self.config.get('rotation_threshold_days', 30)

        logger.info("KeyConsumer 初始化完成")

    def get_key_for_provider(self, provider: str, skip_audit: bool = False) -> str:
        """
        获取指定提供商的密钥（主接口）

        Args:
            provider: 提供商名称
            skip_audit: 是否跳过审计记录（内部调用使用）

        Returns:
            密钥值

        Raises:
            KeyError: 密钥不存在
            ValueError: 密钥无效
        """
        start_time = datetime.now()
        success = True
        error_msg = None

        try:
            # 1. 从存储获取
            processed_key = self.storage.get_key(provider)

            if not processed_key:
                raise KeyError(f"未找到提供商 {provider} 的密钥")

            # 2. 检查有效性
            if not processed_key.is_valid:
                raise ValueError(f"提供商 {provider} 的密钥已失效")

            if processed_key.is_expired():
                raise ValueError(f"提供商 {provider} 的密钥已过期")

            # 3. 记录访问统计
            with self._lock:
                self._access_count[provider] = self._access_count.get(provider, 0) + 1
                self._last_access[provider] = datetime.now()

            # 4. 检查是否需要轮转
            if processed_key.needs_rotation(self.rotation_threshold_days):
                logger.info(f"密钥 {provider} 可能需要轮转")
                if self.rotator:
                    self.rotator.schedule_rotation(provider)

            # 5. 返回密钥值
            return processed_key.value

        except (KeyError, ValueError) as e:
            success = False
            error_msg = str(e)
            raise

        except Exception as e:
            success = False
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"获取密钥 {provider} 时发生错误: {e}")
            raise

        finally:
            # 6. 记录审计日志
            if not skip_audit:
                duration_ms = (datetime.now() - start_time).total_seconds() * 1000

                self.audit_logger.log_access(
                    provider=provider,
                    key_id=getattr(processed_key, 'id', 'unknown') if success else 'unknown',
                    action=AccessAction.KEY_ACCESS,
                    success=success,
                    error=error_msg,
                    duration_ms=duration_ms,
                    access_count=self._access_count.get(provider, 0)
                )

    def get_all_keys(self) -> Dict[str, str]:
        """
        获取所有可用密钥

        Returns:
            provider -> key_value 的字典
        """
        keys = {}
        providers = self.storage.list_providers()

        for provider in providers:
            try:
                key_value = self.get_key_for_provider(provider, skip_audit=True)
                keys[provider] = key_value
            except Exception as e:
                logger.warning(f"获取密钥 {provider} 失败: {e}")

        return keys

    def get_access_stats(self) -> Dict[str, Any]:
        """获取访问统计"""
        with self._lock:
            return {
                'access_count': self._access_count.copy(),
                'last_access': {k: v.isoformat() for k, v in self._last_access.items()},
                'total_providers': len(self._access_count)
            }

    def reset_stats(self):
        """重置访问统计"""
        with self._lock:
            self._access_count.clear()
            self._last_access.clear()

    def validate_key(self, provider: str) -> bool:
        """
        验证密钥有效性

        Returns:
            密钥是否有效
        """
        try:
            processed_key = self.storage.get_key(provider)
            if not processed_key:
                return False

            # 在线验证
            if processed_key.is_valid and not processed_key.is_expired():
                return True

            return False

        except Exception as e:
            logger.error(f"验证密钥 {provider} 失败: {e}")
            return False

    def get_key_info(self, provider: str) -> Optional[Dict]:
        """
        获取密钥信息（不含密钥值）

        Returns:
            密钥信息字典
        """
        try:
            processed_key = self.storage.get_key(provider)
            if not processed_key:
                return None

            return {
                'provider': processed_key.provider,
                'key_type': processed_key.key_type.value if hasattr(processed_key.key_type, 'value') else str(processed_key.key_type),
                'is_valid': processed_key.is_valid,
                'is_expired': processed_key.is_expired(),
                'expires_at': processed_key.expires_at.isoformat() if processed_key.expires_at else None,
                'days_until_expiry': processed_key.days_until_expiry(),
                'needs_rotation': processed_key.needs_rotation(self.rotation_threshold_days),
                'source': processed_key.source,
                'access_count': self._access_count.get(provider, 0),
                'last_access': self._last_access.get(provider, None)
            }

        except Exception as e:
            logger.error(f"获取密钥信息 {provider} 失败: {e}")
            return None

    def list_providers_with_info(self) -> List[Dict]:
        """列出所有密钥及其信息"""
        providers = self.storage.list_providers()
        result = []

        for provider in providers:
            info = self.get_key_info(provider)
            if info:
                result.append(info)

        return result


class KeyValidationCache:
    """
    密钥验证缓存 - 用于缓存验证结果

    避免频繁调用provider的验证API
    """

    def __init__(self, ttl_seconds: int = 3600):
        self.ttl = ttl_seconds
        self._cache: Dict[str, Dict] = {}
        self._lock = threading.Lock()

    def get(self, provider: str, key_fingerprint: str) -> Optional[bool]:
        """获取缓存的验证结果"""
        with self._lock:
            cache_key = f"{provider}:{key_fingerprint}"
            if cache_key in self._cache:
                entry = self._cache[cache_key]
                if entry['expires_at'] > datetime.now():
                    return entry['result']
                else:
                    del self._cache[cache_key]
        return None

    def set(self, provider: str, key_fingerprint: str, result: bool):
        """缓存验证结果"""
        with self._lock:
            cache_key = f"{provider}:{key_fingerprint}"
            self._cache[cache_key] = {
                'result': result,
                'expires_at': datetime.now().timestamp() + self.ttl
            }

    def invalidate(self, provider: str = None):
        """使缓存失效"""
        with self._lock:
            if provider:
                # 只删除指定provider的缓存
                keys_to_delete = [k for k in self._cache if k.startswith(f"{provider}:")]
                for k in keys_to_delete:
                    del self._cache[k]
            else:
                self._cache.clear()