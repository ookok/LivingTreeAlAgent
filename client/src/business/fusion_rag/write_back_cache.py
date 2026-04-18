"""
L4 回填缓存机制
将 L4 执行结果异步写入上层缓存
实现"执行一次，多层受益"的缓存加速效果
"""

import asyncio
import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime, timedelta
from collections import defaultdict
from threading import Lock

logger = logging.getLogger(__name__)


class WriteBackCache:
    """
    L4 回填缓存

    职责:
    1. 接收 L4 执行结果
    2. 生成多级缓存 Key（L1 精确/L2 会话/L3 知识库）
    3. 异步回填上层缓存
    4. 批量合并写入，减少 IO
    """

    def __init__(
        self,
        l1_cache: Optional[Any] = None,
        l2_cache: Optional[Any] = None,
        l3_cache: Optional[Any] = None,
        batch_interval: float = 1.0,
        max_batch_size: int = 10
    ):
        """
        Args:
            l1_cache: L1 精确缓存层
            l2_cache: L2 会话缓存层
            l3_cache: L3 知识库缓存层
            batch_interval: 批量写入间隔（秒）
            max_batch_size: 最大批量大小
        """
        self.l1_cache = l1_cache
        self.l2_cache = l2_cache
        self.l3_cache = l3_cache

        # 批量写入队列
        self._queue: Dict[str, Dict[str, Any]] = {}
        self._queue_lock = Lock()
        self._batch_interval = batch_interval
        self._max_batch_size = max_batch_size

        # 统计
        self._stats = {
            "total_write_backs": 0,
            "l1_writes": 0,
            "l2_writes": 0,
            "l3_writes": 0,
            "batches": 0,
            "errors": 0
        }

        # 后台任务
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def start(self):
        """启动后台写入任务"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._background_writer())
        logger.info("[WriteBack] 回填缓存已启动")

    async def stop(self):
        """停止后台写入任务"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # 刷写剩余队列
        await self._flush_queue()
        logger.info("[WriteBack] 回填缓存已停止")

    async def write_back(
        self,
        messages: list,
        result: Dict[str, Any],
        ttl: Optional[int] = None
    ):
        """
        回填缓存

        Args:
            messages: 原始消息
            result: L4 执行结果
            ttl: 缓存过期时间（秒）
        """
        cache_key = self._generate_cache_key(messages)

        # 生成缓存条目
        entry = {
            "key": cache_key,
            "messages": messages,
            "result": result,
            "created_at": datetime.now().isoformat(),
            "ttl": ttl or 3600  # 默认 1 小时
        }

        # 加入队列
        with self._queue_lock:
            self._queue[cache_key] = entry
            queue_size = len(self._queue)

        # 检查是否需要触发立即刷新
        if queue_size >= self._max_batch_size:
            await self._flush_queue()

        self._stats["total_write_backs"] += 1

    def _generate_cache_key(self, messages: list) -> str:
        """生成缓存 Key"""
        content = "".join(m.get("content", "") for m in messages)
        return f"l4:{hashlib.md5(content.encode()).hexdigest()}"

    async def _background_writer(self):
        """后台批量写入任务"""
        while self._running:
            try:
                await asyncio.sleep(self._batch_interval)
                await self._flush_queue()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[WriteBack] 后台写入异常: {e}")
                self._stats["errors"] += 1

    async def _flush_queue(self):
        """批量写入缓存"""
        with self._queue_lock:
            if not self._queue:
                return
            entries = list(self._queue.values())
            self._queue.clear()
            self._stats["batches"] += 1

        for entry in entries:
            try:
                await self._write_to_all_layers(entry)
            except Exception as e:
                logger.warning(f"[WriteBack] 写入缓存失败: {e}")
                self._stats["errors"] += 1

    async def _write_to_all_layers(self, entry: Dict[str, Any]):
        """写入所有缓存层"""
        key = entry["key"]
        result = entry["result"]

        # L1: 精确缓存（完整结果）
        if self.l1_cache:
            try:
                await self._write_with_ttl(self.l1_cache, key, result, entry["ttl"])
                self._stats["l1_writes"] += 1
            except Exception as e:
                logger.debug(f"[WriteBack] L1 写入跳过: {e}")

        # L2: 会话缓存（带会话上下文）
        if self.l2_cache:
            try:
                session_key = f"{key}:{entry['created_at']}"
                await self._write_with_ttl(self.l2_cache, session_key, result, entry["ttl"])
                self._stats["l2_writes"] += 1
            except Exception as e:
                logger.debug(f"[WriteBack] L2 写入跳过: {e}")

        # L3: 知识库缓存（语义向量 + 摘要）
        if self.l3_cache:
            try:
                await self._write_to_l3(key, result, entry)
                self._stats["l3_writes"] += 1
            except Exception as e:
                logger.debug(f"[WriteBack] L3 写入跳过: {e}")

    async def _write_with_ttl(self, cache, key: str, value: Any, ttl: int):
        """写入带 TTL 的缓存"""
        if asyncio.iscoroutinefunction(cache.set):
            await cache.set(key, value, expire=ttl)
        elif hasattr(cache, 'setex'):
            cache.setex(key, ttl, json.dumps(value))
        elif hasattr(cache, '__setitem__'):
            cache[key] = value

    async def _write_to_l3(self, key: str, result: Dict[str, Any], entry: Dict[str, Any]):
        """写入 L3 知识库缓存"""
        # 提取内容用于语义索引
        content = ""
        if "choices" in result and len(result["choices"]) > 0:
            delta = result["choices"][0].get("message", {})
            content = delta.get("content", "")

        if not content:
            return

        # 生成摘要
        summary = content[:200] + "..." if len(content) > 200 else content

        # 生成向量 Key（简化处理，实际应使用嵌入模型）
        vector_key = f"vec:{hashlib.md5(content.encode()).hexdigest()}"

        l3_entry = {
            "key": key,
            "content": content,
            "summary": summary,
            "vector_key": vector_key,
            "model": result.get("model", "unknown"),
            "created_at": entry["created_at"],
            "ttl": entry["ttl"]
        }

        if asyncio.iscoroutinefunction(self.l3_cache.set):
            await self.l3_cache.set(key, l3_entry, expire=entry["ttl"])
        else:
            self.l3_cache[key] = l3_entry

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            **self._stats,
            "queue_size": len(self._queue)
        }


# ==================== 全局回填缓存实例 ====================

_write_back_cache: Optional[WriteBackCache] = None


def get_write_back_cache() -> WriteBackCache:
    """获取全局回填缓存实例"""
    global _write_back_cache
    if _write_back_cache is None:
        _write_back_cache = WriteBackCache()
        _write_back_cache.start()
    return _write_back_cache


# ==================== 与 L4 执行器集成 ====================

def integrate_with_l4_executor(l4_executor, l1_cache=None, l2_cache=None, l3_cache=None):
    """
    将回填缓存与 L4 执行器集成

    Args:
        l4_executor: L4RelayExecutor 实例
        l1_cache: L1 精确缓存
        l2_cache: L2 会话缓存
        l3_cache: L3 知识库缓存
    """
    cache = WriteBackCache(
        l1_cache=l1_cache,
        l2_cache=l2_cache,
        l3_cache=l3_cache
    )
    cache.start()

    # 设置回填回调
    async def write_back_callback(cache_key, result):
        # 这里需要原始 messages，但回调只传了 result
        # 实际使用时需要通过闭包或其他方式传递 messages
        pass

    l4_executor.set_write_back_callback(write_back_callback)

    return cache