"""
降级系统 - Fallback System

功能：
1. 注册降级方案
2. 执行降级逻辑
3. 管理降级策略
4. 无MCP时平滑降级
"""

import logging
import time
import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class FallbackStrategy(Enum):
    """降级策略"""
    NONE = "none"              # 无降级
    LOCAL_TOOL = "local_tool"  # 使用本地工具
    SIMULATED = "simulated"    # 模拟结果
    CACHED = "cached"          # 使用缓存
    ERROR_MESSAGE = "error"    # 返回错误消息


@dataclass
class FallbackConfig:
    """降级配置"""
    tool_name: str
    strategy: FallbackStrategy
    handler: Callable = None
    description: str = ""
    enabled: bool = True


class FallbackSystem:
    """
    降级系统 - 无MCP时的优雅降级
    
    核心能力：
    1. 注册降级处理器
    2. 执行降级逻辑
    3. 缓存结果
    4. 模拟工具调用
    """
    
    def __init__(self):
        self._fallbacks: Dict[str, FallbackConfig] = {}
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 300  # 缓存有效期（秒）
        
        # 注册默认降级方案
        self._register_default_fallbacks()
    
    def _register_default_fallbacks(self):
        """注册默认降级方案"""
        # 搜索工具降级
        self.register_fallback("web_search", self._web_search_fallback, 
                             description="网络搜索降级", 
                             strategy=FallbackStrategy.SIMULATED)
        
        # 计算器工具降级
        self.register_fallback("calculator", self._calculator_fallback,
                             description="计算器降级",
                             strategy=FallbackStrategy.LOCAL_TOOL)
        
        # 文件工具降级
        self.register_fallback("file_read", self._file_read_fallback,
                             description="文件读取降级",
                             strategy=FallbackStrategy.LOCAL_TOOL)
        
        # 代码执行降级
        self.register_fallback("code_execution", self._code_execution_fallback,
                             description="代码执行降级",
                             strategy=FallbackStrategy.SIMULATED)
        
        # 浏览器工具降级
        self.register_fallback("browser", self._browser_fallback,
                             description="浏览器降级",
                             strategy=FallbackStrategy.SIMULATED)
    
    def register_fallback(self, tool_name: str, handler: Callable, 
                         description: str = "", 
                         strategy: FallbackStrategy = FallbackStrategy.SIMULATED):
        """
        注册降级处理器
        
        Args:
            tool_name: 工具名称
            handler: 降级处理函数
            description: 描述
            strategy: 降级策略
        """
        self._fallbacks[tool_name] = FallbackConfig(
            tool_name=tool_name,
            strategy=strategy,
            handler=handler,
            description=description,
            enabled=True
        )
        logger.info(f"注册降级方案: {tool_name}")
    
    def execute_fallback(self, tool_name: str, **kwargs) -> Dict:
        """
        执行降级方案
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
        
        Returns:
            降级结果
        """
        start_time = time.time()
        
        # 检查缓存
        cache_key = self._generate_cache_key(tool_name, kwargs)
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            execution_time = time.time() - start_time
            return {
                'success': True,
                'content': cached_result,
                'tool_name': tool_name,
                'used_fallback': True,
                'execution_time': execution_time,
                'source': 'cache'
            }
        
        # 获取降级配置
        fallback_config = self._fallbacks.get(tool_name)
        if not fallback_config or not fallback_config.enabled:
            return {
                'success': False,
                'error': f"工具 {tool_name} 不可用",
                'used_fallback': True,
                'execution_time': time.time() - start_time
            }
        
        # 执行降级处理
        try:
            result = fallback_config.handler(**kwargs)
            execution_time = time.time() - start_time
            
            # 缓存结果
            if result.get('success'):
                self._cache_result(cache_key, result.get('content'))
            
            return {
                'success': result.get('success', False),
                'content': result.get('content', ''),
                'tool_name': tool_name,
                'used_fallback': True,
                'execution_time': execution_time,
                'source': 'fallback'
            }
        
        except Exception as e:
            logger.error(f"降级执行失败 {tool_name}: {e}")
            return {
                'success': False,
                'error': str(e),
                'tool_name': tool_name,
                'used_fallback': True,
                'execution_time': time.time() - start_time
            }
    
    def _generate_cache_key(self, tool_name: str, kwargs: Dict) -> str:
        """生成缓存键"""
        args_hash = hash(frozenset(kwargs.items()))
        return f"{tool_name}_{args_hash}"
    
    def _get_cached_result(self, cache_key: str) -> Optional[Any]:
        """获取缓存结果"""
        entry = self._cache.get(cache_key)
        if entry:
            timestamp, data = entry
            if time.time() - timestamp < self._cache_ttl:
                return data
            else:
                # 缓存过期
                del self._cache[cache_key]
        return None
    
    def _cache_result(self, cache_key: str, data: Any):
        """缓存结果"""
        self._cache[cache_key] = (time.time(), data)
        
        # 限制缓存大小
        max_cache_size = 100
        if len(self._cache) > max_cache_size:
            # 删除最旧的
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][0])
            del self._cache[oldest_key]
    
    def _web_search_fallback(self, **kwargs) -> Dict:
        """网络搜索降级"""
        query = kwargs.get('query', '')
        return {
            'success': True,
            'content': {
                'results': [
                    {
                        'title': f"搜索结果: {query}",
                        'url': "#",
                        'snippet': "由于MCP服务不可用，无法执行真实搜索。请确保MCP服务已启动或切换到本地搜索模式。"
                    }
                ],
                'fallback_message': "MCP服务不可用，显示模拟搜索结果"
            }
        }
    
    def _calculator_fallback(self, **kwargs) -> Dict:
        """计算器降级（使用本地计算）"""
        expression = kwargs.get('expression', '')
        
        try:
            # 安全计算（限制表达式复杂度）
            if len(expression) > 100:
                raise ValueError("表达式过长")
            
            # 限制允许的操作
            allowed_chars = set('0123456789+-*/(). ')
            if not all(c in allowed_chars for c in expression):
                raise ValueError("包含非法字符")
            
            # 使用eval进行计算（谨慎使用）
            result = eval(expression)
            
            return {
                'success': True,
                'content': {
                    'result': result,
                    'expression': expression,
                    'source': 'local_calculator'
                }
            }
        except Exception as e:
            return {
                'success': False,
                'content': {'error': str(e)}
            }
    
    def _file_read_fallback(self, **kwargs) -> Dict:
        """文件读取降级"""
        file_path = kwargs.get('path', '')
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(10000)  # 限制读取大小
            
            return {
                'success': True,
                'content': {
                    'content': content,
                    'path': file_path,
                    'truncated': len(content) >= 10000
                }
            }
        except Exception as e:
            return {
                'success': False,
                'content': {'error': str(e)}
            }
    
    def _code_execution_fallback(self, **kwargs) -> Dict:
        """代码执行降级"""
        return {
            'success': True,
            'content': {
                'output': "代码执行需要MCP服务。由于服务不可用，无法执行代码。",
                'fallback_message': "MCP服务不可用，代码执行已禁用"
            }
        }
    
    def _browser_fallback(self, **kwargs) -> Dict:
        """浏览器工具降级"""
        return {
            'success': True,
            'content': {
                'message': "浏览器自动化需要MCP服务。请启动MCP服务以启用浏览器功能。",
                'fallback_message': "MCP服务不可用，浏览器功能已禁用"
            }
        }
    
    def get_registered_fallbacks(self) -> List[str]:
        """获取已注册的降级方案"""
        return list(self._fallbacks.keys())
    
    def is_fallback_available(self, tool_name: str) -> bool:
        """检查降级方案是否可用"""
        fallback = self._fallbacks.get(tool_name)
        return fallback is not None and fallback.enabled