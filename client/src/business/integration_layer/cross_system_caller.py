"""
跨系统调用器 - Cross System Caller

功能：
1. 统一跨系统调用接口
2. 自动路由到目标系统
3. 调用缓存与重试
4. 异步调用支持
"""

import logging
import time
from typing import Dict, Any, Optional, Callable
from functools import wraps

logger = logging.getLogger(__name__)


class CrossSystemCaller:
    """
    跨系统调用器 - 实现系统间方法调用
    
    核心能力：
    1. 动态路由到目标子系统
    2. 参数验证
    3. 调用缓存
    4. 异常处理与重试
    5. 异步调用支持
    """
    
    def __init__(self):
        self._system_manager = None
        self._call_cache: Dict[str, Any] = {}
        self._cache_ttl = 60  # 缓存有效期（秒）
        self._max_retries = 2
    
    def _get_system_manager(self):
        """延迟获取系统管理器"""
        if self._system_manager is None:
            from livingtree.core.integration.system_manager import get_system_manager
            self._system_manager = get_system_manager()
        return self._system_manager
    
    def call(self, system_name: str, method_name: str, **kwargs) -> Dict:
        """
        同步调用子系统方法
        
        Args:
            system_name: 子系统名称
            method_name: 方法名称
            **kwargs: 方法参数
        
        Returns:
            调用结果
        """
        start_time = time.time()
        
        # 检查缓存
        cache_key = f"{system_name}_{method_name}_{hash(frozenset(kwargs.items()))}"
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            return cached_result
        
        try:
            manager = self._get_system_manager()
            subsystem = manager.get_subsystem(system_name)
            
            if not subsystem:
                return {
                    'success': False,
                    'error': f"子系统未找到或未初始化: {system_name}"
                }
            
            if not hasattr(subsystem, method_name):
                return {
                    'success': False,
                    'error': f"方法不存在: {method_name}"
                }
            
            method = getattr(subsystem, method_name)
            
            # 执行调用（带重试）
            result = self._call_with_retry(method, kwargs)
            
            if result.get('success', True):
                self._cache_result(cache_key, result)
            
            execution_time = time.time() - start_time
            logger.debug(f"跨系统调用 {system_name}.{method_name} 耗时: {execution_time:.3f}s")
            
            return result
        
        except Exception as e:
            logger.error(f"跨系统调用失败 {system_name}.{method_name}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _call_with_retry(self, method: Callable, kwargs: Dict, retry_count: int = 0) -> Any:
        """带重试的调用"""
        try:
            result = method(**kwargs)
            
            # 如果返回的是字典，检查success字段
            if isinstance(result, dict) and not result.get('success', True):
                raise Exception(result.get('error', '调用失败'))
            
            return {'success': True, 'data': result}
        
        except Exception as e:
            if retry_count < self._max_retries:
                time.sleep(0.5 * (retry_count + 1))
                return self._call_with_retry(method, kwargs, retry_count + 1)
            
            return {'success': False, 'error': str(e)}
    
    def async_call(self, system_name: str, method_name: str, callback: Optional[Callable] = None, **kwargs):
        """
        异步调用子系统方法
        
        Args:
            system_name: 子系统名称
            method_name: 方法名称
            callback: 回调函数
            **kwargs: 方法参数
        """
        import threading
        
        def worker():
            result = self.call(system_name, method_name, **kwargs)
            if callback:
                try:
                    callback(result)
                except Exception as e:
                    logger.error(f"异步调用回调失败: {e}")
        
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict]:
        """获取缓存结果"""
        entry = self._call_cache.get(cache_key)
        if entry:
            timestamp, data = entry
            if time.time() - timestamp < self._cache_ttl:
                return data
            else:
                del self._call_cache[cache_key]
        return None
    
    def _cache_result(self, cache_key: str, result: Dict):
        """缓存结果"""
        self._call_cache[cache_key] = (time.time(), result)
        
        # 限制缓存大小
        max_cache_size = 500
        if len(self._call_cache) > max_cache_size:
            # 删除最旧的
            oldest_key = min(self._call_cache.keys(), key=lambda k: self._call_cache[k][0])
            del self._call_cache[oldest_key]
    
    def clear_cache(self):
        """清空缓存"""
        self._call_cache.clear()
    
    def get_cached_methods(self) -> list:
        """获取缓存的方法列表"""
        return list(self._call_cache.keys())


# 单例模式
_caller_instance = None

def get_cross_system_caller() -> CrossSystemCaller:
    """获取跨系统调用器实例"""
    global _caller_instance
    if _caller_instance is None:
        _caller_instance = CrossSystemCaller()
    return _caller_instance


def cross_system_call(system_name: str, method_name: str):
    """
    装饰器：自动调用跨系统方法
    
    Usage:
        @cross_system_call('brain_memory', 'store_short_term')
        def store_memory(content, metadata):
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            caller = get_cross_system_caller()
            return caller.call(system_name, method_name, **kwargs)
        return wrapper
    return decorator