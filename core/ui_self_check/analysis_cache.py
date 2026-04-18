"""
分析结果缓存 - AnalysisCache
核心理念：对常见错误模式和组件结构，缓存分析结果，下次遇到直接返回

设计特点：
1. LRU淘汰策略 - 限制内存占用
2. TTL过期机制 - 避免过期数据
3. 懒清理 - 不阻塞主线程
"""

import json
import hashlib
import threading
import time
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)


@dataclass
class CachedAnalysis:
    """缓存的分析结果"""
    cache_key: str
    error_type: str
    component_name: str
    diagnosis: str           # AI诊断结果
    suggestion: str          # 修复建议
    code_diff: Optional[str]  # 代码差分（可选）
    doc_links: list          # 相关文档链接
    confidence: float         # 置信度 0-1
    created_at: float        # 创建时间戳
    accessed_at: float        # 最后访问时间
    hit_count: int           # 命中次数
    expires_at: float         # 过期时间戳

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def touch(self):
        """更新访问时间"""
        self.accessed_at = time.time()
        self.hit_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AnalysisCache:
    """
    分析结果缓存

    缓存策略：
    1. 按 error_type + component_name + stack_hash 建立Key
    2. LRU淘汰：当缓存超过 max_size 时，淘汰最久未使用的
    3. TTL过期：默认24小时过期，可配置
    4. 懒清理：每次访问时检查过期，而非定时清理
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
        self._cache: OrderedDict[str, CachedAnalysis] = OrderedDict()
        self._max_size = 1000           # 最大缓存条目
        self._default_ttl_seconds = 24 * 3600  # 默认24小时过期
        self._cleanup_threshold = 0.2    # 清理阈值（超过20%过期时触发懒清理）
        self._lock = threading.RLock()
        self._persist_path: Optional[str] = None
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "cleanups": 0
        }

    def set_persist_path(self, path: str):
        """设置持久化路径"""
        self._persist_path = path
        self._load_from_disk()

    def get(
        self,
        error_type: str,
        component_name: str,
        stack_hash: str
    ) -> Optional[CachedAnalysis]:
        """
        获取缓存的分析结果

        Returns:
            CachedAnalysis 或 None（未命中或已过期）
        """
        cache_key = self._make_key(error_type, component_name, stack_hash)

        with self._lock:
            cached = self._cache.get(cache_key)

            if cached is None:
                self._stats["misses"] += 1
                return None

            # 检查过期
            if cached.is_expired():
                del self._cache[cache_key]
                self._stats["misses"] += 1
                self._maybe_cleanup()
                return None

            # 更新访问时间并移动到末尾（LRU）
            cached.touch()
            self._cache.move_to_end(cache_key)
            self._stats["hits"] += 1

            return cached

    def put(
        self,
        error_type: str,
        component_name: str,
        stack_hash: str,
        diagnosis: str,
        suggestion: str,
        code_diff: Optional[str] = None,
        doc_links: Optional[list] = None,
        confidence: float = 0.9,
        ttl_seconds: Optional[int] = None
    ) -> str:
        """
        存入缓存

        Returns:
            cache_key
        """
        cache_key = self._make_key(error_type, component_name, stack_hash)
        ttl = ttl_seconds or self._default_ttl_seconds

        cached = CachedAnalysis(
            cache_key=cache_key,
            error_type=error_type,
            component_name=component_name,
            diagnosis=diagnosis,
            suggestion=suggestion,
            code_diff=code_diff,
            doc_links=doc_links or [],
            confidence=confidence,
            created_at=time.time(),
            accessed_at=time.time(),
            hit_count=0,
            expires_at=time.time() + ttl
        )

        with self._lock:
            # 如果已存在，先删除（更新时重新排序）
            if cache_key in self._cache:
                del self._cache[cache_key]

            self._cache[cache_key] = cached
            self._cache.move_to_end(cache_key)

            # 检查是否需要淘汰
            self._maybe_evict()

        # 异步持久化
        if self._persist_path:
            self._save_to_disk_async()

        return cache_key

    def _make_key(self, error_type: str, component_name: str, stack_hash: str) -> str:
        """生成缓存Key"""
        key_data = f"{error_type}:{component_name}:{stack_hash}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:24]

    def _maybe_evict(self):
        """LRU淘汰"""
        if len(self._cache) > self._max_size:
            # 淘汰最旧的 10%
            evict_count = max(1, int(self._max_size * 0.1))
            for _ in range(evict_count):
                self._cache.popitem(last=False)
                self._stats["evictions"] += 1

    def _maybe_cleanup(self):
        """懒清理过期条目"""
        if len(self._cache) < 100:
            return

        expired_count = sum(1 for c in self._cache.values() if c.is_expired())
        total_count = len(self._cache)

        # 超过阈值时清理
        if expired_count / total_count > self._cleanup_threshold:
            self._cleanup_expired()

    def _cleanup_expired(self):
        """清理过期条目"""
        now = time.time()
        keys_to_delete = [
            k for k, v in self._cache.items()
            if now > v.expires_at
        ]
        for key in keys_to_delete:
            del self._cache[key]

        if keys_to_delete:
            self._stats["cleanups"] += 1
            logger.info(f"Cleaned up {len(keys_to_delete)} expired cache entries")

    def _save_to_disk_async(self):
        """异步保存到磁盘"""
        def _save():
            if not self._persist_path:
                return
            try:
                with self._lock:
                    data = {
                        "cache": [v.to_dict() for v in self._cache.values()],
                        "stats": self._stats,
                        "saved_at": time.time()
                    }
                with open(self._persist_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Failed to save cache to disk: {e}")

        threading.Thread(target=_save, daemon=True).start()

    def _load_from_disk(self):
        """从磁盘加载"""
        if not self._persist_path or not os.path.exists(self._persist_path):
            return
        try:
            with open(self._persist_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            with self._lock:
                self._cache.clear()
                for item in data.get("cache", []):
                    cached = CachedAnalysis(**item)
                    if not cached.is_expired():
                        self._cache[cached.cache_key] = cached
                self._stats.update(data.get("stats", {}))
            logger.info(f"Loaded {len(self._cache)} cached entries from disk")
        except Exception as e:
            logger.error(f"Failed to load cache from disk: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total if total > 0 else 0
            return {
                **self._stats,
                "size": len(self._cache),
                "max_size": self._max_size,
                "hit_rate": f"{hit_rate:.2%}"
            }

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._stats = {"hits": 0, "misses": 0, "evictions": 0, "cleanups": 0}

    def invalidate_pattern(self, pattern: str):
        """按模式使缓存失效（如组件名匹配）"""
        with self._lock:
            keys_to_delete = [
                k for k, v in self._cache.items()
                if pattern.lower() in v.component_name.lower()
            ]
            for key in keys_to_delete:
                del self._cache[key]
