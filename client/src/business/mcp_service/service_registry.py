"""
服务注册中心 - Service Registry

功能：
1. 服务注册与发现
2. 服务健康检查
3. 服务元数据管理
4. 动态服务配置
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ServiceType(Enum):
    """服务类型"""
    MCP = "mcp"
    API = "api"
    DATABASE = "database"
    CACHE = "cache"
    MESSAGE = "message"
    OTHER = "other"


class ServiceStatus(Enum):
    """服务状态"""
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass
class ServiceInfo:
    """服务信息"""
    name: str
    type: ServiceType
    host: str
    port: int
    status: ServiceStatus = ServiceStatus.UNKNOWN
    metadata: Dict = None
    registered_at: float = None
    last_heartbeat: float = None
    priority: int = 0
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.registered_at is None:
            self.registered_at = time.time()
        if self.last_heartbeat is None:
            self.last_heartbeat = time.time()


class ServiceRegistry:
    """
    服务注册中心
    
    核心功能：
    1. 服务注册
    2. 服务发现
    3. 健康检查
    4. 负载均衡
    """
    
    def __init__(self):
        self._services: Dict[str, ServiceInfo] = {}
        self._services_by_type: Dict[str, List[str]] = {}
        self._heartbeat_interval = 30  # 心跳间隔（秒）
        self._heartbeat_timeout = 60   # 心跳超时（秒）
    
    def register_service(self, name: str, service_type: ServiceType, 
                        host: str, port: int, metadata: Dict = None) -> bool:
        """
        注册服务
        
        Args:
            name: 服务名称
            service_type: 服务类型
            host: 主机地址
            port: 端口号
            metadata: 元数据
        
        Returns:
            是否成功
        """
        if name in self._services:
            logger.warning(f"服务已存在: {name}")
            return False
        
        service = ServiceInfo(
            name=name,
            type=service_type,
            host=host,
            port=port,
            status=ServiceStatus.UP,
            metadata=metadata or {}
        )
        
        self._services[name] = service
        
        # 按类型索引
        type_key = service_type.value
        if type_key not in self._services_by_type:
            self._services_by_type[type_key] = []
        self._services_by_type[type_key].append(name)
        
        logger.info(f"服务注册成功: {name} ({host}:{port})")
        return True
    
    def unregister_service(self, name: str) -> bool:
        """
        注销服务
        
        Args:
            name: 服务名称
        
        Returns:
            是否成功
        """
        service = self._services.get(name)
        if not service:
            return False
        
        # 从类型索引中移除
        type_key = service.type.value
        if type_key in self._services_by_type:
            self._services_by_type[type_key].remove(name)
        
        del self._services[name]
        logger.info(f"服务注销: {name}")
        return True
    
    def get_service(self, name: str) -> Optional[ServiceInfo]:
        """
        获取服务信息
        
        Args:
            name: 服务名称
        
        Returns:
            服务信息
        """
        return self._services.get(name)
    
    def get_services_by_type(self, service_type: ServiceType) -> List[ServiceInfo]:
        """
        按类型获取服务
        
        Args:
            service_type: 服务类型
        
        Returns:
            服务列表
        """
        type_key = service_type.value
        names = self._services_by_type.get(type_key, [])
        return [self._services[name] for name in names]
    
    def get_all_services(self) -> List[ServiceInfo]:
        """获取所有服务"""
        return list(self._services.values())
    
    def update_heartbeat(self, name: str) -> bool:
        """
        更新心跳
        
        Args:
            name: 服务名称
        
        Returns:
            是否成功
        """
        service = self._services.get(name)
        if not service:
            return False
        
        service.last_heartbeat = time.time()
        service.status = ServiceStatus.UP
        return True
    
    def check_health(self) -> Dict[str, ServiceStatus]:
        """
        检查所有服务健康状态
        
        Returns:
            服务状态字典
        """
        results = {}
        current_time = time.time()
        
        for name, service in self._services.items():
            if current_time - service.last_heartbeat > self._heartbeat_timeout:
                service.status = ServiceStatus.DOWN
                logger.warning(f"服务心跳超时: {name}")
            results[name] = service.status
        
        return results
    
    def get_available_services(self, service_type: ServiceType = None) -> List[ServiceInfo]:
        """
        获取可用服务
        
        Args:
            service_type: 服务类型（可选）
        
        Returns:
            可用服务列表
        """
        if service_type:
            services = self.get_services_by_type(service_type)
        else:
            services = self.get_all_services()
        
        return [s for s in services if s.status == ServiceStatus.UP]
    
    def select_service(self, service_type: ServiceType) -> Optional[ServiceInfo]:
        """
        选择服务（简单负载均衡）
        
        Args:
            service_type: 服务类型
        
        Returns:
            选中的服务
        """
        available = self.get_available_services(service_type)
        
        if not available:
            return None
        
        # 按优先级排序，然后选择第一个
        available.sort(key=lambda s: s.priority, reverse=True)
        return available[0]
    
    def update_service_metadata(self, name: str, metadata: Dict):
        """
        更新服务元数据
        
        Args:
            name: 服务名称
            metadata: 元数据
        """
        service = self._services.get(name)
        if service:
            service.metadata.update(metadata)
    
    def get_service_count(self) -> int:
        """获取服务数量"""
        return len(self._services)
    
    def is_service_available(self, name: str) -> bool:
        """检查服务是否可用"""
        service = self._services.get(name)
        return service is not None and service.status == ServiceStatus.UP