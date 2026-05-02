"""
MCP管理器 - MCP Manager

功能：
1. 统一管理多个MCP服务
2. 服务注册与发现
3. 负载均衡
4. 故障转移
5. 降级策略管理
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MCPMode(Enum):
    """MCP运行模式"""
    DISABLED = "disabled"      # 禁用MCP
    LOCAL = "local"           # 本地进程
    REMOTE = "remote"         # 远程服务
    HYBRID = "hybrid"         # 混合模式


@dataclass
class ToolCallRecord:
    """工具调用记录"""
    tool_name: str
    success: bool
    execution_time: float
    used_fallback: bool
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class MCPManager:
    """
    MCP管理器 - 统一管理MCP服务
    
    核心功能：
    1. 服务生命周期管理
    2. 工具调用路由
    3. 自动降级
    4. 性能监控
    """
    
    def __init__(self):
        self._mode = MCPMode.LOCAL
        self._client = None
        self._fallback_system = None
        self._service_registry = None
        
        # 调用记录
        self._call_history: List[ToolCallRecord] = []
        self._max_history = 100
        
        # 性能统计
        self._stats = {
            'total_calls': 0,
            'success_calls': 0,
            'failed_calls': 0,
            'fallback_calls': 0,
            'avg_execution_time': 0.0
        }
    
    def _init_components(self):
        """延迟初始化组件"""
        if self._client is None:
            from .mcp_client import MCPClient
            from .fallback_system import FallbackSystem
            from .service_registry import ServiceRegistry
            
            self._client = MCPClient()
            self._fallback_system = FallbackSystem()
            self._service_registry = ServiceRegistry()
    
    def start(self, mode: str = "local"):
        """
        启动MCP管理器
        
        Args:
            mode: 运行模式 (disabled/local/remote/hybrid)
        """
        self._init_components()
        
        try:
            self._mode = MCPMode(mode.lower())
        except ValueError:
            self._mode = MCPMode.LOCAL
        
        if self._mode == MCPMode.DISABLED:
            logger.info("MCP服务已禁用，将使用降级方案")
            return
        
        # 尝试连接MCP服务
        success = self._client.connect(mode=self._get_connection_mode())
        
        if success:
            logger.info("MCP服务连接成功")
            self._publish_mcp_event('connected')
        else:
            logger.warning("MCP服务连接失败，自动切换到降级模式")
            self._mode = MCPMode.DISABLED
            self._publish_mcp_event('disconnected')
    
    def _get_connection_mode(self) -> str:
        """获取连接模式"""
        mode_map = {
            MCPMode.LOCAL: "subprocess",
            MCPMode.REMOTE: "tcp",
            MCPMode.HYBRID: "subprocess"
        }
        return mode_map.get(self._mode, "subprocess")
    
    def call_tool(self, tool_name: str, **kwargs) -> Dict:
        """
        调用工具（统一入口）
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
        
        Returns:
            调用结果
        """
        start_time = time.time()
        
        # 检查是否禁用MCP
        if self._mode == MCPMode.DISABLED:
            result = self._call_fallback(tool_name, **kwargs)
            execution_time = time.time() - start_time
            self._record_call(tool_name, result['success'], execution_time, True)
            return result
        
        # 检查服务状态
        status = self._client.get_status()
        if status.value != "connected":
            # 尝试重新连接
            if self._try_reconnect():
                return self.call_tool(tool_name, **kwargs)
            else:
                # 使用降级方案
                result = self._call_fallback(tool_name, **kwargs)
                execution_time = time.time() - start_time
                self._record_call(tool_name, result['success'], execution_time, True)
                return result
        
        # 调用MCP工具
        try:
            result = self._client.call_tool(tool_name, **kwargs)
            execution_time = time.time() - start_time
            
            if result.get('success'):
                self._record_call(tool_name, True, execution_time, False)
                return result
            else:
                # MCP调用失败，尝试降级
                logger.warning(f"MCP工具调用失败: {tool_name}")
                fallback_result = self._call_fallback(tool_name, **kwargs)
                self._record_call(tool_name, fallback_result['success'], execution_time, True)
                return fallback_result
        
        except Exception as e:
            logger.error(f"MCP调用异常 {tool_name}: {e}")
            result = self._call_fallback(tool_name, **kwargs)
            execution_time = time.time() - start_time
            self._record_call(tool_name, result['success'], execution_time, True)
            return result
    
    def _try_reconnect(self) -> bool:
        """尝试重新连接MCP服务"""
        try:
            logger.info("尝试重新连接MCP服务...")
            return self._client.connect(mode=self._get_connection_mode())
        except Exception as e:
            logger.error(f"重新连接失败: {e}")
            return False
    
    def _call_fallback(self, tool_name: str, **kwargs) -> Dict:
        """调用降级方案"""
        if self._fallback_system is None:
            self._init_components()
        
        return self._fallback_system.execute_fallback(tool_name, **kwargs)
    
    def _record_call(self, tool_name: str, success: bool, execution_time: float, used_fallback: bool):
        """记录调用"""
        self._stats['total_calls'] += 1
        
        if success:
            self._stats['success_calls'] += 1
        else:
            self._stats['failed_calls'] += 1
        
        if used_fallback:
            self._stats['fallback_calls'] += 1
        
        # 更新平均执行时间
        self._stats['avg_execution_time'] = (
            self._stats['avg_execution_time'] * (self._stats['total_calls'] - 1) + execution_time
        ) / self._stats['total_calls']
        
        # 记录历史
        self._call_history.append(ToolCallRecord(
            tool_name=tool_name,
            success=success,
            execution_time=execution_time,
            used_fallback=used_fallback
        ))
        
        # 限制历史大小
        if len(self._call_history) > self._max_history:
            self._call_history = self._call_history[-self._max_history:]
    
    def stop(self):
        """停止MCP管理器"""
        # 发布断开连接事件
        self._publish_mcp_event('disconnected')
        
        if self._client:
            self._client.disconnect()
        logger.info("MCP管理器已停止")
    
    def _publish_mcp_event(self, event_type: str):
        """发布MCP事件"""
        try:
            from livingtree.core.integration.event_bus import EventType, publish
            
            if event_type == 'connected':
                publish(EventType.MCP_CONNECTED, 'mcp_service', {
                    'mode': self._mode.value
                })
            else:
                publish(EventType.MCP_DISCONNECTED, 'mcp_service', {
                    'mode': self._mode.value
                })
        except ImportError:
            pass
    
    def get_status(self) -> Dict:
        """获取状态"""
        return {
            'mode': self._mode.value,
            'service_status': self._client.get_status().value if self._client else 'unknown',
            'stats': self._get_stats()
        }
    
    def _get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self._stats,
            'success_rate': self._stats['success_calls'] / self._stats['total_calls'] if self._stats['total_calls'] > 0 else 0,
            'fallback_rate': self._stats['fallback_calls'] / self._stats['total_calls'] if self._stats['total_calls'] > 0 else 0,
            'history_count': len(self._call_history)
        }
    
    def set_mode(self, mode: str):
        """设置运行模式"""
        self._mode = MCPMode(mode.lower())
        logger.info(f"MCP模式已切换为: {mode}")
    
    def register_fallback(self, tool_name: str, fallback_func):
        """注册降级函数"""
        if self._fallback_system is None:
            self._init_components()
        
        self._fallback_system.register_fallback(tool_name, fallback_func)


# 单例模式
_manager_instance = None

def get_mcp_manager() -> MCPManager:
    """获取MCP管理器实例"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = MCPManager()
    return _manager_instance