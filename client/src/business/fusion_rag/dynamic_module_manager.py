"""
动态模块管理器 (Dynamic Module Manager)
========================================

实现模块的动态注册、注销和更新：
1. 模块动态注册/注销
2. 版本更新（无需重启）
3. 优雅资源清理

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

import asyncio
import importlib
import sys
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class ModuleState(Enum):
    """模块状态"""
    INITIALIZING = "initializing"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class RegisteredModule:
    """已注册模块"""
    name: str
    module_type: str
    instance: Any
    version: str = "1.0.0"
    state: ModuleState = ModuleState.RUNNING
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    stop_callback: Optional[Callable] = None


class DynamicModuleManager:
    """
    动态模块管理器
    
    支持模块的热更新和动态管理：
    - 动态注册模块
    - 动态注销模块
    - 模块版本更新
    - 优雅资源清理
    """
    
    def __init__(self):
        """初始化管理器"""
        self._modules: Dict[str, RegisteredModule] = {}
        self._modules_by_type: Dict[str, List[str]] = {}
        self._update_lock = asyncio.Lock()
        
    async def register_module(
        self,
        name: str,
        module_type: str,
        instance: Any,
        version: str = "1.0.0",
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        stop_callback: Optional[Callable] = None
    ) -> bool:
        """
        注册模块
        
        Args:
            name: 模块名称
            module_type: 模块类型
            instance: 模块实例
            version: 版本号
            dependencies: 依赖模块列表
            metadata: 元数据
            stop_callback: 停止回调函数
            
        Returns:
            是否注册成功
        """
        async with self._update_lock:
            if name in self._modules:
                logger.warning(f"[DynamicModuleManager] 模块已存在: {name}")
                return False
                
            # 检查依赖是否满足
            if dependencies:
                for dep in dependencies:
                    if dep not in self._modules:
                        logger.warning(f"[DynamicModuleManager] 模块 {name} 缺少依赖: {dep}")
                        return False
                        
            module = RegisteredModule(
                name=name,
                module_type=module_type,
                instance=instance,
                version=version,
                dependencies=dependencies or [],
                metadata=metadata or {},
                stop_callback=stop_callback
            )
            
            self._modules[name] = module
            
            # 按类型分组
            if module_type not in self._modules_by_type:
                self._modules_by_type[module_type] = []
            self._modules_by_type[module_type].append(name)
            
            logger.info(f"[DynamicModuleManager] 模块注册成功: {name} v{version} ({module_type})")
            return True
            
    async def unregister_module(self, name: str) -> bool:
        """
        注销模块
        
        Args:
            name: 模块名称
            
        Returns:
            是否注销成功
        """
        async with self._update_lock:
            if name not in self._modules:
                logger.warning(f"[DynamicModuleManager] 模块不存在: {name}")
                return False
                
            module = self._modules[name]
            
            # 检查是否有其他模块依赖此模块
            for other_name, other_module in self._modules.items():
                if name in other_module.dependencies:
                    logger.warning(f"[DynamicModuleManager] 模块 {name} 被 {other_name} 依赖，无法注销")
                    return False
                    
            # 优雅停止模块
            module.state = ModuleState.STOPPING
            
            try:
                if module.stop_callback:
                    await module.stop_callback()
                elif hasattr(module.instance, 'stop'):
                    await module.instance.stop()
                elif hasattr(module.instance, '__del__'):
                    pass
            except Exception as e:
                logger.warning(f"[DynamicModuleManager] 模块 {name} 停止失败: {e}")
                
            module.state = ModuleState.STOPPED
            
            # 从注册表中移除
            del self._modules[name]
            module_type = module.module_type
            if module_type in self._modules_by_type and name in self._modules_by_type[module_type]:
                self._modules_by_type[module_type].remove(name)
                
            logger.info(f"[DynamicModuleManager] 模块注销成功: {name}")
            return True
            
    async def update_module(self, name: str, new_version: str, new_instance: Any) -> bool:
        """
        更新模块版本
        
        Args:
            name: 模块名称
            new_version: 新版本号
            new_instance: 新模块实例
            
        Returns:
            是否更新成功
        """
        async with self._update_lock:
            if name not in self._modules:
                logger.warning(f"[DynamicModuleManager] 模块不存在: {name}")
                return False
                
            old_module = self._modules[name]
            
            # 优雅停止旧模块
            old_module.state = ModuleState.STOPPING
            
            try:
                if old_module.stop_callback:
                    await old_module.stop_callback()
                elif hasattr(old_module.instance, 'stop'):
                    await old_module.instance.stop()
            except Exception as e:
                logger.warning(f"[DynamicModuleManager] 旧模块停止失败: {e}")
                
            # 创建新模块
            new_module = RegisteredModule(
                name=name,
                module_type=old_module.module_type,
                instance=new_instance,
                version=new_version,
                dependencies=old_module.dependencies,
                metadata=old_module.metadata,
                stop_callback=old_module.stop_callback
            )
            
            new_module.state = ModuleState.RUNNING
            self._modules[name] = new_module
            
            logger.info(f"[DynamicModuleManager] 模块更新成功: {name} v{old_module.version} -> v{new_version}")
            return True
            
    def get_module(self, name: str) -> Optional[RegisteredModule]:
        """
        获取模块信息
        
        Args:
            name: 模块名称
            
        Returns:
            模块信息，如果不存在返回 None
        """
        return self._modules.get(name)
        
    def get_modules_by_type(self, module_type: str) -> List[str]:
        """
        获取指定类型的模块列表
        
        Args:
            module_type: 模块类型
            
        Returns:
            模块名称列表
        """
        return self._modules_by_type.get(module_type, [])
        
    def get_all_modules(self) -> List[Dict[str, Any]]:
        """获取所有模块信息"""
        result = []
        for name, module in self._modules.items():
            result.append({
                'name': name,
                'type': module.module_type,
                'version': module.version,
                'state': module.state.value,
                'dependencies': module.dependencies
            })
        return result
        
    def is_module_running(self, name: str) -> bool:
        """检查模块是否正在运行"""
        module = self._modules.get(name)
        return module is not None and module.state == ModuleState.RUNNING
        
    async def _dynamic_import(self, module_path: str, class_name: str) -> Optional[Any]:
        """
        动态导入模块
        
        Args:
            module_path: 模块路径
            class_name: 类名
            
        Returns:
            类对象，如果导入失败返回 None
        """
        try:
            module = importlib.import_module(module_path)
            return getattr(module, class_name, None)
        except ImportError as e:
            logger.warning(f"[DynamicModuleManager] 动态导入失败 {module_path}.{class_name}: {e}")
            return None
