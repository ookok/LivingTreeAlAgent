"""
性能优化模块
实现流式输出、智能缓存、资源管理等功能
"""

import os
import time
import asyncio
import threading
import queue
from typing import Optional, Dict, List, Any, Callable, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class CacheType(Enum):
    """缓存类型"""
    SEMANTIC = "semantic"
    CODE_SNIPPET = "code_snippet"
    MODEL_OUTPUT = "model_output"
    EMBEDDING = "embedding"


@dataclass
class CacheItem:
    """缓存项"""
    key: str
    value: Any
    cache_type: CacheType
    created_at: datetime = field(default_factory=datetime.now)
    accessed_at: datetime = field(default_factory=datetime.now)
    ttl: int = 3600  # 过期时间（秒）
    size: int = 0  # 大小（字节）


class LRUCache:
    """LRU缓存"""
    
    def __init__(self, max_size: int = 100, max_memory: int = 1024 * 1024 * 100):  # 100MB
        self.max_size = max_size
        self.max_memory = max_memory
        self.cache: Dict[str, CacheItem] = {}
        self.access_order: List[str] = []
        self.current_memory = 0
    
    def _update_access(self, key: str):
        """更新访问顺序"""
        if key in self.access_order:
            self.access_order.remove(key)
        self.access_order.append(key)
    
    def _evict(self):
        """驱逐缓存"""
        # 先驱逐过期项
        now = datetime.now()
        expired_keys = []
        for key, item in self.cache.items():
            if (now - item.created_at).total_seconds() > item.ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            self._remove(key)
        
        # 如果仍然超出限制，驱逐最久未使用的
        while len(self.cache) > self.max_size or self.current_memory > self.max_memory:
            if not self.access_order:
                break
            oldest_key = self.access_order.pop(0)
            self._remove(oldest_key)
    
    def _remove(self, key: str):
        """移除缓存项"""
        if key in self.cache:
            item = self.cache[key]
            self.current_memory -= item.size
            del self.cache[key]
            if key in self.access_order:
                self.access_order.remove(key)
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if key not in self.cache:
            return None
        
        # 检查是否过期
        item = self.cache[key]
        if (datetime.now() - item.created_at).total_seconds() > item.ttl:
            self._remove(key)
            return None
        
        # 更新访问时间和顺序
        item.accessed_at = datetime.now()
        self._update_access(key)
        
        return item.value
    
    def set(self, key: str, value: Any, cache_type: CacheType, ttl: int = 3600):
        """设置缓存"""
        # 计算大小
        size = len(str(value).encode('utf-8'))
        
        # 如果已经存在，先移除
        if key in self.cache:
            self._remove(key)
        
        # 创建缓存项
        item = CacheItem(
            key=key,
            value=value,
            cache_type=cache_type,
            ttl=ttl,
            size=size
        )
        
        # 添加到缓存
        self.cache[key] = item
        self.current_memory += size
        self._update_access(key)
        
        # 驱逐超出限制的项
        self._evict()
    
    def delete(self, key: str):
        """删除缓存"""
        self._remove(key)
    
    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self.access_order.clear()
        self.current_memory = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        stats = {
            'size': len(self.cache),
            'memory_used': self.current_memory,
            'memory_limit': self.max_memory,
            'items_by_type': {}
        }
        
        for item in self.cache.values():
            stats['items_by_type'][item.cache_type.value] = stats['items_by_type'].get(item.cache_type.value, 0) + 1
        
        return stats


class StreamingOutput:
    """流式输出"""
    
    def __init__(self):
        self.queue = asyncio.Queue()
        self.done = False
    
    async def write(self, chunk: str):
        """写入数据"""
        await self.queue.put(chunk)
    
    async def close(self):
        """关闭流"""
        self.done = True
        await self.queue.put(None)  # 发送结束信号
    
    async def __aiter__(self):
        """异步迭代器"""
        while not self.done or not self.queue.empty():
            chunk = await self.queue.get()
            if chunk is None:
                break
            yield chunk


class StreamingManager:
    """流式输出管理器"""
    
    def __init__(self):
        self.streams: Dict[str, StreamingOutput] = {}
    
    def create_stream(self, stream_id: str) -> StreamingOutput:
        """创建流"""
        stream = StreamingOutput()
        self.streams[stream_id] = stream
        return stream
    
    def get_stream(self, stream_id: str) -> Optional[StreamingOutput]:
        """获取流"""
        return self.streams.get(stream_id)
    
    async def close_stream(self, stream_id: str):
        """关闭流"""
        stream = self.streams.get(stream_id)
        if stream:
            await stream.close()
            del self.streams[stream_id]
    
    def clear_streams(self):
        """清空所有流"""
        for stream_id in list(self.streams.keys()):
            asyncio.create_task(self.close_stream(stream_id))


class ResourceManager:
    """资源管理器"""
    
    def __init__(self):
        self.resources: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.RLock()
    
    def acquire_resource(self, resource_id: str, resource_type: str, **kwargs) -> bool:
        """获取资源"""
        with self.lock:
            if resource_id in self.resources:
                # 资源已被占用
                return False
            
            self.resources[resource_id] = {
                'type': resource_type,
                'acquired_at': datetime.now(),
                'metadata': kwargs
            }
            return True
    
    def release_resource(self, resource_id: str):
        """释放资源"""
        with self.lock:
            if resource_id in self.resources:
                del self.resources[resource_id]
    
    def get_resource_status(self, resource_id: str) -> Optional[Dict[str, Any]]:
        """获取资源状态"""
        with self.lock:
            return self.resources.get(resource_id)
    
    def list_resources(self) -> List[Dict[str, Any]]:
        """列出所有资源"""
        with self.lock:
            return list(self.resources.values())
    
    def clear_unused_resources(self, timeout: int = 3600):
        """清理未使用的资源"""
        with self.lock:
            now = datetime.now()
            to_remove = []
            
            for resource_id, resource in self.resources.items():
                acquired_at = resource.get('acquired_at')
                if (now - acquired_at).total_seconds() > timeout:
                    to_remove.append(resource_id)
            
            for resource_id in to_remove:
                del self.resources[resource_id]


