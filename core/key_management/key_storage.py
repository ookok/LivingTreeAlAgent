"""
第3层：密钥存储管理器 (Key Storage Layer)
==========================================

功能：多级密钥存储，支持不同访问场景

三级存储策略：
1. 内存缓存 (InMemoryCache) - 毫秒级访问，高频使用
2. 加密文件 (EncryptedFileCache) - 秒级访问，持久化存储
3. 外部缓存 (ExternalCache) - 网络访问，分布式场景

Author: Hermes Desktop AI Assistant
"""

import os
import json
import pickle
import shutil
import logging
import threading
import time
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from abc import ABC, abstractmethod
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class StorageStats:
    """存储统计信息"""
    total_keys: int = 0
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    last_cleanup: Optional[datetime] = None
    storage_size_bytes: int = 0


class StorageLayer(ABC):
    """存储层抽象基类"""

    @abstractmethod
    def store(self, keys: Dict[str, 'ProcessedKey']) -> bool:
        """存储密钥"""
        pass

    @abstractmethod
    def retrieve(self, provider: str) -> Optional['ProcessedKey']:
        """检索密钥"""
        pass

    @abstractmethod
    def delete(self, provider: str) -> bool:
        """删除密钥"""
        pass

    @abstractmethod
    def exists(self, provider: str) -> bool:
        """检查密钥是否存在"""
        pass

    @abstractmethod
    def list_all(self) -> List[str]:
        """列出所有密钥provider"""
        pass


class ProcessedKey:
    """简化引用，避免循环导入"""
    pass


class InMemoryCache(StorageLayer):
    """
    内存缓存 - 用于高频访问的密钥

    特点：
    - 毫秒级访问速度
    - 基于LRU的淘汰策略
    - TTL过期机制
    - 线程安全

    使用场景：
    - 热路径中的API密钥访问
    - 频繁使用的服务密钥
    """

    DEFAULT_TTL_SECONDS = 300  # 5分钟
    MAX_CACHE_SIZE = 100       # 最大缓存条目

    def __init__(self, ttl_seconds: int = None, max_size: int = None):
        self.ttl = ttl_seconds or self.DEFAULT_TTL_SECONDS
        self.max_size = max_size or self.MAX_CACHE_SIZE
        self._cache: Dict[str, Dict] = {}
        self._lock = threading.RLock()
        self._access_order: List[str] = []  # 用于LRU

        # 统计
        self._hits = 0
        self._misses = 0
        self._evictions = 0

        logger.info(f"InMemoryCache 初始化完成，TTL={self.ttl}s, MaxSize={self.max_size}")

    def store(self, keys: Dict[str, ProcessedKey]) -> bool:
        """存储密钥到内存缓存"""
        with self._lock:
            for provider, key in keys.items():
                # 检查是否需要淘汰
                if len(self._cache) >= self.max_size and provider not in self._cache:
                    self._evict_lru()

                # 存储
                self._cache[provider] = {
                    'key': key,
                    'stored_at': time.time(),
                    'expires_at': time.time() + self.ttl,
                    'access_count': 0
                }

                # 更新访问顺序
                if provider in self._access_order:
                    self._access_order.remove(provider)
                self._access_order.append(provider)

            return True

    def retrieve(self, provider: str) -> Optional[ProcessedKey]:
        """从内存缓存检索密钥"""
        with self._lock:
            if provider not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[provider]

            # 检查过期
            if time.time() > entry['expires_at']:
                self._cache.pop(provider, None)
                self._access_order.remove(provider) if provider in self._access_order else None
                self._misses += 1
                return None

            # 更新访问信息
            entry['access_count'] += 1
            entry['last_access'] = time.time()

            # 移到访问顺序末尾（LRU）
            if provider in self._access_order:
                self._access_order.remove(provider)
            self._access_order.append(provider)

            self._hits += 1
            return entry['key']

    def delete(self, provider: str) -> bool:
        """从内存缓存删除密钥"""
        with self._lock:
            if provider in self._cache:
                self._cache.pop(provider, None)
                if provider in self._access_order:
                    self._access_order.remove(provider)
                return True
            return False

    def exists(self, provider: str) -> bool:
        """检查密钥是否存在（未过期）"""
        with self._lock:
            if provider not in self._cache:
                return False

            entry = self._cache[provider]
            if time.time() > entry['expires_at']:
                self._cache.pop(provider, None)
                return False

            return True

    def list_all(self) -> List[str]:
        """列出所有未过期的provider"""
        with self._lock:
            now = time.time()
            expired = []

            for provider, entry in self._cache.items():
                if now > entry['expires_at']:
                    expired.append(provider)

            # 清理过期条目
            for provider in expired:
                self._cache.pop(provider, None)
                if provider in self._access_order:
                    self._access_order.remove(provider)

            return list(self._cache.keys())

    def _evict_lru(self):
        """淘汰最少使用的条目"""
        if not self._access_order:
            return

        # 移除最旧的（列表开头）
        lru_provider = self._access_order.pop(0)
        self._cache.pop(lru_provider, None)
        self._evictions += 1
        logger.debug(f"LRU淘汰: {lru_provider}")

    def get_stats(self) -> StorageStats:
        """获取缓存统计"""
        with self._lock:
            return StorageStats(
                total_keys=len(self._cache),
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
                last_cleanup=None
            )

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
            logger.info("内存缓存已清空")

    def cleanup_expired(self) -> int:
        """清理过期条目，返回清理数量"""
        with self._lock:
            now = time.time()
            expired = [
                provider for provider, entry in self._cache.items()
                if now > entry['expires_at']
            ]

            for provider in expired:
                self._cache.pop(provider, None)
                if provider in self._access_order:
                    self._access_order.remove(provider)

            if expired:
                logger.info(f"清理了 {len(expired)} 个过期缓存条目")

            return len(expired)


