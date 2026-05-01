"""
系统管理器 - System Manager

功能：
1. 统一管理所有子系统
2. 协调系统间通信
3. 生命周期管理
4. 状态监控
"""

import logging
import time
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class SystemState(Enum):
    """系统状态"""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    SHUTTING_DOWN = "shutting_down"
    ERROR = "error"


@dataclass
class SubsystemInfo:
    """子系统信息"""
    name: str
    module: Any
    initialized: bool = False
    status: SystemState = SystemState.UNINITIALIZED
    error: Optional[str] = None


class SystemManager:
    """
    系统管理器 - 统一管理所有AI代理子系统
    
    管理的子系统：
    1. 大脑启发记忆系统 (brain_memory)
    2. 自修复容错系统 (self_healing)
    3. 持续学习系统 (continual_learning)
    4. 认知推理系统 (cognitive_reasoning)
    5. 自我意识系统 (self_awareness)
    6. MCP服务 (mcp_service)
    7. API网关 (api_gateway)
    """
    
    def __init__(self):
        self._subsystems: Dict[str, SubsystemInfo] = {}
        self._state = SystemState.UNINITIALIZED
        self._api_gateway = None
        
        # 深度集成层组件
        self._event_bus = None
        self._cross_system_caller = None
        self._context_manager = None
        self._integration_coordinator = None
        
        # 系统初始化顺序（依赖顺序）
        self._init_order = [
            'brain_memory',
            'cognitive_reasoning',
            'continual_learning',
            'self_healing',
            'self_awareness',
            'mcp_service',
            'api_gateway'
        ]
        
        # 集成层初始化（最先初始化）
        self._init_integration_layer()
    
    def _init_integration_layer(self):
        """初始化深度集成层"""
        logger.info("初始化深度集成层...")
        
        try:
            from client.src.business.integration_layer import (
                get_event_bus,
                get_cross_system_caller,
                get_context_manager,
                get_integration_coordinator
            )
            
            self._event_bus = get_event_bus()
            self._cross_system_caller = get_cross_system_caller()
            self._context_manager = get_context_manager()
            self._integration_coordinator = get_integration_coordinator()
            
            # 注册系统事件监听器
            self._register_system_event_listeners()
            
            logger.info("深度集成层初始化完成")
        except Exception as e:
            logger.error(f"初始化深度集成层失败: {e}")
    
    def _register_system_event_listeners(self):
        """注册系统事件监听器"""
        from client.src.business.integration_layer import EventType
        
        # 监听子系统状态变化
        self._event_bus.subscribe(EventType.SUBSYSTEM_STATUS_CHANGED,
                                 self._on_subsystem_status_changed)
        
        # 监听MCP连接状态变化
        self._event_bus.subscribe(EventType.MCP_CONNECTED,
                                 self._on_mcp_connected)
        self._event_bus.subscribe(EventType.MCP_DISCONNECTED,
                                 self._on_mcp_disconnected)
        
        # 监听健康告警
        self._event_bus.subscribe(EventType.HEALTH_ALERT,
                                 self._on_health_alert)
    
    def _on_subsystem_status_changed(self, event):
        """处理子系统状态变化"""
        subsystem_name = event.data.get('name')
        status = event.data.get('status')
        
        logger.info(f"子系统状态变化: {subsystem_name} -> {status}")
        
        # 更新子系统状态
        if subsystem_name in self._subsystems:
            self._subsystems[subsystem_name].status = SystemState(status)
    
    def _on_mcp_connected(self, event):
        """处理MCP连接"""
        logger.info("MCP服务已连接")
        self._context_manager.set_feature_flag('mcp_enabled', True)
    
    def _on_mcp_disconnected(self, event):
        """处理MCP断开"""
        logger.warning("MCP服务已断开")
        self._context_manager.set_feature_flag('mcp_enabled', False)
        
        # 触发降级工作流
        self._integration_coordinator.handle_mcp_disconnect()
    
    def _on_health_alert(self, event):
        """处理健康告警"""
        issue = event.data
        logger.warning(f"健康告警: {issue}")
        
        # 触发问题解决工作流
        self._integration_coordinator.orchestrate_task('problem_solve',
                                                      issue=issue)
    
    def initialize(self):
        """初始化所有系统"""
        if self._state != SystemState.UNINITIALIZED:
            logger.warning("系统已初始化")
            return
        
        self._state = SystemState.INITIALIZING
        logger.info("开始初始化系统...")
        
        try:
            for subsystem_name in self._init_order:
                self._initialize_subsystem(subsystem_name)
            
            self._state = SystemState.RUNNING
            logger.info("所有系统初始化完成")
            
        except Exception as e:
            logger.error(f"系统初始化失败: {e}")
            self._state = SystemState.ERROR
    
    def _initialize_subsystem(self, name: str):
        """初始化单个子系统"""
        logger.info(f"初始化子系统: {name}")
        
        try:
            module = self._import_subsystem(name)
            
            if module:
                # 创建子系统实例
                instance = self._create_subsystem_instance(name, module)
                
                if instance:
                    # 启动子系统
                    if hasattr(instance, 'start'):
                        instance.start()
                    
                    # 注册到API网关
                    self._register_to_api_gateway(name, instance)
                    
                    # 记录状态
                    self._subsystems[name] = SubsystemInfo(
                        name=name,
                        module=instance,
                        initialized=True,
                        status=SystemState.RUNNING
                    )
                    
                    logger.info(f"子系统初始化成功: {name}")
                else:
                    self._subsystems[name] = SubsystemInfo(
                        name=name,
                        module=None,
                        initialized=False,
                        status=SystemState.ERROR,
                        error=f"无法创建实例: {name}"
                    )
            else:
                self._subsystems[name] = SubsystemInfo(
                    name=name,
                    module=None,
                    initialized=False,
                    status=SystemState.ERROR,
                    error=f"无法导入模块: {name}"
                )
                
        except Exception as e:
            logger.error(f"初始化子系统失败 {name}: {e}")
            self._subsystems[name] = SubsystemInfo(
                name=name,
                module=None,
                initialized=False,
                status=SystemState.ERROR,
                error=str(e)
            )
    
    def _import_subsystem(self, name: str) -> Optional[Any]:
        """导入子系统模块"""
        import importlib
        
        module_paths = {
            'brain_memory': 'client.src.business.brain_memory',
            'self_healing': 'client.src.business.self_healing',
            'continual_learning': 'client.src.business.continual_learning',
            'cognitive_reasoning': 'client.src.business.cognitive_reasoning',
            'self_awareness': 'client.src.business.self_awareness',
            'mcp_service': 'client.src.business.mcp_service',
            'api_gateway': 'client.src.business.api_gateway'
        }
        
        module_path = module_paths.get(name)
        if not module_path:
            return None
        
        try:
            return importlib.import_module(module_path)
        except ImportError as e:
            logger.warning(f"导入模块失败 {name}: {e}")
            return None
    
    def _create_subsystem_instance(self, name: str, module: Any) -> Optional[Any]:
        """创建子系统实例"""
        instance_map = {
            'brain_memory': lambda: module.MemoryRouter(),
            'self_healing': lambda: module.HealingRouter(),
            'continual_learning': lambda: module.LearningRouter(),
            'cognitive_reasoning': lambda: module.ReasoningCoordinator(),
            'self_awareness': lambda: module.SelfAwarenessSystem(),
            'mcp_service': lambda: module.get_mcp_manager(),
            'api_gateway': lambda: module.get_api_gateway()
        }
        
        creator = instance_map.get(name)
        if creator:
            try:
                return creator()
            except Exception as e:
                logger.error(f"创建实例失败 {name}: {e}")
                return None
        
        return None
    
    def _register_to_api_gateway(self, name: str, instance: Any):
        """注册到API网关"""
        if self._api_gateway is None:
            from client.src.business.api_gateway import get_api_gateway
            self._api_gateway = get_api_gateway()
        
        try:
            self._api_gateway.register_module(name, instance)
        except Exception as e:
            logger.warning(f"注册到API网关失败 {name}: {e}")
    
    def shutdown(self):
        """关闭所有系统"""
        self._state = SystemState.SHUTTING_DOWN
        logger.info("开始关闭系统...")
        
        # 逆序关闭
        for name in reversed(self._init_order):
            self._shutdown_subsystem(name)
        
        self._state = SystemState.UNINITIALIZED
        logger.info("所有系统已关闭")
    
    def _shutdown_subsystem(self, name: str):
        """关闭单个子系统"""
        info = self._subsystems.get(name)
        if not info or not info.initialized:
            return
        
        try:
            if hasattr(info.module, 'stop'):
                info.module.stop()
            logger.info(f"子系统已关闭: {name}")
        except Exception as e:
            logger.error(f"关闭子系统失败 {name}: {e}")
    
    def get_subsystem(self, name: str) -> Optional[Any]:
        """获取子系统实例"""
        info = self._subsystems.get(name)
        if info and info.initialized:
            return info.module
        return None
    
    def get_status(self) -> Dict:
        """获取系统状态"""
        return {
            'system_state': self._state.value,
            'subsystems': {
                name: {
                    'initialized': info.initialized,
                    'status': info.status.value,
                    'error': info.error
                }
                for name, info in self._subsystems.items()
            }
        }
    
    def get_subsystem_status(self, name: str) -> Dict:
        """获取子系统状态"""
        info = self._subsystems.get(name)
        if info:
            # 尝试获取更详细的状态
            if info.initialized and hasattr(info.module, 'get_status'):
                try:
                    return info.module.get_status()
                except Exception as e:
                    return {'error': str(e)}
            else:
                return {
                    'initialized': info.initialized,
                    'status': info.status.value,
                    'error': info.error
                }
        return {'error': '子系统不存在'}
    
    def call_subsystem(self, subsystem_name: str, method: str, **kwargs) -> Any:
        """调用子系统方法"""
        subsystem = self.get_subsystem(subsystem_name)
        if not subsystem:
            return {'success': False, 'error': f"子系统未初始化: {subsystem_name}"}
        
        if not hasattr(subsystem, method):
            return {'success': False, 'error': f"方法不存在: {method}"}
        
        try:
            func = getattr(subsystem, method)
            result = func(**kwargs)
            return {'success': True, 'data': result}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def is_running(self) -> bool:
        """检查系统是否运行中"""
        return self._state == SystemState.RUNNING
    
    def get_active_subsystems(self) -> List[str]:
        """获取活跃子系统列表"""
        return [name for name, info in self._subsystems.items() 
                if info.initialized and info.status == SystemState.RUNNING]


# 单例模式
_manager_instance = None

def get_system_manager() -> SystemManager:
    """获取系统管理器实例"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = SystemManager()
    return _manager_instance