class PerformanceOptimizer:
    """性能优化器"""
    
    def __init__(self):
        self.cache = LRUCache()
        self.streaming_manager = StreamingManager()
        self.resource_manager = ResourceManager()
        self.request_times: Dict[str, List[float]] = {}
    
    def cache_get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        return self.cache.get(key)
    
    def cache_set(self, key: str, value: Any, cache_type: CacheType, ttl: int = 3600):
        """设置缓存"""
        self.cache.set(key, value, cache_type, ttl)
    
    def create_stream(self, stream_id: str) -> StreamingOutput:
        """创建流"""
        return self.streaming_manager.create_stream(stream_id)
    
    async def stream_response(self, stream_id: str, generator: AsyncGenerator[str, None]):
        """流式响应"""
        stream = self.streaming_manager.create_stream(stream_id)
        try:
            async for chunk in generator:
                await stream.write(chunk)
        finally:
            await stream.close()
    
    def acquire_resource(self, resource_id: str, resource_type: str, **kwargs) -> bool:
        """获取资源"""
        return self.resource_manager.acquire_resource(resource_id, resource_type, **kwargs)
    
    def release_resource(self, resource_id: str):
        """释放资源"""
        self.resource_manager.release_resource(resource_id)
    
    def track_request_time(self, request_type: str, duration: float):
        """跟踪请求时间"""
        if request_type not in self.request_times:
            self.request_times[request_type] = []
        self.request_times[request_type].append(duration)
        # 只保留最近100个记录
        if len(self.request_times[request_type]) > 100:
            self.request_times[request_type] = self.request_times[request_type][-100:]
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        stats = {
            'cache': self.cache.get_stats(),
            'resources': {
                'count': len(self.resource_manager.list_resources()),
                'details': self.resource_manager.list_resources()
            },
            'request_times': {}
        }
        
        # 计算请求时间统计
        for request_type, times in self.request_times.items():
            if times:
                stats['request_times'][request_type] = {
                    'count': len(times),
                    'average': sum(times) / len(times),
                    'min': min(times),
                    'max': max(times)
                }
        
        return stats
    
    def optimize(self, operation: str, **kwargs) -> Dict[str, Any]:
        """优化操作"""
        start_time = time.time()
        
        # 检查缓存
        cache_key = f"{operation}:{str(kwargs)}"
        cached_result = self.cache_get(cache_key)
        if cached_result:
            self.track_request_time(operation, time.time() - start_time)
            return {
                'result': cached_result,
                'from_cache': True,
                'time': time.time() - start_time
            }
        
        # 这里可以添加具体的优化逻辑
        # 例如：模型选择、批处理等
        
        result = kwargs.get('default_result', None)
        
        # 缓存结果
        if result is not None:
            self.cache_set(cache_key, result, CacheType.MODEL_OUTPUT)
        
        self.track_request_time(operation, time.time() - start_time)
        
        return {
            'result': result,
            'from_cache': False,
            'time': time.time() - start_time
        }
    
    def clear(self):
        """清理所有资源"""
        self.cache.clear()
        self.streaming_manager.clear_streams()
        self.resource_manager.clear_unused_resources()
        self.request_times.clear()


class ModelLoadBalancer:
    """模型负载均衡器"""
    
    def __init__(self):
        self.models: Dict[str, Dict[str, Any]] = {}
        self.request_counts: Dict[str, int] = {}
    
    def register_model(self, model_id: str, model_info: Dict[str, Any]):
        """注册模型"""
        self.models[model_id] = model_info
        self.request_counts[model_id] = 0
    
    def unregister_model(self, model_id: str):
        """注销模型"""
        if model_id in self.models:
            del self.models[model_id]
            del self.request_counts[model_id]
    
    def select_model(self, task_type: str, context_size: int) -> Optional[str]:
        """选择模型"""
        candidates = []
        
        for model_id, model_info in self.models.items():
            # 检查模型是否支持任务类型
            if task_type not in model_info.get('supported_tasks', []):
                continue
            
            # 检查上下文大小
            if context_size > model_info.get('max_context_size', 4096):
                continue
            
            # 计算分数：基于负载和性能
            score = 1.0 / (self.request_counts.get(model_id, 0) + 1)
            score *= model_info.get('performance_score', 1.0)
            
            candidates.append((score, model_id))
        
        if candidates:
            candidates.sort(reverse=True, key=lambda x: x[0])
            selected_model = candidates[0][1]
            self.request_counts[selected_model] += 1
            return selected_model
        
        return None
    
    def release_model(self, model_id: str):
        """释放模型"""
        if model_id in self.request_counts:
            self.request_counts[model_id] = max(0, self.request_counts[model_id] - 1)
    
    def get_model_stats(self) -> Dict[str, Any]:
        """获取模型统计"""
        stats = {}
        for model_id, model_info in self.models.items():
            stats[model_id] = {
                'requests': self.request_counts.get(model_id, 0),
                'info': model_info
            }
        return stats


def create_performance_optimizer() -> PerformanceOptimizer:
    """
    创建性能优化器
    
    Returns:
        PerformanceOptimizer: 性能优化器实例
    """
    return PerformanceOptimizer()


def create_model_load_balancer() -> ModelLoadBalancer:
    """
    创建模型负载均衡器
    
    Returns:
        ModelLoadBalancer: 模型负载均衡器实例
    """
    return ModelLoadBalancer()