class EncryptedFileCache(StorageLayer):
    """
    加密文件缓存 - 用于持久化存储

    特点：
    - 加密存储，防止密钥泄露
    - 持久化到磁盘
    - 每个密钥单独文件
    - 文件级权限控制

    使用场景：
    - 应用重启后密钥恢复
    - 密钥的持久化备份
    - 多进程共享密钥
    """

    def __init__(self, storage_dir: str = None, cipher=None):
        self.storage_dir = Path(storage_dir or os.path.expanduser('~/.ecohub/keys'))
        self.cipher = cipher
        self._ensure_storage_dir()

        # 统计
        self._read_count = 0
        self._write_count = 0

        logger.info(f"EncryptedFileCache 初始化完成，存储目录: {self.storage_dir}")

    def _ensure_storage_dir(self):
        """确保存储目录存在"""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        # 设置目录权限（仅当前用户）
        os.chmod(self.storage_dir, 0o700)

    def _get_key_path(self, provider: str) -> Path:
        """获取密钥文件路径"""
        # provider名称做hash，避免文件系统限制
        safe_name = hashlib.sha256(provider.encode()).hexdigest()[:16]
        return self.storage_dir / f"{safe_name}.ekey"

    def store(self, keys: Dict[str, ProcessedKey]) -> bool:
        """加密存储密钥到文件"""
        for provider, key in keys.items():
            try:
                key_path = self._get_key_path(provider)

                # 序列化
                key_data = {
                    'provider': key.provider,
                    'value': key.value,
                    'key_type': key.key_type.value if hasattr(key.key_type, 'value') else str(key.key_type),
                    'is_valid': key.is_valid,
                    'expires_at': key.expires_at.isoformat() if key.expires_at else None,
                    'source': key.source,
                    'injected_at': key.injected_at.isoformat() if hasattr(key, 'injected_at') else None,
                    'metadata': key.metadata if hasattr(key, 'metadata') else {},
                }

                # JSON序列化
                json_data = json.dumps(key_data, ensure_ascii=False)

                # 加密
                if self.cipher:
                    encrypted = self.cipher.encrypt(json_data.encode())
                else:
                    encrypted = json_data.encode()

                # 写入文件
                with open(key_path, 'wb') as f:
                    f.write(encrypted)

                # 设置文件权限
                os.chmod(key_path, 0o600)

                self._write_count += 1

            except Exception as e:
                logger.error(f"存储密钥 {provider} 到文件失败: {e}")
                return False

        return True

    def retrieve(self, provider: str) -> Optional[ProcessedKey]:
        """从文件读取并解密密钥"""
        key_path = self._get_key_path(provider)

        if not key_path.exists():
            return None

        try:
            with open(key_path, 'rb') as f:
                encrypted = f.read()

            # 解密
            if self.cipher:
                json_data = self.cipher.decrypt(encrypted).decode()
            else:
                json_data = encrypted.decode()

            # 反序列化
            key_data = json.loads(json_data)

            # 重建ProcessedKey对象
            from .key_processor import ProcessedKey, KeyType
            key = ProcessedKey(
                provider=key_data['provider'],
                value=key_data['value'],
                key_type=KeyType(key_data.get('key_type', 'unknown')),
                is_valid=key_data.get('is_valid', True),
                expires_at=datetime.fromisoformat(key_data['expires_at']) if key_data.get('expires_at') else None,
                source=key_data.get('source', 'file'),
                metadata=key_data.get('metadata', {})
            )

            self._read_count += 1
            return key

        except Exception as e:
            logger.error(f"读取密钥 {provider} 失败: {e}")
            return None

    def delete(self, provider: str) -> bool:
        """删除密钥文件"""
        key_path = self._get_key_path(provider)
        if key_path.exists():
            try:
                key_path.unlink()
                return True
            except Exception as e:
                logger.error(f"删除密钥文件 {provider} 失败: {e}")
        return False

    def exists(self, provider: str) -> bool:
        """检查密钥文件是否存在"""
        return self._get_key_path(provider).exists()

    def list_all(self) -> List[str]:
        """列出所有密钥provider"""
        providers = []
        for key_file in self.storage_dir.glob('*.ekey'):
            # 尝试读取获取provider名称
            key = self.retrieve(key_file.stem)
            if key:
                providers.append(key.provider)
        return providers

    def get_stats(self) -> StorageStats:
        """获取存储统计"""
        total_size = sum(f.stat().st_size for f in self.storage_dir.glob('*.ekey'))
        return StorageStats(
            total_keys=len(list(self.storage_dir.glob('*.ekey'))),
            storage_size_bytes=total_size
        )

    def backup(self, backup_dir: str = None) -> str:
        """备份所有密钥文件"""
        backup_path = Path(backup_dir or str(self.storage_dir) + '.backup')
        backup_path.mkdir(parents=True, exist_ok=True)

        for key_file in self.storage_dir.glob('*.ekey'):
            shutil.copy2(key_file, backup_path / key_file.name)

        logger.info(f"密钥已备份到: {backup_path}")
        return str(backup_path)


class ExternalCache(StorageLayer):
    """
    外部缓存 - 用于分布式/跨进程场景

    支持的后端：
    - Redis
    - Memcached
    - 自定义HTTP后端

    使用场景：
    - 多实例部署
    - 容器环境密钥共享
    - 密钥的集中管理
    """

    def __init__(self, backend: str = 'redis', config: Dict = None):
        self.backend = backend.lower()
        self.config = config or {}
        self._client = None
        self._connected = False

        # 初始化连接
        self._connect()

    def _connect(self):
        """建立连接"""
        if self.backend == 'redis':
            self._connect_redis()
        elif self.backend == 'memcached':
            self._connect_memcached()
        else:
            logger.warning(f"不支持的外部缓存后端: {self.backend}")

    def _connect_redis(self):
        """连接Redis"""
        try:
            import redis

            redis_config = {
                'host': self.config.get('host', 'localhost'),
                'port': self.config.get('port', 6379),
                'db': self.config.get('db', 0),
                'password': self.config.get('password'),
                'ssl': self.config.get('ssl', False),
                'socket_timeout': self.config.get('timeout', 5),
            }

            self._client = redis.Redis(**redis_config)
            # 测试连接
            self._client.ping()
            self._connected = True
            logger.info("已连接到Redis")

        except ImportError:
            logger.warning("redis模块未安装，外部缓存不可用")
        except Exception as e:
            logger.warning(f"Redis连接失败: {e}")

    def _connect_memcached(self):
        """连接Memcached"""
        try:
            import memcache

            servers = self.config.get('servers', ['localhost:11211'])
            self._client = memcache.Client(servers)
            self._connected = True
            logger.info("已连接到Memcached")

        except ImportError:
            logger.warning("pymemcache模块未安装，外部缓存不可用")
        except Exception as e:
            logger.warning(f"Memcached连接失败: {e}")

    def store(self, keys: Dict[str, ProcessedKey]) -> bool:
        """存储到外部缓存"""
        if not self._connected:
            return False

        try:
            for provider, key in keys.items():
                cache_key = f"key:{provider}"
                cache_value = pickle.dumps(key)

                if self.backend == 'redis':
                    self._client.setex(
                        cache_key,
                        self.config.get('ttl', 3600),
                        cache_value
                    )
                elif self.backend == 'memcached':
                    self._client.set(cache_key, cache_value)

            return True

        except Exception as e:
            logger.error(f"外部缓存存储失败: {e}")
            return False

    def retrieve(self, provider: str) -> Optional[ProcessedKey]:
        """从外部缓存检索"""
        if not self._connected:
            return None

        try:
            cache_key = f"key:{provider}"

            if self.backend == 'redis':
                value = self._client.get(cache_key)
            elif self.backend == 'memcached':
                value = self._client.get(cache_key)

            if value:
                return pickle.loads(value)

        except Exception as e:
            logger.error(f"外部缓存检索失败: {e}")

        return None

    def delete(self, provider: str) -> bool:
        """从外部缓存删除"""
        if not self._connected:
            return False

        try:
            cache_key = f"key:{provider}"
            self._client.delete(cache_key)
            return True
        except Exception as e:
            logger.error(f"外部缓存删除失败: {e}")
            return False

    def exists(self, provider: str) -> bool:
        """检查外部缓存是否存在"""
        if not self._connected:
            return False

        try:
            cache_key = f"key:{provider}"
            if self.backend == 'redis':
                return self._client.exists(cache_key) > 0
            elif self.backend == 'memcached':
                return self._client.get(cache_key) is not None
        except Exception:
            pass

        return False

    def list_all(self) -> List[str]:
        """列出外部缓存中的所有provider"""
        if not self._connected:
            return []

        try:
            if self.backend == 'redis':
                keys = self._client.keys('key:*')
                return [k.decode()[4:] for k in keys]  # 移除 'key:' 前缀
        except Exception as e:
            logger.error(f"外部缓存列表失败: {e}")

        return []

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected


class KeyStorage:
    """
    密钥存储管理器 - 统一管理多层存储

    设计理念：
    - 存储分层：内存 → 文件 → 外部
    - 读取时从最快层开始，逐层降级查找
    - 写入时同时写入所有层
    - 自动处理层级间的同步

    使用示例：
        storage = KeyStorage()
        storage.store_keys(processed_keys)
        key = storage.get_key('openai')
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

        # 初始化各层存储
        self.memory_cache = InMemoryCache(
            ttl_seconds=self.config.get('memory_ttl', 300),
            max_size=self.config.get('max_memory_keys', 100)
        )

        self.file_cache = EncryptedFileCache(
            storage_dir=self.config.get('storage_dir'),
            cipher=self.config.get('cipher')
        )

        self.external_cache = None
        if self.config.get('enable_external', False):
            self.external_cache = ExternalCache(
                backend=self.config.get('external_backend', 'redis'),
                config=self.config.get('external_config', {})
            )

        # 读取优先级（从快到慢）
        self.read_priority = ['memory', 'external', 'file']
        # 写入同步（同时写入）
        self.write_sync = self.config.get('write_sync', ['memory', 'file'])

        logger.info(f"KeyStorage 初始化完成，读取优先级: {self.read_priority}")

    def store_keys(self, keys: Dict[str, ProcessedKey]) -> bool:
        """
        存储所有密钥到各层

        Args:
            keys: ProcessedKey字典

        Returns:
            是否全部成功
        """
        results = {}

        # 同步写入
        if 'memory' in self.write_sync:
            results['memory'] = self.memory_cache.store(keys)

        if 'file' in self.write_sync:
            results['file'] = self.file_cache.store(keys)

        if 'external' in self.write_sync and self.external_cache:
            results['external'] = self.external_cache.store(keys)

        # 只要有一层成功就认为成功
        success = any(results.values())

        logger.info(f"密钥存储完成: {results}")
        return success

    def get_key(self, provider: str) -> Optional[ProcessedKey]:
        """
        获取密钥（多级缓存查询）

        按优先级逐层查找：
        1. 内存缓存
        2. 外部缓存
        3. 文件缓存
        """
        for layer in self.read_priority:
            try:
                if layer == 'memory':
                    key = self.memory_cache.retrieve(provider)
                elif layer == 'external' and self.external_cache:
                    key = self.external_cache.retrieve(provider)
                elif layer == 'file':
                    key = self.file_cache.retrieve(provider)
                else:
                    continue

                if key:
                    # 缓存预热：同步到更快层
                    if layer != 'memory':
                        self.memory_cache.store({provider: key})
                    logger.debug(f"从 {layer} 层获取密钥: {provider}")
                    return key

            except Exception as e:
                logger.debug(f"从 {layer} 层获取密钥 {provider} 失败: {e}")

        logger.debug(f"未找到密钥: {provider}")
        return None

    def delete_key(self, provider: str) -> bool:
        """从所有层删除密钥"""
        results = {
            'memory': self.memory_cache.delete(provider),
            'file': self.file_cache.delete(provider),
        }

        if self.external_cache:
            results['external'] = self.external_cache.delete(provider)

        return any(results.values())

    def key_exists(self, provider: str) -> bool:
        """检查密钥是否存在"""
        # 先检查最快层
        if self.memory_cache.exists(provider):
            return True

        # 再检查其他层
        for layer in ['external', 'file']:
            if layer == 'external' and self.external_cache:
                if self.external_cache.exists(provider):
                    return True
            elif layer == 'file':
                if self.file_cache.exists(provider):
                    return True

        return False

    def list_providers(self) -> List[str]:
        """列出所有provider（合并各层）"""
        all_providers = set()

        all_providers.update(self.memory_cache.list_all())
        all_providers.update(self.file_cache.list_all())

        if self.external_cache:
            all_providers.update(self.external_cache.list_all())

        return list(all_providers)

    def get_stats(self) -> Dict[str, StorageStats]:
        """获取各层存储统计"""
        return {
            'memory': self.memory_cache.get_stats(),
            'file': self.file_cache.get_stats(),
        }

    def cleanup(self) -> Dict[str, int]:
        """清理过期数据"""
        results = {
            'memory': self.memory_cache.cleanup_expired()
        }
        return results

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        health = {
            'memory': {
                'available': True,
                'keys': len(self.memory_cache.list_all())
            },
            'file': {
                'available': True,
                'keys': len(self.file_cache.list_all()),
                'size_bytes': self.file_cache.get_stats().storage_size_bytes
            }
        }

        if self.external_cache:
            health['external'] = {
                'available': self.external_cache.is_connected(),
                'keys': len(self.external_cache.list_all()) if self.external_cache.is_connected() else 0
            }

        return health